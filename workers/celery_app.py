"""Celery background worker application for ThinkBuddy."""

import os

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "thinkbuddy_workers",
    broker=REDIS_URL,
    backend=REDIS_URL,
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
    },
)


@celery_app.task(name="health_check")
def worker_health_check() -> dict[str, str]:
    """Basic health check task for background workers."""
    return {"status": "ok", "service": "worker"}
