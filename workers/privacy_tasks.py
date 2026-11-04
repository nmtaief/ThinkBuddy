"""Celery background tasks for daily privacy data purge execution."""

from __future__ import annotations

import asyncio
import logging

from core.common.database import async_session_factory
from core.privacy.purge import execute_data_purge
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="daily_privacy_purge_task")
def daily_privacy_purge_task() -> dict[str, int]:
    """Daily scheduled background task to purge data for accounts past their 14-day grace period."""
    logger.info("Starting daily privacy data purge background job...")

    async def _run() -> dict[str, int]:
        async with async_session_factory() as session:
            report = await execute_data_purge(session)
            return {
                "purged_accounts": report.purged_accounts,
                "purged_families": report.purged_families,
                "revoked_sessions": report.revoked_sessions,
                "revoked_push_tokens": report.revoked_push_tokens,
                "deleted_notifications": report.deleted_notifications,
                "deleted_learning_signals": report.deleted_learning_signals,
                "deleted_shadow_runs": report.deleted_shadow_runs,
                "anonymized_audit_records": report.anonymized_audit_records,
            }

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(_run())

