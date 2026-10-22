"""Redis client management and readiness checks."""

import logging

import redis.asyncio as aioredis

from core.common.config import settings

logger = logging.getLogger(__name__)

_redis_client: aioredis.Redis | None = None


def get_redis_client() -> aioredis.Redis:
    """Return a singleton async Redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=3.0,
            socket_connect_timeout=3.0,
        )
    return _redis_client


async def close_redis() -> None:
    """Close active Redis connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


async def check_redis_ready() -> tuple[bool, str]:
    """Check Redis server responsiveness with PING."""
    try:
        client = get_redis_client()
        pong = await client.ping()
        if pong is True:
            return True, "Redis healthy"
        return False, "Redis ping failed"
    except Exception as exc:  # noqa: BLE001
        logger.error("Redis readiness check failed: %s", exc)
        return False, str(exc)
