"""CLI tool to generate and print full, unabbreviated multi-subject study plans.

Implements Requirement E.16:
- Class 7 Student (General)
- Class 10 Science Student (Physics, Chemistry, Biology, Higher Math)
- Demonstrates Planner v2:
  * Dynamic configuration layer (3-tier resolution)
  * Day types: school_day, holiday (Fri/Sat off days as study days), blackout, exam_day
  * Priority weight mappings (normal: 1.0, main: 1.3, difficult: 1.6)
  * Rotation rule: <= 2 consecutive study days per subject when >= 3 subjects active
  * Today's remaining budget formula
  * Full unabbreviated printing (no "...")
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.auth.models  # noqa: F401
import core.curriculum.models  # noqa: F401
from core.planner.engine import (
    ChapterPlanInput,
    SubjectSetupInput,
    TimeShareConfig,
    generate_student_plan,
)
from core.planner.models import Holiday
from core.planner.settings_resolver import (
    ResolvedPlannerSettings,
    resolve_calendar_days,
)


def build_class_7_scenarios(
    today: date,
) -> tuple[list[SubjectSetupInput], ResolvedPlannerSettings, list[Holiday]]:
    """Build active setups and resolved settings for a Class 7 student."""
    math_chapters = [
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=1,
            title="মূলদ ও অমূলদ সংখ্যা",
            printed_page_start=1,
            printed_page_end=18,
            custom_order=1,
            book_title="গণিত (সপ্তম শ্রেণি)",
            difficulty_factor=1.2,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=2,
            title="সমানুপাত ও লাভ-ক্ষতি",
            printed_page_start=19,
            printed_page_end=38,
            custom_order=2,
            book_title="গণিত (সপ্তম শ্রেণি)",
            difficulty_factor=1.0,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=3,
            title="পরিমাপ",
            printed_page_start=39,
            printed_page_end=55,
            custom_order=3,
            book_title="গণিত (সপ্তম শ্রেণি)",
            difficulty_factor=1.1,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=4,
            title="বীজগণিতীয় রাশির গুণ ও ভাগ",
            printed_page_start=56,
            printed_page_end=78,
            custom_order=4,
            book_title="গণিত (সপ্তম শ্রেণি)",
            difficulty_factor=1.3,
        ),
    ]

    science_chapters = [
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=1,
            title="নিম্নশ্রেণির জীব",
            printed_page_start=1,
            printed_page_end=12,
            custom_order=1,
            book_title="বিজ্ঞান (সপ্তম শ্রেণি)",
            difficulty_factor=1.0,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=2,
            title="উদ্ভিদ ও প্রাণীর কোষীয় সংগঠন",
            printed_page_start=13,
            printed_page_end=26,
            custom_order=2,
            book_title="বিজ্ঞান (সপ্তম শ্রেণি)",
            difficulty_factor=1.1,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=3,
            title="উদ্ভিদের বাহ্যিক বৈশিষ্ট্য",
            printed_page_start=27,
            printed_page_end=40,
            custom_order=3,
            book_title="বিজ্ঞান (সপ্তম শ্রেণি)",
            difficulty_factor=1.0,
        ),
    ]

    english_chapters = [
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=1,
            title="Unit 1: Attention, please!",
            printed_page_start=1,
            printed_page_end=10,
            custom_order=1,
            book_title="English for Today (Class 7)",
            difficulty_factor=0.9,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=2,
            title="Unit 2: My study guide",
            printed_page_start=11,
            printed_page_end=22,
            custom_order=2,
            book_title="English for Today (Class 7)",
            difficulty_factor=1.0,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=3,
            title="Unit 3: What are friends for?",
            printed_page_start=23,
            printed_page_end=35,
            custom_order=3,
            book_title="English for Today (Class 7)",
            difficulty_factor=0.9,
        ),
    ]

    bengali_chapters = [
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=1,
            title="কাবুলিওয়ালা (গল্প)",
            printed_page_start=1,
            printed_page_end=10,
            custom_order=1,
            book_title="সপ্তবর্ণা (সপ্তম শ্রেণি)",
            difficulty_factor=0.9,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=2,
            title="কুলি-মজুর (কবিতা)",
            printed_page_start=11,
            printed_page_end=18,
            custom_order=2,
            book_title="সপ্তবর্ণা (সপ্তম শ্রেণি)",
            difficulty_factor=0.9,
        ),
    ]

    setups = [
        SubjectSetupInput(
            subject="Mathematics",
            exam_name="Class 7 Math Midterm",
            exam_date=today + timedelta(days=28),
            chapters=math_chapters,
        ),
        SubjectSetupInput(
            subject="General Science",
            exam_name="Class 7 Science Midterm",
            exam_date=today + timedelta(days=32),
            chapters=science_chapters,
        ),
        SubjectSetupInput(
            subject="English",
            exam_name="Class 7 English Midterm",
            exam_date=today + timedelta(days=35),
            chapters=english_chapters,
        ),
        SubjectSetupInput(
            subject="Bengali",
            exam_name="Class 7 Bangla Midterm",
            exam_date=today + timedelta(days=38),
            chapters=bengali_chapters,
        ),
    ]

    settings = ResolvedPlannerSettings(
        class_band="6-8",
        group="general",
        school_day_minutes=75,
        holiday_minutes=120,
        study_window_start="17:00",
        study_window_end="21:30",
        weekly_off_days=["fri", "sat"],
        recurring_unavailable_blocks=[],
        blocked_observance_keys=[],
        custom_blackout_dates=[
            {
                "start_date": str(today + timedelta(days=12)),
                "end_date": str(today + timedelta(days=12)),
                "reason": "family_event",
            }
        ],
        subject_priorities={
            "Mathematics": "difficult",
            "General Science": "main",
            "English": "normal",
            "Bengali": "normal",
        },
        planner_parameters={
            "max_consecutive_days_per_subject": 2,
            "min_subject_daily_share": 0.10,
            "priority_weight_mapping": {"normal": 1.0, "main": 1.3, "difficult": 1.6},
        },
        recommended_daily_minutes=90,
        settings_version=2,
    )

    holidays = [
        Holiday(
            start_date=today + timedelta(days=18),
            end_date=today + timedelta(days=18),
            name="National Martyrs Day",
            holiday_type="national",
            study_blackout=True,
            verified=True,
            status="published",
        )
    ]

    return setups, settings, holidays


def build_class_10_science_scenarios(
    today: date,
) -> tuple[list[SubjectSetupInput], ResolvedPlannerSettings, list[Holiday]]:
    """Build active setups and resolved settings for a Class 10 Science student."""
    physics_chapters = [
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=1,
            title="ভৌত রাশি ও পরিমাপ",
            printed_page_start=1,
            printed_page_end=22,
            custom_order=1,
            book_title="পদার্থবিজ্ঞান (নবম-দশম)",
            difficulty_factor=1.1,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=2,
            title="গতি (Motion)",
            printed_page_start=23,
            printed_page_end=54,
            custom_order=2,
            book_title="পদার্থবিজ্ঞান (নবম-দশম)",
            difficulty_factor=1.3,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=3,
            title="বল (Force & Newton's Laws)",
            printed_page_start=55,
            printed_page_end=88,
            custom_order=3,
            book_title="পদার্থবিজ্ঞান (নবম-দশম)",
            difficulty_factor=1.4,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=4,
            title="কাজ, ক্ষমতা ও শক্তি",
            printed_page_start=89,
            printed_page_end=120,
            custom_order=4,
            book_title="পদার্থবিজ্ঞান (নবম-দশম)",
            difficulty_factor=1.2,
        ),
    ]

    chemistry_chapters = [
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=1,
            title="রসায়নের ধারণা",
            printed_page_start=1,
            printed_page_end=16,
            custom_order=1,
            book_title="রসায়ন (নবম-দশম)",
            difficulty_factor=1.0,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=2,
            title="পদার্থের অবস্থা",
            printed_page_start=17,
            printed_page_end=36,
            custom_order=2,
            book_title="রসায়ন (নবম-দশম)",
            difficulty_factor=1.1,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=3,
            title="পদার্থের গঠন",
            printed_page_start=37,
            printed_page_end=62,
            custom_order=3,
            book_title="রসায়ন (নবম-দশম)",
            difficulty_factor=1.3,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=4,
            title="পর্যায় সারণি (Periodic Table)",
            printed_page_start=63,
            printed_page_end=94,
            custom_order=4,
            book_title="রসায়ন (নবম-দশম)",
            difficulty_factor=1.4,
        ),
    ]

    biology_chapters = [
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=1,
            title="জীবন পাঠ",
            printed_page_start=1,
            printed_page_end=18,
            custom_order=1,
            book_title="জীববিজ্ঞান (নবম-দশম)",
            difficulty_factor=0.9,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=2,
            title="জীবকোষ ও টিস্যু",
            printed_page_start=19,
            printed_page_end=48,
            custom_order=2,
            book_title="জীববিজ্ঞান (নবম-দশম)",
            difficulty_factor=1.2,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=3,
            title="কোষ বিভাজন",
            printed_page_start=49,
            printed_page_end=68,
            custom_order=3,
            book_title="জীববিজ্ঞান (নবম-দশম)",
            difficulty_factor=1.1,
        ),
    ]

    # Synthetic fixture data: Chapters 1, 2, 3, and 7 are synthetic fixture data
    # for testing non-contiguous custom chapter order. This chapter set is an arbitrary
    # fixture for test and visualization purposes; no claims are made regarding NCTB term structure.
    higher_math_chapters = [
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=1,
            title="সেট ও ফাংশন",
            printed_page_start=1,
            printed_page_end=28,
            custom_order=1,
            book_title="উচ্চতর গণিত (নবম-দশম)",
            difficulty_factor=1.3,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=2,
            title="বীজগাণিতিক রাশি",
            printed_page_start=29,
            printed_page_end=60,
            custom_order=2,
            book_title="উচ্চতর গণিত (নবম-দশম)",
            difficulty_factor=1.4,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=3,
            title="জ্যামিতি (অ্যাপোলোনিয়াসের উপপাদ্য)",
            printed_page_start=61,
            printed_page_end=88,
            custom_order=3,
            book_title="উচ্চতর গণিত (নবম-দশম)",
            difficulty_factor=1.5,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=7,
            title="অসীম ধারা (Infinite Series)",
            printed_page_start=130,
            printed_page_end=152,
            custom_order=4,
            book_title="উচ্চতর গণিত (নবম-দশম)",
            difficulty_factor=1.4,
        ),
    ]

    setups = [
        SubjectSetupInput(
            subject="Physics",
            exam_name="SSC Model Test - Physics",
            exam_date=today + timedelta(days=30),
            chapters=physics_chapters,
        ),
        SubjectSetupInput(
            subject="Chemistry",
            exam_name="SSC Model Test - Chemistry",
            exam_date=today + timedelta(days=34),
            chapters=chemistry_chapters,
        ),
        SubjectSetupInput(
            subject="Biology",
            exam_name="SSC Model Test - Biology",
            exam_date=today + timedelta(days=37),
            chapters=biology_chapters,
        ),
        SubjectSetupInput(
            subject="Higher Mathematics",
            exam_name="SSC Model Test - Higher Math",
            exam_date=today + timedelta(days=40),
            chapters=higher_math_chapters,
        ),
    ]

    settings = ResolvedPlannerSettings(
        class_band="9-10",
        group="science",
        school_day_minutes=150,
        holiday_minutes=210,
        study_window_start="16:30",
        study_window_end="22:00",
        weekly_off_days=["fri", "sat"],
        recurring_unavailable_blocks=[
            {
                "day_of_week": "mon",
                "start_time": "18:00",
                "end_time": "19:30",
                "label": "Physics/Math Coaching",
            },
            {
                "day_of_week": "wed",
                "start_time": "18:00",
                "end_time": "19:30",
                "label": "Chemistry Coaching",
            },
        ],
        blocked_observance_keys=[],
        custom_blackout_dates=[
            {
                "start_date": str(today + timedelta(days=15)),
                "end_date": str(today + timedelta(days=15)),
                "reason": "school_event",
            }
        ],
        subject_priorities={
            "Higher Mathematics": "difficult",
            "Physics": "main",
            "Chemistry": "normal",
            "Biology": "normal",
        },
        planner_parameters={
            "max_consecutive_days_per_subject": 2,
            "min_subject_daily_share": 0.10,
            "priority_weight_mapping": {"normal": 1.0, "main": 1.3, "difficult": 1.6},
        },
        recommended_daily_minutes=150,
        settings_version=3,
    )

    holidays = [
        Holiday(
            start_date=today + timedelta(days=21),
            end_date=today + timedelta(days=21),
            name="Public Blackout Day",
            holiday_type="national",
            study_blackout=True,
            verified=True,
            status="published",
        )
    ]

    return setups, settings, holidays


def build_stress_case_scenarios(
    today: date,
) -> tuple[list[SubjectSetupInput], ResolvedPlannerSettings, list[Holiday]]:
    """Build a stress-case scenario (exams in 20 days, large syllabus) triggering coverage shortfalls."""
    exam_date = today + timedelta(days=20)

    def make_large_subject_chapters(sub_name: str, total_chapters: int = 5, pages_per_ch: int = 50) -> list[ChapterPlanInput]:
        return [
            ChapterPlanInput(
                id=uuid.uuid4(),
                number=i,
                title=f"{sub_name} Chapter {i}",
                printed_page_start=(i - 1) * pages_per_ch + 1,
                printed_page_end=i * pages_per_ch,
                custom_order=i,
                book_title=f"{sub_name} Comprehensive Volume",
                difficulty_factor=1.2,
            )
            for i in range(1, total_chapters + 1)
        ]

    setups = [
        SubjectSetupInput(
            subject="Mathematics",
            exam_name="Term Final - Math",
            exam_date=exam_date,
            chapters=make_large_subject_chapters("Mathematics", total_chapters=6, pages_per_ch=50),  # 300 pages
        ),
        SubjectSetupInput(
            subject="Physics",
            exam_name="Term Final - Physics",
            exam_date=exam_date,
            chapters=make_large_subject_chapters("Physics", total_chapters=5, pages_per_ch=50),  # 250 pages
        ),
        SubjectSetupInput(
            subject="Chemistry",
            exam_name="Term Final - Chemistry",
            exam_date=exam_date,
            chapters=make_large_subject_chapters("Chemistry", total_chapters=5, pages_per_ch=50),  # 250 pages
        ),
        SubjectSetupInput(
            subject="Biology",
            exam_name="Term Final - Biology",
            exam_date=exam_date,
            chapters=make_large_subject_chapters("Biology", total_chapters=5, pages_per_ch=50),  # 250 pages
        ),
    ]

    settings = ResolvedPlannerSettings(
        class_band="9-10",
        group="science",
        school_day_minutes=75,
        holiday_minutes=90,
        study_window_start="18:00",
        study_window_end="21:30",
        weekly_off_days=["fri", "sat"],
        recurring_unavailable_blocks=[],
        blocked_observance_keys=[],
        custom_blackout_dates=[
            {
                "start_date": (today + timedelta(days=10)).isoformat(),
                "end_date": (today + timedelta(days=10)).isoformat(),
                "reason": "Family event",
            }
        ],
        subject_priorities={
            "Mathematics": "difficult",
            "Physics": "main",
            "Chemistry": "normal",
            "Biology": "normal",
        },
        planner_parameters={
            "max_consecutive_days_per_subject": 2,
            "min_subject_daily_share": 0.10,
            "priority_weight_mapping": {"normal": 1.0, "main": 1.3, "difficult": 1.6},
            "appearance_frequency_targets": {"difficult": 0.67, "main": 0.50, "normal": 0.38},
        },
        settings_version=1,
    )

    holidays = [
        Holiday(
            start_date=today + timedelta(days=10),
            end_date=today + timedelta(days=10),
            name="District Observance Day",
            holiday_type="district",
            study_blackout=True,
            verified=True,
            status="published",
        )
    ]

    return setups, settings, holidays


def print_complete_plan(
    title: str,
    today: date,
    setups: list[SubjectSetupInput],
    settings: ResolvedPlannerSettings,
    holidays: list[Holiday],
    output_path: str | None = None,
) -> None:
    """Generate and print the entire schedule without omission or truncation."""
    now_dt = datetime(today.year, today.month, today.day, 16, 0)
    max_exam = max(s.exam_date for s in setups)

    plan_warnings: list[str] = []
    # Build exam lookup mapping date to subject names
    exam_dates_map: dict[date, list[str]] = {}
    for s in setups:
        exam_dates_map.setdefault(s.exam_date, []).append(s.subject)

    day_calendar = resolve_calendar_days(
        start_date=today,
        end_date=max_exam,
        now=now_dt,
        resolved_settings=settings,
        published_holidays=holidays,
        exam_dates=exam_dates_map,
        completed_minutes_today=0,
        warnings=plan_warnings,
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=settings.school_day_minutes,
        setups=setups,
        available_days=["sat", "sun", "mon", "tue", "wed", "thu", "fri"],
        time_shares=TimeShareConfig(
            study_share=0.65,
            revision_share=0.25,
            weak_point_share=0.0,
            homework_quiz_share=0.10,
        ),
        min_subject_daily_share=0.10,
        rolling_horizon_days=60,
        resolved_settings=settings,
        day_calendar=day_calendar,
    )
    # Merge calendar warnings into plan warnings
    for pw in plan_warnings:
        if pw not in plan.warnings:
            plan.warnings.append(pw)

    output_lines: list[str] = []

    def out(line: str = "") -> None:
        print(line)
        output_lines.append(line)

    out("=" * 125)
    out(f"THINKBUDDY ADAPTIVE STUDY PLANNER V2 - {title}")
    out(
        f"Class Band: {settings.class_band} | Group: {settings.group} | "
        f"School Day: {settings.school_day_minutes}m | Holiday: {settings.holiday_minutes}m"
    )
    out(
        f"Study Window: {settings.study_window_start} - {settings.study_window_end} | "
        f"Weekly Off Days (Study Days): {settings.weekly_off_days}"
    )
    out(f"Priorities: {settings.subject_priorities}")
    out(f"Adaptive Mode: {settings.adaptive_mode}")
    out("=" * 125)

    header = (
        f"{'Day':<5} | {'Date':<10} | {'Day Type':<11} | {'Subject':<18} | "
        f"{'Task Type':<10} | {'Pages / Curriculum Ref':<38} | {'Mins':>5} | {'Day Total':>9}"
    )
    out(header)
    out("-" * 125)

    subject_minutes: dict[str, int] = {}
    total_study_days = 0
    zero_study_days = 0
    zero_study_reasons: dict[str, int] = {}

    for idx, day in enumerate(plan.days, start=1):
        day_str = f"D{idx:02d}"
        date_str = str(day.date)
        type_str = day.day_type.replace("_", " ").title()

        if not day.tasks or day.planned_minutes == 0:
            zero_study_days += 1
            z_reason = day.zero_reason or (
                "parent blackout" if day.day_type == "blackout" else "rest"
            )
            zero_study_reasons[z_reason] = zero_study_reasons.get(z_reason, 0) + 1
            reason_detail = f"Reason: {z_reason}"
            out(
                f"{day_str:<5} | {date_str:<10} | {type_str:<11} | {'[ZERO STUDY]':<18} | "
                f"{'-':<10} | {reason_detail:<38} | {0:>4}m | {0:>8}m"
            )
            out("-" * 125)
            continue

        total_study_days += 1
        day_total_str = f"{day.planned_minutes}m"

        for t_idx, task in enumerate(day.tasks):
            subject_minutes[task.subject] = subject_minutes.get(task.subject, 0) + task.est_minutes
            d_col = day_str if t_idx == 0 else ""
            dt_col = date_str if t_idx == 0 else ""
            tp_col = type_str if t_idx == 0 else ""
            tot_col = day_total_str if t_idx == 0 else ""

            ch_num = task.refs.get("chapter_number")
            p_start = task.refs.get("printed_page_start")
            p_end = task.refs.get("printed_page_end")
            spaced_d = task.refs.get("spaced_interval_days")

            if p_start and p_end and ch_num:
                if task.type == "revision" and spaced_d:
                    detail = f"Ch {ch_num} (pp. {p_start}-{p_end}) [Spaced +{spaced_d}d]"
                else:
                    detail = f"Ch {ch_num} (printed pp. {p_start}-{p_end})"
            elif task.type == "quiz":
                detail = f"Mock Test / Quiz {f'(Ch {ch_num})' if ch_num else '[Placeholder]'}"
            elif task.type == "revision":
                detail = f"Review & Practice {f'(Ch {ch_num})' if ch_num else ''}"
            elif task.type == "homework":
                detail = f"Exercise & HW {f'(Ch {ch_num})' if ch_num else ''}"
            else:
                detail = task.refs.get("guideline", "")[:36]

            row = (
                f"{d_col:<5} | {dt_col:<10} | {tp_col:<11} | {task.subject:<18} | "
                f"{task.type.capitalize():<10} | {detail:<38} | "
                f"{task.est_minutes:>4}m | {tot_col:>9}"
            )
            out(row)

        out("-" * 125)

    out("\nPLAN METRICS & VERIFICATION SUMMARY:")
    out(
        f"Total Calendar Days: {len(plan.days)} "
        f"(Active Study Days: {total_study_days}, Zero-Study Days: {zero_study_days})"
    )
    out(f"Zero-Study Day Breakdown: {zero_study_reasons}")
    out(f"Total Tasks Generated: {plan.total_tasks}")
    out("Subject Allocation & Priority Multiplier Effect:")
    total_mins = sum(subject_minutes.values())
    for sub, mins in sorted(subject_minutes.items(), key=lambda x: x[1], reverse=True):
        prio = settings.subject_priorities.get(sub, "normal")
        pct = (mins / total_mins * 100) if total_mins > 0 else 0
        days_cnt = sum(1 for d in plan.days if any(t.subject == sub for t in d.tasks))
        out(f"  * {sub:<18} [{prio.upper():<9}]: {mins:>4} mins ({pct:.1f}% share, {days_cnt} active days)")

    out("\nPER-SUBJECT SYLLABUS COVERAGE AUDIT (Before Exam):")
    out(f"  {'Subject':<18} | {'Exam Date':<10} | {'Chapters':<10} | {'Pages Covered':<16} | {'Coverage %':<10} | Status")
    out("  " + "-" * 85)
    for sub, rep in sorted(plan.coverage_reports.items()):
        status_str = "PASS (100%)" if rep.shortfall_pages == 0 else f"SHORTFALL (-{rep.shortfall_pages} pages)"
        out(
            f"  {sub:<18} | {rep.exam_date.isoformat():<10} | "
            f"{rep.scheduled_chapters}/{rep.total_chapters:<8} | "
            f"{rep.scheduled_pages}/{rep.total_pages:<14} | "
            f"{rep.coverage_pct:>8.1f}% | {status_str}"
        )

    if plan.warnings:
        out("\nDiagnostic Feedback & Warnings:")
        for w in plan.warnings:
            out(f"  [INFO] {w}")
    out("=" * 125)
    out("\n")

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(output_lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="Print complete study plans.")
    parser.add_argument(
        "--target",
        choices=["7", "10", "stress", "all"],
        default="all",
        help="Target student schedule to print (7, 10, stress, or all)",
    )
    args = parser.parse_args()

    today = date(2026, 10, 23)

    if args.target in ("7", "all"):
        c7_setups, c7_settings, c7_holidays = build_class_7_scenarios(today)
        print_complete_plan(
            title="CLASS 7 STUDENT (GENERAL) - 4 SUBJECT SCHEDULE",
            today=today,
            setups=c7_setups,
            settings=c7_settings,
            holidays=c7_holidays,
            output_path="reports/P03_class_7_schedule.txt",
        )

    if args.target in ("10", "all"):
        c10_setups, c10_settings, c10_holidays = build_class_10_science_scenarios(today)
        print_complete_plan(
            title="CLASS 10 SCIENCE STUDENT - PHYSICS, CHEMISTRY, BIOLOGY, HIGHER MATH",
            today=today,
            setups=c10_setups,
            settings=c10_settings,
            holidays=c10_holidays,
            output_path="reports/P03_class_10_science_schedule.txt",
        )

    if args.target in ("stress", "all"):
        stress_setups, stress_settings, stress_holidays = build_stress_case_scenarios(today)
        print_complete_plan(
            title="STRESS CASE (EXAM IN 20 DAYS, 1050 PAGES, 75M DAILY BUDGET)",
            today=today,
            setups=stress_setups,
            settings=stress_settings,
            holidays=stress_holidays,
            output_path="reports/P03_stress_case_schedule.txt",
        )


if __name__ == "__main__":
    main()
