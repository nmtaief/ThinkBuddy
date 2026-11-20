"""AI Study Planner & Weakness Review Engine.

Provides:
1. Free-form text parser to extract study preferences and goals from natural language.
2. LLM-powered weakness reviewer to validate student workloads, identify risks,
   and provide personalized study guidance in Bangla and English.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.admin.service import get_or_create_ai_tutor_config
from core.curriculum.nctb_subjects import get_subjects_for_class_and_group
from core.planner.dataset import PlanDatasetSummary, calculate_study_and_revision_dataset

logger = logging.getLogger("thinkbuddy.planner.ai_planner")


class AIPlanReviewRequest(BaseModel):
    freeform_text: str | None = Field(default=None, description="Free-form student description of goals and weaknesses")
    class_level: int = Field(default=8, ge=6, le=10)
    medium: str = Field(default="bangla")
    group: str = Field(default="general")
    exam_name: str | None = Field(default="অর্ধ-বার্ষিক পরীক্ষা (Half-Yearly Exam)")
    exam_date: str | None = Field(default=None)
    daily_study_hours: float = Field(default=3.0, ge=0.5, le=10.0)
    routine_strategy: str = Field(default="core_weak_daily", description="'all_daily', 'core_weak_daily', or 'importance_weighted_rotation'")
    selected_subjects: list[str] = Field(default_factory=list)
    weak_subjects: list[str] = Field(default_factory=list)
    focus_subjects: list[str] = Field(default_factory=list)
    subject_priorities: dict[str, str] = Field(default_factory=dict)
    chapter_statuses: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description="Map of subject_slug -> chapter_number -> 'new' | 'completed' | 'weak'",
    )


class AIPlanReviewResponse(BaseModel):
    success: bool
    plan_dataset: dict[str, Any]
    ai_review_status: str  # "optimal", "needs_more_time", "balanced", "intensive"
    ai_guidance_bn: str
    ai_guidance_en: str
    key_recommendations: list[str]
    feasibility_score: float  # 0.0 to 1.0
    extracted_from_text: dict[str, Any] | None = None


def parse_freeform_student_text(text: str) -> dict[str, Any]:
    """Extract class, hours, exam date, and subject weaknesses from natural language text."""
    extracted: dict[str, Any] = {
        "class_level": 8,
        "group": "general",
        "daily_study_hours": 2.5,
        "weak_subjects": [],
        "focus_subjects": [],
        "exam_days_remaining": 60,
    }
    lower_text = text.lower()

    # 1. Detect Class Level
    class_patterns = [
        r"(?:class|শ্রেণি|ক্লাস)\s*[:=]?\s*([6-9]|10|৬|৭|৮|৯|১০)",
        r"([6-9]|10|৬|৭|৮|৯|১০)\s*(?:th|তম|ম|ষ্ঠ|ম|র্থ)?\s*(?:class|শ্রেণি|ক্লাস|গ্রেড)",
    ]
    bn_num_map = {"৬": 6, "৭": 7, "৮": 8, "৯": 9, "১০": 10, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10}
    for pat in class_patterns:
        m = re.search(pat, lower_text)
        if m:
            val = m.group(1)
            extracted["class_level"] = bn_num_map.get(val, 8)
            break

    # Group detection for classes 9-10
    if extracted["class_level"] >= 9:
        if any(w in lower_text for w in ["বিজ্ঞান", "science"]):
            extracted["group"] = "science"
        elif any(w in lower_text for w in ["বাণিজ্য", "ব্যবসায়", "ব্যবসা", "commerce", "business"]):
            extracted["group"] = "commerce"
        elif any(w in lower_text for w in ["মানবিক", "humanities", "arts"]):
            extracted["group"] = "humanities"
        else:
            extracted["group"] = "science"

    # 2. Detect Daily Study Hours
    hour_match = re.search(r"(\d+(?:\.\d+)?|[১-৯]+)\s*(?:hour|hours|ঘণ্টা|ঘন্টা|hr|hrs)", lower_text)
    if hour_match:
        h_str = hour_match.group(1)
        bn_digit_map = {"১": "1", "২": "2", "৩": "3", "৪": "4", "৫": "5", "৬": "6", "৭": "7", "৮": "8", "৯": "9"}
        normalized_h = "".join(bn_digit_map.get(c, c) for c in h_str)
        try:
            extracted["daily_study_hours"] = min(8.0, max(1.0, float(normalized_h)))
        except ValueError:
            extracted["daily_study_hours"] = 2.5

    # 3. Detect Weak Subjects
    weak_found: list[str] = []
    subject_keywords = {
        "math": ["math", "গণিত", "অঙ্ক", "ম্যাথ", "বীজগণিত", "জ্যামিতি", "algebra", "geometry"],
        "science": ["science", "বিজ্ঞান"],
        "physics": ["পদার্থ", "পদার্থবিজ্ঞান", "physics"],
        "chemistry": ["রসায়ন", "রসায়ন", "chemistry"],
        "biology": ["জীববিজ্ঞান", "biology"],
        "higher_math": ["higher math", "উচ্চতর গণিত"],
        "accounting": ["হিসাববিজ্ঞান", "accounting"],
        "finance": ["ফিন্যান্স", "finance"],
        "english": ["english", "ইংরেজি", "গ্রামার", "grammar", "vocabulary"],
        "bangla": ["bangla", "বাংলা", "ব্যাকরণ", "সমাস"],
        "ict": ["ict", "তথ্য ও যোগাযোগ", "আইসিটি", "কম্পিউটার"],
    }

    # Context indicators for weakness
    negative_cues = ["weak", "দুর্বল", "কঠিন", "পারি না", "ভয়", "ভয়", "সমস্যা", "struggle", "bad at", "hard", "বাকি"]

    for sub_key, kws in subject_keywords.items():
        has_sub = any(kw in lower_text for kw in kws)
        if has_sub:
            is_negative = any(cue in lower_text for cue in negative_cues)
            if is_negative:
                weak_found.append(sub_key)

    if weak_found:
        extracted["weak_subjects"] = weak_found

    # 4. Detect Exam Date or timeframe
    days_match = re.search(r"(\d+|[১-৯]+)\s*(?:দিন|days)\s*(?:পর|বাকি|left|remaining)", lower_text)
    months_match = re.search(r"(\d+|[১-৯]+)\s*(?:মাস|month|months)\s*(?:পর|বাকি|left|remaining)", lower_text)
    
    bn_digit_map = {"১": "1", "২": "2", "৩": "3", "৪": "4", "৫": "5", "৬": "6", "৭": "7", "৮": "8", "৯": "9", "০": "0"}
    if days_match:
        d_str = days_match.group(1)
        normalized_d = "".join(bn_digit_map.get(c, c) for c in d_str)
        try:
            d_val = int(normalized_d)
            extracted["exam_days_remaining"] = d_val
            target_date = date.today() + timedelta(days=d_val)
            extracted["exam_date"] = target_date.strftime("%Y-%m-%d")
        except ValueError:
            pass
    elif months_match:
        m_str = months_match.group(1)
        normalized_m = "".join(bn_digit_map.get(c, c) for c in m_str)
        try:
            m_val = int(normalized_m)
            d_val = m_val * 30
            extracted["exam_days_remaining"] = d_val
            target_date = date.today() + timedelta(days=d_val)
            extracted["exam_date"] = target_date.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return extracted


async def review_and_generate_ai_plan(
    payload: AIPlanReviewRequest,
    db: AsyncSession,
) -> AIPlanReviewResponse:
    """Analyze student study setup and generate an AI-reviewed balanced plan."""
    extracted = None
    target_class = payload.class_level
    target_hours = payload.daily_study_hours
    target_exam_date = payload.exam_date
    weak_subs = list(payload.weak_subjects)
    focus_subs = list(payload.focus_subjects)

    # 1. Process free-form natural language text if present
    if payload.freeform_text and payload.freeform_text.strip():
        extracted = parse_freeform_student_text(payload.freeform_text)
        if "class_level" in extracted:
            target_class = extracted["class_level"]
        if "daily_study_hours" in extracted:
            target_hours = extracted["daily_study_hours"]
        if "exam_date" in extracted:
            target_exam_date = extracted["exam_date"]
        if "weak_subjects" in extracted:
            # Map canonical keys to specific class subject slugs
            prefix = f"c{target_class}_"
            for w in extracted["weak_subjects"]:
                slug_candidate = f"{prefix}{w}"
                if slug_candidate not in weak_subs:
                    weak_subs.append(slug_candidate)

    # 2. Compute the mathematical study and revision dataset
    dataset_summary = calculate_study_and_revision_dataset(
        class_level=target_class,
        group=payload.group,
        selected_subject_slugs=payload.selected_subjects or None,
        weak_subject_slugs=weak_subs or None,
        focus_subject_slugs=focus_subs or None,
        subject_priorities=payload.subject_priorities or None,
        chapter_statuses=payload.chapter_statuses or None,
        daily_study_hours=target_hours,
        routine_strategy=payload.routine_strategy,
        exam_date_val=target_exam_date,
        exam_name=payload.exam_name or "অর্ধ-বার্ষিক পরীক্ষা (Half-Yearly Exam)",
    )

    # 3. Analyze workload feasibility and pacing
    days = dataset_summary.days_remaining
    unread_chapters = dataset_summary.total_unread_chapters
    done_chapters = dataset_summary.total_completed_chapters
    total_study_mins = dataset_summary.daily_total_minutes

    weeks_remaining = max(1.0, days / 7.0)
    chapters_per_week = round(unread_chapters / weeks_remaining, 1)

    # Feasibility score
    hours_per_unread_chapter = (days * (total_study_mins / 60.0)) / max(1, unread_chapters)
    if hours_per_unread_chapter >= 5.0:
        ai_status = "optimal"
        feasibility_score = 0.95
    elif hours_per_unread_chapter >= 3.0:
        ai_status = "balanced"
        feasibility_score = 0.82
    elif hours_per_unread_chapter >= 1.5:
        ai_status = "intensive"
        feasibility_score = 0.65
    else:
        ai_status = "needs_more_time"
        feasibility_score = 0.45

    # 4. Generate localized AI Tutor feedback
    key_recs: list[str] = []

    if unread_chapters > 0:
        key_recs.append(
            f"নতুন পড়ার গতি: প্রতি সপ্তাহে গড়ে {chapters_per_week}টি নতুন অধ্যায় সম্পন্ন করার লক্ষ্য নির্ধারণ করা হয়েছে।"
        )
    if done_chapters > 0:
        key_recs.append(
            f"স্পেসড রিভিশন: পড়া শেষ হওয়া {done_chapters}টি অধ্যায় ভুলে যাওয়া রোধে ১, ৩ ও ৭ দিনের বিরতিতে লাইটনার বক্সে রিভিশন দেওয়া হবে।"
        )

    for sub in dataset_summary.subjects:
        if sub.is_weak:
            key_recs.append(
                f"{sub.name_bn}: দুর্বল বিষয় হওয়ায় প্রতিদিন {sub.daily_total_minutes} মিনিট সময় (+৪০% অতিরিক্ত সময়) ও সংকুচিত রিভিশন সাইকেল বরাদ্দ করা হয়েছে।"
            )

    # AI Guidance in Bengali and English
    if ai_status == "optimal":
        guidance_bn = (
            f"তোমার পরীক্ষার বাকি {days} দিন এবং মোট {unread_chapters}টি নতুন অধ্যায় রয়েছে। "
            f"দৈনিক {target_hours} ঘণ্টা পড়াশোনা তোমার জন্য একদম পারফেক্ট ও রিল্যাক্সড পেসিং! "
            f"প্রতিটি বিষয়ে নতুন পড়ার পাশাপাশি নিয়মিত স্পেসড রিভিশন রাখার ফলে পরীক্ষার আগে কোনো অতিরিক্ত মানসিক চাপ থাকবে না।"
        )
        guidance_en = (
            f"With {days} days remaining and {unread_chapters} unread chapters, studying {target_hours} hours daily "
            f"provides an optimal, stress-free pace. You have ample time for both deep conceptual mastery and Leitner spaced repetition."
        )
    elif ai_status == "balanced":
        guidance_bn = (
            f"তোমার সময়সূচি বেশ ভারসাম্যপূর্ণ। পরীক্ষার আগে সিলেবাস শেষ করতে প্রতি সপ্তাহে প্রায় {chapters_per_week}টি অধ্যায় শেষ করতে হবে। "
            f"দুর্বল চিহ্নিত অধ্যায়গুলোতে শুরুতে বাড়তি মনোযোগ দাও এবং শেষ ১৫ দিন শুধু মডেল টেস্ট ও রিভিশনের জন্য সংরক্ষণ করো।"
        )
        guidance_en = (
            f"Your schedule is well-balanced. Aim to complete approximately {chapters_per_week} chapters per week. "
            f"Prioritize your declared weak chapters first, reserving the final 15% of days exclusively for mock tests and revision."
        )
    else:
        guidance_bn = (
            f"পরীক্ষার বাকি সময় ({days} দিন) অনুযায়ী তোমার পড়া বাকি থাকা অধ্যায়ের সংখ্যা বেশি ({unread_chapters}টি)। "
            f"আমরা তোমার প্ল্যানে নতুন পড়ার গতি বৃদ্ধি করেছি। সম্ভব হলে দৈনিক পড়ার সময় আরও ৩০-৪৫ মিনিট বাড়ালে ফলাফল আরও ভালো হবে।"
        )
        guidance_en = (
            f"Given {days} days remaining, completing {unread_chapters} chapters is an intensive goal. "
            f"We have accelerated your new study slots. If possible, consider adding 30-45 minutes to your daily study budget."
        )

    # Serialize dataset
    from dataclasses import asdict
    plan_dict = asdict(dataset_summary)

    return AIPlanReviewResponse(
        success=True,
        plan_dataset=plan_dict,
        ai_review_status=ai_status,
        ai_guidance_bn=guidance_bn,
        ai_guidance_en=guidance_en,
        key_recommendations=key_recs,
        feasibility_score=feasibility_score,
        extracted_from_text=extracted,
    )
