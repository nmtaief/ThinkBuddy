"""SQLAlchemy Models for Student Mastery, Attempt History, and Hierarchical Rollups."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from core.common.database import Base


class StudentQuestionHistory(Base):
    __tablename__ = "student_question_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    question_id = Column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    quiz_mode = Column(String(32), nullable=False)  # daily_quiz, practice_quiz, exam_week_drill
    is_correct = Column(Boolean, nullable=False)
    time_taken_sec = Column(Integer, default=0, nullable=False)
    attempted_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        Index("idx_history_user_question_py", "user_id", "question_id", "attempted_at"),
    )


class StudentQuestionState(Base):
    __tablename__ = "student_question_state"

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    question_id = Column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    status = Column(
        String(32), default="unseen", nullable=False
    )  # unseen, weak, recovering, mastered
    wrong_count = Column(Integer, default=0, nullable=False)
    correct_count = Column(Integer, default=0, nullable=False)
    consecutive_correct = Column(Integer, default=0, nullable=False)
    last_wrong_at = Column(DateTime(timezone=True), nullable=True)
    last_correct_at = Column(DateTime(timezone=True), nullable=True)
    next_review_at = Column(DateTime(timezone=True), nullable=True)
    weakness_weight = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index(
            "idx_state_review_priority_py", "user_id", "status", "next_review_at", "weakness_weight"
        ),
    )


class StudentProgressRollup(Base):
    __tablename__ = "student_progress_rollups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    grain_level = Column(String(32), nullable=False)  # class, subject, chapter, book_topic
    class_level = Column(Integer, nullable=False)
    subject = Column(String(64), nullable=True)
    paper = Column(String(32), default="1st")
    chapter_id = Column(UUID(as_uuid=True), nullable=True)
    book_topic_id = Column(
        UUID(as_uuid=True), ForeignKey("book_topics.id", ondelete="CASCADE"), nullable=True
    )
    book_topic_name = Column(String(255), nullable=True)

    total_attempted = Column(Integer, default=0, nullable=False)
    weak_count = Column(Integer, default=0, nullable=False)
    recovering_count = Column(Integer, default=0, nullable=False)
    mastered_count = Column(Integer, default=0, nullable=False)
    recovered_from_wrong_count = Column(Integer, default=0, nullable=False)

    accuracy_pct = Column(Float, default=0.0, nullable=False)
    mastery_pct = Column(Float, default=0.0, nullable=False)
    needs_more_practice = Column(Boolean, default=False, nullable=False)

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "grain_level",
            "class_level",
            "subject",
            "chapter_id",
            "book_topic_id",
            name="uq_student_rollup_py",
        ),
        Index("idx_rollups_user_grain_py", "user_id", "grain_level", "class_level", "subject"),
    )
