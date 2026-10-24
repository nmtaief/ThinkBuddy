"""Admin API Endpoints for Question Bank Management (P04).

Admin-only routes to create, import, and review question bank items and isolated question keys.
All admin operations write immutable audit records to audit_log.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit.models import AuditLog
from core.auth.dependencies import require_role
from core.auth.models import User
from core.common.database import get_db_session
from core.quiz.models import Question, QuestionKey
from core.quiz.schemas import QuestionAdminCreate

logger = logging.getLogger("thinkbuddy.quiz.admin")

router = APIRouter(prefix="/admin/questions", tags=["Admin - Question Bank"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
async def create_question_admin(
    payload: QuestionAdminCreate,
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Create a new question bank item and its isolated question key."""
    q = Question(
        type=payload.type,
        chapter_id=payload.chapter_id,
        concept_id=payload.concept_id,
        difficulty=payload.difficulty,
        language=payload.language,
        stem=payload.stem,
        options=[opt.model_dump() for opt in payload.options],
        rubric=payload.rubric,
        explanation=payload.explanation,
        source_chunk_ids=payload.source_chunk_ids,
        origin=payload.origin,
        review_status=payload.review_status,
        variant_group_id=payload.variant_group_id,
    )
    db.add(q)
    await db.flush()

    # Store isolated key
    key = QuestionKey(
        question_id=q.id,
        correct_option_id=payload.correct_option_id,
        correct_text=payload.correct_text,
        grading_rules=payload.grading_rules,
        explanation=payload.explanation,
    )
    db.add(key)

    # Audit log
    audit = AuditLog(
        actor_id=current_user.id,
        action="question.create",
        target_type="question",
        target_id=str(q.id),
        meta={"type": q.type, "chapter_id": str(q.chapter_id) if q.chapter_id else None},
    )
    db.add(audit)
    await db.commit()

    return {
        "id": str(q.id),
        "type": q.type,
        "chapter_id": str(q.chapter_id) if q.chapter_id else None,
        "review_status": q.review_status,
        "created_at": q.created_at.isoformat(),
    }


@router.post(
    "/import",
    status_code=status.HTTP_201_CREATED,
)
async def import_questions_bulk(
    items: list[QuestionAdminCreate],
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Bulk import questions and question keys with audit logging."""
    created_count = 0
    for payload in items:
        q = Question(
            type=payload.type,
            chapter_id=payload.chapter_id,
            concept_id=payload.concept_id,
            difficulty=payload.difficulty,
            language=payload.language,
            stem=payload.stem,
            options=[opt.model_dump() for opt in payload.options],
            rubric=payload.rubric,
            explanation=payload.explanation,
            source_chunk_ids=payload.source_chunk_ids,
            origin=payload.origin,
            review_status=payload.review_status,
            variant_group_id=payload.variant_group_id,
        )
        db.add(q)
        await db.flush()

        key = QuestionKey(
            question_id=q.id,
            correct_option_id=payload.correct_option_id,
            correct_text=payload.correct_text,
            grading_rules=payload.grading_rules,
            explanation=payload.explanation,
        )
        db.add(key)
        created_count += 1

    audit = AuditLog(
        actor_id=current_user.id,
        action="question.bulk_import",
        target_type="question_bank",
        target_id="bulk",
        meta={"count": created_count},
    )
    db.add(audit)
    await db.commit()

    return {"imported_count": created_count, "status": "success"}


@router.get(
    "",
    status_code=status.HTTP_200_OK,
)
async def list_questions_admin(
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    chapter_id: uuid.UUID | None = Query(default=None),
    review_status: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    """List questions in question bank."""
    stmt = select(Question)
    if chapter_id:
        stmt = stmt.where(Question.chapter_id == chapter_id)
    if review_status:
        stmt = stmt.where(Question.review_status == review_status)

    res = await db.execute(stmt)
    questions = res.scalars().all()

    return [
        {
            "id": str(q.id),
            "type": q.type,
            "chapter_id": str(q.chapter_id) if q.chapter_id else None,
            "concept_id": q.concept_id,
            "difficulty": q.difficulty,
            "language": q.language,
            "review_status": q.review_status,
            "options_count": len(q.options),
        }
        for q in questions
    ]
