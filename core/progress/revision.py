"""Spaced revision scheduler using Leitner 5-box system.

Deliverable 3 & Requirement 4:
- Leitner boxes 1 to 5 with configured intervals (1, 3, 7, 14, 30 days).
- Promote on correct (box + 1), demote on wrong (box = 1).
- Cap revision queue by available daily minutes.
- Exclude subjects in blackout on the target date or past their exam date.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.curriculum.models import Chapter
from core.planner.models import StudySetup
from core.progress.models import Mastery, RevisionItem

# Default Leitner intervals in days
LEITNER_INTERVALS = {
    1: timedelta(days=1),
    2: timedelta(days=3),
    3: timedelta(days=7),
    4: timedelta(days=14),
    5: timedelta(days=30),
}

# Estimated minutes per revision item (for queue capping)
ESTIMATED_MINUTES_PER_ITEM = 2


def calculate_next_box(current_box: int, is_correct: bool) -> tuple[int, timedelta]:
    """Calculate the next Leitner box and due date interval.

    Rule:
    - Correct: Promote to min(5, current_box + 1)
    - Wrong: Demote to Box 1
    """
    if is_correct:
        next_box = min(5, max(1, current_box) + 1)
    else:
        next_box = 1

    interval = LEITNER_INTERVALS.get(next_box, timedelta(days=1))
    return next_box, interval


def calculate_due_date(from_dt: datetime, interval: timedelta) -> datetime:
    """Calculate the next due date by adding interval to the given datetime."""
    return from_dt + interval


class RevisionScheduler:
    """Service to schedule, query, and promote/demote Leitner revision items."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_due_items(
        self,
        student_id: uuid.UUID,
        target_date: date,
        now_dt: datetime,
        available_minutes: int = 15,
        blackout_subjects: set[str] | None = None,
        passed_exam_subjects: set[str] | None = None,
    ) -> list[RevisionItem]:
        """Fetch prioritized due revision items capped by available minutes.

        Requirement 4:
        - Exclude subjects that are in blackout on target_date.
        - Exclude subjects whose exam date has passed.
        - Cap the queue by available minutes.
        """
        if passed_exam_subjects is None:
            stmt_exams = select(StudySetup.subject).where(
                StudySetup.student_id == student_id,
                StudySetup.exam_date <= target_date,
            )
            res_exams = await self.db.execute(stmt_exams)
            passed_subjs = set(res_exams.scalars().all())
        else:
            passed_subjs = passed_exam_subjects

        blackout_subjs = blackout_subjects or set()
        excluded_subjects = blackout_subjs | passed_subjs

        # 1. Fetch due items up to now_dt
        stmt = (
            select(RevisionItem)
            .options(
                selectinload(RevisionItem.chapter).selectinload(Chapter.book),
                selectinload(RevisionItem.question),
            )
            .where(
                RevisionItem.student_id == student_id,
                RevisionItem.due_at <= now_dt,
            )
        )
        res = await self.db.execute(stmt)
        candidates = list(res.scalars().all())

        if not candidates:
            return []

        # 2. Filter out excluded subjects (blackout or past exam)
        valid_items: list[RevisionItem] = []
        for item in candidates:
            subj = item.chapter.book.subject if item.chapter and item.chapter.book else ""
            if subj in excluded_subjects:
                continue
            valid_items.append(item)

        if not valid_items:
            return []

        # 3. Load chapter mastery scores to order by weakness (overdue * (1.0 - mastery))
        chapter_ids = [it.chapter_id for it in valid_items]
        m_stmt = select(Mastery.chapter_id, Mastery.score).where(
            Mastery.student_id == student_id,
            Mastery.chapter_id.in_(chapter_ids),
        )
        m_res = await self.db.execute(m_stmt)
        mastery_map = dict(m_res.all())

        def get_priority(it: RevisionItem) -> float:
            score = mastery_map.get(it.chapter_id, 0.5)
            # Days overdue
            overdue_days = max(1.0, (now_dt - it.due_at).total_seconds() / 86400.0)
            return overdue_days * (1.0 - score)

        valid_items.sort(key=get_priority, reverse=True)

        # 4. Cap by available minutes (Requirement 4)
        max_items = max(1, available_minutes // ESTIMATED_MINUTES_PER_ITEM)
        return valid_items[:max_items]

    async def record_review(
        self,
        item_id: uuid.UUID,
        student_id: uuid.UUID,
        is_correct: bool,
        now_dt: datetime,
    ) -> RevisionItem | None:
        """Promote or demote a revision item based on review outcome."""
        stmt = select(RevisionItem).where(
            RevisionItem.id == item_id,
            RevisionItem.student_id == student_id,
        )
        res = await self.db.execute(stmt)
        item = res.scalar_one_or_none()
        if not item:
            return None

        next_box, interval = calculate_next_box(item.box, is_correct)
        item.box = next_box
        item.due_at = now_dt + interval
        item.last_result = "correct" if is_correct else "wrong"
        item.updated_at = now_dt

        await self.db.commit()
        await self.db.refresh(item)
        return item
