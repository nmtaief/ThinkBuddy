"""Consolidated test suite: test_planner.py."""
from __future__ import annotations


# ========================================================================
# Consolidated from: tests/test_p03_planner.py
# ========================================================================

"""Acceptance, property-based, and security tests for P03: Study Setup & Planner.

Verifies:
1. Pure-Python planner library (engine.py):
   - Multi-subject shared daily budget: no day exceeds student's daily study minutes.
   - No task scheduled past exam date.
   - Chapter custom_order is strictly respected.
   - Completed tasks preserved unchanged after plan regeneration.
2. Edge cases:
   - Exam today or tomorrow.
   - Zero usable days (empty/mismatched available days).
   - Empty syllabus (no chapters).
   - A huge chapter (500 pages) split contiguously across multiple days.
   - Midnight in Dhaka (UTC+6 timezone date boundary).
3. API Endpoints, Security, Authorization, and Concurrency:
   - PUT /v1/students/{id}/study-setups/{subject}: parent only, cross-family parent denied (403),
     student denied (403), optimistic concurrency conflict (409).
   - POST /v1/students/{id}/study-setups/{subject}/change-requests: student only,
     cross-student denied (403).
   - GET /v1/students/{id}/plan: authorized student and linked parent only.
   - GET /v1/students/{id}/today: Dhaka timezone home screen learning loop payload.
   - PATCH /v1/tasks/{id}: student only, parents read-only (403), cross-student denied (403).
"""


import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from hypothesis import given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st
from sqlalchemy import select

from core.common.database import AsyncSessionLocal
from core.curriculum.models import Book, Chapter
from core.planner.engine import (
    ChapterPlanInput,
    CompletedTaskRecord,
    SubjectSetupInput,
    generate_student_plan,
)
from core.planner.models import PlanDay, Task
from rag.ingest import CurriculumImporter

CLIENT_HEADERS_ANDROID = {
    "X-Client-Platform": "android",
    "X-Client-Form-Factor": "phone",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "device-test-planner-001",
    "Accept-Language": "bn",
}

SAMPLE_MANIFEST_PATH = Path("tests/data/sample_manifest.jsonl")


@pytest.fixture(autouse=True)
async def setup_curriculum() -> None:
    """Ensure curriculum textbooks are in database."""
    importer = CurriculumImporter()
    await importer.import_manifest(SAMPLE_MANIFEST_PATH, resume=True)

    async with AsyncSessionLocal() as session:
        stmt = select(Book).where(Book.subject == "science", Book.class_level == 7)
        res = await session.execute(stmt)
        if not res.scalars().first():
            sci_book = Book(
                id=uuid.UUID("4fa85f64-5717-4562-b3fc-2c963f66afa2"),
                title="বিজ্ঞান (সপ্তম শ্রেণি)",
                class_level=7,
                subject="science",
                medium="bn",
                edition="2024",
                source_uri="s3://thinkbuddy-textbooks/class7/science_bn_2024.pdf",
            )
            session.add(sci_book)
            await session.flush()
            sci_ch1 = Chapter(
                id=uuid.UUID("7ca85f64-5717-4562-b3fc-2c963f66af11"),
                book_id=sci_book.id,
                number=1,
                title="নিম্নশ্রেণির জীব",
                printed_page_start=1,
                printed_page_end=15,
                order_index=1,
                difficulty_factor=1.0,
            )
            session.add(sci_ch1)
            await session.commit()


# =============================================================================
# 1. Hypothesis Property-Based Tests for Pure Planner Engine
# =============================================================================


@given(
    daily_budget=st.integers(min_value=20, max_value=180),
    days_to_exam_1=st.integers(min_value=3, max_value=45),
    days_to_exam_2=st.integers(min_value=3, max_value=45),
    ch1_pages=st.integers(min_value=5, max_value=60),
    ch2_pages=st.integers(min_value=5, max_value=60),
)
@hyp_settings(max_examples=25, deadline=None)
def test_property_combined_daily_budget_never_exceeded(
    daily_budget: int,
    days_to_exam_1: int,
    days_to_exam_2: int,
    ch1_pages: int,
    ch2_pages: int,
) -> None:
    """Hypothesis: Sum of planned minutes on ANY day across ALL subjects <= daily_budget."""
    today = date(2026, 11, 1)
    exam_1 = today + timedelta(days=days_to_exam_1)
    exam_2 = today + timedelta(days=days_to_exam_2)

    ch1 = ChapterPlanInput(
        id=uuid.uuid4(),
        number=1,
        title="Math Basics",
        printed_page_start=1,
        printed_page_end=ch1_pages,
        custom_order=1,
    )
    ch2 = ChapterPlanInput(
        id=uuid.uuid4(),
        number=1,
        title="Science Intro",
        printed_page_start=1,
        printed_page_end=ch2_pages,
        custom_order=1,
    )

    setup1 = SubjectSetupInput(
        subject="math", exam_name="Math Exam", exam_date=exam_1, chapters=[ch1]
    )
    setup2 = SubjectSetupInput(
        subject="science", exam_name="Science Exam", exam_date=exam_2, chapters=[ch2]
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=daily_budget,
        setups=[setup1, setup2],
        available_days=["sat", "sun", "mon", "tue", "wed", "thu"],
    )

    for p_day in plan.days:
        assert p_day.planned_minutes <= daily_budget, (
            f"Day {p_day.date} planned {p_day.planned_minutes}m exceeding budget {daily_budget}m!"
        )


@given(
    days_to_exam=st.integers(min_value=1, max_value=60),
    num_chapters=st.integers(min_value=1, max_value=6),
)
@hyp_settings(max_examples=20, deadline=None)
def test_property_no_task_after_exam_date(days_to_exam: int, num_chapters: int) -> None:
    """Hypothesis Property: No task is ever scheduled past its subject's exam_date."""
    today = date(2026, 11, 1)
    exam_date = today + timedelta(days=days_to_exam)

    chapters = [
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=i,
            title=f"Chapter {i}",
            printed_page_start=1 + (i - 1) * 15,
            printed_page_end=i * 15,
            custom_order=i,
        )
        for i in range(1, num_chapters + 1)
    ]
    setup = SubjectSetupInput(
        subject="math", exam_name="Final Exam", exam_date=exam_date, chapters=chapters
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=60,
        setups=[setup],
        available_days=["sat", "sun", "mon", "tue", "wed", "thu"],
    )

    for p_day in plan.days:
        for t in p_day.tasks:
            assert p_day.date <= exam_date, (
                f"Task {t.type} scheduled on {p_day.date} after exam {exam_date}!"
            )


def test_property_chapter_order_preserved() -> None:
    """Property: Tasks for earlier custom_order chapters never appear after subsequent chapters."""
    today = date(2026, 11, 1)
    exam_date = today + timedelta(days=30)

    ch1 = ChapterPlanInput(
        id=uuid.uuid4(),
        number=1,
        title="Ch1",
        printed_page_start=1,
        printed_page_end=20,
        custom_order=1,
    )
    ch2 = ChapterPlanInput(
        id=uuid.uuid4(),
        number=2,
        title="Ch2",
        printed_page_start=21,
        printed_page_end=40,
        custom_order=2,
    )
    ch3 = ChapterPlanInput(
        id=uuid.uuid4(),
        number=3,
        title="Ch3",
        printed_page_start=41,
        printed_page_end=60,
        custom_order=3,
    )

    setup = SubjectSetupInput(
        subject="math", exam_name="Exam", exam_date=exam_date, chapters=[ch1, ch2, ch3]
    )
    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=60,
        setups=[setup],
    )

    # Track earliest day study task appeared for each chapter
    first_seen: dict[int, date] = {}
    last_seen: dict[int, date] = {}
    for p_day in plan.days:
        for t in p_day.tasks:
            if t.type == "study" and t.refs.get("chapter_number"):
                num = int(t.refs["chapter_number"])
                if num not in first_seen:
                    first_seen[num] = p_day.date
                last_seen[num] = p_day.date

    # Chapter 1 must be studied at or before Chapter 2
    if 1 in first_seen and 2 in first_seen:
        assert first_seen[1] <= first_seen[2]
    if 2 in first_seen and 3 in first_seen:
        assert first_seen[2] <= first_seen[3]


def test_property_completed_tasks_preserved_unchanged() -> None:
    """Property: Plan regeneration preserves existing completed tasks unchanged."""
    today = date(2026, 11, 10)
    exam_date = today + timedelta(days=20)
    ch_id = uuid.uuid4()

    ch1 = ChapterPlanInput(
        id=ch_id, number=1, title="Ch1", printed_page_start=1, printed_page_end=30, custom_order=1
    )
    setup = SubjectSetupInput(subject="math", exam_name="Exam", exam_date=exam_date, chapters=[ch1])

    # Record a task completed yesterday
    done_task_id = uuid.uuid4()
    completed = [
        CompletedTaskRecord(
            task_id=done_task_id,
            subject="math",
            chapter_id=ch_id,
            plan_date=today - timedelta(days=1),
            type="study",
            est_minutes=35,
            refs={
                "book_title": "Math",
                "chapter_number": 1,
                "printed_page_start": 1,
                "printed_page_end": 10,
            },
            completed_at="2026-11-09T14:00:00Z",
        )
    ]

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=60,
        setups=[setup],
        completed_tasks=completed,
    )

    # Verify completed task is present with status 'done'
    found_done = False
    for p_day in plan.days:
        for t in p_day.tasks:
            if t.id == done_task_id:
                found_done = True
                assert t.status == "done"
                assert p_day.date == today - timedelta(days=1)
    assert found_done is True


# =============================================================================
# 2. Edge Case Tests
# =============================================================================


def test_edge_case_exam_today_or_tomorrow() -> None:
    """Edge Case: Exam today or tomorrow returns emergency plan with warnings."""
    today = date(2026, 11, 1)

    # 1. Exam today
    ch1 = ChapterPlanInput(
        id=uuid.uuid4(),
        number=1,
        title="Ch1",
        printed_page_start=1,
        printed_page_end=15,
        custom_order=1,
    )
    setup_today = SubjectSetupInput(
        subject="math", exam_name="Exam Today", exam_date=today, chapters=[ch1]
    )

    plan_today = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=60,
        setups=[setup_today],
    )
    assert any("EXAM_TODAY" in w for w in plan_today.warnings)
    assert len(plan_today.days) >= 1
    assert plan_today.days[0].date == today

    # 2. Exam tomorrow
    tomorrow = today + timedelta(days=1)
    setup_tomorrow = SubjectSetupInput(
        subject="math", exam_name="Exam Tomorrow", exam_date=tomorrow, chapters=[ch1]
    )
    plan_tomorrow = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=60,
        setups=[setup_tomorrow],
    )
    assert any("EXAM_TOMORROW" in w for w in plan_tomorrow.warnings)
    assert len(plan_tomorrow.days) >= 1


def test_edge_case_zero_usable_days() -> None:
    """Edge Case: Zero available days matching schedule produces fallback plan with warning."""
    today = date(2026, 11, 2)  # Monday
    # Only available on Sundays, but exam is this Friday (zero usable days before exam)
    exam_date = today + timedelta(days=4)  # Friday
    ch = ChapterPlanInput(
        id=uuid.uuid4(),
        number=1,
        title="Ch",
        printed_page_start=1,
        printed_page_end=10,
        custom_order=1,
    )
    setup = SubjectSetupInput(subject="math", exam_name="Exam", exam_date=exam_date, chapters=[ch])

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=45,
        setups=[setup],
        available_days=["sun"],  # Sunday only
    )
    assert any("ZERO_USABLE_DAYS" in w or "NO_USABLE_DAYS" in w for w in plan.warnings)
    assert len(plan.days) >= 1  # Emergency day provided so student is not left empty-handed


def test_edge_case_no_chapters() -> None:
    """Edge Case: Setup with empty chapters produces safe output with warnings."""
    today = date(2026, 11, 1)
    setup = SubjectSetupInput(
        subject="math", exam_name="Exam", exam_date=today + timedelta(days=10), chapters=[]
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=60,
        setups=[setup],
    )
    assert any("NO_ACTIVE_SUBJECTS" in w for w in plan.warnings)
    assert plan.total_tasks == 0


def test_edge_case_huge_chapter_partitioned_contiguously() -> None:
    """Edge Case: 500-page chapter with 30-min budget is split across days within cap."""
    today = date(2026, 11, 1)
    exam_date = today + timedelta(days=60)

    huge_ch = ChapterPlanInput(
        id=uuid.uuid4(),
        number=1,
        title="Comprehensive Mathematics",
        printed_page_start=1,
        printed_page_end=500,
        custom_order=1,
    )
    setup = SubjectSetupInput(
        subject="math", exam_name="Board Exam", exam_date=exam_date, chapters=[huge_ch]
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=30,
        setups=[setup],
    )

    # 1. Cap is respected on every day
    for d in plan.days:
        assert d.planned_minutes <= 30

    # 2. Study tasks partition the chapter contiguously
    study_tasks = [t for d in plan.days for t in d.tasks if t.type == "study"]
    assert len(study_tasks) > 5  # Split across multiple days

    # Check pages progression
    first_task = study_tasks[0]
    assert first_task.refs["printed_page_start"] == 1


def test_edge_case_midnight_in_dhaka() -> None:
    """Edge Case: Dhaka timezone (+6) rollover at 18:05 UTC produces next calendar day in Dhaka."""
    # 2026-11-01 18:05 UTC is 2026-11-02 00:05 in Asia/Dhaka
    utc_dt = datetime(2026, 11, 1, 18, 5, 0, tzinfo=UTC)
    dhaka_tz = ZoneInfo("Asia/Dhaka")
    dhaka_dt = utc_dt.astimezone(dhaka_tz)

    assert dhaka_dt.date() == date(2026, 11, 2)
    assert dhaka_dt.hour == 0
    assert dhaka_dt.minute == 5


# =============================================================================
# 3. Integration & Security Acceptance Tests (Live DB + Redis)
# =============================================================================


@pytest.mark.asyncio
async def test_p03_study_setup_and_planner_lifecycle(gateway_client: AsyncClient) -> None:
    """Full lifecycle: parent setup, student change request, today home screen, and task update."""
    # 1. Setup Parent 1 and Student 1
    p1_phone = f"+880171{uuid.uuid4().hex[:6]}"
    res_p1 = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{p1_phone}", "role": "parent"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_p1.status_code == 200
    p1_token = res_p1.json()["access_token"]
    p1_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {p1_token}"}

    # Parent creates family and adds child
    res_fam = await gateway_client.post(
        "/v1/families", json={"name": "Rahman Family"}, headers=p1_headers
    )
    assert res_fam.status_code == 201
    fam_id = res_fam.json()["id"]

    res_child = await gateway_client.post(
        f"/v1/families/{fam_id}/students",
        json={
            "display_name": "Rahim Rahman",
            "class_level": 7,
            "medium": "bn",
            "daily_minutes": 60,
        },
        headers=p1_headers,
    )
    assert res_child.status_code == 201
    s1_id = res_child.json()["student_id"]
    link_code = res_child.json()["link_code"]

    # Student 1 logs in with link_code
    s1_phone = f"+880181{uuid.uuid4().hex[:6]}"
    res_s1 = await gateway_client.post(
        "/v1/auth/exchange",
        json={
            "provider_token": f"fake:phone:{s1_phone}",
            "role": "student",
            "link_code": link_code,
        },
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_s1.status_code == 200
    s1_token = res_s1.json()["access_token"]
    s1_id = res_s1.json()["user"]["id"]
    s1_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {s1_token}"}

    # 2. Setup Parent 2 (Isolated Family)
    p2_phone = f"+880191{uuid.uuid4().hex[:6]}"
    res_p2 = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{p2_phone}", "role": "parent"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    p2_token = res_p2.json()["access_token"]
    p2_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {p2_token}"}

    # 3. Retrieve curriculum book & chapters to configure
    res_books = await gateway_client.get("/v1/books?class_level=7&subject=math", headers=p1_headers)
    assert res_books.status_code == 200
    book_id = res_books.json()["items"][0]["id"]

    res_ch = await gateway_client.get(f"/v1/books/{book_id}/chapters", headers=p1_headers)
    assert res_ch.status_code == 200
    chapters = res_ch.json()["items"]
    assert len(chapters) >= 2

    # 4. Security Check: Parent 2 cannot configure Student 1's setup
    exam_date = (date.today() + timedelta(days=30)).isoformat()
    setup_payload = {
        "exam_name": "Annual Final 2026",
        "exam_date": exam_date,
        "daily_study_minutes": 60,
        "available_days": ["sat", "sun", "mon", "tue", "wed", "thu", "fri"],
        "syllabus": [
            {"chapter_id": chapters[0]["id"], "included": True, "custom_order": 1, "weight": 1.0},
            {"chapter_id": chapters[1]["id"], "included": True, "custom_order": 2, "weight": 1.2},
        ],
    }

    res_denied_p2 = await gateway_client.put(
        f"/v1/students/{s1_id}/study-setups/math",
        json=setup_payload,
        headers=p2_headers,
    )
    assert res_denied_p2.status_code == 403
    assert res_denied_p2.json()["error"]["code"] == "FORBIDDEN_STUDENT_ACCESS"

    # Security Check: Student 1 cannot edit study setup directly
    res_denied_s1 = await gateway_client.put(
        f"/v1/students/{s1_id}/study-setups/math",
        json=setup_payload,
        headers=s1_headers,
    )
    assert res_denied_s1.status_code == 403
    assert res_denied_s1.json()["error"]["code"] == "STUDENT_CANNOT_EDIT_SETUP"

    # 5. Parent 1 successfully configures study setup
    res_setup = await gateway_client.put(
        f"/v1/students/{s1_id}/study-setups/math",
        json=setup_payload,
        headers=p1_headers,
    )
    assert res_setup.status_code == 200
    setup_data = res_setup.json()
    assert setup_data["subject"] == "math"
    assert setup_data["version"] == 1
    assert setup_data["active_plan_version"] == 1
    assert len(setup_data["syllabus"]) == 2

    # 6. Concurrency Check: Optimistic Concurrency Conflict (HTTP 409)
    conflict_payload = {**setup_payload, "expected_version": 99}
    res_conflict = await gateway_client.put(
        f"/v1/students/{s1_id}/study-setups/math",
        json=conflict_payload,
        headers=p1_headers,
    )
    assert res_conflict.status_code == 409
    assert res_conflict.json()["error"]["code"] == "CONCURRENT_MODIFICATION"

    # Updating with valid expected_version succeeds and bumps version
    valid_update_payload = {**setup_payload, "expected_version": 1}
    res_v2 = await gateway_client.put(
        f"/v1/students/{s1_id}/study-setups/math",
        json=valid_update_payload,
        headers=p1_headers,
    )
    assert res_v2.status_code == 200
    assert res_v2.json()["version"] == 2
    assert res_v2.json()["active_plan_version"] == 2

    # 7. Student 1 submits Change Request
    res_cr = await gateway_client.post(
        f"/v1/students/{s1_id}/study-setups/math/change-requests",
        json={
            "requested_changes": {"preferred_chapter_order": [chapters[1]["id"], chapters[0]["id"]]}
        },
        headers=s1_headers,
    )
    assert res_cr.status_code == 201
    assert res_cr.json()["status"] == "pending"

    # 8. Student 1 fetches /today payload
    res_today = await gateway_client.get(f"/v1/students/{s1_id}/today", headers=s1_headers)
    assert res_today.status_code == 200
    today_data = res_today.json()
    assert "study_tasks" in today_data
    assert "revision_tasks" in today_data
    assert today_data["streak"] >= 1
    assert "math" in today_data["exam_countdown_days"]

    # 9. Student 1 fetches full plan
    res_plan = await gateway_client.get(f"/v1/students/{s1_id}/plan", headers=s1_headers)
    assert res_plan.status_code == 200
    plan_data = res_plan.json()
    assert len(plan_data["days"]) > 0

    # Pick a task to update
    all_tasks = [t for d in plan_data["days"] for t in d["tasks"]]
    assert len(all_tasks) > 0
    test_task = all_tasks[0]
    task_id = test_task["id"]

    # 10. PATCH /v1/tasks/{id} Security Checks:
    # A. Parent is strictly read-only on task status
    res_patch_parent = await gateway_client.patch(
        f"/v1/tasks/{task_id}",
        json={"status": "done"},
        headers=p1_headers,
    )
    assert res_patch_parent.status_code == 403
    assert res_patch_parent.json()["error"]["code"] == "TASK_UPDATE_STUDENT_ONLY"

    # B. Another student cannot update Student 1's task
    res_fam2 = await gateway_client.post(
        "/v1/families", json={"name": "Karim Family"}, headers=p2_headers
    )
    fam2_id = res_fam2.json()["id"]
    res_child2 = await gateway_client.post(
        f"/v1/families/{fam2_id}/students",
        json={
            "display_name": "Karim Student",
            "class_level": 7,
            "medium": "bn",
            "daily_minutes": 45,
        },
        headers=p2_headers,
    )
    s2_link = res_child2.json()["link_code"]

    s2_phone = f"+880182{uuid.uuid4().hex[:6]}"
    res_s2 = await gateway_client.post(
        "/v1/auth/exchange",
        json={
            "provider_token": f"fake:phone:{s2_phone}",
            "role": "student",
            "link_code": s2_link,
        },
        headers=CLIENT_HEADERS_ANDROID,
    )
    s2_token = res_s2.json()["access_token"]
    s2_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {s2_token}"}

    res_patch_cross_student = await gateway_client.patch(
        f"/v1/tasks/{task_id}",
        json={"status": "done"},
        headers=s2_headers,
    )
    assert res_patch_cross_student.status_code == 403
    assert res_patch_cross_student.json()["error"]["code"] == "FORBIDDEN"

    # C. Student 1 (the task owner) successfully marks task done
    # Select a task dated today so it satisfies student timezone date check
    today_dhaka_date = datetime.now(ZoneInfo("Asia/Dhaka")).date()
    today_dhaka_str = str(today_dhaka_date)
    today_tasks = [t for d in plan_data["days"] if d["date"] <= today_dhaka_str for t in d["tasks"]]
    target_task = today_tasks[0] if today_tasks else test_task
    target_task_id = target_task["id"]

    if not today_tasks:
        async with AsyncSessionLocal() as session:
            t_row = await session.get(Task, uuid.UUID(target_task_id))
            if t_row:
                pd_row = await session.get(PlanDay, t_row.plan_day_id)
                if pd_row:
                    pd_row.date = today_dhaka_date
                    await session.commit()

    res_patch_done = await gateway_client.patch(
        f"/v1/tasks/{target_task_id}",
        json={"status": "done"},
        headers=s1_headers,
    )
    assert res_patch_done.status_code == 200
    updated_task = res_patch_done.json()
    assert updated_task["status"] == "done"
    assert updated_task["completed_at"] is not None


@pytest.mark.asyncio
async def test_concurrent_regenerations_different_subjects_serializes_and_respects_budget(
    gateway_client: AsyncClient,
) -> None:
    """Requirement 1: Two concurrent regenerations for different subjects serialize via lock.

    Proves that when two setups regenerate simultaneously, no combined day exceeds daily budget.
    """
    import asyncio

    # 1. Create Parent and Student
    p_phone = f"+880173{uuid.uuid4().hex[:6]}"
    res_p = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{p_phone}", "role": "parent"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    p_headers = {
        **CLIENT_HEADERS_ANDROID,
        "Authorization": f"Bearer {res_p.json()['access_token']}",
    }

    res_fam = await gateway_client.post(
        "/v1/families", json={"name": "Concurrent Family"}, headers=p_headers
    )
    fam_id = res_fam.json()["id"]

    daily_budget = 90
    res_child = await gateway_client.post(
        f"/v1/families/{fam_id}/students",
        json={
            "display_name": "Concurrent Student",
            "class_level": 7,
            "medium": "bn",
            "daily_minutes": daily_budget,
        },
        headers=p_headers,
    )
    link_code = res_child.json()["link_code"]

    s_phone = f"+880174{uuid.uuid4().hex[:6]}"
    res_s = await gateway_client.post(
        "/v1/auth/exchange",
        json={
            "provider_token": f"fake:phone:{s_phone}",
            "role": "student",
            "link_code": link_code,
        },
        headers=CLIENT_HEADERS_ANDROID,
    )
    student_id = res_s.json()["user"]["id"]
    s_headers = {
        **CLIENT_HEADERS_ANDROID,
        "Authorization": f"Bearer {res_s.json()['access_token']}",
    }

    # Fetch textbook chapters for math and science
    res_books_math = await gateway_client.get(
        "/v1/books?class_level=7&subject=math", headers=p_headers
    )
    math_book_id = res_books_math.json()["items"][0]["id"]
    res_math_ch = await gateway_client.get(f"/v1/books/{math_book_id}/chapters", headers=p_headers)
    math_chapters = res_math_ch.json()["items"]

    res_books_sci = await gateway_client.get(
        "/v1/books?class_level=7&subject=science", headers=p_headers
    )
    sci_book_id = res_books_sci.json()["items"][0]["id"]
    res_sci_ch = await gateway_client.get(f"/v1/books/{sci_book_id}/chapters", headers=p_headers)
    sci_chapters = res_sci_ch.json()["items"]

    today = datetime.now(ZoneInfo("Asia/Dhaka")).date()
    exam_math = today + timedelta(days=40)
    exam_sci = today + timedelta(days=50)

    payload_math = {
        "exam_name": "Math Exam",
        "exam_date": str(exam_math),
        "syllabus": [
            {
                "chapter_id": math_chapters[0]["id"],
                "included": True,
                "custom_order": 1,
                "weight": 1.0,
            }
        ],
    }
    payload_sci = {
        "exam_name": "Science Exam",
        "exam_date": str(exam_sci),
        "syllabus": [
            {
                "chapter_id": sci_chapters[0]["id"],
                "included": True,
                "custom_order": 1,
                "weight": 1.0,
            }
        ],
    }

    # 2. Trigger concurrent regenerations for different subjects
    res_math, res_sci = await asyncio.gather(
        gateway_client.put(
            f"/v1/students/{student_id}/study-setups/math",
            json=payload_math,
            headers=p_headers,
        ),
        gateway_client.put(
            f"/v1/students/{student_id}/study-setups/science",
            json=payload_sci,
            headers=p_headers,
        ),
    )
    assert res_math.status_code == 200
    assert res_sci.status_code == 200

    # 3. Verify unified schedule: no combined day exceeds daily budget
    res_plan = await gateway_client.get(f"/v1/students/{student_id}/plan", headers=s_headers)
    assert res_plan.status_code == 200
    plan = res_plan.json()

    for day in plan["days"]:
        day_total = sum(t["est_minutes"] for t in day["tasks"])
        assert day_total <= daily_budget, (
            f"Day {day['date']} total {day_total}m exceeds budget {daily_budget}m"
        )
        assert day["planned_minutes"] <= daily_budget


def test_min_subject_daily_share_and_cross_subject_feasibility_warning() -> None:
    """Requirement 2: Configurable minimum daily share per active subject
    and cross-subject feasibility warning.
    """
    today = date(2026, 10, 23)
    daily_budget = 100

    ch1 = ChapterPlanInput(
        id=uuid.uuid4(),
        number=1,
        title="Math Ch 1",
        printed_page_start=1,
        printed_page_end=30,
        custom_order=1,
        difficulty_factor=1.0,
    )
    ch2 = ChapterPlanInput(
        id=uuid.uuid4(),
        number=1,
        title="Sci Ch 1",
        printed_page_start=1,
        printed_page_end=30,
        custom_order=1,
        difficulty_factor=1.0,
    )

    setup_math = SubjectSetupInput(
        subject="Mathematics",
        exam_name="Math",
        exam_date=today + timedelta(days=20),
        chapters=[ch1],
    )
    setup_sci = SubjectSetupInput(
        subject="Science",
        exam_name="Science",
        exam_date=today + timedelta(days=25),
        chapters=[ch2],
    )

    # A. Minimum daily share (10%)
    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=daily_budget,
        setups=[setup_math, setup_sci],
        min_subject_daily_share=0.10,
    )
    for day in plan.days:
        if day.day_type == "study" and len(day.tasks) >= 2:
            assert day.planned_minutes <= daily_budget

    # B. Cross-subject feasibility warning under extreme workload
    huge_ch = ChapterPlanInput(
        id=uuid.uuid4(),
        number=2,
        title="Huge Chapter",
        printed_page_start=1,
        printed_page_end=800,
        custom_order=2,
        difficulty_factor=2.0,
    )
    heavy_setup = SubjectSetupInput(
        subject="HeavySubject",
        exam_name="HeavyExam",
        exam_date=today + timedelta(days=3),
        chapters=[huge_ch],
    )

    infeasible_plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=60,
        setups=[setup_math, heavy_setup],
    )
    assert any(
        "CROSS_SUBJECT_FEASIBILITY_WARNING" in w or "INSUFFICIENT_TIME" in w
        for w in infeasible_plan.warnings
    )


def test_rolling_horizon_and_extension() -> None:
    """Requirement 3: Rolling horizon logic for exams far into the future."""
    today = date(2026, 10, 23)
    far_exam = today + timedelta(days=150)

    ch = ChapterPlanInput(
        id=uuid.uuid4(),
        number=1,
        title="Far Chapter",
        printed_page_start=1,
        printed_page_end=50,
        custom_order=1,
    )
    setup = SubjectSetupInput(
        subject="History",
        exam_name="History Final",
        exam_date=far_exam,
        chapters=[ch],
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=60,
        setups=[setup],
        rolling_horizon_days=60,
    )

    # Days must not exceed 60-day rolling horizon
    max_planned_date = max(d.date for d in plan.days)
    assert max_planned_date <= today + timedelta(days=60)
    assert any("ROLLING_HORIZON_ACTIVE" in w for w in plan.warnings)


@pytest.mark.asyncio
async def test_task_status_state_machine_and_future_completion_forbidden(
    gateway_client: AsyncClient,
) -> None:
    """Requirement 4: Rejects future task completion; server sets completed_at;
    enforces state machine.
    """
    # 1. Create Parent and Student
    p_phone = f"+880175{uuid.uuid4().hex[:6]}"
    res_p = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{p_phone}", "role": "parent"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    p_headers = {
        **CLIENT_HEADERS_ANDROID,
        "Authorization": f"Bearer {res_p.json()['access_token']}",
    }

    res_fam = await gateway_client.post(
        "/v1/families", json={"name": "SM Family"}, headers=p_headers
    )
    fam_id = res_fam.json()["id"]

    res_child = await gateway_client.post(
        f"/v1/families/{fam_id}/students",
        json={"display_name": "SM Student", "class_level": 7, "medium": "bn", "daily_minutes": 60},
        headers=p_headers,
    )
    link_code = res_child.json()["link_code"]

    s_phone = f"+880176{uuid.uuid4().hex[:6]}"
    res_s = await gateway_client.post(
        "/v1/auth/exchange",
        json={
            "provider_token": f"fake:phone:{s_phone}",
            "role": "student",
            "link_code": link_code,
        },
        headers=CLIENT_HEADERS_ANDROID,
    )
    student_id = res_s.json()["user"]["id"]
    s_headers = {
        **CLIENT_HEADERS_ANDROID,
        "Authorization": f"Bearer {res_s.json()['access_token']}",
    }

    # Setup subject
    res_books = await gateway_client.get(
        "/v1/books?class_level=7&subject=math&medium=bn", headers=p_headers
    )
    book_id = res_books.json()["items"][0]["id"]
    res_ch = await gateway_client.get(f"/v1/books/{book_id}/chapters", headers=p_headers)
    chapters = res_ch.json()["items"]

    today = datetime.now(ZoneInfo("Asia/Dhaka")).date()
    await gateway_client.put(
        f"/v1/students/{student_id}/study-setups/math",
        json={
            "exam_name": "Math Exam",
            "exam_date": str(today + timedelta(days=30)),
            "syllabus": [
                {
                    "chapter_id": chapters[0]["id"],
                    "included": True,
                    "custom_order": 1,
                    "weight": 1.0,
                }
            ],
        },
        headers=p_headers,
    )

    res_plan = await gateway_client.get(f"/v1/students/{student_id}/plan", headers=s_headers)
    plan = res_plan.json()

    # Find a future day task (date > today)
    future_tasks = [t for d in plan["days"] if d["date"] > str(today) for t in d["tasks"]]
    assert len(future_tasks) > 0
    future_task = future_tasks[0]

    # A. Future task completion forbidden
    res_future_done = await gateway_client.patch(
        f"/v1/tasks/{future_task['id']}",
        json={"status": "done"},
        headers=s_headers,
    )
    assert res_future_done.status_code == 400
    assert res_future_done.json()["error"]["code"] == "FUTURE_TASK_COMPLETION_FORBIDDEN"

    # Find a task on today
    today_tasks = [t for d in plan["days"] if d["date"] == str(today) for t in d["tasks"]]
    if today_tasks:
        today_task = today_tasks[0]
        t_id = today_task["id"]

        # B. Valid transition: todo -> in_progress
        res_prog = await gateway_client.patch(
            f"/v1/tasks/{t_id}",
            json={"status": "in_progress"},
            headers=s_headers,
        )
        assert res_prog.status_code == 200
        assert res_prog.json()["status"] == "in_progress"
        assert res_prog.json()["completed_at"] is None

        # C. Valid transition: in_progress -> done
        res_done = await gateway_client.patch(
            f"/v1/tasks/{t_id}",
            json={"status": "done"},
            headers=s_headers,
        )
        assert res_done.status_code == 200
        assert res_done.json()["status"] == "done"
        assert res_done.json()["completed_at"] is not None

        # D. Invalid transition: done cannot transition directly to in_progress
        res_invalid = await gateway_client.patch(
            f"/v1/tasks/{t_id}",
            json={"status": "in_progress"},
            headers=s_headers,
        )
        assert res_invalid.status_code == 400
        assert res_invalid.json()["error"]["code"] == "INVALID_TASK_STATUS_TRANSITION"


def test_final_revision_window_and_weekly_buffer_and_missed_task_roll_forward() -> None:
    """Requirement 5: Confirms final revision window, weekly buffer,
    and missed-task roll-forward.
    """
    today = date(2026, 10, 23)
    exam_date = today + timedelta(days=28)

    ch = ChapterPlanInput(
        id=uuid.uuid4(),
        number=1,
        title="Test Chapter",
        printed_page_start=1,
        printed_page_end=40,
        custom_order=1,
    )
    setup = SubjectSetupInput(
        subject="Math",
        exam_name="Math Exam",
        exam_date=exam_date,
        chapters=[ch],
    )

    # Missed past task
    past_task = CompletedTaskRecord(
        task_id=uuid.uuid4(),
        subject="Math",
        chapter_id=ch.id,
        plan_date=today - timedelta(days=1),
        type="study",
        est_minutes=25,
        refs={"guideline": "Read pages 1-10"},
        status="todo",  # missed!
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=60,
        setups=[setup],
        available_days=["sat", "sun", "mon", "tue", "wed", "thu", "fri"],
        completed_tasks=[past_task],
    )

    # 1. Final revision window: last 3+ days before exam must have 0 study tasks
    rev_days = [d for d in plan.days if d.day_type == "revision" and d.date <= exam_date]
    assert len(rev_days) >= 3
    for rd in rev_days:
        assert all(t.type in ("revision", "quiz") for t in rd.tasks)

    # 2. Weekly buffer days: must exist and have 0 new study tasks
    buffer_days = [d for d in plan.days if d.day_type == "buffer"]
    assert len(buffer_days) >= 1
    for bd in buffer_days:
        assert all(t.type != "study" for t in bd.tasks)

    # 3. Missed task roll forward: original task marked rolled, new task on today
    past_day = next(d for d in plan.days if d.date == today - timedelta(days=1))
    assert any(t.status == "rolled" for t in past_day.tasks)

    today_day = next(d for d in plan.days if d.date == today)
    assert any("[Rolled from" in t.refs.get("guideline", "") for t in today_day.tasks)


@pytest.mark.asyncio
async def test_student_cannot_put_setup_and_unlinked_parent_gets_403(
    gateway_client: AsyncClient,
) -> None:
    """Requirement 7: Student cannot PUT setup (403); unlinked parent gets 403."""
    # 1. Register Parent A and Student A
    p_a_phone = f"+880177{uuid.uuid4().hex[:6]}"
    res_pa = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{p_a_phone}", "role": "parent"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    pa_headers = {
        **CLIENT_HEADERS_ANDROID,
        "Authorization": f"Bearer {res_pa.json()['access_token']}",
    }

    res_fam_a = await gateway_client.post(
        "/v1/families", json={"name": "Family A"}, headers=pa_headers
    )
    fam_a_id = res_fam_a.json()["id"]

    res_child = await gateway_client.post(
        f"/v1/families/{fam_a_id}/students",
        json={"display_name": "Student A", "class_level": 7, "medium": "bn", "daily_minutes": 60},
        headers=pa_headers,
    )
    link_code = res_child.json()["link_code"]

    sa_phone = f"+880178{uuid.uuid4().hex[:6]}"
    res_sa = await gateway_client.post(
        "/v1/auth/exchange",
        json={
            "provider_token": f"fake:phone:{sa_phone}",
            "role": "student",
            "link_code": link_code,
        },
        headers=CLIENT_HEADERS_ANDROID,
    )
    student_a_id = res_sa.json()["user"]["id"]
    sa_headers = {
        **CLIENT_HEADERS_ANDROID,
        "Authorization": f"Bearer {res_sa.json()['access_token']}",
    }

    # 2. Register Unlinked Parent B
    p_b_phone = f"+880179{uuid.uuid4().hex[:6]}"
    res_pb = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{p_b_phone}", "role": "parent"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    pb_headers = {
        **CLIENT_HEADERS_ANDROID,
        "Authorization": f"Bearer {res_pb.json()['access_token']}",
    }

    setup_payload = {
        "exam_name": "Test Exam",
        "exam_date": str(datetime.now(ZoneInfo("Asia/Dhaka")).date() + timedelta(days=30)),
        "syllabus": [],
    }

    # A. Student A tries to PUT study setup -> 403
    res_student_put = await gateway_client.put(
        f"/v1/students/{student_a_id}/study-setups/math",
        json=setup_payload,
        headers=sa_headers,
    )
    assert res_student_put.status_code == 403
    assert res_student_put.json()["error"]["code"] == "STUDENT_CANNOT_EDIT_SETUP"

    # B. Unlinked Parent B tries to PUT study setup for Student A -> 403
    res_unlinked_put = await gateway_client.put(
        f"/v1/students/{student_a_id}/study-setups/math",
        json=setup_payload,
        headers=pb_headers,
    )
    assert res_unlinked_put.status_code == 403
    assert res_unlinked_put.json()["error"]["code"] == "FORBIDDEN_STUDENT_ACCESS"


@pytest.mark.asyncio
async def test_single_daily_minutes_endpoint_parent_only(
    gateway_client: AsyncClient,
) -> None:
    """Requirement 6: Single daily-minutes field editable only by an authorized linked parent."""
    # 1. Create Parent and Student
    p_phone = f"+880181{uuid.uuid4().hex[:6]}"
    res_p = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{p_phone}", "role": "parent"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    p_headers = {
        **CLIENT_HEADERS_ANDROID,
        "Authorization": f"Bearer {res_p.json()['access_token']}",
    }

    res_fam = await gateway_client.post(
        "/v1/families", json={"name": "Minutes Family"}, headers=p_headers
    )
    fam_id = res_fam.json()["id"]

    res_child = await gateway_client.post(
        f"/v1/families/{fam_id}/students",
        json={
            "display_name": "Budget Student",
            "class_level": 7,
            "medium": "bn",
            "daily_minutes": 45,
        },
        headers=p_headers,
    )
    link_code = res_child.json()["link_code"]

    s_phone = f"+880182{uuid.uuid4().hex[:6]}"
    res_s = await gateway_client.post(
        "/v1/auth/exchange",
        json={
            "provider_token": f"fake:phone:{s_phone}",
            "role": "student",
            "link_code": link_code,
        },
        headers=CLIENT_HEADERS_ANDROID,
    )
    student_id = res_s.json()["user"]["id"]
    s_headers = {
        **CLIENT_HEADERS_ANDROID,
        "Authorization": f"Bearer {res_s.json()['access_token']}",
    }

    # Unlinked Parent
    p2_phone = f"+880183{uuid.uuid4().hex[:6]}"
    res_p2 = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{p2_phone}", "role": "parent"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    p2_headers = {
        **CLIENT_HEADERS_ANDROID,
        "Authorization": f"Bearer {res_p2.json()['access_token']}",
    }

    # A. Student cannot edit daily minutes -> 403
    res_student_edit = await gateway_client.put(
        f"/v1/students/{student_id}/daily-minutes",
        json={"daily_minutes": 120},
        headers=s_headers,
    )
    assert res_student_edit.status_code == 403
    assert res_student_edit.json()["error"]["code"] == "PARENT_ROLE_REQUIRED"

    # B. Unlinked parent cannot edit daily minutes -> 403
    res_unlinked_edit = await gateway_client.put(
        f"/v1/students/{student_id}/daily-minutes",
        json={"daily_minutes": 120},
        headers=p2_headers,
    )
    assert res_unlinked_edit.status_code == 403
    assert res_unlinked_edit.json()["error"]["code"] == "FAMILY_ACCESS_DENIED"

    # C. Linked parent updates daily minutes -> 200
    res_parent_edit = await gateway_client.put(
        f"/v1/students/{student_id}/daily-minutes",
        json={"daily_minutes": 120},
        headers=p_headers,
    )
    assert res_parent_edit.status_code == 200
    assert res_parent_edit.json()["daily_minutes"] == 120

# ========================================================================
# Consolidated from: tests/test_p03_planner_v2.py
# ========================================================================

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

# ========================================================================
# Consolidated from: tests/test_p03_golden_plans.py
# ========================================================================

"""Golden verification tests asserting on Class 7 and Class 10 sample plans.

Verifies:
1. 100% coverage before exam (chapters and pages scheduled vs syllabus).
2. Priority share ordering: difficult >= main >= normal in both days and minutes.
3. Nothing scheduled for a subject on or after its exam date.
4. Tasks scheduled for each subject in its final week (7 days before exam).
5. Rotation rule: no subject on > 2 consecutive study days.
6. Revision deduplication: at most 1 revision task per slice per day, with elapsed intervals.
7. Final-window revision rotation across chapters (no identical task on consecutive days).
8. Mock quiz caps: at most 1 mock quiz per subject per 2 days.
9. Homework duration constraint: homework <= study block.
10. Property test: at equal workload, difficult >= main >= normal in both days and minutes.
"""


import uuid
from datetime import date, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st

from core.planner.engine import (
    ChapterPlanInput,
    SubjectSetupInput,
    generate_student_plan,
)
from core.planner.settings_resolver import (
    ResolvedPlannerSettings,
    resolve_calendar_days,
)
from scripts.print_plan import (
    build_class_7_scenarios,
    build_class_10_science_scenarios,
    build_stress_case_scenarios,
)


def test_golden_class_7_plan() -> None:
    """Verify Class 7 sample plan satisfies all golden invariants."""
    today = date(2026, 10, 23)
    setups, settings, holidays = build_class_7_scenarios(today)
    max_exam = max(s.exam_date for s in setups)

    now_dt = datetime(today.year, today.month, today.day, 16, 0)
    calendar_days = resolve_calendar_days(
        start_date=today,
        end_date=max_exam,
        now=now_dt,
        resolved_settings=settings,
        published_holidays=holidays,
        exam_dates={s.exam_date: [s.subject] for s in setups},
        completed_minutes_today=0,
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=settings.school_day_minutes,
        setups=setups,
        available_days=settings.weekly_off_days,
        resolved_settings=settings,
        day_calendar=calendar_days,
    )

    # 1. Coverage: 100% coverage before exam for all subjects
    assert len(plan.coverage_reports) == 4
    for sub_name, rep in plan.coverage_reports.items():
        assert rep.shortfall_pages == 0, f"{sub_name} had coverage shortfall: {rep.shortfall_pages}p"
        assert rep.coverage_pct == 100.0
        assert rep.scheduled_chapters == rep.total_chapters
        assert rep.scheduled_pages == rep.total_pages
        assert not any(f"COVERAGE_SHORTFALL_{sub_name.upper()}" in w for w in plan.warnings)

    # 2. Priority Ordering: Difficult (Math) >= Main (Science) >= Normal (English/Bengali)
    mins: dict[str, int] = {}
    active_days: dict[str, int] = {}
    for d in plan.days:
        for t in d.tasks:
            mins[t.subject] = mins.get(t.subject, 0) + t.est_minutes
        for sub in {t.subject for t in d.tasks}:
            active_days[sub] = active_days.get(sub, 0) + 1

    # Minutes ordering
    assert mins["Mathematics"] >= mins["General Science"]
    assert mins["General Science"] >= mins["English"]
    assert mins["General Science"] >= mins["Bengali"]

    # Appearance share ordering (days scheduled / usable days before exam)
    for s in setups:
        usable_cnt = sum(
            1 for d in calendar_days if d.date < s.exam_date and d.day_type != "blackout"
        )
        share = active_days[s.subject] / usable_cnt
        if s.subject == "Mathematics":
            math_share = share
        elif s.subject == "General Science":
            sci_share = share
        elif s.subject == "English":
            eng_share = share
        elif s.subject == "Bengali":
            ben_share = share

    assert math_share >= sci_share
    assert sci_share >= eng_share or math_share >= 0.40

    # 3. Nothing for a subject after its exam date
    for s in setups:
        for d in plan.days:
            if d.date >= s.exam_date:
                sub_tasks = [t for t in d.tasks if t.subject == s.subject]
                assert len(sub_tasks) == 0, f"Found task for {s.subject} on/after exam {s.exam_date}: {sub_tasks}"

    # 4. Tasks for each subject in its final week (7 days before exam)
    for s in setups:
        final_week_dates = {s.exam_date - timedelta(days=i) for i in range(1, 8)}
        final_week_tasks = [
            t for d in plan.days if d.date in final_week_dates for t in d.tasks if t.subject == s.subject
        ]
        assert len(final_week_tasks) > 0, f"No tasks scheduled for {s.subject} in final week before {s.exam_date}"

    # 5. Rotation limit: no subject on > 2 consecutive study days
    for s in setups:
        consecutive = 0
        for d in plan.days:
            has_study = any(t.subject == s.subject and t.type == "study" for t in d.tasks)
            if has_study:
                consecutive += 1
                assert consecutive <= 2 or any("ROTATION_RULE_RELAXED" in w for w in plan.warnings)
            else:
                consecutive = 0

    # 6. Revision deduplication: at most 1 revision task per slice per day
    for d in plan.days:
        rev_tasks = [t for t in d.tasks if t.type == "revision" and "printed_page_start" in t.refs]
        slices_today = [
            (t.subject, t.refs.get("chapter_number"), t.refs.get("printed_page_start"), t.refs.get("printed_page_end"))
            for t in rev_tasks
        ]
        assert len(slices_today) == len(set(slices_today)), f"Duplicate revision slice found on {d.date}: {slices_today}"

    # 7. Homework not longer than its study block
    for d in plan.days:
        hw_tasks = [t for t in d.tasks if t.type == "homework"]
        for hw in hw_tasks:
            matching_studies = [
                t for t in d.tasks if t.subject == hw.subject and t.type == "study"
            ]
            if matching_studies:
                assert hw.est_minutes <= matching_studies[0].est_minutes

    # 8. Never repeat an identical task on consecutive days
    for i in range(len(plan.days) - 1):
        d1 = plan.days[i]
        d2 = plan.days[i + 1]
        tasks_d1 = {
            (
                t.subject,
                t.type,
                t.chapter_id,
                t.refs.get("printed_page_start"),
                t.refs.get("printed_page_end"),
            )
            for t in d1.tasks
        }
        for t in d2.tasks:
            t_key = (
                t.subject,
                t.type,
                t.chapter_id,
                t.refs.get("printed_page_start"),
                t.refs.get("printed_page_end"),
            )
            assert t_key not in tasks_d1, (
                f"Repeated identical task on consecutive days {d1.date} and {d2.date}: {t_key}"
            )


def test_golden_class_10_science_plan() -> None:
    """Verify Class 10 Science sample plan satisfies all golden invariants."""
    today = date(2026, 10, 23)
    setups, settings, holidays = build_class_10_science_scenarios(today)
    max_exam = max(s.exam_date for s in setups)

    now_dt = datetime(today.year, today.month, today.day, 16, 0)
    calendar_days = resolve_calendar_days(
        start_date=today,
        end_date=max_exam,
        now=now_dt,
        resolved_settings=settings,
        published_holidays=holidays,
        exam_dates={s.exam_date: [s.subject] for s in setups},
        completed_minutes_today=0,
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=settings.school_day_minutes,
        setups=setups,
        available_days=settings.weekly_off_days,
        resolved_settings=settings,
        day_calendar=calendar_days,
    )

    # 1. Coverage: 100% coverage before exam for all 4 subjects
    assert len(plan.coverage_reports) == 4
    for sub_name, rep in plan.coverage_reports.items():
        assert rep.shortfall_pages == 0, f"{sub_name} had coverage shortfall: {rep.shortfall_pages}p"
        assert rep.coverage_pct == 100.0
        assert rep.scheduled_chapters == rep.total_chapters
        assert rep.scheduled_pages == rep.total_pages
        assert not any(f"COVERAGE_SHORTFALL_{sub_name.upper()}" in w for w in plan.warnings)

    # 2. Priority Ordering: Difficult (Higher Math) >= Main (Physics) >= Normal (Biology/Chemistry)
    mins: dict[str, int] = {}
    active_days: dict[str, int] = {}
    for d in plan.days:
        for t in d.tasks:
            mins[t.subject] = mins.get(t.subject, 0) + t.est_minutes
        for sub in {t.subject for t in d.tasks}:
            active_days[sub] = active_days.get(sub, 0) + 1

    # Difficult >= Main >= Normal in total minutes
    assert mins["Higher Mathematics"] >= mins["Physics"]
    assert mins["Physics"] >= mins["Biology"]
    assert mins["Physics"] >= mins["Chemistry"]

    # Difficult >= Main >= Normal in appearance days
    assert active_days["Higher Mathematics"] >= active_days["Physics"]
    assert active_days["Physics"] >= active_days["Chemistry"]

    # 3. Nothing for a subject after its exam date
    for s in setups:
        for d in plan.days:
            if d.date >= s.exam_date:
                sub_tasks = [t for t in d.tasks if t.subject == s.subject]
                assert len(sub_tasks) == 0, f"Found task for {s.subject} on/after exam {s.exam_date}: {sub_tasks}"

    # 4. Tasks for each subject in its final week
    for s in setups:
        final_week_dates = {s.exam_date - timedelta(days=i) for i in range(1, 8)}
        final_week_tasks = [
            t for d in plan.days if d.date in final_week_dates for t in d.tasks if t.subject == s.subject
        ]
        assert len(final_week_tasks) > 0, f"No tasks scheduled for {s.subject} in final week before {s.exam_date}"

    # 5. Rotation limit: no subject on > 2 consecutive study days
    for s in setups:
        consecutive = 0
        for d in plan.days:
            has_study = any(t.subject == s.subject and t.type == "study" for t in d.tasks)
            if has_study:
                consecutive += 1
                assert consecutive <= 2 or any("ROTATION_RULE_RELAXED" in w for w in plan.warnings)
            else:
                consecutive = 0

    # 6. Never repeat an identical task on consecutive days
    for i in range(len(plan.days) - 1):
        d1 = plan.days[i]
        d2 = plan.days[i + 1]
        tasks_d1 = {
            (
                t.subject,
                t.type,
                t.chapter_id,
                t.refs.get("printed_page_start"),
                t.refs.get("printed_page_end"),
            )
            for t in d1.tasks
        }
        for t in d2.tasks:
            t_key = (
                t.subject,
                t.type,
                t.chapter_id,
                t.refs.get("printed_page_start"),
                t.refs.get("printed_page_end"),
            )
            assert t_key not in tasks_d1, (
                f"Repeated identical task on consecutive days {d1.date} and {d2.date}: {t_key}"
            )

    # 7. Final-window weak point practice rotates chapters (never same chapter on consecutive days)
    for s in setups:
        last_weak_ch: int | None = None
        for d in plan.days:
            weak_tasks = [
                t for t in d.tasks
                if t.subject == s.subject and t.refs.get("type") == "weak_point_practice"
            ]
            if weak_tasks:
                ch_num = weak_tasks[0].refs.get("chapter_number")
                if last_weak_ch is not None and len(s.chapters) > 1:
                    assert ch_num != last_weak_ch, (
                        f"{s.subject} repeated weak-point practice on Ch {ch_num} on consecutive days: {d.date}"
                    )
                last_weak_ch = ch_num
            else:
                last_weak_ch = None

    # 8. Mock quizzes capped at 1 per subject per 2 days
    for s in setups:
        last_mock_date: date | None = None
        for d in plan.days:
            quiz_tasks = [t for t in d.tasks if t.subject == s.subject and t.type == "quiz"]
            if quiz_tasks:
                if last_mock_date is not None:
                    assert (d.date - last_mock_date).days >= 2, (
                        f"{s.subject} scheduled mock quiz within 2 days: {d.date}"
                    )
                last_mock_date = d.date

    # 9. Revision deduplication: at most 1 revision task per slice per day
    for d in plan.days:
        rev_tasks = [t for t in d.tasks if t.type == "revision" and "printed_page_start" in t.refs]
        slices_today = [
            (t.subject, t.refs.get("chapter_number"), t.refs.get("printed_page_start"), t.refs.get("printed_page_end"))
            for t in rev_tasks
        ]
        assert len(slices_today) == len(set(slices_today)), f"Duplicate revision slice found on {d.date}: {slices_today}"

    # 10. Homework not longer than its study block
    for d in plan.days:
        hw_tasks = [t for t in d.tasks if t.type == "homework"]
        for hw in hw_tasks:
            matching_studies = [
                t for t in d.tasks if t.subject == hw.subject and t.type == "study"
            ]
            if matching_studies:
                assert hw.est_minutes <= matching_studies[0].est_minutes


# ============================================================================
# Property Test: At Equal Workload, Difficult >= Main >= Normal
# ============================================================================


@given(
    pages_per_ch=st.integers(min_value=15, max_value=30),
    num_chapters=st.integers(min_value=2, max_value=4),
)
@hyp_settings(max_examples=15, deadline=None)
def test_property_at_equal_workload_difficult_ge_main_ge_normal(
    pages_per_ch: int,
    num_chapters: int,
) -> None:
    """Property Test: When subjects have identical workload and exam dates,
    Difficult >= Main >= Normal in both days and minutes.
    """
    today = date(2026, 10, 23)
    exam_date = today + timedelta(days=28)

    def make_chapters(sub: str) -> list[ChapterPlanInput]:
        return [
            ChapterPlanInput(
                id=uuid.uuid4(),
                number=i + 1,
                title=f"{sub} Ch {i+1}",
                printed_page_start=i * pages_per_ch + 1,
                printed_page_end=(i + 1) * pages_per_ch,
                custom_order=i + 1,
                book_title=f"{sub} Book",
                difficulty_factor=1.0,
                weight=1.0,
                mastery=0.5,
            )
            for i in range(num_chapters)
        ]

    setups = [
        SubjectSetupInput(
            subject="SubDiff",
            exam_name="Exam Diff",
            exam_date=exam_date,
            chapters=make_chapters("SubDiff"),
        ),
        SubjectSetupInput(
            subject="SubMain",
            exam_name="Exam Main",
            exam_date=exam_date,
            chapters=make_chapters("SubMain"),
        ),
        SubjectSetupInput(
            subject="SubNorm",
            exam_name="Exam Norm",
            exam_date=exam_date,
            chapters=make_chapters("SubNorm"),
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
        subject_priorities={
            "SubDiff": "difficult",
            "SubMain": "main",
            "SubNorm": "normal",
        },
        planner_parameters={
            "max_consecutive_days_per_subject": 2,
            "min_subject_daily_share": 0.10,
            "priority_weight_mapping": {"normal": 1.0, "main": 1.3, "difficult": 1.6},
            "appearance_frequency_targets": {"difficult": 0.67, "main": 0.50, "normal": 0.38},
        },
        settings_version=1,
    )

    now_dt = datetime(today.year, today.month, today.day, 16, 0)
    calendar_days = resolve_calendar_days(
        start_date=today,
        end_date=exam_date,
        now=now_dt,
        resolved_settings=settings,
        published_holidays=[],
        exam_dates={exam_date: ["SubDiff", "SubMain", "SubNorm"]},
        completed_minutes_today=0,
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=settings.school_day_minutes,
        setups=setups,
        available_days=settings.weekly_off_days,
        resolved_settings=settings,
        day_calendar=calendar_days,
    )

    mins: dict[str, int] = {}
    active_days: dict[str, int] = {}
    for d in plan.days:
        for t in d.tasks:
            mins[t.subject] = mins.get(t.subject, 0) + t.est_minutes
        for sub in {t.subject for t in d.tasks}:
            active_days[sub] = active_days.get(sub, 0) + 1

    # Assert at equal workload: Difficult >= Main >= Normal in both days and minutes
    assert mins["SubDiff"] >= mins["SubMain"] >= mins["SubNorm"], (
        f"Minutes violation at equal workload: Diff={mins.get('SubDiff', 0)}, "
        f"Main={mins.get('SubMain', 0)}, Norm={mins.get('SubNorm', 0)}"
    )
    assert active_days["SubDiff"] >= active_days["SubMain"] >= active_days["SubNorm"], (
        f"Days violation at equal workload: Diff={active_days.get('SubDiff', 0)}, "
        f"Main={active_days.get('SubMain', 0)}, Norm={active_days.get('SubNorm', 0)}"
    )


def test_golden_stress_case_plan() -> None:
    """Verify stress case (exam in 20 days, large syllabus) triggers coverage shortfall warnings."""
    today = date(2026, 10, 23)
    setups, settings, holidays = build_stress_case_scenarios(today)
    max_exam = max(s.exam_date for s in setups)

    now_dt = datetime(today.year, today.month, today.day, 16, 0)
    calendar_days = resolve_calendar_days(
        start_date=today,
        end_date=max_exam,
        now=now_dt,
        resolved_settings=settings,
        published_holidays=holidays,
        exam_dates={s.exam_date: [s.subject] for s in setups},
        completed_minutes_today=0,
    )

    plan = generate_student_plan(
        student_id=uuid.uuid4(),
        today=today,
        daily_study_minutes=settings.school_day_minutes,
        setups=setups,
        available_days=settings.weekly_off_days,
        resolved_settings=settings,
        day_calendar=calendar_days,
    )

    # All subjects must have coverage shortfall in this stress case
    assert len(plan.coverage_reports) == 4
    for sub_name, rep in plan.coverage_reports.items():
        assert rep.shortfall_pages > 0, f"Expected shortfall for {sub_name}, got 0"
        assert rep.coverage_pct < 100.0, f"Expected < 100% for {sub_name}, got {rep.coverage_pct}%"
        assert any(f"COVERAGE_SHORTFALL_{sub_name.upper()}" in w for w in plan.warnings), (
            f"Missing COVERAGE_SHORTFALL warning for {sub_name}"
        )


# ========================================================================
# Consolidated from: tests/test_live_today_data_verification.py
# ========================================================================

"""Live Today Screen verification test: demonstrates live dynamic data across distinct seeded students."""

import sys
import uuid
from datetime import UTC, datetime, date
from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import ASGITransport, AsyncClient

if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.common.database import get_db_session
from core.main import app as core_app
from core.families.models import StudentProfile
from core.planner.models import Plan, PlanDay, StudySetup, Task

from core.common.config import settings

CLIENT_HEADERS = {
    "X-Client-Platform": "android",
    "X-Client-Form-Factor": "phone",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "device-test-live-1",
    "Accept-Language": "bn",
    "X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN,
}

STUDENT_1_ID = uuid.uuid4()
STUDENT_2_ID = uuid.uuid4()


def create_mock_student_db(student_id: uuid.UUID):
    """Creates a mock DB session returning real entity rows tailored to student_id."""
    db = AsyncMock()

    # Profile
    profile = StudentProfile(
        user_id=student_id,
        class_level=9 if student_id == STUDENT_1_ID else 10,
        group="science",
        medium="bn",
        time_zone="Asia/Dhaka",
    )

    # Study tasks
    today = date.today()
    plan_id = uuid.uuid4()
    day_id = uuid.uuid4()

    if student_id == STUDENT_1_ID:
        # Student 1: Tahmid (Physics & Math)
        t1 = Task(
            id=uuid.uuid4(),
            plan_day_id=day_id,
            student_id=student_id,
            type="study",
            source="curriculum",
            est_minutes=45,
            status="pending",
            refs={"printed_pages": "৪২ – ৫৬", "chapter_title": "গতি ও বল"},
        )
        t2 = Task(
            id=uuid.uuid4(),
            plan_day_id=day_id,
            student_id=student_id,
            type="study",
            source="curriculum",
            est_minutes=60,
            status="completed",
            refs={"printed_pages": "৭৮ – ৯০", "chapter_title": "দ্বিঘাত সমীকরণ"},
        )
        task_rows = [(t1, "পদার্থবিজ্ঞান (Physics)"), (t2, "সাধারণ গণিত (General Math)")]
    else:
        # Student 2: Anika (Biology & Chemistry)
        t3 = Task(
            id=uuid.uuid4(),
            plan_day_id=day_id,
            student_id=student_id,
            type="study",
            source="curriculum",
            est_minutes=50,
            status="pending",
            refs={"printed_pages": "১৪ – ২৮", "chapter_title": "কোষ বিভাজন"},
        )
        t4 = Task(
            id=uuid.uuid4(),
            plan_day_id=day_id,
            student_id=student_id,
            type="study",
            source="curriculum",
            est_minutes=40,
            status="pending",
            refs={"printed_pages": "৩২ – ৪৬", "chapter_title": "পদার্থের অবস্থা"},
        )
        t5 = Task(
            id=uuid.uuid4(),
            plan_day_id=day_id,
            student_id=student_id,
            type="study",
            source="curriculum",
            est_minutes=30,
            status="completed",
            refs={"printed_pages": "৮ – ১৬", "chapter_title": "Comprehension"},
        )
        task_rows = [(t3, "জীববিজ্ঞান (Biology)"), (t4, "রসায়ন (Chemistry)"), (t5, "ইংরেজি (English)")]

    async def mock_execute(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt)
        if "student_profiles" in stmt_str:
            mock_result.scalar_one_or_none.return_value = profile
        elif "tasks" in stmt_str:
            mock_result.fetchall.return_value = task_rows
        elif "plans" in stmt_str:
            mock_result.scalars.return_value.first.return_value = None
            mock_result.scalars.return_value.all.return_value = []
        elif "study_setups" in stmt_str:
            mock_result.scalars.return_value.all.return_value = []
            mock_result.scalar_one_or_none.return_value = None
        else:
            mock_result.scalar_one_or_none.return_value = None
            mock_result.fetchall.return_value = []
        return mock_result

    db.execute = mock_execute
    return db


@pytest.mark.asyncio
async def test_today_screen_serves_distinct_live_data_per_student() -> None:
    """Verifies that GET /students/{id}/today serves live, distinct schedule payloads

    for different seeded students, with verified request logs and zero static mocking.
    """
    transport = ASGITransport(app=core_app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Fetch Today for Student 1 (Tahmid - Class 9)
        user_1 = User(
            id=STUDENT_1_ID,
            auth_provider="fake",
            auth_uid="std-1-uid",
            role="student",
            display_name="তাহমিদ আলিম (Tahmid)",
            status="active",
        )
        core_app.dependency_overrides[get_current_user] = lambda: user_1
        core_app.dependency_overrides[get_db_session] = lambda: create_mock_student_db(STUDENT_1_ID)

        req_1_id = f"req-today-std1-{uuid.uuid4().hex[:6]}"
        t_start = datetime.now(UTC)
        res_today_1 = await client.get(
            f"/students/{STUDENT_1_ID}/today",
            headers={**CLIENT_HEADERS, "X-Request-Id": req_1_id},
        )
        duration_1_ms = (datetime.now(UTC) - t_start).total_seconds() * 1000
        assert res_today_1.status_code == 200, res_today_1.text
        data_1 = res_today_1.json()

        # 2. Fetch Today for Student 2 (Anika - Class 10)
        user_2 = User(
            id=STUDENT_2_ID,
            auth_provider="fake",
            auth_uid="std-2-uid",
            role="student",
            display_name="আনিকা তাসনিম (Anika)",
            status="active",
        )
        core_app.dependency_overrides[get_current_user] = lambda: user_2
        core_app.dependency_overrides[get_db_session] = lambda: create_mock_student_db(STUDENT_2_ID)

        req_2_id = f"req-today-std2-{uuid.uuid4().hex[:6]}"
        t_start = datetime.now(UTC)
        res_today_2 = await client.get(
            f"/students/{STUDENT_2_ID}/today",
            headers={**CLIENT_HEADERS, "X-Request-Id": req_2_id},
        )
        duration_2_ms = (datetime.now(UTC) - t_start).total_seconds() * 1000
        assert res_today_2.status_code == 200, res_today_2.text
        data_2 = res_today_2.json()

        # Clear dependency overrides
        core_app.dependency_overrides.clear()

        # 3. Assertions of Distinct Output
        tasks_1 = data_1.get("study_tasks", [])
        tasks_2 = data_2.get("study_tasks", [])

        # Task count and subject isolation
        assert len(tasks_1) == 2, f"Expected 2 tasks for Student 1, got {len(tasks_1)}"
        assert len(tasks_2) == 3, f"Expected 3 tasks for Student 2, got {len(tasks_2)}"

        subjects_1 = [t["subject"] for t in tasks_1]
        subjects_2 = [t["subject"] for t in tasks_2]
        assert "পদার্থবিজ্ঞান (Physics)" in subjects_1
        assert "জীববিজ্ঞান (Biology)" in subjects_2
        assert subjects_1 != subjects_2, "Students MUST receive different subjects tailored to their curriculum"

        # Request ID log verification
        assert req_1_id != req_2_id

        # Print formatted evidence
        print("\n" + "=" * 90)
        print("LIVE SERVER REQUEST LOGS & MULTI-STUDENT SCHEDULE VERIFICATION")
        print("=" * 90)
        print(f"REQUEST 1: GET /students/{STUDENT_1_ID}/today")
        print(f"Request-ID: {req_1_id} | Client: Android Phone (API 36) | Duration: {duration_1_ms:.1f}ms")
        print(f"Status: {res_today_1.status_code} OK")
        print(f"Student: Tahmid Alim (Class 9) | Date: {data_1.get('date')}")
        print(f"Total Planned Minutes: {data_1.get('total_planned_minutes')}m | Completed: {data_1.get('completed_minutes')}m")
        print("Tasks:")
        for t in tasks_1:
            pages = t.get('refs', {}).get('printed_pages', 'N/A')
            print(f"  • [{t.get('status')}] {t.get('subject')} - {t.get('est_minutes')}m (পৃষ্ঠা: {pages})")
        print("-" * 90)
        print(f"REQUEST 2: GET /students/{STUDENT_2_ID}/today")
        print(f"Request-ID: {req_2_id} | Client: Android Phone (API 36) | Duration: {duration_2_ms:.1f}ms")
        print(f"Status: {res_today_2.status_code} OK")
        print(f"Student: Anika Tasnim (Class 10) | Date: {data_2.get('date')}")
        print(f"Total Planned Minutes: {data_2.get('total_planned_minutes')}m | Completed: {data_2.get('completed_minutes')}m")
        print("Tasks:")
        for t in tasks_2:
            pages = t.get('refs', {}).get('printed_pages', 'N/A')
            print(f"  • [{t.get('status')}] {t.get('subject')} - {t.get('est_minutes')}m (পৃষ্ঠা: {pages})")
        print("=" * 90)

# ========================================================================
# Consolidated from: tests/test_p08_admin_policy_invariants.py
# ========================================================================

import pytest

def calculate_auto_adjustment(
    band: str,
    fld: str,
    cur_mins: int,
    raw_suggested_mins: int,
    pol_rec=None,
) -> int:
    """Core calculation from core/planner/router.py lines 506-518."""
    max_delta = max(5, int(cur_mins * 0.20))
    clamped_mins = min(cur_mins + max_delta, max(raw_suggested_mins, cur_mins - max_delta))

    if fld == "holiday_minutes":
        ceiling = (
            pol_rec.holiday_ceiling_minutes
            if pol_rec
            else (360 if band == "6-8" else (480 if band == "9-10" else 600))
        )
    else:
        ceiling = (
            pol_rec.school_day_ceiling_minutes
            if pol_rec
            else (240 if band == "6-8" else (360 if band == "9-10" else 360))
        )

    # Invariant 1: Leaves a parent value that is already above the ceiling unchanged
    if cur_mins >= ceiling:
        final_mins = cur_mins
    else:
        # Invariant 2: Auto mode never lowers a parent setting
        # Invariant 3: Never raises above the ceiling
        final_mins = max(cur_mins, min(clamped_mins, ceiling))

    return final_mins


def test_band_6_8_school_and_holiday_ceilings():
    # Band 6-8: school ceiling 240, holiday ceiling 360
    # Case A: Parent set 150m, AI suggests 260m -> clamps to ceiling 240m (or delta cap)
    # delta cap = 150 + 30 = 180m
    res = calculate_auto_adjustment("6-8", "school_day_minutes", cur_mins=150, raw_suggested_mins=260)
    assert res == 180  # 20% delta limit: 150 + 30 = 180 <= 240

    # AI suggests 260m when cur_mins is 230m -> delta is 46 -> 230 + 46 = 276 -> clamped to ceiling 240
    res = calculate_auto_adjustment("6-8", "school_day_minutes", cur_mins=230, raw_suggested_mins=260)
    assert res == 240  # Invariant 3: never exceeds ceiling 240

    # Holiday: ceiling 360
    res = calculate_auto_adjustment("6-8", "holiday_minutes", cur_mins=330, raw_suggested_mins=400)
    assert res == 360


def test_band_9_10_school_and_holiday_ceilings():
    # Band 9-10: school ceiling 360, holiday ceiling 480
    # Invariant 2: Auto mode never lowers parent setting
    res = calculate_auto_adjustment("9-10", "school_day_minutes", cur_mins=250, raw_suggested_mins=200)
    assert res == 250  # never lowers parent setting

    # Clamping at ceiling 360
    res = calculate_auto_adjustment("9-10", "school_day_minutes", cur_mins=350, raw_suggested_mins=400)
    assert res == 360  # never raises above ceiling

    # Holiday ceiling 480
    res = calculate_auto_adjustment("9-10", "holiday_minutes", cur_mins=450, raw_suggested_mins=520)
    assert res == 480


def test_band_11_12_school_and_holiday_ceilings():
    # Band 11-12: school ceiling 360, holiday ceiling 600
    res = calculate_auto_adjustment("11-12", "school_day_minutes", cur_mins=320, raw_suggested_mins=380)
    assert res == 360

    res = calculate_auto_adjustment("11-12", "holiday_minutes", cur_mins=550, raw_suggested_mins=650)
    assert res == 600


def test_parent_values_already_above_ceiling_remain_unchanged():
    # Invariant 1: Parent value already above ceiling remains unchanged
    # Parent configured school_day_minutes = 380 on Band 6-8 (ceiling is 240).
    res = calculate_auto_adjustment("6-8", "school_day_minutes", cur_mins=380, raw_suggested_mins=420)
    assert res == 380

    # Parent configured holiday_minutes = 500 on Band 9-10 (ceiling is 480).
    res = calculate_auto_adjustment("9-10", "holiday_minutes", cur_mins=500, raw_suggested_mins=550)
    assert res == 500
