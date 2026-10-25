"""Streak calculation engine with weekend, blackout, and exam day continuity.

Requirement 2:
Streaks must not break on blackout, exam, rest, or weekly off days.
Only active school days require task completion to maintain the streak.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.planner.models import Plan, PlanDay, Task
from core.planner.settings_resolver import (
    ResolvedPlannerSettings,
    get_published_holidays,
    resolve_calendar_days,
)
from core.progress.models import ProgressDaily


async def calculate_streak(
    db: AsyncSession,
    student_id: uuid.UUID,
    as_of_date: date,
    resolved_settings: ResolvedPlannerSettings,
    exam_dates: set[date] | None = None,
) -> int:
    """Calculate unbroken consecutive study days for a student.

    Rules (Requirement 2):
    1. Days classified as 'blackout', 'holiday' (Friday/Saturday/national holidays),
       or 'exam_day' are exempt from study requirements.
    2. Missing study on an exempt day NEVER breaks an existing streak.
    3. Studying on a school day increments the streak.
    4. Missing study on a completed school day terminates the streak.
    """
    exam_set = exam_dates or set()

    # Lookback window for streak up to 180 days
    start_lookback = as_of_date - timedelta(days=180)

    # 1. Load progress daily records in lookback window
    stmt = select(ProgressDaily).where(
        ProgressDaily.student_id == student_id,
        ProgressDaily.date >= start_lookback,
        ProgressDaily.date <= as_of_date,
    )
    res = await db.execute(stmt)
    records = {r.date: r for r in res.scalars().all()}

    # 2. Load published holidays in lookback window
    published_holidays = await get_published_holidays(db, start_lookback, as_of_date)
    now_dt = datetime.combine(as_of_date, datetime.min.time())
    cal_days = resolve_calendar_days(
        start_date=start_lookback,
        end_date=as_of_date,
        now=now_dt,
        resolved_settings=resolved_settings,
        published_holidays=published_holidays,
        exam_dates=exam_set,
    )
    cal_map = {d.date: d.day_type for d in cal_days}

    # 3. Load active plan and planned task counts per day (Requirement 5)
    active_plan_stmt = (
        select(Plan.id)
        .where(Plan.student_id == student_id)
        .order_by(Plan.version.desc())
        .limit(1)
    )
    active_plan_id = (await db.execute(active_plan_stmt)).scalar_one_or_none()

    has_plan = active_plan_id is not None
    planned_task_counts: dict[date, int] = {}
    if has_plan:
        stmt_tasks = (
            select(PlanDay.date, func.count(Task.id))
            .join(PlanDay, Task.plan_day_id == PlanDay.id)
            .where(
                PlanDay.plan_id == active_plan_id,
                PlanDay.date >= start_lookback,
                PlanDay.date <= as_of_date,
            )
            .group_by(PlanDay.date)
        )
        res_tasks = await db.execute(stmt_tasks)
        planned_task_counts = dict(res_tasks.all())

    streak = 0
    current_check_date = as_of_date
    grace_days_used: set[tuple[int, int]] = set()

    while current_check_date >= start_lookback:
        day_type = cal_map.get(current_check_date, "school_day")

        prog = records.get(current_check_date)
        has_studied = prog is not None and (prog.tasks_done > 0 or prog.minutes > 0)

        if has_studied:
            streak += 1
        else:
            # Check if this day is exempt (Requirement 2 & Requirement 5)
            is_exempt = day_type in ("blackout", "holiday", "exam_day")

            # Days with no planned tasks must not break a streak (Requirement 5)
            if has_plan:
                has_no_planned_tasks = planned_task_counts.get(current_check_date, 0) == 0
            else:
                has_no_planned_tasks = prog is not None and prog.tasks_total == 0

            if is_exempt or has_no_planned_tasks:
                # Streak is preserved across exempt and 0-task days without breaking
                pass
            else:
                # Non-exempt school day:
                # If checking as_of_date itself (today currently in progress), do not break yet
                if current_check_date == as_of_date:
                    pass
                else:
                    # Check weekly grace day (Requirement 5: 1 grace day per weekly calendar window)
                    week_key = current_check_date.isocalendar()[:2]
                    if week_key not in grace_days_used:
                        grace_days_used.add(week_key)
                        # Grace day consumed for this week; streak is preserved
                        pass
                    else:
                        # Grace day already used in this week; streak terminates
                        break

        current_check_date -= timedelta(days=1)

    return streak
