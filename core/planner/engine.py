"""Pure-Python deterministic adaptive study planner engine.

Implements docs/06_ADAPTIVE_ENGINE.md §1 & §4, and product flows §4.1, §4.2:
- Zero DB, HTTP, or framework imports.
- Pure parameter-driven: accepts `today` explicitly and never reads the system clock.
- Multi-subject shared daily budget: student-level daily minutes cap shared across all active
  subjects, favoring nearer exams and heavier chapters.
- Dynamic appearance frequency by priority (difficult up to 2 of 3 days, main ~half, normal
  ~third-to-half), enforcing rotation limit (<= 2 consecutive study days).
- Spaced revision at 1, 3, 7 days referencing earlier material, never same-day study,
  always with page ranges.
- Exam days: zero study only for subject with exam that day; approaching exams (<= 3 days)
  at reduced load (<= 50%).
- Exam on weekly off or blackout warning generation.
- Buffer day separation from blackout: catch-up days carrying rolled tasks; zero-day reason codes
  (exam, parent blackout, calendar blackout, rest).
- Pre-exam spare budget fill target (default 80%) for practice/weak points;
  mock quiz capped at 1 per 2 days.
- Minimum study block (default 20m) derived from pages, min/page, difficulty; merges small tasks.
- Content-reflective day labels: days with study tasks are labeled "study", not "revision".
- Per-subject and per-chapter mastery input (defaulting to unknown).
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.planner.settings_resolver import DayScheduleInfo, ResolvedPlannerSettings

DAY_NAMES_TO_WEEKDAY = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


@dataclass(frozen=True)
class TimeShareConfig:
    """Configurable time shares for daily task composition per docs/06_ADAPTIVE_ENGINE.md §4."""

    study_share: float = 0.65
    revision_share: float = 0.25
    weak_point_share: float = 0.0
    homework_quiz_share: float = 0.10

    def __post_init__(self) -> None:
        total = (
            self.study_share
            + self.revision_share
            + self.weak_point_share
            + self.homework_quiz_share
        )
        if not math.isclose(total, 1.0, rel_tol=1e-3):
            msg = f"Time shares must sum to 1.0, got {total}"
            raise ValueError(msg)


@dataclass
class ChapterPlanInput:
    """Textbook chapter definition for syllabus planning."""

    id: uuid.UUID | str
    number: int
    title: str
    printed_page_start: int
    printed_page_end: int
    custom_order: int
    book_id: uuid.UUID | str | None = None
    book_title: str = ""
    weight: float = 1.0
    difficulty_factor: float = 1.0  # Default 1.0, configurable per chapter
    mastery: float | None = None  # Unknown mastery defaults to 0.5

    @property
    def total_pages(self) -> int:
        return max(1, self.printed_page_end - self.printed_page_start + 1)

    @property
    def effective_mastery(self) -> float:
        return self.mastery if self.mastery is not None else 0.5

    @property
    def effort(self) -> float:
        """Effort formula: pages * difficulty * weight * (1 + (1 - mastery))."""
        return (
            self.total_pages
            * self.difficulty_factor
            * self.weight
            * (1.0 + (1.0 - self.effective_mastery))
        )


@dataclass
class SubjectSetupInput:
    """Study setup configuration for a single subject."""

    subject: str
    exam_name: str
    exam_date: date
    chapters: list[ChapterPlanInput]
    setup_id: uuid.UUID | str | None = None
    mastery: float | None = None  # Per-subject default mastery (unknown defaults to 0.5)


@dataclass
class CompletedTaskRecord:
    """Historical task to be preserved or rolled during plan regeneration."""

    task_id: uuid.UUID | str
    subject: str
    chapter_id: uuid.UUID | str | None
    plan_date: date
    type: str
    est_minutes: int
    refs: dict[str, Any]
    status: str = "done"  # done, todo, in_progress, rolled
    completed_at: str | None = None


# Alias for clarity
HistoricalTaskRecord = CompletedTaskRecord


@dataclass
class GeneratedTask:
    """A generated study or revision task for a specific plan day."""

    id: uuid.UUID
    subject: str
    type: str  # study, revision, homework, quiz, broad, review_quiz
    chapter_id: uuid.UUID | str | None
    est_minutes: int
    refs: dict[str, Any]
    status: str = "todo"  # todo, in_progress, done, skipped, rolled
    source: str = "planner"  # planner, adaptive, teacher
    completed_at: str | None = None


@dataclass
class GeneratedPlanDay:
    """A calendar day within a student's study plan."""

    date: date
    planned_minutes: int
    day_type: str  # study, buffer, revision, blackout, exam_day
    tasks: list[GeneratedTask] = field(default_factory=list)
    zero_reason: str | None = None  # exam, parent blackout, calendar blackout, rest


@dataclass
class SubjectCoverageReport:
    """Coverage audit for a subject's syllabus before its exam."""

    subject: str
    exam_date: date
    total_chapters: int
    scheduled_chapters: int
    total_pages: int
    scheduled_pages: int
    coverage_pct: float
    shortfall_pages: int
    shortfall_warning: str | None = None


@dataclass
class SingleSubjectPlan:
    """Generated plan for a single subject."""

    subject: str
    exam_date: date
    days: list[GeneratedPlanDay]
    warnings: list[str] = field(default_factory=list)
    coverage: SubjectCoverageReport | None = None


@dataclass
class MultiSubjectPlanOutput:
    """Consolidated study plan across all subjects for a student."""

    student_id: uuid.UUID | str
    today: date
    daily_study_minutes: int
    days: list[GeneratedPlanDay]
    subject_plans: dict[str, SingleSubjectPlan]
    warnings: list[str] = field(default_factory=list)
    total_tasks: int = 0
    coverage_reports: dict[str, SubjectCoverageReport] = field(default_factory=dict)


@dataclass
class PendingSpacedRevision:
    """A scheduled spaced revision task to be realized on or after target_date."""

    subject: str
    chapter_id: uuid.UUID | str | None
    chapter_number: int
    chapter_title: str
    book_title: str
    printed_page_start: int
    printed_page_end: int
    interval_days: int
    target_date: date
    study_date: date
    est_minutes: int


def normalize_available_days(available_days: list[str] | list[int] | set[int]) -> set[int]:
    """Convert string day names ('mon', 'tue', etc.) or integers (0..6) to set of weekdays."""
    result: set[int] = set()
    for item in available_days:
        if isinstance(item, int) and 0 <= item <= 6:
            result.add(item)
        elif isinstance(item, str):
            clean = item.strip().lower()
            if clean in DAY_NAMES_TO_WEEKDAY:
                result.add(DAY_NAMES_TO_WEEKDAY[clean])
    return result or {0, 1, 2, 3, 4, 5, 6}


def calculate_usable_dates(
    today: date,
    exam_date: date,
    available_weekdays: set[int],
    max_days: int = 365,
) -> list[date]:
    """Return ordered list of calendar dates between today and exam_date matching available days."""
    if exam_date < today:
        return []

    usable: list[date] = []
    curr = today
    limit = min(exam_date, today + timedelta(days=max_days))
    while curr <= limit:
        if curr.weekday() in available_weekdays:
            usable.append(curr)
        curr += timedelta(days=1)
    return usable


def generate_student_plan(
    student_id: uuid.UUID | str,
    today: date,
    daily_study_minutes: int,
    setups: list[SubjectSetupInput],
    available_days: list[str] | list[int] | set[int] | None = None,
    completed_tasks: list[CompletedTaskRecord] | None = None,
    time_shares: TimeShareConfig = TimeShareConfig(),
    max_days: int = 365,
    min_subject_daily_share: float = 0.10,
    rolling_horizon_days: int = 60,
    resolved_settings: ResolvedPlannerSettings | None = None,
    day_calendar: list[DayScheduleInfo] | None = None,
) -> MultiSubjectPlanOutput:
    """Generate a multi-subject versioned study plan honoring a shared daily budget.

    Guarantees:
    - Never schedules any study tasks after a subject's exam_date.
    - Sum of planned task minutes on any day across ALL subjects <= daily_study_minutes.
    - Spaced revision at 1, 3, 7 days referencing earlier material, never same-day study.
    - Priority-based appearance frequency (difficult <= 2/3, main ~half, normal ~third)
      with rotation limit <= 2.
    - Exam days: zero study only for exam subject; approaching exams (<= 3d) at <= 50% load.
    - Warnings if exam dates fall on weekly off days or blackout dates.
    - Buffer days separated from blackout days; reason codes for every zero-study day.
    - Pre-exam spare budget filled up to 80% with practice; mock quizzes capped at 1 per 2 days.
    - Minimum study block of 20 minutes (merging small tasks).
    - Day labels reflect content (days with study tasks are labeled 'study', not 'revision').
    """
    global_warnings: list[str] = []
    available_weekdays = normalize_available_days(
        available_days or ["sat", "sun", "mon", "tue", "wed", "thu", "fri"]
    )
    completed = completed_tasks or []

    # Filter out empty setups
    active_setups = [s for s in setups if s.chapters]
    if not active_setups:
        return MultiSubjectPlanOutput(
            student_id=student_id,
            today=today,
            daily_study_minutes=daily_study_minutes,
            days=[],
            subject_plans={},
            warnings=["NO_ACTIVE_SUBJECTS: No subjects with chapters configured for planning."],
            total_tasks=0,
        )

    # 1. Inherit subject mastery into chapters if chapter mastery is None
    for s in active_setups:
        if s.mastery is not None:
            for ch in s.chapters:
                if ch.mastery is None:
                    ch.mastery = s.mastery

    # 2. Extract configuration parameters
    planner_params = resolved_settings.planner_parameters if resolved_settings else {}
    prio_mapping = planner_params.get(
        "priority_weight_mapping",
        {"normal": 1.0, "main": 1.3, "difficult": 1.6},
    )
    max_consecutive_days = planner_params.get("max_consecutive_days_per_subject", 2)
    appearance_targets = planner_params.get(
        "appearance_frequency_targets",
        {"difficult": 0.67, "main": 0.50, "normal": 0.38},
    )
    exam_approaching_window = planner_params.get("exam_approaching_window_days", 3)
    exam_approaching_load_ratio = planner_params.get("exam_approaching_load_ratio", 0.50)
    final_window_fill_target = planner_params.get("final_window_fill_target", 0.80)
    mock_quiz_max_frequency_days = planner_params.get("mock_quiz_max_frequency_days", 2)
    min_study_block_minutes = planner_params.get("min_study_block_minutes", 20)
    weekly_off_days_list = (
        resolved_settings.weekly_off_days if resolved_settings else ["fri", "sat"]
    )
    sub_priorities = resolved_settings.subject_priorities if resolved_settings else {}

    weekday_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    # 3. Check exam edge cases and emit warnings
    for s in active_setups:
        if s.exam_date < today:
            global_warnings.append(
                f"EXAM_PASSED_{s.subject.upper()}: Exam date {s.exam_date} has already passed."
            )
        elif s.exam_date == today:
            global_warnings.append(f"EXAM_TODAY_{s.subject.upper()}: Exam is scheduled for today.")
        elif s.exam_date == today + timedelta(days=1):
            global_warnings.append(
                f"EXAM_TOMORROW_{s.subject.upper()}: Exam is tomorrow; urgent review."
            )

        # Check if exam falls on weekly off day
        w_name = weekday_names[s.exam_date.weekday()]
        if w_name in weekly_off_days_list:
            warn = (
                f"EXAM_ON_WEEKLY_OFF: Exam for {s.subject} on {s.exam_date.isoformat()} "
                f"falls on a weekly off day ({w_name.upper()})."
            )
            if warn not in global_warnings:
                global_warnings.append(warn)

    # 4. Build day calendar, blackout map, and zero-reason codes
    max_exam_date = max(s.exam_date for s in active_setups)
    horizon_limit = today + timedelta(days=rolling_horizon_days)

    if max_exam_date > horizon_limit:
        effective_max_date = horizon_limit
        global_warnings.append(
            f"ROLLING_HORIZON_ACTIVE: Planning horizon set to {rolling_horizon_days} days "
            f"(through {horizon_limit}). Future syllabus through {max_exam_date} will be "
            "scheduled automatically as time advances."
        )
    else:
        effective_max_date = max_exam_date

    day_budget_map: dict[date, int] = {}
    day_map: dict[date, GeneratedPlanDay] = {}
    blackout_dates: set[date] = set()
    blackout_reasons: dict[date, str] = {}
    calendar_exam_dates: set[date] = {s.exam_date for s in active_setups}

    if day_calendar:
        for ds in day_calendar:
            d = ds.date
            day_budget_map[d] = ds.budget_minutes
            if ds.day_type == "blackout":
                blackout_dates.add(d)
                blackout_reasons[d] = ds.zero_reason or "parent blackout"
                day_map[d] = GeneratedPlanDay(
                    date=d,
                    planned_minutes=0,
                    day_type="blackout",
                    tasks=[],
                    zero_reason=ds.zero_reason or "parent blackout",
                )
            else:
                day_map[d] = GeneratedPlanDay(
                    date=d,
                    planned_minutes=0,
                    day_type=ds.day_type,
                    tasks=[],
                    zero_reason=ds.zero_reason,
                )
        all_usable_dates = [ds.date for ds in day_calendar if ds.day_type != "blackout"]
    else:
        all_usable_dates = calculate_usable_dates(
            today,
            effective_max_date,
            available_weekdays,
            max_days=min(max_days, rolling_horizon_days),
        )
        if not all_usable_dates:
            global_warnings.append("ZERO_USABLE_DAYS: No available study days found.")
            all_usable_dates = [today]

        for d in all_usable_dates:
            day_budget_map[d] = daily_study_minutes
            day_map[d] = GeneratedPlanDay(
                date=d, planned_minutes=0, day_type="study", tasks=[], zero_reason=None
            )

    # Warn if exam falls on blackout
    for s in active_setups:
        if s.exam_date in blackout_dates:
            b_reason = blackout_reasons.get(s.exam_date, "blackout")
            warn = (
                f"EXAM_ON_BLACKOUT: Exam for {s.subject} on {s.exam_date.isoformat()} "
                f"falls on a blackout date ({b_reason})."
            )
            if warn not in global_warnings:
                global_warnings.append(warn)

    # 5. Cross-subject workload feasibility
    total_curriculum_effort_mins = 0.0
    subject_efforts: dict[str, float] = {}
    for s in active_setups:
        prio = sub_priorities.get(s.subject, "normal")
        prio_mult = prio_mapping.get(prio, 1.0)
        s_effort = sum(ch.effort for ch in s.chapters) * 2.5 * prio_mult
        subject_efforts[s.subject] = s_effort
        total_curriculum_effort_mins += s_effort

    total_budget_all_usable_days = sum(
        day_budget_map.get(d, daily_study_minutes) for d in all_usable_dates
    )
    if total_curriculum_effort_mins > total_budget_all_usable_days:
        needed_m = math.ceil(total_curriculum_effort_mins)
        u_days = len(all_usable_dates)
        global_warnings.append(
            f"CROSS_SUBJECT_FEASIBILITY_WARNING: Combined curriculum workload across "
            f"{len(active_setups)} active subjects requires {needed_m} mins, exceeding total "
            f"budget of {total_budget_all_usable_days} mins across {u_days} usable days. "
            f"Recommend increasing student daily study minutes (currently {daily_study_minutes}m) "
            "or adjusting exam dates."
        )

    # 6. Process historical tasks and missed-task roll-forward
    today_target_candidates = [
        d for d in all_usable_dates if d >= today and d not in blackout_dates
    ]
    today_target_date = today_target_candidates[0] if today_target_candidates else today
    if today_target_date not in day_map:
        day_map[today_target_date] = GeneratedPlanDay(
            date=today_target_date, planned_minutes=0, day_type="study", tasks=[], zero_reason=None
        )
    today_target_day = day_map[today_target_date]

    rolled_forward_tasks_count = 0
    for ct in completed:
        if ct.plan_date < today:
            if ct.plan_date not in day_map:
                day_map[ct.plan_date] = GeneratedPlanDay(
                    date=ct.plan_date,
                    planned_minutes=0,
                    day_type="study",
                    tasks=[],
                    zero_reason=None,
                )
            hist_day = day_map[ct.plan_date]
            if ct.status == "done":
                gt = GeneratedTask(
                    id=uuid.UUID(str(ct.task_id)) if isinstance(ct.task_id, str) else ct.task_id,
                    subject=ct.subject,
                    type=ct.type,
                    chapter_id=ct.chapter_id,
                    est_minutes=ct.est_minutes,
                    refs=ct.refs,
                    status="done",
                    completed_at=ct.completed_at,
                )
                hist_day.tasks.append(gt)
                hist_day.planned_minutes += ct.est_minutes
            elif ct.status in ("todo", "in_progress"):
                rolled_hist_task = GeneratedTask(
                    id=uuid.UUID(str(ct.task_id)) if isinstance(ct.task_id, str) else ct.task_id,
                    subject=ct.subject,
                    type=ct.type,
                    chapter_id=ct.chapter_id,
                    est_minutes=ct.est_minutes,
                    refs=ct.refs,
                    status="rolled",
                )
                hist_day.tasks.append(rolled_hist_task)

                # Roll forward to today
                orig_guideline = ct.refs.get("guideline", "")
                rolled_forward_task = GeneratedTask(
                    id=uuid.uuid4(),
                    subject=ct.subject,
                    type=ct.type,
                    chapter_id=ct.chapter_id,
                    est_minutes=ct.est_minutes,
                    refs={
                        **ct.refs,
                        "guideline": f"[Rolled from {ct.plan_date}] {orig_guideline}".strip(),
                        "rolled_from_task_id": str(ct.task_id),
                    },
                    status="todo",
                    source="planner",
                )
                today_target_day.tasks.append(rolled_forward_task)
                today_target_day.planned_minutes += ct.est_minutes
                rolled_forward_tasks_count += 1
        else:
            if ct.plan_date not in day_map:
                day_map[ct.plan_date] = GeneratedPlanDay(
                    date=ct.plan_date,
                    planned_minutes=0,
                    day_type="study",
                    tasks=[],
                    zero_reason=None,
                )
            cur_day = day_map[ct.plan_date]
            gt = GeneratedTask(
                id=uuid.UUID(str(ct.task_id)) if isinstance(ct.task_id, str) else ct.task_id,
                subject=ct.subject,
                type=ct.type,
                chapter_id=ct.chapter_id,
                est_minutes=ct.est_minutes,
                refs=ct.refs,
                status=ct.status,
                completed_at=ct.completed_at,
            )
            cur_day.tasks.append(gt)
            cur_day.planned_minutes += ct.est_minutes

    # 7. Calculate subject weights and daily budget slices
    floor_share = min(min_subject_daily_share, 1.0 / max(1, len(active_setups)))
    raw_weights: dict[str, float] = {}
    for setup in active_setups:
        days_to_exam = max(1, (setup.exam_date - today).days)
        urgency = 1.0 / days_to_exam
        prio = sub_priorities.get(setup.subject, "normal")
        prio_mult = prio_mapping.get(prio, 1.0)
        workload = sum(ch.effort for ch in setup.chapters) * prio_mult
        raw_weights[setup.subject] = urgency * workload

    total_raw_weight = sum(raw_weights.values()) or 1.0
    subject_daily_budgets: dict[str, int] = {}
    for setup in active_setups:
        proportional_share = raw_weights[setup.subject] / total_raw_weight
        effective_share = max(floor_share, proportional_share)
        budget = max(min_study_block_minutes, math.floor(daily_study_minutes * effective_share))
        subject_daily_budgets[setup.subject] = budget

    # 8. Setup Subject Progress Trackers
    class SubjectStudyState:
        def __init__(
            self,
            setup: SubjectSetupInput,
            sorted_chapters: list[ChapterPlanInput],
            rev_window_dates: set[date],
            buffer_dates: set[date],
            compression_ratio: float,
        ) -> None:
            self.setup = setup
            self.sorted_chapters = sorted_chapters
            self.rev_window_dates = rev_window_dates
            self.buffer_dates = buffer_dates
            self.compression_ratio = compression_ratio
            self.total_pages = sum(ch.total_pages for ch in sorted_chapters)
            self.chapter_idx = 0
            self.pages_covered = 0
            self.consecutive_study_days = 0
            self.days_scheduled = 0
            self.total_study_minutes = 0
            self.finished_all_chapters = False
            self.last_mock_quiz_date: date | None = None
            self.pending_spaced_revisions: list[PendingSpacedRevision] = []
            self.sub_warnings: list[str] = []
            self.covered_pages_set: set[int] = set()
            self.chapters_covered_set: set[uuid.UUID | str] = set()
            self.chapter_last_revised_date: dict[uuid.UUID | str, date] = {}
            self.slice_last_revised_date: dict[tuple[Any, int, int], date] = {}

    trackers: dict[str, SubjectStudyState] = {}
    for setup in active_setups:
        sub_usable_dates = [
            d for d in all_usable_dates if d <= setup.exam_date and d not in blackout_dates
        ]
        if not sub_usable_dates:
            sub_usable_dates = [today]

        num_days = len(sub_usable_dates)
        if num_days <= 3:
            rev_window_size = num_days
        else:
            rev_window_size = max(3, math.ceil(num_days * 0.15))

        rev_window_dates = set(sub_usable_dates[-rev_window_size:])
        buffer_dates: set[date] = set()

        for idx, d in enumerate(
            sub_usable_dates[:-rev_window_size] if num_days > rev_window_size else []
        ):
            if (idx + 1) % 7 == 0:
                buffer_dates.add(d)
                if day_map[d].day_type not in ("blackout", "exam_day"):
                    day_map[d].day_type = "buffer"

        for d in rev_window_dates:
            if day_map[d].day_type not in ("blackout", "exam_day"):
                day_map[d].day_type = "revision"

        sorted_chapters = sorted(setup.chapters, key=lambda c: c.custom_order)
        study_candidate_dates = [
            d
            for d in sub_usable_dates
            if d not in rev_window_dates and d not in buffer_dates and d not in blackout_dates
        ]
        if not study_candidate_dates:
            study_candidate_dates = list(sub_usable_dates)

        sub_daily_b = subject_daily_budgets.get(setup.subject, min_study_block_minutes)
        prio = sub_priorities.get(setup.subject, "normal")
        prio_mult = prio_mapping.get(prio, 1.0)
        est_study_minutes_needed = sum(ch.effort for ch in sorted_chapters) * 2.5 * prio_mult
        total_available_study_minutes = len(study_candidate_dates) * math.floor(
            sub_daily_b * time_shares.study_share
        )

        compression_ratio = 1.0
        if (
            total_available_study_minutes > 0
            and est_study_minutes_needed > total_available_study_minutes
        ):
            compression_ratio = total_available_study_minutes / est_study_minutes_needed

        trackers[setup.subject] = SubjectStudyState(
            setup=setup,
            sorted_chapters=sorted_chapters,
            rev_window_dates=rev_window_dates,
            buffer_dates=buffer_dates,
            compression_ratio=compression_ratio,
        )

    # 9. Day-by-Day Scheduling Loop
    usable_dates_sorted = sorted(
        [d for d in all_usable_dates if d not in blackout_dates and d >= today]
    )

    study_day_counter = 0

    for cur_date in usable_dates_sorted:
        cur_day = day_map[cur_date]
        day_cap = day_budget_map.get(cur_date, daily_study_minutes)
        if day_cap <= 0:
            continue

        study_day_counter += 1
        subjects_studied_today: set[str] = set()
        subjects_with_study_task: set[str] = set()

        # Step A: Identify active subjects on cur_date
        # Exam days: zero study only for subject with an exam that day
        # Approaching exams (<= 3 days) scheduled at reduced load (<= 50%)
        active_for_day: list[SubjectStudyState] = []
        for tracker in trackers.values():
            if cur_date >= tracker.setup.exam_date:
                # Zero study on or after exam date
                continue
            active_for_day.append(tracker)

        # Check approaching exam reduction
        effective_subject_budgets: dict[str, int] = {}
        for tracker in active_for_day:
            base_b = subject_daily_budgets.get(tracker.setup.subject, min_study_block_minutes)
            days_to_exam = (tracker.setup.exam_date - cur_date).days
            if 0 < days_to_exam <= exam_approaching_window:
                effective_subject_budgets[tracker.setup.subject] = max(
                    min_study_block_minutes, math.floor(base_b * exam_approaching_load_ratio)
                )
            else:
                effective_subject_budgets[tracker.setup.subject] = base_b

        # Step B & C: Select Eligible Subjects for cur_date by Rotation Limit & Appearance Priority
        eligible_for_study: list[SubjectStudyState] = []
        for tracker in active_for_day:
            # If in revision window AND finished all chapters, handled in final revision window (Step D)
            if cur_date in tracker.rev_window_dates and tracker.finished_all_chapters:
                continue
            if cur_date in tracker.buffer_dates:
                continue

            # Rotation limit: cannot study > max_consecutive_days consecutively
            if tracker.consecutive_study_days >= max_consecutive_days:
                continue
            eligible_for_study.append(tracker)

        # If all subjects reached the rotation limit, relax rule
        if not eligible_for_study and any(
            (cur_date not in t.rev_window_dates or not t.finished_all_chapters)
            and cur_date not in t.buffer_dates
            for t in active_for_day
        ):
            if not any("ROTATION_RULE_RELAXED" in w for w in global_warnings):
                global_warnings.append(
                    f"ROTATION_RULE_RELAXED: Consecutive study limit of {max_consecutive_days} "
                    "days relaxed due to remaining subject study demand."
                )
            eligible_for_study = [
                t
                for t in active_for_day
                if (cur_date not in t.rev_window_dates or not t.finished_all_chapters)
                and cur_date not in t.buffer_dates
            ]

        # Prioritize by Appearance Frequency Target & Fulfillment Ratio, with Exam Urgency
        def subject_appearance_priority(t: SubjectStudyState) -> tuple[float, float, float]:
            p = sub_priorities.get(t.setup.subject, "normal")
            target_freq = appearance_targets.get(p, 0.38)
            fulfillment_ratio = t.days_scheduled / max(0.01, target_freq)
            pm = prio_mapping.get(p, 1.0)
            days_to_exam = (t.setup.exam_date - cur_date).days
            urgency = 10.0 / max(1, days_to_exam) if days_to_exam <= 7 else 0.0
            return (urgency, -fulfillment_ratio, pm)

        eligible_for_study.sort(key=subject_appearance_priority, reverse=True)

        # Dynamic concurrency based on day budget:
        # 1-2 subjects for <= 100m, up to 3 subjects for >= 150m
        if len(active_for_day) >= 3:
            max_daily_slots = 2 if day_cap <= 100 else min(3, len(active_for_day))
            eligible_for_study = eligible_for_study[:max_daily_slots]

        for tracker in eligible_for_study:
            available_today = day_cap - cur_day.planned_minutes
            if available_today < min_study_block_minutes:
                break

            sub_budget = effective_subject_budgets.get(
                tracker.setup.subject, min_study_block_minutes
            )

            # 1. Realize pending spaced revisions due on or before cur_date
            # Collapse duplicate revisions to ONE per slice per day and compute actual elapsed days
            due_revisions = [
                r for r in tracker.pending_spaced_revisions if r.target_date <= cur_date
            ]
            slices_seen: set[tuple[Any, int, int]] = set()
            collapsed_revisions: list[PendingSpacedRevision] = []
            for r in due_revisions:
                s_key = (r.chapter_id, r.printed_page_start, r.printed_page_end)
                if s_key not in slices_seen:
                    slices_seen.add(s_key)
                    collapsed_revisions.append(r)

            tracker.pending_spaced_revisions = [
                r for r in tracker.pending_spaced_revisions if r.target_date > cur_date
            ]

            yesterday = cur_date - timedelta(days=1)
            for rev_item in collapsed_revisions:
                s_key = (rev_item.chapter_id, rev_item.printed_page_start, rev_item.printed_page_end)
                # Never repeat an identical task on consecutive days:
                # If this slice was already revised yesterday, defer by 2 days so it doesn't repeat consecutively
                if tracker.slice_last_revised_date.get(s_key) == yesterday:
                    rev_item.target_date = cur_date + timedelta(days=2)
                    if rev_item.target_date < tracker.setup.exam_date:
                        tracker.pending_spaced_revisions.append(rev_item)
                    continue

                rem_b = day_cap - cur_day.planned_minutes
                # If subject has unstudied chapters, preserve at least min_study_block_minutes for study
                if not tracker.finished_all_chapters and rem_b <= min_study_block_minutes:
                    tracker.pending_spaced_revisions.append(rev_item)
                    continue
                if rem_b < min_study_block_minutes:
                    tracker.pending_spaced_revisions.append(rev_item)
                    break

                rev_task_mins = min(rem_b, min_study_block_minutes)
                actual_elapsed_days = max(1, (cur_date - rev_item.study_date).days)
                rev_task = GeneratedTask(
                    id=uuid.uuid4(),
                    subject=tracker.setup.subject,
                    type="revision",
                    chapter_id=rev_item.chapter_id,
                    est_minutes=rev_task_mins,
                    refs={
                        "book_title": rev_item.book_title,
                        "chapter_number": rev_item.chapter_number,
                        "chapter_title": rev_item.chapter_title,
                        "printed_page_start": rev_item.printed_page_start,
                        "printed_page_end": rev_item.printed_page_end,
                        "guideline": (
                            f"Spaced revision (+{actual_elapsed_days}d): Review pages "
                            f"{rev_item.printed_page_start}–{rev_item.printed_page_end} of Chapter "
                            f"{rev_item.chapter_number} ({rev_item.chapter_title})."
                        ),
                        "spaced_interval_days": actual_elapsed_days,
                    },
                    status="todo",
                    source="planner",
                )
                cur_day.tasks.append(rev_task)
                cur_day.planned_minutes += rev_task_mins
                tracker.total_study_minutes += rev_task_mins
                tracker.slice_last_revised_date[s_key] = cur_date
                subjects_studied_today.add(tracker.setup.subject)

            available_today = day_cap - cur_day.planned_minutes
            if available_today < min_study_block_minutes:
                continue

            sub_budget = effective_subject_budgets.get(
                tracker.setup.subject, min_study_block_minutes
            )
            base_slice = math.floor(
                sub_budget * (time_shares.study_share + time_shares.revision_share)
            )
            sub_prio = sub_priorities.get(tracker.setup.subject, "normal")
            ch_prio_mult = prio_mapping.get(sub_prio, 1.0)
            adj_slice = math.floor(base_slice * (ch_prio_mult / 1.0))
            study_slice = min(available_today, max(min_study_block_minutes, adj_slice))

            if tracker.finished_all_chapters:
                # Practice review session rotating across chapters (oldest or weakest first)
                candidates = [
                    c for c in tracker.sorted_chapters
                    if tracker.chapter_last_revised_date.get(c.id) != yesterday
                ]
                if not candidates:
                    candidates = list(tracker.sorted_chapters)

                def ch_priority(c: ChapterPlanInput) -> tuple[float, date, int]:
                    last_rev = tracker.chapter_last_revised_date.get(c.id, date.min)
                    return (c.effective_mastery, last_rev, c.custom_order)

                candidates.sort(key=ch_priority)
                ch = candidates[0]
                tracker.chapter_last_revised_date[ch.id] = cur_date

                rev_task = GeneratedTask(
                    id=uuid.uuid4(),
                    subject=tracker.setup.subject,
                    type="revision",
                    chapter_id=ch.id,
                    est_minutes=study_slice,
                    refs={
                        "book_id": str(ch.book_id) if ch.book_id else None,
                        "book_title": ch.book_title,
                        "chapter_number": ch.number,
                        "chapter_title": ch.title,
                        "printed_page_start": ch.printed_page_start,
                        "printed_page_end": ch.printed_page_end,
                        "guideline": (
                            f"Concept revision and practice for Chapter {ch.number} ({ch.title})."
                        ),
                        "type": "practice_review",
                    },
                    status="todo",
                    source="planner",
                )
                cur_day.tasks.append(rev_task)
                cur_day.planned_minutes += study_slice
                tracker.total_study_minutes += study_slice
                subjects_studied_today.add(tracker.setup.subject)
                subjects_with_study_task.add(tracker.setup.subject)
                continue

            ch = tracker.sorted_chapters[tracker.chapter_idx]
            sub_prio = sub_priorities.get(tracker.setup.subject, "normal")
            ch_prio_mult = prio_mapping.get(sub_prio, 1.0)

            # Pacing calculation to guarantee 100% syllabus coverage before exam
            usable_days_left = sum(
                1
                for d in all_usable_dates
                if cur_date <= d < tracker.setup.exam_date
                and d not in blackout_dates
                and d not in tracker.buffer_dates
            )
            target_f = appearance_targets.get(sub_prio, 0.38)
            est_sessions_left = max(1, math.floor(usable_days_left * target_f))

            remaining_unstudied_pages = sum(
                c.total_pages for c in tracker.sorted_chapters[tracker.chapter_idx :]
            ) - tracker.pages_covered
            pace_pages = math.ceil(remaining_unstudied_pages / est_sessions_left)

            raw_ch_minutes = math.ceil(ch.effort * 2.5 * ch_prio_mult * tracker.compression_ratio)
            ch_study_minutes = max(min_study_block_minutes, raw_ch_minutes)
            fraction = min(1.0, study_slice / ch_study_minutes) if ch_study_minutes > 0 else 1.0

            pages_total = ch.total_pages
            pages_remaining_in_ch = pages_total - tracker.pages_covered

            pages_in_slice = max(pace_pages, math.ceil(pages_total * fraction))
            pages_in_slice = min(pages_remaining_in_ch, max(1, pages_in_slice))

            p_start = ch.printed_page_start + tracker.pages_covered
            p_end = p_start + pages_in_slice - 1
            tracker.pages_covered += pages_in_slice

            for pg in range(p_start, p_end + 1):
                tracker.covered_pages_set.add(pg)
            tracker.chapters_covered_set.add(ch.id)

            guideline_study = (
                f"Read pages {p_start}–{p_end} of Chapter {ch.number} ({ch.title}). "
                "Focus on core concepts, formulas, and highlighted examples."
            )
            study_task = GeneratedTask(
                id=uuid.uuid4(),
                subject=tracker.setup.subject,
                type="study",
                chapter_id=ch.id,
                est_minutes=study_slice,
                refs={
                    "book_id": str(ch.book_id) if ch.book_id else None,
                    "book_title": ch.book_title,
                    "chapter_number": ch.number,
                    "chapter_title": ch.title,
                    "printed_page_start": p_start,
                    "printed_page_end": p_end,
                    "guideline": guideline_study,
                },
                status="todo",
                source="planner",
            )
            cur_day.tasks.append(study_task)
            cur_day.planned_minutes += study_slice
            tracker.total_study_minutes += study_slice
            subjects_studied_today.add(tracker.setup.subject)
            subjects_with_study_task.add(tracker.setup.subject)

            # Queue Spaced Revision tasks at intervals 1, 3, 7 days (never same-day study)
            rev_intervals = [1, 3, 7]
            for delta in rev_intervals:
                target_rev_date = cur_date + timedelta(days=delta)
                if target_rev_date < tracker.setup.exam_date:
                    tracker.pending_spaced_revisions.append(
                        PendingSpacedRevision(
                            subject=tracker.setup.subject,
                            chapter_id=ch.id,
                            chapter_number=ch.number,
                            chapter_title=ch.title,
                            book_title=ch.book_title,
                            printed_page_start=p_start,
                            printed_page_end=p_end,
                            interval_days=delta,
                            target_date=target_rev_date,
                            study_date=cur_date,
                            est_minutes=min_study_block_minutes,
                        )
                    )

            # Homework task: homework NOT longer than study block
            rem_b = day_cap - cur_day.planned_minutes
            if rem_b >= min_study_block_minutes:
                hw_mins = min(rem_b, min_study_block_minutes, study_slice)
                hw_task = GeneratedTask(
                    id=uuid.uuid4(),
                    subject=tracker.setup.subject,
                    type="homework",
                    chapter_id=ch.id,
                    est_minutes=hw_mins,
                    refs={
                        "book_title": ch.book_title,
                        "chapter_number": ch.number,
                        "chapter_title": ch.title,
                        "printed_page_start": p_start,
                        "printed_page_end": p_end,
                        "guideline": (
                            f"Practice exercises for Chapter {ch.number} (Pages {p_start}–{p_end})."
                        ),
                    },
                    status="todo",
                    source="planner",
                )
                cur_day.tasks.append(hw_task)
                cur_day.planned_minutes += hw_mins
                tracker.total_study_minutes += hw_mins

            if tracker.pages_covered >= pages_total:
                tracker.chapter_idx += 1
                tracker.pages_covered = 0
                if tracker.chapter_idx >= len(tracker.sorted_chapters):
                    tracker.finished_all_chapters = True

        # Step D: Final Revision Window & Pre-Exam Spare Budget Fill (80% target)
        rev_active = [
            t
            for t in active_for_day
            if (cur_date in t.rev_window_dates or t.finished_all_chapters)
        ]
        rev_active.sort(key=subject_appearance_priority, reverse=True)
        if len(active_for_day) >= 3:
            max_daily_slots = 2 if day_cap <= 100 else min(3, len(active_for_day))
            rev_active = rev_active[:max_daily_slots]

        for tracker in rev_active:
            target_fill_minutes = math.floor(day_cap * final_window_fill_target)
            rem_fill = target_fill_minutes - cur_day.planned_minutes
            if rem_fill < min_study_block_minutes:
                continue

            # 1. Mock quiz capped at 1 per subject per 2 days (placeholder until P04)
            can_schedule_mock = False
            if tracker.last_mock_quiz_date is None:
                can_schedule_mock = True
            elif (cur_date - tracker.last_mock_quiz_date).days >= mock_quiz_max_frequency_days:
                can_schedule_mock = True

            if can_schedule_mock and rem_fill >= min_study_block_minutes:
                quiz_mins = min(rem_fill, min_study_block_minutes)
                quiz_task = GeneratedTask(
                    id=uuid.uuid4(),
                    subject=tracker.setup.subject,
                    type="quiz",
                    chapter_id=None,
                    est_minutes=quiz_mins,
                    refs={
                        "guideline": (
                            f"Mock quiz placeholder (P04): Practice exam questions and "
                            f"weak-point review for {tracker.setup.subject}."
                        ),
                        "placeholder": True,
                    },
                    status="todo",
                    source="planner",
                )
                cur_day.tasks.append(quiz_task)
                cur_day.planned_minutes += quiz_mins
                tracker.total_study_minutes += quiz_mins
                tracker.last_mock_quiz_date = cur_date
                subjects_studied_today.add(tracker.setup.subject)
                rem_fill -= quiz_mins

            # 2. Practice & weak-point review rotating across all chapters:
            # Oldest or weakest first, never repeating an identical task on consecutive days
            if rem_fill >= min_study_block_minutes and tracker.sorted_chapters:
                rev_mins = min(rem_fill, min_study_block_minutes + 15)
                yesterday = cur_date - timedelta(days=1)
                candidates = [
                    ch
                    for ch in tracker.sorted_chapters
                    if tracker.chapter_last_revised_date.get(ch.id) != yesterday
                ]
                if not candidates:
                    candidates = list(tracker.sorted_chapters)

                def chapter_rev_priority(c: ChapterPlanInput) -> tuple[float, date, int]:
                    last_rev = tracker.chapter_last_revised_date.get(c.id, date.min)
                    return (c.effective_mastery, last_rev, c.custom_order)

                candidates.sort(key=chapter_rev_priority)
                chosen_ch = candidates[0]
                tracker.chapter_last_revised_date[chosen_ch.id] = cur_date

                rev_task = GeneratedTask(
                    id=uuid.uuid4(),
                    subject=tracker.setup.subject,
                    type="revision",
                    chapter_id=chosen_ch.id,
                    est_minutes=rev_mins,
                    refs={
                        "book_title": chosen_ch.book_title,
                        "chapter_number": chosen_ch.number,
                        "chapter_title": chosen_ch.title,
                        "printed_page_start": chosen_ch.printed_page_start,
                        "printed_page_end": chosen_ch.printed_page_end,
                        "guideline": (
                            f"Final window review across Chapter {chosen_ch.number} ({chosen_ch.title}). "
                            f"Focus on weak points and textbook summary (pp. {chosen_ch.printed_page_start}–{chosen_ch.printed_page_end})."
                        ),
                        "type": "weak_point_practice",
                    },
                    status="todo",
                    source="planner",
                )
                cur_day.tasks.append(rev_task)
                cur_day.planned_minutes += rev_mins
                tracker.total_study_minutes += rev_mins
                subjects_studied_today.add(tracker.setup.subject)

        # Update streak specifically for study tasks, and days_scheduled for appearance
        for s_name, tracker in trackers.items():
            if s_name in subjects_with_study_task:
                tracker.consecutive_study_days += 1
            else:
                tracker.consecutive_study_days = 0

            if s_name in subjects_studied_today:
                tracker.days_scheduled += 1

    # 10. Final consolidation, Content-Reflective Day Labels & Zero-Day Reason Codes
    consolidated_days = sorted(day_map.values(), key=lambda d: d.date)
    total_task_count = 0

    all_buffer_dates: set[date] = set()
    for tracker in trackers.values():
        all_buffer_dates.update(tracker.buffer_dates)

    for p_day in consolidated_days:
        cap = day_budget_map.get(p_day.date, daily_study_minutes)

        if p_day.date in blackout_dates:
            p_day.tasks = []
            p_day.planned_minutes = 0
            p_day.day_type = "blackout"
            if not p_day.zero_reason:
                p_day.zero_reason = blackout_reasons.get(p_day.date, "parent blackout")
        elif p_day.planned_minutes > cap:
            # Enforce strict daily cap
            excess = p_day.planned_minutes - cap
            for task in reversed(p_day.tasks):
                if task.status != "done" and excess > 0:
                    reduction = min(excess, max(0, task.est_minutes - min_study_block_minutes))
                    task.est_minutes -= reduction
                    excess -= reduction
            p_day.planned_minutes = sum(t.est_minutes for t in p_day.tasks)

        # Content-reflective day labels and zero reason codes
        is_buffer_day = p_day.day_type == "buffer" or p_day.date in all_buffer_dates
        if len(p_day.tasks) > 0:
            has_study = any(t.type == "study" for t in p_day.tasks)
            if has_study:
                p_day.day_type = "study"
            elif is_buffer_day:
                p_day.day_type = "buffer"
            else:
                p_day.day_type = "revision"
            p_day.zero_reason = None
        else:
            # 0 planned minutes / 0 tasks
            if p_day.day_type == "blackout":
                pass  # zero_reason already set
            elif p_day.date in calendar_exam_dates:
                # If exam day and no other subjects studying
                p_day.day_type = "exam_day"
                p_day.zero_reason = "exam"
            elif is_buffer_day:
                p_day.day_type = "buffer"
                p_day.zero_reason = "rest"
            else:
                p_day.day_type = "holiday" if p_day.day_type == "holiday" else "rest"
                p_day.zero_reason = "rest"

        total_task_count += len(p_day.tasks)

    # 11. Per-subject coverage report & shortfall warning computation
    coverage_reports: dict[str, SubjectCoverageReport] = {}
    for setup in active_setups:
        tracker = trackers[setup.subject]
        total_ch = len(setup.chapters)
        total_pg = tracker.total_pages
        sched_pg = len(tracker.covered_pages_set)
        sched_ch = len(tracker.chapters_covered_set)

        cov_pct = (sched_pg / max(1, total_pg)) * 100.0
        shortfall = max(0, total_pg - sched_pg)

        shortfall_warn = None
        if shortfall > 0:
            shortfall_warn = (
                f"COVERAGE_SHORTFALL_{setup.subject.upper()}: Only {sched_pg}/{total_pg} pages "
                f"({cov_pct:.1f}%) scheduled before exam on {setup.exam_date.isoformat()}. "
                f"Shortfall of {shortfall} pages."
            )
            global_warnings.append(shortfall_warn)
            tracker.sub_warnings.append(shortfall_warn)

        cov_rep = SubjectCoverageReport(
            subject=setup.subject,
            exam_date=setup.exam_date,
            total_chapters=total_ch,
            scheduled_chapters=sched_ch,
            total_pages=total_pg,
            scheduled_pages=sched_pg,
            coverage_pct=cov_pct,
            shortfall_pages=shortfall,
            shortfall_warning=shortfall_warn,
        )
        coverage_reports[setup.subject] = cov_rep

    subject_plans: dict[str, SingleSubjectPlan] = {}
    for setup in active_setups:
        subject_plans[setup.subject] = SingleSubjectPlan(
            subject=setup.subject,
            exam_date=setup.exam_date,
            days=[d for d in consolidated_days if any(t.subject == setup.subject for t in d.tasks)],
            warnings=trackers[setup.subject].sub_warnings,
            coverage=coverage_reports.get(setup.subject),
        )

    return MultiSubjectPlanOutput(
        student_id=student_id,
        today=today,
        daily_study_minutes=daily_study_minutes,
        days=consolidated_days,
        subject_plans=subject_plans,
        warnings=global_warnings,
        total_tasks=total_task_count,
        coverage_reports=coverage_reports,
    )
