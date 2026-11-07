"""Background cleanup tasks for ThinkBuddy.

Deliverable:
- Cleans up expired chat idempotency records past their expires_at deadline.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.chat.models import ChatIdempotencyRecord
from core.common.database import AsyncSessionLocal
from workers.celery_app import celery_app

logger = logging.getLogger("thinkbuddy.workers.cleanup_tasks")


def utcnow() -> datetime:
    return datetime.now(UTC)


async def cleanup_expired_idempotency_records(db: AsyncSession | None = None) -> int:
    """Delete all expired idempotency records from chat_idempotency_records.

    Returns the count of purged rows.
    """
    now = utcnow()
    stmt = delete(ChatIdempotencyRecord).where(ChatIdempotencyRecord.expires_at <= now)

    if db is not None:
        result = await db.execute(stmt)
        await db.commit()
        deleted_count = result.rowcount or 0
        logger.info("Purged %d expired idempotency records", deleted_count)
        return deleted_count

    async with AsyncSessionLocal() as session:
        result = await session.execute(stmt)
        await session.commit()
        deleted_count = result.rowcount or 0
        logger.info("Purged %d expired idempotency records", deleted_count)
        return deleted_count


@celery_app.task(name="cleanup_expired_idempotency_records_task")
def cleanup_expired_idempotency_records_task() -> dict[str, Any]:
    """Celery scheduled task to automatically purge expired idempotency records."""
    count = asyncio.run(cleanup_expired_idempotency_records())
    return {"cleaned_records": count, "status": "success"}

