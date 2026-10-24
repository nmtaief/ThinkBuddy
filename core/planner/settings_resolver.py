"""Dynamic settings resolver for ThinkBuddy planner v2.

Implements the 3-tier configuration hierarchy:
Tier 1: System defaults (hardcoded baseline)
Tier 2: Admin policy by class band and group (from database)
Tier 3: Parent settings per student, clamped to admin hard limits

Computes day types (school day, holiday, blackout, exam day) and today's remaining time budget.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.families.models import StudentProfile
from core.planner.models import AdminPolicy, Holiday, StudentStudySettings

DEFAULT_PLANNER_PARAMETERS: dict[str, Any] = {
    "study_share": 0.65,
    "revision_share": 0.25,
    "homework_quiz_share": 0.10,
    "revision_intervals": [1, 3, 7],
    "final_revision_window_pct": 0.15,
    "final_revision_min_days": 3,
    "weekly_buffer_interval": 7,
    "min_subject_daily_share": 0.10,
    "rolling_horizon_days": 60,
    "max_consecutive_days_per_subject": 2,
    "priority_weight_mapping": {"normal": 1.0, "main": 1.3, "difficult": 1.6},
    "appearance_frequency_targets": {
        "difficult": 0.67,
        "main": 0.50,
        "normal": 0.38,
    },
    "exam_approaching_window_days": 3,
    "exam_approaching_load_ratio": 0.50,
    "final_window_fill_target": 0.80,
    "mock_quiz_max_frequency_days": 2,
    "min_study_block_minutes": 20,
}

CLASS_BAND_RECOMMENDED_MINUTES: dict[str, int] = {
    "6-8": 90,
    "9-10": 150,
    "11-12": 210,
}


def get_class_band(class_level: int) -> str:
    """Map class level (6-12) to administrative class band."""
    if 6 <= class_level <= 8:
        return "6-8"
    if 9 <= class_level <= 10:
        return "9-10"
    if 11 <= class_level <= 12:
        return "11-12"
    return "6-8"


@dataclass(frozen=True)
class ResolvedPlannerSettings:
    """Final resolved settings consumed by the planner engine."""

    class_band: str
    group: str
    school_day_minutes: int
    holiday_minutes: int
    study_window_start: str
    study_window_end: str
    weekly_off_days: list[str]
    recurring_unavailable_blocks: list[dict[str, Any]]
    blocked_observance_keys: list[str]
    custom_blackout_dates: list[dict[str, Any]]
    subject_priorities: dict[str, str]
    rest_weekday: str | None = None
    planner_parameters: dict[str, Any] = field(default_factory=dict)
    adaptive_mode: str = "suggest"
    ai_adjustments: dict[str, Any] = field(default_factory=dict)
    parent_locked_fields: list[str] = field(default_factory=list)
    clamping_notices: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommended_daily_minutes: int = 90
    admin_hard_limits: dict[str, Any] = field(default_factory=dict)
    settings_version: int = 1


@dataclass(frozen=True)
class DayScheduleInfo:
    """Daily schedule metadata for a specific calendar date."""

    date: date
    day_type: Literal["school_day", "holiday", "buffer", "blackout", "exam_day"]
    budget_minutes: int
    reason: str | None = None
    zero_reason: str | None = None
    subject_exams: list[str] = field(default_factory=list)


def parse_time_str(time_str: str) -> time:
    """Parse HH:MM string to datetime.time."""
    parts = [int(p) for p in time_str.split(":")]
    return time(hour=parts[0], minute=parts[1])


def resolve_calendar_days(
    start_date: date,
    end_date: date,
    now: datetime,
    resolved_settings: ResolvedPlannerSettings,
    published_holidays: list[Holiday],
    exam_dates: set[date] | dict[date, list[str]],
    completed_minutes_today: int = 0,
    warnings: list[str] | None = None,
) -> list[DayScheduleInfo]:
    """Pure calendar resolver: computes day types and daily study budgets.

    Zero DB calls. Consumes resolved settings, holiday models, and current time.
    Separates blackout days from buffer days and emits warnings if exam dates fall on
    weekly off days or blackout dates.
    """
    days: list[DayScheduleInfo] = []
    weekday_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    today_date = now.date()

    # Pre-index holidays by date
    holiday_map: dict[date, list[Holiday]] = {}
    for h in published_holidays:
        curr = h.start_date
        while curr <= h.end_date:
            holiday_map.setdefault(curr, []).append(h)
            curr = date.fromordinal(curr.toordinal() + 1)

    # Convert exam_dates to lookup map: date -> list of subject names
    exam_lookup: dict[date, list[str]] = {}
    if isinstance(exam_dates, dict):
        exam_lookup = exam_dates
    elif isinstance(exam_dates, set):
        exam_lookup = {ed: [] for ed in exam_dates}

    curr_date = start_date
    while curr_date <= end_date:
        w_name = weekday_names[curr_date.weekday()]
        h_list = holiday_map.get(curr_date, [])

        # 1. Check for Blackout:
        # A. Custom parent blackout date
        is_custom_blackout = False
        blackout_reason = None
        for cb in resolved_settings.custom_blackout_dates:
            cb_start = cb.get("start_date")
            cb_end = cb.get("end_date")
            if isinstance(cb_start, str):
                cb_start = date.fromisoformat(cb_start)
            if isinstance(cb_end, str):
                cb_end = date.fromisoformat(cb_end)
            if cb_start and cb_end and cb_start <= curr_date <= cb_end:
                is_custom_blackout = True
                blackout_reason = f"custom_blackout:{cb.get('reason', 'other')}"
                break

        # B. Published holiday with study_blackout=True
        holiday_blackout = any(h.study_blackout for h in h_list)
        if holiday_blackout:
            blackout_reason = "holiday_study_blackout"

        # C. Blocked observance
        observance_blackout = any(
            h.observance_key in resolved_settings.blocked_observance_keys
            for h in h_list
            if h.observance_key
        )
        if observance_blackout:
            blackout_reason = "blocked_observance"

        # Check for exam falling on blackout or weekly off day
        if curr_date in exam_lookup:
            sub_list_str = (
                ", ".join(exam_lookup[curr_date]) if exam_lookup[curr_date] else "Scheduled Exam"
            )
            if w_name in resolved_settings.weekly_off_days and warnings is not None:
                warn_msg = (
                    f"EXAM_ON_WEEKLY_OFF: Exam date {curr_date.isoformat()} ({sub_list_str}) "
                    f"falls on a weekly off day ({w_name.upper()})."
                )
                if warn_msg not in warnings:
                    warnings.append(warn_msg)

            if (
                is_custom_blackout or holiday_blackout or observance_blackout
            ) and warnings is not None:
                warn_msg = (
                    f"EXAM_ON_BLACKOUT: Exam date {curr_date.isoformat()} ({sub_list_str}) "
                    f"falls on a blackout date ({blackout_reason})."
                )
                if warn_msg not in warnings:
                    warnings.append(warn_msg)

        if is_custom_blackout or holiday_blackout or observance_blackout:
            zero_code = "parent blackout" if is_custom_blackout else "calendar blackout"
            days.append(
                DayScheduleInfo(
                    date=curr_date,
                    day_type="blackout",
                    budget_minutes=0,
                    reason=blackout_reason,
                    zero_reason=zero_code,
                    subject_exams=exam_lookup.get(curr_date, []),
                )
            )
            curr_date = date.fromordinal(curr_date.toordinal() + 1)
            continue

        # 2. Check for Rest Day (parent-configured rest weekday) or Holiday (Weekly off or published non-blackout holiday)
        is_parent_rest = (
            resolved_settings.rest_weekday is not None
            and w_name == resolved_settings.rest_weekday.strip().lower()[:3]
        )
        is_weekly_off = w_name in resolved_settings.weekly_off_days
        has_holiday = len(h_list) > 0

        zero_code = None
        if is_parent_rest:
            base_type: Literal["school_day", "holiday"] = "holiday"
            base_budget = 0
            zero_code = "rest"
        elif is_weekly_off or has_holiday:
            base_type = "holiday"
            base_budget = resolved_settings.holiday_minutes
        else:
            base_type = "school_day"
            base_budget = resolved_settings.school_day_minutes

        # 3. Check for Exam Day (zero study only for exam subject; budget remains for others)
        is_exam_day = curr_date in exam_lookup
        effective_day_type = "exam_day" if is_exam_day else base_type

        # 4. Handle Today's remaining budget calculation (Requirement D.11)
        if curr_date == today_date:
            today_budget = calculate_today_remaining_budget(
                now=now,
                base_budget=base_budget,
                study_window_start=resolved_settings.study_window_start,
                study_window_end=resolved_settings.study_window_end,
                recurring_unavailable_blocks=resolved_settings.recurring_unavailable_blocks,
                completed_minutes_today=completed_minutes_today,
            )
            days.append(
                DayScheduleInfo(
                    date=curr_date,
                    day_type=effective_day_type,
                    budget_minutes=today_budget,
                    reason="today_remaining_budget",
                    zero_reason="rest" if today_budget == 0 else None,
                    subject_exams=exam_lookup.get(curr_date, []),
                )
            )
        else:
            days.append(
                DayScheduleInfo(
                    date=curr_date,
                    day_type=effective_day_type,
                    budget_minutes=base_budget,
                    reason="exam_day" if is_exam_day else None,
                    zero_reason=zero_code if base_budget == 0 else None,
                    subject_exams=exam_lookup.get(curr_date, []),
                )
            )

        curr_date = date.fromordinal(curr_date.toordinal() + 1)

    return days


def calculate_today_remaining_budget(
    now: datetime,
    base_budget: int,
    study_window_start: str,
    study_window_end: str,
    recurring_unavailable_blocks: list[dict[str, Any]],
    completed_minutes_today: int,
) -> int:
    """Calculate time remaining in student's study window today after now (Req D.11).

    Formula:
    remaining_window_after_now - remaining_unavailable_blocks - completed_minutes_today,
    clamped to [0, base_budget].
    """
    if base_budget <= 0:
        return 0

    w_start = parse_time_str(study_window_start)
    w_end = parse_time_str(study_window_end)
    now_time = now.time()

    # If now is already past the study window end time, remaining window is 0
    if now_time >= w_end:
        return 0

    # Effective start of study time is max(now_time, w_start)
    eff_start = max(now_time, w_start)

    # Window remaining in minutes
    start_minutes = eff_start.hour * 60 + eff_start.minute
    end_minutes = w_end.hour * 60 + w_end.minute
    window_remaining = max(0, end_minutes - start_minutes)

    # Calculate overlapping unavailable blocks scheduled today that occur after eff_start
    weekday_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    today_w_name = weekday_names[now.date().weekday()]

    unavailable_overlap = 0
    for block in recurring_unavailable_blocks:
        if block.get("day_of_week") != today_w_name:
            continue
        b_start = parse_time_str(block["start_time"])
        b_end = parse_time_str(block["end_time"])

        b_start_min = b_start.hour * 60 + b_start.minute
        b_end_min = b_end.hour * 60 + b_end.minute

        # Overlap with [start_minutes, end_minutes]
        overlap_start = max(start_minutes, b_start_min)
        overlap_end = min(end_minutes, b_end_min)
        if overlap_end > overlap_start:
            unavailable_overlap += overlap_end - overlap_start

    net_available = window_remaining - unavailable_overlap - completed_minutes_today
    return max(0, min(base_budget, net_available))


async def resolve_student_settings(
    db: AsyncSession,
    student_id: uuid.UUID,
) -> ResolvedPlannerSettings:
    """Resolve 5-tier settings hierarchy:
    Tier 1 (Base): System defaults
    Tier 2: Class-band defaults (AdminPolicy)
    Tier 3: AI adjustments (versioned ai_adjustments)
    Tier 4: Parent-locked values (StudentStudySettings)
    Tier 5 (Top): Admin hard limits (clamping and bounds)
    """
    # 1. Fetch Student Profile
    stmt_profile = select(StudentProfile).where(StudentProfile.user_id == student_id)
    res_profile = await db.execute(stmt_profile)
    profile = res_profile.scalar_one_or_none()

    class_level = profile.class_level if profile else 7
    class_band = get_class_band(class_level)
    student_group = profile.group if profile and profile.group else "general"

    # 2. Fetch Published Admin Policy (matching band and group, fallback to general)
    stmt_policy = (
        select(AdminPolicy)
        .where(
            AdminPolicy.class_band == class_band,
            AdminPolicy.group.in_([student_group, "general"]),
            AdminPolicy.status == "published",
        )
        .order_by(AdminPolicy.version.desc())
    )
    res_policy = await db.execute(stmt_policy)
    policies = res_policy.scalars().all()
    admin_policy = next((p for p in policies if p.group == student_group), None)
    if not admin_policy and policies:
        admin_policy = policies[0]

    # --- TIER 1: SYSTEM DEFAULTS ---
    sys_recommended = CLASS_BAND_RECOMMENDED_MINUTES.get(class_band, 90)
    res_school_m = sys_recommended
    res_holiday_m = sys_recommended
    res_win_start = "17:00"
    res_win_end = "22:00"
    res_weekly_off = ["fri", "sat"]
    res_unavail: list[dict[str, Any]] = []
    res_blocked_obs: list[str] = []
    res_custom_blackouts: list[dict[str, Any]] = []
    res_sub_prio: dict[str, str] = {}
    res_planner_params: dict[str, Any] = DEFAULT_PLANNER_PARAMETERS.copy()

    # --- TIER 2: CLASS-BAND DEFAULTS (AdminPolicy) ---
    if admin_policy:
        if admin_policy.recommended_daily_minutes:
            res_school_m = admin_policy.recommended_daily_minutes
            res_holiday_m = admin_policy.recommended_daily_minutes
        if admin_policy.latest_end_time:
            res_win_end = admin_policy.latest_end_time
        if admin_policy.weekly_off_days:
            res_weekly_off = list(admin_policy.weekly_off_days)
        if admin_policy.planner_parameters:
            res_planner_params.update(admin_policy.planner_parameters)

    # 3. Fetch Parent Settings (StudentStudySettings)
    stmt_settings = select(StudentStudySettings).where(
        StudentStudySettings.student_id == student_id
    )
    res_settings = await db.execute(stmt_settings)
    parent_settings = res_settings.scalar_one_or_none()

    adaptive_mode = parent_settings.adaptive_mode if parent_settings else "suggest"
    raw_ai_adjustments = parent_settings.ai_adjustments if parent_settings else {}
    ai_adjustments = raw_ai_adjustments if isinstance(raw_ai_adjustments, dict) else {}
    parent_locked_fields = parent_settings.parent_locked_fields if parent_settings else []
    parent_locked_set = set(parent_locked_fields or [])

    # --- TIER 3: AI ADJUSTMENTS LAYER ---
    # Apply AI adjustments if adaptive_mode is auto_within_limits and field is not locked by parent
    ai_vals = (
        ai_adjustments.get("adjustments", ai_adjustments)
        if isinstance(ai_adjustments, dict)
        else {}
    )
    if adaptive_mode == "auto_within_limits" and isinstance(ai_vals, dict):
        if "school_day_minutes" in ai_vals and "school_day_minutes" not in parent_locked_set:
            res_school_m = int(ai_vals["school_day_minutes"])
        if "holiday_minutes" in ai_vals and "holiday_minutes" not in parent_locked_set:
            res_holiday_m = int(ai_vals["holiday_minutes"])
        if "subject_priorities" in ai_vals and "subject_priorities" not in parent_locked_set:
            if isinstance(ai_vals["subject_priorities"], dict):
                res_sub_prio.update(ai_vals["subject_priorities"])
        if "planner_parameters" in ai_vals and "planner_parameters" not in parent_locked_set:
            if isinstance(ai_vals["planner_parameters"], dict):
                res_planner_params.update(ai_vals["planner_parameters"])

    # --- TIER 4: PARENT-LOCKED & PARENT EXPLICIT SETTINGS ---
    settings_version = 1
    if parent_settings:
        settings_version = parent_settings.version
        # Parent values take precedence if explicitly configured or locked
        if parent_settings.school_day_minutes is not None:
            if (
                "school_day_minutes" in parent_locked_set
                or adaptive_mode != "auto_within_limits"
                or "school_day_minutes" not in ai_vals
            ):
                res_school_m = parent_settings.school_day_minutes

        if parent_settings.holiday_minutes is not None:
            if (
                "holiday_minutes" in parent_locked_set
                or adaptive_mode != "auto_within_limits"
                or "holiday_minutes" not in ai_vals
            ):
                res_holiday_m = parent_settings.holiday_minutes

        if parent_settings.study_window_start:
            res_win_start = parent_settings.study_window_start
        if parent_settings.study_window_end:
            res_win_end = parent_settings.study_window_end
        if parent_settings.recurring_unavailable_blocks:
            res_unavail = parent_settings.recurring_unavailable_blocks
        if parent_settings.blocked_observance_keys:
            res_blocked_obs = parent_settings.blocked_observance_keys
        if parent_settings.custom_blackout_dates:
            res_custom_blackouts = parent_settings.custom_blackout_dates
        if parent_settings.subject_priorities:
            if (
                "subject_priorities" in parent_locked_set
                or adaptive_mode != "auto_within_limits"
                or "subject_priorities" not in ai_vals
            ):
                res_sub_prio = dict(parent_settings.subject_priorities)

    # --- TIER 5: ADMIN HARD LIMITS & CLAMPING ---
    min_daily_m = admin_policy.min_daily_minutes if admin_policy else 0
    max_daily_m = admin_policy.max_daily_minutes if admin_policy else 600
    rec_daily_m = admin_policy.recommended_daily_minutes if admin_policy else sys_recommended
    max_block_m = admin_policy.max_block_minutes if admin_policy else 90
    latest_end = admin_policy.latest_end_time if admin_policy else "22:00"

    admin_hard_limits = {
        "min_daily_minutes": min_daily_m,
        "max_daily_minutes": max_daily_m,
        "recommended_daily_minutes": rec_daily_m,
        "max_block_minutes": max_block_m,
        "latest_end_time": latest_end,
    }

    clamping_notices: list[str] = []
    warnings: list[str] = []

    # Clamp school day minutes
    clamped_school_m = min(max(res_school_m, min_daily_m), max_daily_m)
    if clamped_school_m != res_school_m:
        clamping_notices.append(
            f"NOTICE: School day minutes clamped from {res_school_m}m to {clamped_school_m}m "
            f"to adhere to admin policy limits [{min_daily_m}m - {max_daily_m}m]."
        )

    # Clamp holiday minutes
    clamped_holiday_m = min(max(res_holiday_m, min_daily_m), max_daily_m)
    if clamped_holiday_m != res_holiday_m:
        clamping_notices.append(
            f"NOTICE: Holiday minutes clamped from {res_holiday_m}m to {clamped_holiday_m}m "
            f"to adhere to admin policy limits [{min_daily_m}m - {max_daily_m}m]."
        )

    # Clamp study window end time to latest_end if necessary
    if parse_time_str(res_win_end) > parse_time_str(latest_end):
        clamping_notices.append(
            f"NOTICE: Study window end time {res_win_end} clamped to "
            f"admin latest allowed time {latest_end}."
        )
        res_win_end = latest_end

    # Warning if study time exceeds recommended level (Req D.14)
    if clamped_school_m > rec_daily_m:
        warnings.append(
            f"WARNING: School day study time ({clamped_school_m}m) exceeds the recommended level "
            f"({rec_daily_m}m) for class band {class_band}."
        )
    if clamped_holiday_m > (rec_daily_m * 2):
        warnings.append(
            f"WARNING: Holiday study time ({clamped_holiday_m}m) exceeds the recommended level "
            f"({rec_daily_m * 2}m) for class band {class_band}."
        )

    return ResolvedPlannerSettings(
        class_band=class_band,
        group=student_group,
        school_day_minutes=clamped_school_m,
        holiday_minutes=clamped_holiday_m,
        study_window_start=res_win_start,
        study_window_end=res_win_end,
        weekly_off_days=res_weekly_off,
        recurring_unavailable_blocks=res_unavail,
        blocked_observance_keys=res_blocked_obs,
        custom_blackout_dates=res_custom_blackouts,
        subject_priorities=res_sub_prio,
        rest_weekday=parent_settings.rest_weekday if parent_settings else None,
        planner_parameters=res_planner_params,
        adaptive_mode=adaptive_mode,
        ai_adjustments=ai_adjustments,
        parent_locked_fields=parent_locked_fields,
        clamping_notices=clamping_notices,
        warnings=warnings,
        recommended_daily_minutes=rec_daily_m,
        admin_hard_limits=admin_hard_limits,
        settings_version=settings_version,
    )


async def get_published_holidays(
    db: AsyncSession,
    from_date: date,
    to_date: date,
) -> list[Holiday]:
    """Load published holidays overlapping the given date range."""
    stmt = (
        select(Holiday)
        .where(
            Holiday.status == "published",
            Holiday.start_date <= to_date,
            Holiday.end_date >= from_date,
        )
        .order_by(Holiday.start_date.asc())
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())
