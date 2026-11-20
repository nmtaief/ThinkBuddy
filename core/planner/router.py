"""API routes for study setup, syllabus items, versioned planner, and daily tasks."""

from __future__ import annotations

import uuid
import zlib
from asyncio import Lock
from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
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
from core.progress.models import ProgressDaily, RevisionItem
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

        # Check if student account is pending deletion
        stmt_u = select(User).where(User.id == student_id)
        student_user = (await db.execute(stmt_u)).scalar_one_or_none()
        if student_user and student_user.status == "pending_deletion":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ACCOUNT_PENDING_DELETION", "message": "Account is pending deletion. Study plan updates are suspended."},
            )
        if student_user and not student_user.has_parental_consent:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "CONSENT_WITHDRAWN", "message": "Parental consent is required to generate or update study plans."},
            )

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

        stmt_m = select(Mastery).where(Mastery.student_id == student_id)
        res_m = await db.execute(stmt_m)
        all_mastery_rows = res_m.scalars().all()
        student_mastery_map = {m.chapter_id: m.score for m in all_mastery_rows}

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

        # Load real learning signals, mastery, and spaced revision (docs/07_AI_PLANNER_API.md §5)
        mastery_records = [
            {
                "chapter_id": str(m.chapter_id),
                "concept_id": str(m.concept_id) if m.concept_id else None,
                "score": m.score,
                "confidence": m.confidence,
                "last_seen": m.last_signal_at.isoformat() if m.last_signal_at else None,
            }
            for m in all_mastery_rows
        ]

        stmt_r = select(RevisionItem).where(RevisionItem.student_id == student_id)
        res_r = await db.execute(stmt_r)
        revision_records = [
            {
                "chapter_id": str(r.chapter_id),
                "concept_id": str(r.concept_id) if r.concept_id else None,
                "box": r.box,
                "due_at": r.due_at.isoformat() if r.due_at else None,
            }
            for r in res_r.scalars().all()
        ]

        stmt_p = (
            select(ProgressDaily)
            .where(ProgressDaily.student_id == student_id)
            .order_by(ProgressDaily.date.desc())
            .limit(14)
        )
        res_p = await db.execute(stmt_p)
        progress_days = res_p.scalars().all()
        quiz_accs = [p.quiz_avg for p in progress_days if p.quiz_avg is not None]
        avg_quiz_acc = (sum(quiz_accs) / len(quiz_accs)) if quiz_accs else 0.8
        skipped_count = sum(p.tasks_total - p.tasks_done for p in progress_days if p.tasks_total > p.tasks_done)

        learning_signals = {
            "quiz_accuracy": round(avg_quiz_acc, 2),
            "speed_vs_expected": 1.0,
            "repeated_chat_topics": [],
            "skipped_tasks_count": skipped_count,
            "self_rated_difficulty": None,
        }

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
            mastery_records=mastery_records,
            learning_signals=learning_signals,
            revision_items=revision_records,
        )

        # Check per-student override and dynamic rollout config (Item 3)
        from core.planner.rollout import get_ai_planner_rollout_config
        from core.planner.models import AiPlannerShadowRun

        stmt_sett = select(StudentStudySettings).where(StudentStudySettings.student_id == student_id)
        res_sett = await db.execute(stmt_sett)
        settings_record = res_sett.scalars().first()
        per_student_override = settings_record.ai_planner_override if settings_record else None

        rollout_cfg = await get_ai_planner_rollout_config()
        plan_provider = get_plan_provider(
            resolved_settings,
            per_student_override=per_student_override,
            rollout_config=rollout_cfg,
        )
        provider_result = await plan_provider.generate_plan(provider_ctx)
        plan_out = provider_result.plan_out

        # Shadow Mode: if enabled and primary is deterministic, evaluate AI planner in background (Item 5)
        shadow_enabled = rollout_cfg.get("shadow_mode", app_settings.AI_PLANNER_SHADOW_MODE)
        if shadow_enabled and provider_result.provider == "deterministic":
            try:
                ai_shadow_provider = AiPlannerProvider()
                ai_shadow_res = await ai_shadow_provider.generate_plan(provider_ctx)
                if ai_shadow_res.plan_out:
                    from core.planner.shadow_comparator import compare_plans
                    shadow_report = compare_plans(ai_shadow_res.plan_out, plan_out)
                    provider_result.shadow_comparison = shadow_report
                    # Persist shadow evaluation to dedicated table (no payload data, no prompt, no PII) (Item 5)
                    shadow_run = AiPlannerShadowRun(
                        student_id=student_id,
                        at=datetime.now(UTC),
                        recommendation=shadow_report.get("recommendation", "review_delta"),
                        coverage_parity_met=bool(shadow_report.get("coverage_parity_met", False)),
                        churn_rate_pct=float(shadow_report.get("churn_rate_pct", 0.0)),
                        minutes_delta=int(shadow_report.get("minutes_delta", 0)),
                        ai_warnings_count=int(shadow_report.get("ai_warnings_count", 0)),
                        metrics={
                            "total_ai_tasks": shadow_report.get("total_ai_tasks", 0),
                            "total_deterministic_tasks": shadow_report.get("total_deterministic_tasks", 0),
                            "ai_total_minutes": shadow_report.get("ai_total_minutes", 0),
                            "deterministic_total_minutes": shadow_report.get("deterministic_total_minutes", 0),
                            "subject_coverage_delta": shadow_report.get("subject_coverage_delta", {}),
                        },
                    )
                    db.add(shadow_run)
                    # Also persist to audit_log
                    audit_shadow = AuditLog(
                        actor_id=student_id,
                        action="ai_planner.shadow_comparison",
                        target_type="plan",
                        target_id=str(student_id),
                        meta={
                            **shadow_report,
                            "student_id": str(student_id),
                            "at": datetime.now(UTC).isoformat(),
                        },
                    )
                    db.add(audit_shadow)
            except Exception as shadow_exc:
                logger.warning("AI Planner Shadow Mode execution error: %s", shadow_exc)

        # Suggestions processing: de-duplication, daily cap (3/day), non-labeling rationales, and auto_within_limits (Items 2, 4, 7)
        from core.parent.service import sanitize_non_labeling_reason, localize_rationale_bn
        from core.notifications.service import NotificationService
        from core.families.models import ParentStudentLink

        stmt_plink = select(ParentStudentLink.parent_id).where(
            ParentStudentLink.student_id == student_id,
            ParentStudentLink.status == "active",
        )
        res_plink = await db.execute(stmt_plink)
        linked_parent_id = res_plink.scalars().first()

        suggestions_to_process = list(provider_result.priority_suggestions or [])
        # Minute-change suggestion if exam is within 14 days or skipped tasks
        if resolved_settings.adaptive_mode in ("suggest", "auto_within_limits"):
            exam_proximity = exam_dates and min((ed - today_dhaka).days for ed in exam_dates) < 14
            if (exam_proximity or learning_signals.get("skipped_tasks_count", 0) > 3) and resolved_settings.school_day_minutes < 240:
                suggestions_to_process.append({
                    "type": "ai_minute_suggestion",
                    "field": "school_day_minutes",
                    "current_minutes": resolved_settings.school_day_minutes,
                    "suggested_minutes": min(resolved_settings.school_day_minutes + 15, 240),
                    "minutes_delta": 15,
                    "evidence_codes": ["PACING_ALIGNMENT"],
                    "rationale": "Recommended pacing adjustment of +15 daily study minutes to reinforce exam preparation.",
                })

        if suggestions_to_process and settings_record:
            today_start = datetime.combine(today_dhaka, datetime.min.time(), tzinfo=UTC)
            stmt_cap = select(func.count(StudentChangeRequest.id)).where(
                StudentChangeRequest.student_id == student_id,
                StudentChangeRequest.created_at >= today_start,
            )
            daily_count = (await db.execute(stmt_cap)).scalar() or 0

            stmt_pending = select(StudentChangeRequest).where(
                StudentChangeRequest.student_id == student_id,
                StudentChangeRequest.status == "pending",
            )
            res_pending = await db.execute(stmt_pending)
            pending_reqs = res_pending.scalars().all()
            pending_keys = {
                (
                    (r.requested_changes or {}).get("type"),
                    (r.requested_changes or {}).get("subject") or (r.requested_changes or {}).get("field"),
                )
                for r in pending_reqs
            }

            locked_fields = set(settings_record.parent_locked_fields or [])

            for ps in suggestions_to_process:
                sugg_type = ps.get("type", "ai_priority_suggestion")
                target_key = ps.get("subject") if sugg_type == "ai_priority_suggestion" else ps.get("field")
                if (sugg_type, target_key) in pending_keys:
                    continue

                raw_rationale = ps.get("rationale") or "Balanced pacing recommendation."
                clean_rationale = sanitize_non_labeling_reason(raw_rationale)
                clean_rationale_bn = localize_rationale_bn(clean_rationale, ps.get("subject"))

                # Check if target is locked by parent
                is_locked = False
                if sugg_type == "ai_priority_suggestion":
                    sub = ps.get("subject")
                    if sub in locked_fields or f"priority_{sub}" in locked_fields or "subject_priorities" in locked_fields:
                        is_locked = True
                elif sugg_type == "ai_minute_suggestion":
                    fld = ps.get("field")
                    if fld in locked_fields:
                        is_locked = True

                if settings_record.adaptive_mode == "auto_within_limits" and not is_locked:
                    # Item 2 & 5: Auto-apply strictly within caps
                    adj_id = str(uuid.uuid4())
                    prev_state: dict[str, Any] = {}
                    summary_en = ""
                    summary_bn = ""

                    if sugg_type == "ai_priority_suggestion":
                        sub = ps.get("subject")
                        raw_lvl = ps.get("suggested_level", "main")
                        # Rule: At most one priority level step per cycle (Item 5)
                        prio_map = {"normal": 0, "main": 1, "difficult": 2}
                        rev_prio = {0: "normal", 1: "main", 2: "difficult"}
                        curr_prios = dict(settings_record.subject_priorities or {})
                        curr_lvl = curr_prios.get(sub, "normal")
                        curr_idx = prio_map.get(curr_lvl, 0)
                        req_idx = prio_map.get(raw_lvl, 1)
                        if abs(req_idx - curr_idx) > 1:
                            step = 1 if req_idx > curr_idx else -1
                            new_lvl = rev_prio.get(curr_idx + step, curr_lvl)
                        else:
                            new_lvl = raw_lvl

                        prev_state["subject_priorities"] = dict(settings_record.subject_priorities or {})
                        new_prios = dict(settings_record.subject_priorities or {})
                        new_prios[sub] = new_lvl
                        settings_record.subject_priorities = new_prios
                        summary_en = f"Adjusted study priority for {sub} to {new_lvl} to build foundational mastery."
                        summary_bn = f"{sub}-এর পড়ার গুরুত্ব সমন্বয় করা হয়েছে।"
                    elif sugg_type == "ai_minute_suggestion":
                        fld = ps.get("field", "school_day_minutes")
                        raw_mins = ps.get("suggested_minutes", settings_record.school_day_minutes)
                        cur_mins = getattr(settings_record, fld, 60)

                        # Rule: At most a set percentage (<= 20%) of minutes per cycle (Item 5)
                        max_delta = max(5, int(cur_mins * 0.20))
                        if raw_mins > cur_mins:
                            clamped_mins = min(raw_mins, cur_mins + max_delta)
                        elif raw_mins < cur_mins:
                            clamped_mins = max(raw_mins, cur_mins - max_delta)
                        else:
                            clamped_mins = raw_mins

                        # Rule: Ceilings per class band and day type from admin_policies table
                        # Auto mode never lowers a parent setting, never raises above the ceiling,
                        # and leaves a parent value that is already above the ceiling unchanged.
                        stmt_prof = select(StudentProfile.class_level).where(StudentProfile.user_id == student_id)
                        res_prof = await db.execute(stmt_prof)
                        cls_lvl = res_prof.scalar_one_or_none() or 10
                        band = "6-8" if cls_lvl <= 8 else ("9-10" if cls_lvl <= 10 else "11-12")

                        stmt_pol = (
                            select(AdminPolicy)
                            .where(AdminPolicy.class_band == band, AdminPolicy.status == "published")
                            .order_by(AdminPolicy.version.desc())
                        )
                        res_pol = await db.execute(stmt_pol)
                        pol_rec = res_pol.scalars().first()

                        if fld == "holiday_minutes":
                            ceiling = pol_rec.holiday_ceiling_minutes if pol_rec else (360 if band == "6-8" else (480 if band == "9-10" else 600))
                        else:
                            ceiling = pol_rec.school_day_ceiling_minutes if pol_rec else (240 if band == "6-8" else (360 if band == "9-10" else 360))

                        # Invariant 1: Leaves a parent value that is already above the ceiling unchanged
                        if cur_mins >= ceiling:
                            final_mins = cur_mins
                        else:
                            # Invariant 2: Auto mode never lowers a parent setting
                            # Invariant 3: Never raises above the ceiling
                            final_mins = max(cur_mins, min(clamped_mins, ceiling))

                        prev_state[fld] = cur_mins
                        setattr(settings_record, fld, final_mins)
                        summary_en = f"Adjusted daily study time to {final_mins} minutes for exam pacing."
                        summary_bn = f"দৈনিক পড়ার সময় {final_mins} মিনিটে সমন্বয় করা হয়েছে।"

                    settings_record.version += 1
                    cur_adj = dict(settings_record.ai_adjustments or {})
                    recent_adj = list(cur_adj.get("recent_adjustments", []))
                    recent_adj.append({
                        "adjustment_id": adj_id,
                        "type": sugg_type,
                        "previous_state": prev_state,
                        "summary": summary_en,
                        "summary_bn": summary_bn,
                        "applied_at": datetime.now(UTC).isoformat(),
                        "undone": False,
                    })
                    cur_adj["recent_adjustments"] = recent_adj
                    settings_record.ai_adjustments = cur_adj

                    # Notify parent with one-tap undo option (Item 2)
                    if linked_parent_id:
                        await NotificationService.create_notification(
                            db=db,
                            user_id=linked_parent_id,
                            type="ai_adjustment_auto_applied",
                            title="Study plan automatically adjusted",
                            body=f"{summary_en} You can undo this anytime from your dashboard.",
                            title_bn="পড়ার রুটিন স্বয়ংক্রিয়ভাবে সমন্বয় করা হয়েছে",
                            body_bn=f"{summary_bn} আপনি যেকোনো সময় পূর্বাবস্থায় ফিরিয়ে নিতে পারেন।",
                            data={
                                "student_id": str(student_id),
                                "adjustment_id": adj_id,
                                "can_undo": True,
                            },
                        )
                    continue

                # In 'suggest' mode (or if locked), enqueue pending suggestion if under daily cap (Item 4)
                if daily_count < 3:
                    scr = StudentChangeRequest(
                        setup_id=None,
                        student_id=student_id,
                        requested_changes={
                            "type": sugg_type,
                            "subject": ps.get("subject"),
                            "field": ps.get("field"),
                            "current_level": ps.get("current_level"),
                            "suggested_level": ps.get("suggested_level"),
                            "current_minutes": ps.get("current_minutes"),
                            "suggested_minutes": ps.get("suggested_minutes"),
                            "evidence_codes": ps.get("evidence_codes", []),
                            "rationale": clean_rationale,
                            "rationale_bn": clean_rationale_bn,
                            "expires_at": (datetime.now(UTC) + timedelta(days=14)).isoformat(),
                        },
                        status="pending",
                    )
                    db.add(scr)
                    daily_count += 1
                    pending_keys.add((sugg_type, target_key))

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

            plan_id = uuid.uuid4()
            new_plan = Plan(
                id=plan_id,
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

            for g_day in plan_out.days:
                sub_tasks = [t for t in g_day.tasks if t.subject == s.subject]
                if not sub_tasks:
                    continue

                day_id = uuid.uuid4()
                p_day = PlanDay(
                    id=day_id,
                    plan_id=plan_id,
                    date=g_day.date,
                    planned_minutes=sum(t.est_minutes for t in sub_tasks),
                    day_type=g_day.day_type,
                )
                db.add(p_day)

                for g_task in sub_tasks:
                    t_row = Task(
                        id=uuid.uuid4(),
                        plan_day_id=day_id,
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
        setup_version=setup.version,
        expires_at=utcnow() + timedelta(days=7),
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
        setup_version=req.setup_version,
        expires_at=req.expires_at,
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
                "message": "You do not view this student's tasks.",
            },
        )

    if current_user.role == "student" and current_user.has_parental_consent is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CONSENT_WITHDRAWN",
                "message": "Parental consent is required to process minor student data. Processing is suspended.",
            },
        )

    # 1. Resolve student timezone
    stmt_tz = select(StudentProfile.time_zone).where(StudentProfile.user_id == student_id)
    tz_res = await db.execute(stmt_tz)
    tz_name = tz_res.scalar_one_or_none() or "Asia/Dhaka"
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

    # 3. Calculate exam countdowns and resolve active plan provenance in a single query
    stmt_setups_plan = (
        select(
            StudySetup.subject,
            StudySetup.exam_date,
            Plan.provider,
            Plan.generation_reason,
            Plan.params,
        )
        .outerjoin(
            Plan,
            (Plan.setup_id == StudySetup.id) & (Plan.status == "active"),
        )
        .where(StudySetup.student_id == student_id)
        .order_by(Plan.version.desc().nullslast())
    )
    res_sp = await db.execute(stmt_setups_plan)
    sp_rows = res_sp.fetchall()

    countdowns: dict[str, int] = {}
    prov = "deterministic"
    gen_reason = "deterministic_baseline"
    reason_for_parents = "Study plan optimized for syllabus coverage, priority appearance, and spaced retention."
    first_plan_found = False

    for s_subject, s_exam_date, p_prov, p_gen_reason, p_params in sp_rows:
        diff = (s_exam_date - today_date).days
        countdowns[s_subject] = max(0, diff)

        if not first_plan_found and p_prov is not None:
            first_plan_found = True
            prov = p_prov or "deterministic"
            gen_reason = p_gen_reason or "deterministic_baseline"
            rationale_map = (p_params or {}).get("rationale", {})
            if rationale_map:
                reason_for_parents = next(
                    iter(rationale_map.values()),
                    reason_for_parents,
                )

    completion_pct = (completed_mins / total_planned * 100.0) if total_planned > 0 else 0.0

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

    stmt_sett = select(StudentStudySettings.version).where(StudentStudySettings.student_id == student_id)
    res_sett = await db.execute(stmt_sett)
    sett_ver = res_sett.scalar_one_or_none()

    req = StudentChangeRequest(
        setup_id=None,
        student_id=student_id,
        requested_changes=payload.requested_changes,
        status="pending",
        setup_version=sett_ver,
        expires_at=utcnow() + timedelta(days=7),
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
        setup_version=req.setup_version,
        expires_at=req.expires_at,
        created_at=req.created_at,
    )


# ============================================================================
# AI Planner Suggestion & Parent Approval Flow (P06a)
# ============================================================================


async def verify_parent_access_to_student(user: User, student_id: uuid.UUID, session: AsyncSession) -> None:
    """Verify that a parent user has an active linked relationship to the student."""
    has_access = await can_access_student(user, student_id, session)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Parent not authorized for this student",
        )


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
        ch_type = ch.get("type", "ai_priority_suggestion")
        if ch_type in ("ai_priority_suggestion", "ai_minute_suggestion"):
            exp_raw = ch.get("expires_at")
            exp_dt = datetime.fromisoformat(exp_raw) if exp_raw else None
            output.append(
                AiSuggestionResponse(
                    id=r.id,
                    student_id=r.student_id,
                    type=ch_type,
                    subject=ch.get("subject"),
                    field=ch.get("field"),
                    current_level=ch.get("current_level"),
                    suggested_level=ch.get("suggested_level"),
                    current_minutes=ch.get("current_minutes"),
                    suggested_minutes=ch.get("suggested_minutes"),
                    evidence_codes=ch.get("evidence_codes", []),
                    rationale=ch.get("rationale", ""),
                    rationale_bn=ch.get("rationale_bn"),
                    status=r.status,
                    created_at=r.created_at,
                    expires_at=exp_dt,
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
    """Parent approves an AI planner suggestion (priority or minute-change), updating settings and regenerating plan."""
    if current_user.role != "parent" and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Parent authorization required")
    if current_user.role == "parent":
        await verify_parent_access_to_student(current_user, student_id, db)

    # 1. Row-level lock to prevent race conditions (Item 4)
    stmt = (
        select(StudentChangeRequest)
        .where(
            StudentChangeRequest.id == suggestion_id,
            StudentChangeRequest.student_id == student_id,
        )
        .with_for_update()
    )
    res = await db.execute(stmt)
    req = res.scalars().first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pending suggestion not found")

    # Item (4): Concurrent approvals return 409 Conflict
    if req.status in ("approved", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Suggestion has already been processed",
        )

    if req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve suggestion in status '{req.status}'",
        )

    ch = req.requested_changes or {}
    sugg_type = ch.get("type", "ai_priority_suggestion")

    # Item (4): Expire after set time
    expires_at_raw = ch.get("expires_at")
    if expires_at_raw:
        try:
            exp_dt = datetime.fromisoformat(expires_at_raw)
            if datetime.now(UTC) > exp_dt:
                req.status = "expired"
                await db.commit()
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="Suggestion has expired",
                )
        except (ValueError, TypeError):
            pass

    # 2. Re-validate at approval against active student study settings (Item 4)
    stmt_settings = select(StudentStudySettings).where(StudentStudySettings.student_id == student_id).with_for_update()
    res_s = await db.execute(stmt_settings)
    settings_obj = res_s.scalars().first()

    locked_fields = set(settings_obj.parent_locked_fields or []) if settings_obj else set()
    old_val: Any = None
    new_val: Any = None
    sub: str | None = None
    sugg_level: str | None = None

    if sugg_type == "ai_priority_suggestion":
        sub = ch.get("subject")
        sugg_level = ch.get("suggested_level")
        if settings_obj and sub:
            if sub in locked_fields or f"priority_{sub}" in locked_fields or "subject_priorities" in locked_fields:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Subject priority for '{sub}' is locked by parent against AI suggestions (Rule V09)",
                )
        old_prios = dict(settings_obj.subject_priorities) if settings_obj else {}
        old_val = old_prios.get(sub, "normal")
        new_val = sugg_level
        if settings_obj and sub and sugg_level:
            new_prios = dict(settings_obj.subject_priorities or {})
            new_prios[sub] = sugg_level
            settings_obj.subject_priorities = new_prios
            settings_obj.version += 1
            settings_obj.updated_at = datetime.now(UTC)
    elif sugg_type == "ai_minute_suggestion":
        fld = ch.get("field", "school_day_minutes")
        sugg_mins = ch.get("suggested_minutes")
        if fld in locked_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Daily minute field '{fld}' is locked by parent against AI suggestions",
            )
        old_val = getattr(settings_obj, fld, 60) if settings_obj else 60
        new_val = sugg_mins
        if settings_obj and sugg_mins:
            setattr(settings_obj, fld, sugg_mins)
            settings_obj.version += 1
            settings_obj.updated_at = datetime.now(UTC)

    req.status = "approved"
    req.reviewed_at = datetime.now(UTC)
    req.reviewed_by_id = current_user.id

    # Immutable Audit Log
    audit = AuditLog(
        actor_id=current_user.id,
        action="ai_planner.approve_suggestion",
        target_type="student_study_settings",
        target_id=str(student_id),
        meta={
            "suggestion_id": str(suggestion_id),
            "type": sugg_type,
            "old_value": old_val,
            "new_value": new_val,
            "at": datetime.now(UTC).isoformat(),
        },
    )
    db.add(audit)
    await db.commit()

    # Trigger plan regeneration
    _, new_plan_version = await execute_student_plan_regeneration(
        db=db,
        student_id=student_id,
        reason="adaptive",
    )

    return {
        "status": "approved",
        "suggestion_id": str(suggestion_id),
        "subject": sub,
        "new_priority": sugg_level,
        "new_plan_version": new_plan_version,
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
        target_id=str(student_id),
        meta={"suggestion_id": str(suggestion_id), "at": datetime.now(UTC).isoformat()},
    )
    db.add(audit)
    await db.commit()

    return {"status": "rejected", "suggestion_id": str(suggestion_id)}


# ==============================================================================
# ONBOARDING & INTERACTIVE TIME ALLOCATION ENGINE
# ==============================================================================

class CalculateAllocationPayload(BaseModel):
    class_level: int = Field(default=8, ge=6, le=10)
    group: str = Field(default="general")
    selected_subject_slugs: list[str] | None = None
    weak_subject_slugs: list[str] | None = None
    focus_subject_slugs: list[str] | None = None
    subject_priorities: dict[str, str] | None = None
    chapter_statuses: dict[str, dict[str, str]] | None = None
    daily_study_hours: float = Field(default=2.5, ge=0.5, le=10.0)
    exam_name: str = Field(default="অর্ধবার্ষিক পরীক্ষা (Half-Yearly Exam)")
    exam_date: str | None = None


class StudentOnboardingPayload(BaseModel):
    class_level: int = Field(default=8, ge=6, le=10)
    medium: str = Field(default="bn")
    group: str = Field(default="general")
    selected_subject_slugs: list[str] = Field(default_factory=list)
    weak_subject_slugs: list[str] = Field(default_factory=list)
    focus_subject_slugs: list[str] = Field(default_factory=list)
    subject_priorities: dict[str, str] = Field(default_factory=dict)
    daily_study_hours: float = Field(default=2.5, ge=0.5, le=10.0)
    exam_name: str = Field(default="অর্ধবার্ষিক পরীক্ষা (Half-Yearly Exam)")
    exam_date: str | None = None
    study_window_start: str = Field(default="18:00")
    study_window_end: str = Field(default="22:00")
    weekly_off_days: list[str] = Field(default_factory=lambda: ["fri", "sat"])


@router.post("/planner/calculate-allocation")
async def calculate_allocation_preview(
    payload: CalculateAllocationPayload,
) -> dict[str, Any]:
    """Calculate mathematically grounded daily time and spaced revision allocation for any subject combination."""
    from dataclasses import asdict
    from core.planner.dataset import calculate_study_and_revision_dataset

    summary = calculate_study_and_revision_dataset(
        class_level=payload.class_level,
        group=payload.group,
        selected_subject_slugs=payload.selected_subject_slugs,
        weak_subject_slugs=payload.weak_subject_slugs,
        focus_subject_slugs=payload.focus_subject_slugs,
        subject_priorities=payload.subject_priorities,
        chapter_statuses=payload.chapter_statuses,
        daily_study_hours=payload.daily_study_hours,
        exam_date_val=payload.exam_date,
        exam_name=payload.exam_name,
    )
    return asdict(summary)


@router.post("/planner/ai-review-and-plan")
async def ai_review_and_plan_endpoint(
    payload: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Review student study setup with LLM, parse natural text, and generate balanced plan."""
    from pydantic import TypeAdapter
    from core.planner.ai_planner import AIPlanReviewRequest, review_and_generate_ai_plan

    req_obj = TypeAdapter(AIPlanReviewRequest).validate_python(payload)
    res = await review_and_generate_ai_plan(req_obj, db)
    return res.model_dump()


@router.post("/students/onboarding")
async def submit_student_onboarding(
    payload: StudentOnboardingPayload,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Submit student self-onboarding: configure syllabus, exams, study budget, weak/focus subjects."""
    from dataclasses import asdict
    from core.planner.dataset import calculate_study_and_revision_dataset

    student_id = current_user.id
    if current_user.role == "parent":
        # If parent is onboarding, find or create student under parent
        stmt_link = select(ParentStudentLink).where(
            ParentStudentLink.parent_id == current_user.id,
            ParentStudentLink.status == "active",
        )
        res_link = await db.execute(stmt_link)
        link = res_link.scalars().first()
        if link and link.student_id:
            student_id = link.student_id

    # 1. Update or create StudentProfile
    stmt_prof = select(StudentProfile).where(StudentProfile.user_id == student_id)
    profile = (await db.execute(stmt_prof)).scalar_one_or_none()
    daily_mins = int(round(payload.daily_study_hours * 60))

    if not profile:
        profile = StudentProfile(
            user_id=student_id,
            class_level=payload.class_level,
            group=payload.group,
            medium=payload.medium,
            school=None,
            optional_subject_ids=[],
            daily_minutes=daily_mins,
            available_days=payload.weekly_off_days,
            time_zone="Asia/Dhaka",
        )
        db.add(profile)
    else:
        profile.class_level = payload.class_level
        profile.group = payload.group
        profile.medium = payload.medium
        profile.daily_minutes = daily_mins
        profile.available_days = payload.weekly_off_days

    # 2. Update or create StudentStudySettings
    stmt_settings = select(StudentStudySettings).where(StudentStudySettings.student_id == student_id)
    settings_obj = (await db.execute(stmt_settings)).scalar_one_or_none()

    if not settings_obj:
        settings_obj = StudentStudySettings(
            id=uuid.uuid4(),
            student_id=student_id,
            school_day_minutes=daily_mins,
            holiday_minutes=int(round(daily_mins * 1.2)),
            study_window_start=payload.study_window_start,
            study_window_end=payload.study_window_end,
            recurring_unavailable_blocks=[],
            blocked_observance_keys=[],
            custom_blackout_dates=[],
            subject_priorities=payload.subject_priorities,
            version=1,
            updated_by_user_id=current_user.id,
        )
        db.add(settings_obj)
    else:
        settings_obj.school_day_minutes = daily_mins
        settings_obj.holiday_minutes = int(round(daily_mins * 1.2))
        settings_obj.study_window_start = payload.study_window_start
        settings_obj.study_window_end = payload.study_window_end
        settings_obj.subject_priorities = payload.subject_priorities
        settings_obj.version = (settings_obj.version or 1) + 1
        settings_obj.updated_by_user_id = current_user.id

    # 3. Create or update StudySetup for primary exam
    exam_target_date = None
    if payload.exam_date:
        try:
            exam_target_date = datetime.strptime(payload.exam_date[:10], "%Y-%m-%d").date()
        except ValueError:
            pass

    for slug in payload.selected_subject_slugs:
        stmt_setup = select(StudySetup).where(
            StudySetup.student_id == student_id,
            StudySetup.subject == slug,
        )
        setup = (await db.execute(stmt_setup)).scalar_one_or_none()
        if not setup:
            setup = StudySetup(
                id=uuid.uuid4(),
                student_id=student_id,
                subject=slug,
                exam_name=payload.exam_name,
                exam_date=exam_target_date,
                set_by_user_id=current_user.id,
                active_plan_version=1,
                version=1,
            )
            db.add(setup)
        else:
            setup.exam_name = payload.exam_name
            setup.exam_date = exam_target_date
            setup.version = (setup.version or 1) + 1

    await db.flush()

    # 4. Generate balanced time and revision allocation dataset
    summary = calculate_study_and_revision_dataset(
        class_level=payload.class_level,
        group=payload.group,
        selected_subject_slugs=payload.selected_subject_slugs,
        weak_subject_slugs=payload.weak_subject_slugs,
        focus_subject_slugs=payload.focus_subject_slugs,
        subject_priorities=payload.subject_priorities,
        daily_study_hours=payload.daily_study_hours,
        exam_date_val=payload.exam_date,
        exam_name=payload.exam_name,
    )

    return {
        "status": "success",
        "message": "Student study onboarding completed successfully.",
        "summary": asdict(summary),
    }


@router.get("/planner/combinations")
async def get_planner_combinations(
    class_level: int | None = Query(default=None, ge=6, le=10),
    group: str | None = Query(default=None),
    strategy: str | None = Query(default=None),
    daily_hours: float | None = Query(default=None),
) -> dict[str, Any]:
    """Retrieve pre-generated combination datasets for classes, groups, and routine strategies."""
    import json
    from pathlib import Path

    data_path = Path(__file__).resolve().parent / "datasets" / "all_combinations_dataset.json"
    if not data_path.exists():
        raise HTTPException(status_code=404, detail="Combinations dataset not yet generated")

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    combs = data.get("combinations", [])
    if class_level is not None:
        combs = [c for c in combs if c.get("class_level") == class_level]
    if group is not None:
        combs = [c for c in combs if c.get("group") == group]
    if strategy is not None:
        combs = [c for c in combs if c.get("routine_strategy") == strategy]
    if daily_hours is not None:
        combs = [c for c in combs if c.get("daily_study_hours") == daily_hours]

    return {
        "status": "success",
        "total_matches": len(combs),
        "rules": data.get("rules", {}),
        "combinations": combs,
    }


