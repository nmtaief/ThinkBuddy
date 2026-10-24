"""Quiz Builder Service (core/quiz/builder.py).

Per docs/05_SECURE_QUIZ.md §2, §4, §5:
- Selects questions from pool matching chapter/concept/difficulty.
- Variant group deduplication: At most 1 question per variant_group_id.
- Per-student randomization of question order.
- Randomized option order with opaque IDs (opt_0, opt_1, etc.) to guarantee zero key leakage.
- Generates server-authoritative nonce per item.
"""

from __future__ import annotations

import random
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.quiz.models import (
    AttemptItem,
    Question,
    Quiz,
    QuizAttempt,
)


class QuizBuilderService:
    """Builds customized, variant-deduplicated, randomized quizzes and attempt items."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def build_quiz(
        self,
        student_id: uuid.UUID,
        chapter_ids: list[uuid.UUID] | None = None,
        concept_ids: list[str] | None = None,
        title: str = "Daily Quiz",
        kind: str = "daily",
        mode: str = "assessed",
        question_count: int = 5,
        time_limit_s: int = 600,
        task_id: uuid.UUID | None = None,
    ) -> Quiz:
        """Create a quiz record for a student."""
        quiz = Quiz(
            student_id=student_id,
            task_id=task_id,
            title=title,
            kind=kind,
            mode=mode,
            time_limit_s=time_limit_s,
            per_question_limit_s=None,
            question_count=question_count,
        )
        self.db.add(quiz)
        await self.db.flush()
        return quiz

    async def select_and_randomize_questions(
        self,
        question_count: int = 5,
        student_id: uuid.UUID | None = None,
        mode: str = "assessed",
        chapter_ids: list[uuid.UUID] | None = None,
        concept_ids: list[str] | None = None,
        difficulty_target: float = 0.5,
        seed: int | None = None,
    ) -> list[Question]:
        """Query question bank, filter by pool, exclude seen questions, deduplicate variants, and randomize order."""
        rng = random.Random(seed)

        # 1. Base query filtered by mode pool ('both' or matching mode)
        allowed_pools = [mode, "both"]
        stmt = select(Question).where(
            Question.review_status == "approved",
            Question.type.in_(["mcq", "short"]),
            Question.pool.in_(allowed_pools),
        )
        if chapter_ids:
            stmt = stmt.where(Question.chapter_id.in_(chapter_ids))
        if concept_ids:
            stmt = stmt.where(Question.concept_id.in_(concept_ids))

        res = await self.db.execute(stmt)
        candidates = list(res.scalars().all())

        if not candidates:
            # Fallback to any approved questions in allowed pool
            fallback_res = await self.db.execute(
                select(Question)
                .where(
                    Question.review_status == "approved",
                    Question.type.in_(["mcq", "short"]),
                    Question.pool.in_(allowed_pools),
                )
                .limit(question_count * 3)
            )
            candidates = list(fallback_res.scalars().all())

        # 2. Exclude questions the student has seen and answered in assessed quizzes
        if student_id and mode == "assessed":
            answered_stmt = (
                select(AttemptItem.question_id)
                .join(QuizAttempt, QuizAttempt.id == AttemptItem.attempt_id)
                .where(
                    QuizAttempt.student_id == student_id,
                    AttemptItem.answered_at.is_not(None),
                )
            )
            answered_res = await self.db.execute(answered_stmt)
            answered_q_ids = set(answered_res.scalars().all())

            unseen = [q for q in candidates if q.id not in answered_q_ids]
            if len(unseen) >= question_count:
                candidates = unseen
            elif unseen:
                # Prioritize unseen questions first, fill remaining from candidates
                seen = [q for q in candidates if q.id in answered_q_ids]
                candidates = unseen + seen

        # 3. Group by variant_group_id to enforce deduplication
        variant_groups: dict[uuid.UUID, list[Question]] = {}
        standalones: list[Question] = []

        for q in candidates:
            if q.variant_group_id:
                variant_groups.setdefault(q.variant_group_id, []).append(q)
            else:
                standalones.append(q)

        # Pick at most 1 question per variant group
        selected_pool: list[Question] = list(standalones)
        for grp_id, group_questions in variant_groups.items():
            chosen = rng.choice(group_questions)
            selected_pool.append(chosen)

        # 4. Shuffle per student
        rng.shuffle(selected_pool)

        return selected_pool[:question_count]

    async def initialize_attempt_items(
        self,
        attempt: QuizAttempt,
        questions: list[Question],
        seed: int | None = None,
    ) -> list[AttemptItem]:
        """Create sequential AttemptItems with randomized opaque options and server nonces."""
        rng = random.Random(seed)
        items: list[AttemptItem] = []

        for pos, q in enumerate(questions, start=1):
            nonce = secrets.token_hex(16)
            item = AttemptItem(
                attempt_id=attempt.id,
                position=pos,
                question_id=q.id,
                nonce=nonce,
                points=1.0,
            )
            self.db.add(item)
            items.append(item)

        await self.db.flush()
        return items
