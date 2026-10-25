"""API routes for study setup, syllabus items, versioned planner, and daily tasks."""

from __future__ import annotations

import uuid
import zlib
from asyncio import Lock
from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.audit.models import AuditLog
from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.common.config import settings as app_settings
from core.common.database import get_db_session
from core.common.policy import can_access_student
from core.common.rate_limit import RateLimiter
from core.curriculum.models import Chapter
from core.families.models import ParentStudentLink, StudentProfile
from core.planner.engine import (
    ChapterPlanInput,
    CompletedTaskRecord,
    MultiSubjectPlanOutput,
    SubjectSetupInput,
    generate_student_plan,
)
from core.planner.provider import (
    AiPlannerProvider,
    PlanProviderContext,
    get_plan_provider,
)
from core.planner.models import (
    Plan,
    PlanDay,
    StudentChangeRequest,
    StudentStudySettings,
    StudySetup,
    SyllabusItem,
    Task,
)
from core.planner.schemas import (
    AiSuggestionResponse,
    DailyMinutesResponse,
    PlanDayResponse,
    PlanResponse,
    StudentChangeRequestInput,
    StudentChangeRequestResponse,
    StudentStudySettingsResponse,
    StudySetupResponse,
    SyllabusItemSummary,
    TaskResponse,
    TodayHomePayloadResponse,
    UpdateDailyMinutesRequest,
    UpdateStudentStudySettingsRequest,
    UpdateTaskStatusRequest,
    UpsertStudySetupRequest,
)
from core.planner.settings_resolver import (
    get_published_holidays,
    resolve_calendar_days,
    resolve_student_settings,
)

router = APIRouter(prefix="", tags=["Planner & Study Setup"])

_STUDENT_ASYNC_LOCKS: dict[uuid.UUID, Lock] = {}


def get_student_async_lock(student_id: uuid.UUID) -> Lock:
    """In-process per-student lock to serialize concurrent plan regenerations."""
    if student_id not in _STUDENT_ASYNC_LOCKS:
        _STUDENT_ASYNC_LOCKS[student_id] = Lock()
    return _STUDENT_ASYNC_LOCKS[student_id]


async def acquire_student_advisory_lock(db: AsyncSession, student_id: uuid.UUID) -> None:
    """Acquire transaction-level PostgreSQL advisory lock on student UUID."""
    bind = db.bind
    dialect_name = bind.dialect.name if bind else ""
    if dialect_name == "postgresql":
        lock_key = zlib.crc32(str(student_id).encode("utf-8")) & 0x7FFFFFFF
        await db.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})


def utcnow() -> datetime:
    return datetime.now(UTC)


async def execute_student_plan_regeneration(
    db: AsyncSession,
    student_id: uuid.UUID,
    reason: str = "regeneration",
    trigger_setup_id: uuid.UUID | None = None,
    future_only: bool = False,
) -> tuple[MultiSubjectPlanOutput, int]:
    """Execute serialized multi-subject plan regeneration under student advisory lock (v2)."""
    async with get_student_async_lock(student_id):
        await acquire_student_advisory_lock(db, student_id)

        # 1. Fetch student profile
        stmt_prof = select(StudentProfile).where(StudentProfile.user_id == student_id)
        res_prof = await db.execute(stmt_prof)
        profile = res_prof.scalar_one_or_none()
        if not profile:
            profile = StudentProfile(
                user_id=student_id,
                class_level=7,
                medium="bn",
                daily_minutes=60,
                available_days=["sat", "sun", "mon", "tue", "wed", "thu"],
                time_zone="Asia/Dhaka",
            )
            db.add(profile)
            await db.flush()

        tz_name = profile.time_zone or "Asia/Dhaka"
        try:
            user_tz = ZoneInfo(tz_name)
        except Exception:
            user_tz = ZoneInfo("Asia/Dhaka")
        now_dt = datetime.now(user_tz)
        today_dhaka = now_dt.date()

        # 2. Query max plan version
        stmt_max_v = select(func.coalesce(func.max(Plan.version), 0)).where(
            Plan.student_id == student_id
        )
        res_max_v = await db.execute(stmt_max_v)
        current_max_v = int(res_max_v.scalar_one())
        new_student_plan_version = max(current_max_v, profile.plan_version or 0) + 1
        profile.plan_version = new_student_plan_version

        # 3. Load all active setups for student
        stmt_all_setups = (
            select(StudySetup)
            .options(
                selectinload(StudySetup.syllabus_items)
                .selectinload(SyllabusItem.chapter)
                .selectinload(Chapter.book)
            )
            .where(StudySetup.student_id == student_id)
        )
        res_all_setups = await db.execute(stmt_all_setups)
        all_setups = res_all_setups.scalars().all()

        # 4. Resolve 3-tier settings
        resolved_settings = await resolve_student_settings(db, student_id)

        # 4b. Load student chapter mastery for adaptive input (P06)
        from core.progress.models import Mastery

        stmt_m = select(Mastery.chapter_id, Mastery.score).where(Mastery.student_id == student_id)
        res_m = await db.execute(stmt_m)
        student_mastery_map = dict(res_m.all())

        # 5. Prepare engine inputs
        engine_setups: list[SubjectSetupInput] = []
        exam_dates: set[date] = set()
        for s in all_setups:
            s.active_plan_version = new_student_plan_version
            if s.exam_date:
                exam_dates.add(s.exam_date)
            ch_inputs: list[ChapterPlanInput] = []
            for s_item in sorted(s.syllabus_items, key=lambda i: i.custom_order):
                if not s_item.included or not s_item.chapter:
                    continue
                ch = s_item.chapter
                ch_inputs.append(
                    ChapterPlanInput(
                        id=ch.id,
                        number=ch.number,
                        title=ch.title,
                        printed_page_start=ch.printed_page_start,
                        printed_page_end=ch.printed_page_end,
                        custom_order=s_item.custom_order,
                        book_id=ch.book_id,
                        book_title=ch.book.title if ch.book else "",
                        weight=s_item.weight,
                        difficulty_factor=s_item.custom_difficulty or ch.difficulty_factor or 1.0,
                        mastery=student_mastery_map.get(ch.id, 0.5),
                    )
                )
            engine_setups.append(
                SubjectSetupInput(
                    subject=s.subject,
                    exam_name=s.exam_name,
                    exam_date=s.exam_date,
                    chapters=ch_inputs,
                    setup_id=s.id,
                )
            )

        # 6. Load existing tasks
        stmt_existing_tasks = (
            select(Task, PlanDay.date, StudySetup.subject)
            .join(PlanDay, Task.plan_day_id == PlanDay.id)
            .join(Plan, PlanDay.plan_id == Plan.id)
            .join(StudySetup, Plan.setup_id == StudySetup.id)
            .where(Task.student_id == student_id)
        )
        res_existing_tasks = await db.execute(stmt_existing_tasks)
        all_task_rows = res_existing_tasks.fetchall()

        historical_records = [
            CompletedTaskRecord(
                task_id=t.id,
                subject=sub,
                chapter_id=t.chapter_id,
                plan_date=p_date,
                type=t.type,
                est_minutes=t.est_minutes,
                refs=t.refs,
                status=t.status,
                completed_at=t.completed_at.isoformat() if t.completed_at else None,
            )
            for t, p_date, sub in all_task_rows
        ]

        completed_minutes_today = sum(
            t.est_minutes
            for t, p_date, _ in all_task_rows
            if p_date == today_dhaka and t.status == "done"
        )

        max_horizon_date = max(
            exam_dates,
            default=today_dhaka + timedelta(days=60),
        )
        if max_horizon_date < today_dhaka + timedelta(days=30):
            max_horizon_date = today_dhaka + timedelta(days=30)

        published_holidays = await get_published_holidays(db, today_dhaka, max_horizon_date)
        day_calendar = resolve_calendar_days(
            start_date=today_dhaka,
            end_date=max_horizon_date,
            now=now_dt,
            resolved_settings=resolved_settings,
            published_holidays=published_holidays,
            exam_dates=exam_dates,
            completed_minutes_today=completed_minutes_today,
        )

        # Run Planner via PlanProvider Abstraction (P06a)
        provider_ctx = PlanProviderContext(
            student_id=student_id,
            today=today_dhaka,
            now_dhaka=now_dt,
            daily_study_minutes=resolved_settings.school_day_minutes,
            setups=engine_setups,
            available_days=profile.available_days,
            completed_tasks=historical_records,
            resolved_settings=resolved_settings,
            day_calendar=day_calendar,
        )

        plan_provider = get_plan_provider(resolved_settings)
        provider_result = await plan_provider.generate_plan(provider_ctx)
        plan_out = provider_result.plan_out

        # Shadow Mode: if enabled and primary is deterministic, evaluate AI planner in background
        if app_settings.AI_PLANNER_SHADOW_MODE and provider_result.provider == "deterministic":
            try:
                ai_shadow_provider = AiPlannerProvider()
                ai_shadow_res = await ai_shadow_provider.generate_plan(provider_ctx)
                if ai_shadow_res.plan_out:
                    from core.planner.shadow_comparator import compare_plans
                    shadow_report = compare_plans(ai_shadow_res.plan_out, plan_out)
                    provider_result.shadow_comparison = shadow_report
            except Exception as shadow_exc:
                logger.warning("AI Planner Shadow Mode execution error: %s", shadow_exc)

        # Record AI priority suggestions in 'suggest' mode for parent review
        if provider_result.priority_suggestions and resolved_settings.adaptive_mode in ("suggest", "manual"):
            for ps in provider_result.priority_suggestions:
                scr = StudentChangeRequest(
                    setup_id=None,
                    student_id=student_id,
                    requested_changes={
                        "type": "ai_priority_suggestion",
                        "subject": ps.get("subject"),
                        "current_level": ps.get("current_level"),
                        "suggested_level": ps.get("suggested_level"),
                        "evidence_codes": ps.get("evidence_codes", []),
                        "rationale": ps.get("rationale", ""),
                    },
                    status="pending",
                )
                db.add(scr)

        all_warnings = (
            list(plan_out.warnings)
            + list(resolved_settings.clamping_notices)
            + list(resolved_settings.warnings)
        )

        # Persist plans across ALL active setups for this student under new_student_plan_version
        for s in all_setups:
            old_plans_stmt = select(Plan).where(Plan.setup_id == s.id, Plan.status == "active")
            res_old = await db.execute(old_plans_stmt)
            for op in res_old.scalars().all():
                op.status = "superseded"

            plan_reason = reason
            if trigger_setup_id and s.id == trigger_setup_id and s.version > 1:
                plan_reason = "syllabus_change"
            elif trigger_setup_id and s.id != trigger_setup_id:
                plan_reason = "multi_subject_sync"

            new_plan = Plan(
                setup_id=s.id,
                student_id=student_id,
                version=new_student_plan_version,
                reason=plan_reason,
                status="active",
                provider=provider_result.provider,
                model_version=provider_result.model_version,
                contract_version=provider_result.contract_version,
                settings_version=provider_result.settings_version,
                generation_reason=provider_result.generation_reason,
                params={
                    "warnings": all_warnings,
                    "clamping_notices": resolved_settings.clamping_notices,
                    "settings_version": resolved_settings.settings_version,
                    "class_band": resolved_settings.class_band,
                    "group": resolved_settings.group,
                    "school_day_minutes": resolved_settings.school_day_minutes,
                    "holiday_minutes": resolved_settings.holiday_minutes,
                    "daily_minutes": resolved_settings.school_day_minutes,
                    "today": str(today_dhaka),
                    "rationale": provider_result.rationale,
                },
            )
            db.add(new_plan)
            await db.flush()

            for g_day in plan_out.days:
                sub_tasks = [t for t in g_day.tasks if t.subject == s.subject]
                if not sub_tasks:
                    continue

                p_day = PlanDay(
                    plan_id=new_plan.id,
                    date=g_day.date,
                    planned_minutes=sum(t.est_minutes for t in sub_tasks),
                    day_type=g_day.day_type,
                )
                db.add(p_day)
                await db.flush()

                for g_task in sub_tasks:
                    t_row = Task(
                        id=uuid.uuid4(),
                        plan_day_id=p_day.id,
                        student_id=student_id,
                        type=g_task.type,
                        chapter_id=uuid.UUID(str(g_task.chapter_id)) if g_task.chapter_id else None,
                        refs={**g_task.refs, "planned_task_id": str(g_task.id)},
                        est_minutes=g_task.est_minutes,
                        status=g_task.status,
                        source=g_task.source,
                        completed_at=datetime.fromisoformat(g_task.completed_at)
                        if g_task.completed_at
                        else None,
                    )
                    db.add(t_row)

        await db.commit()
        return plan_out, new_student_plan_version


@router.put(
    "/students/{student_id}/study-setups/{subject}",
    response_model=StudySetupResponse,
    status_code=status.HTTP_200_OK,
)
async def upsert_study_setup(
    student_id: uuid.UUID,
    subject: str,
    payload: UpsertStudySetupRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> StudySetupResponse:
    """Parent configures syllabus, exam date, and chapter order; system produces a versioned plan.

    Authorization:
    - Only parents linked to the student (or admins) may create/edit study setups.
    - Students are rejected with HTTP 403 (must use change requests).
    - Unlinked parents are rejected with HTTP 403.
    """
    subject_norm = subject.lower().strip()

    # 1. Authorization: Role check
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "STUDENT_CANNOT_EDIT_SETUP",
                "message": (
                    "Students cannot edit study setups directly; submit a change request instead."
                ),
            },
        )
    if current_user.role not in {"parent", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_ROLE",
                "message": "Only parents or admins may configure study setups.",
            },
        )

    # 2. Ownership check: verify active parent-student link
    if current_user.role == "parent":
        stmt_link = select(ParentStudentLink).where(
            ParentStudentLink.parent_id == current_user.id,
            ParentStudentLink.student_id == student_id,
            ParentStudentLink.status == "active",
            ParentStudentLink.revoked_at.is_(None),
        )
        res_link = await db.execute(stmt_link)
        if not res_link.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN_STUDENT_ACCESS",
                    "message": "You are not an active parent for this student.",
                },
            )

    # 3. Verify student exists and load profile
    stmt_student = (
        select(User)
        .options(selectinload(User.student_profile))
        .where(User.id == student_id, User.deleted_at.is_(None))
    )
    res_student = await db.execute(stmt_student)
    student = res_student.scalar_one_or_none()
    if not student or student.role != "student":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "STUDENT_NOT_FOUND", "message": "Student account not found."},
        )

    profile = student.student_profile
    if not profile:
        profile = StudentProfile(
            user_id=student.id,
            class_level=7,
            medium="bn",
            daily_minutes=60,
            available_days=["sat", "sun", "mon", "tue", "wed", "thu"],
            time_zone="Asia/Dhaka",
        )
        db.add(profile)
        await db.flush()

    # Update profile study parameters if provided
    if payload.daily_study_minutes is not None:
        profile.daily_minutes = payload.daily_study_minutes
    if payload.available_days is not None:
        profile.available_days = payload.available_days

    # 4. Resolve calendar dates and input validation
    tz_name = profile.time_zone or "Asia/Dhaka"
    try:
        user_tz = ZoneInfo(tz_name)
    except Exception:
        user_tz = ZoneInfo("Asia/Dhaka")

    today_dhaka = datetime.now(user_tz).date()

    if payload.exam_date < today_dhaka:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "EXAM_DATE_PAST",
                "message": f"Exam date {payload.exam_date} cannot be before today ({today_dhaka}).",
            },
        )
    if payload.exam_date > today_dhaka + (
        today_dhaka.replace(year=today_dhaka.year + 2) - today_dhaka
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "EXAM_DATE_TOO_FAR",
                "message": "Exam date cannot exceed 2 years from today.",
            },
        )

    # 5. Validate syllabus chapters belong to student's class and subject
    chapter_ids = [item.chapter_id for item in payload.syllabus if item.included]
    chapters_by_id: dict[uuid.UUID, Chapter] = {}
    if chapter_ids:
        stmt_ch = (
            select(Chapter).options(selectinload(Chapter.book)).where(Chapter.id.in_(chapter_ids))
        )
        res_ch = await db.execute(stmt_ch)
        fetched_chapters = res_ch.scalars().all()
        chapters_by_id = {ch.id: ch for ch in fetched_chapters}

        for item in payload.syllabus:
            if not item.included:
                continue
            ch = chapters_by_id.get(item.chapter_id)
            if not ch:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "CHAPTER_NOT_FOUND",
                        "message": f"Chapter {item.chapter_id} not found.",
                    },
                )
            if ch.book.subject.lower() != subject_norm:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "CHAPTER_SUBJECT_MISMATCH",
                        "message": (
                            f"Chapter {ch.number} belongs to subject '{ch.book.subject}', "
                            f"not '{subject_norm}'."
                        ),
                    },
                )
            if ch.book.class_level != profile.class_level:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "CHAPTER_CLASS_MISMATCH",
                        "message": (
                            f"Chapter {ch.number} belongs to class {ch.book.class_level}, "
                            f"not student's class {profile.class_level}."
                        ),
                    },
                )

    if payload.available_days is not None:
        profile.available_days = payload.available_days

    # 6. Concurrency Check: query existing setup with row lock
    stmt_existing = (
        select(StudySetup)
        .options(selectinload(StudySetup.syllabus_items))
        .where(StudySetup.student_id == student_id, StudySetup.subject == subject_norm)
        .with_for_update()
    )
    res_existing = await db.execute(stmt_existing)
    setup = res_existing.scalar_one_or_none()

    if setup:
        # Optimistic concurrency check
        if payload.expected_version is not None and setup.version != payload.expected_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "CONCURRENT_MODIFICATION",
                    "message": (
                        f"Study setup modified by another parent. Version: {setup.version}, "
                        f"expected: {payload.expected_version}."
                    ),
                },
            )
        setup.exam_name = payload.exam_name
        setup.exam_date = payload.exam_date
        setup.set_by_user_id = current_user.id
        setup.version += 1
        setup.active_plan_version += 1
        setup.updated_at = utcnow()
    else:
        setup = StudySetup(
            student_id=student_id,
            subject=subject_norm,
            exam_name=payload.exam_name,
            exam_date=payload.exam_date,
            set_by_user_id=current_user.id,
            version=1,
            active_plan_version=1,
        )
        db.add(setup)
        await db.flush()

    # 7. Replace syllabus items
    await db.execute(delete(SyllabusItem).where(SyllabusItem.setup_id == setup.id))
    new_syllabus_items: list[SyllabusItem] = []
    for item in payload.syllabus:
        s_item = SyllabusItem(
            setup_id=setup.id,
            chapter_id=item.chapter_id,
            included=item.included,
            custom_order=item.custom_order,
            weight=item.weight,
            custom_difficulty=item.custom_difficulty,
        )
        db.add(s_item)
        new_syllabus_items.append(s_item)

    await db.flush()

    # 8. Record audit log
    audit_row = AuditLog(
        actor_id=current_user.id,
        action="study_setup.upsert",
        target_type="study_setup",
        target_id=str(setup.id),
        meta={
            "student_id": str(student_id),
            "subject": subject_norm,
            "version": setup.version,
            "active_plan_version": setup.active_plan_version,
            "exam_date": str(setup.exam_date),
            "chapters_count": len([i for i in payload.syllabus if i.included]),
        },
    )
    db.add(audit_row)

    # 9. Concurrency lock: serialize plan regeneration per student (v2)
    plan_out, new_student_plan_version = await execute_student_plan_regeneration(
        db=db,
        student_id=student_id,
        reason="syllabus_change",
        trigger_setup_id=setup.id,
    )
    setup.active_plan_version = new_student_plan_version

    # Format response
    summary_items = [
        SyllabusItemSummary(
            id=item.id,
            chapter_id=item.chapter_id,
            chapter_number=chapters_by_id[item.chapter_id].number
            if item.chapter_id in chapters_by_id
            else None,
            chapter_title=chapters_by_id[item.chapter_id].title
            if item.chapter_id in chapters_by_id
            else None,
            included=item.included,
            custom_order=item.custom_order,
            weight=item.weight,
            custom_difficulty=item.custom_difficulty,
        )
        for item in new_syllabus_items
    ]

    return StudySetupResponse(
        id=setup.id,
        student_id=setup.student_id,
        subject=setup.subject,
        exam_name=setup.exam_name,
        exam_date=setup.exam_date,
        active_plan_version=setup.active_plan_version,
        version=setup.version,
        syllabus=summary_items,
        warnings=plan_out.warnings,
        created_at=setup.created_at,
        updated_at=setup.updated_at,
    )


@router.post(
    "/students/{student_id}/study-setups/{subject}/change-requests",
    response_model=StudentChangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_student_change_request(
    student_id: uuid.UUID,
    subject: str,
    payload: StudentChangeRequestInput,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> StudentChangeRequestResponse:
    """Student submits a proposed modification to their study setup."""
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "STUDENT_ONLY",
                "message": "Only students may submit study setup change requests.",
            },
        )
    if current_user.id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN",
                "message": "Cannot submit change request for another student.",
            },
        )

    stmt_setup = select(StudySetup).where(
        StudySetup.student_id == student_id, StudySetup.subject == subject.lower().strip()
    )
    res_setup = await db.execute(stmt_setup)
    setup = res_setup.scalar_one_or_none()
    if not setup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "SETUP_NOT_FOUND",
                "message": f"Study setup for subject '{subject}' not found.",
            },
        )

    req = StudentChangeRequest(
        setup_id=setup.id,
        student_id=student_id,
        requested_changes=payload.requested_changes,
        status="pending",
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)

    return StudentChangeRequestResponse(
        id=req.id,
        setup_id=req.setup_id,
        student_id=req.student_id,
        requested_changes=req.requested_changes,
        status=req.status,
        created_at=req.created_at,
    )


@router.get("/students/{student_id}/plan", response_model=PlanResponse)
async def get_student_plan(
    student_id: uuid.UUID,
    subject: str | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> PlanResponse:
    """Fetch active study plan with tasks and planned minutes."""
    has_access = await can_access_student(current_user, student_id, db)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_STUDENT_ACCESS",
                "message": "You cannot view this student's study plan.",
            },
        )

    stmt_plan = (
        select(Plan)
        .options(
            selectinload(Plan.days).selectinload(PlanDay.tasks),
            selectinload(Plan.setup),
        )
        .where(Plan.student_id == student_id, Plan.status == "active")
        .order_by(Plan.version.desc())
    )
    if subject:
        stmt_plan = stmt_plan.join(StudySetup, Plan.setup_id == StudySetup.id).where(
            StudySetup.subject == subject.lower().strip()
        )

    res_plan = await db.execute(stmt_plan)
    plans = res_plan.scalars().all()
    if not plans:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PLAN_NOT_FOUND", "message": "No active study plan found for student."},
        )

    primary_plan = plans[0]
    days_by_date: dict[date, tuple[str, list[TaskResponse]]] = {}
    all_warnings: list[str] = []

    for p in plans:
        all_warnings.extend(p.params.get("warnings", []))
        for d in p.days:
            if from_date and d.date < from_date:
                continue
            if to_date and d.date > to_date:
                continue

            if d.date not in days_by_date:
                days_by_date[d.date] = (d.day_type, [])

            cur_type, t_list = days_by_date[d.date]
            if d.day_type in ("revision", "buffer") and cur_type == "study":
                cur_type = d.day_type
                days_by_date[d.date] = (cur_type, t_list)

            for t in d.tasks:
                sub_name = p.setup.subject if p.setup else "general"
                t_list.append(
                    TaskResponse(
                        id=t.id,
                        plan_day_id=t.plan_day_id,
                        student_id=t.student_id,
                        subject=sub_name,
                        type=t.type,
                        chapter_id=t.chapter_id,
                        refs=t.refs,
                        est_minutes=t.est_minutes,
                        status=t.status,
                        source=t.source,
                        completed_at=t.completed_at,
                    )
                )

    day_items: list[PlanDayResponse] = []
    for d_date in sorted(days_by_date.keys()):
        d_type, t_items = days_by_date[d_date]
        day_items.append(
            PlanDayResponse(
                date=d_date,
                planned_minutes=sum(t.est_minutes for t in t_items),
                day_type=d_type,
                tasks=t_items,
            )
        )

    return PlanResponse(
        setup_id=primary_plan.setup_id,
        student_id=primary_plan.student_id,
        version=primary_plan.version,
        generated_at=primary_plan.generated_at,
        reason=primary_plan.reason,
        status=primary_plan.status,
        days=day_items,
        warnings=all_warnings,
        provider=getattr(primary_plan, "provider", "deterministic") or "deterministic",
        model_version=getattr(primary_plan, "model_version", "v2-rules") or "v2-rules",
        contract_version=getattr(primary_plan, "contract_version", "p03-engine") or "p03-engine",
        settings_version=getattr(primary_plan, "settings_version", 1) or 1,
        generation_reason=getattr(primary_plan, "generation_reason", "deterministic_baseline") or "deterministic_baseline",
        rationale=primary_plan.params.get("rationale", {}) if primary_plan.params else {},
    )


@router.get("/students/{student_id}/today", response_model=TodayHomePayloadResponse)
async def get_today_payload(
    student_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TodayHomePayloadResponse:
    """Home screen learning loop payload (Product Flows §4.2 / Rule 4)."""
    has_access = await can_access_student(current_user, student_id, db)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_STUDENT_ACCESS",
                "message": "You cannot view this student's tasks.",
            },
        )

    # 1. Resolve student timezone
    stmt_profile = select(StudentProfile).where(StudentProfile.user_id == student_id)
    res_prof = await db.execute(stmt_profile)
    profile = res_prof.scalar_one_or_none()

    tz_name = profile.time_zone if profile else "Asia/Dhaka"
    try:
        user_tz = ZoneInfo(tz_name)
    except Exception:
        user_tz = ZoneInfo("Asia/Dhaka")

    today_date = datetime.now(user_tz).date()

    # 2. Query today's tasks
    stmt_tasks = (
        select(Task, StudySetup.subject)
        .join(PlanDay, Task.plan_day_id == PlanDay.id)
        .join(Plan, PlanDay.plan_id == Plan.id)
        .join(StudySetup, Plan.setup_id == StudySetup.id)
        .where(
            Task.student_id == student_id,
            PlanDay.date == today_date,
            Plan.status == "active",
        )
    )
    res_tasks = await db.execute(stmt_tasks)
    rows = res_tasks.fetchall()

    study_tasks: list[TaskResponse] = []
    rev_tasks: list[TaskResponse] = []
    hw_tasks: list[TaskResponse] = []
    quiz_tasks: list[TaskResponse] = []
    total_planned = 0
    completed_mins = 0

    for task, sub in rows:
        t_resp = TaskResponse(
            id=task.id,
            plan_day_id=task.plan_day_id,
            student_id=task.student_id,
            subject=sub,
            type=task.type,
            chapter_id=task.chapter_id,
            refs=task.refs,
            est_minutes=task.est_minutes,
            status=task.status,
            source=task.source,
            completed_at=task.completed_at,
        )
        total_planned += task.est_minutes
        if task.status == "done":
            completed_mins += task.est_minutes

        if task.type == "study":
            study_tasks.append(t_resp)
        elif task.type == "revision":
            rev_tasks.append(t_resp)
        elif task.type == "homework":
            hw_tasks.append(t_resp)
        elif task.type in {"quiz", "review_quiz"}:
            quiz_tasks.append(t_resp)

    # 3. Calculate exam countdowns
    stmt_setups = select(StudySetup).where(StudySetup.student_id == student_id)
    res_setups = await db.execute(stmt_setups)
    setups = res_setups.scalars().all()
    countdowns: dict[str, int] = {}
    for s in setups:
        diff = (s.exam_date - today_date).days
        countdowns[s.subject] = max(0, diff)

    completion_pct = (completed_mins / total_planned * 100.0) if total_planned > 0 else 0.0

    # 4. Resolve active plan provenance and parent rationale
    stmt_act_plan = (
        select(Plan)
        .where(Plan.student_id == student_id, Plan.status == "active")
        .order_by(Plan.version.desc())
    )
    res_act = await db.execute(stmt_act_plan)
    act_plan = res_act.scalars().first()

    prov = getattr(act_plan, "provider", "deterministic") if act_plan else "deterministic"
    gen_reason = getattr(act_plan, "generation_reason", "deterministic_baseline") if act_plan else "deterministic_baseline"
    rationale_map = act_plan.params.get("rationale", {}) if act_plan and act_plan.params else {}
    reason_for_parents = next(
        iter(rationale_map.values()),
        "Study plan optimized for syllabus coverage, priority appearance, and spaced retention.",
    )

    return TodayHomePayloadResponse(
        date=today_date,
        student_id=student_id,
        study_tasks=study_tasks,
        revision_tasks=rev_tasks,
        homework_tasks=hw_tasks,
        quiz_tasks=quiz_tasks,
        total_planned_minutes=total_planned,
        completed_minutes=completed_mins,
        completion_percentage=round(completion_pct, 1),
        exam_countdown_days=countdowns,
        streak=1,
        provider=prov or "deterministic",
        generation_reason=gen_reason or "deterministic_baseline",
        reason_for_parents=reason_for_parents,
    )


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task_status(
    task_id: uuid.UUID,
    payload: UpdateTaskStatusRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaskResponse:
    """Update task status.

    Authorization:
    - ONLY the student owning the task may update completion status.
    - Parents are strictly read-only on task status (HTTP 403 TASK_UPDATE_STUDENT_ONLY).
    - Other students are rejected with HTTP 403 (FORBIDDEN).
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "TASK_UPDATE_STUDENT_ONLY",
                "message": (
                    "Only students may update task completion status; parents are read-only."
                ),
            },
        )

    stmt_task = (
        select(Task, StudySetup.subject, PlanDay.date)
        .join(PlanDay, Task.plan_day_id == PlanDay.id)
        .join(Plan, PlanDay.plan_id == Plan.id)
        .join(StudySetup, Plan.setup_id == StudySetup.id)
        .where(Task.id == task_id)
    )
    res_task = await db.execute(stmt_task)
    row = res_task.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TASK_NOT_FOUND", "message": "Task not found."},
        )

    task, sub, plan_date = row
    if task.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Cannot modify another student's task."},
        )

    # 1. Status state machine
    valid_transitions: dict[str, set[str]] = {
        "todo": {"in_progress", "done", "skipped", "rolled"},
        "in_progress": {"todo", "done", "skipped"},
        "done": {"todo"},
        "skipped": {"todo"},
        "rolled": {"todo"},
    }
    if payload.status != task.status and payload.status not in valid_transitions.get(
        task.status, set()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_TASK_STATUS_TRANSITION",
                "message": (
                    f"Cannot transition task status from '{task.status}' to '{payload.status}'."
                ),
            },
        )

    # 2. Date check: only allow completing tasks dated today or earlier in student's timezone
    if payload.status == "done":
        profile = await db.get(StudentProfile, task.student_id)
        tz_name = profile.time_zone if profile and profile.time_zone else "Asia/Dhaka"
        try:
            student_tz = ZoneInfo(tz_name)
        except Exception:
            student_tz = ZoneInfo("Asia/Dhaka")
        student_today = datetime.now(student_tz).date()

        if plan_date > student_today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "FUTURE_TASK_COMPLETION_FORBIDDEN",
                    "message": (
                        f"Cannot mark future task scheduled for {plan_date} as completed. "
                        f"Today is {student_today}."
                    ),
                },
            )
        task.completed_at = utcnow()
    else:
        task.completed_at = None

    old_status = task.status
    task.status = payload.status

    # 3. Audit log
    audit_row = AuditLog(
        actor_id=current_user.id,
        action="task.status_update",
        target_type="task",
        target_id=str(task.id),
        meta={
            "student_id": str(task.student_id),
            "old_status": old_status,
            "new_status": payload.status,
            "plan_date": str(plan_date),
        },
    )
    db.add(audit_row)

    await db.commit()
    await db.refresh(task)

    return TaskResponse(
        id=task.id,
        plan_day_id=task.plan_day_id,
        student_id=task.student_id,
        subject=sub,
        type=task.type,
        chapter_id=task.chapter_id,
        refs=task.refs,
        est_minutes=task.est_minutes,
        status=task.status,
        source=task.source,
        completed_at=task.completed_at,
    )


@router.put(
    "/students/{student_id}/daily-minutes",
    response_model=DailyMinutesResponse,
    status_code=status.HTTP_200_OK,
)
async def update_student_daily_minutes(
    student_id: uuid.UUID,
    payload: UpdateDailyMinutesRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> DailyMinutesResponse:
    """Update student-level daily minutes budget.

    Authorization:
    - Only authorized linked parents may update student daily minutes.
    - Students are rejected with HTTP 403 (PARENT_ROLE_REQUIRED).
    - Unlinked parents are rejected with HTTP 403 (FAMILY_ACCESS_DENIED).
    """
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PARENT_ROLE_REQUIRED",
                "message": "Only parents may modify student daily study budget.",
            },
        )

    stmt_link = select(ParentStudentLink).where(
        ParentStudentLink.parent_id == current_user.id,
        ParentStudentLink.student_id == student_id,
        ParentStudentLink.status == "active",
        ParentStudentLink.revoked_at.is_(None),
    )
    res_link = await db.execute(stmt_link)
    if not res_link.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FAMILY_ACCESS_DENIED",
                "message": "You are not an active parent for this student.",
            },
        )

    profile = await db.get(StudentProfile, student_id)
    if not profile:
        profile = StudentProfile(
            user_id=student_id,
            class_level=7,
            medium="bn",
            daily_minutes=payload.daily_minutes,
            available_days=["sat", "sun", "mon", "tue", "wed", "thu"],
            time_zone="Asia/Dhaka",
        )
        db.add(profile)
    else:
        profile.daily_minutes = payload.daily_minutes

    audit_row = AuditLog(
        actor_id=current_user.id,
        action="student.update_daily_minutes",
        target_type="student_profile",
        target_id=str(student_id),
        meta={"daily_minutes": payload.daily_minutes},
    )
    db.add(audit_row)
    await db.commit()

    return DailyMinutesResponse(
        student_id=student_id,
        daily_minutes=profile.daily_minutes,
    )


@router.get(
    "/students/{student_id}/study-settings",
    response_model=StudentStudySettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_student_study_settings(
    student_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> StudentStudySettingsResponse:
    """Get resolved study settings, clamping notices, and admin hard limits for a student."""
    has_access = await can_access_student(current_user, student_id, db)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_STUDENT_ACCESS",
                "message": "You are not authorized to view this student's study settings.",
            },
        )

    resolved = await resolve_student_settings(db, student_id)

    # Fetch raw settings model if exists
    stmt = select(StudentStudySettings).where(StudentStudySettings.student_id == student_id)
    res = await db.execute(stmt)
    raw = res.scalar_one_or_none()

    setting_id = raw.id if raw else uuid.uuid4()
    version = raw.version if raw else 1

    return StudentStudySettingsResponse(
        id=setting_id,
        student_id=student_id,
        school_day_minutes=resolved.school_day_minutes,
        holiday_minutes=resolved.holiday_minutes,
        study_window_start=resolved.study_window_start,
        study_window_end=resolved.study_window_end,
        recurring_unavailable_blocks=resolved.recurring_unavailable_blocks,
        blocked_observance_keys=resolved.blocked_observance_keys,
        custom_blackout_dates=resolved.custom_blackout_dates,
        subject_priorities=resolved.subject_priorities,
        rest_weekday=resolved.rest_weekday,
        adaptive_mode=resolved.adaptive_mode,
        ai_adjustments=resolved.ai_adjustments,
        parent_locked_fields=resolved.parent_locked_fields,
        version=version,
        clamping_notices=resolved.clamping_notices,
        warnings=resolved.warnings,
        recommended_daily_minutes=resolved.recommended_daily_minutes,
        admin_hard_limits=resolved.admin_hard_limits,
    )


@router.put(
    "/students/{student_id}/study-settings",
    response_model=StudentStudySettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def update_student_study_settings(
    student_id: uuid.UUID,
    payload: UpdateStudentStudySettingsRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> StudentStudySettingsResponse:
    """Parent updates student study settings.

    Authorization:
    - Only parents linked to the student (or admins) may update study settings.
    - Students are rejected with HTTP 403 (STUDENT_CANNOT_EDIT_SETTINGS).
    - Unlinked parents are rejected with HTTP 403 (FAMILY_ACCESS_DENIED).
    Rate-limiting:
    - Parent regeneration requests are debounced and rate-limited.
    Optimistic Concurrency:
    - Verifies expected_version; returns HTTP 409 if version mismatch.
    """
    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "STUDENT_CANNOT_EDIT_SETTINGS",
                "message": (
                    "Students cannot edit study settings directly; submit a change request instead."
                ),
            },
        )

    has_access = await can_access_student(current_user, student_id, db)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FAMILY_ACCESS_DENIED",
                "message": "You are not authorized to manage this student's settings.",
            },
        )

    # Debounce / rate limit parent regeneration
    rate_key = f"rl:parent_regen:parent:{current_user.id}:student:{student_id}"
    allowed, retry_after = await RateLimiter.check_rate_limit(
        rate_key, max_requests=10, window_seconds=60
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            detail={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": (
                    "Too many settings updates requested. Please wait before updating again."
                ),
            },
        )

    # Concurrency check
    stmt_raw = (
        select(StudentStudySettings)
        .where(StudentStudySettings.student_id == student_id)
        .with_for_update()
    )
    res_raw = await db.execute(stmt_raw)
    raw = res_raw.scalar_one_or_none()

    if raw and payload.expected_version is not None and raw.version != payload.expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CONCURRENT_MODIFICATION",
                "message": (
                    f"Study settings were modified by another transaction. Expected version "
                    f"{payload.expected_version}, but database version is {raw.version}."
                ),
            },
        )

    old_dict = (
        {
            "school_day_minutes": raw.school_day_minutes,
            "holiday_minutes": raw.holiday_minutes,
            "study_window_start": raw.study_window_start,
            "study_window_end": raw.study_window_end,
            "recurring_unavailable_blocks": raw.recurring_unavailable_blocks,
            "blocked_observance_keys": raw.blocked_observance_keys,
            "custom_blackout_dates": raw.custom_blackout_dates,
            "subject_priorities": raw.subject_priorities,
            "rest_weekday": raw.rest_weekday,
            "version": raw.version,
        }
        if raw
        else None
    )

    unavail_json = [b.model_dump() for b in payload.recurring_unavailable_blocks]
    blackouts_json = [
        {"start_date": str(b.start_date), "end_date": str(b.end_date), "reason": b.reason}
        for b in payload.custom_blackout_dates
    ]

    if not raw:
        raw = StudentStudySettings(
            student_id=student_id,
            school_day_minutes=payload.school_day_minutes,
            holiday_minutes=payload.holiday_minutes,
            study_window_start=payload.study_window_start,
            study_window_end=payload.study_window_end,
            recurring_unavailable_blocks=unavail_json,
            blocked_observance_keys=payload.blocked_observance_keys,
            custom_blackout_dates=blackouts_json,
            subject_priorities=payload.subject_priorities,
            rest_weekday=payload.rest_weekday,
            adaptive_mode=payload.adaptive_mode,
            ai_adjustments=payload.ai_adjustments,
            parent_locked_fields=payload.parent_locked_fields,
            version=1,
        )
        db.add(raw)
    else:
        raw.school_day_minutes = payload.school_day_minutes
        raw.holiday_minutes = payload.holiday_minutes
        raw.study_window_start = payload.study_window_start
        raw.study_window_end = payload.study_window_end
        raw.recurring_unavailable_blocks = unavail_json
        raw.blocked_observance_keys = payload.blocked_observance_keys
        raw.custom_blackout_dates = blackouts_json
        raw.subject_priorities = payload.subject_priorities
        raw.rest_weekday = payload.rest_weekday
        raw.adaptive_mode = payload.adaptive_mode
        raw.ai_adjustments = payload.ai_adjustments
        raw.parent_locked_fields = payload.parent_locked_fields
        raw.version += 1

    await db.flush()

    new_dict = {
        "school_day_minutes": raw.school_day_minutes,
        "holiday_minutes": raw.holiday_minutes,
        "study_window_start": raw.study_window_start,
        "study_window_end": raw.study_window_end,
        "recurring_unavailable_blocks": raw.recurring_unavailable_blocks,
        "blocked_observance_keys": raw.blocked_observance_keys,
        "custom_blackout_dates": raw.custom_blackout_dates,
        "subject_priorities": raw.subject_priorities,
        "rest_weekday": raw.rest_weekday,
        "adaptive_mode": raw.adaptive_mode,
        "ai_adjustments": raw.ai_adjustments,
        "parent_locked_fields": raw.parent_locked_fields,
        "version": raw.version,
    }

    # Record structured audit log
    audit_row = AuditLog(
        actor_id=current_user.id,
        action="student_study_settings.update",
        target_type="student_study_settings",
        target_id=str(raw.id),
        meta={"old_value": old_dict, "new_value": new_dict, "student_id": str(student_id)},
    )
    db.add(audit_row)

    # Sync student profile daily_minutes
    stmt_prof = select(StudentProfile).where(StudentProfile.user_id == student_id)
    res_prof = await db.execute(stmt_prof)
    profile = res_prof.scalar_one_or_none()
    if profile:
        profile.daily_minutes = raw.school_day_minutes

    await db.commit()

    # Trigger plan regeneration with new resolved settings
    await execute_student_plan_regeneration(
        db=db,
        student_id=student_id,
        reason="study_settings_update",
    )

    resolved = await resolve_student_settings(db, student_id)

    return StudentStudySettingsResponse(
        id=raw.id,
        student_id=student_id,
        school_day_minutes=resolved.school_day_minutes,
        holiday_minutes=resolved.holiday_minutes,
        study_window_start=resolved.study_window_start,
        study_window_end=resolved.study_window_end,
        recurring_unavailable_blocks=resolved.recurring_unavailable_blocks,
        blocked_observance_keys=resolved.blocked_observance_keys,
        custom_blackout_dates=resolved.custom_blackout_dates,
        subject_priorities=resolved.subject_priorities,
        rest_weekday=resolved.rest_weekday,
        adaptive_mode=resolved.adaptive_mode,
        ai_adjustments=resolved.ai_adjustments,
        parent_locked_fields=resolved.parent_locked_fields,
        version=raw.version,
        clamping_notices=resolved.clamping_notices,
        warnings=resolved.warnings,
        recommended_daily_minutes=resolved.recommended_daily_minutes,
        admin_hard_limits=resolved.admin_hard_limits,
    )


@router.post(
    "/students/{student_id}/study-settings/change-requests",
    response_model=StudentChangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_student_settings_change_request(
    student_id: uuid.UUID,
    payload: StudentChangeRequestInput,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> StudentChangeRequestResponse:
    """Student submits proposed adjustments to their general study settings (Req B.6)."""
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "STUDENT_ONLY",
                "message": "Only students may submit study settings change requests.",
            },
        )
    if current_user.id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN",
                "message": "Cannot submit change request for another student.",
            },
        )

    req = StudentChangeRequest(
        setup_id=None,
        student_id=student_id,
        requested_changes=payload.requested_changes,
        status="pending",
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)

    return StudentChangeRequestResponse(
        id=req.id,
        setup_id=req.setup_id,
        student_id=req.student_id,
        requested_changes=req.requested_changes,
        status=req.status,
        created_at=req.created_at,
    )


# ============================================================================
# AI Planner Suggestion & Parent Approval Flow (P06a)
# ============================================================================


@router.get(
    "/students/{student_id}/ai-suggestions",
    response_model=list[AiSuggestionResponse],
    status_code=status.HTTP_200_OK,
)
async def list_ai_suggestions(
    student_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AiSuggestionResponse]:
    """List pending AI planner priority suggestions for a student."""
    if current_user.role == "parent":
        await verify_parent_access_to_student(current_user, student_id, db)
    elif current_user.id != student_id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    stmt = (
        select(StudentChangeRequest)
        .where(
            StudentChangeRequest.student_id == student_id,
            StudentChangeRequest.status == "pending",
        )
        .order_by(StudentChangeRequest.created_at.desc())
    )
    res = await db.execute(stmt)
    records = res.scalars().all()

    output: list[AiSuggestionResponse] = []
    for r in records:
        ch = r.requested_changes or {}
        if ch.get("type") == "ai_priority_suggestion":
            output.append(
                AiSuggestionResponse(
                    id=r.id,
                    student_id=r.student_id,
                    subject=ch.get("subject", ""),
                    current_level=ch.get("current_level", "normal"),
                    suggested_level=ch.get("suggested_level", "main"),
                    evidence_codes=ch.get("evidence_codes", []),
                    rationale=ch.get("rationale", ""),
                    status=r.status,
                    created_at=r.created_at,
                )
            )
    return output


@router.post(
    "/students/{student_id}/ai-suggestions/{suggestion_id}/approve",
    status_code=status.HTTP_200_OK,
)
async def approve_ai_suggestion(
    student_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Parent approves an AI planner priority suggestion, updating settings and regenerating plan."""
    if current_user.role != "parent" and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Parent authorization required")
    if current_user.role == "parent":
        await verify_parent_access_to_student(current_user, student_id, db)

    stmt = select(StudentChangeRequest).where(
        StudentChangeRequest.id == suggestion_id,
        StudentChangeRequest.student_id == student_id,
    )
    res = await db.execute(stmt)
    req = res.scalars().first()
    if not req or req.status != "pending":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pending suggestion not found")

    ch = req.requested_changes or {}
    sub = ch.get("subject")
    sugg_level = ch.get("suggested_level")

    # Apply to student study settings
    stmt_settings = select(StudentStudySettings).where(StudentStudySettings.student_id == student_id).with_for_update()
    res_s = await db.execute(stmt_settings)
    settings_obj = res_s.scalars().first()

    old_prios = dict(settings_obj.subject_priorities) if settings_obj else {}
    if settings_obj and sub and sugg_level:
        settings_obj.subject_priorities[sub] = sugg_level
        settings_obj.version += 1
        settings_obj.updated_by_user_id = current_user.id

    req.status = "approved"
    req.reviewed_at = datetime.now(UTC)
    req.reviewed_by_id = current_user.id

    # Immutable Audit Log
    audit = AuditLog(
        actor_id=current_user.id,
        action="ai_planner.approve_suggestion",
        target_type="student_study_settings",
        target_id=student_id,
        meta={
            "suggestion_id": str(suggestion_id),
            "subject": sub,
            "old_priority": old_prios.get(sub),
            "new_priority": sugg_level,
            "at": datetime.now(UTC).isoformat(),
        },
    )
    db.add(audit)
    await db.commit()

    # Trigger plan regeneration
    plan_resp = await _sync_regenerate_plan_for_student(
        student_id=student_id,
        db=db,
        reason="adaptive",
    )

    return {
        "status": "approved",
        "suggestion_id": str(suggestion_id),
        "subject": sub,
        "new_priority": sugg_level,
        "new_plan_version": plan_resp.version,
    }


@router.post(
    "/students/{student_id}/ai-suggestions/{suggestion_id}/reject",
    status_code=status.HTTP_200_OK,
)
async def reject_ai_suggestion(
    student_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str]:
    """Parent rejects an AI planner suggestion."""
    if current_user.role != "parent" and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Parent authorization required")
    if current_user.role == "parent":
        await verify_parent_access_to_student(current_user, student_id, db)

    stmt = select(StudentChangeRequest).where(
        StudentChangeRequest.id == suggestion_id,
        StudentChangeRequest.student_id == student_id,
    )
    res = await db.execute(stmt)
    req = res.scalars().first()
    if not req or req.status != "pending":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pending suggestion not found")

    req.status = "rejected"
    req.reviewed_at = datetime.now(UTC)
    req.reviewed_by_id = current_user.id

    audit = AuditLog(
        actor_id=current_user.id,
        action="ai_planner.reject_suggestion",
        target_type="student_study_settings",
        target_id=student_id,
        meta={"suggestion_id": str(suggestion_id), "at": datetime.now(UTC).isoformat()},
    )
    db.add(audit)
    await db.commit()

    return {"status": "rejected", "suggestion_id": str(suggestion_id)}

