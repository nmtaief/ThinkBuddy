"""SQLAlchemy Models for ThinkBuddy Question Bank, Canonical Book Topics & Uddipok Stems."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    from sqlalchemy.types import UserDefinedType

    class Vector(UserDefinedType):
        def __init__(self, dim):
            self.dim = dim

        def get_col_spec(self, **kw):
            return f"vector({self.dim})"


from core.common.database import Base


class BookTopic(Base):
    __tablename__ = "book_topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_level = Column(Integer, nullable=False)
    version = Column(String(10), nullable=False, default="bn")
    subject = Column(String(64), nullable=False)
    paper = Column(String(32), default="1st")
    book_name = Column(String(255), nullable=False)
    author = Column(String(255), default="NCTB")
    chapter_number = Column(Integer, nullable=False)
    chapter_title = Column(String(255), nullable=False)
    topic_code = Column(String(32), nullable=False)
    book_topic_name = Column(String(255), nullable=False)
    parent_topic_id = Column(
        UUID(as_uuid=True), ForeignKey("book_topics.id", ondelete="SET NULL"), nullable=True
    )
    page_start = Column(Integer, nullable=False)
    page_end = Column(Integer, nullable=False)
    topic_embedding = Column(Vector(1024), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint(
            "class_level",
            "version",
            "subject",
            "chapter_number",
            "topic_code",
            name="uq_book_topic",
        ),
        Index("idx_book_topics_lookup_py", "class_level", "version", "subject", "chapter_number"),
    )


class UddipokStem(Base):
    __tablename__ = "uddipok_stems"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stem_text = Column(Text, nullable=False)
    media_urls = Column(JSONB, default=list)
    chapter_id = Column(UUID(as_uuid=True), nullable=True)
    book_topic_id = Column(
        UUID(as_uuid=True), ForeignKey("book_topics.id", ondelete="SET NULL"), nullable=True
    )
    source_attribution = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class Question(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uddipok_id = Column(
        UUID(as_uuid=True), ForeignKey("uddipok_stems.id", ondelete="SET NULL"), nullable=True
    )
    class_level = Column(Integer, nullable=False)
    version = Column(String(10), nullable=False, default="bn")
    subject = Column(String(64), nullable=False)
    paper = Column(String(32), default="1st")
    chapter_id = Column(UUID(as_uuid=True), nullable=True)
    book_topic_id = Column(
        UUID(as_uuid=True), ForeignKey("book_topics.id", ondelete="SET NULL"), nullable=True
    )
    book_topic_name = Column(String(255), nullable=False)
    subtopic_name = Column(String(255), nullable=True)

    source_type = Column(String(32), nullable=False)  # Book, Board, School, Admission
    format = Column(String(32), nullable=False)  # MCQ, CQ, Short, Book_Exercise
    cognitive_tier = Column(
        String(32), nullable=False
    )  # Gyanmulok, Unudhabon, Proyog, Uchchotor_Dokkhota
    difficulty = Column(Float, default=3.0, nullable=False)  # 1-5
    mcq_subtype = Column(String(32), default="simple")  # simple, multiple_completion, situation_set

    question_text = Column(Text, nullable=False)
    options_json = Column(JSONB, default=list)
    correct_answer = Column(Text, nullable=False)
    explanation_text = Column(Text, nullable=True)
    exact_citation = Column(JSONB, default=dict)

    appearance_tags = Column(JSONB, default=list)  # e.g. ["DB-2024", "RB-2023"]
    repetitiveness_score = Column(Float, default=1.0, nullable=False)
    importance_score = Column(Float, default=1.0, nullable=False)
    related_topic_ids = Column(JSONB, default=list)  # List of prerequisite book_topic_ids
    embedding = Column(Vector(1024), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index(
            "idx_questions_query_py",
            "class_level",
            "version",
            "subject",
            "book_topic_id",
            "format",
            "difficulty",
        ),
        Index("idx_questions_importance_py", "importance_score", "repetitiveness_score"),
    )
