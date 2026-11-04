"""API Endpoints for Secure Quiz Engine (P04).

Conforms strictly to:
- docs/04_API_CONTRACT.md §2 (Quiz)
- docs/05_SECURE_QUIZ.md §2, §4, §5
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.dependencies import get_current_user, require_role
from core.auth.models import User
from core.common.database import get_db_session
from core.common.service_token import require_internal_service_token
from core.quiz.models import OPEN_ATTEMPT_STATES, QuizAttempt
from core.quiz.schemas import (
    AllowAttemptRequest,
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
    chapter_ids = (
        [uuid.UUID(c) for c in payload.get("chapter_ids", [])]
        if payload.get("chapter_ids")
        else None
    )
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
    "/quizzes/{quiz_id}/attempts/create",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
)
async def create_quiz_attempt_endpoint(
    quiz_id: uuid.UUID,
    payload: StartAttemptRequest,
    current_user: Annotated[User, Depends(require_role("student"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_client_platform: str = Header("android", alias="X-Client-Platform"),
    x_device_id: str | None = Header(None, alias="X-Device-Id"),
) -> dict[str, Any]:
    """Create a quiz attempt in state 'created' with a short 5-minute expiry.

    Returns attempt_id and integrity_nonce (bound to attempt_id) for Play Integrity.
    """
    service = QuizService(db)
    attempt = await service.create_attempt(
        quiz_id=quiz_id,
        student_id=current_user.id,
        client_platform=x_client_platform,
        device_id=payload.device_id or x_device_id,
    )
    raw_nonce = getattr(attempt, "_raw_nonce", str(attempt.id))
    return {
        "attempt_id": str(attempt.id),
        "state": attempt.state,
        "nonce": raw_nonce,
        "deadline_at": attempt.deadline_at.isoformat() if attempt.deadline_at else None,
        "attempt_token": attempt.attempt_token,
    }


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
    request: Request,
    x_client_platform: str = Header("android", alias="X-Client-Platform"),
    x_device_id: str | None = Header(None, alias="X-Device-Id"),
    x_device_integrity: str | None = Header(None, alias="X-Device-Integrity"),
) -> StartAttemptResponse:
    """Start a quiz attempt.

    Enforces:
    - Web platform practice-only restriction
    - Device integrity verdict (Play Integrity / App Attest)
    - One-active-assessed-attempt limit per student
    - Sequential question serving (Rule 6: answer keys withheld)
    """
    service = QuizService(db)
    return await service.start_attempt(
        quiz_id=quiz_id,
        student_id=current_user.id,
        client_platform=x_client_platform,
        device_id=payload.device_id or x_device_id,
        integrity_verdict=payload.integrity_token or payload.integrity_verdict or x_device_integrity,
        headers=dict(request.headers),
        attempt_id=payload.attempt_id,
    )


@router.post(
    "/attempts/{attempt_id}/attest",
    response_model=StartAttemptResponse,
    status_code=status.HTTP_200_OK,
)
async def attest_quiz_attempt(
    attempt_id: uuid.UUID,
    payload: StartAttemptRequest,
    current_user: Annotated[User, Depends(require_role("student"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    request: Request,
    x_client_platform: str = Header("android", alias="X-Client-Platform"),
    x_device_id: str | None = Header(None, alias="X-Device-Id"),
    x_device_integrity: str | None = Header(None, alias="X-Device-Integrity"),
) -> StartAttemptResponse:
    """Attest and activate a created quiz attempt using Play Integrity token.

    Moves attempt state from 'created' to 'active'.
    Validates single-use random server nonce and enforces device downgrade prevention.
    """
    service = QuizService(db)
    attempt_res = await db.execute(select(QuizAttempt).where(QuizAttempt.id == attempt_id))
    attempt = attempt_res.scalar_one_or_none()
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ATTEMPT_NOT_FOUND", "message": "Attempt not found."},
        )
    return await service.start_attempt(
        quiz_id=attempt.quiz_id,
        student_id=current_user.id,
        client_platform=x_client_platform,
        device_id=payload.device_id or x_device_id,
        integrity_verdict=payload.integrity_token or payload.integrity_verdict or x_device_integrity,
        headers=dict(request.headers),
        attempt_id=attempt_id,
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
        user=current_user,
    )


@router.post(
    "/attempts/{attempt_id}/allow",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    tags=["Quiz"],
)
async def allow_quiz_attempt(
    attempt_id: uuid.UUID,
    payload: AllowAttemptRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Parent or admin override to allow an attempt that was warned, paused, or invalidated."""
    service = QuizService(db)
    attempt = await service.allow_attempt(attempt_id, current_user, payload.reason)
    return {
        "attempt_id": str(attempt.id),
        "state": attempt.state,
        "integrity_score": attempt.integrity_score,
        "invalid_reason": attempt.invalid_reason,
        "allowed": True,
    }


# ---------------------------------------------------------------------------
# Internal Gateway & Chat Support Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/internal/quiz/students/{student_id}/active-attempt",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
)
async def is_assessed_attempt_active(
    student_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _service_token: Annotated[dict[str, Any], Depends(require_internal_service_token)],
) -> dict[str, Any]:
    """Internal service endpoint used by gateway/chat to detect active assessed attempts."""
    service = QuizService(db)
    is_active = await service.is_assessed_attempt_active(student_id)
    attempt_info: dict[str, Any] = {
        "student_id": str(student_id),
        "is_active": is_active,
        "attempt_id": None,
        "deadline_at": None,
        "mode": None,
        "state": None,
    }
    if is_active:
        stmt = (
            select(QuizAttempt)
            .where(
                QuizAttempt.student_id == student_id,
                QuizAttempt.state.in_(OPEN_ATTEMPT_STATES),
                QuizAttempt.mode == "assessed",
            )
            .limit(1)
        )
        res = await db.execute(stmt)
        attempt = res.scalar_one_or_none()
        if attempt:
            attempt_info.update(
                {
                    "attempt_id": str(attempt.id),
                    "deadline_at": attempt.deadline_at.isoformat() if attempt.deadline_at else None,
                    "mode": attempt.mode,
                    "state": attempt.state,
                }
            )

    return attempt_info
