"""Rate limiting utilities using Redis with in-memory fallback.

Enforces brute-force and abuse protection per docs/01_ARCHITECTURE.md §3
and docs/04_API_CONTRACT.md §1.
"""

from __future__ import annotations

import logging
import time
from typing import ClassVar

from core.common.redis import get_redis_client

logger = logging.getLogger(__name__)


class RateLimiter:
    """Fixed-window rate limiter backed by Redis with in-memory fallback."""

    # In-memory timestamp store for unit tests or when Redis is unreachable
    _memory_store: ClassVar[dict[str, list[float]]] = {}

    @classmethod
    async def check_rate_limit(
        cls,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """Check if request is permitted under rate limit.

        Args:
            key: Unique identifier (e.g. "link_redeem:127.0.0.1:device123")
            max_requests: Maximum allowed attempts in window
            window_seconds: Duration of rate limit window in seconds

        Returns:
            (is_allowed, retry_after_seconds)
        """
        # 1. Attempt Redis rate limit
        try:
            redis = get_redis_client()
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, window_seconds)
            if current > max_requests:
                ttl = await redis.ttl(key)
                return False, max(ttl, 1)
            return True, 0
        except Exception:
            # 2. In-memory sliding window fallback
            now = time.monotonic()
            history = cls._memory_store.setdefault(key, [])
            cutoff = now - window_seconds
            history = [ts for ts in history if ts > cutoff]
            cls._memory_store[key] = history

            if len(history) >= max_requests:
                oldest = history[0]
                retry_after = max(int(window_seconds - (now - oldest)), 1)
                return False, retry_after

            history.append(now)
            return True, 0

    @classmethod
    async def reset(cls) -> None:
        """Clear rate limit entries from memory and Redis (used in test fixtures)."""
        cls._memory_store.clear()
        try:
            redis = get_redis_client()
            keys = await redis.keys("rate_limit:*")
            if keys:
                await redis.delete(*keys)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed clearing Redis rate limit keys: %s", exc)
