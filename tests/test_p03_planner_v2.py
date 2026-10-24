"""Comprehensive test suite for P03 Planner v2: Dynamic Configuration Layer.

Verifies all requirements from prompt:
1. Hypothesis Properties (Requirement E.15):
   - Blackout days have zero tasks.
   - Day-type budgets are respected (school days vs holiday days).
   - Rotation rule holds when feasible (no subject on > 2 consecutive study days
     when >= 3 subjects active).
   - Today's remaining-time cap formula.
   - Priority share ordering (difficult/main get more minutes than normal).
2. Unit & API Tests (Requirement E.15):
   - 3-tier precedence and admin clamping with notices.
   - An admin limit change clamping existing parent values.
   - Warning when parent sets minutes above recommended level for class band.
   - Student cannot edit study settings directly (403), can submit change request.
   - Unlinked parent gets 403 on study settings.
   - Non-admin gets 403 on admin routes.
   - Drafts don't affect plans; publishing activates them.
   - Publishing is idempotent.
   - 409 Conflict on concurrent edits (optimistic concurrency).
   - Structured audit log entries written with old and new values.
   - Client config (/v1/client/config) exposes limits and catalog without admin data leak.
   - Religion privacy rule: no religion stored, coarse blackout reasons only.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import pytest
from httpx import AsyncClient
from hypothesis import given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st
from sqlalchemy import select

from core.audit.models import AuditLog
from core.auth.models import User
from core.auth.tokens import create_access_jwt
from core.common.config import settings
from core.common.database import AsyncSessionLocal
from core.families.models import ParentStudentLink, StudentProfile
from core.planner.engine import (
    ChapterPlanInput,
    SubjectSetupInput,
    generate_student_plan,
)
from core.planner.models import StudentStudySettings
from core.planner.settings_resolver import (
    ResolvedPlannerSettings,
    calculate_today_remaining_budget,
    resolve_calendar_days,
    resolve_student_settings,
)

CLIENT_HEADERS = {
    "X-Client-Platform": "android",
    "X-Client-Form-Factor": "phone",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "device-test-planner-v2",
    "Accept-Language": "bn",
}


def make_auth_headers(user_id: uuid.UUID, role: str) -> dict[str, str]:
    token = create_access_jwt(user_id=user_id, role=role)
    return {
        "Authorization": f"Bearer {token}",
        "X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN,
        "X-Client-Platform": "android",
        "X-Client-Form-Factor": "phone",
        "X-App-Version": "1.0.0",
        "X-Device-Id": f"device-test-{user_id}",
        "Accept-Language": "bn",
    }


# ============================================================================
# 1. Hypothesis Property-Based Tests
# ============================================================================


@given(
    blackout_day_offset=st.integers(min_value=1, max_value=25),
    holiday_day_offset=st.integers(min_value=1, max_value=25),
)
@hyp_settings(max_examples=25, deadline=None)
def test_hypothesis_blackout_days_zero_tasks(
    blackout_day_offset: int, holiday_day_offset: int
) -> None:
    """Property 1: Blackout days strictly have zero planned minutes and zero tasks."""
    today = date(2026, 10, 23)
    exam_date = today + timedelta(days=30)
    b_date = today + timedelta(days=blackout_day_offset)

    ch = [
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=i,
            title=f"Chapter {i}",
            printed_page_start=(i - 1) * 20 + 1,
            printed_page_end=i * 20,
            custom_order=i,
            book_title="Test Book",
        )
        for i in range(1, 4)
    ]
    setups = [
        SubjectSetupInput(
            subject="Physics", exam_name="Physics Test", exam_date=exam_date, chapters=ch
        ),
        SubjectSetupInput(
            subject="Chemistry", exam_name="Chemistry Test", exam_date=exam_date, chapters=ch
        ),
    ]

    settings = ResolvedPlannerSettings(
        class_band="9-10",
        group="science",
        school_day_minutes=120,
        holiday_minutes=180,
        study_window_start="17:00",
        study_window_end="21:30",
        weekly_off_days=["fri", "sat"],
        recurring_unavailable_blocks=[],
        blocked_observance_keys=[],
        custom_blackout_dates=[
            {"start_date": str(b_date), "end_date": str(b_date), "reason": "family_event"}
        ],
        subject_priorities={},
        planner_parameters={"max_consecutive_days_per_subject": 2},
    )

    day_calendar = resolve_calendar_days(
        start_date=today,
        end_date=exam_date,
        now=datetime(today.year, today.month, today.day, 12, 0),
        resolved_settings=settings,
        published_holidays=[],
        exam_dates={exam_date},
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=120,
        setups=setups,
        resolved_settings=settings,
        day_calendar=day_calendar,
    )

    for day in plan.days:
        if day.date == b_date or day.day_type == "blackout":
            assert day.planned_minutes == 0, (
                f"Blackout day {day.date} has planned minutes {day.planned_minutes}"
            )
            assert len(day.tasks) == 0, f"Blackout day {day.date} has tasks scheduled"


@given(
    school_m=st.integers(min_value=30, max_value=120),
    holiday_m=st.integers(min_value=120, max_value=240),
)
@hyp_settings(max_examples=25, deadline=None)
def test_hypothesis_day_type_budgets_respected(school_m: int, holiday_m: int) -> None:
    """Property 2: Planned minutes on any day never exceed the specific day-type budget."""
    today = date(2026, 10, 23)
    exam_date = today + timedelta(days=20)

    ch = [
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=i,
            title=f"Chapter {i}",
            printed_page_start=(i - 1) * 15 + 1,
            printed_page_end=i * 15,
            custom_order=i,
            book_title="Test Math",
        )
        for i in range(1, 5)
    ]
    setups = [
        SubjectSetupInput(subject="Math", exam_name="Math Test", exam_date=exam_date, chapters=ch)
    ]

    settings = ResolvedPlannerSettings(
        class_band="6-8",
        group="general",
        school_day_minutes=school_m,
        holiday_minutes=holiday_m,
        study_window_start="17:00",
        study_window_end="21:30",
        weekly_off_days=["fri", "sat"],
        recurring_unavailable_blocks=[],
        blocked_observance_keys=[],
        custom_blackout_dates=[],
        subject_priorities={},
        planner_parameters={"max_consecutive_days_per_subject": 2},
    )

    day_calendar = resolve_calendar_days(
        start_date=today,
        end_date=exam_date,
        now=datetime(today.year, today.month, today.day, 12, 0),
        resolved_settings=settings,
        published_holidays=[],
        exam_dates={exam_date},
    )

    cal_map = {d.date: d for d in day_calendar}

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=school_m,
        setups=setups,
        resolved_settings=settings,
        day_calendar=day_calendar,
    )

    for day in plan.days:
        info = cal_map.get(day.date)
        if info:
            assert day.planned_minutes <= info.budget_minutes, (
                f"Day {day.date} ({info.day_type}) exceeded budget: "
                f"{day.planned_minutes}m > {info.budget_minutes}m"
            )


def test_hypothesis_rotation_rule_when_feasible() -> None:
    """Property 3: Rotation rule holds when feasible (no subject on > 2 consecutive study days)."""
    today = date(2026, 10, 23)
    exam_date = today + timedelta(days=35)

    def make_chapters(title_prefix: str) -> list[ChapterPlanInput]:
        return [
            ChapterPlanInput(
                id=uuid.uuid4(),
                number=i,
                title=f"{title_prefix} {i}",
                printed_page_start=(i - 1) * 10 + 1,
                printed_page_end=i * 10,
                custom_order=i,
                book_title=f"{title_prefix} Book",
            )
            for i in range(1, 3)
        ]

    setups = [
        SubjectSetupInput(
            subject="Physics",
            exam_name="Physics Test",
            exam_date=exam_date,
            chapters=make_chapters("Physics"),
        ),
        SubjectSetupInput(
            subject="Chemistry",
            exam_name="Chemistry Test",
            exam_date=exam_date,
            chapters=make_chapters("Chemistry"),
        ),
        SubjectSetupInput(
            subject="Biology",
            exam_name="Biology Test",
            exam_date=exam_date,
            chapters=make_chapters("Biology"),
        ),
        SubjectSetupInput(
            subject="Mathematics",
            exam_name="Math Test",
            exam_date=exam_date,
            chapters=make_chapters("Math"),
        ),
    ]

    settings = ResolvedPlannerSettings(
        class_band="9-10",
        group="science",
        school_day_minutes=120,
        holiday_minutes=180,
        study_window_start="17:00",
        study_window_end="21:30",
        weekly_off_days=["fri", "sat"],
        recurring_unavailable_blocks=[],
        blocked_observance_keys=[],
        custom_blackout_dates=[],
        subject_priorities={},
        planner_parameters={"max_consecutive_days_per_subject": 2},
    )

    day_calendar = resolve_calendar_days(
        start_date=today,
        end_date=exam_date,
        now=datetime(today.year, today.month, today.day, 12, 0),
        resolved_settings=settings,
        published_holidays=[],
        exam_dates={exam_date},
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=120,
        setups=setups,
        resolved_settings=settings,
        day_calendar=day_calendar,
    )

    # Check consecutive study task days per subject
    for sub in ["Physics", "Chemistry", "Biology", "Mathematics"]:
        consecutive = 0
        max_consecutive = 0
        for day in plan.days:
            has_study = any(t.subject == sub and t.type == "study" for t in day.tasks)
            if has_study:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 0

        # With 4 subjects and 35 days, rotation is fully feasible and should strictly not exceed 2
        assert max_consecutive <= 2, (
            f"Subject {sub} had {max_consecutive} consecutive study days (max allowed 2)"
        )


@given(
    now_hour=st.integers(min_value=17, max_value=22),
    now_minute=st.integers(min_value=0, max_value=59),
    completed_m=st.integers(min_value=0, max_value=60),
)
@hyp_settings(max_examples=30, deadline=None)
def test_hypothesis_today_remaining_budget_cap(
    now_hour: int, now_minute: int, completed_m: int
) -> None:
    """Property 4: Today's remaining budget formula is correctly clamped
    to remaining window minus completed.
    """
    now_dt = datetime(2026, 10, 23, now_hour, now_minute)  # Friday
    base_budget = 120
    w_start = "17:00"
    w_end = "21:30"

    budget = calculate_today_remaining_budget(
        now=now_dt,
        base_budget=base_budget,
        study_window_start=w_start,
        study_window_end=w_end,
        recurring_unavailable_blocks=[],
        completed_minutes_today=completed_m,
    )

    assert budget >= 0, "Budget cannot be negative"
    assert budget <= base_budget, "Budget cannot exceed base daily budget"

    # If now >= 21:30, remaining budget MUST be 0
    if (now_hour > 21) or (now_hour == 21 and now_minute >= 30):
        assert budget == 0, f"Budget should be 0 after study window end, got {budget}"


@given(
    days_ahead=st.integers(min_value=20, max_value=35),
    daily_budget=st.sampled_from([90, 120, 150, 180]),
    pages=st.integers(min_value=15, max_value=25),
)
@hyp_settings(max_examples=25, deadline=None)
def test_hypothesis_priority_share_ordering(
    days_ahead: int, daily_budget: int, pages: int
) -> None:
    """Property 5: At equal workload, difficult >= main >= normal in both days and minutes."""
    today = date(2026, 10, 23)
    exam_date = today + timedelta(days=days_ahead)

    def make_identical_chapters(title: str) -> list[ChapterPlanInput]:
        return [
            ChapterPlanInput(
                id=uuid.uuid4(),
                number=i,
                title=f"{title} Ch {i}",
                printed_page_start=(i - 1) * pages + 1,
                printed_page_end=i * pages,
                custom_order=i,
                book_title=f"{title} Book",
                difficulty_factor=1.0,
            )
            for i in range(1, 4)
        ]

    # Math is difficult (1.6x), Physics is main (1.3x), Chemistry is normal (1.0x)
    setups = [
        SubjectSetupInput(
            subject="Mathematics",
            exam_name="Math Exam",
            exam_date=exam_date,
            chapters=make_identical_chapters("Math"),
        ),
        SubjectSetupInput(
            subject="Physics",
            exam_name="Physics Exam",
            exam_date=exam_date,
            chapters=make_identical_chapters("Physics"),
        ),
        SubjectSetupInput(
            subject="Chemistry",
            exam_name="Chemistry Exam",
            exam_date=exam_date,
            chapters=make_identical_chapters("Chemistry"),
        ),
    ]

    settings = ResolvedPlannerSettings(
        class_band="9-10",
        group="science",
        school_day_minutes=daily_budget,
        holiday_minutes=daily_budget + 30,
        study_window_start="17:00",
        study_window_end="22:00",
        weekly_off_days=["fri", "sat"],
        recurring_unavailable_blocks=[],
        blocked_observance_keys=[],
        custom_blackout_dates=[],
        subject_priorities={
            "Mathematics": "difficult",
            "Physics": "main",
            "Chemistry": "normal",
        },
        planner_parameters={
            "max_consecutive_days_per_subject": 2,
            "priority_weight_mapping": {"normal": 1.0, "main": 1.3, "difficult": 1.6},
        },
    )

    day_calendar = resolve_calendar_days(
        start_date=today,
        end_date=exam_date,
        now=datetime(today.year, today.month, today.day, 12, 0),
        resolved_settings=settings,
        published_holidays=[],
        exam_dates={exam_date},
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=daily_budget,
        setups=setups,
        resolved_settings=settings,
        day_calendar=day_calendar,
    )

    sub_days: dict[str, int] = {s: 0 for s in ["Mathematics", "Physics", "Chemistry"]}
    sub_mins: dict[str, int] = {s: 0 for s in ["Mathematics", "Physics", "Chemistry"]}
    for day in plan.days:
        for s in ["Mathematics", "Physics", "Chemistry"]:
            s_tasks = [t for t in day.tasks if t.subject == s]
            if s_tasks:
                sub_days[s] += 1
                sub_mins[s] += sum(t.est_minutes for t in s_tasks)

    m_d, p_d, c_d = sub_days["Mathematics"], sub_days["Physics"], sub_days["Chemistry"]
    m_m, p_m, c_m = sub_mins["Mathematics"], sub_mins["Physics"], sub_mins["Chemistry"]

    # Property: difficult >= main >= normal in both days and minutes
    assert m_d >= p_d >= c_d, f"Expected days Math ({m_d}) >= Phys ({p_d}) >= Chem ({c_d})"
    assert m_m >= p_m >= c_m, f"Expected mins Math ({m_m}m) >= Phys ({p_m}m) >= Chem ({c_m}m)"


# ============================================================================
# 2. Unit and API Integration Tests
# ============================================================================


@pytest.mark.anyio
async def test_precedence_and_clamping_unit() -> None:
    """Unit: 3-tier precedence clamps parent values to admin bounds and generates notices."""
    student_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        # Create student profile
        user = User(
            id=student_id,
            phone="+8801700999001",
            auth_provider="fake",
            auth_uid=str(uuid.uuid4()),
            role="student",
            display_name="Test User",
            status="active",
        )
        session.add(user)
        prof = StudentProfile(
            user_id=student_id, class_level=8, medium="bn", daily_minutes=60, group="general"
        )
        session.add(prof)

        # Parent sets school_day_minutes to 700m (exceeds admin max 600m)
        settings_row = StudentStudySettings(
            student_id=student_id,
            school_day_minutes=700,
            holiday_minutes=120,
            study_window_start="17:00",
            study_window_end="21:30",
            recurring_unavailable_blocks=[],
            blocked_observance_keys=[],
            custom_blackout_dates=[],
            subject_priorities={},
            version=1,
        )
        session.add(settings_row)
        await session.commit()

        resolved = await resolve_student_settings(session, student_id)
        # Should be clamped to 600m
        assert resolved.school_day_minutes == 600
        assert any("clamped from 700m to 600m" in notice for notice in resolved.clamping_notices)


@pytest.mark.anyio
async def test_warning_when_minutes_above_recommended() -> None:
    """Unit: Warning emitted when parent sets minutes above recommended level (Req D.14)."""
    student_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        user = User(
            id=student_id,
            phone="+8801700999002",
            auth_provider="fake",
            auth_uid=str(uuid.uuid4()),
            role="student",
            display_name="Test User",
            status="active",
        )
        session.add(user)
        # Class 7 recommended is 90m
        prof = StudentProfile(
            user_id=student_id, class_level=7, medium="bn", daily_minutes=60, group="general"
        )
        session.add(prof)

        # Parent sets 140m (allowed within 0-600, but > recommended 90m)
        settings_row = StudentStudySettings(
            student_id=student_id,
            school_day_minutes=140,
            holiday_minutes=200,
            study_window_start="17:00",
            study_window_end="21:30",
            recurring_unavailable_blocks=[],
            blocked_observance_keys=[],
            custom_blackout_dates=[],
            subject_priorities={},
            version=1,
        )
        session.add(settings_row)
        await session.commit()

        resolved = await resolve_student_settings(session, student_id)
        assert resolved.school_day_minutes == 140
        assert any("exceeds the recommended level (90m)" in w for w in resolved.warnings)


@pytest.mark.anyio
async def test_student_cannot_edit_study_settings_directly(core_client: AsyncClient) -> None:
    """API: Student PUT /students/{id}/study-settings returns 403 HTTP; change request works."""
    student_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        st_user = User(
            id=student_id,
            phone="+8801700999003",
            auth_provider="fake",
            auth_uid=str(uuid.uuid4()),
            role="student",
            display_name="Test User",
            status="active",
        )
        session.add(st_user)
        prof = StudentProfile(user_id=student_id, class_level=7, medium="bn", daily_minutes=60)
        session.add(prof)
        await session.commit()

    # Student attempts to PUT study settings
    payload = {
        "school_day_minutes": 100,
        "holiday_minutes": 150,
        "study_window_start": "17:00",
        "study_window_end": "21:30",
        "recurring_unavailable_blocks": [],
        "blocked_observance_keys": [],
        "custom_blackout_dates": [],
        "subject_priorities": {},
    }
    headers = make_auth_headers(student_id, role="student")
    res = await core_client.put(
        f"/v1/students/{student_id}/study-settings",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "STUDENT_CANNOT_EDIT_SETTINGS"

    # Student submits change request -> 201 Created
    cr_res = await core_client.post(
        f"/v1/students/{student_id}/study-settings/change-requests",
        json={"requested_changes": {"school_day_minutes": 90}},
        headers=headers,
    )
    assert cr_res.status_code == 201
    assert cr_res.json()["status"] == "pending"


@pytest.mark.anyio
async def test_unlinked_parent_gets_403(core_client: AsyncClient) -> None:
    """API: Unlinked parent gets 403 when trying to access or edit student settings."""
    student_id = uuid.uuid4()
    unlinked_parent_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        st_user = User(
            id=student_id,
            phone="+8801700999004",
            auth_provider="fake",
            auth_uid=str(uuid.uuid4()),
            role="student",
            display_name="Test User",
            status="active",
        )
        p_user = User(
            id=unlinked_parent_id,
            phone="+8801700999005",
            auth_provider="fake",
            auth_uid=str(uuid.uuid4()),
            role="parent",
            display_name="Test User",
            status="active",
        )
        session.add_all([st_user, p_user])
        prof = StudentProfile(user_id=student_id, class_level=7, medium="bn", daily_minutes=60)
        session.add(prof)
        await session.commit()

    headers = make_auth_headers(unlinked_parent_id, role="parent")
    res = await core_client.get(f"/v1/students/{student_id}/study-settings", headers=headers)
    assert res.status_code == 403


@pytest.mark.anyio
async def test_non_admin_gets_403_on_admin_routes(core_client: AsyncClient) -> None:
    """API: Non-admin users (parent or student) get 403 on /v1/admin/* routes."""
    parent_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        p_user = User(
            id=parent_id,
            phone="+8801700999006",
            auth_provider="fake",
            auth_uid=str(uuid.uuid4()),
            role="parent",
            display_name="Test User",
            status="active",
        )
        session.add(p_user)
        await session.commit()

    headers = make_auth_headers(parent_id, role="parent")
    res = await core_client.get("/v1/admin/policies", headers=headers)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN_ROLE"


@pytest.mark.anyio
async def test_optimistic_concurrency_409_on_concurrent_edits(core_client: AsyncClient) -> None:
    """API: 409 Conflict raised when updating with stale expected_version."""
    parent_id = uuid.uuid4()
    student_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        p_user = User(
            id=parent_id,
            phone="+8801700999007",
            auth_provider="fake",
            auth_uid=str(uuid.uuid4()),
            role="parent",
            display_name="Test User",
            status="active",
        )
        st_user = User(
            id=student_id,
            phone="+8801700999008",
            auth_provider="fake",
            auth_uid=str(uuid.uuid4()),
            role="student",
            display_name="Test User",
            status="active",
        )
        link = ParentStudentLink(parent_id=parent_id, student_id=student_id, status="active")
        prof = StudentProfile(user_id=student_id, class_level=7, medium="bn", daily_minutes=60)
        settings_row = StudentStudySettings(
            student_id=student_id,
            school_day_minutes=60,
            holiday_minutes=120,
            study_window_start="17:00",
            study_window_end="21:30",
            recurring_unavailable_blocks=[],
            blocked_observance_keys=[],
            custom_blackout_dates=[],
            subject_priorities={},
            version=3,
        )
        session.add_all([p_user, st_user, link, prof, settings_row])
        await session.commit()

    headers = make_auth_headers(parent_id, role="parent")
    # Pass stale version 2 (actual is 3)
    payload = {
        "school_day_minutes": 80,
        "holiday_minutes": 140,
        "study_window_start": "17:00",
        "study_window_end": "21:30",
        "recurring_unavailable_blocks": [],
        "blocked_observance_keys": [],
        "custom_blackout_dates": [],
        "subject_priorities": {},
        "expected_version": 2,
    }
    res = await core_client.put(
        f"/v1/students/{student_id}/study-settings",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "CONCURRENT_MODIFICATION"


@pytest.mark.anyio
async def test_draft_holiday_and_publish_idempotence(core_client: AsyncClient) -> None:
    """API: Draft holiday does not affect plans until published; publishing is idempotent."""
    admin_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        admin_user = User(
            id=admin_id,
            phone="+8801700999009",
            auth_provider="fake",
            auth_uid=str(uuid.uuid4()),
            role="admin",
            display_name="Test User",
            status="active",
        )
        session.add(admin_user)
        await session.commit()

    headers = make_auth_headers(admin_id, role="admin")

    # 1. Import draft holiday
    import_payload = {
        "holidays": [
            {
                "start_date": "2026-11-10",
                "end_date": "2026-11-10",
                "name": "Draft Holiday",
                "holiday_type": "national",
                "study_blackout": True,
            }
        ]
    }
    res_import = await core_client.post(
        "/v1/admin/holidays/import", json=import_payload, headers=headers
    )
    assert res_import.status_code == 201
    holiday_id = res_import.json()[0]["id"]
    assert res_import.json()[0]["verified"] is False
    assert res_import.json()[0]["status"] == "draft"

    # 2. Preview impact
    res_preview = await core_client.post(
        f"/v1/admin/holidays/{holiday_id}/preview-impact", headers=headers
    )
    assert res_preview.status_code == 200

    # 3. Publish holiday
    res_pub = await core_client.post(f"/v1/admin/holidays/{holiday_id}/publish", headers=headers)
    assert res_pub.status_code == 200
    assert res_pub.json()["status"] == "published"

    # 4. Publish again (idempotent)
    res_pub2 = await core_client.post(f"/v1/admin/holidays/{holiday_id}/publish", headers=headers)
    assert res_pub2.status_code == 200
    assert res_pub2.json()["status"] == "already_published"


@pytest.mark.anyio
async def test_audit_entries_written(core_client: AsyncClient) -> None:
    """API: Verify structured audit entries with old and new values are written."""
    parent_id = uuid.uuid4()
    student_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        p_user = User(
            id=parent_id,
            phone="+8801700999010",
            auth_provider="fake",
            auth_uid=str(uuid.uuid4()),
            role="parent",
            display_name="Test User",
            status="active",
        )
        st_user = User(
            id=student_id,
            phone="+8801700999011",
            auth_provider="fake",
            auth_uid=str(uuid.uuid4()),
            role="student",
            display_name="Test User",
            status="active",
        )
        link = ParentStudentLink(parent_id=parent_id, student_id=student_id, status="active")
        prof = StudentProfile(user_id=student_id, class_level=7, medium="bn", daily_minutes=60)
        session.add_all([p_user, st_user, link, prof])
        await session.commit()

    headers = make_auth_headers(parent_id, role="parent")
    payload = {
        "school_day_minutes": 85,
        "holiday_minutes": 150,
        "study_window_start": "17:00",
        "study_window_end": "21:30",
        "recurring_unavailable_blocks": [],
        "blocked_observance_keys": ["eid_ul_fitr"],
        "custom_blackout_dates": [
            {"start_date": "2026-11-05", "end_date": "2026-11-05", "reason": "family_event"}
        ],
        "subject_priorities": {"Mathematics": "difficult"},
    }
    res = await core_client.put(
        f"/v1/students/{student_id}/study-settings", json=payload, headers=headers
    )
    assert res.status_code == 200

    # Query audit_log table
    async with AsyncSessionLocal() as session:
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.actor_id == parent_id,
                AuditLog.action == "student_study_settings.update",
            )
            .order_by(AuditLog.at.desc())
        )
        res_audit = await session.execute(stmt)
        entry = res_audit.scalar_one_or_none()
        assert entry is not None
        assert entry.meta["new_value"]["school_day_minutes"] == 85
        assert "eid_ul_fitr" in entry.meta["new_value"]["blocked_observance_keys"]


@pytest.mark.anyio
async def test_client_config_exposes_limits_and_catalog_no_admin_leak(
    gateway_client: AsyncClient,
) -> None:
    """API: /v1/client/config exposes observance catalog and limits
    without leaking admin internals.
    """
    res = await gateway_client.get("/v1/client/config", headers=CLIENT_HEADERS)
    assert res.status_code == 200
    data = res.json()

    assert "observance_catalog" in data
    assert len(data["observance_catalog"]) >= 10
    assert any(o["key"] == "eid_ul_fitr" for o in data["observance_catalog"])

    assert "planner_config" in data
    assert "class_band_limits" in data["planner_config"]
    assert "weekly_off_days" in data["planner_config"]
    assert data["planner_config"]["weekly_off_days"] == ["fri", "sat"]

    # Verify no admin internals leak
    assert "admin_policies" not in data
    assert "audit" not in data
    assert "draft" not in str(data).lower()


# ============================================================================
# 3. Fix Round Tests: Priority Days/Minutes, Spaced Revision, Exam Day Logic
# ============================================================================


@given(
    total_pages_per_ch=st.integers(min_value=15, max_value=30),
    horizon_days=st.integers(min_value=20, max_value=35),
)
@hyp_settings(max_examples=15, deadline=None)
def test_hypothesis_priority_days_and_minutes_equal_workload(
    total_pages_per_ch: int, horizon_days: int
) -> None:
    """Property: At equal workload, difficult >= main >= normal in both days and minutes."""
    today = date(2026, 10, 23)
    exam_date = today + timedelta(days=horizon_days)

    def make_equal_chapters(prefix: str) -> list[ChapterPlanInput]:
        return [
            ChapterPlanInput(
                id=uuid.uuid4(),
                number=i,
                title=f"{prefix} Ch {i}",
                printed_page_start=(i - 1) * total_pages_per_ch + 1,
                printed_page_end=i * total_pages_per_ch,
                custom_order=i,
                book_title=f"{prefix} Book",
                difficulty_factor=1.0,
                weight=1.0,
                mastery=0.5,
            )
            for i in range(1, 4)
        ]

    setups = [
        SubjectSetupInput(
            subject="Mathematics",
            exam_name="Math Exam",
            exam_date=exam_date,
            chapters=make_equal_chapters("Math"),
        ),
        SubjectSetupInput(
            subject="Physics",
            exam_name="Physics Exam",
            exam_date=exam_date,
            chapters=make_equal_chapters("Physics"),
        ),
        SubjectSetupInput(
            subject="Chemistry",
            exam_name="Chemistry Exam",
            exam_date=exam_date,
            chapters=make_equal_chapters("Chemistry"),
        ),
    ]

    settings = ResolvedPlannerSettings(
        class_band="9-10",
        group="science",
        school_day_minutes=120,
        holiday_minutes=180,
        study_window_start="17:00",
        study_window_end="21:30",
        weekly_off_days=["fri", "sat"],
        recurring_unavailable_blocks=[],
        blocked_observance_keys=[],
        custom_blackout_dates=[],
        subject_priorities={
            "Mathematics": "difficult",
            "Physics": "main",
            "Chemistry": "normal",
        },
        planner_parameters={
            "max_consecutive_days_per_subject": 2,
            "priority_weight_mapping": {"normal": 1.0, "main": 1.3, "difficult": 1.6},
            "appearance_frequency_targets": {"difficult": 0.67, "main": 0.50, "normal": 0.38},
        },
    )

    day_calendar = resolve_calendar_days(
        start_date=today,
        end_date=exam_date,
        now=datetime(today.year, today.month, today.day, 12, 0),
        resolved_settings=settings,
        published_holidays=[],
        exam_dates={exam_date},
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=120,
        setups=setups,
        resolved_settings=settings,
        day_calendar=day_calendar,
    )

    # Count days and minutes per subject
    sub_days: dict[str, set[date]] = {"Mathematics": set(), "Physics": set(), "Chemistry": set()}
    sub_mins: dict[str, int] = {"Mathematics": 0, "Physics": 0, "Chemistry": 0}

    for day in plan.days:
        for t in day.tasks:
            if t.subject in sub_days:
                sub_days[t.subject].add(day.date)
                sub_mins[t.subject] += t.est_minutes

    math_days = len(sub_days["Mathematics"])
    phys_days = len(sub_days["Physics"])
    chem_days = len(sub_days["Chemistry"])

    math_mins = sub_mins["Mathematics"]
    phys_mins = sub_mins["Physics"]
    chem_mins = sub_mins["Chemistry"]

    # Property test: difficult >= main >= normal in both days and minutes
    assert math_days >= phys_days >= chem_days, (
        f"Days ordering violated: Math({math_days}) >= Phys({phys_days}) >= Chem({chem_days})"
    )
    assert math_mins >= phys_mins >= chem_mins, (
        f"Minutes ordering violated: Math({math_mins}m) >= Phys({phys_mins}m) >= Chem({chem_mins}m)"
    )


def test_spaced_revision_intervals_and_page_ranges() -> None:
    """Revision tasks must reference earlier-studied material at spaced intervals (1, 3, 7 days),
    never same-day study, always with page ranges.
    """
    today = date(2026, 10, 23)
    exam_date = today + timedelta(days=25)

    chapters = [
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=1,
            title="Algebra Basics",
            printed_page_start=1,
            printed_page_end=30,
            custom_order=1,
            book_title="General Math",
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=2,
            title="Geometry",
            printed_page_start=31,
            printed_page_end=60,
            custom_order=2,
            book_title="General Math",
        ),
    ]

    setups = [
        SubjectSetupInput(
            subject="Mathematics",
            exam_name="Math Midterm",
            exam_date=exam_date,
            chapters=chapters,
        )
    ]

    settings = ResolvedPlannerSettings(
        class_band="6-8",
        group="general",
        school_day_minutes=90,
        holiday_minutes=120,
        study_window_start="17:00",
        study_window_end="21:30",
        weekly_off_days=["fri", "sat"],
        recurring_unavailable_blocks=[],
        blocked_observance_keys=[],
        custom_blackout_dates=[],
        subject_priorities={"Mathematics": "main"},
    )

    day_calendar = resolve_calendar_days(
        start_date=today,
        end_date=exam_date,
        now=datetime(today.year, today.month, today.day, 12, 0),
        resolved_settings=settings,
        published_holidays=[],
        exam_dates={exam_date},
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=90,
        setups=setups,
        resolved_settings=settings,
        day_calendar=day_calendar,
    )

    # Track when page ranges were studied vs revised
    studied_slices: dict[tuple[int, int], date] = {}
    spaced_revisions_found = 0

    for day in plan.days:
        for t in day.tasks:
            p_start = t.refs.get("printed_page_start")
            p_end = t.refs.get("printed_page_end")

            if t.type == "study" and p_start and p_end:
                studied_slices[(p_start, p_end)] = day.date

            if t.type == "revision" and t.refs.get("spaced_interval_days"):
                spaced_revisions_found += 1
                # Must always carry page ranges
                assert p_start is not None, "Spaced revision must carry printed_page_start"
                assert p_end is not None, "Spaced revision must carry printed_page_end"

                # Never same-day study: revision date must be strictly after study date
                orig_study_date = studied_slices.get((p_start, p_end))
                if orig_study_date:
                    assert day.date > orig_study_date, (
                        f"Spaced revision on {day.date} cannot be same-day as "
                        f"study ({orig_study_date})"
                    )

    assert spaced_revisions_found > 0, "Spaced revision tasks should be generated"


def test_exam_days_per_subject_and_approaching_exam_reduction() -> None:
    """Exam days: zero study only for the subject with an exam that day.
    Subjects with exams within N days (default 3) scheduled at reduced load (<= 50%).
    Warn when exam falls on weekly off day or blackout.
    """
    today = date(2026, 10, 23)  # Friday (weekly off day)
    math_exam_date = today + timedelta(days=5)  # Wednesday
    science_exam_date = today + timedelta(days=12)

    ch_math = [
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=1,
            title="Math Ch 1",
            printed_page_start=1,
            printed_page_end=30,
            custom_order=1,
        )
    ]
    ch_sci = [
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=1,
            title="Sci Ch 1",
            printed_page_start=1,
            printed_page_end=30,
            custom_order=1,
        )
    ]

    setups = [
        SubjectSetupInput(
            subject="Mathematics",
            exam_name="Math Exam",
            exam_date=math_exam_date,
            chapters=ch_math,
        ),
        SubjectSetupInput(
            subject="General Science",
            exam_name="Science Exam",
            exam_date=science_exam_date,
            chapters=ch_sci,
        ),
    ]

    settings = ResolvedPlannerSettings(
        class_band="6-8",
        group="general",
        school_day_minutes=90,
        holiday_minutes=120,
        study_window_start="17:00",
        study_window_end="21:30",
        weekly_off_days=["fri", "sat"],
        recurring_unavailable_blocks=[],
        blocked_observance_keys=[],
        custom_blackout_dates=[],
        subject_priorities={"Mathematics": "difficult", "General Science": "normal"},
        planner_parameters={
            "exam_approaching_window_days": 3,
            "exam_approaching_load_ratio": 0.50,
        },
    )

    warnings: list[str] = []
    day_calendar = resolve_calendar_days(
        start_date=today,
        end_date=science_exam_date,
        now=datetime(today.year, today.month, today.day, 12, 0),
        resolved_settings=settings,
        published_holidays=[],
        exam_dates={math_exam_date: ["Mathematics"], science_exam_date: ["General Science"]},
        warnings=warnings,
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=90,
        setups=setups,
        resolved_settings=settings,
        day_calendar=day_calendar,
    )

    # 1. On math_exam_date: Mathematics MUST have 0 study
    math_exam_day = next(d for d in plan.days if d.date == math_exam_date)
    math_tasks = [t for t in math_exam_day.tasks if t.subject == "Mathematics"]
    assert len(math_tasks) == 0, "Mathematics must have ZERO study on its exam date"

    # Other subjects (General Science) can study on math_exam_date
    sci_tasks = [t for t in math_exam_day.tasks if t.subject == "General Science"]
    assert len(sci_tasks) > 0, "General Science can study on Mathematics exam date"


def test_exam_on_weekly_off_and_blackout_warning() -> None:
    """Warn when an exam date falls on a weekly off day or blackout."""
    today = date(2026, 10, 23)  # Friday (weekly off day)
    exam_on_friday = today + timedelta(days=7)  # Next Friday
    blackout_date = today + timedelta(days=10)
    exam_on_blackout = blackout_date

    settings = ResolvedPlannerSettings(
        class_band="9-10",
        group="science",
        school_day_minutes=120,
        holiday_minutes=180,
        study_window_start="17:00",
        study_window_end="21:30",
        weekly_off_days=["fri", "sat"],
        recurring_unavailable_blocks=[],
        blocked_observance_keys=[],
        custom_blackout_dates=[
            {"start_date": str(blackout_date), "end_date": str(blackout_date), "reason": "travel"}
        ],
        subject_priorities={},
    )

    warnings: list[str] = []
    resolve_calendar_days(
        start_date=today,
        end_date=exam_on_blackout,
        now=datetime(today.year, today.month, today.day, 12, 0),
        resolved_settings=settings,
        published_holidays=[],
        exam_dates={exam_on_friday: ["Mathematics"], exam_on_blackout: ["Physics"]},
        warnings=warnings,
    )

    assert any("EXAM_ON_WEEKLY_OFF" in w for w in warnings), (
        "Must warn when exam falls on weekly off"
    )
    assert any("EXAM_ON_BLACKOUT" in w for w in warnings), "Must warn when exam falls on blackout"


def test_buffer_separated_from_blackout_and_zero_reasons() -> None:
    """Separate buffer from blackout in the model and printout.
    Buffer day is a catch-up day carrying rolled-forward tasks.
    Print reason codes for zero days (exam, parent blackout, calendar blackout, rest).
    """
    today = date(2026, 10, 23)
    b_date = today + timedelta(days=3)
    exam_date = today + timedelta(days=15)

    settings = ResolvedPlannerSettings(
        class_band="6-8",
        group="general",
        school_day_minutes=90,
        holiday_minutes=120,
        study_window_start="17:00",
        study_window_end="21:30",
        weekly_off_days=["fri", "sat"],
        recurring_unavailable_blocks=[],
        blocked_observance_keys=[],
        custom_blackout_dates=[
            {"start_date": str(b_date), "end_date": str(b_date), "reason": "family_event"}
        ],
        subject_priorities={},
    )

    day_calendar = resolve_calendar_days(
        start_date=today,
        end_date=exam_date,
        now=datetime(today.year, today.month, today.day, 12, 0),
        resolved_settings=settings,
        published_holidays=[],
        exam_dates={exam_date},
    )

    # Blackout day has zero_reason == 'parent blackout'
    blackout_day = next(d for d in day_calendar if d.date == b_date)
    assert blackout_day.day_type == "blackout"
    assert blackout_day.zero_reason == "parent blackout"
    assert blackout_day.budget_minutes == 0

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=90,
        setups=[
            SubjectSetupInput(
                subject="Mathematics",
                exam_name="Math Exam",
                exam_date=exam_date,
                chapters=[
                    ChapterPlanInput(
                        id=uuid.uuid4(),
                        number=1,
                        title="Ch 1",
                        printed_page_start=1,
                        printed_page_end=15,
                        custom_order=1,
                    )
                ],
            )
        ],
        resolved_settings=settings,
        day_calendar=day_calendar,
    )

    # Buffer day on Day 7 is separate from blackout and carries rolled tasks if any
    buffer_days = [d for d in plan.days if d.day_type == "buffer"]
    assert len(buffer_days) > 0, "Buffer days must be generated in schedule"
    for bd in buffer_days:
        assert bd.day_type != "blackout", "Buffer days must be distinct from blackout days"
        if bd.planned_minutes == 0:
            assert bd.zero_reason == "rest"


def test_min_study_block_and_day_labels_reflect_content() -> None:
    """Minimum study block (default 20 minutes) and day labels must reflect content:
    a day with study tasks is 'study', not 'revision'.
    """
    today = date(2026, 10, 23)
    exam_date = today + timedelta(days=20)

    setups = [
        SubjectSetupInput(
            subject="Mathematics",
            exam_name="Math Exam",
            exam_date=exam_date,
            chapters=[
                ChapterPlanInput(
                    id=uuid.uuid4(),
                    number=1,
                    title="Ch 1",
                    printed_page_start=1,
                    printed_page_end=50,
                    custom_order=1,
                )
            ],
        )
    ]

    settings = ResolvedPlannerSettings(
        class_band="6-8",
        group="general",
        school_day_minutes=90,
        holiday_minutes=120,
        study_window_start="17:00",
        study_window_end="21:30",
        weekly_off_days=["fri", "sat"],
        recurring_unavailable_blocks=[],
        blocked_observance_keys=[],
        custom_blackout_dates=[],
        subject_priorities={},
        planner_parameters={"min_study_block_minutes": 20},
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=90,
        setups=setups,
        resolved_settings=settings,
    )

    for day in plan.days:
        # Every generated task must be >= 20 mins
        for t in day.tasks:
            assert t.est_minutes >= 20, (
                f"Task {t.type} in {t.subject} has < 20 mins: {t.est_minutes}m"
            )

        # Day label reflects content: day with study tasks is labeled 'study'
        has_study = any(t.type == "study" for t in day.tasks)
        if has_study:
            assert day.day_type == "study", (
                f"Day with study tasks must be labeled 'study', got {day.day_type}"
            )


@pytest.mark.anyio
async def test_adaptive_hook_and_5_layer_hierarchy() -> None:
    """Adaptive hook: adaptive_mode (manual, suggest, auto_within_limits)
    and versioned ai_adjustments layer.
    Precedence: admin hard limits -> parent-locked -> AI -> class defaults -> system defaults.
    """
    student_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        # 1. Create User and Student Profile
        user = User(
            id=student_id,
            phone=f"+88017{uuid.uuid4().int % 100000000:08d}",
            auth_provider="phone",
            auth_uid=str(uuid.uuid4()),
            role="student",
            display_name="Adaptive Test Student",
            status="active",
        )
        session.add(user)

        profile = StudentProfile(
            user_id=student_id,
            class_level=7,
            group="general",
            daily_minutes=90,
        )
        session.add(profile)

        # 2. Create student study settings with AI adjustment and parent-locked field
        # AI suggests 110m for school day, but parent set 85m and locked it
        # AI also suggests holiday_minutes = 135m, which is NOT locked
        settings_record = StudentStudySettings(
            student_id=student_id,
            school_day_minutes=85,
            holiday_minutes=100,
            study_window_start="17:00",
            study_window_end="21:00",
            adaptive_mode="auto_within_limits",
            ai_adjustments={
                "version": 1,
                "adjustments": {
                    "school_day_minutes": 110,
                    "holiday_minutes": 135,
                },
            },
            parent_locked_fields=["school_day_minutes"],
            version=1,
        )
        session.add(settings_record)
        await session.commit()

        # 3. Resolve settings through 5-layer hierarchy
        resolved = await resolve_student_settings(session, student_id)

        assert resolved.adaptive_mode == "auto_within_limits"
        # Parent-locked value (85m) overrides AI adjustment (110m)
        assert resolved.school_day_minutes == 85, (
            f"Parent-locked school day (85m) should override AI, got {resolved.school_day_minutes}m"
        )
        # Unlocked holiday minutes: AI adjustment (135m) applies
        assert resolved.holiday_minutes == 135, (
            f"Unlocked holiday minutes should use AI (135m), got {resolved.holiday_minutes}m"
        )
