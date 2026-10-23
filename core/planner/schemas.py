"""Pydantic schemas for study setup, syllabus items, versioned plan, and today payload."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class SyllabusItemInput(BaseModel):
    """Chapter inclusion and order specification."""

    chapter_id: uuid.UUID
    included: bool = True
    custom_order: int = Field(ge=1, description="1-indexed sequence order")
    weight: float = Field(default=1.0, ge=0.1, le=5.0, description="Relative priority weight")
    custom_difficulty: float | None = Field(default=None, ge=0.5, le=3.0)


class SyllabusItemSummary(BaseModel):
    """Summary of a chapter in the syllabus."""

    id: uuid.UUID
    chapter_id: uuid.UUID
    chapter_number: int | None = None
    chapter_title: str | None = None
    included: bool
    custom_order: int
    weight: float
    custom_difficulty: float | None = None


class UpsertStudySetupRequest(BaseModel):
    """Parent configuration for a subject's study syllabus and exam."""

    exam_name: str = Field(min_length=1, max_length=255)
    exam_date: date
    syllabus: list[SyllabusItemInput] = Field(min_length=0, max_length=100)
    expected_version: int | None = Field(
        default=None, description="Current version for optimistic concurrency"
    )
    daily_study_minutes: int | None = Field(
        default=None, ge=15, le=480, description="Override student daily budget"
    )
    available_days: list[str] | None = Field(
        default=None, description="Available study days (e.g. ['sat', 'sun', ...])"
    )


class UpdateDailyMinutesRequest(BaseModel):
    """Parent update to student-level shared daily study minutes budget."""

    daily_minutes: int = Field(ge=15, le=480, description="Student daily study budget in minutes")


class DailyMinutesResponse(BaseModel):
    """Response returning student's daily study minutes budget."""

    student_id: uuid.UUID
    daily_minutes: int


class StudySetupResponse(BaseModel):
    """Study setup details for a subject."""

    id: uuid.UUID
    student_id: uuid.UUID
    subject: str
    exam_name: str
    exam_date: date
    active_plan_version: int
    version: int
    syllabus: list[SyllabusItemSummary]
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class StudentChangeRequestInput(BaseModel):
    """Student proposed modification to study schedule or order."""

    requested_changes: dict[str, Any] = Field(description="Proposed schedule adjustments")


class StudentChangeRequestResponse(BaseModel):
    """Change request submission record."""

    id: uuid.UUID
    setup_id: uuid.UUID
    student_id: uuid.UUID
    requested_changes: dict[str, Any]
    status: str
    created_at: datetime


class TaskRefs(BaseModel):
    """Task citation and guidelines."""

    book_id: str | None = None
    book_title: str | None = None
    chapter_number: int | None = None
    chapter_title: str | None = None
    printed_page_start: int | None = None
    printed_page_end: int | None = None
    guideline: str = ""


class TaskResponse(BaseModel):
    """Study, revision, homework, or quiz task."""

    id: uuid.UUID
    plan_day_id: uuid.UUID
    student_id: uuid.UUID
    subject: str
    type: str
    chapter_id: uuid.UUID | None = None
    refs: dict[str, Any]
    est_minutes: int
    status: str
    source: str
    completed_at: datetime | None = None


class PlanDayResponse(BaseModel):
    """Daily study plan allocation."""

    date: date
    planned_minutes: int
    day_type: str
    tasks: list[TaskResponse]


class PlanResponse(BaseModel):
    """Full versioned study plan."""

    setup_id: uuid.UUID
    student_id: uuid.UUID
    version: int
    generated_at: datetime
    reason: str
    status: str
    days: list[PlanDayResponse]
    warnings: list[str] = Field(default_factory=list)


class TodayHomePayloadResponse(BaseModel):
    """Home screen learning loop payload (Product Flows §4.2 / Rule 4)."""

    date: date
    student_id: uuid.UUID
    study_tasks: list[TaskResponse]
    revision_tasks: list[TaskResponse]
    homework_tasks: list[TaskResponse]
    quiz_tasks: list[TaskResponse]
    total_planned_minutes: int
    completed_minutes: int
    completion_percentage: float
    exam_countdown_days: dict[str, int]
    streak: int = 0


class UpdateTaskStatusRequest(BaseModel):
    """Task status update payload."""

    status: str = Field(pattern="^(todo|in_progress|done|skipped)$")
