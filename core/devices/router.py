"""Device registration and push token management endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.common.database import get_db_session
from core.devices.models import Device

router = APIRouter(tags=["Devices"])


def utcnow() -> datetime:
    return datetime.now(UTC)


class RegisterDeviceRequest(BaseModel):
    platform: str = Field(..., description="Platform: android, ios, or web")
    form_factor: str = Field(default="phone", description="phone, tablet, desktop")
    push_token: str | None = Field(default=None, description="FCM / APNs push token")
    app_version: str = Field(default="1.0.0", description="App semantic version")


class UpdateDeviceRequest(BaseModel):
    push_token: str | None = Field(default=None)
    app_version: str | None = Field(default=None)


class DeviceResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    platform: str
    form_factor: str
    app_version: str
    push_token: str | None = None
    integrity_status: str
    last_seen_at: datetime


@router.post("/devices", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: RegisterDeviceRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> DeviceResponse:
    if payload.push_token:
        # Reassign push token: nullify on any other device across users (Item 3 & 4: shared devices)
        await db.execute(
            update(Device)
            .where(Device.push_token == payload.push_token)
            .values(push_token=None)
        )

    device = Device(
        id=uuid.uuid4(),
        user_id=current_user.id,
        platform=payload.platform.lower(),
        form_factor=payload.form_factor.lower(),
        push_token=payload.push_token,
        app_version=payload.app_version,
        integrity_status="clean",
    )
    db.add(device)
    await db.flush()

    return DeviceResponse(
        id=device.id,
        user_id=device.user_id,
        platform=device.platform,
        form_factor=device.form_factor,
        app_version=device.app_version,
        push_token=device.push_token,
        integrity_status=device.integrity_status,
        last_seen_at=device.last_seen_at,
    )


@router.patch("/devices/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: uuid.UUID,
    payload: UpdateDeviceRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> DeviceResponse:
    """Update device push token or app version."""
    stmt = select(Device).where(Device.id == device_id, Device.user_id == current_user.id)
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DEVICE_NOT_FOUND", "message": "Device not found for current user."},
        )

    if payload.push_token is not None:
        if payload.push_token:
            # Reassign push token: nullify on any other device (Item 3 & 4)
            await db.execute(
                update(Device)
                .where(Device.push_token == payload.push_token, Device.id != device_id)
                .values(push_token=None)
            )
        device.push_token = payload.push_token
    if payload.app_version is not None:
        device.app_version = payload.app_version

    device.last_seen_at = utcnow()
    await db.flush()

    return DeviceResponse(
        id=device.id,
        user_id=device.user_id,
        platform=device.platform,
        form_factor=device.form_factor,
        app_version=device.app_version,
        push_token=device.push_token,
        integrity_status=device.integrity_status,
        last_seen_at=device.last_seen_at,
    )
