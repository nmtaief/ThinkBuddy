"""SQLAlchemy models for authentication, users, and sessions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.common.database import Base

if TYPE_CHECKING:
    from core.families.models import StudentProfile


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    """Core user account representing students, parents, teachers, and admins."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    auth_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    auth_uid: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # student, parent, teacher, admin
    display_name: Mapped[str] = mapped_column(Text, nullable=False)  # Unicode Bangla-safe
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    locale: Mapped[str] = mapped_column(String(10), default="bn", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    has_valid_attestation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_parental_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consent_terms_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    sessions: Mapped[list[Session]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )
    student_profile: Mapped[StudentProfile | None] = relationship(
        "StudentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class Session(Base):
    """User authentication session tracking rotating refresh tokens."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    user: Mapped[User] = relationship("User", back_populates="sessions")


Index("ix_sessions_token_active", Session.refresh_token_hash, Session.revoked_at)
