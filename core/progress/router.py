"""API routes for student progress, mastery, spaced revision, and adaptive background jobs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.common.database import get_db_session
from core.common.policy import can_access_student
from core.progress.jobs import run_daily_composition_job, run_three_day_review_cycle
from core.progress.revision import RevisionScheduler
from core.progress.schemas import (
    ChapterMasteryItem,
    DailyProgressRecord,
    NeedsPracticeTopic,
    ProgressSummaryResponse,
    RevisionItemResponse,
    RevisionReviewRequest,
)
from core.progress.service import ProgressService

router = APIRouter(tags=["Progress"])


async def resolve_student_access(
    current_user: User,
    db: AsyncSession,
    requested_student_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Enforce Standing Rule 9: Role checks + ownership checks."""
    if current_user.role == "student":
        if requested_student_id and requested_student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Students can only access their own data."},
            )
        return current_user.id

    if current_user.role == "parent":
        if not requested_student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "STUDENT_ID_REQUIRED", "message": "student_id is required for parent access."},
            )
        is_linked = await can_access_student(current_user, requested_student_id, db)
        if not is_linked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "UNLINKED_STUDENT_ACCESS", "message": "Parent is not linked to this student."},
            )
        return requested_student_id

    if current_user.role == "admin":
        if not requested_student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "STUDENT_ID_REQUIRED", "message": "student_id is required for admin view."},
            )
        return requested_student_id

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "FORBIDDEN", "message": "Unauthorized role for progress access."},
    )


@router.get("/progress/summary", response_model=ProgressSummaryResponse)
async def get_progress_summary_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    student_id: uuid.UUID | None = Query(None, description="Target student ID for linked parents"),
) -> ProgressSummaryResponse:
    """Get overall progress, mastery score, confidence, and streak for student/parent dashboard."""
    target_id = await resolve_student_access(current_user, db, student_id)
    service = ProgressService(db)
    return await service.get_progress_summary(target_id)


@router.get("/progress/mastery", response_model=list[ChapterMasteryItem])
async def get_chapter_mastery_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    student_id: uuid.UUID | None = Query(None, description="Target student ID for linked parents"),
) -> list[ChapterMasteryItem]:
    """Get chapter-by-chapter mastery scores and statuses ('mastered', 'needs_practice', 'not_enough_data')."""
    target_id = await resolve_student_access(current_user, db, student_id)
    service = ProgressService(db)
    return await service.get_chapter_mastery(target_id)


@router.get("/progress/weak-points", response_model=list[NeedsPracticeTopic])
async def get_needs_practice_topics_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    student_id: uuid.UUID | None = Query(None, description="Target student ID for linked parents"),
) -> list[NeedsPracticeTopic]:
    """Get topics needing practice and suggested interventions (Requirement 7: never labeled 'weak')."""
    target_id = await resolve_student_access(current_user, db, student_id)
    service = ProgressService(db)
    return await service.get_needs_practice_topics(target_id)


@router.get("/progress/history", response_model=list[DailyProgressRecord])
async def get_progress_history_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    student_id: uuid.UUID | None = Query(None, description="Target student ID for linked parents"),
    days: int = Query(30, ge=1, le=180, description="Historical lookback days"),
) -> list[DailyProgressRecord]:
    """Get daily study history, minutes, tasks completed, and quiz averages."""
    target_id = await resolve_student_access(current_user, db, student_id)
    from sqlalchemy import select

    from core.progress.models import ProgressDaily

    start_date = datetime.now(UTC).date() - timedelta(days=days)
    stmt = (
        select(ProgressDaily)
        .where(
            ProgressDaily.student_id == target_id,
            ProgressDaily.date >= start_date,
        )
        .order_by(ProgressDaily.date.desc())
    )
    res = await db.execute(stmt)
    records = list(res.scalars().all())
    return [DailyProgressRecord.model_validate(r) for r in records]


@router.get("/revision/daily", response_model=list[RevisionItemResponse])
async def get_daily_revision_items_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    student_id: uuid.UUID | None = Query(None, description="Target student ID for linked parents"),
) -> list[RevisionItemResponse]:
    """Get spaced repetition items due today ordered by Leitner box priority and capped by minutes."""
    target_id = await resolve_student_access(current_user, db, student_id)
    now_dt = datetime.now(UTC)
    scheduler = RevisionScheduler(db)
    items = await scheduler.get_due_items(
        student_id=target_id,
        target_date=now_dt.date(),
        now_dt=now_dt,
        available_minutes=15,
    )
    responses: list[RevisionItemResponse] = []
    for it in items:
        ch_title = it.chapter.title if it.chapter else "General Topic"
        subj = it.chapter.book.subject if it.chapter and it.chapter.book else "General"
        responses.append(
            RevisionItemResponse(
                id=it.id,
                chapter_id=it.chapter_id,
                chapter_title=ch_title,
                subject=subj,
                question_id=it.question_id,
                box=it.box,
                due_at=it.due_at,
                is_overdue=it.due_at <= now_dt,
                last_result=it.last_result,
            )
        )
    return responses


@router.post("/revision/{item_id}/review", response_model=RevisionItemResponse)
async def review_revision_item_endpoint(
    item_id: uuid.UUID,
    payload: RevisionReviewRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RevisionItemResponse:
    """Submit revision item review result, promoting (box+1) or demoting (box=1)."""
    now_dt = datetime.now(UTC)
    scheduler = RevisionScheduler(db)
    is_correct = payload.result == "correct"
    updated = await scheduler.record_review(
        item_id=item_id,
        student_id=current_user.id,
        is_correct=is_correct,
        now_dt=now_dt,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REVISION_ITEM_NOT_FOUND", "message": "Revision item not found."},
        )

    ch_title = updated.chapter.title if updated.chapter else "General Topic"
    subj = updated.chapter.book.subject if updated.chapter and updated.chapter.book else "General"
    return RevisionItemResponse(
        id=updated.id,
        chapter_id=updated.chapter_id,
        chapter_title=ch_title,
        subject=subj,
        question_id=updated.question_id,
        box=updated.box,
        due_at=updated.due_at,
        is_overdue=updated.due_at <= now_dt,
        last_result=updated.last_result,
    )


# -----------------------------------------------------------------------------
# Internal / Administrative Background Jobs
# -----------------------------------------------------------------------------
@router.post("/internal/jobs/daily-composition")
async def trigger_daily_composition_endpoint(
    student_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Trigger daily adaptive composition for a student (idempotent, regenerates planner)."""
    new_version = await run_daily_composition_job(db, student_id)
    return {"status": "ok", "student_id": str(student_id), "plan_version": new_version}


@router.post("/internal/jobs/three-day-review")
async def trigger_three_day_review_endpoint(
    student_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Trigger 3-day review cycle for a student (builds review quiz, regenerates planner)."""
    new_version, quiz_id = await run_three_day_review_cycle(db, student_id)
    return {
        "status": "ok",
        "student_id": str(student_id),
        "plan_version": new_version,
        "review_quiz_id": str(quiz_id) if quiz_id else None,
    }
