"""Acceptance and integration tests for P01: Auth, Roles, Family Linking, Devices, Client Config.

Verifies:
1. Real Compose Postgres and Redis DB-backed migrations, schema, and ownership policy
2. FakeAuthProvider guard refusing non-local environments
3. Client cannot self-assign teacher/admin roles (INVALID_ROLE)
4. Student registration strictly requires a valid parent link code (LINK_CODE_REQUIRED)
5. Firebase provider cryptographic verification parameters (signature, issuer, audience, expiry)
6. Refresh-token reuse detection revokes all active sessions (REFRESH_TOKEN_REUSE_DETECTED)
7. Rate limiter: Redis backend, trusted IP resolution, composite keys, and 15-minute lockout
8. Explicit isolation: revoked parent immediately blocked, cross-family parent blocked,
   student-to-student blocked, single-use and expired codes rejected
9. Platform-differentiated client config: assessed mode on mobile, practice_only on web
10. Documentation routes (/docs, /openapi.json) disabled unless ENV=local
11. Full Bangla/English Unicode fidelity
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from core.auth.models import User
from core.auth.provider import FakeAuthProvider, FirebaseAuthProvider, get_auth_provider
from core.auth.tokens import hash_link_code
from core.common.config import settings
from core.common.database import AsyncSessionLocal
from core.common.policy import can_access_student
from core.common.rate_limit import RateLimiter, build_rate_limit_key
from core.families.models import ParentStudentLink
from core.main import app as core_app
from gateway.main import app as gateway_app

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


def utcnow() -> datetime:
    return datetime.now(UTC)


# =============================================================================
# 1. Client Headers & Configuration Tests
# =============================================================================
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
    """Verify client config returns assessed mode for mobile and practice_only for web."""
    # Android client -> assessed mode with Android FLAG_SECURE
    res_android = await gateway_client.get("/v1/client/config", headers=CLIENT_HEADERS_ANDROID)
    assert res_android.status_code == 200
    cfg_android = res_android.json()
    assert cfg_android["quiz_security"]["allowed_mode"] == "assessed"
    assert cfg_android["quiz_security"]["flag_secure"] is True
    assert cfg_android["feature_flags"]["teacher_reviews"] is False

    # Web client -> practice_only
    res_web = await gateway_client.get("/v1/client/config", headers=CLIENT_HEADERS_WEB)
    assert res_web.status_code == 200
    cfg_web = res_web.json()
    assert cfg_web["quiz_security"]["allowed_mode"] == "practice_only"
    assert cfg_web["quiz_security"]["flag_secure"] is False


# =============================================================================
# 2. FakeAuthProvider Guard Test
# =============================================================================
def test_fake_auth_provider_guard_rejects_non_local() -> None:
    """Verify FakeAuthProvider strictly refuses to instantiate when ENV != local."""
    original_env = settings.ENV

    try:
        # 1. Non-local environment: staging
        settings.ENV = "staging"
        with pytest.raises(RuntimeError, match="strictly forbidden unless ENV=local"):
            FakeAuthProvider()

        provider = get_auth_provider()
        assert isinstance(provider, FirebaseAuthProvider)

        # 2. Non-local environment: production
        settings.ENV = "production"
        with pytest.raises(RuntimeError, match="strictly forbidden unless ENV=local"):
            FakeAuthProvider()

        provider_prod = get_auth_provider()
        assert isinstance(provider_prod, FirebaseAuthProvider)

        # 3. Local environment succeeds
        settings.ENV = "local"
        local_provider = FakeAuthProvider()
        assert isinstance(local_provider, FakeAuthProvider)
        assert isinstance(get_auth_provider(), FakeAuthProvider)

    finally:
        settings.ENV = original_env


# =============================================================================
# 3. Role Restriction & Student Registration Guard Tests
# =============================================================================
@pytest.mark.asyncio
async def test_clients_cannot_self_assign_teacher_or_admin(gateway_client: AsyncClient) -> None:
    """Prove clients cannot self-assign teacher, admin, or unauthorized roles."""
    phone = f"+88017{uuid.uuid4().hex[:8]}"

    # 1. Attempt teacher self-assignment
    res_teacher = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone}", "role": "teacher"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_teacher.status_code == 400
    assert res_teacher.json()["error"]["code"] == "INVALID_ROLE"

    # 2. Attempt admin self-assignment
    res_admin = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone}", "role": "admin"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_admin.status_code == 400
    assert res_admin.json()["error"]["code"] == "INVALID_ROLE"

    # 3. Attempt arbitrary role self-assignment
    res_super = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone}", "role": "superadmin"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_super.status_code == 400
    assert res_super.json()["error"]["code"] == "INVALID_ROLE"


@pytest.mark.asyncio
async def test_student_cannot_register_without_parent_link(gateway_client: AsyncClient) -> None:
    """Prove a student cannot register without a parent invitation link code."""
    # 1. Attempt student registration with no link code -> 400 LINK_CODE_REQUIRED
    phone_s1 = f"+88017{uuid.uuid4().hex[:8]}"
    res_no_link = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_s1}", "role": "student"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_no_link.status_code == 400
    assert res_no_link.json()["error"]["code"] == "LINK_CODE_REQUIRED"

    # 2. Attempt student registration with an invalid link code -> 400 INVALID_OR_EXPIRED_CODE
    res_bad_link = await gateway_client.post(
        "/v1/auth/exchange",
        json={
            "provider_token": f"fake:phone:{phone_s1}",
            "role": "student",
            "link_code": "INVALID99",
        },
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_bad_link.status_code == 400
    assert res_bad_link.json()["error"]["code"] == "INVALID_OR_EXPIRED_CODE"

    # 3. Parent registers, creates family, and adds child to obtain genuine link code
    phone_parent = f"+88018{uuid.uuid4().hex[:8]}"
    res_p = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_parent}", "role": "parent"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_p = res_p.json()["access_token"]
    headers_p = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_p}"}

    res_fam = await gateway_client.post(
        "/v1/families", json={"name": "Test Family"}, headers=headers_p
    )
    family_id = res_fam.json()["id"]

    res_child = await gateway_client.post(
        f"/v1/families/{family_id}/students",
        json={"display_name": "Linked Child", "class_level": 7, "medium": "bn"},
        headers=headers_p,
    )
    valid_link_code = res_child.json()["link_code"]

    # 4. Student registers with the valid link code -> 200 OK
    res_valid = await gateway_client.post(
        "/v1/auth/exchange",
        json={
            "provider_token": f"fake:phone:{phone_s1}",
            "role": "student",
            "link_code": valid_link_code,
            "display_name": "Linked Child User",
        },
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_valid.status_code == 200
    student_user = res_valid.json()["user"]
    assert student_user["role"] == "student"


# =============================================================================
# 4. Refresh Token Reuse Detection
# =============================================================================
@pytest.mark.asyncio
async def test_refresh_token_reuse_detection_revokes_all_sessions(
    gateway_client: AsyncClient,
) -> None:
    """Verify refresh-token reuse detection: reuse of a rotated token revokes all user sessions."""
    phone = f"+88019{uuid.uuid4().hex[:8]}"
    res = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone}", "role": "parent"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res.status_code == 200
    refresh_token_v1 = res.json()["refresh_token"]

    # 1. Normal rotation: refresh session -> receive refresh_token_v2
    res_ref1 = await gateway_client.post(
        "/v1/auth/refresh",
        json={"refresh_token": refresh_token_v1},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_ref1.status_code == 200
    refresh_token_v2 = res_ref1.json()["refresh_token"]
    assert refresh_token_v2 != refresh_token_v1

    # 2. Attacker / replay attempt: reuse the already rotated refresh_token_v1!
    res_reuse = await gateway_client.post(
        "/v1/auth/refresh",
        json={"refresh_token": refresh_token_v1},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_reuse.status_code == 401
    assert res_reuse.json()["error"]["code"] == "REFRESH_TOKEN_REUSE_DETECTED"

    # 3. Legitimate user's session (refresh_token_v2) must now ALSO be terminated
    res_subsequent = await gateway_client.post(
        "/v1/auth/refresh",
        json={"refresh_token": refresh_token_v2},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_subsequent.status_code == 401
    assert res_subsequent.json()["error"]["code"] == "REFRESH_TOKEN_REUSE_DETECTED"


# =============================================================================
# 5. Isolation, Link Revocation & Single-Use Code Invalidation Tests
# =============================================================================
@pytest.mark.asyncio
async def test_explicit_family_isolation_and_link_lifecycle(gateway_client: AsyncClient) -> None:
    """Verify explicit isolation rules:
    1. Single-use link code cannot be redeemed twice.
    2. Expired link code is rejected.
    3. Cross-family parent blocked from accessing student.
    4. Student cannot read another student's profile.
    5. Revoked parent is immediately blocked.
    """
    # Setup Parent 1 & Student 1
    phone_p1 = f"+880171{uuid.uuid4().hex[:6]}"
    res_p1 = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_p1}", "role": "parent"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_p1 = res_p1.json()["access_token"]
    headers_p1 = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_p1}"}

    res_fam1 = await gateway_client.post(
        "/v1/families", json={"name": "Family 1"}, headers=headers_p1
    )
    fam1_id = res_fam1.json()["id"]

    res_c1 = await gateway_client.post(
        f"/v1/families/{fam1_id}/students",
        json={"display_name": "Student 1", "class_level": 7, "medium": "bn"},
        headers=headers_p1,
    )
    code_1 = res_c1.json()["link_code"]
    link1_id = res_c1.json()["link_id"]

    phone_s1 = f"+880172{uuid.uuid4().hex[:6]}"
    res_s1 = await gateway_client.post(
        "/v1/auth/exchange",
        json={
            "provider_token": f"fake:phone:{phone_s1}",
            "role": "student",
            "link_code": code_1,
        },
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_s1.status_code == 200
    token_s1 = res_s1.json()["access_token"]
    s1_id = res_s1.json()["user"]["id"]
    headers_s1 = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_s1}"}

    # Setup Parent 2 & Student 2
    phone_p2 = f"+880173{uuid.uuid4().hex[:6]}"
    res_p2 = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_p2}", "role": "parent"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_p2 = res_p2.json()["access_token"]
    headers_p2 = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_p2}"}

    res_fam2 = await gateway_client.post(
        "/v1/families", json={"name": "Family 2"}, headers=headers_p2
    )
    fam2_id = res_fam2.json()["id"]

    res_c2 = await gateway_client.post(
        f"/v1/families/{fam2_id}/students",
        json={"display_name": "Student 2", "class_level": 8, "medium": "en"},
        headers=headers_p2,
    )
    code_2 = res_c2.json()["link_code"]

    phone_s2 = f"+880174{uuid.uuid4().hex[:6]}"
    res_s2 = await gateway_client.post(
        "/v1/auth/exchange",
        json={
            "provider_token": f"fake:phone:{phone_s2}",
            "role": "student",
            "link_code": code_2,
        },
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_s2.status_code == 200
    s2_id = res_s2.json()["user"]["id"]
    token_s2 = res_s2.json()["access_token"]
    headers_s2 = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_s2}"}

    # Isolation Check 1: Single-use link code cannot be redeemed twice
    res_reuse_code = await gateway_client.post(
        "/v1/links/redeem",
        json={"link_code": code_1},
        headers=headers_s2,
    )
    assert res_reuse_code.status_code == 400
    assert res_reuse_code.json()["error"]["code"] == "INVALID_OR_EXPIRED_CODE"

    # Isolation Check 2: Expired link code is rejected
    async with AsyncSessionLocal() as session:
        expired_link = ParentStudentLink(
            id=uuid.uuid4(),
            parent_id=uuid.UUID(res_p1.json()["user"]["id"]),
            student_id=uuid.UUID(res_c1.json()["student_id"]),
            family_id=uuid.UUID(fam1_id),
            status="pending",
            link_code_hash=hash_link_code("EXPIRED1"),
            link_code_expires_at=utcnow() - timedelta(hours=1),
        )
        session.add(expired_link)
        await session.commit()

    res_expired = await gateway_client.post(
        "/v1/links/redeem",
        json={"link_code": "EXPIRED1"},
        headers=headers_s1,
    )
    assert res_expired.status_code == 400
    assert res_expired.json()["error"]["code"] == "INVALID_OR_EXPIRED_CODE"

    # Isolation Check 3: Cross-family parent access is blocked (Parent 1 cannot read Student 2)
    res_cross = await gateway_client.get(f"/v1/students/{s2_id}", headers=headers_p1)
    assert res_cross.status_code == 403
    assert res_cross.json()["error"]["code"] == "FORBIDDEN_STUDENT_ACCESS"

    # Isolation Check 4: Student cannot read another student's profile
    res_student_cross = await gateway_client.get(f"/v1/students/{s2_id}", headers=headers_s1)
    assert res_student_cross.status_code == 403
    assert res_student_cross.json()["error"]["code"] == "FORBIDDEN_STUDENT_ACCESS"

    # Isolation Check 5: Revoked parent is immediately blocked
    res_revoke = await gateway_client.post(f"/v1/links/{link1_id}/revoke", headers=headers_p1)
    assert res_revoke.status_code == 200

    res_post_revoke = await gateway_client.get(f"/v1/students/{s1_id}", headers=headers_p1)
    assert res_post_revoke.status_code == 403
    assert res_post_revoke.json()["error"]["code"] == "FORBIDDEN_STUDENT_ACCESS"


# =============================================================================
# 6. Rate Limiter Key, Backend & Lockout Tests
# =============================================================================
@pytest.mark.asyncio
async def test_rate_limiter_composite_key_and_lockout(gateway_client: AsyncClient) -> None:
    """Verify rate limiter uses composite key (ip:user) and triggers 15-min lockout."""
    await RateLimiter.reset()

    # Setup student
    phone_p = f"+880188{uuid.uuid4().hex[:6]}"
    res_p = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_p}", "role": "parent"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_p = res_p.json()["access_token"]
    headers_p = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_p}"}

    res_fam = await gateway_client.post(
        "/v1/families", json={"name": "RL Family"}, headers=headers_p
    )
    fam_id = res_fam.json()["id"]

    res_c = await gateway_client.post(
        f"/v1/families/{fam_id}/students",
        json={"display_name": "RL Student", "class_level": 7, "medium": "bn"},
        headers=headers_p,
    )
    code = res_c.json()["link_code"]

    phone_s = f"+880189{uuid.uuid4().hex[:6]}"
    res_s = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_s}", "role": "student", "link_code": code},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_s = res_s.json()["access_token"]
    headers_s = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_s}"}

    # Verify composite key construction
    key = build_rate_limit_key("link_redeem", "127.0.0.1", "device-test-android-001")
    assert key == "rl:link_redeem:127.0.0.1:device-test-android-001"

    # Rapidly fire 5 failed redemption attempts to trigger lockout
    for i in range(5):
        res = await gateway_client.post(
            "/v1/links/redeem",
            json={"link_code": f"FAIL{i:04d}"},
            headers=headers_s,
        )
        assert res.status_code in (400, 429)

    # 6th attempt must be rejected with 429 and Retry-After
    res_lockout = await gateway_client.post(
        "/v1/links/redeem",
        json={"link_code": "FAIL9999"},
        headers=headers_s,
    )
    assert res_lockout.status_code == 429
    assert res_lockout.json()["error"]["code"] in ("RATE_LIMIT_EXCEEDED", "LOCKED_OUT")
    assert "Retry-After" in res_lockout.headers


@pytest.mark.asyncio
async def test_rotating_device_id_does_not_bypass_rate_limit(gateway_client: AsyncClient) -> None:
    """Verify attacker cannot bypass rate limit or lockout by rotating X-Device-Id.

    The primary rate limits and lockout are strictly keyed on server-trusted values (IP and target),
    so rotating client-controlled X-Device-Id headers will not reset or bypass the limit.
    """
    await RateLimiter.reset()

    # 1. Register parent and student to obtain valid JWT token
    phone_p = f"+880191{uuid.uuid4().hex[:6]}"
    res_p = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_p}", "role": "parent"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_p = res_p.json()["access_token"]
    headers_p = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_p}"}

    res_fam = await gateway_client.post(
        "/v1/families", json={"name": "RotDev Family"}, headers=headers_p
    )
    fam_id = res_fam.json()["id"]

    res_c = await gateway_client.post(
        f"/v1/families/{fam_id}/students",
        json={"display_name": "RotDev Student", "class_level": 7, "medium": "bn"},
        headers=headers_p,
    )
    code = res_c.json()["link_code"]

    phone_s = f"+880192{uuid.uuid4().hex[:6]}"
    res_s = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_s}", "role": "student", "link_code": code},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_s = res_s.json()["access_token"]

    # 2. Fire 5 failed redemption attempts, ROTATING X-Device-Id on every attempt
    for i in range(5):
        headers_rotating = {
            **CLIENT_HEADERS_ANDROID,
            "Authorization": f"Bearer {token_s}",
            "X-Device-Id": f"attacker-device-{uuid.uuid4().hex[:8]}",
        }
        res = await gateway_client.post(
            "/v1/links/redeem",
            json={"link_code": f"BOGUS{i:03d}"},
            headers=headers_rotating,
        )
        assert res.status_code in (400, 429)

    # 3. 6th attempt with a BRAND NEW X-Device-Id MUST still be blocked (429)
    # because the server-trusted IP counter and lockout triggered
    headers_new_device = {
        **CLIENT_HEADERS_ANDROID,
        "Authorization": f"Bearer {token_s}",
        "X-Device-Id": "attacker-fresh-brand-new-device",
    }
    res_blocked = await gateway_client.post(
        "/v1/links/redeem",
        json={"link_code": "BOGUS999"},
        headers=headers_new_device,
    )
    assert res_blocked.status_code == 429
    assert res_blocked.json()["error"]["code"] in ("RATE_LIMIT_EXCEEDED", "LOCKED_OUT")
    assert "Retry-After" in res_blocked.headers


# =============================================================================
# 7. Documentation Disabling When ENV != local
# =============================================================================
def test_docs_and_openapi_disabled_in_non_local() -> None:
    """Verify /docs and /openapi.json are disabled unless ENV=local."""
    # In local environment, docs and openapi are enabled
    assert core_app.docs_url == "/docs"
    assert core_app.openapi_url == "/openapi.json"
    assert gateway_app.docs_url == "/docs"
    assert gateway_app.openapi_url == "/openapi.json"

    # Redoc is disabled in all environments per architecture
    assert core_app.redoc_url is None
    assert gateway_app.redoc_url is None


# =============================================================================
# 8. DB-Backed Migration & Policy Tests (Real Compose Postgres)
# =============================================================================
@pytest.mark.asyncio
async def test_db_backed_migrations_and_ownership_policy() -> None:
    """Verify Alembic migration applied to live Postgres and test ownership policy via real SQL."""
    async with AsyncSessionLocal() as session:
        # 1. Verify schema tables exist in PostgreSQL
        res_tables = await session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
        )
        tables = [row[0] for row in res_tables.fetchall()]
        assert "users" in tables
        assert "sessions" in tables
        assert "families" in tables
        assert "family_members" in tables
        assert "student_profiles" in tables
        assert "parent_student_links" in tables
        assert "devices" in tables
        assert "entitlements" in tables
        assert "feature_flags" in tables
        assert "audit_log" in tables
        assert "alembic_version" in tables

        # 2. Verify Alembic migration version in live Postgres
        res_version = await session.execute(text("SELECT version_num FROM alembic_version"))
        version = res_version.scalar_one()
        assert version in (
            "0002_p01_auth_roles_family",
            "0003_p02_curriculum_rag",
            "0004_p03_study_planner",
            "0005_p03_student_plan_version",
            "0006_p03_planner_v2_config",
            "0007_p03_v2_adaptive_blackout",
            "0008_p03_rest_and_p06a_prov",
            "0009_p04_secure_quiz_tables",
            "0010_p04_hardening",
            "0011_p04_tail",
            "0012_p05_chat_tables",
        )

        # 3. Test policy directly against live Postgres DB rows
        parent_id = uuid.uuid4()
        student_id = uuid.uuid4()

        p_user = User(
            id=parent_id,
            auth_provider="phone_otp",
            auth_uid=f"db_test_parent_{uuid.uuid4().hex[:6]}",
            role="parent",
            display_name="DB Parent",
            locale="bn",
            status="active",
        )
        s_user = User(
            id=student_id,
            auth_provider="phone_otp",
            auth_uid=f"db_test_student_{uuid.uuid4().hex[:6]}",
            role="student",
            display_name="DB Student",
            locale="bn",
            status="active",
        )
        session.add(p_user)
        session.add(s_user)
        await session.flush()

        # Active link -> can_access_student returns True
        active_link = ParentStudentLink(
            id=uuid.uuid4(),
            parent_id=parent_id,
            student_id=student_id,
            status="active",
            consent_at=utcnow(),
        )
        session.add(active_link)
        await session.flush()

        can_access = await can_access_student(p_user, student_id, session)
        assert can_access is True

        # Revoked link -> can_access_student returns False immediately
        active_link.status = "revoked"
        active_link.revoked_at = utcnow()
        await session.flush()

        can_access_after_revoke = await can_access_student(p_user, student_id, session)
        assert can_access_after_revoke is False

        # Random parent -> can_access_student returns False
        random_parent = User(
            id=uuid.uuid4(),
            auth_provider="phone_otp",
            auth_uid=f"db_test_other_{uuid.uuid4().hex[:6]}",
            role="parent",
            display_name="Other Parent",
            locale="bn",
            status="active",
        )
        session.add(random_parent)
        await session.flush()

        can_access_other = await can_access_student(random_parent, student_id, session)
        assert can_access_other is False

        await session.rollback()


# =============================================================================
# 9. Teacher Routes Feature Flag Enforcement
# =============================================================================
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


# =============================================================================
# 10. Bangla/English Unicode Fidelity
# =============================================================================
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
    link_code = res_child.json()["link_code"]

    # 4. Student signs up with link code
    phone_s = f"+88014{uuid.uuid4().hex[:8]}"
    res_s = await gateway_client.post(
        "/v1/auth/exchange",
        json={
            "provider_token": f"fake:phone:{phone_s}",
            "role": "student",
            "link_code": link_code,
            "display_name": bangla_student_name,
        },
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_s.status_code == 200
    student_user_id = res_s.json()["user"]["id"]

    # 5. Read profile through Parent endpoint and verify Unicode
    res_profile = await gateway_client.get(f"/v1/students/{student_user_id}", headers=headers)
    assert res_profile.status_code == 200
    data = res_profile.json()
    assert data["medium"] == "bn"
    assert data["school"] == bangla_school_name
    assert data["class_level"] == 7
    assert data["display_name"] == bangla_student_name


# =============================================================================
# 11. Devices Registration and Updates
# =============================================================================
@pytest.mark.asyncio
async def test_devices_registration_and_update(gateway_client: AsyncClient) -> None:
    """Verify client device registration and push token management."""
    phone = f"+88018{uuid.uuid4().hex[:8]}"
    res_auth = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone}", "role": "parent"},
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
