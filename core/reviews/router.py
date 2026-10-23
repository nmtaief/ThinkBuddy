"""Teacher review and grading endpoints (Feature flagged off in beta).

Fulfills P01 requirement:
'Teacher/Admin present in RBAC but disabled by feature flag.
teacher routes return 404/403 while flag is off.'
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from core.auth.dependencies import require_role
from core.auth.models import User
from core.common.config import settings

router = APIRouter(prefix="/teacher", tags=["Teacher Reviews (Feature Flagged)"])


def require_teacher_feature_flag() -> None:
    """Dependency verifying that the teacher review module is enabled."""
    if not settings.TEACHER_REVIEW_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FEATURE_DISABLED",
                "message": "Teacher review feature is currently disabled in beta.",
            },
        )


class ReviewSubmissionRequest(BaseModel):
    score: float = Field(..., ge=0, le=100)
    comment: str = Field(..., min_length=1)
    flagged_topics: list[str] = Field(default_factory=list)


@router.get("/queue", dependencies=[Depends(require_teacher_feature_flag)])
async def get_teacher_review_queue(
    current_user: Annotated[User, Depends(require_role("teacher", "admin"))],
) -> dict[str, Any]:
    """Retrieve queue of broad submissions awaiting review."""
    return {"queue": []}


@router.post(
    "/submissions/{submission_id}/review", dependencies=[Depends(require_teacher_feature_flag)]
)
async def submit_teacher_review(
    submission_id: uuid.UUID,
    payload: ReviewSubmissionRequest,
    current_user: Annotated[User, Depends(require_role("teacher", "admin"))],
) -> dict[str, Any]:
    """Submit teacher evaluation and score for a written question."""
    return {"status": "reviewed", "submission_id": submission_id}


class FlagTopicRequest(BaseModel):
    topic_id: str = Field(..., min_length=1)


@router.post("/topics/flag", dependencies=[Depends(require_teacher_feature_flag)])
async def flag_difficult_topic(
    payload: FlagTopicRequest,
    current_user: Annotated[User, Depends(require_role("teacher", "admin"))],
) -> dict[str, Any]:
    """Flag a difficult topic to adjust adaptive revision weights."""
    return {"status": "flagged", "topic_id": payload.topic_id}
