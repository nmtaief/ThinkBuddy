"""Service layer for Parent Dashboard, AI chat summaries, and controls (Milestone P07).

Standing Rules & Deliverables:
- Rule 9: Family link authorization enforced on all parent routes.
- Template-based localized reason mapper with fallback word filter (Item 4).
- Topic-level AI chat summaries; never raw chat transcripts (Deliverable 12).
- Student change request approval & decline with audit log and plan regeneration (Item 2).
- Numeric caps for auto mode and parent-only optimistic-locked undo (Item 5).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit.models import AuditLog
from core.auth.models import User
from core.common.redis import get_redis_client
from core.chat.models import ChatCitation, ChatMessage, ChatSession
from core.curriculum.models import Book, Chapter
from core.families.models import ParentStudentLink, StudentProfile
from core.notifications.service import NotificationService
from core.parent.schemas import (
    ParentAiAdjustmentView,
    ParentAiSuggestionView,
    ParentChatTopicSummary,
    ParentExamCountdown,
    ParentMasterySubjectSummary,
    ParentOverviewResponse,
    ParentProgressSummary,
    ParentRevisionSummary,
    ParentStudentSummary,
    StudentDashboardResponse,
)
from core.planner.models import (
    AdminPolicy,
    StudentChangeRequest,
    StudentStudySettings,
    StudySetup,
)
from core.planner.router import execute_student_plan_regeneration
from core.progress.models import Mastery, ProgressDaily, RevisionItem

logger = logging.getLogger("thinkbuddy.parent")

# Class band recommended minute ceilings (Item 5)
CLASS_BAND_RECOMMENDED_CEILINGS: dict[str, int] = {
    "6-8": 120,
    "9-10": 180,
    "11-12": 240,
}

# Approved localized rationale templates (Item 4)
APPROVED_REASON_TEMPLATES: dict[str, dict[str, str]] = {
    "EXAM_APPROACHING": {
        "en": "Upcoming exam requires focused practice on core curriculum chapters.",
        "bn": "আসন্ন পরীক্ষার জন্য মূল অধ্যায়গুলোতে নিয়মিত অনুশীলন প্রয়োজন।",
    },
    "PACING_BEHIND": {
        "en": "Study pace adjusted to reinforce steady progress and syllabus completion.",
        "bn": "সিলেবাস সময়মতো সম্পন্ন করতে পড়ার ধারাবাহিকতা বজায় রাখা প্রয়োজন।",
    },
    "HIGH_MASTERY_REDUCTION": {
        "en": "Strong mastery demonstrated; reallocating study time to subjects needing practice.",
        "bn": "উচ্চ দক্ষতা অর্জিত হয়েছে; যে বিষয়গুলোতে অনুশীলন প্রয়োজন সেগুলোতে সময় পুনর্বণ্টন করা হচ্ছে।",
    },
    "DAILY_PRACTICE_BOOST": {
        "en": "Recommended additional study minutes to support upcoming milestones.",
        "bn": "আসন্ন মাইলফলকের প্রস্তুতির জন্য অতিরিক্ত পড়ার সময়ের পরামর্শ দেওয়া হলো।",
    },
    "REVISION_DUE_SURGE": {
        "en": "Spaced revision items are due; allocating dedicated review time.",
        "bn": "পুনরাবৃত্তি পড়া জমা হয়েছে; রিভিশনের জন্য বাড়তি সময় বরাদ্দ করা হয়েছে।",
    },
    "SCHEDULE_CONSISTENCY": {
        "en": "Balancing study sessions across days to maintain a steady learning rhythm.",
        "bn": "ধারাবাহিকতা বজায় রাখতে বিভিন্ন দিনে পড়ার সময় সামঞ্জস্য করা হয়েছে।",
    },
    "WEAK_CONCEPT": {
        "en": "Concept needs additional guided practice to build solid understanding.",
        "bn": "ধারণাটি পুরোপুরি আত্মস্থ করতে আরও অনুশীলনের প্রয়োজন।",
    },
    "SPACED_REVIEW_DUE": {
        "en": "Scheduled spaced revision due to reinforce memory retention.",
        "bn": "পড়া মনে রাখার জন্য নির্ধারিত সময়ের রিভিশন প্রয়োজন।",
    },
    "STRENGTH_MAINTENANCE": {
        "en": "Topic well understood; periodic review scheduled to maintain retention.",
        "bn": "বিষয়টিতে ভালো দক্ষতা রয়েছে; স্মৃতিতে ধরে রাখতে নিয়মিত রিভিশন রাখা হয়েছে।",
    },
    "CATCH_UP_MISSED": {
        "en": "Rescheduling missed study topics to keep syllabus progress on track.",
        "bn": "বাদ পড়া বিষয়গুলো পুনরায় যুক্ত করে সিলেবাসে এগিয়ে থাকার পরিকল্পনা।",
    },
    "RECENT_ERRORS": {
        "en": "Recent quiz questions highlight specific topics for focused review.",
        "bn": "সাম্প্রতিক কুইজের ফলাফলের ভিত্তিতে গুরুত্বপূর্ণ বিষয়গুলো ঝালিয়ে নেওয়া হচ্ছে।",
    },
    "REPEATED_QUESTIONS": {
        "en": "Frequent questions on this topic suggest dedicated practice time.",
        "bn": "এই বিষয়ে বারবার প্রশ্ন আসায় বাড়তি সময় বরাদ্দ করা হয়েছে।",
    },
    "BALANCE_ROTATION": {
        "en": "Rotational scheduling ensures balanced coverage across all subjects.",
        "bn": "সব বিষয়ে সমভাবে পড়ার অভ্যাস গড়ে তুলতে পড়ার রুটিন সমন্বয় করা হয়েছে।",
    },
    "LOW_DATA_DEFAULT": {
        "en": "Standard curriculum pacing applied while gathering learning insights.",
        "bn": "শিক্ষণ অগ্রগতি মূল্যায়নের প্রাথমিক পর্যায়ে স্ট্যান্ডার্ড রুটিন অনুসরণ করা হচ্ছে।",
    },
    "PRIORITY_PARENT": {
        "en": "Subject prioritized in accordance with parent-configured goals.",
        "bn": "অভিভাবকের অগ্রাধিকার অনুসারে বিষয়টিকে গুরুত্ব দেওয়া হয়েছে।",
    },
}


def utcnow() -> datetime:
    return datetime.now(UTC)


def sanitize_non_labeling_reason(text: str) -> str:
    """Ensure parent-facing rationale strictly avoids deficit labeling (Item 7). Fallback filter."""
    replacements = {
        "weak": "needs practice",
        "weakness": "area for practice",
        "failing": "developing",
        "poor": "foundational",
        "slow": "paced",
        "struggling": "building mastery",
        "durbol": "অনুশীলন প্রয়োজন",
    }
    cleaned = text
    for word, repl in replacements.items():
        import re

        cleaned = re.sub(rf"\b{word}\b", repl, cleaned, flags=re.IGNORECASE)
    return cleaned


def format_parent_reason(
    reason_code: str | None = None,
    raw_text: str | None = None,
    subject: str | None = None,
    language: str = "en",
) -> str:
    """Map AI reason codes to approved localized templates; keep word filter only as fallback (Item 4)."""
    if reason_code and reason_code.upper() in APPROVED_REASON_TEMPLATES:
        template = APPROVED_REASON_TEMPLATES[reason_code.upper()]
        return template.get(language, template["en"])

    if raw_text:
        cleaned = sanitize_non_labeling_reason(raw_text)
        if language == "bn":
            return localize_rationale_bn(cleaned, subject)
        return cleaned

    sub_name = subject or ("বিষয়" if language == "bn" else "subject")
    return (
        f"{sub_name}-এ নিয়মিত অগ্রগতির জন্য পড়ার সময় সমন্বয় করা হয়েছে।"
        if language == "bn"
        else f"Adjusted {sub_name} study schedule to support steady learning progress."
    )


def localize_rationale_bn(text: str, subject: str | None = None) -> str:
    """Generate constructive Bengali explanation for study recommendations."""
    sub_text = subject or "বিষয়"
    if "practice" in text.lower() or "reinforce" in text.lower():
        return f"{sub_text}-এ ভিত্তি মজবুত ও দক্ষতা বৃদ্ধির জন্য অতিরিক্ত অনুশীলন প্রয়োজন।"
    if "exam" in text.lower():
        return "আসন্ন পরীক্ষার ধারাবাহিক প্রস্তুতির জন্য পড়ার সময় সমন্বয় করা হয়েছে।"
    return f"{sub_text}-এর পাঠ্যক্রমের ধারাবাহিকতা বজায় রাখতে এআই প্ল্যানার এই সমন্বয় প্রস্তাব করেছে।"


class ParentService:
    """Aggregates multi-source metrics into growth-oriented parent dashboard."""

    @staticmethod
    async def verify_parent_student_link(
        db: AsyncSession,
        parent_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> None:
        """Verify active parent-student family linkage (Rule 9)."""
        stmt = select(ParentStudentLink).where(
            ParentStudentLink.parent_id == parent_id,
            ParentStudentLink.student_id == student_id,
            ParentStudentLink.status == "active",
        )
        res = await db.execute(stmt)
        if not res.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Parent is not linked to this student (Rule 9)",
            )

    @staticmethod
    async def get_student_dashboard(
        db: AsyncSession,
        parent_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> StudentDashboardResponse:
        # 1. Authorization MUST be evaluated BEFORE reading or returning any cached dashboard (Item 5)
        await ParentService.verify_parent_student_link(db, parent_id, student_id)

        # 2. Check Redis cache only AFTER verifying active parent linkage
        cache_key = f"thinkbuddy:dashboard:{student_id}"
        try:
            redis = await get_redis_client()
            cached = await redis.get(cache_key)
            if cached:
                return StudentDashboardResponse.model_validate_json(cached)
        except Exception as ex:
            logger.debug("Redis cache miss/error for dashboard %s: %s", student_id, ex)

        # 1. Fetch student user and profile
        stmt_u = select(User).where(User.id == student_id)
        res_u = await db.execute(stmt_u)
        user = res_u.scalars().first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

        stmt_prof = select(StudentProfile).where(StudentProfile.user_id == student_id)
        res_prof = await db.execute(stmt_prof)
        profile = res_prof.scalars().first()
        class_level = profile.class_level if profile else 10
        class_band = "6-8" if class_level <= 8 else ("9-10" if class_level <= 10 else "11-12")
        group = profile.group if profile else "general"
        student_summary = ParentStudentSummary(
            student_id=student_id,
            name=user.display_name or "Student",
            class_band=class_band,
            group=group,
            avatar_url=None,
        )

        # 2. Progress and Streaks
        stmt_p = (
            select(ProgressDaily)
            .where(ProgressDaily.student_id == student_id)
            .order_by(ProgressDaily.date.desc())
        )
        res_p = await db.execute(stmt_p)
        progress_rows = res_p.scalars().all()

        total_mins = sum(r.minutes for r in progress_rows)
        total_tasks_done = sum(r.tasks_done for r in progress_rows)
        total_tasks_all = sum(r.tasks_total for r in progress_rows)
        completion_pct = (
            round((total_tasks_done / total_tasks_all) * 100.0, 1) if total_tasks_all > 0 else 100.0
        )
        latest_streak = progress_rows[0].streak if progress_rows else 0
        quiz_scores = [r.quiz_avg for r in progress_rows if r.quiz_avg is not None]
        avg_quiz = round(sum(quiz_scores) / len(quiz_scores), 2) if quiz_scores else None

        progress_summary = ParentProgressSummary(
            total_minutes_studied=total_mins,
            total_tasks_completed=total_tasks_done,
            completion_rate_pct=completion_pct,
            active_streak_days=latest_streak,
            weekly_grace_available=True,
            quiz_score_avg=avg_quiz,
        )

        # 3. Non-labeling Subject Mastery
        stmt_m = (
            select(Mastery, Book.subject)
            .join(Chapter, Mastery.chapter_id == Chapter.id)
            .join(Book, Chapter.book_id == Book.id)
            .where(Mastery.student_id == student_id)
        )
        res_m = await db.execute(stmt_m)
        mastery_rows = res_m.all()

        subject_scores: dict[str, list[float]] = {}
        for m_obj, subj in mastery_rows:
            subject_scores.setdefault(subj, []).append(m_obj.score)

        subjects_mastery: list[ParentMasterySubjectSummary] = []
        for subj, scores in subject_scores.items():
            avg_m = round(sum(scores) / len(scores), 2) if scores else 0.5
            if avg_m < 0.6:
                m_status = "needs_practice"
                m_status_bn = "অনুশীলন প্রয়োজন"
            elif avg_m < 0.8:
                m_status = "in_progress"
                m_status_bn = "অগ্রগতি চলমান"
            else:
                m_status = "mastered"
                m_status_bn = "দক্ষতা অর্জিত"

            subjects_mastery.append(
                ParentMasterySubjectSummary(
                    subject=subj,
                    mastery_score=avg_m,
                    confidence=0.8,
                    status=m_status,
                    status_bn=m_status_bn,
                    focus_areas=[],
                )
            )

        # 4. Spaced Revision
        stmt_rev = select(RevisionItem).where(RevisionItem.student_id == student_id)
        res_rev = await db.execute(stmt_rev)
        rev_items = res_rev.scalars().all()
        now_dt = datetime.now(UTC)
        due_count = sum(1 for r in rev_items if r.due_at <= now_dt)
        box_dist: dict[str, int] = {}
        for r in rev_items:
            k = f"box_{r.box}"
            box_dist[k] = box_dist.get(k, 0) + 1

        revision_summary = ParentRevisionSummary(
            due_count=due_count,
            boxes_distribution=box_dist,
        )

        # 5. Upcoming Exams
        stmt_setups = select(StudySetup).where(StudySetup.student_id == student_id)
        res_setups = await db.execute(stmt_setups)
        setups = res_setups.scalars().all()
        today_date = date.today()
        upcoming_exams: list[ParentExamCountdown] = []
        for s in setups:
            delta_days = (s.exam_date - today_date).days
            upcoming_exams.append(
                ParentExamCountdown(
                    subject=s.subject,
                    exam_name=s.exam_name,
                    exam_date=s.exam_date,
                    days_remaining=delta_days,
                )
            )

        # 6. AI Suggestions (pending review) with Template Mapping (Item 4)
        stmt_sugg = (
            select(StudentChangeRequest)
            .where(
                StudentChangeRequest.student_id == student_id,
                StudentChangeRequest.status == "pending",
            )
            .order_by(StudentChangeRequest.created_at.desc())
        )
        res_sugg = await db.execute(stmt_sugg)
        sugg_records = res_sugg.scalars().all()
        ai_suggestions: list[ParentAiSuggestionView] = []
        for r in sugg_records:
            ch = r.requested_changes or {}
            ch_type = ch.get("type", "ai_priority_suggestion")
            if ch_type in ("ai_priority_suggestion", "ai_minute_suggestion"):
                reason_code = ch.get("reason_code")
                sub_name = ch.get("subject")
                raw_rationale = ch.get("rationale") or "Pacing adjustment recommended."

                # Use approved localized template with fallback word filter (Item 4)
                clean_rationale = format_parent_reason(
                    reason_code=reason_code,
                    raw_text=raw_rationale,
                    subject=sub_name,
                    language="en",
                )
                rationale_bn = format_parent_reason(
                    reason_code=reason_code,
                    raw_text=raw_rationale,
                    subject=sub_name,
                    language="bn",
                )

                cur_val = ch.get("current_level") if ch_type == "ai_priority_suggestion" else ch.get("current_minutes")
                sugg_val = ch.get("suggested_level") if ch_type == "ai_priority_suggestion" else ch.get("suggested_minutes")

                ai_suggestions.append(
                    ParentAiSuggestionView(
                        id=r.id,
                        student_id=r.student_id,
                        type=ch_type,
                        subject=sub_name,
                        field=ch.get("field"),
                        current_value=cur_val,
                        suggested_value=sugg_val,
                        rationale=clean_rationale,
                        rationale_bn=rationale_bn,
                        evidence_codes=ch.get("evidence_codes", []),
                        status=r.status,
                        created_at=r.created_at,
                        expires_at=None,
                    )
                )

        # 7. Recent Auto-Applied Adjustments (with one-tap undo)
        stmt_sett = select(StudentStudySettings).where(StudentStudySettings.student_id == student_id)
        res_sett = await db.execute(stmt_sett)
        settings_obj = res_sett.scalars().first()

        recent_adjustments: list[ParentAiAdjustmentView] = []
        adaptive_mode = settings_obj.adaptive_mode if settings_obj else "suggest"
        if settings_obj and settings_obj.ai_adjustments:
            raw_adj = settings_obj.ai_adjustments.get("recent_adjustments", [])
            for a in raw_adj:
                if not a.get("undone", False):
                    recent_adjustments.append(
                        ParentAiAdjustmentView(
                            adjustment_id=a.get("adjustment_id", ""),
                            type=a.get("type", "ai_minute_adjustment"),
                            summary=a.get("summary", "Automated plan pacing adjustment"),
                            summary_bn=a.get("summary_bn", "স্বয়ংক্রিয় রুটিন সমন্বয়"),
                            applied_at=a.get("applied_at", ""),
                            can_undo=True,
                        )
                    )

        # 8. Topic-Level AI Chat Summaries (Deliverable 12: strictly no raw transcripts)
        stmt_chat = (
            select(
                ChatCitation.chapter_title,
                ChatCitation.book_title,
                func.count(ChatCitation.id).label("q_count"),
                func.max(ChatCitation.created_at).label("last_asked"),
            )
            .join(ChatMessage, ChatCitation.message_id == ChatMessage.id)
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .where(ChatSession.student_id == student_id)
            .group_by(ChatCitation.chapter_title, ChatCitation.book_title)
            .order_by(func.count(ChatCitation.id).desc())
            .limit(10)
        )
        res_chat = await db.execute(stmt_chat)
        chat_topics = [
            ParentChatTopicSummary(
                topic=row[0],
                subject=row[1],
                question_count=int(row[2]),
                last_asked_at=row[3],
            )
            for row in res_chat.all()
        ]

        dashboard_response = StudentDashboardResponse(
            student=student_summary,
            progress=progress_summary,
            subjects_mastery=subjects_mastery,
            spaced_revision=revision_summary,
            upcoming_exams=upcoming_exams,
            ai_suggestions=ai_suggestions,
            recent_ai_adjustments=recent_adjustments,
            chat_topics=chat_topics,
            adaptive_mode=adaptive_mode,
        )

        # Cache response in Redis with 60s TTL (Item 7)
        try:
            redis = await get_redis_client()
            await redis.set(cache_key, dashboard_response.model_dump_json(), ex=60)
        except Exception as ex:
            logger.debug("Failed to set dashboard cache for %s: %s", student_id, ex)

        return dashboard_response

    @staticmethod
    async def get_parent_overview(
        db: AsyncSession,
        parent_id: uuid.UUID,
    ) -> ParentOverviewResponse:
        """Consolidated multi-student overview for all linked children."""
        stmt = (
            select(ParentStudentLink.student_id)
            .where(
                ParentStudentLink.parent_id == parent_id,
                ParentStudentLink.status == "active",
            )
        )
        res = await db.execute(stmt)
        student_ids = res.scalars().all()

        student_dashboards: list[StudentDashboardResponse] = []
        for sid in student_ids:
            try:
                dash = await ParentService.get_student_dashboard(db, parent_id, sid)
                student_dashboards.append(dash)
            except Exception as e:
                logger.warning("Error fetching dashboard for student %s: %s", sid, e)

        return ParentOverviewResponse(
            parent_id=parent_id,
            students=student_dashboards,
        )

    # -------------------------------------------------------------------------
    # Student Change Request Controls (Item 2)
    # -------------------------------------------------------------------------

    @staticmethod
    async def approve_student_change_request(
        db: AsyncSession,
        parent_id: uuid.UUID,
        student_id: uuid.UUID,
        request_id: uuid.UUID,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Parent approves student change request, applying changes and regenerating plan (Item 2)."""
        await ParentService.verify_parent_student_link(db, parent_id, student_id)

        stmt = (
            select(StudentChangeRequest)
            .where(
                StudentChangeRequest.id == request_id,
                StudentChangeRequest.student_id == student_id,
            )
            .with_for_update()
        )
        res = await db.execute(stmt)
        req = res.scalars().first()
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student change request not found")

        if req.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Change request has already been processed (status={req.status})",
            )

        # Check expiration (Item 4 & 6: cannot revive expired requests)
        if (req.expires_at and req.expires_at <= utcnow()) or req.status == "expired":
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Change request has expired and cannot be approved",
            )

        changes = req.requested_changes or {}

        # Re-validate all fields against active AdminPolicy limits (Item 4 & 6)
        stmt_prof = select(StudentProfile.class_level).where(StudentProfile.user_id == student_id)
        res_prof = await db.execute(stmt_prof)
        cls_lvl = res_prof.scalar_one_or_none() or 10
        band = "6-8" if cls_lvl <= 8 else ("9-10" if cls_lvl <= 10 else "11-12")

        stmt_pol = (
            select(AdminPolicy)
            .where(AdminPolicy.class_band == band, AdminPolicy.status == "published")
            .order_by(AdminPolicy.version.desc())
        )
        res_pol = await db.execute(stmt_pol)
        policy = res_pol.scalars().first()
        school_hard_limit = getattr(policy, "school_day_hard_limit_minutes", 180) if policy else 180
        holiday_hard_limit = getattr(policy, "holiday_hard_limit_minutes", 240) if policy else 240

        if "school_day_minutes" in changes:
            sm = int(changes["school_day_minutes"])
            if sm < 0 or sm > school_hard_limit:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "LIMIT_EXCEEDED",
                        "message": f"school_day_minutes ({sm}) must be between 0 and hard limit {school_hard_limit}m",
                    },
                )

        if "holiday_minutes" in changes:
            hm = int(changes["holiday_minutes"])
            if hm < 0 or hm > holiday_hard_limit:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "LIMIT_EXCEEDED",
                        "message": f"holiday_minutes ({hm}) must be between 0 and hard limit {holiday_hard_limit}m",
                    },
                )

        if "subject_priorities" in changes:
            for sub, prio in changes["subject_priorities"].items():
                if prio not in ("normal", "main", "difficult"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"code": "INVALID_PRIORITY", "message": f"Priority for {sub} must be normal, main, or difficult"},
                    )

        if "exam_date" in changes:
            ed = date.fromisoformat(changes["exam_date"])
            if ed <= date.today():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "INVALID_EXAM_DATE", "message": "Exam date must be in the future"},
                )

        # Apply settings changes
        stmt_sett = (
            select(StudentStudySettings)
            .where(StudentStudySettings.student_id == student_id)
            .with_for_update()
        )
        res_sett = await db.execute(stmt_sett)
        settings_obj = res_sett.scalars().first()

        # Check version conflict if request was for settings
        if not req.setup_id and req.setup_version is not None and settings_obj:
            if settings_obj.version != req.setup_version:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "SETTINGS_VERSION_CONFLICT",
                        "message": "Study settings were modified concurrently after change request was created.",
                    },
                )

        if settings_obj:
            if "school_day_minutes" in changes:
                settings_obj.school_day_minutes = int(changes["school_day_minutes"])
            if "holiday_minutes" in changes:
                settings_obj.holiday_minutes = int(changes["holiday_minutes"])
            if "subject_priorities" in changes:
                settings_obj.subject_priorities = dict(changes["subject_priorities"])
            settings_obj.version += 1
            settings_obj.updated_at = utcnow()

        # Apply setup changes (exam date, syllabus)
        if req.setup_id:
            stmt_setup = (
                select(StudySetup)
                .where(StudySetup.id == req.setup_id, StudySetup.student_id == student_id)
                .with_for_update()
            )
            res_setup = await db.execute(stmt_setup)
            setup_obj = res_setup.scalars().first()
            if not setup_obj:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study setup not found")
            if req.setup_version is not None and setup_obj.version != req.setup_version:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "SETUP_VERSION_CONFLICT",
                        "message": "Study setup was modified concurrently after change request was created.",
                    },
                )

            if "exam_date" in changes:
                setup_obj.exam_date = date.fromisoformat(changes["exam_date"])
                setup_obj.version += 1
                setup_obj.updated_at = utcnow()

        req.status = "approved"
        req.reviewed_at = utcnow()
        req.reviewed_by_id = parent_id

        # Audit Log
        audit = AuditLog(
            actor_id=parent_id,
            action="parent.approve_student_change_request",
            target_type="student_change_request",
            target_id=str(request_id),
            meta={"changes": changes, "student_id": str(student_id)},
        )
        db.add(audit)
        await db.commit()

        # Regenerate student plan
        _, new_plan_version = await execute_student_plan_regeneration(
            db=db,
            student_id=student_id,
            reason="student_change_request_approved",
        )

        # Notify student
        await NotificationService.trigger_plan_changed(
            db=db,
            user_id=student_id,
            reason="Parent approved your study change request",
            reason_bn="অভিভাবক আপনার পড়ার পরিবর্তনের আবেদন অনুমোদন করেছেন",
        )
        await db.commit()
        await ParentService.invalidate_student_dashboard_cache(student_id)

        return {
            "status": "approved",
            "request_id": str(request_id),
            "student_id": str(student_id),
            "new_plan_version": new_plan_version,
            "reviewed_at": req.reviewed_at.isoformat(),
        }

    @staticmethod
    async def decline_student_change_request(
        db: AsyncSession,
        parent_id: uuid.UUID,
        student_id: uuid.UUID,
        request_id: uuid.UUID,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Parent declines a student-initiated change request."""
        await ParentService.verify_parent_student_link(db, parent_id, student_id)

        stmt = (
            select(StudentChangeRequest)
            .where(
                StudentChangeRequest.id == request_id,
                StudentChangeRequest.student_id == student_id,
            )
            .with_for_update()
        )
        res = await db.execute(stmt)
        req = res.scalars().first()
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student change request not found")

        if req.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Change request has already been processed (status={req.status})",
            )

        req.status = "rejected"
        req.reviewed_at = utcnow()
        req.reviewed_by_id = parent_id

        # Audit Log
        audit = AuditLog(
            actor_id=parent_id,
            action="parent.decline_student_change_request",
            target_type="student_change_request",
            target_id=str(request_id),
            meta={"comment": comment, "student_id": str(student_id)},
        )
        db.add(audit)
        await db.commit()
        await ParentService.invalidate_student_dashboard_cache(student_id)

        return {
            "status": "declined",
            "request_id": str(request_id),
            "student_id": str(student_id),
            "reviewed_at": req.reviewed_at.isoformat(),
            "comment": comment,
        }

    # -------------------------------------------------------------------------
    # One-Tap Undo (Item 2 & 5: Parent-only, optimistic-locked, clamped)
    # -------------------------------------------------------------------------

    @staticmethod
    async def undo_ai_adjustment(
        db: AsyncSession,
        parent_id: uuid.UUID,
        student_id: uuid.UUID,
        adjustment_id: str,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        """Perform one-tap undo of an auto-applied adjustment (Items 2 & 5)."""
        await ParentService.verify_parent_student_link(db, parent_id, student_id)

        stmt = (
            select(StudentStudySettings)
            .where(StudentStudySettings.student_id == student_id)
            .with_for_update()
        )
        res = await db.execute(stmt)
        settings_obj = res.scalars().first()
        if not settings_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student settings not found")

        # Optimistic locking check (Item 5)
        if expected_version is not None and settings_obj.version != expected_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Settings version mismatch (current={settings_obj.version}, expected={expected_version})",
            )

        adj_list = list(settings_obj.ai_adjustments.get("recent_adjustments", []))
        target_adj = None
        for a in adj_list:
            if a.get("adjustment_id") == str(adjustment_id) and not a.get("undone", False):
                target_adj = a
                break

        if not target_adj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active auto-adjustment not found or already undone",
            )

        # Retrieve student class band to clamp restored minutes
        stmt_prof = select(StudentProfile).where(StudentProfile.user_id == student_id)
        res_prof = await db.execute(stmt_prof)
        profile = res_prof.scalars().first()
        class_level = profile.class_level if profile else 10
        class_band = "6-8" if class_level <= 8 else ("9-10" if class_level <= 10 else "11-12")
        max_ceiling = CLASS_BAND_RECOMMENDED_CEILINGS.get(class_band, 180)

        # Restore previous state clamped to limits (Item 5)
        prev_state = target_adj.get("previous_state", {})
        if "school_day_minutes" in prev_state:
            restored_mins = int(prev_state["school_day_minutes"])
            settings_obj.school_day_minutes = max(15, min(restored_mins, max_ceiling))
        if "holiday_minutes" in prev_state:
            restored_h = int(prev_state["holiday_minutes"])
            settings_obj.holiday_minutes = max(15, min(restored_h, max_ceiling + 60))
        if "subject_priorities" in prev_state:
            settings_obj.subject_priorities = dict(prev_state["subject_priorities"])

        target_adj["undone"] = True
        target_adj["undone_at"] = utcnow().isoformat()
        settings_obj.ai_adjustments = {"recent_adjustments": [dict(x) for x in adj_list]}
        flag_modified(settings_obj, "ai_adjustments")
        settings_obj.version += 1
        settings_obj.updated_at = utcnow()

        # Immutable Audit Log
        audit = AuditLog(
            actor_id=parent_id,
            action="ai_planner.undo_adjustment",
            target_type="student_study_settings",
            target_id=str(student_id),
            meta={
                "adjustment_id": str(adjustment_id),
                "reverted_state": prev_state,
                "at": utcnow().isoformat(),
            },
        )
        db.add(audit)
        await db.commit()

        # Regenerate study plan
        _, new_version = await execute_student_plan_regeneration(
            db=db,
            student_id=student_id,
            reason="undo_ai_adjustment",
        )
        await ParentService.invalidate_student_dashboard_cache(student_id)

        return {
            "status": "undone",
            "adjustment_id": str(adjustment_id),
            "reverted_state": prev_state,
            "new_plan_version": new_version,
        }

    @staticmethod
    async def invalidate_student_dashboard_cache(student_id: uuid.UUID) -> None:
        """Invalidate cached student dashboard after modifications (Item 7)."""
        try:
            redis = await get_redis_client()
            await redis.delete(f"thinkbuddy:dashboard:{student_id}")
        except Exception:
            pass
