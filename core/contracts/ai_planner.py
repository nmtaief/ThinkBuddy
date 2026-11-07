"""Shared AI Planner API Contract models (ai-planner/v1.0).

Used across the ThinkBuddy backend, AI provider client, validator, and mock test services.
Conforms strictly to docs/07_AI_PLANNER_API.md.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal
from pydantic import BaseModel, Field

CONTRACT_VERSION_V1_0 = "ai-planner/v1.0"
ALLOWED_CONTRACT_VERSIONS = {CONTRACT_VERSION_V1_0, "ai-planner/v1"}


# ---------------------------------------------------------------------------
# Envelope & Common Structures
# ---------------------------------------------------------------------------

class CommonEnvelope(BaseModel):
    """Common request envelope required on all AI Planner calls."""
    contract_version: str = Field(default=CONTRACT_VERSION_V1_0)
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    idempotency_key: str
    student_ref: str
    as_of: datetime
    locale: Literal["bn", "en"] = "bn"
    mode: Literal["manual", "suggest", "auto_within_limits"] = "suggest"
    seed: int | None = None


# ---------------------------------------------------------------------------
# 1. Plans Propose Models
# ---------------------------------------------------------------------------

class PlanProposeProfile(BaseModel):
    class_level: str
    group: str
    medium: Literal["bn", "en"] = "bn"
    time_zone: str = "Asia/Dhaka"


class PlanProposeLimits(BaseModel):
    min_daily_minutes: int = 30
    max_daily_minutes: int = 180
    max_block_minutes: int = 90
    min_block_minutes: int = 20
    latest_end_time: str = "22:00"
    max_tasks_per_day: int = 6
    max_consecutive_days_per_subject: int = 2
    mock_quiz_max_frequency_days: int = 2


class UnavailableBlock(BaseModel):
    day_of_week: str  # "mon", "tue", etc.
    start_time: str   # "18:00"
    end_time: str     # "19:00"
    label: str = "unavailable"


class PlanProposeSettings(BaseModel):
    school_day_minutes: int
    holiday_minutes: int
    study_window_start: str = "17:00"
    study_window_end: str = "22:00"
    unavailable_blocks: list[UnavailableBlock] = Field(default_factory=list)
    priorities: dict[str, str] = Field(default_factory=dict)
    locked_fields: list[str] = Field(default_factory=list)
    rest_weekday: str | None = None


class CalendarDaySnapshot(BaseModel):
    date: date
    day_type: str
    available_minutes: int
    zero_reason: str | None = None


class ExamSnapshot(BaseModel):
    subject: str
    exam_date: date
    weightage: float = 1.0
    target_grade: str = "A+"


class ChapterSnapshot(BaseModel):
    id: str
    number: int
    title: str
    printed_page_start: int
    printed_page_end: int
    difficulty_factor: float = 1.0
    custom_order: int
    concept_ids: list[str] = Field(default_factory=list)


class SyllabusSnapshot(BaseModel):
    subject: str
    chapters: list[ChapterSnapshot]


class PinnedTaskSnapshot(BaseModel):
    date: date
    task_id: str
    subject: str
    type: str
    chapter_id: str | None = None
    minutes: int
    status: str = "todo"


class PlanProposeRequest(CommonEnvelope):
    profile: PlanProposeProfile
    limits: PlanProposeLimits = Field(default_factory=PlanProposeLimits)
    settings: PlanProposeSettings
    calendar: list[CalendarDaySnapshot]
    exams: list[ExamSnapshot]
    syllabus: list[SyllabusSnapshot]
    progress: dict[str, Any] = Field(default_factory=dict)
    mastery: dict[str, Any] = Field(default_factory=dict)
    signals: dict[str, Any] = Field(default_factory=dict)
    pinned: list[PinnedTaskSnapshot] = Field(default_factory=list)
    previous_plan: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


class ProposedTask(BaseModel):
    temp_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Literal["study", "revision", "homework", "practice", "quiz", "broad", "buffer"]
    subject: str
    chapter_id: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    concept_ids: list[str] = Field(default_factory=list)
    minutes: int
    reason_code: str = "CATCH_UP_MISSED"
    spaced_interval_days: int | None = None
    quiz_request_ref: str | None = None
    refs: dict[str, Any] = Field(default_factory=dict)


class ProposedDay(BaseModel):
    date: date
    tasks: list[ProposedTask] = Field(default_factory=list)


class QuizRequestSpec(BaseModel):
    request_ref: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kind: Literal["diagnostic", "daily", "review", "chapter"] = "daily"
    target_concepts: list[str] = Field(default_factory=list)
    item_count: int = 5
    difficulty_mix: dict[str, float] = Field(default_factory=lambda: {"easy": 0.2, "medium": 0.6, "hard": 0.2})
    item_types: list[str] = Field(default_factory=lambda: ["mcq", "short"])
    mode: Literal["practice", "assessed"] = "practice"
    time_limit_s: int = 600


class PrioritySuggestion(BaseModel):
    subject: str
    current_level: str
    suggested_level: str
    evidence_codes: list[str] = Field(default_factory=list)
    rationale: str = ""


class PlanProposeResponse(BaseModel):
    proposal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_version: str = CONTRACT_VERSION_V1_0
    model_info: dict[str, Any] = Field(default_factory=lambda: {"model_id": "ai-planner-v1.0", "version": "1.0"})
    confidence: float = 0.95
    data_sufficiency: Literal["low", "ok"] = "ok"
    days: list[ProposedDay]
    quiz_requests: list[QuizRequestSpec] = Field(default_factory=list)
    priority_suggestions: list[PrioritySuggestion] = Field(default_factory=list)
    rationale: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 2. Quizzes Propose Models
# ---------------------------------------------------------------------------

class QuizProposeRequest(CommonEnvelope):
    target_date: date
    kind: Literal["diagnostic", "daily", "review", "chapter", "practice"]
    subject: str
    concept_pool: list[str]
    question_bank_availability: dict[str, int] = Field(default_factory=dict)


class QuizProposeResponse(BaseModel):
    proposal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_version: str = CONTRACT_VERSION_V1_0
    quiz_specs: list[QuizRequestSpec]


# ---------------------------------------------------------------------------
# 3. Revision Propose Models
# ---------------------------------------------------------------------------

class RevisionProposeRequest(CommonEnvelope):
    revision_state: dict[str, Any]
    mastery: dict[str, Any]
    window_days: int = 7


class RevisionItemProposal(BaseModel):
    chapter_id: str
    concept_id: str | None = None
    box: int = 1
    due_date: date
    reason_code: str = "SPACED_REVIEW_DUE"


class RevisionProposeResponse(BaseModel):
    proposal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_version: str = CONTRACT_VERSION_V1_0
    revision_items: list[RevisionItemProposal]


# ---------------------------------------------------------------------------
# 4. Questions Draft Models
# ---------------------------------------------------------------------------

class QuestionChunkRef(BaseModel):
    chunk_id: str
    book_title: str
    chapter_title: str
    printed_page: int
    text_snippet: str


class QuestionDraftRequest(CommonEnvelope):
    source_chunks: list[QuestionChunkRef]
    type_mix: list[Literal["mcq", "short", "broad"]] = Field(default_factory=lambda: ["mcq"])
    difficulty: float = 0.5
    language: Literal["bn", "en"] = "bn"
    count: int = 3


class DraftedQuestion(BaseModel):
    temp_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Literal["mcq", "short", "broad"]
    stem: dict[str, Any]
    options: list[dict[str, Any]] = Field(default_factory=list)
    answer_key: dict[str, Any]
    explanation: dict[str, Any]
    rubric: dict[str, Any] = Field(default_factory=dict)
    source_chunk_ids: list[str]
    status: str = "draft"


class QuestionDraftResponse(BaseModel):
    proposal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_version: str = CONTRACT_VERSION_V1_0
    questions: list[DraftedQuestion]


# ---------------------------------------------------------------------------
# 5. Insights Explain Models
# ---------------------------------------------------------------------------

class InsightExplainRequest(CommonEnvelope):
    mastery_trends: dict[str, Any]
    plan_diff_summary: dict[str, Any]


class InsightExplainResponse(BaseModel):
    proposal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_version: str = CONTRACT_VERSION_V1_0
    explanations: dict[str, str]
