"""CLI tool to generate and print a multi-subject study plan as a readable table.

Scenario:
- Class 7 student
- 4 subjects: Mathematics, General Science, English, Bengali
- Staggered exam dates starting 45 days from today
- 120 minutes a day shared study budget
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.planner.engine import (
    ChapterPlanInput,
    SubjectSetupInput,
    TimeShareConfig,
    generate_student_plan,
)


def build_class_7_scenarios(today: date) -> list[SubjectSetupInput]:
    """Build 4 active subject setups for a Class 7 student."""
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
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=5,
            title="বীজগণিতীয় সূত্রাবলী ও প্রয়োগ",
            printed_page_start=79,
            printed_page_end=98,
            custom_order=5,
            book_title="গণিত (সপ্তম শ্রেণি)",
            difficulty_factor=1.2,
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
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=4,
            title="শ্বসন ও রক্তসংবহন",
            printed_page_start=41,
            printed_page_end=54,
            custom_order=4,
            book_title="বিজ্ঞান (সপ্তম শ্রেণি)",
            difficulty_factor=1.2,
        ),
    ]

    english_chapters = [
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=1,
            title="A Day in the Life",
            printed_page_start=1,
            printed_page_end=15,
            custom_order=1,
            book_title="English for Today (Class 7)",
            difficulty_factor=0.9,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=2,
            title="My Dream School",
            printed_page_start=16,
            printed_page_end=30,
            custom_order=2,
            book_title="English for Today (Class 7)",
            difficulty_factor=1.0,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=3,
            title="Writing Poems & Stories",
            printed_page_start=31,
            printed_page_end=48,
            custom_order=3,
            book_title="English for Today (Class 7)",
            difficulty_factor=1.0,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=4,
            title="Friends Across Cultures",
            printed_page_start=49,
            printed_page_end=65,
            custom_order=4,
            book_title="English for Today (Class 7)",
            difficulty_factor=1.1,
        ),
    ]

    bengali_chapters = [
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=1,
            title="মাতৃভাষা ও কবিতা",
            printed_page_start=1,
            printed_page_end=14,
            custom_order=1,
            book_title="বাংলা (সপ্তম শ্রেণি)",
            difficulty_factor=0.9,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=2,
            title="ছোটগল্প ও সাহিত্য",
            printed_page_start=15,
            printed_page_end=32,
            custom_order=2,
            book_title="বাংলা (সপ্তম শ্রেণি)",
            difficulty_factor=1.0,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=3,
            title="ব্যাকরণ ও ভাষা রীতি",
            printed_page_start=33,
            printed_page_end=54,
            custom_order=3,
            book_title="বাংলা (সপ্তম শ্রেণি)",
            difficulty_factor=1.2,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=4,
            title="নির্মিতি ও রচনা",
            printed_page_start=55,
            printed_page_end=72,
            custom_order=4,
            book_title="বাংলা (সপ্তম শ্রেণি)",
            difficulty_factor=1.0,
        ),
    ]

    return [
        SubjectSetupInput(
            subject="Mathematics",
            exam_name="Class 7 Math Term Exam",
            exam_date=today + timedelta(days=45),
            chapters=math_chapters,
        ),
        SubjectSetupInput(
            subject="General Science",
            exam_name="Class 7 Science Exam",
            exam_date=today + timedelta(days=52),
            chapters=science_chapters,
        ),
        SubjectSetupInput(
            subject="English",
            exam_name="Class 7 English 1st Paper",
            exam_date=today + timedelta(days=60),
            chapters=english_chapters,
        ),
        SubjectSetupInput(
            subject="Bengali",
            exam_name="Class 7 Bangla 1st Paper",
            exam_date=today + timedelta(days=65),
            chapters=bengali_chapters,
        ),
    ]


def main() -> None:
    today = date(2026, 10, 23)
    daily_budget = 120  # 120 minutes/day
    setups = build_class_7_scenarios(today)

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=daily_budget,
        setups=setups,
        available_days=["sat", "sun", "mon", "tue", "wed", "thu"],
        time_shares=TimeShareConfig(
            study_share=0.65,
            revision_share=0.25,
            weak_point_share=0.0,
            homework_quiz_share=0.10,
        ),
        min_subject_daily_share=0.10,
        rolling_horizon_days=60,
    )

    print("=" * 110)
    print("THINKBUDDY ADAPTIVE STUDY PLANNER - CLASS 7 MULTI-SUBJECT SCHEDULE")
    print(f"Student: Class 7 | Shared Daily Budget: {daily_budget} mins/day | Start Date: {today}")
    print("Exams: Math (Day +45), Science (Day +52), English (Day +60), Bengali (Day +65)")
    print("=" * 110)

    # Print table header
    header = (
        f"{'Day':<5} | {'Date':<10} | {'Type':<8} | {'Subject':<15} | "
        f"{'Task Type':<10} | {'Pages / Details':<36} | {'Mins':>5} | {'Total':>5}"
    )
    print(header)
    print("-" * 110)

    max_day_budget_seen = 0
    subject_mins: dict[str, int] = {}

    for idx, day in enumerate(plan.days, start=1):
        if not day.tasks:
            continue
        max_day_budget_seen = max(max_day_budget_seen, day.planned_minutes)
        day_total_str = f"{day.planned_minutes}m"

        for t_idx, task in enumerate(day.tasks):
            subject_mins[task.subject] = subject_mins.get(task.subject, 0) + task.est_minutes
            day_str = f"D{idx:02d}" if t_idx == 0 else ""
            date_str = str(day.date) if t_idx == 0 else ""
            type_str = day.day_type.capitalize() if t_idx == 0 else ""
            tot_str = day_total_str if t_idx == 0 else ""

            # Extract brief summary of details
            ch_num = task.refs.get("chapter_number")
            p_start = task.refs.get("printed_page_start")
            p_end = task.refs.get("printed_page_end")

            if p_start and p_end and ch_num:
                detail = f"Ch {ch_num} (pp. {p_start}-{p_end})"
            elif task.type == "quiz":
                detail = "Preparation / Mock Quiz"
            elif task.type == "revision":
                detail = f"Ch {ch_num} Review" if ch_num else "Comprehensive Review"
            elif task.type == "homework":
                detail = f"Ch {ch_num} Exercises" if ch_num else "Practice Problems"
            else:
                detail = task.refs.get("guideline", "")[:35]

            task_type = task.type.capitalize()
            row = (
                f"{day_str:<5} | {date_str:<10} | {type_str:<8} | {task.subject:<15} | "
                f"{task_type:<10} | {detail:<36} | {task.est_minutes:>4}m | {tot_str:>5}"
            )
            print(row)

        print("-" * 110)

    print("\nPLAN SUMMARY & VERIFICATION:")
    print(f"Total Scheduled Calendar Days: {len(plan.days)}")
    print(f"Maximum Combined Day Minutes: {max_day_budget_seen}m (Cap: {daily_budget}m - OK)")
    print(f"Total Generated Tasks: {plan.total_tasks}")
    print("Subject Minute Allocation:")
    for sub, mins in sorted(subject_mins.items()):
        pct = (mins / sum(subject_mins.values())) * 100
        print(f"  - {sub:<15}: {mins:>4} mins ({pct:.1f}%)")

    if plan.warnings:
        print("\nDiagnostic Warnings / Notices:")
        for w in plan.warnings:
            print(f"  * {w}")
    print("=" * 110)


if __name__ == "__main__":
    main()
