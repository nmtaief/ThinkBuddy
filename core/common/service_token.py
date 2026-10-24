"""Signed JWT service tokens for internal inter-service authentication.

Per docs/04_API_CONTRACT.md and P04 hardening:
- Internal routes (/internal/*) are never reachable through the gateway.
- Inter-service calls require signed HS256 JWT tokens containing issuer, audience, and expiration.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
from fastapi import Header, HTTPException, status

from core.common.config import settings


def utcnow() -> datetime:
    return datetime.now(UTC)


def create_internal_service_token(
    issuer: str = "thinkbuddy-gateway",
    audience: str = "thinkbuddy-core",
    expires_minutes: int = 15,
) -> str:
    """Create short-lived signed JWT service token for internal communication."""
    now = utcnow()
    payload = {
        "jti": uuid.uuid4().hex,
        "iss": issuer,
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
        "role": "internal_service",
    }
    return jwt.encode(payload, settings.INTERNAL_SERVICE_SECRET, algorithm="HS256")


def verify_internal_service_token(token: str) -> dict[str, Any]:
    """Verify and decode signed internal service token.

    Raises HTTPException(403) on invalid, expired, or tampered tokens.
    """
    try:
        return jwt.decode(
            token,
            settings.INTERNAL_SERVICE_SECRET,
            algorithms=["HS256"],
            audience="thinkbuddy-core",
            options={"require": ["exp", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "SERVICE_TOKEN_EXPIRED", "message": "Internal service token has expired."},
        ) from None
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "SERVICE_TOKEN_INVALID", "message": "Invalid internal service token signature."},
        ) from None


async def require_internal_service_token(
    x_internal_service_token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> dict[str, Any]:
    """FastAPI dependency enforcing signed internal service token authentication."""
    token = x_internal_service_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "MISSING_SERVICE_TOKEN", "message": "Missing internal service authorization token."},
        )

    return verify_internal_service_token(token)
