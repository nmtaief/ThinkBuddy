"""SQLAlchemy model for AI Tutor and RAG configuration."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.common.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class AITutorConfig(Base):
    """Administrative configuration for Buddy the AI Tutor and RAG engine."""

    __tablename__ = "ai_tutor_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    llm_provider: Mapped[str] = mapped_column(
        String(50), default="gemini", nullable=False
    )
    api_key: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    api_base: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    primary_model: Mapped[str] = mapped_column(
        String(100), default="gemini/gemini-1.5-flash", nullable=False
    )
    fallback_model: Mapped[str] = mapped_column(
        String(100), default="openai/gpt-4o-mini", nullable=False
    )
    temperature: Mapped[float] = mapped_column(
        Float, default=0.3, nullable=False
    )
    system_prompt: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    embedding_provider: Mapped[str] = mapped_column(
        String(50), default="bge-m3", nullable=False
    )
    embedding_api_key: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    embedding_model: Mapped[str] = mapped_column(
        String(100), default="bge-m3", nullable=False
    )
    embedding_dimensions: Mapped[int] = mapped_column(
        Integer, default=1024, nullable=False
    )
    confidence_threshold: Mapped[float] = mapped_column(
        Float, default=0.45, nullable=False
    )
    max_chunks: Mapped[int] = mapped_column(
        Integer, default=4, nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
