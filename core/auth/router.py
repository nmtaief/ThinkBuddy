"""Authentication API endpoints for token exchange, session refresh, and logout."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit.models import AuditLog
from core.auth.dependencies import get_current_user
from core.auth.models import Session as DbSession
from core.auth.models import User
from core.auth.provider import get_auth_provider, get_google_auth_provider
from core.auth.tokens import create_access_jwt, generate_secure_token, hash_link_code, hash_token
from core.common.config import settings
from core.common.database import get_db_session
from core.families.models import FamilyMember, ParentStudentLink, StudentProfile

router = APIRouter(tags=["Auth"])


def utcnow() -> datetime:
    return datetime.now(UTC)


class AuthExchangeRequest(BaseModel):
    provider_token: str = Field(..., description="Firebase ID token or test token")
    role: str = Field(default="student", description="Role: student or parent")
    link_code: str | None = Field(
        default=None,
        description="Expiring invitation link code from parent (required for student registration)",
    )
    display_name: str | None = Field(default=None, description="User full name (Bangla/English)")
    locale: str = Field(default="bn", description="Preferred locale: bn or en")
    class_level: int | None = Field(default=None, description="Class level (6-12) for students")
    group: str | None = Field(
        default=None, description="Group for 9-12 (science, humanities, business_studies)"
    )
    medium: str = Field(default="bn", description="Medium: bn or en")


class GoogleAuthRequest(BaseModel):
    id_token: str = Field(..., description="Google OAuth2 ID token credential from Google Sign-In")
    role: str = Field(default="student", description="Role: student or parent")
    link_code: str | None = Field(
        default=None,
        description="Optional invitation link code from parent",
    )
    display_name: str | None = Field(default=None, description="User full name (Bangla/English)")
    locale: str = Field(default="bn", description="Preferred locale: bn or en")
    class_level: int | None = Field(default=None, description="Class level (6-12) for students")
    group: str | None = Field(
        default=None, description="Group for 9-12 (science, humanities, business_studies)"
    )
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
        # Check if student is registering via parent invitation link code
        link: ParentStudentLink | None = None
        if requested_role == "student" and payload.link_code:
            code_hash = hash_link_code(payload.link_code)
            link_stmt = select(ParentStudentLink).where(
                ParentStudentLink.link_code_hash == code_hash,
                ParentStudentLink.status == "pending",
                ParentStudentLink.link_code_expires_at > utcnow(),
            )
            link_res = await db.execute(link_stmt)
            link = link_res.scalar_one_or_none()
            if not link:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "INVALID_OR_EXPIRED_CODE",
                        "message": "Link code is invalid, expired, or already used.",
                    },
                )

        display_name = payload.display_name or verified_user.display_name or "ThinkBuddy User"
        initial_consent = False if requested_role == "parent" else True
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
            has_parental_consent=initial_consent,
        )
        db.add(user)
        await db.flush()

        # If registering as a student with verified parent link, configure profile & redeem link
        if requested_role == "student" and link is not None:
            # Check if parent pre-configured academic details on placeholder profile
            parent_prof_stmt = select(StudentProfile).where(
                StudentProfile.user_id == link.student_id
            )
            parent_prof_res = await db.execute(parent_prof_stmt)
            parent_prof = parent_prof_res.scalar_one_or_none()

            class_lvl = parent_prof.class_level if parent_prof else (payload.class_level or 8)
            med = parent_prof.medium if parent_prof else payload.medium
            sch = parent_prof.school if parent_prof else None
            grp = parent_prof.group if parent_prof else payload.group
            opts = parent_prof.optional_subject_ids if parent_prof else []
            mins = parent_prof.daily_minutes if parent_prof else 60

            profile = StudentProfile(
                user_id=user.id,
                class_level=class_lvl,
                group=grp,
                optional_subject_ids=opts,
                medium=med,
                school=sch,
                daily_minutes=mins,
            )
            db.add(profile)

            # Establish and activate link
            link.status = "active"
            link.student_id = user.id
            link.consent_at = utcnow()
            user.has_parental_consent = True
            link.link_code_hash = None  # Invalidate single-use code immediately

            if link.family_id:
                member = FamilyMember(
                    id=uuid.uuid4(),
                    family_id=link.family_id,
                    user_id=user.id,
                    relation="child",
                )
                db.add(member)
        elif requested_role == "student":
            # Self-registered student (direct web onboarding)
            profile = StudentProfile(
                user_id=user.id,
                class_level=payload.class_level or 8,
                group=payload.group,
                optional_subject_ids=[],
                medium=payload.medium or "bn",
                school=None,
                daily_minutes=60,
            )
            db.add(profile)

            audit = AuditLog(
                id=uuid.uuid4(),
                actor_id=user.id,
                action="family.student_registered_via_link",
                target_type="parent_student_link",
                target_id=str(link.id),
                meta={"parent_id": str(link.parent_id), "student_id": str(user.id)},
            )
            db.add(audit)
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


@router.post("/auth/google", response_model=TokenResponse)
async def google_auth_exchange(
    payload: GoogleAuthRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    """Exchange verified Google OAuth2 ID token for ThinkBuddy session tokens."""
    provider = get_google_auth_provider()
    try:
        verified_user = await provider.verify_token(payload.id_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_GOOGLE_TOKEN", "message": str(exc)},
        ) from exc

    requested_role = payload.role.lower()
    if requested_role not in {"student", "parent"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_ROLE",
                "message": "Only 'student' or 'parent' roles can register.",
            },
        )

    # Find existing user by auth_uid or email
    stmt = select(User).where(
        (User.auth_uid == verified_user.uid)
        | ((User.email == verified_user.email) & (User.email.isnot(None)))
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        display_name = payload.display_name or verified_user.display_name or "ThinkBuddy User"
        initial_consent = False if requested_role == "parent" else True
        user = User(
            id=uuid.uuid4(),
            auth_provider="google",
            auth_uid=verified_user.uid,
            role=requested_role,
            display_name=display_name,
            phone=verified_user.phone,
            email=verified_user.email,
            locale=payload.locale,
            status="active",
            has_parental_consent=initial_consent,
        )
        db.add(user)
        await db.flush()

        if requested_role == "student":
            profile = StudentProfile(
                user_id=user.id,
                class_level=payload.class_level or 8,
                group=payload.group,
                optional_subject_ids=[],
                medium=payload.medium or "bn",
                school=None,
                daily_minutes=60,
            )
            db.add(profile)
    else:
        # Update user auth_uid / auth_provider if previously unlinked or registered via email
        if user.auth_provider != "google" and verified_user.email and user.email == verified_user.email:
            user.auth_provider = "google"
            user.auth_uid = verified_user.uid

    # Create new session
    raw_refresh = generate_secure_token()
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
    """Rotate refresh token and issue a new access token.

    Detects refresh token reuse attacks: presenting an already-revoked refresh token
    immediately revokes all active sessions for that user and records an audit log.
    """
    token_hash = hash_token(payload.refresh_token)

    # 1. Search session by token hash WITHOUT filtering out revoked_at
    stmt = select(DbSession).where(DbSession.refresh_token_hash == token_hash)
    result = await db.execute(stmt)
    old_session = result.scalar_one_or_none()

    if not old_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_REFRESH_TOKEN",
                "message": "Invalid refresh token.",
            },
        )

    # 2. Check if token was already revoked/rotated -> REUSE ATTACK DETECTED!
    if old_session.revoked_at is not None:
        # Compromised refresh token reuse detected!
        # Revoke ALL active sessions for this user immediately
        revoke_all_stmt = (
            update(DbSession)
            .where(DbSession.user_id == old_session.user_id, DbSession.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        await db.execute(revoke_all_stmt)
        # Token cleanup on session revocation (Item 3)
        from core.devices.models import Device
        await db.execute(
            update(Device)
            .where(Device.user_id == old_session.user_id)
            .values(push_token=None)
        )

        audit = AuditLog(
            id=uuid.uuid4(),
            actor_id=old_session.user_id,
            action="auth.refresh_token_reuse_detected",
            target_type="session",
            target_id=str(old_session.id),
            meta={
                "security_event": "rotated_refresh_token_reused",
                "action_taken": "all_user_sessions_revoked",
            },
        )
        db.add(audit)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "REFRESH_TOKEN_REUSE_DETECTED",
                "message": (
                    "Revoked refresh token reuse detected. "
                    "All active sessions for this account have been terminated for security."
                ),
            },
        )

    # 3. Check expiration
    if old_session.expires_at <= utcnow():
        old_session.revoked_at = utcnow()
        await db.flush()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "EXPIRED_REFRESH_TOKEN",
                "message": "Refresh token has expired. Please sign in again.",
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
        # Item 3: Logout affects ONLY that specific device
        if sess.device_id:
            from core.devices.models import Device
            await db.execute(
                update(Device)
                .where(Device.id == sess.device_id, Device.user_id == sess.user_id)
                .values(push_token=None)
            )
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


class ReauthenticateRequest(BaseModel):
    provider_token: str
    action: str = Field(
        default="general",
        description="Target action: 'account_delete', 'family_delete', 'family_export', or 'consent_withdraw'",
    )


class ReauthenticateResponse(BaseModel):
    reauth_token: str
    action: str = "general"
    expires_in: int = 600
    reauthenticated_at: datetime


@router.post("/auth/reauthenticate", response_model=ReauthenticateResponse)
async def reauthenticate_user(
    payload: ReauthenticateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ReauthenticateResponse:
    """Dedicated re-authentication endpoint requiring fresh provider sign-in with recent auth_time.

    Required before performing sensitive operations:
    - Account and family deletion
    - Family data export
    - Parental consent withdrawal
    """
    from core.auth.provider import get_auth_provider, get_google_auth_provider
    from core.auth.tokens import create_reauth_jwt

    provider = get_auth_provider()
    try:
        auth_user = await provider.verify_token(payload.provider_token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_PROVIDER_CREDENTIAL", "message": f"Could not verify credential: {e}"},
        )

    # 1. Identity match check: Provider identity must match authenticated user
    identity_matched = False
    if current_user.auth_uid and auth_user.uid == current_user.auth_uid or current_user.phone and auth_user.phone and auth_user.phone == current_user.phone or current_user.email and auth_user.email and auth_user.email == current_user.email:
        identity_matched = True

    if not identity_matched:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "IDENTITY_MISMATCH", "message": "Provider credential does not match the active session user."},
        )

    # 2. Freshness check: auth_time must be within 300 seconds (5 minutes)
    now_epoch = int(datetime.now(UTC).timestamp())
    if auth_user.auth_time is not None:
        if (now_epoch - auth_user.auth_time) > 300:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "REAUTH_STALE", "message": "Authentication is too old. Fresh sign-in required within 5 minutes."},
            )

    # 3. Mint short-lived re-auth JWT (10 min TTL) bound to requested action
    token = create_reauth_jwt(current_user.id, action=payload.action)
    return ReauthenticateResponse(
        reauth_token=token,
        action=payload.action,
        expires_in=600,
        reauthenticated_at=datetime.now(UTC),
    )
