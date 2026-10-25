"""FastAPI router for Parent Dashboard, Change Requests, and AI adjustments undo (P07)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.common.database import get_db_session
from core.families.models import ParentStudentLink
from core.parent.schemas import (
    ParentOverviewResponse,
    ReviewStudentChangeRequestBody,
    ReviewStudentChangeRequestResponse,
    StudentDashboardResponse,
)
from core.parent.service import ParentService

router = APIRouter(tags=["Parent Dashboard"])


# -----------------------------------------------------------------------------
# Authenticated User Paths (/parents/me/...)
# -----------------------------------------------------------------------------


@router.get(
    "/parents/me/dashboard",
    response_model=ParentOverviewResponse,
    status_code=status.HTTP_200_OK,
)
async def get_my_parent_overview_dashboard(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ParentOverviewResponse:
    """Retrieve consolidated overview across all linked children for authenticated parent."""
    if current_user.role not in ("parent", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Parent authorization required",
        )

    stmt = select(ParentStudentLink.student_id).where(
        ParentStudentLink.parent_id == current_user.id,
        ParentStudentLink.status == "active",
    )
    res = await db.execute(stmt)
    student_ids = res.scalars().all()

    student_dashboards: list[StudentDashboardResponse] = []
    for s_id in student_ids:
        try:
            sd = await ParentService.get_student_dashboard(db, current_user.id, s_id)
            student_dashboards.append(sd)
        except Exception:
            pass

    return ParentOverviewResponse(
        parent_id=current_user.id,
        students=student_dashboards,
    )


@router.get(
    "/parents/me/students/{student_id}/dashboard",
    response_model=StudentDashboardResponse,
    status_code=status.HTTP_200_OK,
)
async def get_my_student_dashboard(
    student_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> StudentDashboardResponse:
    """Retrieve growth-oriented dashboard for a student linked to authenticated parent."""
    if current_user.role not in ("parent", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Parent authorization required",
        )

    if current_user.role == "parent":
        await ParentService.verify_parent_student_link(db, current_user.id, student_id)

    return await ParentService.get_student_dashboard(db, current_user.id, student_id)


# -----------------------------------------------------------------------------
# Student Change Request Review Endpoints (Item 2)
# -----------------------------------------------------------------------------


@router.post(
    "/parents/me/students/{student_id}/change-requests/{request_id}/approve",
    response_model=ReviewStudentChangeRequestResponse,
    status_code=status.HTTP_200_OK,
)
async def approve_student_change_request_me(
    student_id: uuid.UUID,
    request_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    body: ReviewStudentChangeRequestBody | None = None,
) -> ReviewStudentChangeRequestResponse:
    """Approve a student study schedule change request and regenerate their plan."""
    if current_user.role not in ("parent", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Parent authorization required",
        )

    res = await ParentService.approve_student_change_request(
        db=db,
        parent_id=current_user.id,
        student_id=student_id,
        request_id=request_id,
        comment=body.comment if body else None,
    )
    return ReviewStudentChangeRequestResponse(
        status=res["status"],
        request_id=uuid.UUID(res["request_id"]),
        student_id=uuid.UUID(res["student_id"]),
        reviewed_at=res["reviewed_at"],
        new_plan_version=res.get("new_plan_version"),
        comment=body.comment if body else None,
    )


@router.post(
    "/parents/me/students/{student_id}/change-requests/{request_id}/decline",
    response_model=ReviewStudentChangeRequestResponse,
    status_code=status.HTTP_200_OK,
)
async def decline_student_change_request_me(
    student_id: uuid.UUID,
    request_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    body: ReviewStudentChangeRequestBody | None = None,
) -> ReviewStudentChangeRequestResponse:
    """Decline a student study schedule change request."""
    if current_user.role not in ("parent", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Parent authorization required",
        )

    res = await ParentService.decline_student_change_request(
        db=db,
        parent_id=current_user.id,
        student_id=student_id,
        request_id=request_id,
        comment=body.comment if body else None,
    )
    return ReviewStudentChangeRequestResponse(
        status=res["status"],
        request_id=uuid.UUID(res["request_id"]),
        student_id=uuid.UUID(res["student_id"]),
        reviewed_at=res["reviewed_at"],
        comment=res.get("comment"),
    )


# -----------------------------------------------------------------------------
# Explicit Parent ID Paths (with strict ID-mismatch rejection - Item 3)
# -----------------------------------------------------------------------------


@router.get(
    "/parents/{parent_id}/students/{student_id}/dashboard",
    response_model=StudentDashboardResponse,
    status_code=status.HTTP_200_OK,
)
async def get_parent_student_dashboard(
    parent_id: uuid.UUID,
    student_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> StudentDashboardResponse:
    """Retrieve growth-oriented dashboard for a student linked to requesting parent."""
    if current_user.role != "admin" and (current_user.role != "parent" or current_user.id != parent_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Parent ID mismatch - access denied",
        )

    if current_user.role == "parent":
        await ParentService.verify_parent_student_link(db, parent_id, student_id)

    return await ParentService.get_student_dashboard(db, parent_id, student_id)


@router.get(
    "/parents/{parent_id}/dashboard",
    response_model=ParentOverviewResponse,
    status_code=status.HTTP_200_OK,
)
async def get_parent_overview_dashboard(
    parent_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ParentOverviewResponse:
    """Retrieve consolidated overview across all linked children for this parent."""
    if current_user.role != "admin" and (current_user.role != "parent" or current_user.id != parent_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Parent ID mismatch - access denied",
        )

    stmt = select(ParentStudentLink.student_id).where(
        ParentStudentLink.parent_id == parent_id,
        ParentStudentLink.status == "active",
    )
    res = await db.execute(stmt)
    student_ids = res.scalars().all()

    student_dashboards: list[StudentDashboardResponse] = []
    for s_id in student_ids:
        try:
            sd = await ParentService.get_student_dashboard(db, parent_id, s_id)
            student_dashboards.append(sd)
        except Exception:
            pass

    return ParentOverviewResponse(
        parent_id=parent_id,
        students=student_dashboards,
    )


@router.post(
    "/parents/{parent_id}/students/{student_id}/change-requests/{request_id}/approve",
    response_model=ReviewStudentChangeRequestResponse,
    status_code=status.HTTP_200_OK,
)
async def approve_student_change_request_explicit(
    parent_id: uuid.UUID,
    student_id: uuid.UUID,
    request_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    body: ReviewStudentChangeRequestBody | None = None,
) -> ReviewStudentChangeRequestResponse:
    """Approve a student study schedule change request via explicit parent path."""
    if current_user.role != "admin" and (current_user.role != "parent" or current_user.id != parent_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Parent ID mismatch - access denied",
        )

    res = await ParentService.approve_student_change_request(
        db=db,
        parent_id=parent_id,
        student_id=student_id,
        request_id=request_id,
        comment=body.comment if body else None,
    )
    return ReviewStudentChangeRequestResponse(
        status=res["status"],
        request_id=uuid.UUID(res["request_id"]),
        student_id=uuid.UUID(res["student_id"]),
        reviewed_at=res["reviewed_at"],
        new_plan_version=res.get("new_plan_version"),
        comment=body.comment if body else None,
    )


@router.post(
    "/parents/{parent_id}/students/{student_id}/change-requests/{request_id}/decline",
    response_model=ReviewStudentChangeRequestResponse,
    status_code=status.HTTP_200_OK,
)
async def decline_student_change_request_explicit(
    parent_id: uuid.UUID,
    student_id: uuid.UUID,
    request_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    body: ReviewStudentChangeRequestBody | None = None,
) -> ReviewStudentChangeRequestResponse:
    """Decline a student study schedule change request via explicit parent path."""
    if current_user.role != "admin" and (current_user.role != "parent" or current_user.id != parent_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Parent ID mismatch - access denied",
        )

    res = await ParentService.decline_student_change_request(
        db=db,
        parent_id=parent_id,
        student_id=student_id,
        request_id=request_id,
        comment=body.comment if body else None,
    )
    return ReviewStudentChangeRequestResponse(
        status=res["status"],
        request_id=uuid.UUID(res["request_id"]),
        student_id=uuid.UUID(res["student_id"]),
        reviewed_at=res["reviewed_at"],
        comment=res.get("comment"),
    )


# -----------------------------------------------------------------------------
# AI Adjustment Undo (Item 2 & 5)
# -----------------------------------------------------------------------------


@router.post(
    "/students/{student_id}/ai-adjustments/{adjustment_id}/undo",
    status_code=status.HTTP_200_OK,
)
async def undo_student_ai_adjustment(
    student_id: uuid.UUID,
    adjustment_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    expected_version: int | None = Query(default=None),
) -> dict[str, Any]:
    """Parent one-tap undo endpoint to revert an auto-applied plan adjustment with optimistic lock."""
    if current_user.role != "parent" and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Parent authorization required",
        )

    return await ParentService.undo_ai_adjustment(
        db=db,
        parent_id=current_user.id,
        student_id=student_id,
        adjustment_id=adjustment_id,
        expected_version=expected_version,
    )
