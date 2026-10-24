"""Chat module endpoints with Secure Quiz lockout enforcement.

Per docs/05_SECURE_QUIZ.md §2:
- Threat: "Using the in-app AI during a quiz"
- Control: "Chat endpoint rejects while the student has an active assessed attempt; logs chat_attempt (server)"
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.dependencies import get_current_user, require_role
from core.auth.models import User
from core.common.database import get_db_session
from core.quiz.models import AttemptEvent, Quiz, QuizAttempt
from core.quiz.service import QuizService

router = APIRouter(prefix="/chat", tags=["Chat"])


async def _assert_no_active_assessed_quiz(student_id: uuid.UUID, db: AsyncSession) -> None:
    """Enforce Rule 12 from docs/05_SECURE_QUIZ.md: Chat lockout during active assessed quiz."""
    quiz_service = QuizService(db)
    is_active = await quiz_service.is_assessed_attempt_active(student_id)
    if is_active:
        # Fetch active attempt to record the telemetry violation
        stmt = (
            select(QuizAttempt)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(
                QuizAttempt.student_id == student_id,
                QuizAttempt.submitted_at.is_(None),
                Quiz.mode == "assessed",
            )
        )
        res = await db.execute(stmt)
        active_attempt = res.scalar_one_or_none()
        if active_attempt:
            # Log chat_attempt event
            event = AttemptEvent(
                attempt_id=active_attempt.id,
                type="chat_attempt",
                meta={"endpoint": "chat", "attempted_at": datetime.now(UTC).isoformat()},
            )
            db.add(event)
            # Evaluate penalty
            from core.quiz.integrity import IntegrityEngine
            IntegrityEngine.process_event(active_attempt, "chat_attempt", {})
            await db.commit()

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "QUIZ_IN_PROGRESS_CHAT_LOCKED",
                "message": "Chat is locked while an active assessed quiz attempt is in progress.",
            },
        )


@router.post(
    "/sessions",
    status_code=status.HTTP_201_CREATED,
)
async def create_chat_session(
    current_user: Annotated[User, Depends(require_role("student"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a new chat session (locked during active assessed quiz)."""
    await _assert_no_active_assessed_quiz(current_user.id, db)
    return {
        "id": str(uuid.uuid4()),
        "student_id": str(current_user.id),
        "title": (payload or {}).get("title", "New Conversation"),
        "created_at": datetime.now(UTC).isoformat(),
    }


@router.post(
    "/sessions/{session_id}/messages",
    status_code=status.HTTP_200_OK,
)
async def send_chat_message(
    session_id: uuid.UUID,
    payload: dict[str, Any],
    current_user: Annotated[User, Depends(require_role("student"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Send a message to the AI tutor (locked during active assessed quiz)."""
    await _assert_no_active_assessed_quiz(current_user.id, db)
    return {
        "id": str(uuid.uuid4()),
        "session_id": str(session_id),
        "role": "assistant",
        "content": "আমি তোমাকে এই বিষয়ে সাহায্য করতে পারি।",
        "citations": [],
    }
