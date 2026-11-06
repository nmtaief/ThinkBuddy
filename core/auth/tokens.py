"""JWT access token signing and rotating refresh token management."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from core.common.config import settings


def utcnow() -> datetime:
    return datetime.now(UTC)


def hash_token(token: str) -> str:
    """Return SHA-256 hash hex string of a secret token for secure database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_link_code(code: str) -> str:
    """Hash short link code using HMAC-SHA256 with server-side LINK_CODE_SECRET.

    Prevents precomputation and rainbow table attacks on short 8-character codes.
    """
    secret = settings.LINK_CODE_SECRET.encode("utf-8")
    normalized = code.strip().upper().encode("utf-8")
    return hmac.new(secret, normalized, hashlib.sha256).hexdigest()


def generate_secure_token(length_bytes: int = 32) -> str:
    """Generate cryptographically secure random hex token."""
    return secrets.token_hex(length_bytes)


def create_access_jwt(
    user_id: uuid.UUID,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create short-lived signed JWT access token."""
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = utcnow() + delta

    payload = {
        "jti": uuid.uuid4().hex,
        "sub": str(user_id),
        "role": role,
        "exp": int(expire.timestamp()),
        "iat": int(utcnow().timestamp()),
        "type": "access",
    }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_jwt(token: str) -> dict[str, Any]:
    """Verify and decode signed JWT access token.

    Raises jwt.PyJWTError on invalid, tampered, or expired tokens.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["exp", "sub", "role"]},
    )


def create_reauth_jwt(
    user_id: uuid.UUID,
    action: str = "general",
    expires_delta: timedelta | None = None,
) -> str:
    """Create short-lived signed JWT re-authentication token bound to user and action (TTL 10 minutes)."""
    delta = expires_delta or timedelta(minutes=10)
    expire = utcnow() + delta

    payload = {
        "jti": uuid.uuid4().hex,
        "sub": str(user_id),
        "action": action,
        "exp": int(expire.timestamp()),
        "iat": int(utcnow().timestamp()),
        "type": "reauth",
    }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_reauth_jwt(token: str) -> dict[str, Any]:
    """Verify and decode signed JWT re-authentication token.

    Raises jwt.PyJWTError on invalid, tampered, or expired tokens.
    """
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["exp", "sub", "type"]},
    )
    if payload.get("type") != "reauth":
        raise jwt.InvalidTokenError("Token is not a valid re-authentication token.")
    return payload
