"""FastAPI authentication and role authorization dependencies."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.models import User
from core.auth.tokens import decode_access_jwt
from core.common.database import get_db_session


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> User:
    """Extract and validate JWT Bearer token and return active User instance."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "MISSING_OR_INVALID_TOKEN",
                "message": "Valid Bearer access token is required.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_jwt(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "TOKEN_EXPIRED",
                "message": "Access token has expired. Refresh your session.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_TOKEN",
                "message": "Token signature verification failed.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN_SUBJECT", "message": "Invalid token subject."},
        )

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN_SUBJECT", "message": "Malformed token subject."},
        ) from None

    user = await session.get(User, user_uuid)

    if not user or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "USER_NOT_FOUND", "message": "User account no longer exists."},
        )

    if user.status not in ("active", "pending_deletion"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ACCOUNT_INACTIVE",
                "message": "User account is suspended or purged.",
            },
        )

    return user


def require_role(*allowed_roles: str) -> Callable[[User], Awaitable[User]]:
    """Factory dependency verifying user has one of the required roles."""

    async def role_checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN_ROLE",
                    "message": f"Operation requires one of: {', '.join(allowed_roles)}.",
                },
            )
        return user

    return role_checker
