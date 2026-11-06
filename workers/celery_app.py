"""Celery background worker application for ThinkBuddy."""

import os

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "thinkbuddy_workers",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["workers.planner_tasks", "workers.quiz_tasks", "workers.privacy_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    beat_schedule={
        "auto-submit-expired-quiz-attempts": {
            "task": "auto_submit_expired_attempts",
            "schedule": 30.0,
        },
        "purge-shadow-runs-retention": {
            "task": "purge_shadow_runs_retention_task",
            "schedule": 86400.0,  # daily purge
        },
        "dispatch-deferred-pushes-every-minute": {
            "task": "dispatch_deferred_pushes_task",
            "schedule": 60.0,  # every minute
        },
        "daily-privacy-data-purge": {
            "task": "daily_privacy_purge_task",
            "schedule": 86400.0,  # daily purge at 24h interval
        },
        "daily-consent-suspension-warnings": {
            "task": "daily_consent_suspension_warnings_task",
            "schedule": 86400.0,  # daily check for day-23 warnings
        },
    },
)


@celery_app.task(name="health_check")
def worker_health_check() -> dict[str, str]:
    """Basic health check task for background workers."""
    return {"status": "ok", "service": "worker"}
