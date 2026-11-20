"""Chat domain service for session management, persistence, usage quota, and learning signals."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.chat.models import ChatCitation, ChatMessage, ChatSession, UsageCounter
from core.chat.retriever import RetrievedChunk
from core.entitlements.models import Entitlement
from core.families.models import FamilyMember
from core.quiz.models import LearningSignal

logger = logging.getLogger(__name__)

DEFAULT_FREE_DAILY_QUOTA = 20
DEFAULT_PREMIUM_DAILY_QUOTA = 100


class ChatService:
    """Service handling Chat session lifecycle, quota checks, and turn persistence."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create_session(
        self,
        student_id: uuid.UUID,
        session_id: uuid.UUID | None = None,
        title: str = "New Conversation",
        subject: str | None = None,
    ) -> ChatSession:
        """Fetch existing session verifying student ownership, or create a new session."""
        if session_id:
            stmt = select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.student_id == student_id,
            )
            res = await self.db.execute(stmt)
            session = res.scalar_one_or_none()
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "CHAT_SESSION_NOT_FOUND",
                        "message": "Chat session not found or unauthorized.",
                    },
                )
            return session

        new_session = ChatSession(
            id=uuid.uuid4(),
            student_id=student_id,
            title=title,
            subject=subject,
            is_active=True,
        )
        self.db.add(new_session)
        await self.db.flush()
        return new_session

    async def get_session(self, session_id: uuid.UUID, student_id: uuid.UUID) -> ChatSession:
        """Fetch a session with full message history and citations, verifying ownership."""
        stmt = (
            select(ChatSession)
            .where(
                ChatSession.id == session_id,
                ChatSession.student_id == student_id,
            )
            .options(
                selectinload(ChatSession.messages).selectinload(ChatMessage.citations),
            )
        )
        res = await self.db.execute(stmt)
        session = res.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "CHAT_SESSION_NOT_FOUND",
                    "message": "Chat session not found or unauthorized.",
                },
            )
        return session

    async def list_sessions(
        self,
        student_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ChatSession]:
        """List active sessions for a student ordered by most recent."""
        stmt = (
            select(ChatSession)
            .where(ChatSession.student_id == student_id, ChatSession.is_active.is_(True))
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_recent_messages(
        self, session_id: uuid.UUID, limit: int = 6
    ) -> list[dict[str, Any]]:
        """Fetch recent message history for multi-turn conversational context."""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .options(selectinload(ChatMessage.citations))
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        msgs = list(reversed(res.scalars().all()))
        return [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "citations": [
                    {
                        "chunk_id": str(c.chunk_id) if c.chunk_id else None,
                        "book_title": c.book_title,
                        "chapter_title": c.chapter_title,
                        "chapter_number": c.chapter_number,
                        "printed_page": c.printed_page,
                    }
                    for c in (m.citations or [])
                ],
            }
            for m in msgs
        ]

    async def check_daily_quota(self, student_id: uuid.UUID) -> tuple[bool, int, int]:
        """Check if student has remaining daily message quota.

        Returns:
            tuple of (is_allowed: bool, current_messages: int, max_allowed: int)
        """
        # Determine plan tier via family entitlement
        max_quota = DEFAULT_FREE_DAILY_QUOTA
        family_stmt = (
            select(FamilyMember.family_id).where(FamilyMember.user_id == student_id).limit(1)
        )
        family_res = await self.db.execute(family_stmt)
        family_id = family_res.scalar_one_or_none()

        if family_id:
            ent_stmt = select(Entitlement).where(Entitlement.family_id == family_id).limit(1)
            ent_res = await self.db.execute(ent_stmt)
            ent = ent_res.scalar_one_or_none()
            if ent and ent.plan == "premium":
                max_quota = DEFAULT_PREMIUM_DAILY_QUOTA

        today = datetime.now(UTC).date()
        counter_stmt = select(UsageCounter).where(
            UsageCounter.student_id == student_id,
            UsageCounter.date == today,
        )
        counter_res = await self.db.execute(counter_stmt)
        counter = counter_res.scalar_one_or_none()
        current_count = counter.chat_messages if counter else 0

        is_allowed = current_count < max_quota
        return is_allowed, current_count, max_quota

    async def record_usage(self, student_id: uuid.UUID, tokens: int = 0) -> None:
        """Upsert student daily usage counter."""
        today = datetime.now(UTC).date()
        stmt = (
            pg_insert(UsageCounter)
            .values(
                student_id=student_id,
                date=today,
                chat_messages=1,
                tokens=tokens,
            )
            .on_conflict_do_update(
                index_elements=["student_id", "date"],
                set_={
                    "chat_messages": UsageCounter.chat_messages + 1,
                    "tokens": UsageCounter.tokens + tokens,
                },
            )
        )
        await self.db.execute(stmt)

    async def get_message_by_id(self, message_id: uuid.UUID) -> ChatMessage | None:
        """Fetch a specific chat message by its primary key ID."""
        stmt = select(ChatMessage).where(ChatMessage.id == message_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def save_user_message(
        self,
        session_id: uuid.UUID,
        content: str,
        language: str = "bn",
    ) -> ChatMessage:
        """Persist user message immediately before model inference begins."""
        now = datetime.now(UTC)
        user_msg = ChatMessage(
            id=uuid.uuid4(),
            session_id=session_id,
            role="user",
            content=content,
            language=language,
            created_at=now,
        )
        self.db.add(user_msg)
        await self.db.flush()
        return user_msg

    async def save_turn(
        self,
        session_id: uuid.UUID,
        student_id: uuid.UUID,
        user_content: str,
        assistant_content: str,
        citations: list[RetrievedChunk],
        retrieval_confidence: float,
        tokens_in: int = 0,
        tokens_out: int = 0,
        latency_ms: int = 0,
        model: str = "tutor-rag-v1",
        language: str = "bn",
        existing_user_msg: ChatMessage | None = None,
    ) -> tuple[ChatMessage, ChatMessage]:
        """Persist user prompt, assistant response, citations, and emit learning signals."""
        now = datetime.now(UTC)

        if existing_user_msg is not None:
            user_msg = existing_user_msg
        else:
            user_msg = ChatMessage(
                id=uuid.uuid4(),
                session_id=session_id,
                role="user",
                content=user_content,
                language=language,
                created_at=now,
            )
            self.db.add(user_msg)

        assistant_msg = ChatMessage(
            id=uuid.uuid4(),
            session_id=session_id,
            role="assistant",
            content=assistant_content,
            language=language,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            retrieval_confidence=retrieval_confidence,
            created_at=now,
        )
        self.db.add(assistant_msg)
        await self.db.flush()

        # Verify FKs exist in database before assigning
        valid_chunk_ids: set[uuid.UUID] = set()
        valid_book_ids: set[uuid.UUID] = set()
        valid_chapter_ids: set[uuid.UUID] = set()

        if citations:
            from core.curriculum.models import Book, Chapter, Chunk

            def get_val(item: Any, key: str) -> Any:
                if isinstance(item, dict):
                    return item.get(key)
                return getattr(item, key, None)

            cand_chunks = [get_val(c, "chunk_id") for c in citations if get_val(c, "chunk_id")]
            if cand_chunks:
                chk_res = await self.db.execute(select(Chunk.id).where(Chunk.id.in_(cand_chunks)))
                valid_chunk_ids = set(chk_res.scalars().all())

            cand_books = [get_val(c, "book_id") for c in citations if get_val(c, "book_id")]
            if cand_books:
                book_res = await self.db.execute(select(Book.id).where(Book.id.in_(cand_books)))
                valid_book_ids = set(book_res.scalars().all())

            cand_chapters = [get_val(c, "chapter_id") for c in citations if get_val(c, "chapter_id")]
            if cand_chapters:
                ch_stmt = select(Chapter.id).where(Chapter.id.in_(cand_chapters))
                ch_res = await self.db.execute(ch_stmt)
                valid_chapter_ids = set(ch_res.scalars().all())

        # Persist citations with separate printed_page and pdf_page_index (Rule 8)
        for c in citations:
            c_chunk_id = c.get("chunk_id") if isinstance(c, dict) else getattr(c, "chunk_id", None)
            c_book_id = c.get("book_id") if isinstance(c, dict) else getattr(c, "book_id", None)
            c_chapter_id = c.get("chapter_id") if isinstance(c, dict) else getattr(c, "chapter_id", None)
            c_book_title = c.get("book_title", "") if isinstance(c, dict) else getattr(c, "book_title", "")
            c_chapter_title = c.get("chapter_title", "") if isinstance(c, dict) else getattr(c, "chapter_title", "")
            c_chapter_number = c.get("chapter_number") if isinstance(c, dict) else getattr(c, "chapter_number", None)
            c_printed_page = c.get("printed_page") if isinstance(c, dict) else getattr(c, "printed_page", None)
            c_pdf_page_index = c.get("pdf_page_index") if isinstance(c, dict) else getattr(c, "pdf_page_index", None)
            if c_pdf_page_index is None:
                c_pdf_page_index = c_printed_page if c_printed_page is not None else 0
            c_score = c.get("score", 1.0) if isinstance(c, dict) else getattr(c, "score", 1.0)

            actual_chunk_id = c_chunk_id if c_chunk_id in valid_chunk_ids else None
            actual_book_id = c_book_id if c_book_id in valid_book_ids else None
            actual_chapter_id = c_chapter_id if c_chapter_id in valid_chapter_ids else None

            citation = ChatCitation(
                id=uuid.uuid4(),
                message_id=assistant_msg.id,
                chunk_id=actual_chunk_id,
                book_id=actual_book_id,
                book_title=c_book_title,
                chapter_id=actual_chapter_id,
                chapter_title=c_chapter_title,
                chapter_number=c_chapter_number,
                printed_page=c_printed_page,
                pdf_page_index=c_pdf_page_index,
                score=c_score,
                created_at=now,
            )
            self.db.add(citation)

        # Emit learning signal for topic queried (ai_question / ai_repeat)
        if citations:
            primary_chunk = citations[0]
            p_chap_id = primary_chunk.get("chapter_id") if isinstance(primary_chunk, dict) else getattr(primary_chunk, "chapter_id", None)
            if p_chap_id and p_chap_id in valid_chapter_ids:
                # Check for repeat asks within past 7 days
                seven_days_ago = now - timedelta(days=7)
                recent_stmt = (
                    select(LearningSignal.id)
                    .where(
                        LearningSignal.student_id == student_id,
                        LearningSignal.chapter_id == p_chap_id,
                        LearningSignal.source.in_(["ai_question", "ai_repeat"]),
                        LearningSignal.at >= seven_days_ago,
                    )
                    .limit(1)
                )
                recent_res = await self.db.execute(recent_stmt)
                is_repeat = recent_res.scalar_one_or_none() is not None

                source = "ai_repeat" if is_repeat else "ai_question"
                weight = 1.2 if is_repeat else 0.8

                sig_stmt = (
                    pg_insert(LearningSignal)
                    .values(
                        id=uuid.uuid4(),
                        student_id=student_id,
                        source=source,
                        chapter_id=primary_chunk.chapter_id,
                        weight=weight,
                        ref_id=str(assistant_msg.id),
                        at=now,
                    )
                    .on_conflict_do_nothing(index_elements=["student_id", "source", "ref_id"])
                )
                await self.db.execute(sig_stmt)

        await self.db.commit()

        # Structured cost and usage logging (Standing Rule 15: no prompt text or tokens leaked)
        logger.info(
            "Chat turn completed: student_id=%s session_id=%s model=%s "
            "tokens_in=%d tokens_out=%d latency_ms=%d confidence=%.2f citations=%d",
            student_id,
            session_id,
            model,
            tokens_in,
            tokens_out,
            latency_ms,
            retrieval_confidence,
            len(citations),
        )

        return user_msg, assistant_msg
