"""Deterministic Study Time Allocation & Adaptive Revision Dataset Generator.

Computes balanced daily study time, spaced repetition revision slots, and subject focus
weights for all NCTB class, subject, and exam date combinations.
Distinguishes between new study chapters (unread) and revision chapters (already done).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any

from core.curriculum.nctb_subjects import (
    NCTBSubjectMeta,
    get_subjects_for_class_and_group,
)


@dataclass
class SubjectTimeAllocation:
    slug: str
    name_bn: str
    name_en: str
    total_chapters: int
    completed_chapters_count: int
    new_chapters_count: int
    weak_chapters_count: int
    is_stem: bool
    is_weak: bool
    is_focus: bool
    priority: str  # "normal", "main", "difficult"
    priority_multiplier: float
    computed_weight: float
    daily_study_minutes: int
    daily_revision_minutes: int
    daily_weakness_minutes: int
    daily_total_minutes: int
    total_estimated_hours_to_exam: float
    recommended_sessions_per_week: int
    revision_box_interval_days: list[int]
    sessions_per_week: int = 7
    session_duration_minutes: int = 30
    days_schedule_label: str = "প্রতিদিন (৭ দিন)"
    is_daily_subject: bool = True
    chapter_breakdown: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PlanDatasetSummary:
    class_level: int
    group: str
    exam_name: str
    exam_date: str
    days_remaining: int
    daily_study_hours: float
    daily_total_minutes: int
    breakdown_shares: dict[str, int]  # study, revision, weakness, quiz
    subjects: list[SubjectTimeAllocation]
    total_allocated_minutes: int
    final_revision_window_days: int
    buffer_catchup_days: int
    routine_strategy: str = "core_weak_daily"
    total_unread_chapters: int = 0
    total_completed_chapters: int = 0
    weekly_schedule: list[dict[str, Any]] = field(default_factory=list)


def calculate_study_and_revision_dataset(
    class_level: int,
    group: str = "general",
    selected_subject_slugs: list[str] | None = None,
    weak_subject_slugs: list[str] | None = None,
    focus_subject_slugs: list[str] | None = None,
    subject_priorities: dict[str, str] | None = None,
    chapter_statuses: dict[str, dict[str | int, str]] | None = None,
    daily_study_hours: float = 3.0,
    routine_strategy: str = "core_weak_daily",
    exam_date_val: date | str | None = None,
    exam_name: str = "অর্ধবার্ষিক পরীক্ষা (Half-Yearly Exam)",
    now_date: date | None = None,
) -> PlanDatasetSummary:
    """Calculate mathematically grounded time allocation and revision schedule with chapter status."""
    today = now_date or date.today()

    # Rule: Minimum 3.0 hours daily study
    effective_daily_hours = max(3.0, float(daily_study_hours or 3.0))

    # Parse exam date
    if isinstance(exam_date_val, str):
        try:
            target_exam = datetime.strptime(exam_date_val[:10], "%Y-%m-%d").date()
        except ValueError:
            target_exam = today.fromordinal(today.toordinal() + 60)
    elif isinstance(exam_date_val, date):
        target_exam = exam_date_val
    else:
        target_exam = today.fromordinal(today.toordinal() + 60)

    days_remaining = max(1, (target_exam - today).days)

    all_catalog_subjects = get_subjects_for_class_and_group(class_level, group)
    active_slugs = set(selected_subject_slugs or [s.slug for s in all_catalog_subjects])
    weak_set = set(weak_subject_slugs or [])
    focus_set = set(focus_subject_slugs or [])
    priorities = subject_priorities or {}
    chap_status_map = chapter_statuses or {}

    active_subjects = [s for s in all_catalog_subjects if s.slug in active_slugs]
    if not active_subjects:
        active_subjects = all_catalog_subjects

    total_daily_mins = int(round(effective_daily_hours * 60))
    # Daily budget breakdown:
    # 55% New study, 20% Spaced revision, 15% Weak-point practice, 10% Quiz/homework
    budget_study = int(round(total_daily_mins * 0.55))
    budget_revision = int(round(total_daily_mins * 0.20))
    budget_weakness = int(round(total_daily_mins * 0.15))
    budget_quiz = max(0, total_daily_mins - (budget_study + budget_revision + budget_weakness))

    p_multipliers = {
        "normal": 1.0,
        "main": 1.30,
        "difficult": 1.60,
    }

    # Step 1: Base subject weight calculation
    weights: dict[str, float] = {}
    for s in active_subjects:
        p_name = priorities.get(s.slug, "main" if s.is_stem else "normal")
        p_mult = p_multipliers.get(p_name, 1.0)
        is_weak = s.slug in weak_set
        is_focus = s.slug in focus_set

        w = s.base_difficulty * p_mult
        if is_weak:
            w *= 1.40  # 40% more attention for weak subject
        if is_focus:
            w *= 1.20  # 20% more attention for exam focus

        weights[s.slug] = w

    sum_weights = sum(weights.values()) or 1.0

    # Step 2: Allocate daily minutes and differentiate New Study vs Revision
    allocated_list: list[SubjectTimeAllocation] = []
    total_assigned_study = 0
    total_assigned_rev = 0
    total_assigned_weak = 0
    grand_unread_chapters = 0
    grand_completed_chapters = 0

    sorted_subs = sorted(active_subjects, key=lambda s: weights.get(s.slug, 1.0), reverse=True)
    non_core_idx = 0

    for s in sorted_subs:
        w = weights[s.slug]
        is_weak = s.slug in weak_set
        is_focus = s.slug in focus_set
        p_name = priorities.get(s.slug, "main" if s.is_stem else "normal")
        is_core = is_weak or is_focus or s.is_stem or w >= 1.3

        # Routine Strategy calculation
        sessions_per_week = 7
        session_duration = 30
        days_label = "প্রতিদিন (৭ দিন)"
        is_daily = True

        if routine_strategy == "all_daily":
            sessions_per_week = 7
            is_daily = True
            days_label = "প্রতিদিন (৭ দিন)"
            raw_mins = int(round(total_daily_mins * (w / sum_weights)))
            session_duration = max(30, raw_mins)
        elif routine_strategy == "core_weak_daily":
            if is_core:
                sessions_per_week = 7
                is_daily = True
                days_label = "প্রতিদিন (রোজ)"
                session_duration = max(45, int(round(total_daily_mins * 0.32)))
            else:
                is_group_a = non_core_idx % 2 == 0
                non_core_idx += 1
                sessions_per_week = 3
                is_daily = False
                days_label = "শনি-সোম-বুধ (৩ দিন)" if is_group_a else "রবি-মঙ্গল-বৃহ (৩ দিন)"
                session_duration = max(30, int(round(35 + (w - 1.0) * 15)))
        else:  # importance_weighted_rotation
            if is_weak or w >= 1.5:
                sessions_per_week = 5
                is_daily = False
                days_label = "সপ্তাহে ৫ দিন (গভীর ফোকাস)"
                session_duration = max(50, int(round(55 + (w - 1.5) * 20)))
            elif is_core or w >= 1.2:
                sessions_per_week = 4
                is_daily = False
                days_label = "সপ্তাহে ৪ দিন"
                session_duration = max(40, int(round(40 + (w - 1.2) * 15)))
            else:
                sessions_per_week = 2
                is_daily = False
                days_label = "সপ্তাহে ২ দিন"
                session_duration = 30

        # Inspect chapters for this subject
        sub_chap_map = chap_status_map.get(s.slug, {})
        chapter_breakdown: list[dict[str, Any]] = []

        completed_count = 0
        new_count = 0
        weak_ch_count = 0

        for ch in s.chapters:
            st = sub_chap_map.get(str(ch.number), sub_chap_map.get(ch.number, "new"))
            is_excluded = st == "excluded"
            is_ch_weak = not is_excluded and (is_weak or ch.is_hard or st == "weak")

            if is_excluded:
                pass
            elif st == "completed":
                completed_count += 1
            else:
                new_count += 1

            if is_ch_weak:
                weak_ch_count += 1

            chapter_breakdown.append({
                "number": ch.number,
                "title_bn": ch.title_bn,
                "title_en": ch.title_en,
                "status": "excluded" if is_excluded else ("completed" if st == "completed" else "new"),
                "is_weak": is_ch_weak,
                "estimated_hours": 0.0 if is_excluded else ch.estimated_study_hours,
            })

        grand_unread_chapters += new_count
        grand_completed_chapters += completed_count

        daily_sub_total = int(round((session_duration * sessions_per_week) / 7.0))
        sub_study_min = max(15, int(round(daily_sub_total * 0.65)))
        sub_rev_min = max(10, int(round(daily_sub_total * 0.25)))
        sub_weak_min = max(10, int(round(daily_sub_total * 0.10))) if is_weak else 0

        # Spaced repetition Leitner box intervals
        box_intervals = [1, 2, 5, 10, 21] if is_weak else [1, 3, 7, 14, 30]
        total_sub_hours = round((daily_sub_total * days_remaining) / 60.0, 1)

        alloc = SubjectTimeAllocation(
            slug=s.slug,
            name_bn=s.name_bn,
            name_en=s.name_en,
            total_chapters=s.total_chapters,
            completed_chapters_count=completed_count,
            new_chapters_count=new_count,
            weak_chapters_count=weak_ch_count,
            is_stem=s.is_stem,
            is_weak=is_weak,
            is_focus=is_focus,
            priority=p_name,
            priority_multiplier=p_multipliers.get(p_name, 1.0),
            computed_weight=round(w, 2),
            daily_study_minutes=sub_study_min,
            daily_revision_minutes=sub_rev_min,
            daily_weakness_minutes=sub_weak_min,
            daily_total_minutes=daily_sub_total,
            total_estimated_hours_to_exam=total_sub_hours,
            recommended_sessions_per_week=sessions_per_week,
            revision_box_interval_days=box_intervals,
            sessions_per_week=sessions_per_week,
            session_duration_minutes=session_duration,
            days_schedule_label=days_label,
            is_daily_subject=is_daily,
            chapter_breakdown=chapter_breakdown,
        )
        allocated_list.append(alloc)
        total_assigned_study += sub_study_min
        total_assigned_rev += sub_rev_min
        total_assigned_weak += sub_weak_min

    # Final revision window (last 15% of days, minimum 3 days)
    final_rev_days = max(3, int(round(days_remaining * 0.15)))
    # Weekly catch-up buffer days (1 every 7 days)
    buffer_days = max(1, days_remaining // 7)

    # Day-by-Day Weekly Routine (Saturday to Friday)
    # Friday & Saturday: Weekend / No School -> 2 hr (120m) Spaced Revision block
    # Sunday to Thursday: School Days -> 3 subjects/day, 25% of time for revision, >=30m per subject
    days_meta = [
        {"day_id": "sat", "name_bn": "শনিবার", "name_en": "Saturday", "is_weekend": True},
        {"day_id": "sun", "name_bn": "রবিবার", "name_en": "Sunday", "is_weekend": False},
        {"day_id": "mon", "name_bn": "সোমবার", "name_en": "Monday", "is_weekend": False},
        {"day_id": "tue", "name_bn": "মঙ্গলবার", "name_en": "Tuesday", "is_weekend": False},
        {"day_id": "wed", "name_bn": "বুধবার", "name_en": "Wednesday", "is_weekend": False},
        {"day_id": "thu", "name_bn": "বৃহস্পতিবার", "name_en": "Thursday", "is_weekend": False},
        {"day_id": "fri", "name_bn": "শুক্রবার", "name_en": "Friday", "is_weekend": True},
    ]

    core_subs = [s for s in allocated_list if s.is_weak or s.is_focus or s.is_stem]
    sec_subs = [s for s in allocated_list if not (s.is_weak or s.is_focus or s.is_stem)]
    if not core_subs:
        core_subs = allocated_list[:2]
    if not sec_subs:
        sec_subs = allocated_list[2:]

    weekly_schedule: list[dict[str, Any]] = []
    weekday_target_mins = max(180, total_daily_mins)

    for d_idx, d in enumerate(days_meta):
        is_wk = d["is_weekend"]
        spec_rev = 120 if is_wk else 0

        if is_wk:
            # Weekend (Sat & Fri): 2 subjects + 2 hr revision
            c = core_subs[d_idx % len(core_subs)]
            s = sec_subs[d_idx % len(sec_subs)] if sec_subs else core_subs[(d_idx + 1) % len(core_subs)]
            day_subs = [c, s]
        else:
            # Weekday: Exactly 3 subjects (NEVER all subjects!)
            c1 = core_subs[d_idx % len(core_subs)]
            c2 = core_subs[(d_idx + 1) % len(core_subs)]
            s1 = sec_subs[d_idx % len(sec_subs)] if sec_subs else core_subs[(d_idx + 2) % len(core_subs)]
            seen = set()
            day_subs = []
            for sub in [c1, s1, c2]:
                if sub.slug not in seen:
                    seen.add(sub.slug)
                    day_subs.append(sub)
            for sub in allocated_list:
                if len(day_subs) >= 3:
                    break
                if sub.slug not in seen:
                    seen.add(sub.slug)
                    day_subs.append(sub)

        avail_mins = max(90, weekday_target_mins - spec_rev) if is_wk else weekday_target_mins
        base_mins = max(30, avail_mins // max(1, len(day_subs)))

        day_study_total = 0
        day_rev_total = spec_rev
        day_items: list[dict[str, Any]] = []

        for sub in day_subs:
            sub_total = base_mins + (15 if sub.is_weak else 0)
            sub_total = max(30, sub_total)

            # Strictly 25% of time for revision
            rev_m = max(8, int(round(sub_total * 0.25)))
            study_m = max(22, sub_total - rev_m)

            day_study_total += study_m
            day_rev_total += rev_m

            day_items.append({
                "subject_slug": sub.slug,
                "subject_name_bn": sub.name_bn,
                "subject_name_en": sub.name_en,
                "is_weak": sub.is_weak,
                "is_focus": sub.is_focus,
                "total_minutes": study_m + rev_m,
                "study_minutes": study_m,
                "revision_minutes": rev_m,
            })

        weekly_schedule.append({
            "day_id": d["day_id"],
            "day_name_bn": d["name_bn"],
            "day_name_en": d["name_en"],
            "is_weekend": is_wk,
            "is_school_day": not is_wk,
            "school_status_label_bn": "স্কুল বন্ধ (ছুটির দিন)" if is_wk else "স্কুল ডে",
            "special_revision_block_minutes": spec_rev,
            "daily_total_minutes": day_study_total + day_rev_total,
            "daily_study_minutes": day_study_total,
            "daily_revision_minutes": day_rev_total,
            "items": day_items,
        })

    return PlanDatasetSummary(
        class_level=class_level,
        group=group,
        exam_name=exam_name,
        exam_date=target_exam.strftime("%Y-%m-%d"),
        days_remaining=days_remaining,
        daily_study_hours=effective_daily_hours,
        daily_total_minutes=total_daily_mins,
        breakdown_shares={
            "new_study": budget_study,
            "spaced_revision": budget_revision,
            "weakness_practice": budget_weakness,
            "quizzes": budget_quiz,
            "study": budget_study,
            "revision": budget_revision,
            "weakness": budget_weakness,
            "quiz": budget_quiz,
            "new_study_minutes": budget_study,
            "spaced_revision_minutes": budget_revision,
            "weakness_practice_minutes": budget_weakness,
            "quiz_minutes": budget_quiz,
        },
        subjects=allocated_list,
        total_allocated_minutes=total_assigned_study + total_assigned_rev + total_assigned_weak,
        final_revision_window_days=final_rev_days,
        buffer_catchup_days=buffer_days,
        routine_strategy=routine_strategy,
        total_unread_chapters=grand_unread_chapters,
        total_completed_chapters=grand_completed_chapters,
        weekly_schedule=weekly_schedule,
    )
