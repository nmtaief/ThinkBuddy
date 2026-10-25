"""Server-Side Auto-Grading & Learning Signal Authority (core/quiz/grading.py).

Per docs/03_DATA_MODEL.md §4, §6 and docs/05_SECURE_QUIZ.md:
- Strictly queries `question_keys` inside this service only.
- Evaluates MCQ and short answers.
- Queues broad answers for rubric review.
- Writes `learning_signals` records with ON CONFLICT DO NOTHING idempotency.
- Applies reduced mastery weight for unverified devices (0.7x) and recycled items (0.7x).
"""

from __future__ import annotations

import logging
import re
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.quiz.models import (
    AttemptItem,
    BroadSubmission,
    LearningSignal,
    Question,
    QuestionKey,
    QuizAttempt,
)

logger = logging.getLogger("thinkbuddy.quiz.grading")


BN_DIGIT_MAP = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
ZERO_WIDTH_CHARS = re.compile(r"[\u200b\u200c\u200d\ufeff\u00a0]")


def normalize_bangla_text(text: str | None) -> str:
    """Normalize Bangla and English text for fair and robust short answer grading."""
    if not text:
        return ""
    s = unicodedata.normalize("NFC", str(text))
    s = ZERO_WIDTH_CHARS.sub("", s)
    s = s.translate(BN_DIGIT_MAP)
    return " ".join(s.strip().lower().split())


class QuizGradingService:
    """Server-side authority for grading attempts and emitting learning signals."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def grade_item(
        self,
        item: AttemptItem,
        response: dict[str, Any],
        time_spent_ms: int,
    ) -> bool:
        """Grade a single item response against the isolated question key."""
        item.answered_at = datetime.now(UTC)
        item.response = response
        item.time_spent_ms = time_spent_ms

        # Fetch isolated key
        key_res = await self.db.execute(
            select(QuestionKey).where(QuestionKey.question_id == item.question_id)
        )
        q_key = key_res.scalar_one_or_none()
        if not q_key:
            logger.warning("No question key found for question %s", item.question_id)
            item.is_correct = False
            item.points = 0.0
            return False

        # Fetch question details for type
        q_res = await self.db.execute(select(Question).where(Question.id == item.question_id))
        question = q_res.scalar_one_or_none()
        q_type = question.type if question else "mcq"

        is_correct = False
        if q_type == "mcq":
            selected_opt = str(response.get("selected_option_id", "")).strip()
            # Must match correct_option_id (or correct_text if option was text-based)
            is_correct = False
            if q_key.correct_option_id and selected_opt == str(q_key.correct_option_id).strip():
                is_correct = True
            elif q_key.correct_text and selected_opt == str(q_key.correct_text).strip():
                is_correct = True
        elif q_type == "short":
            norm_student = normalize_bangla_text(response.get("text"))
            accepted = [normalize_bangla_text(q_key.correct_text)]
            if q_key.accepted_answers:
                accepted.extend([normalize_bangla_text(a) for a in q_key.accepted_answers if a])
            is_correct = any(norm_student == acc for acc in accepted if acc)
        elif q_type == "broad":
            # Broad subjective answer: queue broad submission
            submission = BroadSubmission(
                attempt_item_id=item.id,
                text=response.get("text"),
                image_uris=response.get("image_uris", []),
                ai_feedback={},
                status="ai_reviewed",
            )
            self.db.add(submission)
            is_correct = False  # Pending evaluation

        item.is_correct = is_correct
        max_points = 0.7 if getattr(item, "is_recycled", False) else 1.0
        item.points = max_points if is_correct else 0.0

        return is_correct

    async def finalize_and_emit_signals(self, attempt: QuizAttempt) -> float:
        """Compute final score, update attempt, and write learning signals with ON CONFLICT DO NOTHING."""
        items_res = await self.db.execute(
            select(AttemptItem).where(AttemptItem.attempt_id == attempt.id)
        )
        items = list(items_res.scalars().all())

        if not items:
            attempt.score = 0.0
            return 0.0

        total_points = sum(it.points for it in items)
        max_possible = sum(0.7 if getattr(it, "is_recycled", False) else 1.0 for it in items)
        final_score = round((total_points / max_possible) * 100.0, 1) if max_possible > 0 else 0.0
        attempt.score = final_score

        # Reduced mastery weight scaling for unverified devices (0.7x)
        device_mult = 0.7 if getattr(attempt, "unverified_device", False) else 1.0

        # Emit learning signals for mistakes and slow responses idempotently via ON CONFLICT DO NOTHING
        for it in items:
            recycled_mult = 0.7 if getattr(it, "is_recycled", False) else 1.0

            # Mistake signal
            if it.is_correct is False:
                q_res = await self.db.execute(select(Question).where(Question.id == it.question_id))
                q = q_res.scalar_one_or_none()
                if q:
                    weight_wrong = round(1.0 * device_mult * recycled_mult, 2)
                    stmt_wrong = (
                        pg_insert(LearningSignal)
                        .values(
                            id=uuid.uuid4(),
                            student_id=attempt.student_id,
                            source="quiz_wrong",
                            chapter_id=q.chapter_id,
                            concept_id=q.concept_id,
                            weight=weight_wrong,
                            ref_id=str(it.id),
                            at=datetime.now(UTC),
                        )
                        .on_conflict_do_nothing(
                            index_elements=["student_id", "source", "ref_id"]
                        )
                    )
                    await self.db.execute(stmt_wrong)

            # Slow response signal (> 90s)
            if it.time_spent_ms > 90000:
                q_res = await self.db.execute(select(Question).where(Question.id == it.question_id))
                q = q_res.scalar_one_or_none()
                if q:
                    weight_slow = round(0.5 * device_mult * recycled_mult, 2)
                    stmt_slow = (
                        pg_insert(LearningSignal)
                        .values(
                            id=uuid.uuid4(),
                            student_id=attempt.student_id,
                            source="quiz_slow",
                            chapter_id=q.chapter_id,
                            concept_id=q.concept_id,
                            weight=weight_slow,
                            ref_id=str(it.id),
                            at=datetime.now(UTC),
                        )
                        .on_conflict_do_nothing(
                            index_elements=["student_id", "source", "ref_id"]
                        )
                    )
                    await self.db.execute(stmt_slow)

        await self.db.flush()
        return final_score
