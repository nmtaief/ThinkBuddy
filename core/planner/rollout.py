"""Dynamic rollout configuration and kill switch management for AI Planner (P06a Tail / P07).

Standing Rules & Deliverables:
- Durable Postgres storage in `ai_planner_rollout_configs` with Redis as read-through cache.
- Effective immediately across all workers and API instances via Redis cache invalidation/set.
- Fail closed: if both Redis and Postgres are unavailable or encounter errors, defaults to disabled (enabled=False).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from core.common.config import settings as app_settings
from core.common.database import AsyncSessionLocal
from core.common.redis import get_redis_client

logger = logging.getLogger("thinkbuddy.planner.rollout")

REDIS_ROLLOUT_KEY = "thinkbuddy:config:ai_planner"
REDIS_ROLLOUT_CHANNEL = "thinkbuddy:config:ai_planner:events"
REDIS_CACHE_TTL_SECONDS = 300


async def get_ai_planner_rollout_config() -> dict[str, Any]:
    """Retrieve active AI planner rollout config from Redis cache, falling back to durable Postgres.

    Fails closed (enabled=False) if both Redis and Postgres are unreachable.
    """
    # 1. Check Redis cache first
    try:
        redis = get_redis_client()
        raw = await redis.get(REDIS_ROLLOUT_KEY)
        if raw:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return json.loads(raw)
    except Exception as exc:
        logger.warning("Redis cache read failed for AI planner rollout: %s", exc)

    # 2. Read durable Postgres record
    try:
        async with AsyncSessionLocal() as session:
            stmt = text(
                "SELECT enabled, enabled_class_bands, version, updated_at "
                "FROM ai_planner_rollout_configs WHERE key = 'ai_planner'"
            )
            res = await session.execute(stmt)
            row = res.fetchone()
            if row:
                config_data = {
                    "enabled": bool(row[0]),
                    "shadow_mode": app_settings.AI_PLANNER_SHADOW_MODE,
                    "enabled_class_bands": list(row[1] or []),
                    "version": int(row[2]),
                    "updated_at": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
                    "updated_by": "postgres_durable",
                }
                # Populate Redis cache
                try:
                    redis = get_redis_client()
                    await redis.set(REDIS_ROLLOUT_KEY, json.dumps(config_data), ex=REDIS_CACHE_TTL_SECONDS)
                except Exception as r_err:
                    logger.debug("Failed to populate Redis cache: %s", r_err)
                return config_data
    except Exception as db_exc:
        logger.error("Postgres durable read failed for AI planner rollout: %s", db_exc)

    # 3. Fail-Closed Default (Rule 5: server is the authority, fail safe)
    logger.warning("Failing closed: AI planner disabled across all class bands")
    return {
        "enabled": False,
        "shadow_mode": False,
        "enabled_class_bands": [],
        "version": 0,
        "updated_at": datetime.now(UTC).isoformat(),
        "updated_by": "fail_closed_safe_default",
    }


async def set_ai_planner_rollout_config(
    enabled: bool | None = None,
    shadow_mode: bool | None = None,
    enabled_class_bands: list[str] | None = None,
    updated_by: str = "admin",
) -> dict[str, Any]:
    """Durably persist AI planner rollout config in Postgres and immediately synchronize Redis cache."""
    current = await get_ai_planner_rollout_config()
    new_version = current.get("version", 1) + 1

    updated = {
        "enabled": enabled if enabled is not None else current.get("enabled", False),
        "shadow_mode": (
            shadow_mode if shadow_mode is not None else current.get("shadow_mode", app_settings.AI_PLANNER_SHADOW_MODE)
        ),
        "enabled_class_bands": (
            enabled_class_bands
            if enabled_class_bands is not None
            else current.get("enabled_class_bands", ["9-10", "11-12"])
        ),
        "version": new_version,
        "updated_at": datetime.now(UTC).isoformat(),
        "updated_by": updated_by,
    }

    # 1. Durably persist to Postgres
    try:
        async with AsyncSessionLocal() as session:
            stmt = text(
                """
                INSERT INTO ai_planner_rollout_configs (key, enabled, enabled_class_bands, version, updated_at)
                VALUES ('ai_planner', :enabled, :bands, :version, now())
                ON CONFLICT (key) DO UPDATE SET
                    enabled = EXCLUDED.enabled,
                    enabled_class_bands = EXCLUDED.enabled_class_bands,
                    version = EXCLUDED.version,
                    updated_at = now()
                """
            )
            await session.execute(
                stmt,
                {
                    "enabled": updated["enabled"],
                    "bands": json.dumps(updated["enabled_class_bands"]),
                    "version": updated["version"],
                },
            )
            await session.commit()
    except Exception as db_err:
        logger.error("Failed to persist rollout config to Postgres: %s", db_err)
        raise

    # 2. Update application memory settings
    app_settings.AI_PLANNER_ENABLED = updated["enabled"]
    app_settings.AI_PLANNER_SHADOW_MODE = updated["shadow_mode"]
    app_settings.AI_PLANNER_ENABLED_CLASS_BANDS = list(updated["enabled_class_bands"])

    # 3. Update Redis cache immediately across all workers
    try:
        redis = get_redis_client()
        payload = json.dumps(updated)
        await redis.set(REDIS_ROLLOUT_KEY, payload, ex=REDIS_CACHE_TTL_SECONDS)
        await redis.publish(REDIS_ROLLOUT_CHANNEL, payload)
    except Exception as r_exc:
        logger.warning("Failed to synchronize Redis cache after DB persist: %s", r_exc)

    logger.info(
        "AI planner rollout config updated (enabled=%s, bands=%s, version=%d)",
        updated["enabled"],
        updated["enabled_class_bands"],
        updated["version"],
    )
    return updated
