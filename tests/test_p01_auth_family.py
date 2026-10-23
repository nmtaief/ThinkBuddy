"""Acceptance and integration tests for P01: Auth, Roles, Family Linking, Devices, Client Config.

Verifies:
1. Client headers middleware enforcement
2. Platform-differentiated client config (quiz_security_mode android vs web)
3. Auth token exchange, JWT issuance, and rotating hashed refresh tokens
4. Parent can read only linked children
5. Revoked link immediately blocks access
6. Student cannot read other students' data
7. Teacher routes return 403/404 while feature flag is disabled
8. Brute-force rate limiting on link code redemption
9. Full Bangla/English Unicode fidelity
10. Device registration and updates
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from httpx import AsyncClient

if TYPE_CHECKING:
    pass

CLIENT_HEADERS_ANDROID = {
    "X-Client-Platform": "android",
    "X-Client-Form-Factor": "phone",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "device-test-android-001",
    "Accept-Language": "bn",
}

CLIENT_HEADERS_WEB = {
    "X-Client-Platform": "web",
    "X-Client-Form-Factor": "desktop",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "device-test-web-002",
    "Accept-Language": "en",
}


@pytest.mark.asyncio
async def test_client_headers_middleware_enforcement(gateway_client: AsyncClient) -> None:
    """Verify middleware requires all 5 client headers on API requests and rejects invalid."""

    # 1. Missing X-Client-Platform
    bad_headers = {
        "X-Client-Form-Factor": "phone",
        "X-App-Version": "1.0.0",
        "X-Device-Id": "dev-01",
        "Accept-Language": "bn",
    }
    res = await gateway_client.get("/v1/client/config", headers=bad_headers)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_CLIENT_HEADERS"

    # 2. Invalid platform
    bad_platform = dict(CLIENT_HEADERS_ANDROID)
    bad_platform["X-Client-Platform"] = "windows_mobile"
    res = await gateway_client.get("/v1/client/config", headers=bad_platform)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_CLIENT_HEADERS"

    # 3. Missing Accept-Language
    bad_lang = dict(CLIENT_HEADERS_ANDROID)
    del bad_lang["Accept-Language"]
    res = await gateway_client.get("/v1/client/config", headers=bad_lang)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_CLIENT_HEADERS"

    # 4. Valid headers succeed
    res_ok = await gateway_client.get("/v1/client/config", headers=CLIENT_HEADERS_ANDROID)
    assert res_ok.status_code == 200

    # 5. Exempt routes (/healthz, /readyz) succeed without client headers
    res_health = await gateway_client.get("/healthz")
    assert res_health.status_code == 200


@pytest.mark.asyncio
async def test_client_config_platform_differences(gateway_client: AsyncClient) -> None:
    """Verify /client/config returns different quiz_security_mode for android vs web."""
    # Android client -> secure_kiosk with screen pinning
    res_android = await gateway_client.get("/v1/client/config", headers=CLIENT_HEADERS_ANDROID)
    assert res_android.status_code == 200
    cfg_android = res_android.json()
    assert cfg_android["quiz_security"]["allowed_mode"] == "secure_kiosk"
    assert cfg_android["quiz_security"]["screen_pinning_required"] is True
    assert cfg_android["feature_flags"]["teacher_reviews"] is False

    # Web client -> practice_only
    res_web = await gateway_client.get("/v1/client/config", headers=CLIENT_HEADERS_WEB)
    assert res_web.status_code == 200
    cfg_web = res_web.json()
    assert cfg_web["quiz_security"]["allowed_mode"] == "practice_only"
    assert cfg_web["quiz_security"]["screen_pinning_required"] is False


@pytest.mark.asyncio
async def test_auth_exchange_token_rotation_and_logout(gateway_client: AsyncClient) -> None:
    """Verify auth exchange, short-lived JWT, and rotating hashed refresh tokens."""
    phone = f"+8801700{uuid.uuid4().hex[:6]}"
    exchange_payload = {
        "provider_token": f"fake:phone:{phone}",
        "role": "parent",
        "display_name": "Rahman Parent",
        "locale": "bn",
    }

    # 1. Exchange provider token for session
    res = await gateway_client.post(
        "/v1/auth/exchange",
        json=exchange_payload,
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res.status_code == 200
    tokens = res.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]
    user = tokens["user"]
    assert user["role"] == "parent"
    assert user["phone"] == phone

    # 2. Access /v1/me with access token
    auth_headers = dict(CLIENT_HEADERS_ANDROID)
    auth_headers["Authorization"] = f"Bearer {access_token}"

    res_me = await gateway_client.get("/v1/me", headers=auth_headers)
    assert res_me.status_code == 200
    assert res_me.json()["id"] == user["id"]

    # 3. Refresh session (token rotation)
    res_refresh = await gateway_client.post(
        "/v1/auth/refresh",
        json={"refresh_token": refresh_token},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_refresh.status_code == 200
    new_tokens = res_refresh.json()
    new_access_token = new_tokens["access_token"]
    new_refresh_token = new_tokens["refresh_token"]
    assert new_access_token != access_token
    assert new_refresh_token != refresh_token

    # 4. Old refresh token is revoked; reusing it must fail with 401
    res_reuse = await gateway_client.post(
        "/v1/auth/refresh",
        json={"refresh_token": refresh_token},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_reuse.status_code == 401
    assert res_reuse.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"

    # 5. Logout revokes active refresh token
    res_logout = await gateway_client.post(
        "/v1/auth/logout",
        json={"refresh_token": new_refresh_token},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_logout.status_code == 200
    assert res_logout.json()["status"] == "logged_out"


@pytest.mark.asyncio
async def test_parent_child_linking_and_ownership_policy(gateway_client: AsyncClient) -> None:
    """Verify:
    1. Parent can create family and add child with link code.
    2. Student redeems code to activate link.
    3. Parent can read only linked children (cannot read other parent's child).
    4. Student cannot read other student's profile.
    5. Revoked link immediately blocks parent access.
    """
    # -------------------------------------------------------------
    # Step A: Setup Parent A and Child A
    # -------------------------------------------------------------
    phone_p_a = f"+88018{uuid.uuid4().hex[:8]}"
    res_pa = await gateway_client.post(
        "/v1/auth/exchange",
        json={
            "provider_token": f"fake:phone:{phone_p_a}",
            "role": "parent",
            "display_name": "Parent A",
        },
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_pa = res_pa.json()["access_token"]
    headers_pa = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_pa}"}

    # Parent A creates family
    res_fam_a = await gateway_client.post(
        "/v1/families",
        json={"name": "Family A"},
        headers=headers_pa,
    )
    assert res_fam_a.status_code == 201
    family_a_id = res_fam_a.json()["id"]

    # Parent A adds Child A
    res_add_a = await gateway_client.post(
        f"/v1/families/{family_a_id}/students",
        json={
            "display_name": "Child A",
            "class_level": 7,
            "medium": "bn",
            "school": "School A",
            "daily_minutes": 50,
        },
        headers=headers_pa,
    )
    assert res_add_a.status_code == 201
    add_a_data = res_add_a.json()
    _child_a_id = add_a_data["student_id"]
    link_code_a = add_a_data["link_code"]
    link_id_a = add_a_data["link_id"]

    # Child A signs in as student
    phone_c_a = f"+88017{uuid.uuid4().hex[:8]}"
    res_ca = await gateway_client.post(
        "/v1/auth/exchange",
        json={
            "provider_token": f"fake:phone:{phone_c_a}",
            "role": "student",
            "display_name": "Child A User",
        },
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_ca = res_ca.json()["access_token"]
    student_a_user_id = res_ca.json()["user"]["id"]
    headers_ca = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_ca}"}

    # Child A redeems link code
    res_redeem_a = await gateway_client.post(
        "/v1/links/redeem",
        json={"link_code": link_code_a},
        headers=headers_ca,
    )
    assert res_redeem_a.status_code == 200
    assert res_redeem_a.json()["status"] == "active"

    # -------------------------------------------------------------
    # Step B: Setup Parent B and Child B
    # -------------------------------------------------------------
    phone_p_b = f"+88019{uuid.uuid4().hex[:8]}"
    res_pb = await gateway_client.post(
        "/v1/auth/exchange",
        json={
            "provider_token": f"fake:phone:{phone_p_b}",
            "role": "parent",
            "display_name": "Parent B",
        },
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_pb = res_pb.json()["access_token"]
    headers_pb = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_pb}"}

    res_fam_b = await gateway_client.post(
        "/v1/families",
        json={"name": "Family B"},
        headers=headers_pb,
    )
    family_b_id = res_fam_b.json()["id"]

    res_add_b = await gateway_client.post(
        f"/v1/families/{family_b_id}/students",
        json={"display_name": "Child B", "class_level": 8, "medium": "en"},
        headers=headers_pb,
    )
    _child_b_id = res_add_b.json()["student_id"]
    link_code_b = res_add_b.json()["link_code"]

    phone_c_b = f"+88016{uuid.uuid4().hex[:8]}"
    res_cb = await gateway_client.post(
        "/v1/auth/exchange",
        json={
            "provider_token": f"fake:phone:{phone_c_b}",
            "role": "student",
            "display_name": "Child B User",
        },
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_cb = res_cb.json()["access_token"]
    student_b_user_id = res_cb.json()["user"]["id"]
    headers_cb = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_cb}"}

    res_redeem_b = await gateway_client.post(
        "/v1/links/redeem",
        json={"link_code": link_code_b},
        headers=headers_cb,
    )
    assert res_redeem_b.status_code == 200

    # -------------------------------------------------------------
    # Step C: Acceptance Check 1 - Parent can read only linked children
    # -------------------------------------------------------------
    # Parent A can see Child A in linked children list
    res_list_a = await gateway_client.get("/v1/parents/me/students", headers=headers_pa)
    assert res_list_a.status_code == 200
    linked_students_a = res_list_a.json()
    student_ids_a = [s["student_id"] for s in linked_students_a]
    assert student_a_user_id in student_ids_a
    assert student_b_user_id not in student_ids_a

    # Parent A can read Child A's profile
    res_get_a = await gateway_client.get(f"/v1/students/{student_a_user_id}", headers=headers_pa)
    assert res_get_a.status_code == 200
    assert res_get_a.json()["student_id"] == student_a_user_id

    # Parent A CANNOT read Child B's profile -> 403 Forbidden
    res_get_b_by_pa = await gateway_client.get(
        f"/v1/students/{student_b_user_id}", headers=headers_pa
    )
    assert res_get_b_by_pa.status_code == 403
    assert res_get_b_by_pa.json()["error"]["code"] == "FORBIDDEN_STUDENT_ACCESS"

    # -------------------------------------------------------------
    # Step D: Acceptance Check 2 - Student cannot read other students
    # -------------------------------------------------------------
    # Child A can read their own profile
    res_ca_self = await gateway_client.get(f"/v1/students/{student_a_user_id}", headers=headers_ca)
    assert res_ca_self.status_code == 200

    # Child A CANNOT read Child B's profile -> 403 Forbidden
    res_ca_other = await gateway_client.get(f"/v1/students/{student_b_user_id}", headers=headers_ca)
    assert res_ca_other.status_code == 403
    assert res_ca_other.json()["error"]["code"] == "FORBIDDEN_STUDENT_ACCESS"

    # -------------------------------------------------------------
    # Step E: Acceptance Check 3 - Revoked link immediately blocks access
    # -------------------------------------------------------------
    # Parent A revokes link
    res_revoke = await gateway_client.post(f"/v1/links/{link_id_a}/revoke", headers=headers_pa)
    assert res_revoke.status_code == 200
    assert res_revoke.json()["status"] == "revoked"

    # Immediately, Parent A can NO LONGER read Child A's profile
    res_revoked_access = await gateway_client.get(
        f"/v1/students/{student_a_user_id}", headers=headers_pa
    )
    assert res_revoked_access.status_code == 403
    assert res_revoked_access.json()["error"]["code"] == "FORBIDDEN_STUDENT_ACCESS"

    # Child A is no longer in Parent A's active student list
    res_list_after_revoke = await gateway_client.get("/v1/parents/me/students", headers=headers_pa)
    assert res_list_after_revoke.status_code == 200
    assert all(s["student_id"] != student_a_user_id for s in res_list_after_revoke.json())


@pytest.mark.asyncio
async def test_teacher_routes_unreachable_while_flag_off(gateway_client: AsyncClient) -> None:
    """Verify teacher routes return 403 with code FEATURE_DISABLED while teacher flag is off."""
    res_queue = await gateway_client.get("/v1/teacher/queue", headers=CLIENT_HEADERS_ANDROID)
    assert res_queue.status_code in (403, 404)
    assert res_queue.json()["error"]["code"] == "FEATURE_DISABLED"

    random_id = uuid.uuid4()
    res_review = await gateway_client.post(
        f"/v1/teacher/submissions/{random_id}/review",
        json={"score": 85.0, "comment": "Good effort"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_review.status_code in (403, 404)
    assert res_review.json()["error"]["code"] == "FEATURE_DISABLED"

    res_flag = await gateway_client.post(
        "/v1/teacher/topics/flag",
        json={"topic_id": "math_algebra_ch2"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_flag.status_code in (403, 404)
    assert res_flag.json()["error"]["code"] == "FEATURE_DISABLED"


@pytest.mark.asyncio
async def test_brute_force_rate_limit_on_link_codes(gateway_client: AsyncClient) -> None:
    """Verify link code redemption enforces rate limiting, returning 429 after 5 attempts."""
    # Create student to attempt link redemptions
    phone = f"+88015{uuid.uuid4().hex[:8]}"
    res_st = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone}", "role": "student"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token = res_st.json()["access_token"]
    headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    # Rapidly fire 5 invalid code attempts (allowed up to 5)
    for i in range(5):
        res = await gateway_client.post(
            "/v1/links/redeem",
            json={"link_code": f"FAIL{i:04d}"},
            headers=headers,
        )
        # Should be 400 Bad Request (invalid code)
        assert res.status_code == 400, f"Attempt {i + 1} got unexpected status {res.status_code}"

    # 6th attempt must be blocked by rate limiter with HTTP 429
    res_blocked = await gateway_client.post(
        "/v1/links/redeem",
        json={"link_code": "FAIL9999"},
        headers=headers,
    )
    assert res_blocked.status_code == 429
    data = res_blocked.json()
    assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in res_blocked.headers


@pytest.mark.asyncio
async def test_bangla_and_english_unicode_fidelity(gateway_client: AsyncClient) -> None:
    """Verify fidelity for Bengali Unicode strings in users, families, and profiles."""
    bangla_parent_name = "তাহমিদ আল রহমান"
    bangla_family_name = "রহমান পরিবার (ঢাকা)"
    bangla_student_name = "শাকিব আল রহমান"
    bangla_school_name = "মতিঝিল আইডিয়াল স্কুল অ্যান্ড কলেজ"

    phone = f"+88013{uuid.uuid4().hex[:8]}"
    # 1. Register with Bengali display name
    res_p = await gateway_client.post(
        "/v1/auth/exchange",
        json={
            "provider_token": f"fake:phone:{phone}",
            "role": "parent",
            "display_name": bangla_parent_name,
            "locale": "bn",
        },
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_p.status_code == 200
    assert res_p.json()["user"]["display_name"] == bangla_parent_name
    token = res_p.json()["access_token"]
    headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    # 2. Create family with Bengali name
    res_fam = await gateway_client.post(
        "/v1/families",
        json={"name": bangla_family_name},
        headers=headers,
    )
    assert res_fam.status_code == 201
    assert res_fam.json()["name"] == bangla_family_name
    family_id = res_fam.json()["id"]

    # 3. Add student with Bengali profile details
    res_child = await gateway_client.post(
        f"/v1/families/{family_id}/students",
        json={
            "display_name": bangla_student_name,
            "class_level": 7,
            "medium": "bn",
            "school": bangla_school_name,
            "daily_minutes": 60,
        },
        headers=headers,
    )
    assert res_child.status_code == 201
    _student_id = res_child.json()["student_id"]
    link_code = res_child.json()["link_code"]

    # 4. Student redeems code
    phone_s = f"+88014{uuid.uuid4().hex[:8]}"
    res_s = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_s}", "role": "student"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_s = res_s.json()["access_token"]
    student_user_id = res_s.json()["user"]["id"]
    headers_s = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_s}"}

    res_redeem = await gateway_client.post(
        "/v1/links/redeem",
        json={"link_code": link_code},
        headers=headers_s,
    )
    assert res_redeem.status_code == 200

    # 5. Read profile through Parent endpoint and verify Unicode
    res_profile = await gateway_client.get(f"/v1/students/{student_user_id}", headers=headers)
    assert res_profile.status_code == 200
    data = res_profile.json()
    assert data["medium"] == "bn"
    assert data["school"] == bangla_school_name
    assert data["class_level"] == 7


@pytest.mark.asyncio
async def test_devices_registration_and_update(gateway_client: AsyncClient) -> None:
    """Verify client device registration and push token management."""
    phone = f"+88018{uuid.uuid4().hex[:8]}"
    res_auth = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone}", "role": "student"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token = res_auth.json()["access_token"]
    headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    # Register device
    res_reg = await gateway_client.post(
        "/v1/devices",
        json={
            "platform": "android",
            "form_factor": "phone",
            "push_token": "fcm_token_initial_12345",
            "app_version": "1.0.0",
        },
        headers=headers,
    )
    assert res_reg.status_code == 201
    dev = res_reg.json()
    device_id = dev["id"]
    assert dev["platform"] == "android"
    assert dev["push_token"] == "fcm_token_initial_12345"

    # Update push token and version
    res_patch = await gateway_client.patch(
        f"/v1/devices/{device_id}",
        json={
            "push_token": "fcm_token_updated_67890",
            "app_version": "1.0.1",
        },
        headers=headers,
    )
    assert res_patch.status_code == 200
    updated_dev = res_patch.json()
    assert updated_dev["push_token"] == "fcm_token_updated_67890"
    assert updated_dev["app_version"] == "1.0.1"
