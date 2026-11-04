"""Redis-backed rate limiting and brute-force lockout protection.

Enforces:
1. Rate limiting backend: Strictly Redis (per docs/01_ARCHITECTURE.md §3).
2. Key structure: Composite of action, trusted IP, and user/device identifier (action:ip:user).
3. Trusted IP source: Resolves client IP through trusted reverse proxy headers (X-Forwarded-For).
4. Lockout protection: Enforces 15-minute hard lockout after repeated failures (e.g., 5 failures).
"""

from __future__ import annotations

import ipaddress
import logging
from typing import TYPE_CHECKING

from core.common.config import settings
from core.common.redis import get_redis_client

if TYPE_CHECKING:
    from fastapi import Request

logger = logging.getLogger(__name__)


def is_peer_trusted_proxy(peer_ip: str, trusted_list: list[str] | None = None) -> bool:
    """Check if peer is among configured trusted proxy addresses or dedicated network CIDRs.

    Strictly restricted to explicit web container / gateway addresses.
    No whole private ranges (e.g. 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, or ip.is_private)
    and no hostnames are trusted.
    """
    if trusted_list is None:
        try:
            from gateway.config import settings as gw_settings
            trusted_list = list(gw_settings.GATEWAY_TRUSTED_PROXIES)
        except Exception:
            trusted_list = list(settings.TRUSTED_PROXIES)

    if peer_ip in trusted_list:
        return True
    try:
        ip = ipaddress.ip_address(peer_ip)
        for proxy_entry in trusted_list:
            if "/" in proxy_entry:
                try:
                    if ip in ipaddress.ip_network(proxy_entry, strict=False):
                        return True
                except ValueError:
                    continue
        if ip.is_loopback:
            return True
    except ValueError:
        pass
    return False


def get_trusted_client_ip(request: Request) -> str:
    """Extract client IP, verifying reverse proxy trust and parsing forwarded headers from the right.

    If request arrives via an untrusted peer (e.g. directly from a browser or attacker),
    any browser-supplied X-Forwarded-For header is strictly ignored and peer client host is returned.

    If request arrives via a trusted reverse proxy (e.g. Next.js BFF container 'web' or local proxy),
    we inspect the X-Forwarded-For chain from right to left.
    The first untrusted IP encountered when stepping back from the right is the real client IP.
    """
    peer_ip = request.client.host if request.client else "127.0.0.1"

    # If the direct peer is NOT a trusted proxy, browser-supplied X-Forwarded-For is ignored!
    if not is_peer_trusted_proxy(peer_ip):
        return peer_ip

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        hops = [ip.strip() for ip in forwarded_for.split(",") if ip.strip()]
        # Parse from the right: step back through trusted proxies until we find the real client
        for hop in reversed(hops):
            if not is_peer_trusted_proxy(hop):
                return hop
        if hops:
            return hops[0]

    real_ip = request.headers.get("x-real-ip")
    if real_ip and not is_peer_trusted_proxy(real_ip.strip()):
        return real_ip.strip()

    return peer_ip


def build_rate_limit_key(action: str, client_ip: str, identifier: str | None = None) -> str:
    """Build composite rate limit key combining action, client IP, and user/device ID."""
    ident = identifier.strip() if identifier else "anonymous"
    return f"rl:{action}:{client_ip}:{ident}"


import time

_mem_counters: dict[str, tuple[int, float]] = {}
_mem_lockouts: dict[str, float] = {}
_mem_failures: dict[str, tuple[int, float]] = {}
_redis_down_until: float = 0.0


class RateLimiter:
    """Distributed rate limiter and consecutive-failure lockout backed strictly by Redis,
    with local in-memory fallback for offline test environments.
    """

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
        global _redis_down_until
        now = time.monotonic()
        if now > _redis_down_until:
            try:
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
            except Exception:
                _redis_down_until = now + 10.0

        # Resilient in-memory fallback when Redis is offline or unreachable
        if key in _mem_lockouts:
            remaining = _mem_lockouts[key] - now
            if remaining > 0:
                return False, max(int(remaining), 1)
            del _mem_lockouts[key]

        count, expires_at = _mem_counters.get(key, (0, 0.0))
        if now >= expires_at:
            count = 0
            expires_at = now + window_seconds
        count += 1
        _mem_counters[key] = (count, expires_at)
        if count > max_requests:
            return False, max(int(expires_at - now), 1)
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
        try:
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
        except Exception:
            now = time.monotonic()
            count, expires_at = _mem_failures.get(key, (0, 0.0))
            if now >= expires_at:
                count = 0
                expires_at = now + failure_window_seconds
            count += 1
            _mem_failures[key] = (count, expires_at)
            if count >= max_consecutive_failures:
                _mem_lockouts[key] = now + lockout_duration_seconds
                _mem_failures.pop(key, None)
                return True, lockout_duration_seconds
            return False, 0

    @classmethod
    async def record_success(cls, key: str) -> None:
        """Clear failure tracker on successful operation."""
        try:
            redis = get_redis_client()
            await redis.delete(f"failures:{key}")
        except Exception:
            pass
        _mem_failures.pop(key, None)

    @classmethod
    async def increment_counter(cls, key: str, window_seconds: int = 60) -> int:
        """Increment a counter with an expiration window."""
        try:
            redis = get_redis_client()
            val = await redis.incr(key)
            if val == 1:
                await redis.expire(key, window_seconds)
            return val
        except Exception:
            now = time.monotonic()
            count, expires_at = _mem_counters.get(key, (0, 0.0))
            if now >= expires_at:
                count = 0
                expires_at = now + window_seconds
            count += 1
            _mem_counters[key] = (count, expires_at)
            return count

    @classmethod
    async def reset(cls) -> None:
        """Clear all rate limit, failure, and lockout keys from Redis and local memory."""
        _mem_counters.clear()
        _mem_lockouts.clear()
        _mem_failures.clear()
        try:
            redis = get_redis_client()
            for pattern in ("rl:*", "rate_limit:*", "lockout:*", "failures:*"):
                keys = await redis.keys(pattern)
                if keys:
                    await redis.delete(*keys)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed clearing Redis rate limit keys: %s", exc)
