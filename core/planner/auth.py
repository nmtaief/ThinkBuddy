"""Service-to-service authentication for AI Planner (P06a).

Generates short-lived HMAC-SHA256 signed service JWTs (60s validity)
with audience "ai-planner" and issuer "thinkbuddy-core".
"""

from __future__ import annotations

import time
import uuid
from typing import Any
import jwt


def create_ai_service_token(
    secret_key: str,
    client_id: str = "thinkbuddy-core",
    ttl_seconds: int = 60,
) -> str:
    """Generate a short-lived signed service token for the AI Planner service."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "iss": "thinkbuddy-core",
        "aud": "ai-planner",
        "sub": client_id,
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def verify_ai_service_token(token: str, secret_key: str) -> dict[str, Any]:
    """Verify an AI Planner service token."""
    return jwt.decode(
        token,
        secret_key,
        algorithms=["HS256"],
        audience="ai-planner",
        issuer="thinkbuddy-core",
    )
