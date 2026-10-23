"""SQLAlchemy models for families, student profiles, and parent-student links."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.common.database import Base

if TYPE_CHECKING:
    from core.auth.models import User


def utcnow() -> datetime:
    return datetime.now(UTC)


class StudentProfile(Base):
    """Academic and learning setup details for enrolled students."""

    __tablename__ = "student_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    class_level: Mapped[int] = mapped_column(Integer, nullable=False)  # 6-8 in beta
    medium: Mapped[str] = mapped_column(String(10), default="bn", nullable=False)  # bn or en
    school: Mapped[str | None] = mapped_column(Text, nullable=True)  # Unicode Bangla-safe
    daily_minutes: Mapped[int] = mapped_column(Integer, default=45, nullable=False)
    available_days: Mapped[list[str]] = mapped_column(
        JSONB, default=lambda: ["sat", "sun", "mon", "tue", "wed", "thu"], nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped[User] = relationship("User", back_populates="student_profile")


class Family(Base):
    """Family unit grouping parents and students."""

    __tablename__ = "families"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)  # e.g., "Rahman Family" or "রহমান পরিবার"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    members: Mapped[list[FamilyMember]] = relationship(
        "FamilyMember", back_populates="family", cascade="all, delete-orphan"
    )


class FamilyMember(Base):
    """Association of users within a family."""

    __tablename__ = "family_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relation: Mapped[str] = mapped_column(
        String(30), default="guardian", nullable=False
    )  # mother, father, guardian, child
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    family: Mapped[Family] = relationship("Family", back_populates="members")


class ParentStudentLink(Base):
    """Explicit, verifiable link between a parent and child with consent tracking."""

    __tablename__ = "parent_student_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    family_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("families.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )  # pending, active, revoked
    link_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    link_code_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


Index(
    "ix_parent_student_active",
    ParentStudentLink.parent_id,
    ParentStudentLink.student_id,
    ParentStudentLink.status,
)
