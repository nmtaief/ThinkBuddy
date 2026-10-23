"""Authentication API endpoints for token exchange, session refresh, and logout."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.dependencies import get_current_user
from core.auth.models import Session as DbSession
from core.auth.models import User
from core.auth.provider import get_auth_provider
from core.auth.tokens import create_access_jwt, generate_secure_token, hash_token
from core.common.config import settings
from core.common.database import get_db_session
from core.families.models import StudentProfile

router = APIRouter(tags=["Auth"])


def utcnow() -> datetime:
    return datetime.now(UTC)


class AuthExchangeRequest(BaseModel):
    provider_token: str = Field(..., description="Firebase ID token or test token")
    role: str = Field(default="student", description="Role: student or parent")
    display_name: str | None = Field(default=None, description="User full name (Bangla/English)")
    locale: str = Field(default="bn", description="Preferred locale: bn or en")
    class_level: int | None = Field(default=None, description="Class level (6-8) for students")
    medium: str = Field(default="bn", description="Medium: bn or en")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Active session refresh token")


class UserResponse(BaseModel):
    id: uuid.UUID
    auth_provider: str
    auth_uid: str
    role: str
    display_name: str
    phone: str | None = None
    email: str | None = None
    locale: str
    status: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int

    user: UserResponse


@router.post("/auth/exchange", response_model=TokenResponse)
async def exchange_token(
    payload: AuthExchangeRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    """Exchange a verified third-party provider credential for ThinkBuddy session tokens."""
    provider = get_auth_provider()
    try:
        verified_user = await provider.verify_token(payload.provider_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": str(exc)},
        ) from exc

    # Enforce allowed roles
    requested_role = payload.role.lower()
    if requested_role not in {"student", "parent"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_ROLE",
                "message": "Only 'student' or 'parent' roles can register.",
            },
        )

    # Locate or create user record
    stmt = select(User).where(User.auth_uid == verified_user.uid)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        display_name = payload.display_name or verified_user.display_name or "ThinkBuddy User"
        user = User(
            id=uuid.uuid4(),
            auth_provider=verified_user.provider,
            auth_uid=verified_user.uid,
            role=requested_role,
            display_name=display_name,
            phone=verified_user.phone,
            email=verified_user.email,
            locale=payload.locale,
            status="active",
        )
        db.add(user)
        await db.flush()

        # If registering as a student, create academic profile
        if requested_role == "student":
            profile = StudentProfile(
                user_id=user.id,
                class_level=payload.class_level or 7,
                medium=payload.medium,
            )
            db.add(profile)
            await db.flush()

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCOUNT_INACTIVE", "message": "Account is inactive or suspended."},
        )

    # Create session with rotating refresh token
    raw_refresh = generate_secure_token(32)
    refresh_hash = hash_token(raw_refresh)
    session_expiry = utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    new_session = DbSession(
        id=uuid.uuid4(),
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        expires_at=session_expiry,
    )
    db.add(new_session)
    await db.flush()

    access_token = create_access_jwt(user.id, user.role)

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(
            id=user.id,
            auth_provider=user.auth_provider,
            auth_uid=user.auth_uid,
            role=user.role,
            display_name=user.display_name,
            phone=user.phone,
            email=user.email,
            locale=user.locale,
            status=user.status,
        ),
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_session(
    payload: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    """Rotate refresh token and issue a new access token."""
    token_hash = hash_token(payload.refresh_token)

    stmt = select(DbSession).where(
        DbSession.refresh_token_hash == token_hash,
        DbSession.revoked_at.is_(None),
        DbSession.expires_at > utcnow(),
    )
    result = await db.execute(stmt)
    old_session = result.scalar_one_or_none()

    if not old_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_REFRESH_TOKEN",
                "message": "Invalid or revoked refresh token.",
            },
        )

    # Revoke old session immediately (token rotation)
    old_session.revoked_at = utcnow()

    # Load active user
    user_stmt = select(User).where(User.id == old_session.user_id, User.deleted_at.is_(None))
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "USER_INACTIVE", "message": "User account inactive."},
        )

    # Issue new refresh token
    new_refresh = generate_secure_token(32)
    new_session = DbSession(
        id=uuid.uuid4(),
        user_id=user.id,
        device_id=old_session.device_id,
        refresh_token_hash=hash_token(new_refresh),
        expires_at=utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_session)
    await db.flush()

    new_access = create_access_jwt(user.id, user.role)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(
            id=user.id,
            auth_provider=user.auth_provider,
            auth_uid=user.auth_uid,
            role=user.role,
            display_name=user.display_name,
            phone=user.phone,
            email=user.email,
            locale=user.locale,
            status=user.status,
        ),
    )


@router.post("/auth/logout")
async def logout_session(
    payload: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str]:
    """Revoke refresh token session."""
    token_hash = hash_token(payload.refresh_token)
    stmt = select(DbSession).where(DbSession.refresh_token_hash == token_hash)
    result = await db.execute(stmt)
    sess = result.scalar_one_or_none()

    if sess and sess.revoked_at is None:
        sess.revoked_at = utcnow()
        await db.flush()

    return {"status": "logged_out"}


@router.get("/me", response_model=UserResponse)
@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Return identity and profile of currently authenticated user."""
    return UserResponse(
        id=current_user.id,
        auth_provider=current_user.auth_provider,
        auth_uid=current_user.auth_uid,
        role=current_user.role,
        display_name=current_user.display_name,
        phone=current_user.phone,
        email=current_user.email,
        locale=current_user.locale,
        status=current_user.status,
    )


@router.get("/internal/auth/status")
@router.get("/auth/status")
async def auth_status() -> dict[str, str]:
    """Module status endpoint for internal health and service verification."""
    return {"module": "auth", "status": "active"}
