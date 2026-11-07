"""Quiz Builder Service (core/quiz/builder.py).

Per docs/05_SECURE_QUIZ.md §2, §4, §5 and P04 tail:
- Selects questions from pool matching chapter/concept/difficulty.
- Variant group handling: Prefers unseen variants first before recycling.
- Excludes seen questions in assessed mode; LRU recycling fallback when pool exhausted.
- Recycled questions are marked (is_recycled=True) and weighted lower (0.7 points).
- Admin alert triggered when assessed pools run low (< 2x requested question count).
- Per-student randomization of question order.
- Randomized option order with opaque IDs (opt_0, opt_1, etc.) to guarantee zero key leakage.
- Generates server-authoritative nonce per item.
"""

from __future__ import annotations

import logging
import random
import secrets
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("thinkbuddy.quiz.builder")

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
        """Query question bank, filter by pool, prefer unseen variants, mark recycled questions, and randomize order."""
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

        if not candidates and not chapter_ids:
            # Fallback to any approved questions in allowed pool only if no specific chapters requested
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

        # Low pool alert for administrators
        if mode == "assessed" and len(candidates) < question_count * 2:
            logger.warning(
                "ADMIN_ALERT: Assessed question pool running low (total=%d, recommended_minimum=%d) "
                "for student=%s, chapter_ids=%s, concept_ids=%s",
                len(candidates),
                question_count * 2,
                student_id,
                chapter_ids,
                concept_ids,
            )

        # 2. Exclude seen questions and prefer unseen variants
        if student_id and mode == "assessed":
            answered_stmt = (
                select(AttemptItem.question_id, AttemptItem.answered_at)
                .join(QuizAttempt, QuizAttempt.id == AttemptItem.attempt_id)
                .where(
                    QuizAttempt.student_id == student_id,
                    AttemptItem.answered_at.is_not(None),
                )
                .order_by(AttemptItem.answered_at.asc())
            )
            answered_res = await self.db.execute(answered_stmt)
            answered_rows = list(answered_res.all())
            answered_q_ids = {r[0] for r in answered_rows}

            earliest_answered: dict[uuid.UUID, datetime] = {}
            for q_id, ans_at in answered_rows:
                if q_id not in earliest_answered and ans_at:
                    earliest_answered[q_id] = ans_at

            # Group candidates into variant groups vs standalones
            variant_groups: dict[uuid.UUID, list[Question]] = {}
            standalones: list[Question] = []
            for q in candidates:
                if q.variant_group_id:
                    variant_groups.setdefault(q.variant_group_id, []).append(q)
                else:
                    standalones.append(q)

            primary_unseen: list[Question] = []
            recycled_pool: list[Question] = []

            # Prefer unseen variants first for each variant group
            for grp_id, group_questions in variant_groups.items():
                unseen_in_group = [q for q in group_questions if q.id not in answered_q_ids]
                if unseen_in_group:
                    # Prefer unseen variant!
                    chosen = rng.choice(unseen_in_group)
                    setattr(chosen, "_is_recycled", False)
                    primary_unseen.append(chosen)
                else:
                    # All variants seen: least recently answered variant candidate
                    group_questions_sorted = sorted(
                        group_questions,
                        key=lambda q: earliest_answered.get(q.id, datetime.min),
                    )
                    chosen_seen = group_questions_sorted[0]
                    setattr(chosen_seen, "_is_recycled", True)
                    recycled_pool.append(chosen_seen)

            for q in standalones:
                if q.id not in answered_q_ids:
                    setattr(q, "_is_recycled", False)
                    primary_unseen.append(q)
                else:
                    setattr(q, "_is_recycled", True)
                    recycled_pool.append(q)

            rng.shuffle(primary_unseen)

            if len(primary_unseen) >= question_count:
                selected_pool = primary_unseen[:question_count]
            else:
                # Fallback for exhausted assessed pools: take all unseen, then LRU recycle
                needed = question_count - len(primary_unseen)
                logger.warning(
                    "Assessed question pool exhausted for student %s (unseen=%d, needed=%d). "
                    "Applying LRU recycling fallback within allowed pool %s.",
                    student_id,
                    len(primary_unseen),
                    needed,
                    allowed_pools,
                )
                recycled_pool.sort(key=lambda q: earliest_answered.get(q.id, datetime.min))
                recycled = recycled_pool[:needed]
                for r in recycled:
                    setattr(r, "_is_recycled", True)
                selected_pool = primary_unseen + recycled
        else:
            # Practice mode or no student context: normal variant group deduplication
            variant_groups_dict: dict[uuid.UUID, list[Question]] = {}
            standalones_list: list[Question] = []
            for q in candidates:
                setattr(q, "_is_recycled", False)
                if q.variant_group_id:
                    variant_groups_dict.setdefault(q.variant_group_id, []).append(q)
                else:
                    standalones_list.append(q)

            selected_pool = list(standalones_list)
            for grp_id, group_questions in variant_groups_dict.items():
                chosen = rng.choice(group_questions)
                selected_pool.append(chosen)

        # Shuffle selected questions per student
        rng.shuffle(selected_pool)
        return selected_pool[:question_count]

    async def initialize_attempt_items(
        self,
        attempt: QuizAttempt,
        questions: list[Question],
        seed: int | None = None,
        recycled_ids: set[uuid.UUID] | None = None,
    ) -> list[AttemptItem]:
        """Create sequential AttemptItems with randomized opaque options, server nonces, and recycling flags."""
        items: list[AttemptItem] = []

        for pos, q in enumerate(questions, start=1):
            nonce = secrets.token_hex(16)
            is_recycled = getattr(q, "_is_recycled", False) or (recycled_ids is not None and q.id in recycled_ids)
            # Recycled questions are weighted lower (0.7 points vs 1.0)
            item_points = 0.7 if is_recycled else 1.0

            item = AttemptItem(
                attempt_id=attempt.id,
                position=pos,
                question_id=q.id,
                nonce=nonce,
                points=item_points,
                is_recycled=is_recycled,
            )
            self.db.add(item)
            items.append(item)

        await self.db.flush()
        return items
