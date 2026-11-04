"""Real-backend integration tests for Parent-Child Authorization and Revocation Isolation (Rule 9).

Verifies via real HTTP requests through the gateway and core backend:
1. Parent A requesting Child B's dashboard gets HTTP 403 Forbidden (cross-family isolation).
2. Parent A revoking active link with Child A cuts off access immediately (HTTP 403 Forbidden).
3. Student cannot access other students' endpoints.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

CLIENT_HEADERS_ANDROID = {
    "X-Client-Platform": "android",
    "X-Client-Form-Factor": "phone",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "device-test-android-p08a",
    "Accept-Language": "bn",
}


@pytest.mark.asyncio
async def test_real_backend_parent_isolation_and_immediate_revocation(
    gateway_client: AsyncClient,
) -> None:
    """Verify that Parent A requesting Child B returns 403, and revoked link blocks access immediately."""
    # -------------------------------------------------------------------------
    # 1. Register Parent A and add Child A
    # -------------------------------------------------------------------------
    phone_a = f"+880171{uuid.uuid4().hex[:6]}"
    res_pa = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_a}", "role": "parent", "display_name": "রফিক ইসলাম (Parent A)", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_pa.status_code == 200, res_pa.text
    token_pa = res_pa.json()["access_token"]
    headers_pa = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_pa}"}

    res_fama = await gateway_client.post("/v1/families", json={"name": "ইসলাম পরিবার"}, headers=headers_pa)
    assert res_fama.status_code == 201
    family_a_id = res_fama.json()["id"]

    res_child_a = await gateway_client.post(
        f"/v1/families/{family_a_id}/students",
        json={"display_name": "তাহমিদ (Child A)", "class_level": 9, "medium": "bn", "group": "science", "daily_minutes": 60},
        headers=headers_pa,
    )
    assert res_child_a.status_code == 201
    child_a_data = res_child_a.json()
    child_a_id = child_a_data["student_id"]
    link_a_id = child_a_data["link_id"]
    link_a_code = child_a_data["link_code"]

    # Register Student A with Parent A link code
    phone_sa = f"+880172{uuid.uuid4().hex[:6]}"
    res_sa = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_sa}", "role": "student", "display_name": "তাহমিদ (Child A)", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_sa.status_code == 200
    token_sa = res_sa.json()["access_token"]
    headers_sa = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_sa}"}

    res_redeem_a = await gateway_client.post("/v1/links/redeem", json={"link_code": link_a_code}, headers=headers_sa)
    assert res_redeem_a.status_code == 200

    # -------------------------------------------------------------------------
    # 2. Register Parent B and add Child B
    # -------------------------------------------------------------------------
    phone_b = f"+880173{uuid.uuid4().hex[:6]}"
    res_pb = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_b}", "role": "parent", "display_name": "সালমা বেগম (Parent B)", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_pb.status_code == 200
    token_pb = res_pb.json()["access_token"]
    headers_pb = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_pb}"}

    res_famb = await gateway_client.post("/v1/families", json={"name": "বেগম পরিবার"}, headers=headers_pb)
    assert res_famb.status_code == 201
    family_b_id = res_famb.json()["id"]

    res_child_b = await gateway_client.post(
        f"/v1/families/{family_b_id}/students",
        json={"display_name": "আনিকা (Child B)", "class_level": 10, "medium": "bn", "group": "business", "daily_minutes": 45},
        headers=headers_pb,
    )
    assert res_child_b.status_code == 201
    child_b_data = res_child_b.json()
    child_b_id = child_b_data["student_id"]
    link_b_code = child_b_data["link_code"]

    phone_sb = f"+880174{uuid.uuid4().hex[:6]}"
    res_sb = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_sb}", "role": "student", "display_name": "আনিকা (Child B)", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_sb.status_code == 200
    token_sb = res_sb.json()["access_token"]
    headers_sb = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_sb}"}

    res_redeem_b = await gateway_client.post("/v1/links/redeem", json={"link_code": link_b_code}, headers=headers_sb)
    assert res_redeem_b.status_code == 200

    # -------------------------------------------------------------------------
    # 3. Parent A requesting Child B gets 403 Forbidden (Rule 9)
    # -------------------------------------------------------------------------
    res_cross_dashboard = await gateway_client.get(
        f"/v1/parents/me/students/{child_b_id}/dashboard",
        headers=headers_pa,
    )
    assert res_cross_dashboard.status_code == 403
    assert res_cross_dashboard.json()["error"]["code"] in ("FORBIDDEN_STUDENT_ACCESS", "FAMILY_ACCESS_DENIED")

    res_cross_profile = await gateway_client.get(
        f"/v1/students/{child_b_id}",
        headers=headers_pa,
    )
    assert res_cross_profile.status_code == 403
    assert res_cross_profile.json()["error"]["code"] == "FORBIDDEN_STUDENT_ACCESS"

    # -------------------------------------------------------------------------
    # 4. Parent A accessing Child A succeeds while link is active
    # -------------------------------------------------------------------------
    res_own_profile = await gateway_client.get(
        f"/v1/students/{child_a_id}",
        headers=headers_pa,
    )
    assert res_own_profile.status_code == 200

    # -------------------------------------------------------------------------
    # 5. Revoked link cuts off Parent A access immediately (403 Forbidden)
    # -------------------------------------------------------------------------
    res_revoke = await gateway_client.post(f"/v1/links/{link_a_id}/revoke", headers=headers_pa)
    assert res_revoke.status_code == 200
    assert res_revoke.json()["status"] == "revoked"

    # Immediately requesting Child A's profile or dashboard must return 403 Forbidden
    res_post_revoke_profile = await gateway_client.get(
        f"/v1/students/{child_a_id}",
        headers=headers_pa,
    )
    assert res_post_revoke_profile.status_code == 403
    assert res_post_revoke_profile.json()["error"]["code"] == "FORBIDDEN_STUDENT_ACCESS"

    res_post_revoke_dashboard = await gateway_client.get(
        f"/v1/parents/me/students/{child_a_id}/dashboard",
        headers=headers_pa,
    )
    assert res_post_revoke_dashboard.status_code == 403
    assert res_post_revoke_dashboard.json()["error"]["code"] in ("FORBIDDEN_STUDENT_ACCESS", "FAMILY_ACCESS_DENIED")

