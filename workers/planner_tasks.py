"""Celery tasks for asynchronous plan regeneration and notifications."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.common.database import AsyncSessionLocal
from core.curriculum.models import Chapter
from core.families.models import StudentProfile
from core.planner.engine import (
    ChapterPlanInput,
    CompletedTaskRecord,
    SubjectSetupInput,
    generate_student_plan,
)
from core.planner.models import Plan, PlanDay, StudySetup, SyllabusItem, Task
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _async_regenerate_plan(
    student_id_str: str, setup_id_str: str, version: int
) -> dict[str, Any]:
    """Execute plan regeneration asynchronously inside an async session."""
    student_id = uuid.UUID(student_id_str)
    setup_id = uuid.UUID(setup_id_str)

    async with AsyncSessionLocal() as session:
        # 1. Idempotency check: if plan for this setup and version already exists and is active
        stmt_plan = select(Plan).where(Plan.setup_id == setup_id, Plan.version == version)
        res_plan = await session.execute(stmt_plan)
        existing_plan = res_plan.scalar_one_or_none()
        if existing_plan and existing_plan.status == "active":
            logger.info(
                "Plan for setup %s version %d already active; skipping idempotent run.",
                setup_id,
                version,
            )
            return {
                "status": "skipped",
                "reason": "already_active",
                "plan_id": str(existing_plan.id),
            }

        # 2. Load setup and student profile
        stmt_setup = (
            select(StudySetup)
            .options(
                selectinload(StudySetup.syllabus_items)
                .selectinload(SyllabusItem.chapter)
                .selectinload(Chapter.book)
            )
            .where(StudySetup.id == setup_id)
        )
        res_setup = await session.execute(stmt_setup)
        setup = res_setup.scalar_one_or_none()
        if not setup:
            return {"status": "error", "message": f"Setup {setup_id} not found"}

        stmt_prof = select(StudentProfile).where(StudentProfile.user_id == student_id)
        res_prof = await session.execute(stmt_prof)
        profile = res_prof.scalar_one_or_none()

        daily_mins = profile.daily_minutes if profile else 60
        avail_days = (
            profile.available_days if profile else ["sat", "sun", "mon", "tue", "wed", "thu"]
        )

        # 3. Load all setups for student to allocate shared budget
        stmt_all = (
            select(StudySetup)
            .options(
                selectinload(StudySetup.syllabus_items)
                .selectinload(SyllabusItem.chapter)
                .selectinload(Chapter.book)
            )
            .where(StudySetup.student_id == student_id)
        )
        res_all = await session.execute(stmt_all)
        all_setups = res_all.scalars().all()

        engine_setups: list[SubjectSetupInput] = []
        for s in all_setups:
            ch_inputs = [
                ChapterPlanInput(
                    id=item.chapter.id,
                    number=item.chapter.number,
                    title=item.chapter.title,
                    printed_page_start=item.chapter.printed_page_start,
                    printed_page_end=item.chapter.printed_page_end,
                    custom_order=item.custom_order,
                    book_id=item.chapter.book_id,
                    book_title=item.chapter.book.title if item.chapter.book else "",
                    weight=item.weight,
                    difficulty_factor=item.custom_difficulty
                    or item.chapter.difficulty_factor
                    or 1.0,
                    mastery=0.5,
                )
                for item in s.syllabus_items
                if item.included and item.chapter
            ]
            engine_setups.append(
                SubjectSetupInput(
                    subject=s.subject,
                    exam_name=s.exam_name,
                    exam_date=s.exam_date,
                    chapters=ch_inputs,
                    setup_id=s.id,
                )
            )

        # Load completed tasks
        stmt_done = (
            select(Task, PlanDay.date)
            .join(PlanDay, Task.plan_day_id == PlanDay.id)
            .where(Task.student_id == student_id, Task.status == "done")
        )
        res_done = await session.execute(stmt_done)
        completed = [
            CompletedTaskRecord(
                task_id=t.id,
                subject=t.subject,
                chapter_id=t.chapter_id,
                plan_date=p_date,
                type=t.type,
                est_minutes=t.est_minutes,
                refs=t.refs,
                completed_at=t.completed_at.isoformat() if t.completed_at else None,
            )
            for t, p_date in res_done.fetchall()
        ]

        from datetime import date

        today_date = date.today()

        plan_out = generate_student_plan(
            student_id=student_id,
            today=today_date,
            daily_study_minutes=daily_mins,
            setups=engine_setups,
            available_days=avail_days,
            completed_tasks=completed,
        )

        # Mark previous plans as superseded
        old_stmt = select(Plan).where(Plan.setup_id == setup.id, Plan.status == "active")
        res_old = await session.execute(old_stmt)
        for old_p in res_old.scalars().all():
            old_p.status = "superseded"

        new_plan = Plan(
            setup_id=setup.id,
            student_id=student_id,
            version=version,
            reason="async_regeneration",
            status="active",
            params={"warnings": plan_out.warnings},
        )
        session.add(new_plan)
        await session.flush()

        for g_day in plan_out.days:
            sub_tasks = [t for t in g_day.tasks if t.subject == setup.subject]
            if not sub_tasks:
                continue
            p_day = PlanDay(
                plan_id=new_plan.id,
                date=g_day.date,
                planned_minutes=sum(t.est_minutes for t in sub_tasks),
                day_type=g_day.day_type,
            )
            session.add(p_day)
            await session.flush()

            for g_task in sub_tasks:
                t_row = Task(
                    id=g_task.id,
                    plan_day_id=p_day.id,
                    student_id=student_id,
                    type=g_task.type,
                    chapter_id=uuid.UUID(str(g_task.chapter_id)) if g_task.chapter_id else None,
                    refs=g_task.refs,
                    est_minutes=g_task.est_minutes,
                    status=g_task.status,
                    source=g_task.source,
                )
                session.add(t_row)

        await session.commit()
        return {
            "status": "regenerated",
            "plan_id": str(new_plan.id),
            "total_days": len(plan_out.days),
        }


@celery_app.task(name="regenerate_student_plan", bind=True, max_retries=3)
def regenerate_student_plan_task(
    self: Any, student_id_str: str, setup_id_str: str, version: int
) -> dict[str, Any]:
    """Background task to regenerate a student's study plan idempotently."""
    try:
        return asyncio.run(_async_regenerate_plan(student_id_str, setup_id_str, version))
    except Exception as exc:
        logger.exception("Error in regenerate_student_plan task: %s", exc)
        raise self.retry(exc=exc, countdown=5) from exc
