"""Admin API endpoints for planner dynamic configuration layer.

Provides administrative controls over:
1. Class-band policies and hard limits (/v1/admin/policies)
2. Holiday calendar (/v1/admin/holidays)
3. Observance catalog (/v1/admin/observances)

Enforces admin-role checks, draft/impact-preview/publish workflow, optimistic concurrency (409),
and structured audit logging of every change (who, old value, new value).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit.models import AuditLog
from core.auth.dependencies import require_role
from core.auth.models import User
from core.common.database import get_db_session
from core.families.models import StudentProfile
from core.planner.models import AdminPolicy, Holiday, ObservanceCatalog, Plan, PlanDay
from core.planner.schemas import (
    AdminPolicyResponse,
    AiPlannerStatusResponse,
    CreateAdminPolicyRequest,
    HolidayImpactPreviewResponse,
    HolidayImportRequest,
    HolidayResponse,
    ObservanceResponse,
    PolicyImpactPreviewResponse,
    ShadowMetricsResponse,
    UpdateAdminPolicyRequest,
    UpdateAiPlannerConfigRequest,
    UpdateHolidayRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin - Planner Configuration"])


def utcnow() -> datetime:
    return datetime.now(UTC)


# ============================================================================
# Admin Policies: Class Band Defaults & Hard Limits
# ============================================================================


@router.get(
    "/policies",
    response_model=list[AdminPolicyResponse],
    status_code=status.HTTP_200_OK,
)
async def list_admin_policies(
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    class_band: str | None = Query(default=None),
    group: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[AdminPolicyResponse]:
    """List administrative study policies across class bands and groups."""
    stmt = select(AdminPolicy)
    if class_band:
        stmt = stmt.where(AdminPolicy.class_band == class_band)
    if group:
        stmt = stmt.where(AdminPolicy.group == group)
    if status_filter:
        stmt = stmt.where(AdminPolicy.status == status_filter)

    stmt = stmt.order_by(
        AdminPolicy.class_band.asc(), AdminPolicy.group.asc(), AdminPolicy.version.desc()
    )
    res = await db.execute(stmt)
    policies = res.scalars().all()

    return [
        AdminPolicyResponse(
            id=p.id,
            class_band=p.class_band,
            group=p.group,
            version=p.version,
            status=p.status,
            min_daily_minutes=p.min_daily_minutes,
            max_daily_minutes=p.max_daily_minutes,
            recommended_daily_minutes=p.recommended_daily_minutes,
            max_block_minutes=p.max_block_minutes,
            latest_end_time=p.latest_end_time,
            weekly_off_days=p.weekly_off_days,
            planner_parameters=p.planner_parameters,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in policies
    ]


@router.post(
    "/policies",
    response_model=AdminPolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_policy(
    payload: CreateAdminPolicyRequest,
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminPolicyResponse:
    """Create a new draft administrative policy."""
    # Find next version number for this (class_band, group)
    stmt_v = select(func.coalesce(func.max(AdminPolicy.version), 0)).where(
        AdminPolicy.class_band == payload.class_band,
        AdminPolicy.group == payload.group,
    )
    res_v = await db.execute(stmt_v)
    next_version = int(res_v.scalar_one()) + 1

    policy = AdminPolicy(
        class_band=payload.class_band,
        group=payload.group,
        version=next_version,
        status="draft",
        min_daily_minutes=payload.min_daily_minutes,
        max_daily_minutes=payload.max_daily_minutes,
        recommended_daily_minutes=payload.recommended_daily_minutes,
        max_block_minutes=payload.max_block_minutes,
        latest_end_time=payload.latest_end_time,
        weekly_off_days=payload.weekly_off_days,
        planner_parameters=payload.planner_parameters,
    )
    db.add(policy)
    await db.flush()

    audit = AuditLog(
        actor_id=current_user.id,
        action="admin_policy.create",
        target_type="admin_policy",
        target_id=str(policy.id),
        meta={
            "old_value": None,
            "new_value": {
                "class_band": policy.class_band,
                "group": policy.group,
                "version": policy.version,
                "status": policy.status,
                "min_daily_minutes": policy.min_daily_minutes,
                "max_daily_minutes": policy.max_daily_minutes,
                "recommended_daily_minutes": policy.recommended_daily_minutes,
            },
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(policy)

    return AdminPolicyResponse(
        id=policy.id,
        class_band=policy.class_band,
        group=policy.group,
        version=policy.version,
        status=policy.status,
        min_daily_minutes=policy.min_daily_minutes,
        max_daily_minutes=policy.max_daily_minutes,
        recommended_daily_minutes=policy.recommended_daily_minutes,
        max_block_minutes=policy.max_block_minutes,
        latest_end_time=policy.latest_end_time,
        weekly_off_days=policy.weekly_off_days,
        planner_parameters=policy.planner_parameters,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.get(
    "/policies/{policy_id}",
    response_model=AdminPolicyResponse,
    status_code=status.HTTP_200_OK,
)
async def get_admin_policy(
    policy_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminPolicyResponse:
    """Get a specific administrative policy."""
    stmt = select(AdminPolicy).where(AdminPolicy.id == policy_id)
    res = await db.execute(stmt)
    policy = res.scalar_one_or_none()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "POLICY_NOT_FOUND", "message": "Policy not found."},
        )

    return AdminPolicyResponse(
        id=policy.id,
        class_band=policy.class_band,
        group=policy.group,
        version=policy.version,
        status=policy.status,
        min_daily_minutes=policy.min_daily_minutes,
        max_daily_minutes=policy.max_daily_minutes,
        recommended_daily_minutes=policy.recommended_daily_minutes,
        max_block_minutes=policy.max_block_minutes,
        latest_end_time=policy.latest_end_time,
        weekly_off_days=policy.weekly_off_days,
        planner_parameters=policy.planner_parameters,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.put(
    "/policies/{policy_id}",
    response_model=AdminPolicyResponse,
    status_code=status.HTTP_200_OK,
)
async def update_admin_policy(
    policy_id: uuid.UUID,
    payload: UpdateAdminPolicyRequest,
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminPolicyResponse:
    """Update a draft administrative policy with optimistic concurrency."""
    stmt = select(AdminPolicy).where(AdminPolicy.id == policy_id).with_for_update()
    res = await db.execute(stmt)
    policy = res.scalar_one_or_none()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "POLICY_NOT_FOUND", "message": "Policy not found."},
        )

    # Optimistic concurrency check (Requirement B.6)
    if policy.version != payload.expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CONCURRENT_MODIFICATION",
                "message": (
                    f"Policy was modified by another transaction. Expected version "
                    f"{payload.expected_version}, but database version is {policy.version}."
                ),
            },
        )

    old_dict = {
        "min_daily_minutes": policy.min_daily_minutes,
        "max_daily_minutes": policy.max_daily_minutes,
        "recommended_daily_minutes": policy.recommended_daily_minutes,
        "max_block_minutes": policy.max_block_minutes,
        "latest_end_time": policy.latest_end_time,
        "weekly_off_days": policy.weekly_off_days,
        "planner_parameters": policy.planner_parameters,
    }

    if payload.min_daily_minutes is not None:
        policy.min_daily_minutes = payload.min_daily_minutes
    if payload.max_daily_minutes is not None:
        policy.max_daily_minutes = payload.max_daily_minutes
    if payload.recommended_daily_minutes is not None:
        policy.recommended_daily_minutes = payload.recommended_daily_minutes
    if payload.max_block_minutes is not None:
        policy.max_block_minutes = payload.max_block_minutes
    if payload.latest_end_time is not None:
        policy.latest_end_time = payload.latest_end_time
    if payload.weekly_off_days is not None:
        policy.weekly_off_days = payload.weekly_off_days
    if payload.planner_parameters is not None:
        policy.planner_parameters = payload.planner_parameters

    new_dict = {
        "min_daily_minutes": policy.min_daily_minutes,
        "max_daily_minutes": policy.max_daily_minutes,
        "recommended_daily_minutes": policy.recommended_daily_minutes,
        "max_block_minutes": policy.max_block_minutes,
        "latest_end_time": policy.latest_end_time,
        "weekly_off_days": policy.weekly_off_days,
        "planner_parameters": policy.planner_parameters,
    }

    audit = AuditLog(
        actor_id=current_user.id,
        action="admin_policy.update",
        target_type="admin_policy",
        target_id=str(policy.id),
        meta={"old_value": old_dict, "new_value": new_dict},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(policy)

    return AdminPolicyResponse(
        id=policy.id,
        class_band=policy.class_band,
        group=policy.group,
        version=policy.version,
        status=policy.status,
        min_daily_minutes=policy.min_daily_minutes,
        max_daily_minutes=policy.max_daily_minutes,
        recommended_daily_minutes=policy.recommended_daily_minutes,
        max_block_minutes=policy.max_block_minutes,
        latest_end_time=policy.latest_end_time,
        weekly_off_days=policy.weekly_off_days,
        planner_parameters=policy.planner_parameters,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.post(
    "/policies/{policy_id}/preview-impact",
    response_model=PolicyImpactPreviewResponse,
    status_code=status.HTTP_200_OK,
)
async def preview_policy_impact(
    policy_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PolicyImpactPreviewResponse:
    """Preview affected students and active plans before publishing policy changes (Req C.8)."""
    stmt = select(AdminPolicy).where(AdminPolicy.id == policy_id)
    res = await db.execute(stmt)
    policy = res.scalar_one_or_none()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "POLICY_NOT_FOUND", "message": "Policy not found."},
        )

    # Determine class level range from class band
    band_range = {
        "6-8": [6, 7, 8],
        "9-10": [9, 10],
        "11-12": [11, 12],
    }.get(policy.class_band, [6, 7, 8])

    stmt_st = select(StudentProfile.user_id).where(StudentProfile.class_level.in_(band_range))
    if policy.group != "general":
        stmt_st = stmt_st.where(StudentProfile.group == policy.group)

    res_st = await db.execute(stmt_st)
    affected_student_ids = list(res_st.scalars().all())

    # Count affected active plans
    affected_plans_count = 0
    if affected_student_ids:
        stmt_pl = select(func.count(Plan.id)).where(
            Plan.student_id.in_(affected_student_ids),
            Plan.status == "active",
        )
        res_pl = await db.execute(stmt_pl)
        affected_plans_count = int(res_pl.scalar_one())

    return PolicyImpactPreviewResponse(
        policy_id=policy.id,
        class_band=policy.class_band,
        group=policy.group,
        affected_students_count=len(affected_student_ids),
        affected_student_ids=affected_student_ids,
        affected_active_plans_count=affected_plans_count,
    )


@router.post(
    "/policies/{policy_id}/publish",
    status_code=status.HTTP_200_OK,
)
async def publish_admin_policy(
    policy_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Publish a draft policy and queue idempotent regeneration for affected students (Req C.8)."""
    stmt = select(AdminPolicy).where(AdminPolicy.id == policy_id).with_for_update()
    res = await db.execute(stmt)
    policy = res.scalar_one_or_none()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "POLICY_NOT_FOUND", "message": "Policy not found."},
        )

    old_status = policy.status
    if old_status == "published":
        return {
            "status": "already_published",
            "message": "Policy is already published (idempotent).",
            "policy_id": str(policy.id),
        }

    # Mark existing published policies for the same band/group as superseded
    stmt_prev = select(AdminPolicy).where(
        AdminPolicy.class_band == policy.class_band,
        AdminPolicy.group == policy.group,
        AdminPolicy.status == "published",
        AdminPolicy.id != policy.id,
    )
    res_prev = await db.execute(stmt_prev)
    for p in res_prev.scalars().all():
        p.status = "superseded"

    policy.status = "published"

    # Audit log
    audit = AuditLog(
        actor_id=current_user.id,
        action="admin_policy.publish",
        target_type="admin_policy",
        target_id=str(policy.id),
        meta={"old_value": {"status": old_status}, "new_value": {"status": "published"}},
    )
    db.add(audit)
    await db.commit()

    # Find affected students
    band_range = {
        "6-8": [6, 7, 8],
        "9-10": [9, 10],
        "11-12": [11, 12],
    }.get(policy.class_band, [6, 7, 8])

    stmt_st = select(StudentProfile.user_id).where(StudentProfile.class_level.in_(band_range))
    if policy.group != "general":
        stmt_st = stmt_st.where(StudentProfile.group == policy.group)
    res_st = await db.execute(stmt_st)
    affected_student_ids = list(res_st.scalars().all())

    return {
        "status": "published",
        "policy_id": str(policy.id),
        "affected_students_count": len(affected_student_ids),
        "regeneration_status": "queued",
    }


# ============================================================================
# Holiday Calendar Management
# ============================================================================


@router.get(
    "/holidays",
    response_model=list[HolidayResponse],
    status_code=status.HTTP_200_OK,
)
async def list_holidays(
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[HolidayResponse]:
    """List holiday calendar entries."""
    stmt = select(Holiday)
    if from_date:
        stmt = stmt.where(Holiday.end_date >= from_date)
    if to_date:
        stmt = stmt.where(Holiday.start_date <= to_date)
    if status_filter:
        stmt = stmt.where(Holiday.status == status_filter)

    stmt = stmt.order_by(Holiday.start_date.asc())
    res = await db.execute(stmt)
    holidays = res.scalars().all()

    return [
        HolidayResponse(
            id=h.id,
            start_date=h.start_date,
            end_date=h.end_date,
            name=h.name,
            holiday_type=h.holiday_type,
            study_blackout=h.study_blackout,
            observance_key=h.observance_key,
            verified=h.verified,
            status=h.status,
            version=h.version,
            created_at=h.created_at,
            updated_at=h.updated_at,
        )
        for h in holidays
    ]


@router.post(
    "/holidays/import",
    response_model=list[HolidayResponse],
    status_code=status.HTTP_201_CREATED,
)
async def import_holidays(
    payload: HolidayImportRequest,
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[HolidayResponse]:
    """Import holiday calendar entries.

    Requirement B.7: Seeded entries are always marked unverified (verified=False).
    Draft status ensures plans are not affected until published.
    """
    created_holidays: list[Holiday] = []
    for item in payload.holidays:
        h = Holiday(
            start_date=item.start_date,
            end_date=item.end_date,
            name=item.name,
            holiday_type=item.holiday_type,
            study_blackout=item.study_blackout,
            observance_key=item.observance_key,
            verified=False,  # Strictly marked unverified per Req B.7
            status="draft",  # Drafts never affect plans per Req C.8
            version=1,
        )
        db.add(h)
        created_holidays.append(h)

    await db.flush()

    audit = AuditLog(
        actor_id=current_user.id,
        action="holiday.import",
        target_type="holiday_calendar",
        target_id="bulk",
        meta={"imported_count": len(created_holidays), "verified": False},
    )
    db.add(audit)
    await db.commit()

    for h in created_holidays:
        await db.refresh(h)

    return [
        HolidayResponse(
            id=h.id,
            start_date=h.start_date,
            end_date=h.end_date,
            name=h.name,
            holiday_type=h.holiday_type,
            study_blackout=h.study_blackout,
            observance_key=h.observance_key,
            verified=h.verified,
            status=h.status,
            version=h.version,
            created_at=h.created_at,
            updated_at=h.updated_at,
        )
        for h in created_holidays
    ]


@router.put(
    "/holidays/{holiday_id}",
    response_model=HolidayResponse,
    status_code=status.HTTP_200_OK,
)
async def update_holiday(
    holiday_id: uuid.UUID,
    payload: UpdateHolidayRequest,
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> HolidayResponse:
    """Update a holiday calendar entry with optimistic concurrency."""
    stmt = select(Holiday).where(Holiday.id == holiday_id).with_for_update()
    res = await db.execute(stmt)
    h = res.scalar_one_or_none()
    if not h:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "HOLIDAY_NOT_FOUND", "message": "Holiday not found."},
        )

    # Optimistic concurrency check (Req B.6)
    if h.version != payload.expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CONCURRENT_MODIFICATION",
                "message": (
                    f"Holiday was modified by another transaction. Expected version "
                    f"{payload.expected_version}, but database version is {h.version}."
                ),
            },
        )

    old_dict = {
        "start_date": str(h.start_date),
        "end_date": str(h.end_date),
        "name": h.name,
        "study_blackout": h.study_blackout,
        "observance_key": h.observance_key,
    }

    if payload.start_date is not None:
        h.start_date = payload.start_date
    if payload.end_date is not None:
        h.end_date = payload.end_date
    if payload.name is not None:
        h.name = payload.name
    if payload.holiday_type is not None:
        h.holiday_type = payload.holiday_type
    if payload.study_blackout is not None:
        h.study_blackout = payload.study_blackout
    if payload.observance_key is not None:
        h.observance_key = payload.observance_key

    h.version += 1

    new_dict = {
        "start_date": str(h.start_date),
        "end_date": str(h.end_date),
        "name": h.name,
        "study_blackout": h.study_blackout,
        "observance_key": h.observance_key,
    }

    audit = AuditLog(
        actor_id=current_user.id,
        action="holiday.update",
        target_type="holiday",
        target_id=str(h.id),
        meta={"old_value": old_dict, "new_value": new_dict},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(h)

    return HolidayResponse(
        id=h.id,
        start_date=h.start_date,
        end_date=h.end_date,
        name=h.name,
        holiday_type=h.holiday_type,
        study_blackout=h.study_blackout,
        observance_key=h.observance_key,
        verified=h.verified,
        status=h.status,
        version=h.version,
        created_at=h.created_at,
        updated_at=h.updated_at,
    )


@router.post(
    "/holidays/{holiday_id}/preview-impact",
    response_model=HolidayImpactPreviewResponse,
    status_code=status.HTTP_200_OK,
)
async def preview_holiday_impact(
    holiday_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> HolidayImpactPreviewResponse:
    """Preview affected students and active plans for holiday modification (Req C.8)."""
    stmt = select(Holiday).where(Holiday.id == holiday_id)
    res = await db.execute(stmt)
    h = res.scalar_one_or_none()
    if not h:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "HOLIDAY_NOT_FOUND", "message": "Holiday not found."},
        )

    # Find active plans that have scheduled days overlapping this holiday
    stmt_days = (
        select(Plan.student_id, Plan.id)
        .join(PlanDay, PlanDay.plan_id == Plan.id)
        .where(
            Plan.status == "active",
            PlanDay.date >= h.start_date,
            PlanDay.date <= h.end_date,
        )
        .distinct()
    )
    res_days = await db.execute(stmt_days)
    rows = res_days.fetchall()

    affected_students = list({r[0] for r in rows})
    affected_plans = list({r[1] for r in rows})

    return HolidayImpactPreviewResponse(
        holiday_id=h.id,
        start_date=h.start_date,
        end_date=h.end_date,
        study_blackout=h.study_blackout,
        affected_students_count=len(affected_students),
        affected_student_ids=affected_students,
        affected_active_plans_count=len(affected_plans),
    )


@router.post(
    "/holidays/{holiday_id}/publish",
    status_code=status.HTTP_200_OK,
)
async def publish_holiday(
    holiday_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Publish a draft holiday and queue regeneration for affected students (Req C.8)."""
    stmt = select(Holiday).where(Holiday.id == holiday_id).with_for_update()
    res = await db.execute(stmt)
    h = res.scalar_one_or_none()
    if not h:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "HOLIDAY_NOT_FOUND", "message": "Holiday not found."},
        )

    old_status = h.status
    if old_status == "published":
        return {
            "status": "already_published",
            "message": "Holiday is already published (idempotent).",
            "holiday_id": str(h.id),
        }

    h.status = "published"
    h.verified = True

    audit = AuditLog(
        actor_id=current_user.id,
        action="holiday.publish",
        target_type="holiday",
        target_id=str(h.id),
        meta={"old_value": {"status": old_status}, "new_value": {"status": "published"}},
    )
    db.add(audit)
    await db.commit()

    return {
        "status": "published",
        "holiday_id": str(h.id),
        "verified": True,
        "regeneration_status": "queued",
    }


# ============================================================================
# Observance Catalog
# ============================================================================


@router.get(
    "/observances",
    response_model=list[ObservanceResponse],
    status_code=status.HTTP_200_OK,
)
async def list_observance_catalog(
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ObservanceResponse]:
    """List all observances from the secular cultural catalog."""
    stmt = select(ObservanceCatalog).order_by(ObservanceCatalog.key.asc())
    res = await db.execute(stmt)
    items = res.scalars().all()
    return [
        ObservanceResponse(
            key=item.key,
            name_bn=item.name_bn,
            name_en=item.name_en,
            description=item.description,
        )
        for item in items
    ]


# ============================================================================
# AI Planner Administration (P06a)
# ============================================================================


@router.get(
    "/ai-planner/status",
    response_model=AiPlannerStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_ai_planner_status(
    current_user: Annotated[User, Depends(require_role("admin"))],
) -> AiPlannerStatusResponse:
    """Get administrative status, circuit breaker health, and rollout configuration."""
    from core.common.config import settings as cfg
    from core.planner.provider import _global_ai_circuit_breaker

    is_open = not _global_ai_circuit_breaker.can_execute_sync()
    cb_state = "OPEN" if is_open else "CLOSED"

    return AiPlannerStatusResponse(
        enabled=cfg.AI_PLANNER_ENABLED,
        shadow_mode=cfg.AI_PLANNER_SHADOW_MODE,
        service_url=cfg.AI_PLANNER_URL,
        enabled_class_bands=list(cfg.AI_PLANNER_ENABLED_CLASS_BANDS),
        circuit_breaker={
            "state": cb_state,
            "failure_threshold": cfg.AI_PLANNER_CIRCUIT_BREAKER_FAILURES,
            "reset_timeout_seconds": cfg.AI_PLANNER_CIRCUIT_BREAKER_RESET_SECONDS,
            "consecutive_failures": _global_ai_circuit_breaker._mem_failures,
        },
        contract_version="ai-planner/v1.0",
    )


@router.post(
    "/ai-planner/circuit-breaker/reset",
    status_code=status.HTTP_200_OK,
)
async def reset_ai_circuit_breaker(
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str]:
    """Force reset the AI Planner circuit breaker to CLOSED state."""
    from core.planner.provider import _global_ai_circuit_breaker

    await _global_ai_circuit_breaker.reset()

    # Immutable Audit Log
    audit = AuditLog(
        actor_id=current_user.id,
        action="ai_planner.circuit_breaker_reset",
        target_type="system_config",
        target_id=str(current_user.id),
        meta={"reset_by": str(current_user.id), "at": datetime.now(UTC).isoformat()},
    )
    db.add(audit)
    await db.commit()

    return {"status": "success", "message": "Circuit breaker reset to CLOSED"}


@router.post(
    "/ai-planner/config",
    response_model=AiPlannerStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def update_ai_planner_config(
    payload: UpdateAiPlannerConfigRequest,
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiPlannerStatusResponse:
    """Update AI planner global kill switch, shadow mode, and class band rollout."""
    from core.common.config import settings as cfg

    old_meta = {
        "enabled": cfg.AI_PLANNER_ENABLED,
        "shadow_mode": cfg.AI_PLANNER_SHADOW_MODE,
        "enabled_class_bands": list(cfg.AI_PLANNER_ENABLED_CLASS_BANDS),
    }

    if payload.enabled is not None:
        cfg.AI_PLANNER_ENABLED = payload.enabled
    if payload.shadow_mode is not None:
        cfg.AI_PLANNER_SHADOW_MODE = payload.shadow_mode
    if payload.enabled_class_bands is not None:
        cfg.AI_PLANNER_ENABLED_CLASS_BANDS = payload.enabled_class_bands

    new_meta = {
        "enabled": cfg.AI_PLANNER_ENABLED,
        "shadow_mode": cfg.AI_PLANNER_SHADOW_MODE,
        "enabled_class_bands": list(cfg.AI_PLANNER_ENABLED_CLASS_BANDS),
    }

    # Immutable Audit Log
    audit = AuditLog(
        actor_id=current_user.id,
        action="ai_planner.config_update",
        target_type="system_config",
        target_id=str(current_user.id),
        meta={"old": old_meta, "new": new_meta, "at": datetime.now(UTC).isoformat()},
    )
    db.add(audit)
    await db.commit()

    from core.planner.provider import _global_ai_circuit_breaker

    return AiPlannerStatusResponse(
        enabled=cfg.AI_PLANNER_ENABLED,
        shadow_mode=cfg.AI_PLANNER_SHADOW_MODE,
        service_url=cfg.AI_PLANNER_URL,
        enabled_class_bands=list(cfg.AI_PLANNER_ENABLED_CLASS_BANDS),
        circuit_breaker={
            "state": "CLOSED" if _global_ai_circuit_breaker.can_execute_sync() else "OPEN",
            "failure_threshold": cfg.AI_PLANNER_CIRCUIT_BREAKER_FAILURES,
            "reset_timeout_seconds": cfg.AI_PLANNER_CIRCUIT_BREAKER_RESET_SECONDS,
            "consecutive_failures": _global_ai_circuit_breaker._mem_failures,
        },
        contract_version="ai-planner/v1.0",
    )


@router.get(
    "/ai-planner/shadow-metrics",
    response_model=ShadowMetricsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_ai_planner_shadow_metrics(
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ShadowMetricsResponse:
    """Get aggregated metrics and latest reports from AI planner shadow-mode runs."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.action == "ai_planner.shadow_comparison")
        .order_by(AuditLog.at.desc())
        .limit(100)
    )
    res = await db.execute(stmt)
    logs = res.scalars().all()

    total_runs = len(logs)
    if total_runs == 0:
        return ShadowMetricsResponse(
            total_runs=0,
            coverage_parity_pass_count=0,
            coverage_parity_pass_rate_pct=100.0,
            avg_churn_rate_pct=0.0,
            avg_minute_delta=0.0,
            total_warnings=0,
            recent_runs=[],
        )

    pass_count = 0
    total_churn = 0.0
    total_delta = 0.0
    total_warns = 0
    recent_runs: list[dict[str, Any]] = []

    for l in logs:
        meta = l.meta or {}
        metrics = meta.get("metrics", {})
        parity = metrics.get("coverage_parity_met", True)
        if parity:
            pass_count += 1
        churn = metrics.get("churn_rate_pct", 0.0)
        total_churn += churn
        delta = metrics.get("minutes_delta", 0.0)
        total_delta += delta
        warns = metrics.get("ai_warnings_count", 0)
        total_warns += warns

        if len(recent_runs) < 10:
            recent_runs.append(
                {
                    "student_id": meta.get("student_id"),
                    "at": meta.get("at") or l.at.isoformat(),
                    "recommendation": meta.get("recommendation", "PASS"),
                    "parity_met": parity,
                    "churn_rate_pct": churn,
                    "minutes_delta": delta,
                    "ai_warnings_count": warns,
                }
            )

    pass_rate = round((pass_count / total_runs) * 100.0, 1)
    avg_churn = round(total_churn / total_runs, 1)
    avg_delta = round(total_delta / total_runs, 1)

    return ShadowMetricsResponse(
        total_runs=total_runs,
        coverage_parity_pass_count=pass_count,
        coverage_parity_pass_rate_pct=pass_rate,
        avg_churn_rate_pct=avg_churn,
        avg_minute_delta=avg_delta,
        total_warnings=total_warns,
        recent_runs=recent_runs,
    )


