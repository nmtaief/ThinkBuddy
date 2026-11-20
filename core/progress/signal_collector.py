"""Unified Learning Signal Collector and Mastery Update Pipeline.

Implements Phase 4 Pipeline Rules per PLAN_WEBSITE_LAUNCH.md:
1. Signal Collection Rules:
   - quiz_correct: +0.15 (strong positive)
   - quiz_wrong: -0.20 (strong negative, auto-enqueues Leitner revision)
   - practice_correct: +0.05 (light positive)
   - practice_wrong: -0.08 (light negative, auto-enqueues Leitner revision)
   - quiz_slow: -0.03 (fragile knowledge indicator)
   - ai_question: -0.02 (mild negative - student needed tutor help)
   - ai_repeat: -0.08 (medium negative - persistent gap on same topic)
   - task_skipped: -0.03 (small negative per skipped study task)
   - task_done: +0.03 (small positive on task completion)
   - study_done: +0.02 (consistency reward for study session)

2. Recency Decay & Mastery Updates:
   - Evaluates recent signals with exponential decay: exp(-0.05 * days)
   - Updates student mastery and confidence scores in DB
   - Synchronizes Leitner spaced repetition boxes
"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.progress.models import Mastery, RevisionItem
from core.progress.revision import LEITNER_INTERVALS
from core.progress.weights import DEFAULT_MASTERY_CONFIG
from core.quiz.models import LearningSignal

logger = logging.getLogger("thinkbuddy.progress.signal_collector")

# Signal weight definitions per Phase 4 specification
SIGNAL_WEIGHTS = {
    "quiz_correct": 0.15,
    "quiz_wrong": -0.20,
    "practice_correct": 0.05,
    "practice_wrong": -0.08,
    "quiz_slow": -0.03,
    "ai_question": -0.02,
    "ai_repeat": -0.08,
    "task_skipped": -0.03,
    "task_done": 0.03,
    "study_done": 0.02,
}


class SignalCollector:
    """Collects real-time student activity signals and triggers continuous mastery updates."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def ingest_signal(
        self,
        student_id: uuid.UUID,
        source: str,
        chapter_id: uuid.UUID | None = None,
        concept_id: str | None = None,
        ref_id: str | None = None,
        weight_override: float | None = None,
        auto_update_mastery: bool = True,
    ) -> LearningSignal:
        """Store a learning signal and update mastery."""
        weight = weight_override if weight_override is not None else SIGNAL_WEIGHTS.get(source, 0.0)
        now_dt = datetime.now(UTC)

        signal = LearningSignal(
            id=uuid.uuid4(),
            student_id=student_id,
            source=source,
            chapter_id=chapter_id,
            concept_id=concept_id,
            weight=weight,
            ref_id=ref_id,
            at=now_dt,
        )
        self.db.add(signal)
        await self.db.flush()

        if auto_update_mastery and chapter_id:
            await self.update_chapter_mastery(student_id, chapter_id)

        return signal

    async def record_quiz_outcome(
        self,
        student_id: uuid.UUID,
        chapter_id: uuid.UUID,
        question_id: uuid.UUID | None,
        is_correct: bool,
        is_assessed: bool = False,
        time_spent_sec: float | None = None,
        median_time_sec: float | None = None,
    ) -> list[LearningSignal]:
        """Record outcomes from quiz item submission and handle Leitner enqueueing."""
        signals: list[LearningSignal] = []

        if is_correct:
            src = "quiz_correct" if is_assessed else "practice_correct"
            sig = await self.ingest_signal(
                student_id=student_id,
                source=src,
                chapter_id=chapter_id,
                ref_id=str(question_id) if question_id else None,
                auto_update_mastery=False,
            )
            signals.append(sig)

            # Check if slow (spent > 2x median)
            if time_spent_sec and median_time_sec and time_spent_sec > (2.0 * median_time_sec):
                slow_sig = await self.ingest_signal(
                    student_id=student_id,
                    source="quiz_slow",
                    chapter_id=chapter_id,
                    ref_id=str(question_id) if question_id else None,
                    auto_update_mastery=False,
                )
                signals.append(slow_sig)
        else:
            src = "quiz_wrong" if is_assessed else "practice_wrong"
            sig = await self.ingest_signal(
                student_id=student_id,
                source=src,
                chapter_id=chapter_id,
                ref_id=str(question_id) if question_id else None,
                auto_update_mastery=False,
            )
            signals.append(sig)

            # Auto-enqueue or reset Leitner revision item to Box 1
            if question_id:
                await self._enqueue_revision_item(student_id, chapter_id, question_id)

        # Update mastery after batch
        await self.update_chapter_mastery(student_id, chapter_id)
        await self.db.commit()
        return signals

    async def record_ai_interaction(
        self,
        student_id: uuid.UUID,
        chapter_id: uuid.UUID,
        concept_id: str | None = None,
        is_repeat: bool = False,
    ) -> LearningSignal:
        """Record a student asking questions to the AI tutor about a chapter or concept."""
        source = "ai_repeat" if is_repeat else "ai_question"
        sig = await self.ingest_signal(
            student_id=student_id,
            source=source,
            chapter_id=chapter_id,
            concept_id=concept_id,
            auto_update_mastery=True,
        )
        await self.db.commit()
        return sig

    async def record_task_outcome(
        self,
        student_id: uuid.UUID,
        chapter_id: uuid.UUID,
        task_id: uuid.UUID,
        is_completed: bool,
    ) -> LearningSignal:
        """Record study planner task completion or skip."""
        source = "task_done" if is_completed else "task_skipped"
        sig = await self.ingest_signal(
            student_id=student_id,
            source=source,
            chapter_id=chapter_id,
            ref_id=str(task_id),
            auto_update_mastery=True,
        )
        await self.db.commit()
        return sig

    async def update_chapter_mastery(
        self,
        student_id: uuid.UUID,
        chapter_id: uuid.UUID,
    ) -> Mastery:
        """Recompute student mastery for a chapter incorporating all weighted signals and exponential decay."""
        now_dt = datetime.now(UTC)

        # 1. Fetch all signals for this student and chapter
        stmt = (
            select(LearningSignal)
            .where(
                LearningSignal.student_id == student_id,
                LearningSignal.chapter_id == chapter_id,
            )
            .order_by(LearningSignal.at.asc())
        )
        res = await self.db.execute(stmt)
        signals = list(res.scalars().all())

        # 2. Compute decayed score
        base_score = 0.5
        total_impact = 0.0
        confidence = min(1.0, len(signals) / 10.0)

        for s in signals:
            age_days = max(0.0, (now_dt - (s.at or now_dt)).total_seconds() / 86400.0)
            recency_factor = math.exp(-0.05 * age_days)
            total_impact += s.weight * recency_factor

        final_score = round(max(0.0, min(1.0, base_score + total_impact)), 4)

        # 3. Upsert Mastery record
        m_stmt = select(Mastery).where(
            Mastery.student_id == student_id,
            Mastery.chapter_id == chapter_id,
            Mastery.concept_id.is_(None),
        )
        m_res = await self.db.execute(m_stmt)
        mastery = m_res.scalar_one_or_none()

        if mastery:
            mastery.score = final_score
            mastery.confidence = confidence
            mastery.last_seen_at = now_dt
            mastery.updated_at = now_dt
        else:
            mastery = Mastery(
                id=uuid.uuid4(),
                student_id=student_id,
                chapter_id=chapter_id,
                concept_id=None,
                score=final_score,
                confidence=confidence,
                last_seen_at=now_dt,
                updated_at=now_dt,
            )
            self.db.add(mastery)

        await self.db.flush()
        return mastery

    async def _enqueue_revision_item(
        self,
        student_id: uuid.UUID,
        chapter_id: uuid.UUID,
        question_id: uuid.UUID,
    ) -> RevisionItem:
        """Put a question into Leitner Box 1 for spaced revision."""
        now_dt = datetime.now(UTC)
        stmt = select(RevisionItem).where(
            RevisionItem.student_id == student_id,
            RevisionItem.question_id == question_id,
        )
        res = await self.db.execute(stmt)
        item = res.scalar_one_or_none()

        due_date = now_dt + timedelta(days=LEITNER_INTERVALS.get(1, 1))

        if item:
            item.box = 1  # Reset to Box 1 on error
            item.next_review_at = due_date
            item.last_reviewed_at = now_dt
        else:
            item = RevisionItem(
                id=uuid.uuid4(),
                student_id=student_id,
                chapter_id=chapter_id,
                question_id=question_id,
                box=1,
                next_review_at=due_date,
                last_reviewed_at=now_dt,
            )
            self.db.add(item)

        await self.db.flush()
        return item
