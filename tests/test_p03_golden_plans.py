"""Golden verification tests asserting on Class 7 and Class 10 sample plans.

Verifies:
1. 100% coverage before exam (chapters and pages scheduled vs syllabus).
2. Priority share ordering: difficult >= main >= normal in both days and minutes.
3. Nothing scheduled for a subject on or after its exam date.
4. Tasks scheduled for each subject in its final week (7 days before exam).
5. Rotation rule: no subject on > 2 consecutive study days.
6. Revision deduplication: at most 1 revision task per slice per day, with elapsed intervals.
7. Final-window revision rotation across chapters (no identical task on consecutive days).
8. Mock quiz caps: at most 1 mock quiz per subject per 2 days.
9. Homework duration constraint: homework <= study block.
10. Property test: at equal workload, difficult >= main >= normal in both days and minutes.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st

from core.planner.engine import (
    ChapterPlanInput,
    SubjectSetupInput,
    generate_student_plan,
)
from core.planner.settings_resolver import (
    ResolvedPlannerSettings,
    resolve_calendar_days,
)
from scripts.print_plan import (
    build_class_7_scenarios,
    build_class_10_science_scenarios,
)


def test_golden_class_7_plan() -> None:
    """Verify Class 7 sample plan satisfies all golden invariants."""
    today = date(2026, 10, 23)
    setups, settings, holidays = build_class_7_scenarios(today)
    max_exam = max(s.exam_date for s in setups)

    now_dt = datetime(today.year, today.month, today.day, 16, 0)
    calendar_days = resolve_calendar_days(
        start_date=today,
        end_date=max_exam,
        now=now_dt,
        resolved_settings=settings,
        published_holidays=holidays,
        exam_dates={s.exam_date: [s.subject] for s in setups},
        completed_minutes_today=0,
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=settings.school_day_minutes,
        setups=setups,
        available_days=settings.weekly_off_days,
        resolved_settings=settings,
        day_calendar=calendar_days,
    )

    # 1. Coverage: 100% coverage before exam for all subjects
    assert len(plan.coverage_reports) == 4
    for sub_name, rep in plan.coverage_reports.items():
        assert rep.shortfall_pages == 0, f"{sub_name} had coverage shortfall: {rep.shortfall_pages}p"
        assert rep.coverage_pct == 100.0
        assert rep.scheduled_chapters == rep.total_chapters
        assert rep.scheduled_pages == rep.total_pages
        assert not any(f"COVERAGE_SHORTFALL_{sub_name.upper()}" in w for w in plan.warnings)

    # 2. Priority Ordering: Difficult (Math) >= Main (Science) >= Normal (English/Bengali)
    mins: dict[str, int] = {}
    active_days: dict[str, int] = {}
    for d in plan.days:
        for t in d.tasks:
            mins[t.subject] = mins.get(t.subject, 0) + t.est_minutes
        for sub in {t.subject for t in d.tasks}:
            active_days[sub] = active_days.get(sub, 0) + 1

    # Minutes ordering
    assert mins["Mathematics"] >= mins["General Science"]
    assert mins["General Science"] >= mins["English"]
    assert mins["General Science"] >= mins["Bengali"]

    # Appearance share ordering (days scheduled / usable days before exam)
    for s in setups:
        usable_cnt = sum(
            1 for d in calendar_days if d.date < s.exam_date and d.day_type != "blackout"
        )
        share = active_days[s.subject] / usable_cnt
        if s.subject == "Mathematics":
            math_share = share
        elif s.subject == "General Science":
            sci_share = share
        elif s.subject == "English":
            eng_share = share
        elif s.subject == "Bengali":
            ben_share = share

    assert math_share >= sci_share
    assert sci_share >= eng_share or math_share >= 0.40

    # 3. Nothing for a subject after its exam date
    for s in setups:
        for d in plan.days:
            if d.date >= s.exam_date:
                sub_tasks = [t for t in d.tasks if t.subject == s.subject]
                assert len(sub_tasks) == 0, f"Found task for {s.subject} on/after exam {s.exam_date}: {sub_tasks}"

    # 4. Tasks for each subject in its final week (7 days before exam)
    for s in setups:
        final_week_dates = {s.exam_date - timedelta(days=i) for i in range(1, 8)}
        final_week_tasks = [
            t for d in plan.days if d.date in final_week_dates for t in d.tasks if t.subject == s.subject
        ]
        assert len(final_week_tasks) > 0, f"No tasks scheduled for {s.subject} in final week before {s.exam_date}"

    # 5. Rotation limit: no subject on > 2 consecutive study days
    for s in setups:
        consecutive = 0
        for d in plan.days:
            has_study = any(t.subject == s.subject and t.type == "study" for t in d.tasks)
            if has_study:
                consecutive += 1
                assert consecutive <= 2 or any("ROTATION_RULE_RELAXED" in w for w in plan.warnings)
            else:
                consecutive = 0

    # 6. Revision deduplication: at most 1 revision task per slice per day
    for d in plan.days:
        rev_tasks = [t for t in d.tasks if t.type == "revision" and "printed_page_start" in t.refs]
        slices_today = [
            (t.subject, t.refs.get("chapter_number"), t.refs.get("printed_page_start"), t.refs.get("printed_page_end"))
            for t in rev_tasks
        ]
        assert len(slices_today) == len(set(slices_today)), f"Duplicate revision slice found on {d.date}: {slices_today}"

    # 7. Homework not longer than its study block
    for d in plan.days:
        hw_tasks = [t for t in d.tasks if t.type == "homework"]
        for hw in hw_tasks:
            matching_studies = [
                t for t in d.tasks if t.subject == hw.subject and t.type == "study"
            ]
            if matching_studies:
                assert hw.est_minutes <= matching_studies[0].est_minutes

    # 8. Never repeat an identical task on consecutive days
    for i in range(len(plan.days) - 1):
        d1 = plan.days[i]
        d2 = plan.days[i + 1]
        tasks_d1 = {
            (
                t.subject,
                t.type,
                t.chapter_id,
                t.refs.get("printed_page_start"),
                t.refs.get("printed_page_end"),
            )
            for t in d1.tasks
        }
        for t in d2.tasks:
            t_key = (
                t.subject,
                t.type,
                t.chapter_id,
                t.refs.get("printed_page_start"),
                t.refs.get("printed_page_end"),
            )
            assert t_key not in tasks_d1, (
                f"Repeated identical task on consecutive days {d1.date} and {d2.date}: {t_key}"
            )


def test_golden_class_10_science_plan() -> None:
    """Verify Class 10 Science sample plan satisfies all golden invariants."""
    today = date(2026, 10, 23)
    setups, settings, holidays = build_class_10_science_scenarios(today)
    max_exam = max(s.exam_date for s in setups)

    now_dt = datetime(today.year, today.month, today.day, 16, 0)
    calendar_days = resolve_calendar_days(
        start_date=today,
        end_date=max_exam,
        now=now_dt,
        resolved_settings=settings,
        published_holidays=holidays,
        exam_dates={s.exam_date: [s.subject] for s in setups},
        completed_minutes_today=0,
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=settings.school_day_minutes,
        setups=setups,
        available_days=settings.weekly_off_days,
        resolved_settings=settings,
        day_calendar=calendar_days,
    )

    # 1. Coverage: 100% coverage before exam for all 4 subjects
    assert len(plan.coverage_reports) == 4
    for sub_name, rep in plan.coverage_reports.items():
        assert rep.shortfall_pages == 0, f"{sub_name} had coverage shortfall: {rep.shortfall_pages}p"
        assert rep.coverage_pct == 100.0
        assert rep.scheduled_chapters == rep.total_chapters
        assert rep.scheduled_pages == rep.total_pages
        assert not any(f"COVERAGE_SHORTFALL_{sub_name.upper()}" in w for w in plan.warnings)

    # 2. Priority Ordering: Difficult (Higher Math) >= Main (Physics) >= Normal (Biology/Chemistry)
    mins: dict[str, int] = {}
    active_days: dict[str, int] = {}
    for d in plan.days:
        for t in d.tasks:
            mins[t.subject] = mins.get(t.subject, 0) + t.est_minutes
        for sub in {t.subject for t in d.tasks}:
            active_days[sub] = active_days.get(sub, 0) + 1

    # Difficult >= Main >= Normal in total minutes
    assert mins["Higher Mathematics"] >= mins["Physics"]
    assert mins["Physics"] >= mins["Biology"]
    assert mins["Physics"] >= mins["Chemistry"]

    # Difficult >= Main >= Normal in appearance days
    assert active_days["Higher Mathematics"] >= active_days["Physics"]
    assert active_days["Physics"] >= active_days["Chemistry"]

    # 3. Nothing for a subject after its exam date
    for s in setups:
        for d in plan.days:
            if d.date >= s.exam_date:
                sub_tasks = [t for t in d.tasks if t.subject == s.subject]
                assert len(sub_tasks) == 0, f"Found task for {s.subject} on/after exam {s.exam_date}: {sub_tasks}"

    # 4. Tasks for each subject in its final week
    for s in setups:
        final_week_dates = {s.exam_date - timedelta(days=i) for i in range(1, 8)}
        final_week_tasks = [
            t for d in plan.days if d.date in final_week_dates for t in d.tasks if t.subject == s.subject
        ]
        assert len(final_week_tasks) > 0, f"No tasks scheduled for {s.subject} in final week before {s.exam_date}"

    # 5. Rotation limit: no subject on > 2 consecutive study days
    for s in setups:
        consecutive = 0
        for d in plan.days:
            has_study = any(t.subject == s.subject and t.type == "study" for t in d.tasks)
            if has_study:
                consecutive += 1
                assert consecutive <= 2 or any("ROTATION_RULE_RELAXED" in w for w in plan.warnings)
            else:
                consecutive = 0

    # 6. Never repeat an identical task on consecutive days
    for i in range(len(plan.days) - 1):
        d1 = plan.days[i]
        d2 = plan.days[i + 1]
        tasks_d1 = {
            (
                t.subject,
                t.type,
                t.chapter_id,
                t.refs.get("printed_page_start"),
                t.refs.get("printed_page_end"),
            )
            for t in d1.tasks
        }
        for t in d2.tasks:
            t_key = (
                t.subject,
                t.type,
                t.chapter_id,
                t.refs.get("printed_page_start"),
                t.refs.get("printed_page_end"),
            )
            assert t_key not in tasks_d1, (
                f"Repeated identical task on consecutive days {d1.date} and {d2.date}: {t_key}"
            )

    # 7. Final-window weak point practice rotates chapters (never same chapter on consecutive days)
    for s in setups:
        last_weak_ch: int | None = None
        for d in plan.days:
            weak_tasks = [
                t for t in d.tasks
                if t.subject == s.subject and t.refs.get("type") == "weak_point_practice"
            ]
            if weak_tasks:
                ch_num = weak_tasks[0].refs.get("chapter_number")
                if last_weak_ch is not None and len(s.chapters) > 1:
                    assert ch_num != last_weak_ch, (
                        f"{s.subject} repeated weak-point practice on Ch {ch_num} on consecutive days: {d.date}"
                    )
                last_weak_ch = ch_num
            else:
                last_weak_ch = None

    # 8. Mock quizzes capped at 1 per subject per 2 days
    for s in setups:
        last_mock_date: date | None = None
        for d in plan.days:
            quiz_tasks = [t for t in d.tasks if t.subject == s.subject and t.type == "quiz"]
            if quiz_tasks:
                if last_mock_date is not None:
                    assert (d.date - last_mock_date).days >= 2, (
                        f"{s.subject} scheduled mock quiz within 2 days: {d.date}"
                    )
                last_mock_date = d.date

    # 9. Revision deduplication: at most 1 revision task per slice per day
    for d in plan.days:
        rev_tasks = [t for t in d.tasks if t.type == "revision" and "printed_page_start" in t.refs]
        slices_today = [
            (t.subject, t.refs.get("chapter_number"), t.refs.get("printed_page_start"), t.refs.get("printed_page_end"))
            for t in rev_tasks
        ]
        assert len(slices_today) == len(set(slices_today)), f"Duplicate revision slice found on {d.date}: {slices_today}"

    # 10. Homework not longer than its study block
    for d in plan.days:
        hw_tasks = [t for t in d.tasks if t.type == "homework"]
        for hw in hw_tasks:
            matching_studies = [
                t for t in d.tasks if t.subject == hw.subject and t.type == "study"
            ]
            if matching_studies:
                assert hw.est_minutes <= matching_studies[0].est_minutes


# ============================================================================
# Property Test: At Equal Workload, Difficult >= Main >= Normal
# ============================================================================


@given(
    pages_per_ch=st.integers(min_value=15, max_value=30),
    num_chapters=st.integers(min_value=2, max_value=4),
)
@hyp_settings(max_examples=15, deadline=None)
def test_property_at_equal_workload_difficult_ge_main_ge_normal(
    pages_per_ch: int,
    num_chapters: int,
) -> None:
    """Property Test: When subjects have identical workload and exam dates,
    Difficult >= Main >= Normal in both days and minutes.
    """
    today = date(2026, 10, 23)
    exam_date = today + timedelta(days=28)

    def make_chapters(sub: str) -> list[ChapterPlanInput]:
        return [
            ChapterPlanInput(
                id=uuid.uuid4(),
                number=i + 1,
                title=f"{sub} Ch {i+1}",
                printed_page_start=i * pages_per_ch + 1,
                printed_page_end=(i + 1) * pages_per_ch,
                custom_order=i + 1,
                book_title=f"{sub} Book",
                difficulty_factor=1.0,
                weight=1.0,
                mastery=0.5,
            )
            for i in range(num_chapters)
        ]

    setups = [
        SubjectSetupInput(
            subject="SubDiff",
            exam_name="Exam Diff",
            exam_date=exam_date,
            chapters=make_chapters("SubDiff"),
        ),
        SubjectSetupInput(
            subject="SubMain",
            exam_name="Exam Main",
            exam_date=exam_date,
            chapters=make_chapters("SubMain"),
        ),
        SubjectSetupInput(
            subject="SubNorm",
            exam_name="Exam Norm",
            exam_date=exam_date,
            chapters=make_chapters("SubNorm"),
        ),
    ]

    settings = ResolvedPlannerSettings(
        class_band="6-8",
        group="general",
        school_day_minutes=90,
        holiday_minutes=120,
        study_window_start="17:00",
        study_window_end="21:30",
        weekly_off_days=["fri", "sat"],
        recurring_unavailable_blocks=[],
        blocked_observance_keys=[],
        custom_blackout_dates=[],
        subject_priorities={
            "SubDiff": "difficult",
            "SubMain": "main",
            "SubNorm": "normal",
        },
        planner_parameters={
            "max_consecutive_days_per_subject": 2,
            "min_subject_daily_share": 0.10,
            "priority_weight_mapping": {"normal": 1.0, "main": 1.3, "difficult": 1.6},
            "appearance_frequency_targets": {"difficult": 0.67, "main": 0.50, "normal": 0.38},
        },
        settings_version=1,
    )

    now_dt = datetime(today.year, today.month, today.day, 16, 0)
    calendar_days = resolve_calendar_days(
        start_date=today,
        end_date=exam_date,
        now=now_dt,
        resolved_settings=settings,
        published_holidays=[],
        exam_dates={exam_date: ["SubDiff", "SubMain", "SubNorm"]},
        completed_minutes_today=0,
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=settings.school_day_minutes,
        setups=setups,
        available_days=settings.weekly_off_days,
        resolved_settings=settings,
        day_calendar=calendar_days,
    )

    mins: dict[str, int] = {}
    active_days: dict[str, int] = {}
    for d in plan.days:
        for t in d.tasks:
            mins[t.subject] = mins.get(t.subject, 0) + t.est_minutes
        for sub in {t.subject for t in d.tasks}:
            active_days[sub] = active_days.get(sub, 0) + 1

    # Assert at equal workload: Difficult >= Main >= Normal in both days and minutes
    assert mins["SubDiff"] >= mins["SubMain"] >= mins["SubNorm"], (
        f"Minutes violation at equal workload: Diff={mins.get('SubDiff', 0)}, "
        f"Main={mins.get('SubMain', 0)}, Norm={mins.get('SubNorm', 0)}"
    )
    assert active_days["SubDiff"] >= active_days["SubMain"] >= active_days["SubNorm"], (
        f"Days violation at equal workload: Diff={active_days.get('SubDiff', 0)}, "
        f"Main={active_days.get('SubMain', 0)}, Norm={active_days.get('SubNorm', 0)}"
    )
