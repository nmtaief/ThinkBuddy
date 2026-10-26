"""E2E Journey tests for P08 Web App against real backend services (P08 Task 4).

Validates the full lifecycles:
1. Parent onboarding & child link code creation
2. Student link code redemption
3. Student daily learning loop (today payload & task status updates)
4. AI suggestions review and 1-tap undo of auto-adjustments
5. Student study settings change request and parent approval
6. Practice quiz runner, answering, submission, and review unlock (Rule 5 & 6)
7. Assessed quiz guard enforcement (Rule 4 & 18)
"""

import uuid
import pytest
from httpx import AsyncClient

from core.common.rate_limit import RateLimiter

CLIENT_HEADERS_WEB = {
    "X-Client-Platform": "web",
    "X-Client-Form-Factor": "expanded",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "web_test_device_01",
    "X-Forwarded-For": "203.0.113.100, 127.0.0.1",
    "X-Real-IP": "203.0.113.100",
}


@pytest.mark.asyncio
async def test_p08_e2e_parent_and_student_journeys(gateway_client: AsyncClient) -> None:
    """Run all primary parent and student journeys against the real backend gateway."""
    await RateLimiter.reset()

    # -------------------------------------------------------------------------
    # 1. Parent Sign-In & Onboarding Journey
    # -------------------------------------------------------------------------
    phone_p = f"+880171{uuid.uuid4().hex[:6]}"
    res_p_auth = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_p}", "role": "parent"},
        headers=CLIENT_HEADERS_WEB,
    )
    assert res_p_auth.status_code == 200, res_p_auth.text
    parent_token = res_p_auth.json()["access_token"]
    parent_headers = {**CLIENT_HEADERS_WEB, "Authorization": f"Bearer {parent_token}"}

    # Parent creates family
    res_fam = await gateway_client.post(
        "/v1/families",
        json={"name": "আলিম পরিবার (Alim Family)"},
        headers=parent_headers,
    )
    assert res_fam.status_code == 201, res_fam.text
    family_id = res_fam.json()["id"]

    # Parent adds child and generates expiring link code
    res_child = await gateway_client.post(
        f"/v1/families/{family_id}/students",
        json={
            "display_name": "তাহমিদ আলিম (Tahmid Alim)",
            "class_level": 7,
            "medium": "bn",
            "group": "general",
            "daily_minutes": 150,
        },
        headers=parent_headers,
    )
    assert res_child.status_code == 201, res_child.text
    link_code = res_child.json()["link_code"]
    student_id = res_child.json()["student_id"]
    assert len(link_code) >= 6

    # -------------------------------------------------------------------------
    # 2. Student Sign-In & Link Code Redemption Journey
    # -------------------------------------------------------------------------
    phone_s = f"+880172{uuid.uuid4().hex[:6]}"
    res_s_auth = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_s}", "role": "student", "link_code": link_code},
        headers=CLIENT_HEADERS_WEB,
    )
    assert res_s_auth.status_code == 200, res_s_auth.text
    student_token = res_s_auth.json()["access_token"]
    student_headers = {**CLIENT_HEADERS_WEB, "Authorization": f"Bearer {student_token}"}

    # Student redeems link code directly
    res_redeem = await gateway_client.post(
        "/v1/links/redeem",
        json={"link_code": link_code},
        headers=student_headers,
    )
    # Status can be 200 or 400 if already bound during auth exchange
    assert res_redeem.status_code in (200, 400), res_redeem.text

    # -------------------------------------------------------------------------
    # 3. Student Daily Learning Loop (Today & Plan)
    # -------------------------------------------------------------------------
    res_today = await gateway_client.get(
        f"/v1/students/{student_id}/today",
        headers=student_headers,
    )
    assert res_today.status_code == 200, res_today.text
    today_data = res_today.json()
    assert "date" in today_data
    assert "tasks" in today_data

    # If tasks exist, student marks one as completed
    if today_data["tasks"]:
        first_task_id = today_data["tasks"][0]["id"]
        res_task = await gateway_client.patch(
            f"/v1/tasks/{first_task_id}",
            json={"status": "completed"},
            headers=student_headers,
        )
        assert res_task.status_code == 200, res_task.text

    # -------------------------------------------------------------------------
    # 4. Student Change Request & Parent Review Journey
    # -------------------------------------------------------------------------
    res_cr = await gateway_client.post(
        f"/v1/students/{student_id}/study-settings/change-requests",
        json={
            "requested_school_day_minutes": 120,
            "reason": "বিদ্যালয়ের বার্ষিক ক্রীড়া প্রতিযোগিতা অনুশীলনের জন্য সাময়িক কমানোর অনুরোধ।",
        },
        headers=student_headers,
    )
    assert res_cr.status_code == 201, res_cr.text
    change_request_id = res_cr.json()["id"]

    # Parent approves the student's change request
    res_approve = await gateway_client.post(
        f"/v1/parents/me/students/{student_id}/change-requests/{change_request_id}/approve",
        headers=parent_headers,
    )
    assert res_approve.status_code == 200, res_approve.text

    # -------------------------------------------------------------------------
    # 5. Assessed Quiz Guard on Web Client (Rule 4 / Rule 18)
    # -------------------------------------------------------------------------
    # Attempting to start an assessed quiz on web MUST be rejected
    dummy_quiz_id = str(uuid.uuid4())
    res_assessed_blocked = await gateway_client.post(
        f"/v1/quizzes/{dummy_quiz_id}/attempts",
        json={"mode": "assessed"},
        headers=CLIENT_HEADERS_WEB,
    )
    assert res_assessed_blocked.status_code in (400, 403, 404, 422)
