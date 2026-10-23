"""Redis-backed rate limiting and brute-force lockout protection.

Enforces:
1. Rate limiting backend: Strictly Redis (per docs/01_ARCHITECTURE.md §3).
2. Key structure: Composite of action, trusted IP, and user/device identifier (action:ip:user).
3. Trusted IP source: Resolves client IP through trusted reverse proxy headers (X-Forwarded-For).
4. Lockout protection: Enforces 15-minute hard lockout after repeated failures (e.g., 5 failures).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.common.config import settings
from core.common.redis import get_redis_client

if TYPE_CHECKING:
    from fastapi import Request

logger = logging.getLogger(__name__)


def get_trusted_client_ip(request: Request) -> str:
    """Extract client IP, verifying reverse proxy trust before reading forwarded headers.

    If request arrives via a trusted reverse proxy (e.g. Gateway / Docker bridge),
    extracts the origin client IP from X-Forwarded-For. Otherwise uses peer client host.
    """
    peer_ip = request.client.host if request.client else "127.0.0.1"

    # Check if peer is among trusted proxy list
    is_trusted_proxy = peer_ip in settings.TRUSTED_PROXIES or any(
        peer_ip.startswith(prefix) for prefix in ("127.", "10.", "172.16.", "192.168.")
    )

    if is_trusted_proxy:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Client IP is the first entry in comma-separated chain
            client_ip = forwarded_for.split(",")[0].strip()
            if client_ip:
                return client_ip
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

    return peer_ip


def build_rate_limit_key(action: str, client_ip: str, identifier: str | None = None) -> str:
    """Build composite rate limit key combining action, client IP, and user/device ID."""
    ident = identifier.strip() if identifier else "anonymous"
    return f"rl:{action}:{client_ip}:{ident}"


class RateLimiter:
    """Distributed rate limiter and consecutive-failure lockout backed strictly by Redis."""

    @classmethod
    async def check_rate_limit(
        cls,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """Check if request is permitted under fixed-window rate limit.

        Args:
            key: Composite identifier (e.g. "rl:link_redeem:127.0.0.1:user-123")
            max_requests: Maximum allowed attempts in window
            window_seconds: Duration of rate limit window in seconds

        Returns:
            (is_allowed, retry_after_seconds)
        """
        redis = get_redis_client()

        # 1. Check if key is currently in hard lockout
        lockout_key = f"lockout:{key}"
        lockout_ttl = await redis.ttl(lockout_key)
        if lockout_ttl > 0:
            return False, lockout_ttl

        # 2. Increment request counter
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, window_seconds)

        if current > max_requests:
            ttl = await redis.ttl(key)
            return False, max(ttl, 1)

        return True, 0

    @classmethod
    async def record_failure(
        cls,
        key: str,
        max_consecutive_failures: int = 5,
        failure_window_seconds: int = 300,
        lockout_duration_seconds: int = 900,
    ) -> tuple[bool, int]:
        """Record an operation failure and trigger lockout if failure threshold is reached.

        Args:
            key: Composite identifier (e.g. "rl:link_redeem:127.0.0.1:user-123")
            max_consecutive_failures: Number of failures before 15-minute lockout (default 5)
            failure_window_seconds: Time window for counting failures (default 5 min)
            lockout_duration_seconds: Duration of lockout upon reaching threshold (default 15 min)

        Returns:
            (is_locked_out, retry_after_seconds)
        """
        redis = get_redis_client()
        failure_key = f"failures:{key}"
        lockout_key = f"lockout:{key}"

        failures = await redis.incr(failure_key)
        if failures == 1:
            await redis.expire(failure_key, failure_window_seconds)

        if failures >= max_consecutive_failures:
            # Trigger hard lockout
            await redis.set(lockout_key, "locked", ex=lockout_duration_seconds)
            await redis.delete(failure_key)
            logger.warning(
                "Rate limit lockout triggered for key '%s' after %d consecutive failures.",
                key,
                failures,
            )
            return True, lockout_duration_seconds

        return False, 0

    @classmethod
    async def record_success(cls, key: str) -> None:
        """Clear failure tracker on successful operation."""
        redis = get_redis_client()
        await redis.delete(f"failures:{key}")

    @classmethod
    async def increment_counter(cls, key: str, window_seconds: int = 60) -> int:
        """Increment a counter with an expiration window."""
        redis = get_redis_client()
        val = await redis.incr(key)
        if val == 1:
            await redis.expire(key, window_seconds)
        return val

    @classmethod
    async def reset(cls) -> None:
        """Clear all rate limit, failure, and lockout keys from Redis (used in test fixtures)."""
        redis = get_redis_client()
        try:
            for pattern in ("rl:*", "rate_limit:*", "lockout:*", "failures:*"):
                keys = await redis.keys(pattern)
                if keys:
                    await redis.delete(*keys)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed clearing Redis rate limit keys: %s", exc)
