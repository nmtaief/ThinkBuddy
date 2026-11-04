"""SQLAlchemy domain models for Secure Quiz System (P04).

Per docs/03_DATA_MODEL.md §4, §6 and docs/05_SECURE_QUIZ.md:
- Question & QuestionKey: Strict architectural isolation. Answer keys reside in `question_keys`,
  accessed strictly by server-side auto-grading.
- Quiz & QuizAttempt: State machine (created -> active -> submitted / expired / invalidated).
- AttemptItem: Position-based sequential serving with per-item nonce and deadline enforcement.
- AttemptEvent: Anti-cheat event ingestion (background, screenshot, focus loss, chat attempt).
- BroadSubmission: Long-form / photo response review queue.
- LearningSignal: Written on submit to inform adaptive revision and mastery.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

import core.families.models  # noqa: F401
from core.auth.models import User  # noqa: F401
from core.common.database import Base
from core.curriculum.models import Chapter  # noqa: F401


def utcnow() -> datetime:
    return datetime.now(UTC)


class Question(Base):
    """Question bank item containing stem, non-key options, rubric, and curriculum tags."""

    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # mcq, short, broad
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    concept_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    difficulty: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="bn")
    stem: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # blocks: text, math, image
    options: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )  # [{"id": "opt_...", "text": "..."}]
    rubric: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    explanation: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source_chunk_ids: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    origin: Mapped[str] = mapped_column(String(32), nullable=False, default="curated")
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="approved")
    pool: Mapped[str] = mapped_column(
        String(16), nullable=False, default="both"
    )  # practice, assessed, both
    variant_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    key: Mapped[QuestionKey | None] = relationship(
        "QuestionKey", back_populates="question", uselist=False, cascade="all, delete-orphan"
    )


class QuestionKey(Base):
    """Strictly isolated answer key and grading rules for a question.

    Accessible ONLY by the grading authority service. Never sent to clients or queried in student routes.
    """

    __tablename__ = "question_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    correct_option_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # opaque option id
    correct_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # for short answer
    accepted_answers: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )  # alternative normalized answers
    grading_rules: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    explanation: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    question: Mapped[Question] = relationship("Question", back_populates="key")


class Quiz(Base):
    """Quiz session definition assigned to a student."""

    __tablename__ = "quizzes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Daily Quiz")
    kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default="daily"
    )  # diagnostic, daily, review, chapter, practice
    mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="assessed"
    )  # practice, assessed
    time_limit_s: Mapped[int] = mapped_column(Integer, nullable=False, default=600)
    per_question_limit_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    attempts: Mapped[list[QuizAttempt]] = relationship(
        "QuizAttempt", back_populates="quiz", cascade="all, delete-orphan"
    )


class QuizAttempt(Base):
    """Execution attempt of a quiz with state machine and integrity scoring."""

    __tablename__ = "quiz_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="created"
    )  # created, active, submitted, expired, invalidated
    mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="assessed"
    )  # practice, assessed
    attempt_token: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    integrity_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    invalid_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pause_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unverified_device: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    nonce_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mastery_weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    parent_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parent_flag_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    quiz: Mapped[Quiz] = relationship("Quiz", back_populates="attempts")
    items: Mapped[list[AttemptItem]] = relationship(
        "AttemptItem",
        back_populates="attempt",
        cascade="all, delete-orphan",
        order_by="AttemptItem.position",
    )
    events: Mapped[list[AttemptEvent]] = relationship(
        "AttemptEvent", back_populates="attempt", cascade="all, delete-orphan"
    )


OPEN_ATTEMPT_STATES: tuple[str, ...] = ("created", "active", "warned", "paused")


Index(
    "uq_quiz_attempts_active_student_assessed",
    QuizAttempt.student_id,
    unique=True,
    postgresql_where=text("state IN ('created', 'active', 'warned', 'paused') AND mode = 'assessed'"),
)


class AttemptItem(Base):
    """Specific question assigned to an attempt position with nonce protection."""

    __tablename__ = "attempt_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    served_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )  # {"selected_option_id": "..."} or {"text": "..."}
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    points: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    time_spent_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_recycled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    attempt: Mapped[QuizAttempt] = relationship("QuizAttempt", back_populates="items")
    question: Mapped[Question] = relationship("Question")
    broad_submission: Mapped[BroadSubmission | None] = relationship(
        "BroadSubmission", back_populates="item", uselist=False, cascade="all, delete-orphan"
    )


Index("ix_attempt_items_attempt_pos", AttemptItem.attempt_id, AttemptItem.position, unique=True)


class AttemptEvent(Base):
    """Integrity and security telemetry event recorded during an attempt."""

    __tablename__ = "attempt_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quiz_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # app_background, focus_lost, screenshot_attempt, chat_attempt, etc.
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    attempt: Mapped[QuizAttempt] = relationship("QuizAttempt", back_populates="events")


class BroadSubmission(Base):
    """Subjective broad answer submission pending AI or teacher rubric evaluation."""

    __tablename__ = "broad_submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attempt_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_uris: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    ai_feedback: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    ai_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ai_reviewed"
    )  # ai_reviewed, teacher_pending, teacher_reviewed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    item: Mapped[AttemptItem] = relationship("AttemptItem", back_populates="broad_submission")


class LearningSignal(Base):
    """Learning signal emitted by quiz performance to drive spaced revision & mastery updates."""

    __tablename__ = "learning_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # quiz_wrong, quiz_slow, ai_question, ai_repeat, teacher_flag, task_skipped
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    concept_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    ref_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("student_id", "source", "ref_id", name="uq_learning_signals_student_source_ref"),
    )
