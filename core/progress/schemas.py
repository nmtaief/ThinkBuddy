"""Pydantic schemas for student progress, chapter mastery, and spaced revision.

Per Requirement 7:
Parent-facing wording strictly uses 'needs practice' and 'not enough data', NEVER 'weak'.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MasteryStatus = Literal["mastered", "in_progress", "needs_practice", "not_enough_data"]


class ProgressSummaryResponse(BaseModel):
    """Overall learning summary for student or linked parent dashboard."""

    model_config = ConfigDict(from_attributes=True)

    student_id: uuid.UUID
    overall_mastery: float = Field(ge=0.0, le=1.0, description="Overall average mastery (0.0 - 1.0)")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in overall mastery score")
    status: MasteryStatus = Field(description="Parent-safe mastery status: never uses 'weak'")
    status_label_bn: str = Field(description="Bangla label for dashboard display")
    streak_days: int = Field(ge=0, description="Active study streak in consecutive days")
    study_minutes_today: int = Field(ge=0, description="Study minutes recorded today")
    tasks_completed_today: int = Field(ge=0, description="Tasks completed today")
    tasks_total_today: int = Field(ge=0, description="Total planned tasks for today")


class ChapterMasteryItem(BaseModel):
    """Mastery score and status for a single curriculum chapter."""

    model_config = ConfigDict(from_attributes=True)

    chapter_id: uuid.UUID
    chapter_title: str
    chapter_number: int | None = None
    subject: str
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    status: MasteryStatus = Field(description="'mastered', 'in_progress', 'needs_practice', or 'not_enough_data'")
    status_label_bn: str
    last_seen_at: datetime | None = None


class NeedsPracticeTopic(BaseModel):
    """Chapter or topic needing reinforcement (never labeled as 'weak')."""

    model_config = ConfigDict(from_attributes=True)

    chapter_id: uuid.UUID
    chapter_title: str
    subject: str
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    suggested_action: str
    suggested_action_bn: str


class RevisionItemResponse(BaseModel):
    """Spaced repetition item in the Leitner queue."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chapter_id: uuid.UUID
    chapter_title: str
    subject: str
    question_id: uuid.UUID | None = None
    box: int = Field(ge=1, le=5, description="Leitner box level (1 to 5)")
    due_at: datetime
    is_overdue: bool
    last_result: str | None = None


class RevisionReviewRequest(BaseModel):
    """Submission of a spaced revision item review."""

    result: Literal["correct", "wrong"]
    time_spent_ms: int = Field(ge=0, default=0)


class DailyProgressRecord(BaseModel):
    """Historical daily progress metric."""

    model_config = ConfigDict(from_attributes=True)

    date: date
    minutes: int
    tasks_done: int
    tasks_total: int
    quiz_avg: float | None = None
    streak: int
