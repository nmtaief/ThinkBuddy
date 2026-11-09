"""Administrative API routes for AI Tutor (Buddy) & RAG Knowledge Base configuration."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.admin.schemas import (
    AITutorConfigResponse,
    AITutorStatsResponse,
    TestLLMRequest,
    TestLLMResponse,
    TestRAGRequest,
    TestRAGResponse,
    UpdateAITutorConfigRequest,
)
from core.admin.service import (
    get_or_create_ai_tutor_config,
    get_rag_stats,
    serialize_config_response,
    test_llm_connection,
    test_rag_retrieval,
    update_ai_tutor_config,
)
from core.audit.models import AuditLog
from core.auth.dependencies import require_role
from core.auth.models import User
from core.common.database import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/ai-tutor", tags=["Admin - AI Tutor & RAG"])


@router.get("/config", response_model=AITutorConfigResponse)
async def get_ai_tutor_config_endpoint(
    _current_admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AITutorConfigResponse:
    """Retrieve the current AI Tutor & RAG configuration with masked secrets."""
    config = await get_or_create_ai_tutor_config(db)
    return serialize_config_response(config)


@router.put("/config", response_model=AITutorConfigResponse)
async def update_ai_tutor_config_endpoint(
    payload: UpdateAITutorConfigRequest,
    current_admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AITutorConfigResponse:
    """Update AI Tutor (Buddy) LLM provider, API keys, models, and RAG retrieval settings."""
    config = await update_ai_tutor_config(db, payload)

    # Audit log entry without exposing secret keys
    audit_entry = AuditLog(
        actor_id=current_admin.id,
        action="ai_tutor.config_updated",
        target_type="ai_tutor_config",
        target_id=str(config.id),
        meta={
            "llm_provider": config.llm_provider,
            "primary_model": config.primary_model,
            "fallback_model": config.fallback_model,
            "temperature": config.temperature,
            "embedding_provider": config.embedding_provider,
            "embedding_model": config.embedding_model,
            "confidence_threshold": config.confidence_threshold,
            "max_chunks": config.max_chunks,
            "is_enabled": config.is_enabled,
            "has_api_key": bool(config.api_key),
        },
    )
    db.add(audit_entry)
    await db.commit()

    logger.info(
        "Admin %s updated AI Tutor configuration: provider=%s, model=%s",
        current_admin.id,
        config.llm_provider,
        config.primary_model,
    )
    return serialize_config_response(config)


@router.post("/test-llm", response_model=TestLLMResponse)
async def test_llm_connection_endpoint(
    payload: TestLLMRequest,
    _current_admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TestLLMResponse:
    """Diagnostic check to ping the LLM API and measure response and latency."""
    config = await get_or_create_ai_tutor_config(db)
    return await test_llm_connection(config, payload)


@router.post("/test-rag", response_model=TestRAGResponse)
async def test_rag_retrieval_endpoint(
    payload: TestRAGRequest,
    _current_admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TestRAGResponse:
    """Diagnostic check to test RAG retrieval on NCTB textbooks and inspect chunks."""
    config = await get_or_create_ai_tutor_config(db)
    return await test_rag_retrieval(db, config, payload)


@router.get("/stats", response_model=AITutorStatsResponse)
async def get_ai_tutor_stats_endpoint(
    _current_admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AITutorStatsResponse:
    """Get knowledge base statistics (indexed textbooks, chapters, chunks, and sessions)."""
    config = await get_or_create_ai_tutor_config(db)
    return await get_rag_stats(db, config)
