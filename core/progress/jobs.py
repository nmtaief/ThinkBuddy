"""Adaptive daily composition and 3-day review cycle jobs.

Per Requirements 1, 3, 5:
(1) The daily and 3-day jobs must NOT write tasks directly.
    Feed mastery and weak-point data into the existing P03 planner and regenerate
    future days through the existing student-level lock and plan version, restoring the weak-point share.
(3) Run jobs per student at a fixed local time, batched and throttled.
(5) Build review quizzes from the question bank through the P04 builder;
    if there are too few questions, skip and warn (REVIEW_QUIZ_INSUFFICIENT_QUESTIONS).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.families.models import StudentProfile
from core.planner.models import StudySetup, SyllabusItem
from core.planner.router import (
    execute_student_plan_regeneration,
)
from core.progress.models import Mastery, ProgressDaily
from core.progress.service import ProgressService
from core.quiz.builder import QuizBuilderService
from core.quiz.models import LearningSignal

logger = logging.getLogger("thinkbuddy.progress.jobs")


async def run_daily_composition_job(
    db: AsyncSession,
    student_id: uuid.UUID,
    as_of_date: date | None = None,
) -> int:
    """Execute daily composition job for a student.

    Rules:
    1. Does NOT write tasks directly: triggers P03 planner under student advisory lock.
    2. Regenerates future days with reason='adaptive', bumping plan version.
    3. Idempotent: safe to run repeatedly.
    """
    logger.info("Starting daily composition job for student %s", student_id)

    progress_service = ProgressService(db)

    # 1. Recompute student mastery from any pending signals
    await progress_service.recompute_student_mastery(student_id)

    # 2. Trigger P03 planner regeneration for future days under student lock (Requirement 1)
    plan_out, new_version = await execute_student_plan_regeneration(
        db=db,
        student_id=student_id,
        reason="adaptive",
        future_only=True,
    )

    # 3. Upsert ProgressDaily record for today
    target_date = as_of_date or datetime.now(UTC).date()
    upsert_stmt = (
        pg_insert(ProgressDaily)
        .values(
            id=uuid.uuid4(),
            student_id=student_id,
            date=target_date,
            minutes=0,
            tasks_done=0,
            tasks_total=0,
            streak=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing(index_elements=["student_id", "date"])
    )
    await db.execute(upsert_stmt)
    await db.commit()

    logger.info(
        "Daily composition complete for student %s: plan_version=%d",
        student_id,
        new_version,
    )
    return new_version


async def run_three_day_review_cycle(
    db: AsyncSession,
    student_id: uuid.UUID,
    as_of_date: date | None = None,
) -> tuple[int, uuid.UUID | None]:
    """Execute 3-day review cycle for a student.

    Per Requirement 5:
    - Builds an assessed review quiz targeting recent chapters and weak points.
    - If there are too few questions in the bank, skips quiz creation and logs warning.
    - Triggers P03 planner regeneration under student lock.
    """
    logger.info("Starting 3-day review cycle for student %s", student_id)

    now_dt = datetime.now(UTC)
    three_days_ago = now_dt - timedelta(days=3)

    progress_service = ProgressService(db)

    # 1. Recompute mastery from all historical signals
    await progress_service.recompute_student_mastery(student_id)

    # 2. Identify target chapters for review (recent signals + lowest mastery)
    stmt_sig = (
        select(LearningSignal.chapter_id)
        .where(
            LearningSignal.student_id == student_id,
            LearningSignal.at >= three_days_ago,
        )
        .distinct()
    )
    res_sig = await db.execute(stmt_sig)
    recent_ch_ids = [ch_id for ch_id in res_sig.scalars().all() if ch_id]

    stmt_m = (
        select(Mastery.chapter_id)
        .where(
            Mastery.student_id == student_id,
            Mastery.score < 0.60,
        )
        .order_by(Mastery.score.asc())
        .limit(3)
    )
    res_m = await db.execute(stmt_m)
    weak_ch_ids = list(res_m.scalars().all())

    target_chapters = list(dict.fromkeys(recent_ch_ids + weak_ch_ids))
    if not target_chapters:
        # Fallback to active syllabus chapters from current setups
        stmt_active_ch = (
            select(SyllabusItem.chapter_id)
            .join(StudySetup, SyllabusItem.setup_id == StudySetup.id)
            .where(
                StudySetup.student_id == student_id,
                SyllabusItem.included.is_(True),
            )
            .limit(5)
        )
        res_active_ch = await db.execute(stmt_active_ch)
        target_chapters = list(res_active_ch.scalars().all())

    # 3. Build Review Quiz via P04 QuizBuilder (Requirement 5)
    review_quiz_id: uuid.UUID | None = None
    min_required_questions = 3

    if target_chapters:
        quiz_builder = QuizBuilderService(db)
        available_questions = await quiz_builder.select_and_randomize_questions(
            question_count=min_required_questions,
            student_id=student_id,
            mode="assessed",
            chapter_ids=target_chapters,
        )

        if len(available_questions) < min_required_questions:
            # Requirement 5: Skip quiz creation and warn when pool insufficient
            logger.warning(
                "REVIEW_QUIZ_INSUFFICIENT_QUESTIONS: Skipping review quiz for student %s; "
                "found %d questions, required %d in chapters %s",
                student_id,
                len(available_questions),
                min_required_questions,
                target_chapters,
            )
        else:
            # Create review quiz
            quiz = await quiz_builder.build_quiz(
                student_id=student_id,
                chapter_ids=target_chapters,
                title="৩ দিনের পর্যালোচনা কুইজ (3-Day Review Quiz)",
                kind="review",
                mode="assessed",
                question_count=len(available_questions),
                time_limit_s=600,
            )
            review_quiz_id = quiz.id
            logger.info(
                "Created 3-day review quiz %s for student %s with %d questions",
                quiz.id,
                student_id,
                len(available_questions),
            )

    # 4. Trigger P03 planner regeneration under student lock (Requirement 1)
    plan_out, new_version = await execute_student_plan_regeneration(
        db=db,
        student_id=student_id,
        reason="adaptive",
        future_only=True,
    )

    logger.info(
        "3-Day review cycle complete for student %s: plan_version=%d, quiz_id=%s",
        student_id,
        new_version,
        review_quiz_id,
    )
    return new_version, review_quiz_id


async def run_batched_daily_jobs(
    db: AsyncSession,
    batch_size: int = 20,
    throttle_delay_s: float = 0.05,
    student_ids: list[uuid.UUID] | None = None,
    throttle_delay_sec: float | None = None,
) -> dict[str, int]:
    """Run daily composition jobs batched and throttled across active students (Requirement 3)."""
    delay = throttle_delay_sec if throttle_delay_sec is not None else throttle_delay_s
    if student_ids is not None:
        target_ids = student_ids
    else:
        stmt = select(StudentProfile.user_id)
        res = await db.execute(stmt)
        target_ids = list(res.scalars().all())

    processed_count = 0
    errors_count = 0
    for i in range(0, len(target_ids), batch_size):
        batch = target_ids[i : i + batch_size]
        for s_id in batch:
            try:
                await run_daily_composition_job(db, s_id)
                processed_count += 1
            except Exception as ex:
                logger.error("Failed daily composition for student %s: %s", s_id, ex)
                errors_count += 1

            if delay > 0:
                await asyncio.sleep(delay)

    return {
        "total": processed_count,
        "processed": processed_count,
        "success": processed_count,
        "failed": errors_count,
        "errors": errors_count,
    }
