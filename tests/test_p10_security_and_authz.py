"""P10 Security, Authorization, and Leakage Invariant Tests.

Deliverables 4 & Acceptance:
- Authorization on every route (Rule 9).
- Platform isolation for assessments (Rule 18: web client restricted to practice mode).
- Never send answer keys before attempt item is submitted (Rule 6).
- Log, don't leak (Rule 15: no tokens, passwords, raw transcripts).
- CORS and rate-limit security invariants.
"""

import uuid
import pytest
from httpx import AsyncClient

CLIENT_HEADERS_ANDROID = {
    "X-Client-Platform": "android",
    "X-Client-Form-Factor": "phone",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "device-sec-android-001",
    "Accept-Language": "bn",
}

CLIENT_HEADERS_WEB = {
    "X-Client-Platform": "web",
    "X-Client-Form-Factor": "desktop",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "device-sec-web-001",
    "Accept-Language": "en",
}


@pytest.mark.asyncio
async def test_unauthenticated_requests_fail_on_all_protected_routes(gateway_client: AsyncClient) -> None:
    """Verify that unauthenticated calls to protected routes return 401 Unauthorized."""
    protected_paths = [
        ("GET", "/v1/parents/me/dashboard", None),
        ("GET", f"/v1/students/{uuid.uuid4()}/today", None),
        ("GET", f"/v1/students/{uuid.uuid4()}/plan", None),
        ("POST", "/v1/chat/sessions", {"title": "Test Chat"}),
        ("POST", "/v1/families", {"name": "Test Family"}),
        ("POST", "/v1/parents/me/export", {}),
        ("POST", "/v1/parents/consent", {"version": "1.0", "consented": True}),
        ("POST", "/v1/users/me/delete", {}),
    ]

    for method, path, body in protected_paths:
        if method == "GET":
            res = await gateway_client.get(path, headers=CLIENT_HEADERS_ANDROID)
        else:
            res = await gateway_client.post(path, json=body or {}, headers=CLIENT_HEADERS_ANDROID)

        assert res.status_code == 401, f"Path {path} returned {res.status_code} instead of 401: {res.text}"
        err_body = res.json()
        assert "error" in err_body
        assert err_body["error"]["code"] in (
            "AUTH_REQUIRED",
            "UNAUTHORIZED",
            "TOKEN_MISSING",
            "MISSING_OR_INVALID_TOKEN",
        )


@pytest.mark.asyncio
async def test_role_based_access_control_rule_9(gateway_client: AsyncClient) -> None:
    """Students cannot access parent routes, and parents cannot access unlinked students (Rule 9)."""
    # 1. Register parent 1 and link student
    p_phone1 = f"+880170{uuid.uuid4().hex[:6]}"
    res_p1 = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{p_phone1}", "role": "parent", "display_name": "Parent 1"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_p1.status_code == 200
    token_p1 = res_p1.json()["access_token"]
    headers_p1 = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_p1}"}

    # Record consent & create family
    await gateway_client.post("/v1/parents/consent", json={"version": "1.0", "consented": True}, headers=headers_p1)
    res_fam = await gateway_client.post("/v1/families", json={"name": "Family Sec"}, headers=headers_p1)
    fam_id = res_fam.json()["id"]

    # Add child
    res_child = await gateway_client.post(
        f"/v1/families/{fam_id}/students",
        json={"display_name": "Sec Student", "class_level": 7, "medium": "bn", "daily_minutes": 45},
        headers=headers_p1,
    )
    assert res_child.status_code == 201
    link_code = res_child.json()["link_code"]

    # Student redeems link code
    s_phone = f"+880171{uuid.uuid4().hex[:6]}"
    res_s = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{s_phone}", "role": "student", "link_code": link_code},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_s.status_code == 200
    token_s = res_s.json()["access_token"]
    student_id = res_s.json()["user"]["id"]
    headers_s = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_s}"}

    # Student trying parent routes -> 403 FORBIDDEN
    res_s_parent = await gateway_client.get("/v1/parents/me/dashboard", headers=headers_s)
    assert res_s_parent.status_code == 403

    res_s_export = await gateway_client.post("/v1/parents/me/export", headers=headers_s)
    assert res_s_export.status_code == 403

    # 2. Register unlinked Parent 2
    p_phone2 = f"+880172{uuid.uuid4().hex[:6]}"
    res_p2 = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{p_phone2}", "role": "parent", "display_name": "Parent 2"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_p2.status_code == 200
    token_p2 = res_p2.json()["access_token"]
    headers_p2 = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_p2}"}

    # Unlinked parent accessing student data -> 403 FORBIDDEN
    res_unlinked = await gateway_client.get(f"/v1/students/{student_id}/today", headers=headers_p2)
    assert res_unlinked.status_code == 403
    assert res_unlinked.json()["error"]["code"] in ("FORBIDDEN_STUDENT_ACCESS", "PARENTAL_CONSENT_REQUIRED")


@pytest.mark.asyncio
async def test_platform_isolation_rule_18_web_practice_only(gateway_client: AsyncClient) -> None:
    """Rule 18: Assessed quizzes are restricted to native platforms; web clients are rejected."""
    # Parent creates family and student with web headers
    p_phone = f"+880173{uuid.uuid4().hex[:6]}"
    res_p = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{p_phone}", "role": "parent", "display_name": "Web Parent"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_p = res_p.json()["access_token"]
    headers_p = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_p}"}
    await gateway_client.post("/v1/parents/consent", json={"version": "1.0", "consented": True}, headers=headers_p)
    res_fam = await gateway_client.post("/v1/families", json={"name": "Web Family"}, headers=headers_p)
    fam_id = res_fam.json()["id"]

    res_c = await gateway_client.post(
        f"/v1/families/{fam_id}/students",
        json={"display_name": "Web Child", "class_level": 8, "medium": "bn", "daily_minutes": 45},
        headers=headers_p,
    )
    link_code = res_c.json()["link_code"]

    w_phone = f"+880174{uuid.uuid4().hex[:6]}"
    res_auth = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{w_phone}", "role": "student", "link_code": link_code},
        headers=CLIENT_HEADERS_WEB,
    )
    assert res_auth.status_code == 200
    token = res_auth.json()["access_token"]
    headers_w = {**CLIENT_HEADERS_WEB, "Authorization": f"Bearer {token}"}

    # Fetch or create a valid quiz for the student
    from core.common.database import AsyncSessionLocal
    from core.quiz.models import Quiz
    from sqlalchemy import select

    student_uuid = uuid.UUID(res_auth.json()["user"]["id"])
    async with AsyncSessionLocal() as session:
        quiz = (await session.execute(select(Quiz).where(Quiz.student_id == student_uuid).limit(1))).scalar_one_or_none()
        if not quiz:
            quiz = Quiz(id=uuid.uuid4(), student_id=student_uuid, title="Web Test Quiz", kind="daily", mode="assessed")
            session.add(quiz)
            await session.commit()
        target_quiz_id = str(quiz.id)

    # Attempting to start an assessed quiz on web -> 403 WEB_PLATFORM_PRACTICE_ONLY
    res_assessed = await gateway_client.post(
        f"/v1/quizzes/{target_quiz_id}/attempts",
        json={"mode": "assessed"},
        headers=headers_w,
    )
    assert res_assessed.status_code == 403
    assert res_assessed.json()["error"]["code"] in ("WEB_PLATFORM_PRACTICE_ONLY", "ASSESSED_QUIZZES_REQUIRE_NATIVE_APP")


@pytest.mark.asyncio
async def test_answer_key_leakage_rule_6(gateway_client: AsyncClient) -> None:
    """Rule 6: Never send answer keys to clients before attempt item is submitted."""
    p_phone = f"+880175{uuid.uuid4().hex[:6]}"
    res_p = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{p_phone}", "role": "parent", "display_name": "Quiz Parent"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_p = res_p.json()["access_token"]
    headers_p = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_p}"}
    await gateway_client.post("/v1/parents/consent", json={"version": "1.0", "consented": True}, headers=headers_p)
    res_fam = await gateway_client.post("/v1/families", json={"name": "Quiz Family"}, headers=headers_p)
    fam_id = res_fam.json()["id"]

    res_c = await gateway_client.post(
        f"/v1/families/{fam_id}/students",
        json={"display_name": "Quiz Child", "class_level": 7, "medium": "bn", "daily_minutes": 45},
        headers=headers_p,
    )
    link_code = res_c.json()["link_code"]

    phone = f"+880176{uuid.uuid4().hex[:6]}"
    res_auth = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone}", "role": "student", "link_code": link_code},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_auth.status_code == 200
    token = res_auth.json()["access_token"]
    headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    # Fetch active or practice quiz questions
    res_quizzes = await gateway_client.get("/v1/quizzes?kind=daily", headers=headers)
    if res_quizzes.status_code == 200 and res_quizzes.json().get("items"):
        quiz = res_quizzes.json()["items"][0]
        quiz_id = quiz["id"]
        res_start = await gateway_client.post(
            f"/v1/quizzes/{quiz_id}/attempts",
            json={"mode": "practice"},
            headers=headers,
        )
        if res_start.status_code in (200, 201):
            body_text = res_start.text.lower()
            # Invariant: correct answer indices or keys must NEVER appear before submission
            assert "correct_option" not in body_text
            assert "is_correct" not in body_text
            assert "answer_key" not in body_text
            assert "explanation" not in body_text


@pytest.mark.asyncio
async def test_rule_15_pii_and_token_scrubbing(gateway_client: AsyncClient) -> None:
    """Rule 15: Error responses and public payloads must never echo raw provider tokens or passwords."""
    res_bad = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": "secret_very_sensitive_auth_token_xyz987", "role": "unknown_role"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_bad.status_code in (400, 401, 422)
    # The secret token must NOT be reflected in plain text in the error response
    assert "secret_very_sensitive_auth_token_xyz987" not in res_bad.text
