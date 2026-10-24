"""Pydantic schemas for study setup, syllabus items, versioned plan, and today payload."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SyllabusItemInput(BaseModel):
    """Chapter inclusion and order specification."""

    chapter_id: uuid.UUID
    included: bool = True
    custom_order: int = Field(ge=1, description="1-indexed sequence order")
    weight: float = Field(default=1.0, ge=0.1, le=5.0, description="Relative priority weight")
    custom_difficulty: float | None = Field(default=None, ge=0.5, le=3.0)
    mastery: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Chapter mastery score (0-1), None = unknown"
    )


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
    mastery: float | None = None


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
    setup_id: uuid.UUID | None = None
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


# ============================================================================
# Dynamic Configuration Layer Schemas (Admin Policies, Holidays, Settings)
# ============================================================================


class ObservanceResponse(BaseModel):
    """Observance catalog entry."""

    key: str
    name_bn: str
    name_en: str
    description: str | None = None


class CreateAdminPolicyRequest(BaseModel):
    """Admin creation of a class band policy."""

    class_band: str = Field(pattern="^(6-8|9-10|11-12)$")
    group: str = Field(default="general", pattern="^(general|science|humanities|business_studies)$")
    min_daily_minutes: int = Field(default=0, ge=0, le=600)
    max_daily_minutes: int = Field(default=600, ge=0, le=600)
    recommended_daily_minutes: int = Field(default=90, ge=0, le=600)
    max_block_minutes: int = Field(default=90, ge=15, le=180)
    latest_end_time: str = Field(default="22:00", pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    weekly_off_days: list[str] = Field(default_factory=lambda: ["fri", "sat"])
    planner_parameters: dict[str, Any] = Field(default_factory=dict)


class UpdateAdminPolicyRequest(BaseModel):
    """Admin update to an existing draft policy."""

    min_daily_minutes: int | None = Field(default=None, ge=0, le=600)
    max_daily_minutes: int | None = Field(default=None, ge=0, le=600)
    recommended_daily_minutes: int | None = Field(default=None, ge=0, le=600)
    max_block_minutes: int | None = Field(default=None, ge=15, le=180)
    latest_end_time: str | None = Field(default=None, pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    weekly_off_days: list[str] | None = None
    planner_parameters: dict[str, Any] | None = None
    expected_version: int = Field(description="Optimistic concurrency version check")


class AdminPolicyResponse(BaseModel):
    """Admin policy details."""

    id: uuid.UUID
    class_band: str
    group: str
    version: int
    status: str
    min_daily_minutes: int
    max_daily_minutes: int
    recommended_daily_minutes: int
    max_block_minutes: int
    latest_end_time: str
    weekly_off_days: list[str]
    planner_parameters: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PolicyImpactPreviewResponse(BaseModel):
    """Impact preview for admin policy modification."""

    policy_id: uuid.UUID
    class_band: str
    group: str
    affected_students_count: int
    affected_student_ids: list[uuid.UUID]
    affected_active_plans_count: int


class CreateHolidayRequest(BaseModel):
    """Holiday creation request."""

    start_date: date
    end_date: date
    name: str = Field(min_length=1, max_length=255)
    holiday_type: str = Field(default="national", pattern="^(national|religious|academic|weekly)$")
    study_blackout: bool = False
    observance_key: str | None = None
    status: str = Field(default="draft", pattern="^(draft|published)$")


class HolidayImportRequest(BaseModel):
    """Bulk import payload for holiday calendar."""

    holidays: list[CreateHolidayRequest] = Field(min_length=1)


class UpdateHolidayRequest(BaseModel):
    """Holiday update request."""

    start_date: date | None = None
    end_date: date | None = None
    name: str | None = None
    holiday_type: str | None = Field(default=None, pattern="^(national|religious|academic|weekly)$")
    study_blackout: bool | None = None
    observance_key: str | None = None
    expected_version: int = Field(description="Optimistic concurrency version check")


class HolidayResponse(BaseModel):
    """Holiday details."""

    id: uuid.UUID
    start_date: date
    end_date: date
    name: str
    holiday_type: str
    study_blackout: bool
    observance_key: str | None = None
    verified: bool
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class HolidayImpactPreviewResponse(BaseModel):
    """Impact preview for holiday modification."""

    holiday_id: uuid.UUID
    start_date: date
    end_date: date
    study_blackout: bool
    affected_students_count: int
    affected_student_ids: list[uuid.UUID]
    affected_active_plans_count: int


class RecurringUnavailableBlock(BaseModel):
    """Recurring weekly unavailable window (coaching, tuition, etc.)."""

    day_of_week: str = Field(pattern="^(sat|sun|mon|tue|wed|thu|fri)$")
    start_time: str = Field(pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    end_time: str = Field(pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    label: str = Field(min_length=1, max_length=100)


class CustomBlackoutDate(BaseModel):
    """Parent custom blackout date range with coarse reason choices only (no free text)."""

    start_date: date
    end_date: date
    reason: Literal["travel", "family_event", "school_event", "other"]


class UpdateStudentStudySettingsRequest(BaseModel):
    """Parent-configured study settings for a student."""

    school_day_minutes: int = Field(ge=0, le=600, description="Minutes on school days")
    holiday_minutes: int = Field(ge=0, le=600, description="Minutes on holidays/weekends")
    study_window_start: str = Field(default="17:00", pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    study_window_end: str = Field(default="21:30", pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    recurring_unavailable_blocks: list[RecurringUnavailableBlock] = Field(default_factory=list)
    blocked_observance_keys: list[str] = Field(default_factory=list)
    custom_blackout_dates: list[CustomBlackoutDate] = Field(default_factory=list)
    subject_priorities: dict[str, str] = Field(
        default_factory=dict, description="subject -> normal/main/difficult"
    )
    rest_weekday: str | None = Field(
        default=None, description="Designated rest weekday (e.g. fri, sat, sun)"
    )
    adaptive_mode: Literal["manual", "suggest", "auto_within_limits"] = Field(
        default="suggest", description="Adaptive planning mode"
    )
    ai_adjustments: dict[str, Any] = Field(
        default_factory=dict, description="Versioned AI adjustment overrides"
    )
    parent_locked_fields: list[str] = Field(
        default_factory=list, description="Fields explicitly locked by parent against AI overrides"
    )
    expected_version: int | None = Field(
        default=None, description="Current version for optimistic concurrency"
    )


class StudentStudySettingsResponse(BaseModel):
    """Resolved student study settings with clamping notices and admin bounds."""

    id: uuid.UUID
    student_id: uuid.UUID
    school_day_minutes: int
    holiday_minutes: int
    study_window_start: str
    study_window_end: str
    recurring_unavailable_blocks: list[dict[str, Any]]
    blocked_observance_keys: list[str]
    custom_blackout_dates: list[dict[str, Any]]
    subject_priorities: dict[str, str]
    rest_weekday: str | None = None
    adaptive_mode: str = "suggest"
    ai_adjustments: dict[str, Any] = Field(default_factory=dict)
    parent_locked_fields: list[str] = Field(default_factory=list)
    version: int
    clamping_notices: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommended_daily_minutes: int | None = None
    admin_hard_limits: dict[str, Any] | None = None
