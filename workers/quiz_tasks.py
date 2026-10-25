"""Scheduled background tasks for quiz expiration, auto-grading, and signal emission.

Per docs/05_SECURE_QUIZ.md §4:
- Auto-submits expired attempts whose server-side deadline has passed.
- Evaluates unanswered and pending items.
- Calculates final score.
- Writes learning signals for mastery and adaptive review engines.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.common.database import AsyncSessionLocal
from core.quiz.grading import QuizGradingService
from core.quiz.models import OPEN_ATTEMPT_STATES, QuizAttempt
from workers.celery_app import celery_app

logger = logging.getLogger("thinkbuddy.workers.quiz_tasks")


def utcnow() -> datetime:
    return datetime.now(UTC)


async def auto_submit_expired_attempts(db: AsyncSession | None = None) -> int:
    """Find and finalize all expired quiz attempts whose deadline has passed."""
    if db is not None:
        return await _process_expired_attempts(db)

    async with AsyncSessionLocal() as session:
        return await _process_expired_attempts(session)


async def _process_expired_attempts(session: AsyncSession) -> int:
    """Internal implementation for processing expired attempts using FOR UPDATE SKIP LOCKED."""
    now = utcnow()
    stmt = (
        select(QuizAttempt)
        .options(selectinload(QuizAttempt.items))
        .where(
            QuizAttempt.submitted_at.is_(None),
            QuizAttempt.deadline_at.is_not(None),
            QuizAttempt.deadline_at <= now,
            QuizAttempt.state.in_(OPEN_ATTEMPT_STATES),
        )
        .with_for_update(skip_locked=True)
    )
    res = await session.execute(stmt)
    expired_attempts = list(res.scalars().all())

    if not expired_attempts:
        return 0

    grading_service = QuizGradingService(session)
    count = 0

    for attempt in expired_attempts:
        # Idempotency check: if another process submitted in the interim
        if attempt.submitted_at is not None:
            continue

        attempt.state = "expired"
        attempt.submitted_at = attempt.deadline_at or now

        # Evaluate all items
        for item in attempt.items:
            if item.answered_at is not None and item.is_correct is None and item.response:
                await grading_service.grade_item(item, item.response, item.time_spent_ms)
            elif item.answered_at is None:
                item.is_correct = False
                item.points = 0.0

        await grading_service.finalize_and_emit_signals(attempt)
        count += 1
        logger.info(
            "Auto-submitted expired attempt %s for student %s (score: %.2f)",
            attempt.id,
            attempt.student_id,
            attempt.score or 0.0,
        )

    await session.commit()
    return count


@celery_app.task(name="auto_submit_expired_attempts")
def auto_submit_expired_attempts_task() -> dict[str, Any]:
    """Celery scheduled task to automatically submit expired attempts periodically."""
    count = asyncio.run(auto_submit_expired_attempts())
    return {
        "status": "ok",
        "processed_count": count,
        "timestamp": utcnow().isoformat(),
    }
