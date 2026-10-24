"""API Endpoints for Secure Quiz Engine (P04).

Conforms strictly to:
- docs/04_API_CONTRACT.md §2 (Quiz)
- docs/05_SECURE_QUIZ.md §2, §4, §5
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.dependencies import get_current_user, require_role
from core.auth.models import User
from core.common.database import get_db_session
from core.quiz.models import Quiz
from core.quiz.schemas import (
    AnswerItemRequest,
    AnswerItemResponse,
    AttemptEventRequest,
    AttemptEventResponse,
    AttemptReviewResponse,
    StartAttemptRequest,
    StartAttemptResponse,
    SubmitAttemptResponse,
)
from core.quiz.service import QuizService

router = APIRouter(tags=["Quiz"])


def _extract_token(authorization: str | None, x_attempt_token: str | None) -> str:
    """Extract attempt token from X-Attempt-Token header or Authorization header."""
    if x_attempt_token:
        return x_attempt_token
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
    return ""


# ---------------------------------------------------------------------------
# Helper: Create Quiz for Student
# ---------------------------------------------------------------------------


@router.post(
    "/students/{student_id}/quizzes",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
)
async def create_student_quiz(
    student_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Create a quiz session for a student."""
    # Ownership: self or linked parent or admin
    if current_user.role != "admin" and current_user.id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Cannot create quiz for another student."},
        )

    service = QuizService(db)
    chapter_ids = [uuid.UUID(c) for c in payload.get("chapter_ids", [])] if payload.get("chapter_ids") else None
    quiz = await service.builder.build_quiz(
        student_id=student_id,
        chapter_ids=chapter_ids,
        concept_ids=payload.get("concept_ids"),
        title=payload.get("title", "Daily Quiz"),
        kind=payload.get("kind", "daily"),
        mode=payload.get("mode", "assessed"),
        question_count=payload.get("question_count", 5),
        time_limit_s=payload.get("time_limit_s", 600),
    )
    await db.commit()

    return {
        "id": str(quiz.id),
        "student_id": str(quiz.student_id),
        "title": quiz.title,
        "kind": quiz.kind,
        "mode": quiz.mode,
        "time_limit_s": quiz.time_limit_s,
        "question_count": quiz.question_count,
    }


# ---------------------------------------------------------------------------
# Attempt Endpoints (docs/04_API_CONTRACT.md §2)
# ---------------------------------------------------------------------------


@router.post(
    "/quizzes/{quiz_id}/attempts",
    response_model=StartAttemptResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_quiz_attempt(
    quiz_id: uuid.UUID,
    payload: StartAttemptRequest,
    current_user: Annotated[User, Depends(require_role("student"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_client_platform: str = Header("android", alias="X-Client-Platform"),
    x_device_id: str | None = Header(None, alias="X-Device-Id"),
) -> StartAttemptResponse:
    """Start a quiz attempt.
    
    Enforces:
    - Web platform practice-only restriction
    - One-active-assessed-attempt limit per student
    - Sequential question serving (Rule 6: answer keys withheld)
    """
    service = QuizService(db)
    return await service.start_attempt(
        quiz_id=quiz_id,
        student_id=current_user.id,
        client_platform=x_client_platform,
        device_id=payload.device_id or x_device_id,
    )


@router.post(
    "/attempts/{attempt_id}/items/{position}/answer",
    response_model=AnswerItemResponse,
    status_code=status.HTTP_200_OK,
)
async def answer_quiz_item(
    attempt_id: uuid.UUID,
    position: int,
    payload: AnswerItemRequest,
    current_user: Annotated[User, Depends(require_role("student"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: str | None = Header(None),
    x_attempt_token: str | None = Header(None, alias="X-Attempt-Token"),
) -> AnswerItemResponse:
    """Submit one item answer in sequence.
    
    Enforces:
    - Server deadline authority (expired attempts rejected and auto-submitted)
    - Per-item server nonce verification preventing replay
    - Withholds correctness feedback in assessed mode until submit
    """
    token = _extract_token(authorization, x_attempt_token)
    service = QuizService(db)
    return await service.answer_item(
        attempt_id=attempt_id,
        position=position,
        student_id=current_user.id,
        nonce=payload.nonce,
        response=payload.response,
        time_spent_ms=payload.time_spent_ms,
        token=token,
    )


@router.post(
    "/attempts/{attempt_id}/events",
    response_model=AttemptEventResponse,
    status_code=status.HTTP_200_OK,
)
async def record_attempt_event(
    attempt_id: uuid.UUID,
    payload: AttemptEventRequest,
    current_user: Annotated[User, Depends(require_role("student"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: str | None = Header(None),
    x_attempt_token: str | None = Header(None, alias="X-Attempt-Token"),
) -> AttemptEventResponse:
    """Ingest anti-cheat telemetry events (background, focus loss, screenshot, overlay)."""
    token = _extract_token(authorization, x_attempt_token)
    service = QuizService(db)
    recorded, score, current_state = await service.record_event(
        attempt_id=attempt_id,
        student_id=current_user.id,
        event_type=payload.type,
        meta=payload.meta,
        token=token,
    )
    return AttemptEventResponse(
        recorded=recorded,
        integrity_score=score,
        state=current_state,
    )


@router.post(
    "/attempts/{attempt_id}/submit",
    response_model=SubmitAttemptResponse,
    status_code=status.HTTP_200_OK,
)
async def submit_quiz_attempt(
    attempt_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role("student"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    authorization: str | None = Header(None),
    x_attempt_token: str | None = Header(None, alias="X-Attempt-Token"),
) -> SubmitAttemptResponse:
    """Finalize quiz attempt, compute auto-grade score, emit learning signals, and unlock review."""
    token = _extract_token(authorization, x_attempt_token)
    service = QuizService(db)
    return await service.submit_attempt(
        attempt_id=attempt_id,
        student_id=current_user.id,
        token=token,
    )


@router.get(
    "/attempts/{attempt_id}/review",
    response_model=AttemptReviewResponse,
    status_code=status.HTTP_200_OK,
)
async def review_quiz_attempt(
    attempt_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AttemptReviewResponse:
    """Get full quiz review with correct answers and explanations.
    
    Rule 6: Strictly rejects with 403 FORBIDDEN while attempt is active!
    """
    service = QuizService(db)
    return await service.review_attempt(
        attempt_id=attempt_id,
        student_id=current_user.id,
    )
