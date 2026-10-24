"""Pydantic schemas for Secure Quiz Engine (P04).

Enforces Rule 6: Answer keys and explanations NEVER appear in active student schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Public Question Schemas (Zero Leakage)
# ---------------------------------------------------------------------------


class QuestionOptionPublic(BaseModel):
    """Option with opaque ID and localized text/blocks."""
    id: str = Field(description="Opaque option identifier")
    text: str = Field(description="Localized option text (Bangla/English)")


class QuestionPublic(BaseModel):
    """Question representation served to students during active quizzes.
    
    Zero answer keys, rubrics, or explanations are present.
    """
    id: uuid.UUID
    type: Literal["mcq", "short", "broad"]
    chapter_id: uuid.UUID | None = None
    concept_id: str | None = None
    difficulty: float
    language: str
    stem: dict[str, Any]
    options: list[QuestionOptionPublic] = Field(default_factory=list)


class AttemptItemPublic(BaseModel):
    """Sequential quiz item served to the student."""
    position: int
    nonce: str
    time_limit_s: int | None = None
    question: QuestionPublic


# ---------------------------------------------------------------------------
# Attempt Lifecycle Schemas
# ---------------------------------------------------------------------------


class StartAttemptRequest(BaseModel):
    device_id: str | None = None


class StartAttemptResponse(BaseModel):
    attempt_id: uuid.UUID
    quiz_id: uuid.UUID
    state: str
    mode: str
    started_at: datetime
    deadline_at: datetime
    attempt_token: str
    total_items: int
    current_item: AttemptItemPublic | None = None


class AnswerItemRequest(BaseModel):
    nonce: str
    response: dict[str, Any]  # {"selected_option_id": "opt_..."} or {"text": "..."}
    time_spent_ms: int = Field(default=0, ge=0)


class AnswerItemResponse(BaseModel):
    position: int
    answered: bool
    is_correct: bool | None = None  # None in assessed mode until finalized!
    next_item: AttemptItemPublic | None = None
    has_more: bool = False


class SubmitAttemptResponse(BaseModel):
    attempt_id: uuid.UUID
    state: str
    score: float
    total_possible_score: float
    integrity_score: float
    is_flagged: bool = False
    invalid_reason: str | None = None
    submitted_at: datetime


class AttemptEventRequest(BaseModel):
    type: str  # app_background, focus_lost, screenshot_attempt, multi_window, overlay, clipboard, chat_attempt
    meta: dict[str, Any] = Field(default_factory=dict)


class AttemptEventResponse(BaseModel):
    recorded: bool = True
    integrity_score: float
    state: str  # active, paused, or invalidated


# ---------------------------------------------------------------------------
# Attempt Review Schemas (Strictly After Submission Only)
# ---------------------------------------------------------------------------


class AttemptItemReview(BaseModel):
    position: int
    question: QuestionPublic
    student_response: dict[str, Any] | None
    is_correct: bool | None
    points: float
    correct_answer: dict[str, Any]
    explanation: dict[str, Any]


class AttemptReviewResponse(BaseModel):
    attempt_id: uuid.UUID
    quiz_id: uuid.UUID
    quiz_title: str
    mode: str
    state: str
    score: float
    total_possible_score: float
    integrity_score: float
    started_at: datetime | None
    submitted_at: datetime | None
    items: list[AttemptItemReview]


# ---------------------------------------------------------------------------
# Admin Question Bank Import Schemas
# ---------------------------------------------------------------------------


class QuestionAdminCreate(BaseModel):
    type: Literal["mcq", "short", "broad"]
    chapter_id: uuid.UUID | None = None
    concept_id: str | None = None
    difficulty: float = Field(default=0.5, ge=0.0, le=1.0)
    language: str = "bn"
    stem: dict[str, Any]
    options: list[QuestionOptionPublic] = Field(default_factory=list)
    correct_option_id: str | None = None
    correct_text: str | None = None
    grading_rules: dict[str, Any] = Field(default_factory=dict)
    explanation: dict[str, Any] = Field(default_factory=dict)
    rubric: dict[str, Any] = Field(default_factory=dict)
    source_chunk_ids: list[str] = Field(default_factory=list)
    origin: str = "curated"
    review_status: str = "approved"
    variant_group_id: uuid.UUID | None = None
