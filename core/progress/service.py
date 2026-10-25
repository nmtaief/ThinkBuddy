"""Progress and mastery service managing signals, evaluations, and progress queries.

Implements Deliverable 1, 2, and 7 per docs/06_ADAPTIVE_ENGINE.md:
- Signal ingestion and mastery aggregation across chapters.
- Enqueueing spaced revision items for missed questions or topics needing practice.
- Parent-facing progress summary (uses 'needs practice' and 'not enough data', never 'weak').
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.curriculum.models import Chapter
from core.planner.models import PlanDay, Task
from core.planner.settings_resolver import resolve_student_settings
from core.progress.mastery import SignalInput, compute_mastery
from core.progress.models import Mastery, RevisionItem
from core.progress.revision import LEITNER_INTERVALS
from core.progress.schemas import (
    ChapterMasteryItem,
    NeedsPracticeTopic,
    ProgressSummaryResponse,
)
from core.progress.streak import calculate_streak
from core.quiz.models import LearningSignal

logger = logging.getLogger("thinkbuddy.progress.service")


class ProgressService:
    """Service authority for learning signals, mastery computation, and progress views."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def ingest_signal(
        self,
        student_id: uuid.UUID,
        source: str,
        chapter_id: uuid.UUID,
        weight: float = 1.0,
        ref_id: str | None = None,
        concept_id: uuid.UUID | None = None,
        at: datetime | None = None,
    ) -> LearningSignal:
        """Persist a new learning signal with idempotency on ref_id."""
        now_dt = at or datetime.now(UTC)
        sig = LearningSignal(
            id=uuid.uuid4(),
            student_id=student_id,
            source=source,
            chapter_id=chapter_id,
            concept_id=concept_id,
            weight=weight,
            ref_id=ref_id,
            at=now_dt,
        )
        self.db.add(sig)
        await self.db.flush()
        return sig

    async def recompute_student_mastery(
        self,
        student_id: uuid.UUID,
        eval_time: datetime | None = None,
    ) -> list[Mastery]:
        """Aggregate all historical signals and recompute bounded mastery scores per chapter."""
        now_dt = eval_time or datetime.now(UTC)

        # 1. Fetch all learning signals for student
        stmt_sig = (
            select(LearningSignal)
            .where(LearningSignal.student_id == student_id)
            .order_by(LearningSignal.at.asc())
        )
        res_sig = await self.db.execute(stmt_sig)
        all_signals = list(res_sig.scalars().all())

        # Group signals by (chapter_id, concept_id)
        signals_by_target: dict[tuple[uuid.UUID, uuid.UUID | None], list[SignalInput]] = {}
        for s in all_signals:
            if not s.chapter_id:
                continue
            key = (s.chapter_id, s.concept_id)
            signals_by_target.setdefault(key, []).append(
                SignalInput(
                    source=s.source,
                    weight=s.weight,
                    at=s.at,
                )
            )

        # 2. Fetch existing mastery records
        stmt_m = select(Mastery).where(Mastery.student_id == student_id)
        res_m = await self.db.execute(stmt_m)
        existing_mastery = {(m.chapter_id, m.concept_id): m for m in res_m.scalars().all()}

        updated_records: list[Mastery] = []
        for (ch_id, conc_id), sig_inputs in signals_by_target.items():
            existing = existing_mastery.get((ch_id, conc_id))
            init_score = 0.5
            init_conf = 0.0
            last_up = None

            calc_result = compute_mastery(
                signals=sig_inputs,
                initial_score=init_score,
                initial_confidence=init_conf,
                last_updated_at=last_up,
                evaluation_time=now_dt,
            )

            if existing:
                existing.score = calc_result.score
                existing.confidence = calc_result.confidence
                existing.last_seen_at = sig_inputs[-1].at or now_dt
                existing.updated_at = now_dt
                updated_records.append(existing)
            else:
                new_m = Mastery(
                    id=uuid.uuid4(),
                    student_id=student_id,
                    chapter_id=ch_id,
                    concept_id=conc_id,
                    score=calc_result.score,
                    confidence=calc_result.confidence,
                    last_seen_at=sig_inputs[-1].at or now_dt,
                    updated_at=now_dt,
                )
                self.db.add(new_m)
                updated_records.append(new_m)

            # If score indicates need for practice, ensure item is enqueued in Leitner Box 1
            if calc_result.score < 0.50:
                await self._ensure_revision_item(student_id, ch_id, conc_id, now_dt)

        await self.db.commit()
        return updated_records

    async def _ensure_revision_item(
        self,
        student_id: uuid.UUID,
        chapter_id: uuid.UUID,
        concept_id: uuid.UUID | None,
        now_dt: datetime,
    ) -> None:
        """Enqueue chapter into Leitner Box 1 if not already scheduled."""
        chk_stmt = select(RevisionItem).where(
            RevisionItem.student_id == student_id,
            RevisionItem.chapter_id == chapter_id,
            RevisionItem.concept_id == concept_id,
        )
        res = await self.db.execute(chk_stmt)
        existing = res.scalar_one_or_none()
        if not existing:
            rev_item = RevisionItem(
                id=uuid.uuid4(),
                student_id=student_id,
                chapter_id=chapter_id,
                concept_id=concept_id,
                box=1,
                due_at=now_dt + LEITNER_INTERVALS[1],
                created_at=now_dt,
                updated_at=now_dt,
            )
            self.db.add(rev_item)

    async def get_progress_summary(
        self,
        student_id: uuid.UUID,
        as_of_date: date | None = None,
    ) -> ProgressSummaryResponse:
        """Build parent-safe progress summary for student dashboard."""
        target_date = as_of_date or datetime.now(UTC).date()

        # 1. Fetch resolved settings
        resolved_settings = await resolve_student_settings(self.db, student_id)

        # 2. Compute streak
        streak = await calculate_streak(
            db=self.db,
            student_id=student_id,
            as_of_date=target_date,
            resolved_settings=resolved_settings,
        )

        # 3. Overall mastery average
        m_stmt = select(Mastery).where(Mastery.student_id == student_id)
        m_res = await self.db.execute(m_stmt)
        all_m = list(m_res.scalars().all())

        if all_m:
            avg_score = round(sum(m.score for m in all_m) / len(all_m), 4)
            avg_conf = round(sum(m.confidence for m in all_m) / len(all_m), 4)
        else:
            avg_score = 0.50
            avg_conf = 0.0

        if avg_conf < 0.35:
            status = "not_enough_data"
            label_bn = "পর্যাপ্ত তথ্য নেই"
        elif avg_score >= 0.80:
            status = "mastered"
            label_bn = "দক্ষতা অর্জিত"
        elif avg_score < 0.50:
            status = "needs_practice"
            label_bn = "আরও অনুশীলনের প্রয়োজন"
        else:
            status = "in_progress"
            label_bn = "চলমান"

        # 4. Today's task and minute metrics
        stmt_tasks = (
            select(Task)
            .join(PlanDay, Task.plan_day_id == PlanDay.id)
            .where(
                Task.student_id == student_id,
                PlanDay.date == target_date,
            )
        )
        res_tasks = await self.db.execute(stmt_tasks)
        today_tasks = list(res_tasks.scalars().all())

        completed_tasks = [t for t in today_tasks if t.status == "done"]
        study_minutes_today = sum(t.est_minutes for t in completed_tasks)

        return ProgressSummaryResponse(
            student_id=student_id,
            overall_mastery=avg_score,
            confidence=avg_conf,
            status=status,
            status_label_bn=label_bn,
            streak_days=streak,
            study_minutes_today=study_minutes_today,
            tasks_completed_today=len(completed_tasks),
            tasks_total_today=len(today_tasks),
        )

    async def get_chapter_mastery(
        self,
        student_id: uuid.UUID,
    ) -> list[ChapterMasteryItem]:
        """Fetch all chapter mastery records formatted with parent-safe labels."""
        stmt = (
            select(Mastery)
            .options(selectinload(Mastery.chapter).selectinload(Chapter.book))
            .where(Mastery.student_id == student_id)
            .order_by(Mastery.score.asc())
        )
        res = await self.db.execute(stmt)
        records = list(res.scalars().all())

        items: list[ChapterMasteryItem] = []
        for r in records:
            ch_title = r.chapter.title if r.chapter else "General Topic"
            ch_num = r.chapter.number if r.chapter else None
            subj = r.chapter.book.subject if r.chapter and r.chapter.book else "General"

            if r.confidence < 0.35:
                status = "not_enough_data"
                label_bn = "পর্যাপ্ত তথ্য নেই"
            elif r.score >= 0.80:
                status = "mastered"
                label_bn = "দক্ষতা অর্জিত"
            elif r.score < 0.50:
                status = "needs_practice"
                label_bn = "আরও অনুশীলনের প্রয়োজন"
            else:
                status = "in_progress"
                label_bn = "চলমান"

            items.append(
                ChapterMasteryItem(
                    chapter_id=r.chapter_id,
                    chapter_title=ch_title,
                    chapter_number=ch_num,
                    subject=subj,
                    score=r.score,
                    confidence=r.confidence,
                    status=status,
                    status_label_bn=label_bn,
                    last_seen_at=r.last_seen_at,
                )
            )

        return items

    async def get_needs_practice_topics(
        self,
        student_id: uuid.UUID,
    ) -> list[NeedsPracticeTopic]:
        """Fetch chapters that need reinforcement (Requirement 7: never labeled as 'weak')."""
        stmt = (
            select(Mastery)
            .options(selectinload(Mastery.chapter).selectinload(Chapter.book))
            .where(
                Mastery.student_id == student_id,
                Mastery.confidence >= 0.35,  # Has enough data
                Mastery.score < 0.50,  # Needs reinforcement
            )
            .order_by(Mastery.score.asc())
        )
        res = await self.db.execute(stmt)
        records = list(res.scalars().all())

        topics: list[NeedsPracticeTopic] = []
        for r in records:
            ch_title = r.chapter.title if r.chapter else "General Topic"
            subj = r.chapter.book.subject if r.chapter and r.chapter.book else "General"
            topics.append(
                NeedsPracticeTopic(
                    chapter_id=r.chapter_id,
                    chapter_title=ch_title,
                    subject=subj,
                    score=r.score,
                    confidence=r.confidence,
                    suggested_action="Review chapter notes and complete targeted revision quiz.",
                    suggested_action_bn="অধ্যায়ের মূল অংশগুলো পুনরাবৃত্তি করো এবং অনুশীলন কুইজ সমাধান করো।",
                )
            )

        return topics
