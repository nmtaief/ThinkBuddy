"""Service layer for AI Tutor and RAG administrative management."""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.admin.models import AITutorConfig
from core.admin.schemas import (
    AITutorConfigResponse,
    AITutorStatsResponse,
    RAGTestChunk,
    TestLLMRequest,
    TestLLMResponse,
    TestRAGRequest,
    TestRAGResponse,
    UpdateAITutorConfigRequest,
    mask_secret,
)
from core.chat.models import ChatMessage, ChatSession
from core.chat.retriever import ChatRetriever
from core.common.config import settings
from core.curriculum.models import Book, Chapter, Chunk

logger = logging.getLogger(__name__)


async def get_or_create_ai_tutor_config(db: AsyncSession) -> AITutorConfig:
    """Retrieve the single active AI Tutor configuration or create default."""
    stmt = select(AITutorConfig).order_by(AITutorConfig.created_at.asc()).limit(1)
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if config is None:
        import os
        env_openrouter = os.getenv("OPENROUTER_API_KEY")
        config = AITutorConfig(
            llm_provider="openrouter" if env_openrouter else "gemini",
            api_key=env_openrouter,
            api_base="https://openrouter.ai/api/v1" if env_openrouter else None,
            primary_model="openrouter/auto" if env_openrouter else "gemini/gemini-1.5-flash",
            fallback_model="openrouter/free" if env_openrouter else "openai/gpt-4o-mini",
            temperature=0.3,
            system_prompt="You are Buddy, the friendly and encouraging AI study tutor for ThinkBuddy. "
                          "You teach students according to the NCTB curriculum in Bangla and English. "
                          "Always cite specific textbooks and printed pages when answering.",
            embedding_provider=settings.EMBEDDING_PROVIDER or "bge-m3",
            embedding_api_key=None,
            embedding_model="bge-m3",
            embedding_dimensions=1024,
            confidence_threshold=0.10,
            max_chunks=4,
            is_enabled=True,
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)

    return config


def serialize_config_response(config: AITutorConfig) -> AITutorConfigResponse:
    """Convert DB model to masked Pydantic response schema."""
    return AITutorConfigResponse(
        id=config.id,
        llm_provider=config.llm_provider,
        has_api_key=bool(config.api_key),
        api_key_masked=mask_secret(config.api_key),
        api_base=config.api_base,
        primary_model=config.primary_model,
        fallback_model=config.fallback_model,
        temperature=config.temperature,
        system_prompt=config.system_prompt,
        embedding_provider=config.embedding_provider,
        has_embedding_api_key=bool(config.embedding_api_key),
        embedding_api_key_masked=mask_secret(config.embedding_api_key),
        embedding_model=config.embedding_model,
        embedding_dimensions=config.embedding_dimensions,
        confidence_threshold=config.confidence_threshold,
        max_chunks=config.max_chunks,
        is_enabled=config.is_enabled,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


async def update_ai_tutor_config(
    db: AsyncSession, request: UpdateAITutorConfigRequest
) -> AITutorConfig:
    """Update AI Tutor & RAG parameters with validation."""
    config = await get_or_create_ai_tutor_config(db)

    if request.llm_provider is not None:
        config.llm_provider = request.llm_provider.strip().lower()

    if request.api_key is not None:
        trimmed = request.api_key.strip()
        config.api_key = trimmed if trimmed else None

    if request.api_base is not None:
        trimmed = request.api_base.strip()
        config.api_base = trimmed if trimmed else None

    if request.primary_model is not None:
        config.primary_model = request.primary_model.strip()

    if request.fallback_model is not None:
        config.fallback_model = request.fallback_model.strip()

    if request.temperature is not None:
        config.temperature = request.temperature

    if request.system_prompt is not None:
        config.system_prompt = request.system_prompt.strip()

    if request.embedding_provider is not None:
        config.embedding_provider = request.embedding_provider.strip().lower()

    if request.embedding_api_key is not None:
        trimmed = request.embedding_api_key.strip()
        config.embedding_api_key = trimmed if trimmed else None

    if request.embedding_model is not None:
        config.embedding_model = request.embedding_model.strip()

    if request.embedding_dimensions is not None:
        config.embedding_dimensions = request.embedding_dimensions

    if request.confidence_threshold is not None:
        config.confidence_threshold = request.confidence_threshold

    if request.max_chunks is not None:
        config.max_chunks = request.max_chunks

    if request.is_enabled is not None:
        config.is_enabled = request.is_enabled

    await db.commit()
    await db.refresh(config)
    return config


async def test_llm_connection(
    config: AITutorConfig, req: TestLLMRequest
) -> TestLLMResponse:
    """Diagnostic check to ping the configured LLM API and measure latency."""
    start_time = time.perf_counter()
    target_provider = req.provider or config.llm_provider
    target_model = req.model or config.primary_model
    target_key = req.api_key or config.api_key
    target_base = req.api_base or config.api_base

    # Check if mock or no key
    if target_provider == "mock" or (not target_key and target_provider not in ("ollama", "mock")):
        # Deterministic simulation if no key provided or mock requested
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        return TestLLMResponse(
            success=True,
            content="[Simulation Mode: Mock/Preview] Hello! I am Buddy, your AI tutor for ThinkBuddy. "
                    "আসসালামু আলাইকুম! আমি থিঙ্কবাডি এআই শিক্ষক। জাতীয় শিক্ষাক্রম ও পাঠ্যপুস্তকের আলোকে তোমাকে সাহায্য করতে প্রস্তুত।",
            tokens_in=len(req.prompt.split()),
            tokens_out=42,
            latency_ms=latency_ms,
            model_used=f"{target_model} (mock/preview)",
            error=None,
        )

    # 1. Direct OpenAI-compatible / OpenRouter HTTP execution
    if target_key and (target_provider in ("openrouter", "openai", "groq", "ollama", "custom") or target_base):
        base_url = target_base or (
            "https://openrouter.ai/api/v1" if target_provider == "openrouter" else
            "https://api.groq.com/openai/v1" if target_provider == "groq" else
            "https://api.openai.com/v1" if target_provider == "openai" else
            "http://localhost:11434/v1" if target_provider == "ollama" else
            None
        )
        if base_url:
            chat_url = base_url.rstrip("/") + "/chat/completions"
            headers = {
                "Authorization": f"Bearer {target_key}",
                "Content-Type": "application/json",
            }
            if target_provider == "openrouter" or "openrouter" in base_url:
                headers["HTTP-Referer"] = "https://thinkbuddy.app"
                headers["X-Title"] = "ThinkBuddy AI Tutor"

            clean_model = (
                target_model[11:]
                if target_model.startswith("openrouter/") and target_model.count("/") > 1
                else target_model
            )

            payload = {
                "model": clean_model,
                "messages": [
                    {"role": "system", "content": config.system_prompt or "You are Buddy, the friendly AI tutor for ThinkBuddy."},
                    {"role": "user", "content": req.prompt},
                ],
                "temperature": config.temperature,
                "max_tokens": 500,
            }

            try:
                import httpx
                async with httpx.AsyncClient(timeout=25.0) as client:
                    http_res = await client.post(chat_url, headers=headers, json=payload)
                    latency_ms = int((time.perf_counter() - start_time) * 1000)

                    # Auto-fallback to openrouter/free if paid credit/rate limit error
                    if not http_res.is_success and http_res.status_code in (402, 403, 429) and clean_model != "openrouter/free" and (target_provider == "openrouter" or "openrouter" in base_url):
                        logger.info("OpenRouter returned %s on %s; trying openrouter/free fallback", http_res.status_code, clean_model)
                        payload["model"] = "openrouter/free"
                        fb_res = await client.post(chat_url, headers=headers, json=payload)
                        if fb_res.is_success:
                            res_json = fb_res.json()
                            content = res_json.get("choices", [{}])[0].get("message", {}).get("content", "")
                            usage = res_json.get("usage", {})
                            latency_ms = int((time.perf_counter() - start_time) * 1000)
                            return TestLLMResponse(
                                success=True,
                                content=content,
                                tokens_in=usage.get("prompt_tokens", len(req.prompt.split())),
                                tokens_out=usage.get("completion_tokens", len(content.split())),
                                latency_ms=latency_ms,
                                model_used="openrouter/free (Auto-routed Free Tier)",
                                error=None,
                            )

                    if http_res.is_success:
                        res_json = http_res.json()
                        content = res_json.get("choices", [{}])[0].get("message", {}).get("content", "")
                        usage = res_json.get("usage", {})
                        return TestLLMResponse(
                            success=True,
                            content=content,
                            tokens_in=usage.get("prompt_tokens", len(req.prompt.split())),
                            tokens_out=usage.get("completion_tokens", len(content.split())),
                            latency_ms=latency_ms,
                            model_used=target_model,
                            error=None,
                        )
                    else:
                        err_text = http_res.text
                        logger.error("API error from %s: %s %s", target_provider, http_res.status_code, err_text)
                        return TestLLMResponse(
                            success=False,
                            content="",
                            tokens_in=0,
                            tokens_out=0,
                            latency_ms=latency_ms,
                            model_used=target_model,
                            error=f"HTTP {http_res.status_code}: {err_text[:300]}",
                        )
            except Exception as ex:
                logger.error("HTTP call failed for %s: %s", target_provider, ex)
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                return TestLLMResponse(
                    success=False,
                    content="",
                    tokens_in=0,
                    tokens_out=0,
                    latency_ms=latency_ms,
                    model_used=target_model,
                    error=str(ex),
                )

    try:
        import litellm

        messages = [
            {"role": "system", "content": config.system_prompt or "You are Buddy, the AI tutor for ThinkBuddy."},
            {"role": "user", "content": req.prompt},
        ]

        kwargs: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": config.temperature,
            "timeout": 15.0,
        }
        if target_key:
            kwargs["api_key"] = target_key
        if target_base:
            kwargs["api_base"] = target_base

        response = await litellm.acompletion(**kwargs)
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)

        return TestLLMResponse(
            success=True,
            content=content,
            tokens_in=getattr(usage, "prompt_tokens", len(req.prompt.split())),
            tokens_out=getattr(usage, "completion_tokens", len(content.split())),
            latency_ms=latency_ms,
            model_used=target_model,
            error=None,
        )
    except Exception as ex:
        logger.error("LLM diagnostic call failed for %s: %s", target_model, ex)
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        return TestLLMResponse(
            success=False,
            content="",
            tokens_in=0,
            tokens_out=0,
            latency_ms=latency_ms,
            model_used=target_model,
            error=str(ex),
        )


async def test_rag_retrieval(
    db: AsyncSession, config: AITutorConfig, req: TestRAGRequest
) -> TestRAGResponse:
    """Execute dynamic RAG search to inspect retrieved chunks and confidence."""
    start_time = time.perf_counter()
    retriever = ChatRetriever(db)

    profile_filters: dict[str, Any] = {}
    if req.class_level:
        profile_filters["class_level"] = req.class_level
    if req.subject:
        profile_filters["subject"] = req.subject

    chunks, confidence = await retriever.retrieve(
        query=req.query,
        student_profile=profile_filters if profile_filters else None,
        limit=req.limit or config.max_chunks,
    )

    latency_ms = int((time.perf_counter() - start_time) * 1000)

    test_chunks = [
        RAGTestChunk(
            chunk_id=str(c.chunk_id),
            book_title=c.book_title,
            chapter_title=c.chapter_title,
            chapter_number=c.chapter_number,
            printed_page=c.printed_page,
            pdf_page_index=c.pdf_page_index,
            score=c.score,
            snippet=c.text[:250] + ("..." if len(c.text) > 250 else ""),
        )
        for c in chunks
    ]

    return TestRAGResponse(
        query=req.query,
        confidence=confidence,
        chunks=test_chunks,
        latency_ms=latency_ms,
    )


async def get_rag_stats(
    db: AsyncSession, config: AITutorConfig
) -> AITutorStatsResponse:
    """Compute knowledge base counts and active tutor metrics."""
    res_books = await db.execute(select(func.count(Book.id)))
    total_books = res_books.scalar() or 0

    res_chapters = await db.execute(select(func.count(Chapter.id)))
    total_chapters = res_chapters.scalar() or 0

    res_chunks = await db.execute(select(func.count(Chunk.id)))
    total_chunks = res_chunks.scalar() or 0

    res_sessions = await db.execute(select(func.count(ChatSession.id)))
    total_sessions = res_sessions.scalar() or 0

    res_messages = await db.execute(select(func.count(ChatMessage.id)))
    total_messages = res_messages.scalar() or 0

    return AITutorStatsResponse(
        total_books=total_books,
        total_chapters=total_chapters,
        total_chunks=total_chunks,
        total_chat_sessions=total_sessions,
        total_chat_messages=total_messages,
        active_llm_provider=config.llm_provider,
        active_primary_model=config.primary_model,
        active_embedding_provider=config.embedding_provider,
        rag_chat_enabled=config.is_enabled,
    )
