"""SQLAlchemy database models for curriculum, textbooks, chapters, concepts, and chunks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.common.config import settings
from core.common.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Book(Base):
    """NCTB curriculum textbook."""

    __tablename__ = "books"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    class_level: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    medium: Mapped[str] = mapped_column(String(10), nullable=False, default="bn")
    edition: Mapped[str] = mapped_column(String(50), nullable=False, default="2024")
    source_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    chapters: Mapped[list[Chapter]] = relationship(
        "Chapter",
        back_populates="book",
        cascade="all, delete-orphan",
        order_by="Chapter.order_index",
    )
    chunks: Mapped[list[Chunk]] = relationship(
        "Chunk", back_populates="book", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("class_level", "subject", "medium", "edition", name="uq_books_curriculum"),
    )


class Chapter(Base):
    """Textbook chapter."""

    __tablename__ = "chapters"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    printed_page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    printed_page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    difficulty_factor: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    book: Mapped[Book] = relationship("Book", back_populates="chapters")
    concepts: Mapped[list[Concept]] = relationship(
        "Concept", back_populates="chapter", cascade="all, delete-orphan"
    )
    chunks: Mapped[list[Chunk]] = relationship(
        "Chunk", back_populates="chapter", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("book_id", "number", name="uq_chapters_book_number"),)


class Concept(Base):
    """Core educational concept or formula within a chapter."""

    __tablename__ = "concepts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(
        String(50), nullable=False, default="concept"
    )  # definition, formula, example, concept, exercise
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    chapter: Mapped[Chapter] = relationship("Chapter", back_populates="concepts")
    chunks: Mapped[list[Chunk]] = relationship("Chunk", back_populates="concept")


class IngestBatch(Base):
    """Audit log and progress tracker for content ingestion batches."""

    __tablename__ = "ingest_batches"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_manifest: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="in_progress"
    )  # in_progress, completed, failed, resumed
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Chunk(Base):
    """Ingested textbook content chunk for hybrid RAG retrieval."""

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concept_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    ingest_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ingest_batches.id", ondelete="SET NULL"), nullable=True, index=True
    )

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_original: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="bn")
    chunk_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="explanation"
    )  # explanation, definition, formula, worked_example, exercise, figure_caption

    # Printed page number ≠ PDF page index. Stored separately; printed page shown to users.
    printed_page: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    pdf_page_index: Mapped[int] = mapped_column(Integer, nullable=False)

    ocr_quality: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    validation_flags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    retrievable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    # Config-driven embedding vector dimension and model versioning
    embedding_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default=settings.EMBEDDING_MODEL
    )
    embedding = mapped_column(Vector(settings.EMBEDDING_DIMENSION), nullable=True)
    tsv = mapped_column(TSVECTOR, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    book: Mapped[Book] = relationship("Book", back_populates="chunks")
    chapter: Mapped[Chapter] = relationship("Chapter", back_populates="chunks")
    concept: Mapped[Concept | None] = relationship("Concept", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("book_id", "chunk_index", name="uq_chunks_book_chunk_index"),
        Index("idx_chunks_book_chapter", "book_id", "chapter_id"),
        Index("idx_chunks_chapter_printed_page", "chapter_id", "printed_page"),
        Index("idx_chunks_chunk_type", "chunk_type"),
    )


class ExerciseItem(Base):
    """Textbook exercise question item indexed by exercise label, question number, and printed page."""

    __tablename__ = "exercise_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_label: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    question_no: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    subpart: Mapped[str | None] = mapped_column(String(10), nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    printed_page: Mapped[int] = mapped_column(Integer, nullable=False)
    pdf_page_index: Mapped[int] = mapped_column(Integer, nullable=False)
    has_figure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    figure_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_type: Mapped[str] = mapped_column(String(30), nullable=False, default="short")
    ocr_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="team_checked")
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="NCTB 2024")
    answer_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    book: Mapped[Book] = relationship("Book")
    chapter: Mapped[Chapter] = relationship("Chapter")

    __table_args__ = (
        UniqueConstraint(
            "chapter_id",
            "exercise_label",
            "question_no",
            "subpart",
            name="uq_exercise_item_chapter_label_qno_subpart",
        ),
        Index("idx_exercise_items_lookup", "book_id", "exercise_label", "question_no"),
    )


class MathBook(Base):
    """Separate math textbooks table."""

    __tablename__ = "math_books"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    class_level: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    medium: Mapped[str] = mapped_column(String(20), nullable=False, default="bangla")
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    version_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2026)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    chapters: Mapped[list["MathChapter"]] = relationship("MathChapter", back_populates="book", cascade="all, delete-orphan")


class MathChapter(Base):
    """Separate math chapters table."""

    __tablename__ = "math_chapters"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("math_books.id", ondelete="CASCADE"), nullable=False, index=True)
    class_level: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    medium: Mapped[str] = mapped_column(String(20), nullable=False, default="bangla")
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    title_ascii: Mapped[str | None] = mapped_column(String(150), nullable=True)
    printed_page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    printed_page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    book: Mapped["MathBook"] = relationship("MathBook", back_populates="chapters")
    theories: Mapped[list["MathTheory"]] = relationship("MathTheory", back_populates="chapter", cascade="all, delete-orphan")
    exercises: Mapped[list["MathExercise"]] = relationship("MathExercise", back_populates="chapter", cascade="all, delete-orphan")
    items: Mapped[list["MathItemV2"]] = relationship("MathItemV2", back_populates="chapter", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("book_id", "chapter_number", name="uq_math_chapters_book_number"),
    )


class MathTheory(Base):
    """Textbook theory, definitions, formulas, and worked examples."""

    __tablename__ = "math_theory"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("math_chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    theory_type: Mapped[str] = mapped_column(String(30), nullable=False)  # definition, formula, worked_example, rule
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    printed_page: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    chapter: Mapped["MathChapter"] = relationship("MathChapter", back_populates="theories")


class MathExercise(Base):
    """Discrete exercise sections (e.g. অনুশীলনী ১, অনুশীলনী ৩.১)."""

    __tablename__ = "math_exercises"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("math_chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    exercise_label: Mapped[str] = mapped_column(String(50), nullable=False)
    exercise_label_ascii: Mapped[str] = mapped_column(String(50), nullable=False)
    printed_page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    printed_page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    chapter: Mapped["MathChapter"] = relationship("MathChapter", back_populates="exercises")
    items: Mapped[list["MathItemV2"]] = relationship("MathItemV2", back_populates="exercise", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("chapter_id", "exercise_label", name="uq_math_exercises_chap_label"),
    )


class MathItemV2(Base):
    """Separate verified math exercise items table."""

    __tablename__ = "math_items_v2"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("math_books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("math_chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    exercise_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("math_exercises.id", ondelete="CASCADE"), nullable=True, index=True)
    class_level: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    exercise_label: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(30), nullable=False, default="short")
    question_no: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    question_no_display: Mapped[str] = mapped_column(String(20), nullable=False)
    subpart: Mapped[str | None] = mapped_column(String(20), nullable=True)
    stimulus_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_text_ascii: Mapped[str | None] = mapped_column(Text, nullable=True)
    mcq_options: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    printed_page: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    pdf_page_index: Mapped[int] = mapped_column(Integer, nullable=False)
    needs_figure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_image_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uncertain_chars: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    internal_answer_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    read_1_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    read_2_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff_disagreement: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    chapter: Mapped["MathChapter"] = relationship("MathChapter", back_populates="items")
    exercise: Mapped["MathExercise | None"] = relationship("MathExercise", back_populates="items")
    solution: Mapped["MathSolution | None"] = relationship("MathSolution", back_populates="item", uselist=False, cascade="all, delete-orphan")
    figures: Mapped[list["MathFigure"]] = relationship("MathFigure", back_populates="item", cascade="all, delete-orphan")
    hints: Mapped[list["MathHint"]] = relationship("MathHint", back_populates="item", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint(
            "chapter_id",
            "exercise_label",
            "question_no",
            "subpart",
            name="uq_math_items_v2_chap_label_qno_subpart",
        ),
        Index("idx_math_items_v2_lookup", "class_level", "chapter_number", "exercise_label", "question_no"),
        Index("idx_math_items_v2_page_lookup", "class_level", "printed_page", "question_no"),
    )


class MathFigure(Base):
    """Crops and structured representations for math figures."""

    __tablename__ = "math_figures"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("math_items_v2.id", ondelete="CASCADE"), nullable=False, index=True)
    crop_path: Mapped[str] = mapped_column(String(255), nullable=False)
    structured_description: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    needs_teacher_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    item: Mapped["MathItemV2"] = relationship("MathItemV2", back_populates="figures")


class MathSolution(Base):
    """Verified step-by-step solutions for math items."""

    __tablename__ = "math_solutions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("math_items_v2.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    steps: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    final_answer: Mapped[str] = mapped_column(Text, nullable=False)
    final_answer_ascii: Mapped[str | None] = mapped_column(Text, nullable=True)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    theory_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False, default="gemini-agent-v1")
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False, default="p15-tutor-v1")
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False, default="unverified", index=True)
    verifier_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    item: Mapped["MathItemV2"] = relationship("MathItemV2", back_populates="solution")


class MathHint(Base):
    """3-level hint ladders for math items."""

    __tablename__ = "math_hints"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("math_items_v2.id", ondelete="CASCADE"), nullable=False, index=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    hint_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    item: Mapped["MathItemV2"] = relationship("MathItemV2", back_populates="hints")

    __table_args__ = (
        UniqueConstraint("item_id", "level", name="uq_math_hints_item_level"),
    )


class MathConcept(Base):
    """Mathematical concepts dictionary."""

    __tablename__ = "math_concepts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MathItemConcept(Base):
    """Linking math items to concepts."""

    __tablename__ = "math_item_concepts"

    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("math_items_v2.id", ondelete="CASCADE"), primary_key=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("math_concepts.id", ondelete="CASCADE"), primary_key=True)


