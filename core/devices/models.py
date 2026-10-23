"""SQLAlchemy model for user devices and client telemetry."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.common.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Device(Base):
    """Client device hardware, push tokens, and platform metadata."""

    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)  # android, ios, web
    form_factor: Mapped[str] = mapped_column(
        String(20), default="phone", nullable=False
    )  # phone, tablet, desktop
    push_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    app_version: Mapped[str] = mapped_column(String(50), nullable=False)
    integrity_status: Mapped[str] = mapped_column(String(20), default="clean", nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


Index("ix_devices_user_platform", Device.user_id, Device.platform)
