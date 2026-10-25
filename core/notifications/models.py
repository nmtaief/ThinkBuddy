"""SQLAlchemy database models for notifications and preferences (Milestone P07)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.common.database import Base

if TYPE_CHECKING:
    from core.auth.models import User


def utcnow() -> datetime:
    return datetime.now(UTC)


class Notification(Base):
    """Notification entity storing bilingual parent/student messages and metadata."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    title_bn: Mapped[str] = mapped_column(String(255), nullable=False)
    body_bn: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    user: Mapped[User] = relationship("User")

    __table_args__ = (Index("ix_notifications_user_read", "user_id", "read_at"),)


class NotificationPreference(Base):
    """User-level notification delivery preferences and quiet hours."""

    __tablename__ = "notification_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    channels: Mapped[dict[str, bool]] = mapped_column(
        JSONB, default=lambda: {"in_app": True, "push": True}, nullable=False
    )
    quiet_hours_start: Mapped[str | None] = mapped_column(String(8), nullable=True, default=None)
    quiet_hours_end: Mapped[str | None] = mapped_column(String(8), nullable=True, default=None)
    categories: Mapped[dict[str, bool]] = mapped_column(
        JSONB,
        default=lambda: {
            "ai_adjustments": True,
            "streaks": True,
            "progress": True,
            "exams": True,
        },
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped[User] = relationship("User")


class NotificationDelivery(Base):
    """Delivery log tracking individual push / in-app notification dispatch attempts."""

    __tablename__ = "notification_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)  # push, in_app, email
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # delivered, suppressed_quiet_hours, suppressed_daily_cap, failed
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    deferred_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_notification_deliveries_user_sent", "user_id", "sent_at"),
        Index("ix_notification_deliveries_deferred", "status", "deferred_until"),
    )
