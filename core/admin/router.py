"""Administrative API routes for AI Tutor, Chatbot settings, and Weakness/Strength Analytics."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.admin.analytics import (
    LearningSignalsQueryResponse,
    LLMUsageAnalyticsResponse,
    StudentAnalyticsListItem,
    StudentDetailAnalyticsResponse,
    WeaknessStrengthOverviewResponse,
    get_llm_usage_analytics,
    get_student_detail_analytics,
    get_weakness_strength_overview,
    list_students_analytics,
    query_learning_signals,
)
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
from core.progress.service import ProgressService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


# ============================================================================
# AI Tutor (Buddy) & LLM Provider Configuration
# ============================================================================

@router.get("/ai-tutor/config", response_model=AITutorConfigResponse, tags=["Admin - AI Tutor & RAG"])
async def get_ai_tutor_config_endpoint(
    _current_admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AITutorConfigResponse:
    """Retrieve the current AI Tutor & RAG configuration with masked secrets."""
    config = await get_or_create_ai_tutor_config(db)
    return serialize_config_response(config)


@router.put("/ai-tutor/config", response_model=AITutorConfigResponse, tags=["Admin - AI Tutor & RAG"])
async def update_ai_tutor_config_endpoint(
    payload: UpdateAITutorConfigRequest,
    current_admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AITutorConfigResponse:
    """Update AI Tutor (Buddy) LLM provider, API keys, models, and RAG retrieval settings."""
    config = await update_ai_tutor_config(db, payload)

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


@router.post("/ai-tutor/test-llm", response_model=TestLLMResponse, tags=["Admin - AI Tutor & RAG"])
async def test_llm_connection_endpoint(
    payload: TestLLMRequest,
    _current_admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TestLLMResponse:
    """Diagnostic check to ping the LLM API and measure response and latency."""
    config = await get_or_create_ai_tutor_config(db)
    return await test_llm_connection(config, payload)


@router.post("/ai-tutor/test-rag", response_model=TestRAGResponse, tags=["Admin - AI Tutor & RAG"])
async def test_rag_retrieval_endpoint(
    payload: TestRAGRequest,
    _current_admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TestRAGResponse:
    """Diagnostic check to test RAG retrieval on NCTB textbooks and inspect chunks."""
    config = await get_or_create_ai_tutor_config(db)
    return await test_rag_retrieval(db, config, payload)


@router.get("/ai-tutor/stats", response_model=AITutorStatsResponse, tags=["Admin - AI Tutor & RAG"])
async def get_ai_tutor_stats_endpoint(
    _current_admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AITutorStatsResponse:
    """Get knowledge base statistics (indexed textbooks, chapters, chunks, and sessions)."""
    config = await get_or_create_ai_tutor_config(db)
    return await get_rag_stats(db, config)


# ============================================================================
# Weakness / Strength Analytics & Data Pipeline Intelligence
# ============================================================================

@router.get("/analytics/overview", response_model=WeaknessStrengthOverviewResponse, tags=["Admin - Analytics"])
@router.get("/analytics/weakness-strength", response_model=WeaknessStrengthOverviewResponse, tags=["Admin - Analytics"])
async def get_weakness_strength_overview_endpoint(
    _current_admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    class_level: int | None = Query(None, description="Optional class filter"),
    subject: str | None = Query(None, description="Optional subject slug filter"),
) -> WeaknessStrengthOverviewResponse:
    """Retrieve aggregated platform weakness/strength distributions, struggling chapters, and concepts."""
    return await get_weakness_strength_overview(db, class_level=class_level, subject_slug=subject)


@router.get("/analytics/students", response_model=list[StudentAnalyticsListItem], tags=["Admin - Analytics"])
async def list_students_analytics_endpoint(
    _current_admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[StudentAnalyticsListItem]:
    """List all enrolled students with their mastery level, confidence, and weakness standings."""
    return await list_students_analytics(db, limit=limit, offset=offset)


@router.get("/analytics/students/{student_id}", response_model=StudentDetailAnalyticsResponse, tags=["Admin - Analytics"])
async def get_student_detail_analytics_endpoint(
    student_id: uuid.UUID,
    _current_admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> StudentDetailAnalyticsResponse:
    """Retrieve detailed chapter mastery and weakness profile for a specific student."""
    res = await get_student_detail_analytics(student_id, db)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "STUDENT_NOT_FOUND", "message": f"Student {student_id} not found"},
        )
    return res


@router.get("/analytics/usage", response_model=LLMUsageAnalyticsResponse, tags=["Admin - Analytics"])
async def get_llm_usage_endpoint(
    _current_admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    days: int = Query(14, ge=1, le=90),
) -> LLMUsageAnalyticsResponse:
    """Retrieve real LLM Chatbot token consumption, estimated costs, and daily usage trends."""
    return await get_llm_usage_analytics(db, days=days)


@router.get("/analytics/signals", response_model=LearningSignalsQueryResponse, tags=["Admin - Analytics"])
async def query_signals_endpoint(
    _current_admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    student_id: uuid.UUID | None = Query(None),
    source: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> LearningSignalsQueryResponse:
    """Inspect raw learning signals stream with optional student or source filtering."""
    return await query_learning_signals(db, student_id=student_id, source=source, limit=limit, offset=offset)


@router.post("/analytics/recompute", tags=["Admin - Analytics"])
async def trigger_recompute_mastery_endpoint(
    _current_admin: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    student_id: uuid.UUID | None = Query(None, description="Optional single student ID to recompute"),
) -> dict[str, Any]:
    """Trigger background recomputation of student mastery and recency decay."""
    service = ProgressService(db)
    if student_id:
        await service.recompute_student_mastery(student_id)
        await db.commit()
        return {"status": "success", "message": f"Mastery recomputed for student {student_id}"}

    # Recompute all students
    stmt = select(User.id).where(User.role == "student")
    res = await db.execute(stmt)
    student_ids = list(res.scalars().all())

    for sid in student_ids:
        await service.recompute_student_mastery(sid)

    await db.commit()
    return {"status": "success", "recomputed_count": len(student_ids)}
