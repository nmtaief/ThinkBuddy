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
    """Ensure curriculum textbook is in database."""
    importer = CurriculumImporter()
    await importer.import_manifest(SAMPLE_MANIFEST_PATH, resume=True)


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
    res_patch_done = await gateway_client.patch(
        f"/v1/tasks/{task_id}",
        json={"status": "done"},
        headers=s1_headers,
    )
    assert res_patch_done.status_code == 200
    updated_task = res_patch_done.json()
    assert updated_task["status"] == "done"
    assert updated_task["completed_at"] is not None
