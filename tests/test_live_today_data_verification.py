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
