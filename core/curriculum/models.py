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
    )
