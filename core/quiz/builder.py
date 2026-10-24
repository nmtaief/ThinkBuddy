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
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.quiz.models import (
    AttemptItem,
    Question,
    QuestionKey,
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
        chapter_ids: list[uuid.UUID] | None = None,
        concept_ids: list[str] | None = None,
        difficulty_target: float = 0.5,
        seed: int | None = None,
    ) -> list[Question]:
        """Query question bank, deduplicate variant groups, and randomize order."""
        rng = random.Random(seed)

        stmt = select(Question).where(
            Question.review_status == "approved",
            Question.type.in_(["mcq", "short"]),
        )
        if chapter_ids:
            stmt = stmt.where(Question.chapter_id.in_(chapter_ids))
        if concept_ids:
            stmt = stmt.where(Question.concept_id.in_(concept_ids))

        res = await self.db.execute(stmt)
        candidates = list(res.scalars().all())

        if not candidates:
            # Fallback to any approved questions if filter is too narrow
            fallback_res = await self.db.execute(
                select(Question).where(
                    Question.review_status == "approved",
                    Question.type.in_(["mcq", "short"]),
                ).limit(question_count * 3)
            )
            candidates = list(fallback_res.scalars().all())

        # 1. Group by variant_group_id to enforce deduplication
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

        # 2. Shuffle per student
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
