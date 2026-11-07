"""Central parental consent guard and suspended data policy enforcement.

Enforces parental consent gating across:
- Student chat and assessed quizzes
- Daily planner, study setup, and task completion
- AI planner suggestions, adjustments, and shadow runs
- Push notifications and student daily jobs
- Parent dashboard views of student learning data
- Automatic purge eligibility when suspension exceeds CONSENT_SUSPENSION_RETENTION_DAYS (30 days)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

from core.auth.models import User
from core.privacy.constants import CONSENT_SUSPENSION_RETENTION_DAYS

logger = logging.getLogger(__name__)


def assert_consent_active(user: User) -> None:
    """Enforce that active parental consent is on record before processing student data.

    Raises HTTP 403 CONSENT_WITHDRAWN for students whose consent has been suspended/withdrawn.
    Raises HTTP 403 PARENTAL_CONSENT_REQUIRED for parents who have not consented.
    """
    if user.role == "admin":
        return

    if not user.has_parental_consent:
        if user.role == "student":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "CONSENT_WITHDRAWN",
                    "message": "Parental consent is required to process minor student data. Academic processing is suspended.",
                },
            )
        elif user.role == "parent":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PARENTAL_CONSENT_REQUIRED",
                    "message": "Parental consent must be recorded before child data can be processed.",
                },
            )


def is_student_consent_active(student: User) -> bool:
    """Check if the student has active affirmative parental consent."""
    return bool(student.has_parental_consent)


def is_suspension_retention_expired(
    suspended_at: datetime,
    reference_time: datetime | None = None,
) -> bool:
    """Check whether a suspended account has exceeded the 30-day retention window."""
    now = reference_time or datetime.now(UTC)
    retention_cutoff = suspended_at + timedelta(days=CONSENT_SUSPENSION_RETENTION_DAYS)
    return now >= retention_cutoff

