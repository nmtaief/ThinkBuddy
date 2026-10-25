"""Pydantic schemas for notifications and preferences (P07)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    """Notification response schema with bilingual fields and actionable metadata."""

    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    title: str
    body: str
    title_bn: str
    body_bn: str
    data: dict[str, Any] = Field(default_factory=dict)
    read_at: datetime | None = None
    is_read: bool = False
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Paginated list of notifications with unread counts."""

    notifications: list[NotificationResponse]
    total_count: int
    unread_count: int


class NotificationPreferenceResponse(BaseModel):
    """Notification preferences for a parent or student."""

    user_id: uuid.UUID
    channels: dict[str, bool]
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    categories: dict[str, bool]


class UpdateNotificationPreferenceRequest(BaseModel):
    """Request to update notification channels, categories, and quiet hours."""

    channels: dict[str, bool] | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    categories: dict[str, bool] | None = None
