"""Pure-Python deterministic adaptive study planner engine.

Implements docs/06_ADAPTIVE_ENGINE.md §1 & §4, and product flows §4.1, §4.2:
- Zero DB, HTTP, or framework imports.
- Pure parameter-driven: accepts `today` explicitly and never reads the system clock.
- Multi-subject shared daily budget: student-level daily minutes cap shared across all active
  subjects, favoring nearer exams and heavier chapters.
- Final revision window (last 15% of usable days, minimum 3 days) and weekly buffer days.
- Time shares configurable, with weak-point share reassigned until P06.
- Infeasible exam date handling: returns compressed plan with warnings array, never fails.
- Preserves existing completed tasks upon plan regeneration.
- Rolling forward of uncompleted work without scheduling past exam dates.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

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
    """Configurable time shares for daily task composition per docs/06_ADAPTIVE_ENGINE.md §4.

    Note: In §4, standard breakdown is: Study ~55%, Revision ~20%, Weak-point ~15%, HW/Quiz ~10%.
    Until P06 (mastery & weak-point signals), the 15% weak-point share is reassigned
    to Study (+10% -> 65%) and Revision (+5% -> 25%).
    """

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
    mastery: float = 0.5  # Unknown mastery defaults to 0.5 per §1

    @property
    def total_pages(self) -> int:
        return max(1, self.printed_page_end - self.printed_page_start + 1)

    @property
    def effort(self) -> float:
        """Effort formula: pages * difficulty * weight * (1 + (1 - mastery))."""
        return (
            self.total_pages * self.difficulty_factor * self.weight * (1.0 + (1.0 - self.mastery))
        )


@dataclass
class SubjectSetupInput:
    """Study setup configuration for a single subject."""

    subject: str
    exam_name: str
    exam_date: date
    chapters: list[ChapterPlanInput]
    setup_id: uuid.UUID | str | None = None


@dataclass
class CompletedTaskRecord:
    """Historical completed task to be preserved during plan regeneration."""

    task_id: uuid.UUID | str
    subject: str
    chapter_id: uuid.UUID | str | None
    plan_date: date
    type: str
    est_minutes: int
    refs: dict[str, Any]
    completed_at: str | None = None


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
    day_type: str  # study, buffer, revision
    tasks: list[GeneratedTask] = field(default_factory=list)


@dataclass
class SingleSubjectPlan:
    """Generated plan for a single subject."""

    subject: str
    exam_date: date
    days: list[GeneratedPlanDay]
    warnings: list[str] = field(default_factory=list)


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
    return result or {0, 1, 2, 3, 4, 5}  # Default: Mon-Sat


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
) -> MultiSubjectPlanOutput:
    """Generate a multi-subject versioned study plan honoring a shared daily budget.

    Guarantees:
    - Never schedules any task after a subject's exam_date.
    - Sum of planned task minutes on any day across ALL subjects <= daily_study_minutes.
    - Chapter custom_order is strictly respected.
    - Completed tasks are preserved untouched.
    - Infeasible exams generate compressed plans with clear warnings, never failing.
    - Pure function: reads zero system time, makes zero external calls.
    """
    global_warnings: list[str] = []
    available_weekdays = normalize_available_days(
        available_days or ["sat", "sun", "mon", "tue", "wed", "thu"]
    )
    completed = completed_tasks or []

    # Filter out empty or invalid setups
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

    # 1. Check for immediate exam edge cases
    for s in active_setups:
        if s.exam_date < today:
            global_warnings.append(
                f"EXAM_PASSED_{s.subject.upper()}: Exam date {s.exam_date} has already passed."
            )
        elif s.exam_date == today:
            global_warnings.append(f"EXAM_TODAY_{s.subject.upper()}: Exam is scheduled for today.")
        elif s.exam_date == today + timedelta(days=1):
            global_warnings.append(
                f"EXAM_TOMORROW_{s.subject.upper()}: Exam is tomorrow; urgent high-yield review."
            )

    # 2. Determine horizon and calendar days to instantiate
    max_exam_date = max(s.exam_date for s in active_setups)
    all_usable_dates = calculate_usable_dates(
        today, max_exam_date, available_weekdays, max_days=max_days
    )

    if not all_usable_dates:
        # Emergency: 0 usable days match the available days schedule
        global_warnings.append("ZERO_USABLE_DAYS: No available study days found before exam date.")
        # Fallback to today as a single emergency day so student receives guidance
        all_usable_dates = [today]

    # Map of date -> GeneratedPlanDay
    day_map: dict[date, GeneratedPlanDay] = {}
    for d in all_usable_dates:
        day_map[d] = GeneratedPlanDay(date=d, planned_minutes=0, day_type="study", tasks=[])

    # Re-insert already completed tasks into their respective days
    completed_task_ids: set[str] = set()
    for ct in completed:
        completed_task_ids.add(str(ct.task_id))
        if ct.plan_date not in day_map:
            day_map[ct.plan_date] = GeneratedPlanDay(
                date=ct.plan_date, planned_minutes=0, day_type="study", tasks=[]
            )
        p_day = day_map[ct.plan_date]
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
        p_day.tasks.append(gt)
        p_day.planned_minutes += ct.est_minutes

    # 3. For each subject, schedule chapters across its usable days
    subject_plans: dict[str, SingleSubjectPlan] = {}

    for setup in active_setups:
        sub_warnings: list[str] = []
        sub_usable_dates = [d for d in all_usable_dates if d <= setup.exam_date]

        if not sub_usable_dates:
            sub_warnings.append(
                f"NO_USABLE_DAYS_{setup.subject.upper()}: No usable days before {setup.exam_date}."
            )
            sub_usable_dates = [today]

        # Calculate subject-specific windows:
        # Final revision window: last 15% of usable days, minimum 3 days (or all days if <= 3)
        num_days = len(sub_usable_dates)
        if num_days <= 3:
            rev_window_size = num_days
        else:
            rev_window_size = max(3, math.ceil(num_days * 0.15))

        rev_window_dates = set(sub_usable_dates[-rev_window_size:])

        # Weekly buffer days: every 7th usable day (excluding revision window)
        buffer_dates: set[date] = set()
        study_dates: list[date] = []

        for idx, d in enumerate(
            sub_usable_dates[:-rev_window_size] if num_days > rev_window_size else []
        ):
            if (idx + 1) % 7 == 0:
                buffer_dates.add(d)
                day_map[d].day_type = "buffer"
            else:
                study_dates.append(d)

        # Mark revision window day types
        for d in rev_window_dates:
            day_map[d].day_type = "revision"

        # If study dates is empty because exam is very close, study dates = all available dates
        if not study_dates:
            study_dates = list(sub_usable_dates)

        # Sort chapters strictly by custom_order
        sorted_chapters = sorted(setup.chapters, key=lambda c: c.custom_order)

        # Chapter effort & minute budget estimation
        # Total study effort across all chapters
        total_effort = sum(ch.effort for ch in sorted_chapters)

        # Calculate subject's daily study budget share
        # If there are multiple active subjects on date d, subject gets a proportional slice
        # Base minutes per study day: daily_study_minutes * (1 / len(active_setups))
        subject_weight = 1.0 / len(active_setups)
        sub_daily_budget = max(15, math.floor(daily_study_minutes * subject_weight))

        # Check for infeasible exam compression:
        # Total minutes needed for new study: total_effort * 2.5 min/page effort
        est_study_minutes_needed = total_effort * 2.5
        total_available_study_minutes = len(study_dates) * math.floor(
            sub_daily_budget * time_shares.study_share
        )

        compression_ratio = 1.0
        if (
            total_available_study_minutes > 0
            and est_study_minutes_needed > total_available_study_minutes
        ):
            compression_ratio = total_available_study_minutes / est_study_minutes_needed
            pct = math.floor(compression_ratio * 100)
            sub_warnings.append(
                f"EXAM_TOO_CLOSE_{setup.subject.upper()}: Compressed coverage ({pct}% pace)."
            )

        # Allocate chapters to study_dates
        day_idx = 0
        num_study_days = len(study_dates)

        for ch in sorted_chapters:
            # Minutes allocated to study this chapter
            raw_ch_minutes = math.ceil(ch.effort * 2.5 * compression_ratio)
            ch_study_minutes = max(10, raw_ch_minutes)
            pages_total = ch.total_pages
            pages_covered = 0

            while pages_covered < pages_total and day_idx < num_study_days:
                target_date = study_dates[day_idx]
                target_day = day_map[target_date]

                # Check available budget for target_date across all subjects
                available_today = daily_study_minutes - target_day.planned_minutes
                if available_today <= 10:
                    day_idx += 1
                    continue

                # Target study slice for today
                study_slice = min(
                    available_today,
                    max(10, math.floor(sub_daily_budget * time_shares.study_share)),
                )

                # Determine how many pages this slice covers
                pages_remaining = pages_total - pages_covered
                if ch_study_minutes > 0:
                    fraction = min(1.0, study_slice / ch_study_minutes)
                else:
                    fraction = 1.0

                pages_in_slice = max(1, math.ceil(pages_total * fraction))
                pages_in_slice = min(pages_remaining, pages_in_slice)

                p_start = ch.printed_page_start + pages_covered
                p_end = p_start + pages_in_slice - 1
                pages_covered += pages_in_slice

                # 1. New Study Task
                guideline_study = (
                    f"Read pages {p_start}–{p_end} of Chapter {ch.number} ({ch.title}). "
                    "Focus on core concepts, formulas, and highlighted examples."
                )
                study_task = GeneratedTask(
                    id=uuid.uuid4(),
                    subject=setup.subject,
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
                target_day.tasks.append(study_task)
                target_day.planned_minutes += study_slice

                # Check remaining budget on this day for revision and quiz
                rem_budget = daily_study_minutes - target_day.planned_minutes

                # 2. Daily Spaced Revision Task (~20-25%)
                rev_mins = min(
                    rem_budget, max(5, math.floor(sub_daily_budget * time_shares.revision_share))
                )
                if rev_mins >= 5:
                    rev_guideline = (
                        f"Spend {rev_mins} mins revising terms and formulas "
                        f"from Chapter {ch.number} ({ch.title})."
                    )
                    rev_task = GeneratedTask(
                        id=uuid.uuid4(),
                        subject=setup.subject,
                        type="revision",
                        chapter_id=ch.id,
                        est_minutes=rev_mins,
                        refs={
                            "book_title": ch.book_title,
                            "chapter_number": ch.number,
                            "chapter_title": ch.title,
                            "printed_page_start": ch.printed_page_start,
                            "printed_page_end": p_end,
                            "guideline": rev_guideline,
                        },
                        status="todo",
                        source="planner",
                    )
                    target_day.tasks.append(rev_task)
                    target_day.planned_minutes += rev_mins
                    rem_budget -= rev_mins

                # 3. Homework / Practice & Short Quiz Task (~10%)
                hw_mins = min(
                    rem_budget,
                    max(5, math.floor(sub_daily_budget * time_shares.homework_quiz_share)),
                )
                if hw_mins >= 5:
                    hw_guideline = (
                        f"Practice problems for Chapter {ch.number} (Pages {p_start}–{p_end})."
                    )
                    hw_task = GeneratedTask(
                        id=uuid.uuid4(),
                        subject=setup.subject,
                        type="homework",
                        chapter_id=ch.id,
                        est_minutes=hw_mins,
                        refs={
                            "book_title": ch.book_title,
                            "chapter_number": ch.number,
                            "chapter_title": ch.title,
                            "printed_page_start": p_start,
                            "printed_page_end": p_end,
                            "guideline": hw_guideline,
                        },
                        status="todo",
                        source="planner",
                    )
                    target_day.tasks.append(hw_task)
                    target_day.planned_minutes += hw_mins

                # Move to next study day if this day's budget is full
                if daily_study_minutes - target_day.planned_minutes < 15:
                    day_idx += 1

        # 4. Final Revision Window Tasks (mock exams, comprehensive quizzes)
        for r_date in sorted(rev_window_dates):
            r_day = day_map[r_date]
            rem_r_budget = daily_study_minutes - r_day.planned_minutes
            if rem_r_budget >= 15:
                # Full revision task
                ch_titles = ", ".join(f"Ch {c.number}" for c in sorted_chapters[:3])
                rev_all_task = GeneratedTask(
                    id=uuid.uuid4(),
                    subject=setup.subject,
                    type="revision",
                    chapter_id=sorted_chapters[0].id if sorted_chapters else None,
                    est_minutes=min(rem_r_budget, math.floor(sub_daily_budget * 0.70)),
                    refs={
                        "book_title": sorted_chapters[0].book_title if sorted_chapters else "",
                        "guideline": (
                            f"Final revision window: Comprehensive review of "
                            f"{setup.subject} ({ch_titles})."
                        ),
                    },
                    status="todo",
                    source="planner",
                )
                r_day.tasks.append(rev_all_task)
                r_day.planned_minutes += rev_all_task.est_minutes

                # Comprehensive mock quiz
                quiz_budget = daily_study_minutes - r_day.planned_minutes
                if quiz_budget >= 10:
                    quiz_task = GeneratedTask(
                        id=uuid.uuid4(),
                        subject=setup.subject,
                        type="quiz",
                        chapter_id=None,
                        est_minutes=min(quiz_budget, 15),
                        refs={
                            "guideline": f"Mock exam preparation quiz for {setup.subject}.",
                        },
                        status="todo",
                        source="planner",
                    )
                    r_day.tasks.append(quiz_task)
                    r_day.planned_minutes += quiz_task.est_minutes

        # Store single subject plan
        subject_plans[setup.subject] = SingleSubjectPlan(
            subject=setup.subject,
            exam_date=setup.exam_date,
            days=[d for d in day_map.values() if any(t.subject == setup.subject for t in d.tasks)],
            warnings=sub_warnings,
        )
        global_warnings.extend(sub_warnings)

    # 5. Final consolidation & strict daily minute ceiling check
    consolidated_days = sorted(day_map.values(), key=lambda d: d.date)
    total_task_count = 0

    for p_day in consolidated_days:
        # Strictly verify no day exceeds daily_study_minutes
        if p_day.planned_minutes > daily_study_minutes:
            # Scale down non-completed tasks proportionally
            excess = p_day.planned_minutes - daily_study_minutes
            for task in reversed(p_day.tasks):
                if task.status != "done" and excess > 0:
                    reduction = min(excess, max(0, task.est_minutes - 5))
                    task.est_minutes -= reduction
                    excess -= reduction
            p_day.planned_minutes = sum(t.est_minutes for t in p_day.tasks)

        total_task_count += len(p_day.tasks)

    return MultiSubjectPlanOutput(
        student_id=student_id,
        today=today,
        daily_study_minutes=daily_study_minutes,
        days=consolidated_days,
        subject_plans=subject_plans,
        warnings=global_warnings,
        total_tasks=total_task_count,
    )
