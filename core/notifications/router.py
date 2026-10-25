"""FastAPI router for Notifications API (P07)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.common.database import get_db_session
from core.notifications.models import Notification
from core.notifications.schemas import (
    NotificationListResponse,
    NotificationPreferenceResponse,
    NotificationResponse,
    UpdateNotificationPreferenceRequest,
)
from core.notifications.service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get(
    "",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = Query(default=False),
) -> NotificationListResponse:
    """Retrieve user notifications with pagination and unread counts."""
    items, total, unread = await NotificationService.list_notifications(
        db=db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
    )
    res_items = [
        NotificationResponse(
            id=n.id,
            user_id=n.user_id,
            type=n.type,
            title=n.title,
            body=n.body,
            title_bn=n.title_bn,
            body_bn=n.body_bn,
            data=n.data or {},
            read_at=n.read_at,
            is_read=n.read_at is not None,
            created_at=n.created_at,
        )
        for n in items
    ]
    return NotificationListResponse(
        notifications=res_items,
        total_count=total,
        unread_count=unread,
    )


@router.post(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> NotificationResponse:
    """Mark a specific notification as read with strict ownership check (Rule 9 & Item 3)."""
    # 1. Check existence and verify ownership
    stmt_check = select(Notification).where(Notification.id == notification_id)
    res_check = await db.execute(stmt_check)
    notif = res_check.scalars().first()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if notif.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: notification belongs to another user",
        )

    item = await NotificationService.mark_as_read(
        db=db,
        user_id=current_user.id,
        notification_id=notification_id,
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    await db.commit()
    return NotificationResponse(
        id=item.id,
        user_id=item.user_id,
        type=item.type,
        title=item.title,
        body=item.body,
        title_bn=item.title_bn,
        body_bn=item.body_bn,
        data=item.data or {},
        read_at=item.read_at,
        is_read=True,
        created_at=item.created_at,
    )


@router.post(
    "/read-all",
    status_code=status.HTTP_200_OK,
)
async def mark_all_notifications_read(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Mark all unread notifications as read."""
    count = await NotificationService.mark_all_as_read(
        db=db,
        user_id=current_user.id,
    )
    await db.commit()
    return {"status": "ok", "marked_read_count": count}


@router.get(
    "/preferences",
    response_model=NotificationPreferenceResponse,
    status_code=status.HTTP_200_OK,
)
async def get_notification_preferences(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> NotificationPreferenceResponse:
    """Get current user notification delivery and category preferences."""
    pref = await NotificationService.get_or_create_preferences(db=db, user_id=current_user.id)
    return NotificationPreferenceResponse(
        user_id=pref.user_id,
        channels=pref.channels or {},
        quiet_hours_start=pref.quiet_hours_start,
        quiet_hours_end=pref.quiet_hours_end,
        categories=pref.categories or {},
    )


@router.put(
    "/preferences",
    response_model=NotificationPreferenceResponse,
    status_code=status.HTTP_200_OK,
)
async def update_notification_preferences(
    payload: UpdateNotificationPreferenceRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> NotificationPreferenceResponse:
    """Update notification channels, categories, and quiet hours."""
    pref = await NotificationService.update_preferences(
        db=db,
        user_id=current_user.id,
        channels=payload.channels,
        quiet_hours_start=payload.quiet_hours_start,
        quiet_hours_end=payload.quiet_hours_end,
        categories=payload.categories,
    )
    await db.commit()
    return NotificationPreferenceResponse(
        user_id=pref.user_id,
        channels=pref.channels or {},
        quiet_hours_start=pref.quiet_hours_start,
        quiet_hours_end=pref.quiet_hours_end,
        categories=pref.categories or {},
    )
