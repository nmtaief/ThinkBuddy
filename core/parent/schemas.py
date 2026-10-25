"""Pydantic schemas for Parent Dashboard, AI chat summaries, and change request controls (P07)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class ParentStudentSummary(BaseModel):
    """Summary of child information for parent overview."""

    student_id: uuid.UUID
    name: str
    class_band: str
    group: str
    avatar_url: str | None = None


class ParentProgressSummary(BaseModel):
    """High-level student progress and study streak metrics."""

    total_minutes_studied: int = 0
    total_tasks_completed: int = 0
    completion_rate_pct: float = 0.0
    active_streak_days: int = 0
    weekly_grace_available: bool = True
    quiz_score_avg: float | None = None


class ParentMasterySubjectSummary(BaseModel):
    """Non-labeling, growth-oriented subject mastery status for parents (Item 7)."""

    subject: str
    mastery_score: float
    confidence: float
    status: str  # "needs_practice", "in_progress", "mastered"
    status_bn: str  # "অনুশীলন প্রয়োজন", "অগ্রগতি চলমান", "দক্ষতা অর্জিত"
    focus_areas: list[str] = Field(default_factory=list)


class ParentRevisionSummary(BaseModel):
    """Spaced repetition queue status for the student."""

    due_count: int = 0
    boxes_distribution: dict[str, int] = Field(default_factory=dict)


class ParentExamCountdown(BaseModel):
    """Upcoming exam dates and days remaining."""

    subject: str
    exam_name: str
    exam_date: date
    days_remaining: int


class ParentAiSuggestionView(BaseModel):
    """AI planner suggestion surfaced for parent review with localized, non-labeling reasons."""

    id: uuid.UUID
    student_id: uuid.UUID
    type: str  # "ai_priority_suggestion" | "ai_minute_suggestion"
    subject: str | None = None
    field: str | None = None
    current_value: Any = None
    suggested_value: Any = None
    rationale: str  # English growth-oriented reason (no deficit labeling)
    rationale_bn: str  # Bengali growth-oriented reason
    evidence_codes: list[str] = Field(default_factory=list)
    status: str = "pending"
    created_at: datetime
    expires_at: datetime | None = None


class ParentAiAdjustmentView(BaseModel):
    """Auto-applied adjustment with one-tap undo support (Item 2)."""

    adjustment_id: str
    type: str
    summary: str
    summary_bn: str
    applied_at: str
    can_undo: bool = True


class ParentChatTopicSummary(BaseModel):
    """Topic-level AI chat interaction summary for parents (strictly no raw transcripts - Deliverable 12)."""

    topic: str
    subject: str | None = None
    question_count: int = 1
    last_asked_at: datetime | None = None


class StudentDashboardResponse(BaseModel):
    """Complete consolidated dashboard for a single student."""

    student: ParentStudentSummary
    progress: ParentProgressSummary
    subjects_mastery: list[ParentMasterySubjectSummary]
    spaced_revision: ParentRevisionSummary
    upcoming_exams: list[ParentExamCountdown]
    ai_suggestions: list[ParentAiSuggestionView]
    recent_ai_adjustments: list[ParentAiAdjustmentView]
    chat_topics: list[ParentChatTopicSummary] = Field(default_factory=list)
    adaptive_mode: str = "suggest"


class ParentOverviewResponse(BaseModel):
    """Consolidated parent dashboard across all linked students."""

    parent_id: uuid.UUID
    students: list[StudentDashboardResponse]


class ReviewStudentChangeRequestBody(BaseModel):
    """Optional review payload when parent approves or declines student change request."""

    comment: str | None = None


class ReviewStudentChangeRequestResponse(BaseModel):
    """Response returned upon parent approving or declining a student change request."""

    status: str  # "approved" | "declined"
    request_id: uuid.UUID
    student_id: uuid.UUID
    reviewed_at: datetime
    new_plan_version: int | None = None
    comment: str | None = None

