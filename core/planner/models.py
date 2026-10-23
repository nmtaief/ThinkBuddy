"""SQLAlchemy database models for study setups, syllabus items, versioned plans, and tasks."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.common.database import Base

if TYPE_CHECKING:
    from core.auth.models import User
    from core.curriculum.models import Chapter


def utcnow() -> datetime:
    return datetime.now(UTC)


class StudySetup(Base):
    """Parent configuration of syllabus, exam date, and chapter order for a student and subject."""

    __tablename__ = "study_setups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    exam_name: Mapped[str] = mapped_column(String(255), nullable=False)
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    set_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    active_plan_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )  # Optimistic concurrency
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    # Relationships
    student: Mapped[User] = relationship("User", foreign_keys=[student_id])
    set_by_user: Mapped[User] = relationship("User", foreign_keys=[set_by_user_id])
    syllabus_items: Mapped[list[SyllabusItem]] = relationship(
        "SyllabusItem",
        back_populates="setup",
        cascade="all, delete-orphan",
        order_by="SyllabusItem.custom_order",
    )
    plans: Mapped[list[Plan]] = relationship(
        "Plan", back_populates="setup", cascade="all, delete-orphan", order_by="Plan.version"
    )
    change_requests: Mapped[list[StudentChangeRequest]] = relationship(
        "StudentChangeRequest", back_populates="setup", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("student_id", "subject", name="uq_study_setups_student_subject"),
    )


class SyllabusItem(Base):
    """Chapter inclusion, sequence, and weight within a study setup."""

    __tablename__ = "syllabus_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    setup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("study_setups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    included: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    custom_order: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    custom_difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    setup: Mapped[StudySetup] = relationship("StudySetup", back_populates="syllabus_items")
    chapter: Mapped[Chapter] = relationship("Chapter")

    __table_args__ = (
        UniqueConstraint("setup_id", "chapter_id", name="uq_syllabus_items_setup_chapter"),
        Index("ix_syllabus_setup_order", "setup_id", "custom_order"),
    )


class Plan(Base):
    """Versioned study schedule for a study setup."""

    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    setup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("study_setups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    reason: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # initial, syllabus_change, exam_change, adaptive, missed_work
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # pending, active, superseded
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    setup: Mapped[StudySetup] = relationship("StudySetup", back_populates="plans")
    student: Mapped[User] = relationship("User")
    days: Mapped[list[PlanDay]] = relationship(
        "PlanDay", back_populates="plan", cascade="all, delete-orphan", order_by="PlanDay.date"
    )

    __table_args__ = (
        UniqueConstraint("setup_id", "version", name="uq_plans_setup_version"),
        Index("ix_plans_student_setup_version", "student_id", "setup_id", "version"),
    )


class PlanDay(Base):
    """A planned calendar day within a versioned study plan."""

    __tablename__ = "plan_days"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    planned_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    day_type: Mapped[str] = mapped_column(
        String(20), default="study", nullable=False
    )  # study, buffer, revision

    # Relationships
    plan: Mapped[Plan] = relationship("Plan", back_populates="days")
    tasks: Mapped[list[Task]] = relationship(
        "Task", back_populates="plan_day", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("plan_id", "date", name="uq_plan_days_plan_date"),
        Index("ix_plan_days_plan_date", "plan_id", "date"),
    )


class Task(Base):
    """An actionable study, revision, homework, or quiz task."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_day_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plan_days.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # study, revision, homework, quiz, broad, review_quiz
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    refs: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )  # book_title, chapter_number, printed_page_start/end, guideline
    est_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="todo", nullable=False
    )  # todo, in_progress, done, skipped, rolled
    source: Mapped[str] = mapped_column(
        String(30), default="planner", nullable=False
    )  # planner, adaptive, teacher
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    # Relationships
    plan_day: Mapped[PlanDay] = relationship("PlanDay", back_populates="tasks")
    student: Mapped[User] = relationship("User")
    chapter: Mapped[Chapter | None] = relationship("Chapter")

    __table_args__ = (
        Index("ix_tasks_student_status", "student_id", "status"),
        Index("ix_tasks_plan_day", "plan_day_id"),
    )


class StudentChangeRequest(Base):
    """Student-initiated proposed modification to their study setup."""

    __tablename__ = "student_change_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    setup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("study_setups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_changes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, approved, rejected
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    setup: Mapped[StudySetup] = relationship("StudySetup", back_populates="change_requests")
    student: Mapped[User] = relationship("User", foreign_keys=[student_id])
    reviewed_by: Mapped[User | None] = relationship("User", foreign_keys=[reviewed_by_id])

    __table_args__ = (Index("ix_change_requests_setup_status", "setup_id", "status"),)
