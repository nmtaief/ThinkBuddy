"""Administrative Analytics Service for Weakness/Strength Intelligence and Chatbot LLM Usage.

Provides aggregated and per-student mastery analysis, learning signals telemetry,
and real-time LLM token usage tracking for the ThinkBuddy Admin Panel.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.auth.models import User
from core.families.models import StudentProfile
from core.chat.models import ChatMessage, ChatSession
from core.curriculum.models import Chapter, Book
from core.progress.models import Mastery, RevisionItem
from core.progress.service import ProgressService
from core.progress.weights import DEFAULT_MASTERY_CONFIG
from core.quiz.models import LearningSignal

logger = logging.getLogger("thinkbuddy.admin.analytics")


# ============================================================================
# Pydantic Schemas for Admin Analytics
# ============================================================================

class SubjectWeaknessSummary(BaseModel):
    subject_slug: str
    subject_name_bn: str
    subject_name_en: str
    average_mastery: float
    average_confidence: float
    total_signals: int
    struggling_students_count: int
    mastered_students_count: int


class StrugglingChapterSummary(BaseModel):
    chapter_id: uuid.UUID
    chapter_name_bn: str
    chapter_name_en: str
    chapter_number: int
    subject_slug: str
    class_level: int
    average_mastery: float
    students_count: int
    status: str


class WeaknessStrengthOverviewResponse(BaseModel):
    total_students: int
    total_signals: int
    overall_average_mastery: float
    distribution: dict[str, int] = Field(
        description="Count of chapters across students: mastered, needs_practice, not_enough_data"
    )
    subjects: list[SubjectWeaknessSummary]
    top_struggling_chapters: list[StrugglingChapterSummary]
    top_struggling_concepts: list[dict[str, Any]]


class StudentAnalyticsListItem(BaseModel):
    id: uuid.UUID
    name: str
    role: str
    class_level: int | None
    medium: str | None
    group: str | None
    weak_subjects: list[str]
    focus_subjects: list[str]
    onboarding_completed: bool
    overall_mastery: float
    confidence: float
    status: str
    signals_count: int
    revision_items_due: int


class StudentDetailAnalyticsResponse(BaseModel):
    student_id: uuid.UUID
    name: str
    class_level: int | None
    medium: str | None
    group: str | None
    weak_subjects: list[str]
    focus_subjects: list[str]
    overall_mastery: float
    overall_confidence: float
    chapters: list[dict[str, Any]]
    top_weaknesses: list[dict[str, Any]]
    top_strengths: list[dict[str, Any]]
    recent_signals: list[dict[str, Any]]


class LLMUsageDay(BaseModel):
    date: str
    messages_count: int
    tokens_in: int
    tokens_out: int
    total_tokens: int
    estimated_cost_usd: float


class LLMUsageAnalyticsResponse(BaseModel):
    total_messages: int
    total_tokens_in: int
    total_tokens_out: int
    total_tokens: int
    average_latency_ms: int
    estimated_cost_usd: float
    estimated_cost_bdt: float
    by_model: dict[str, dict[str, Any]]
    daily_trend: list[LLMUsageDay]


class LearningSignalItemResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    source: str
    chapter_id: uuid.UUID | None
    concept_id: str | None
    weight: float
    ref_id: str | None
    created_at: datetime


class LearningSignalsQueryResponse(BaseModel):
    total: int
    items: list[LearningSignalItemResponse]


# ============================================================================
# Service Functions
# ============================================================================

async def get_weakness_strength_overview(
    db: AsyncSession,
    class_level: int | None = None,
    subject_slug: str | None = None,
) -> WeaknessStrengthOverviewResponse:
    """Aggregate learning mastery, struggles, and subject summaries across the platform."""
    # 1. Total students count
    student_query = select(func.count(User.id)).where(User.role == "student")
    total_students_res = await db.execute(student_query)
    total_students = total_students_res.scalar() or 0

    # 2. Total learning signals count
    signal_query = select(func.count(LearningSignal.id))
    total_signals_res = await db.execute(signal_query)
    total_signals = total_signals_res.scalar() or 0

    # 3. Overall mastery scores across all mastery records
    mastery_stmt = select(Mastery).options(selectinload(Mastery.chapter).selectinload(Chapter.book))
    mastery_res = await db.execute(mastery_stmt)
    all_masteries = list(mastery_res.scalars().all())

    distribution = {
        "mastered": 0,
        "needs_practice": 0,
        "not_enough_data": 0,
    }

    total_score_sum = 0.0
    valid_mastery_count = 0

    # Group by subject and chapter
    subject_stats: dict[str, dict[str, Any]] = {}
    chapter_stats: dict[uuid.UUID, dict[str, Any]] = {}

    for m in all_masteries:
        total_score_sum += m.score
        valid_mastery_count += 1

        # Classify according to standard adaptive rules
        if m.confidence < DEFAULT_MASTERY_CONFIG.min_confidence_threshold:
            status_str = "not_enough_data"
        elif m.score >= DEFAULT_MASTERY_CONFIG.mastery_threshold:
            status_str = "mastered"
        else:
            status_str = "needs_practice"
        distribution[status_str] += 1

        # Subject aggregation
        chap = m.chapter
        if chap and chap.book:
            book = chap.book
            slug = book.subject or "general"
            if slug not in subject_stats:
                subject_stats[slug] = {
                    "slug": slug,
                    "name_bn": book.title or slug,
                    "name_en": slug.capitalize(),
                    "scores": [],
                    "confs": [],
                    "signals": 0,
                    "struggling": 0,
                    "mastered": 0,
                }
            subject_stats[slug]["scores"].append(m.score)
            subject_stats[slug]["confs"].append(m.confidence)
            if status_str == "needs_practice":
                subject_stats[slug]["struggling"] += 1
            elif status_str == "mastered":
                subject_stats[slug]["mastered"] += 1

        # Chapter aggregation
        if chap:
            if chap.id not in chapter_stats:
                chapter_stats[chap.id] = {
                    "id": chap.id,
                    "name_bn": chap.title,
                    "name_en": chap.title,
                    "number": chap.number,
                    "subject_slug": chap.book.subject if chap.book else "general",
                    "class_level": chap.book.class_level if chap.book else 8,
                    "scores": [],
                    "confs": [],
                    "students": set(),
                }
            chapter_stats[chap.id]["scores"].append(m.score)
            chapter_stats[chap.id]["confs"].append(m.confidence)
            chapter_stats[chap.id]["students"].add(m.student_id)

    overall_avg_mastery = (
        round(total_score_sum / max(1, valid_mastery_count), 4) if valid_mastery_count > 0 else 0.5
    )

    # Convert subject stats
    subjects_list: list[SubjectWeaknessSummary] = []
    for s in subject_stats.values():
        scores = s["scores"]
        confs = s["confs"]
        avg_score = round(sum(scores) / max(1, len(scores)), 4) if scores else 0.5
        avg_conf = round(sum(confs) / max(1, len(confs)), 4) if confs else 0.0
        subjects_list.append(
            SubjectWeaknessSummary(
                subject_slug=s["slug"],
                subject_name_bn=s["name_bn"],
                subject_name_en=s["name_en"],
                average_mastery=avg_score,
                average_confidence=avg_conf,
                total_signals=len(scores),
                struggling_students_count=s["struggling"],
                mastered_students_count=s["mastered"],
            )
        )

    # Top struggling chapters (lowest average mastery with at least 1 student)
    sorted_chapters = sorted(
        chapter_stats.values(),
        key=lambda c: sum(c["scores"]) / max(1, len(c["scores"])),
    )

    top_chapters: list[StrugglingChapterSummary] = []
    for c in sorted_chapters[:8]:
        avg_chap_score = round(sum(c["scores"]) / max(1, len(c["scores"])), 4)
        status_text = "needs_practice" if avg_chap_score < 0.6 else ("mastered" if avg_chap_score >= 0.8 else "in_progress")
        top_chapters.append(
            StrugglingChapterSummary(
                chapter_id=c["id"],
                chapter_name_bn=c["name_bn"],
                chapter_name_en=c["name_en"],
                chapter_number=c["number"],
                subject_slug=c["subject_slug"],
                class_level=c["class_level"],
                average_mastery=avg_chap_score,
                students_count=len(c["students"]),
                status=status_text,
            )
        )

    # Top struggling concept signals
    sig_stmt = (
        select(LearningSignal.concept_id, func.count(LearningSignal.id).label("cnt"))
        .where(LearningSignal.concept_id.isnot(None))
        .where(LearningSignal.source.in_(["quiz_wrong", "practice_wrong", "quiz_slow", "ai_repeat"]))
        .group_by(LearningSignal.concept_id)
        .order_by(desc("cnt"))
        .limit(6)
    )
    sig_res = await db.execute(sig_stmt)
    top_concepts = [
        {"concept": row[0], "negative_signals_count": row[1]}
        for row in sig_res.all()
    ]

    return WeaknessStrengthOverviewResponse(
        total_students=total_students,
        total_signals=total_signals,
        overall_average_mastery=overall_avg_mastery,
        distribution=distribution,
        subjects=subjects_list,
        top_struggling_chapters=top_chapters,
        top_struggling_concepts=top_concepts,
    )


async def list_students_analytics(
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> list[StudentAnalyticsListItem]:
    """Retrieve all students with their mastery standing, weak/focus subjects, and due revisions."""
    stmt = (
        select(User)
        .where(User.role == "student")
        .options(selectinload(User.student_profile))
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await db.execute(stmt)
    students = list(res.scalars().all())

    output: list[StudentAnalyticsListItem] = []
    for s in students:
        prof = s.student_profile

        # Aggregate student masteries
        m_stmt = select(Mastery).where(Mastery.student_id == s.id)
        m_res = await db.execute(m_stmt)
        student_masteries = list(m_res.scalars().all())

        if student_masteries:
            avg_score = round(sum(m.score for m in student_masteries) / len(student_masteries), 4)
            avg_conf = round(sum(m.confidence for m in student_masteries) / len(student_masteries), 4)
        else:
            avg_score = 0.5
            avg_conf = 0.0

        if avg_conf < DEFAULT_MASTERY_CONFIG.min_confidence_threshold:
            status_text = "not_enough_data"
        elif avg_score >= DEFAULT_MASTERY_CONFIG.mastery_threshold:
            status_text = "mastered"
        else:
            status_text = "needs_practice"

        # Signal count
        sig_cnt_stmt = select(func.count(LearningSignal.id)).where(LearningSignal.student_id == s.id)
        sig_cnt_res = await db.execute(sig_cnt_stmt)
        sig_cnt = sig_cnt_res.scalar() or 0

        # Due revision items
        now_dt = datetime.now(UTC)
        rev_cnt_stmt = select(func.count(RevisionItem.id)).where(
            RevisionItem.student_id == s.id,
            RevisionItem.next_review_at <= now_dt,
        )
        rev_cnt_res = await db.execute(rev_cnt_stmt)
        rev_cnt = rev_cnt_res.scalar() or 0

        output.append(
            StudentAnalyticsListItem(
                id=s.id,
                name=s.name or "Student",
                role=s.role,
                class_level=prof.class_level if prof else 8,
                medium=prof.medium if prof else "bangla",
                group=prof.group if prof else "general",
                weak_subjects=prof.weak_subjects if prof and prof.weak_subjects else [],
                focus_subjects=prof.focus_subjects if prof and prof.focus_subjects else [],
                onboarding_completed=prof.onboarding_completed if prof else False,
                overall_mastery=avg_score,
                confidence=avg_conf,
                status=status_text,
                signals_count=sig_cnt,
                revision_items_due=rev_cnt,
            )
        )

    return output


async def get_student_detail_analytics(
    student_id: uuid.UUID,
    db: AsyncSession,
) -> StudentDetailAnalyticsResponse | None:
    """Retrieve fine-grained mastery, top strengths & weaknesses, and recent signals for a student."""
    user_stmt = (
        select(User)
        .where(User.id == student_id)
        .options(selectinload(User.student_profile))
    )
    user_res = await db.execute(user_stmt)
    student = user_res.scalar_one_or_none()
    if not student:
        return None

    prof = student.student_profile

    # Mastery list
    m_stmt = (
        select(Mastery)
        .where(Mastery.student_id == student_id)
        .options(selectinload(Mastery.chapter).selectinload(Chapter.book))
        .order_by(Mastery.score.asc())
    )
    m_res = await db.execute(m_stmt)
    masteries = list(m_res.scalars().all())

    chapters_data: list[dict[str, Any]] = []
    top_weak: list[dict[str, Any]] = []
    top_strong: list[dict[str, Any]] = []

    total_score = 0.0
    total_conf = 0.0

    for m in masteries:
        total_score += m.score
        total_conf += m.confidence
        c = m.chapter
        sub_name = c.book.title if c and c.book else "সাধারণ"
        chap_name = c.title if c else "অধ্যায়"

        item = {
            "chapter_id": str(m.chapter_id),
            "chapter_name": chap_name,
            "subject": sub_name,
            "score": round(m.score, 4),
            "confidence": round(m.confidence, 4),
            "status": "mastered" if m.score >= 0.8 else ("needs_practice" if m.score < 0.6 else "in_progress"),
            "last_seen_at": m.last_seen_at.isoformat() if m.last_seen_at else None,
        }
        chapters_data.append(item)

        if m.score < 0.6 and len(top_weak) < 5:
            top_weak.append(item)

    # Sort descending for top strengths
    strong_candidates = sorted(masteries, key=lambda x: x.score, reverse=True)
    for m in strong_candidates:
        if m.score >= 0.75 and len(top_strong) < 5:
            c = m.chapter
            top_strong.append({
                "chapter_id": str(m.chapter_id),
                "chapter_name": c.title if c else "অধ্যায়",
                "subject": c.book.title if c and c.book else "সাধারণ",
                "score": round(m.score, 4),
                "confidence": round(m.confidence, 4),
            })

    overall_score = round(total_score / max(1, len(masteries)), 4) if masteries else 0.5
    overall_conf = round(total_conf / max(1, len(masteries)), 4) if masteries else 0.0

    # Recent signals
    sig_stmt = (
        select(LearningSignal)
        .where(LearningSignal.student_id == student_id)
        .order_by(LearningSignal.at.desc())
        .limit(15)
    )
    sig_res = await db.execute(sig_stmt)
    signals = [
        {
            "id": str(s.id),
            "source": s.source,
            "weight": s.weight,
            "ref_id": s.ref_id,
            "at": s.at.isoformat() if s.at else None,
        }
        for s in sig_res.scalars().all()
    ]

    return StudentDetailAnalyticsResponse(
        student_id=student.id,
        name=student.name or "Student",
        class_level=prof.class_level if prof else 8,
        medium=prof.medium if prof else "bangla",
        group=prof.group if prof else "general",
        weak_subjects=prof.weak_subjects if prof and prof.weak_subjects else [],
        focus_subjects=prof.focus_subjects if prof and prof.focus_subjects else [],
        overall_mastery=overall_score,
        overall_confidence=overall_conf,
        chapters=chapters_data,
        top_weaknesses=top_weak,
        top_strengths=top_strong,
        recent_signals=signals,
    )


async def get_llm_usage_analytics(
    db: AsyncSession,
    days: int = 14,
) -> LLMUsageAnalyticsResponse:
    """Analyze real LLM Chatbot token telemetry, latency, and cost estimates."""
    cutoff = datetime.now(UTC) - timedelta(days=days)

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.created_at >= cutoff)
        .order_by(ChatMessage.created_at.asc())
    )
    res = await db.execute(stmt)
    messages = list(res.scalars().all())

    total_tokens_in = sum(m.tokens_in for m in messages)
    total_tokens_out = sum(m.tokens_out for m in messages)
    total_tokens = total_tokens_in + total_tokens_out
    total_messages = len(messages)

    latencies = [m.latency_ms for m in messages if m.latency_ms > 0]
    avg_latency = int(sum(latencies) / max(1, len(latencies))) if latencies else 280

    # Model breakdowns
    by_model: dict[str, dict[str, Any]] = {}
    for m in messages:
        mod = m.model or "default_model"
        if mod not in by_model:
            by_model[mod] = {"messages": 0, "tokens_in": 0, "tokens_out": 0, "total_tokens": 0}
        by_model[mod]["messages"] += 1
        by_model[mod]["tokens_in"] += m.tokens_in
        by_model[mod]["tokens_out"] += m.tokens_out
        by_model[mod]["total_tokens"] += (m.tokens_in + m.tokens_out)

    # Cost calculation: benchmark standard blended $0.15 / 1M input, $0.60 / 1M output (Flash 2.5 rates)
    cost_usd = (total_tokens_in * 0.15 / 1_000_000.0) + (total_tokens_out * 0.60 / 1_000_000.0)
    cost_bdt = cost_usd * 122.0  # Approx BDT conversion

    # Group by day
    daily_groups: dict[str, dict[str, int]] = {}
    for m in messages:
        day_str = m.created_at.strftime("%Y-%m-%d")
        if day_str not in daily_groups:
            daily_groups[day_str] = {"messages": 0, "tokens_in": 0, "tokens_out": 0}
        daily_groups[day_str]["messages"] += 1
        daily_groups[day_str]["tokens_in"] += m.tokens_in
        daily_groups[day_str]["tokens_out"] += m.tokens_out

    daily_trend: list[LLMUsageDay] = []
    for day_str, stats in sorted(daily_groups.items()):
        t_in = stats["tokens_in"]
        t_out = stats["tokens_out"]
        t_tot = t_in + t_out
        d_cost = (t_in * 0.15 / 1_000_000.0) + (t_out * 0.60 / 1_000_000.0)
        daily_trend.append(
            LLMUsageDay(
                date=day_str,
                messages_count=stats["messages"],
                tokens_in=t_in,
                tokens_out=t_out,
                total_tokens=t_tot,
                estimated_cost_usd=round(d_cost, 6),
            )
        )

    return LLMUsageAnalyticsResponse(
        total_messages=total_messages,
        total_tokens_in=total_tokens_in,
        total_tokens_out=total_tokens_out,
        total_tokens=total_tokens,
        average_latency_ms=avg_latency,
        estimated_cost_usd=round(cost_usd, 4),
        estimated_cost_bdt=round(cost_bdt, 2),
        by_model=by_model,
        daily_trend=daily_trend,
    )


async def query_learning_signals(
    db: AsyncSession,
    student_id: uuid.UUID | None = None,
    source: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> LearningSignalsQueryResponse:
    """Query recent learning signals with optional student/source filtering."""
    query = select(LearningSignal)
    if student_id:
        query = query.where(LearningSignal.student_id == student_id)
    if source:
        query = query.where(LearningSignal.source == source)

    count_stmt = select(func.count(LearningSignal.id))
    if student_id:
        count_stmt = count_stmt.where(LearningSignal.student_id == student_id)
    if source:
        count_stmt = count_stmt.where(LearningSignal.source == source)

    total_res = await db.execute(count_stmt)
    total = total_res.scalar() or 0

    query = query.order_by(LearningSignal.at.desc()).limit(limit).offset(offset)
    res = await db.execute(query)
    signals = list(res.scalars().all())

    items = [
        LearningSignalItemResponse(
            id=s.id,
            student_id=s.student_id,
            source=s.source,
            chapter_id=s.chapter_id,
            concept_id=s.concept_id,
            weight=s.weight,
            ref_id=s.ref_id,
            created_at=s.at or datetime.now(UTC),
        )
        for s in signals
    ]

    return LearningSignalsQueryResponse(total=total, items=items)
