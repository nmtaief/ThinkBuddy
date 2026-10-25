"""Chat orchestrator managing query understanding, RAG retrieval, SSE streaming, and guardrails.

Implements Deliverables from thinkbuddy-docs/prompts/P05_rag_chat_streaming.md:
- Query classification (study question vs off-topic vs unsafe vs quiz integrity)
- Secure quiz active lockout enforcement
- Entitlement & daily quota checking
- Hybrid retrieval with chapter/page boosting
- SSE streaming with client disconnect cancellation (docs/04_API_CONTRACT.md §3)
- Authoritative page number citation guarantees (Rule 7 & 8: printed_page != pdf_page_index)
- Low confidence fallback ("not found in your textbook")
- Async persistence and learning signal emission (ai_question / ai_repeat)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.chat.llm import LLMGateway, MockLLMGateway
from core.chat.retriever import CONFIDENCE_THRESHOLD, ChatRetriever
from core.chat.schemas import (
    ChatCitationItem,
    ChatMessageCreateRequest,
    ChatMessageResponse,
)
from core.chat.service import ChatService
from core.quiz.integrity import IntegrityEngine
from core.quiz.models import OPEN_ATTEMPT_STATES, AttemptEvent, Quiz, QuizAttempt
from core.quiz.service import QuizService

logger = logging.getLogger(__name__)


class ChatOrchestrator:
    """End-to-end chat orchestrator running guardrails, retrieval, LLM streaming, and citations."""

    def __init__(
        self,
        db: AsyncSession,
        retriever: ChatRetriever | None = None,
        llm_gateway: LLMGateway | None = None,
        chat_service: ChatService | None = None,
    ) -> None:
        self.db = db
        self.retriever = retriever or ChatRetriever(db)
        self.llm_gateway = llm_gateway or MockLLMGateway()
        self.chat_service = chat_service or ChatService(db)

    async def assert_no_active_assessed_quiz(self, student_id: uuid.UUID) -> None:
        """Lockout chat during active assessed quiz attempts per docs/05_SECURE_QUIZ.md §2."""
        quiz_service = QuizService(self.db)
        is_active = await quiz_service.is_assessed_attempt_active(student_id)
        if is_active:
            stmt = (
                select(QuizAttempt)
                .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
                .where(
                    QuizAttempt.student_id == student_id,
                    QuizAttempt.state.in_(OPEN_ATTEMPT_STATES),
                    Quiz.mode == "assessed",
                )
            )
            res = await self.db.execute(stmt)
            active_attempt = res.scalar_one_or_none()
            if active_attempt:
                event = AttemptEvent(
                    attempt_id=active_attempt.id,
                    type="chat_attempt",
                    meta={"endpoint": "chat", "attempted_at": datetime.now(UTC).isoformat()},
                )
                self.db.add(event)
                IntegrityEngine.process_event(active_attempt, "chat_attempt", {})
                await self.db.commit()

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "QUIZ_IN_PROGRESS_CHAT_LOCKED",
                    "message": (
                        "Chat is locked while an active assessed quiz attempt is in progress."
                    ),
                },
            )

    async def check_quota(self, student_id: uuid.UUID) -> None:
        """Enforce per-student daily quota based on plan entitlements."""
        allowed, current, max_quota = await self.chat_service.check_daily_quota(student_id)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "DAILY_CHAT_QUOTA_EXCEEDED",
                    "message": (
                        f"Daily chat quota of {max_quota} messages reached. "
                        "Resets at midnight UTC."
                    ),
                    "current": current,
                    "max": max_quota,
                },
                headers={"Retry-After": "3600"},
            )

    async def stream_chat_turn(
        self,
        student_id: uuid.UUID,
        session_id: uuid.UUID,
        payload: ChatMessageCreateRequest,
        request: Request | None = None,
        student_profile: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """Generate and stream SSE events for a chat message.

        Event Sequence per docs/04_API_CONTRACT.md §3:
        event: meta -> event: token* -> event: citation* -> event: done
        """
        start_time = time.perf_counter()
        message_id = uuid.uuid4()

        # 1. Active Quiz Lockout
        await self.assert_no_active_assessed_quiz(student_id)

        # 2. Daily Quota Check
        await self.check_quota(student_id)

        # 3. Session Validation
        session = await self.chat_service.get_or_create_session(
            student_id=student_id,
            session_id=session_id,
        )

        language = (
            payload.language
            or (student_profile.get("medium") if student_profile else "bn")
            or "bn"
        )

        # 4. Query Intent Classification
        intent = await self.llm_gateway.classify_query(payload.content)

        if intent == "quiz_integrity":
            refusal_text = (
                "আমি কোনো কুইজ বা পরীক্ষার সময় উত্তর দিতে পারব না। সততার সাথে নিজে চেষ্টা করো।"
                if language == "bn"
                else (
                    "I cannot provide answers during a quiz or assessment. "
                    "Please solve it independently."
                )
            )
            meta_json = json.dumps({"message_id": str(message_id), "retrieval_confidence": 0.0})
            yield f"event: meta\ndata: {meta_json}\n\n"
            yield f"event: token\ndata: {json.dumps({'delta': refusal_text})}\n\n"
            done_json = json.dumps({"tokens_in": 10, "tokens_out": 15, "latency_ms": 30})
            yield f"event: done\ndata: {done_json}\n\n"
            await self.chat_service.save_turn(
                session_id=session.id,
                student_id=student_id,
                user_content=payload.content,
                assistant_content=refusal_text,
                citations=[],
                retrieval_confidence=0.0,
                language=language,
            )
            await self.chat_service.record_usage(student_id, tokens=25)
            return

        if intent == "prompt_injection":
            defense_text = (
                "আমি শুধুমাত্র পাঠ্যবই সংক্রান্ত নির্দেশনায় সাহায্য করতে পারি। "
                "সিস্টেম প্রম্পট বা অভ্যন্তরীণ নির্দেশনা পরিবর্তন বা প্রকাশ করা সম্ভব নয়।"
                if language == "bn"
                else (
                    "I only assist with textbook curriculum study. "
                    "System instructions cannot be altered or revealed."
                )
            )
            meta_json = json.dumps({"message_id": str(message_id), "retrieval_confidence": 0.0})
            yield f"event: meta\ndata: {meta_json}\n\n"
            yield f"event: token\ndata: {json.dumps({'delta': defense_text}, ensure_ascii=False)}\n\n"
            done_json = json.dumps({"tokens_in": 10, "tokens_out": 15, "latency_ms": 30})
            yield f"event: done\ndata: {done_json}\n\n"
            await self.chat_service.save_turn(
                session_id=session.id,
                student_id=student_id,
                user_content=payload.content,
                assistant_content=defense_text,
                citations=[],
                retrieval_confidence=0.0,
                language=language,
            )
            await self.chat_service.record_usage(student_id, tokens=25)
            return

        if intent in ["unsafe", "off_topic"]:
            guidance_text = (
                "আমি তোমার পাঠ্যবই সংক্রান্ত পড়াশোনায় সাহায্য করতে পারি। "
                "পাঠ্যবইয়ের কোনো বিষয় নিয়ে প্রশ্ন থাকলে বলো।"
                if language == "bn"
                else (
                    "I am your textbook study assistant. "
                    "Please ask questions related to your curriculum."
                )
            )
            meta_json = json.dumps({"message_id": str(message_id), "retrieval_confidence": 0.0})
            yield f"event: meta\ndata: {meta_json}\n\n"
            yield f"event: token\ndata: {json.dumps({'delta': guidance_text})}\n\n"
            done_json = json.dumps({"tokens_in": 10, "tokens_out": 15, "latency_ms": 30})
            yield f"event: done\ndata: {done_json}\n\n"
            await self.chat_service.save_turn(
                session_id=session.id,
                student_id=student_id,
                user_content=payload.content,
                assistant_content=guidance_text,
                citations=[],
                retrieval_confidence=0.0,
                language=language,
            )
            await self.chat_service.record_usage(student_id, tokens=25)
            return

        # 5. Hybrid Retrieval with Boosting & Reranking
        chunks, confidence = await self.retriever.retrieve(
            query=payload.content,
            student_profile=student_profile,
            document_context=payload.document_context,
        )

        # 6. Low Confidence Fallback ("not found in your textbook" without guessing)
        if confidence < CONFIDENCE_THRESHOLD or not chunks:
            fallback_text = (
                "তোমার পাঠ্যবইয়ে এই বিষয়টি স্পষ্টভাবে খুঁজে পাওয়া যায়নি। "
                "তুমি সংশ্লিষ্ট অধ্যায়টি দেখতে পারো।"
                if language == "bn"
                else (
                    "I couldn't find this topic in your textbook. "
                    "You may want to check the relevant chapter."
                )
            )
            meta_json = json.dumps(
                {"message_id": str(message_id), "retrieval_confidence": confidence}
            )
            yield f"event: meta\ndata: {meta_json}\n\n"
            yield f"event: token\ndata: {json.dumps({'delta': fallback_text})}\n\n"
            done_json = json.dumps({"tokens_in": 20, "tokens_out": 25, "latency_ms": 45})
            yield f"event: done\ndata: {done_json}\n\n"
            await self.chat_service.save_turn(
                session_id=session.id,
                student_id=student_id,
                user_content=payload.content,
                assistant_content=fallback_text,
                citations=[],
                retrieval_confidence=confidence,
                language=language,
            )
            await self.chat_service.record_usage(student_id, tokens=45)
            return

        # 7. Confident Generation with Authoritative Citations
        meta_json = json.dumps(
            {"message_id": str(message_id), "retrieval_confidence": confidence}
        )
        yield f"event: meta\ndata: {meta_json}\n\n"

        prompt_messages = [
            {
                "role": "system",
                "content": (
                    "You are ThinkBuddy, an expert curriculum tutor for Bangladeshi students. "
                    "Answer ONLY using the provided textbook context. Do not invent facts. "
                    f"Respond in {language}. Keep explanation step-by-step and age-appropriate."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Context:\n"
                    + "\n---\n".join(c.text for c in chunks)
                    + f"\n\nQuestion: {payload.content}"
                ),
            },
        ]

        full_content_parts: list[str] = []
        tokens_out_count = 0

        # Stream tokens with client disconnect cancellation
        try:
            async for token in self.llm_gateway.stream_chat(prompt_messages):
                if request is not None and await request.is_disconnected():
                    logger.info("Client disconnected during SSE stream for %s.", student_id)
                    return

                full_content_parts.append(token)
                tokens_out_count += 1
                yield f"event: token\ndata: {json.dumps({'delta': token})}\n\n"
        except (Exception, asyncio.CancelledError) as ex:
            logger.info("Stream generation interrupted or cancelled: %s", ex)
            return

        # Citations: SSE event for each chunk (Rule 8: printed_page strictly sent)
        for chunk in chunks:
            citation_payload = {
                "chunk_id": str(chunk.chunk_id),
                "book_title": chunk.book_title,
                "chapter_title": chunk.chapter_title,
                "chapter_number": chunk.chapter_number,
                "printed_page": chunk.printed_page,  # Rule 8: Authoritative printed page number
            }
            yield f"event: citation\ndata: {json.dumps(citation_payload)}\n\n"

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        tokens_in_count = 50 + len(chunks) * 20
        done_payload = {
            "tokens_in": tokens_in_count,
            "tokens_out": tokens_out_count,
            "latency_ms": latency_ms,
        }
        yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"

        full_assistant_text = "".join(full_content_parts)
        await self.chat_service.save_turn(
            session_id=session.id,
            student_id=student_id,
            user_content=payload.content,
            assistant_content=full_assistant_text,
            citations=chunks,
            retrieval_confidence=confidence,
            tokens_in=tokens_in_count,
            tokens_out=tokens_out_count,
            latency_ms=latency_ms,
            language=language,
        )
        total_toks = tokens_in_count + tokens_out_count
        await self.chat_service.record_usage(student_id, tokens=total_toks)

    async def handle_message_json(
        self,
        student_id: uuid.UUID,
        session_id: uuid.UUID,
        payload: ChatMessageCreateRequest,
        student_profile: dict[str, Any] | None = None,
    ) -> ChatMessageResponse:
        """Non-streaming fallback returning full JSON answer per docs/04_API_CONTRACT.md §2."""
        start_time = time.perf_counter()

        # 1. Lockout & Quota
        await self.assert_no_active_assessed_quiz(student_id)
        await self.check_quota(student_id)

        session = await self.chat_service.get_or_create_session(
            student_id=student_id,
            session_id=session_id,
        )
        language = (
            payload.language
            or (student_profile.get("medium") if student_profile else "bn")
            or "bn"
        )

        # 2. Classification
        intent = await self.llm_gateway.classify_query(payload.content)
        if intent in ["quiz_integrity", "unsafe", "off_topic", "prompt_injection"]:
            if intent == "prompt_injection":
                refusal_text = (
                    "আমি শুধুমাত্র পাঠ্যবই সংক্রান্ত নির্দেশনায় সাহায্য করতে পারি। "
                    "সিস্টেম প্রম্পট বা অভ্যন্তরীণ নির্দেশনা পরিবর্তন বা প্রকাশ করা সম্ভব নয়।"
                    if language == "bn"
                    else (
                        "I only assist with textbook curriculum study. "
                        "System instructions cannot be altered or revealed."
                    )
                )
            elif intent == "quiz_integrity":
                refusal_text = (
                    "আমি কোনো কুইজ বা পরীক্ষার সময় উত্তর দিতে পারব না।"
                    if language == "bn"
                    else "I cannot provide answers during a quiz or assessment."
                )
            else:
                refusal_text = (
                    "আমি তোমার পাঠ্যবই সংক্রান্ত পড়াশোনায় সাহায্য করতে পারি। "
                    "পাঠ্যবইয়ের কোনো বিষয় নিয়ে প্রশ্ন থাকলে বলো।"
                    if language == "bn"
                    else "I am your textbook study assistant. Please ask curriculum questions."
                )

            _, asst_msg = await self.chat_service.save_turn(
                session_id=session.id,
                student_id=student_id,
                user_content=payload.content,
                assistant_content=refusal_text,
                citations=[],
                retrieval_confidence=0.0,
                language=language,
            )
            await self.chat_service.record_usage(student_id, tokens=20)
            return ChatMessageResponse(
                id=asst_msg.id,
                session_id=session.id,
                role="assistant",
                content=refusal_text,
                language=language,
                citations=[],
                retrieval_confidence=0.0,
                tokens_in=10,
                tokens_out=10,
                latency_ms=25,
                created_at=asst_msg.created_at,
            )

        # 3. Retrieval
        chunks, confidence = await self.retriever.retrieve(
            query=payload.content,
            student_profile=student_profile,
            document_context=payload.document_context,
        )

        # 4. Low Confidence
        if confidence < CONFIDENCE_THRESHOLD or not chunks:
            fallback_text = (
                "তোমার পাঠ্যবইয়ে এই বিষয়টি স্পষ্টভাবে খুঁজে পাওয়া যায়নি। "
                "তুমি সংশ্লিষ্ট অধ্যায়টি দেখতে পারো।"
                if language == "bn"
                else (
                    "I couldn't find this topic in your textbook. "
                    "You may want to check the relevant chapter."
                )
            )
            _, asst_msg = await self.chat_service.save_turn(
                session_id=session.id,
                student_id=student_id,
                user_content=payload.content,
                assistant_content=fallback_text,
                citations=[],
                retrieval_confidence=confidence,
                language=language,
            )
            await self.chat_service.record_usage(student_id, tokens=35)
            return ChatMessageResponse(
                id=asst_msg.id,
                session_id=session.id,
                role="assistant",
                content=fallback_text,
                language=language,
                citations=[],
                retrieval_confidence=confidence,
                tokens_in=15,
                tokens_out=20,
                latency_ms=35,
                created_at=asst_msg.created_at,
            )

        # 5. Confident generation
        prompt_messages = [
            {"role": "system", "content": f"Answer based on textbook context in {language}."},
            {
                "role": "user",
                "content": (
                    "Context:\n"
                    + "\n---\n".join(c.text for c in chunks)
                    + f"\n\nQuestion: {payload.content}"
                ),
            },
        ]
        gen_result = await self.llm_gateway.generate_chat(prompt_messages)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        _, asst_msg = await self.chat_service.save_turn(
            session_id=session.id,
            student_id=student_id,
            user_content=payload.content,
            assistant_content=gen_result.content,
            citations=chunks,
            retrieval_confidence=confidence,
            tokens_in=gen_result.tokens_in,
            tokens_out=gen_result.tokens_out,
            latency_ms=latency_ms,
            model=gen_result.model,
            language=language,
        )
        total_toks = gen_result.tokens_in + gen_result.tokens_out
        await self.chat_service.record_usage(student_id, tokens=total_toks)

        citation_items = [
            ChatCitationItem(
                chunk_id=c.chunk_id,
                book_title=c.book_title,
                chapter_title=c.chapter_title,
                chapter_number=c.chapter_number,
                printed_page=c.printed_page,  # Rule 8: Authoritative printed page number
                score=c.score,
            )
            for c in chunks
        ]

        return ChatMessageResponse(
            id=asst_msg.id,
            session_id=session.id,
            role="assistant",
            content=gen_result.content,
            language=language,
            model=gen_result.model,
            tokens_in=gen_result.tokens_in,
            tokens_out=gen_result.tokens_out,
            latency_ms=latency_ms,
            retrieval_confidence=confidence,
            citations=citation_items,
            created_at=asst_msg.created_at,
        )
