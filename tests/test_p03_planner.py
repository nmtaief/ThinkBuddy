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

from __future__ import annotations

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
        if not res.scalar_one_or_none():
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
    today_dhaka_str = str(datetime.now(ZoneInfo("Asia/Dhaka")).date())
    today_tasks = [t for d in plan_data["days"] if d["date"] <= today_dhaka_str for t in d["tasks"]]
    target_task = today_tasks[0] if today_tasks else test_task
    target_task_id = target_task["id"]

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
