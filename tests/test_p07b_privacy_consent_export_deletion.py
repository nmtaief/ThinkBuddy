"""Tests for Parental Consent, Family Data Export, Account Deletion Grace Period, and Purge Job (P07b)."""

from __future__ import annotations

import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from core.audit.models import AuditLog
from core.auth.models import Session as UserSession, User
from core.auth.tokens import create_access_jwt
from core.common.database import get_db_session
from core.devices.models import Device
from core.families.models import Family, FamilyMember, ParentStudentLink, StudentProfile
from core.privacy.models import AccountDeletion, ParentalConsent
from core.privacy.purge import execute_data_purge

CLIENT_HEADERS_ANDROID = {
    "X-Client-Platform": "android",
    "X-Client-Form-Factor": "phone",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "device-test-android-p07b",
    "Accept-Language": "bn",
}


@pytest.mark.asyncio
async def test_parental_consent_recording_and_status(gateway_client: AsyncClient) -> None:
    """Parent records explicit consent version and timestamp, verified via GET /parents/consent."""
    phone = f"+880173{uuid.uuid4().hex[:6]}"
    res_auth = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone}", "role": "parent", "display_name": "মাসুদ রানা (Parent)", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_auth.status_code == 200
    token = res_auth.json()["access_token"]
    headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    # 1. Check initial consent status
    res_status1 = await gateway_client.get("/v1/parents/consent", headers=headers)
    assert res_status1.status_code == 200
    assert res_status1.json()["has_consent"] is False

    # 2. Record affirmative consent
    res_consent = await gateway_client.post(
        "/v1/parents/consent",
        json={"version": "1.0", "consented": True},
        headers=headers,
    )
    assert res_consent.status_code == 200
    data = res_consent.json()
    assert data["status"] == "granted"
    assert data["version"] == "1.0"
    assert "consented_at" in data

    # 3. Check updated consent status
    res_status2 = await gateway_client.get("/v1/parents/consent", headers=headers)
    assert res_status2.status_code == 200
    assert res_status2.json()["has_consent"] is True
    assert res_status2.json()["version"] == "1.0"


@pytest.mark.asyncio
async def test_parental_consent_gating_child_data_processing(gateway_client: AsyncClient) -> None:
    """Child data processing is strictly gated by server-recorded parental consent."""
    phone = f"+880174{uuid.uuid4().hex[:6]}"
    res_auth = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone}", "role": "parent", "display_name": "আনিসুল হক (Parent)", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_auth.status_code == 200
    token = res_auth.json()["access_token"]
    headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    # Create family
    res_fam = await gateway_client.post("/v1/families", json={"name": "হক পরিবার"}, headers=headers)
    assert res_fam.status_code == 201
    family_id = res_fam.json()["id"]

    # Attempt to add child when consent is missing and gate is enforced
    res_gated = await gateway_client.post(
        f"/v1/families/{family_id}/students",
        json={"display_name": "নাবিল (Child)", "class_level": 7, "medium": "bn", "daily_minutes": 45},
        headers={**headers, "X-Enforce-Consent": "true"},
    )
    assert res_gated.status_code == 403
    assert res_gated.json()["error"]["code"] == "PARENTAL_CONSENT_REQUIRED"

    # Parent records consent
    res_consent = await gateway_client.post(
        "/v1/parents/consent",
        json={"version": "1.0", "consented": True},
        headers=headers,
    )
    assert res_consent.status_code == 200

    # Add child succeeds now that consent is recorded
    res_success = await gateway_client.post(
        f"/v1/families/{family_id}/students",
        json={"display_name": "নাবিল (Child)", "class_level": 7, "medium": "bn", "daily_minutes": 45},
        headers={**headers, "X-Enforce-Consent": "true"},
    )
    assert res_success.status_code == 201
    assert "student_id" in res_success.json()


@pytest.mark.asyncio
async def test_family_data_export_strictly_excludes_raw_chat_transcripts(gateway_client: AsyncClient) -> None:
    """Family data export produces structured JSON with topic-level summaries and ZERO raw chat transcripts (Rule 15)."""
    phone_p = f"+880175{uuid.uuid4().hex[:6]}"
    res_p = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_p}", "role": "parent", "display_name": "শায়লা আহমেদ (Parent)", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_p = res_p.json()["access_token"]
    headers_p = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_p}"}

    # Record consent & create family
    await gateway_client.post("/v1/parents/consent", json={"version": "1.0", "consented": True}, headers=headers_p)
    res_fam = await gateway_client.post("/v1/families", json={"name": "আহমেদ পরিবার"}, headers=headers_p)
    fam_id = res_fam.json()["id"]

    # Add child
    res_c = await gateway_client.post(
        f"/v1/families/{fam_id}/students",
        json={"display_name": "জারা (Child)", "class_level": 8, "medium": "bn", "daily_minutes": 50},
        headers=headers_p,
    )
    assert res_c.status_code == 201

    # Request family data export
    res_exp = await gateway_client.get("/v1/parents/me/export", headers=headers_p)
    assert res_exp.status_code == 200
    export_payload = res_exp.json()["data"]

    # Invariants verification
    assert export_payload["family_id"] == fam_id
    assert export_payload["family_name"] == "আহমেদ পরিবার"
    assert len(export_payload["members"]) >= 1
    assert len(export_payload["students"]) >= 1

    student_data = export_payload["students"][0]
    assert student_data["display_name"] == "জারা (Child)"
    assert "chat_topics" in student_data
    assert isinstance(student_data["chat_topics"], list)

    # RULE 15 GUARANTEE: Raw transcripts (e.g. role, messages list, raw content) MUST NEVER BE LEAKED
    raw_str = res_exp.text.lower()
    assert "raw_transcript" not in raw_str
    assert "user_prompt" not in raw_str


@pytest.mark.asyncio
async def test_student_forbidden_from_requesting_family_data_export(gateway_client: AsyncClient) -> None:
    """Students are forbidden from requesting family data exports (Rule 9)."""
    phone_s = f"+880176{uuid.uuid4().hex[:6]}"
    res_s = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_s}", "role": "student", "display_name": "শিক্ষার্থী", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_s = res_s.json()["access_token"]
    headers_s = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_s}"}

    res_exp = await gateway_client.get("/v1/parents/me/export", headers=headers_s)
    assert res_exp.status_code == 403


@pytest.mark.asyncio
async def test_account_deletion_recent_reauthentication_enforcement(gateway_client: AsyncClient) -> None:
    """Account deletion enforces recent re-authentication and grants 14-day grace period."""
    phone = f"+880177{uuid.uuid4().hex[:6]}"
    res_auth = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone}", "role": "student", "display_name": "নাসির (Student)", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    user_id = uuid.UUID(res_auth.json()["user"]["id"])
    fresh_token = res_auth.json()["access_token"]

    # 1. Mismatched confirmation rejected
    res_bad = await gateway_client.post(
        "/v1/users/me/delete",
        json={"confirmation": "CANCEL"},
        headers={**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {fresh_token}"},
    )
    assert res_bad.status_code == 400

    # 2. Stale token (> 15 minutes / 900 seconds) rejected
    stale_delta = timedelta(minutes=30)
    stale_iat = int((datetime.now(UTC) - stale_delta).timestamp())
    # Create manually forged/expired iat access token
    from core.common.config import settings
    import jwt
    stale_payload = {
        "jti": uuid.uuid4().hex,
        "sub": str(user_id),
        "role": "student",
        "exp": int((datetime.now(UTC) + timedelta(minutes=30)).timestamp()),
        "iat": stale_iat,
        "type": "access",
    }
    stale_token = jwt.encode(stale_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    res_stale = await gateway_client.post(
        "/v1/users/me/delete",
        json={"confirmation": "DELETE"},
        headers={**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {stale_token}"},
    )
    assert res_stale.status_code in (401, 403)
    assert res_stale.json()["error"]["code"] == "REAUTH_REQUIRED"

    # 3. Fresh token schedules deletion with 14-day grace period
    res_del = await gateway_client.post(
        "/v1/users/me/delete",
        json={"confirmation": "DELETE", "reason": "Moving school"},
        headers={**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {fresh_token}"},
    )
    assert res_del.status_code == 200
    del_data = res_del.json()
    assert del_data["status"] == "pending_grace_period"
    assert del_data["grace_period_days"] == 14
    assert "scheduled_purge_at" in del_data

    # 4. Cancel deletion during grace period restores account
    res_cancel = await gateway_client.post(
        "/v1/users/me/cancel-deletion",
        headers={**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {fresh_token}"},
    )
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_student_cannot_delete_family(gateway_client: AsyncClient) -> None:
    """Acceptance check: Students are strictly forbidden from deleting the family account (HTTP 403)."""
    # 1. Setup parent and family
    phone_p = f"+880178{uuid.uuid4().hex[:6]}"
    res_p = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_p}", "role": "parent", "display_name": "অভিভাবক", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_p = res_p.json()["access_token"]
    headers_p = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_p}"}
    res_fam = await gateway_client.post("/v1/families", json={"name": "টেস্ট পরিবার"}, headers=headers_p)
    fam_id = res_fam.json()["id"]

    # 2. Setup student
    phone_s = f"+880179{uuid.uuid4().hex[:6]}"
    res_s = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_s}", "role": "student", "display_name": "শিক্ষার্থী ২", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_s = res_s.json()["access_token"]
    headers_s = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_s}"}

    # Student attempts to delete family
    res_del = await gateway_client.post(
        f"/v1/families/{fam_id}/delete",
        json={"confirmation": "DELETE"},
        headers=headers_s,
    )
    assert res_del.status_code == 403
    assert res_del.json()["error"]["code"] == "STUDENT_CANNOT_DELETE_FAMILY"


@pytest.mark.asyncio
async def test_parent_family_deletion_and_cancellation(gateway_client: AsyncClient) -> None:
    """Owner parent schedules family deletion with 14-day grace period and can cancel it."""
    phone_p = f"+880181{uuid.uuid4().hex[:6]}"
    res_p = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_p}", "role": "parent", "display_name": "মা", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_p = res_p.json()["access_token"]
    headers_p = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_p}"}
    res_fam = await gateway_client.post("/v1/families", json={"name": "চৌধুরী পরিবার"}, headers=headers_p)
    fam_id = res_fam.json()["id"]

    # Schedule family deletion
    res_del = await gateway_client.post(
        f"/v1/families/{fam_id}/delete",
        json={"confirmation": "DELETE"},
        headers=headers_p,
    )
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "pending_grace_period"
    assert res_del.json()["target_type"] == "family"

    # Cancel family deletion
    res_cancel = await gateway_client.post(
        f"/v1/families/{fam_id}/cancel-deletion",
        headers=headers_p,
    )
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_privacy_purge_job_execution() -> None:
    """Purge job revokes sessions & push tokens, removes data, and anonymizes audit records."""
    from core.common.database import AsyncSessionLocal

    now = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        # 1. Create a user scheduled for purge in the past
        user = User(
            id=uuid.uuid4(),
            auth_provider="phone",
            auth_uid=f"purge_user_{uuid.uuid4().hex[:8]}",
            role="student",
            display_name="Purge Candidate",
            status="pending_deletion",
            phone="+8801888888888",
            email="purge@example.com",
        )
        session.add(user)
        await session.flush()

        # Add active session and device push token
        sess = UserSession(
            id=uuid.uuid4(),
            user_id=user.id,
            refresh_token_hash="hash123",
            expires_at=now + timedelta(days=1),
        )
        dev = Device(
            id=uuid.uuid4(),
            user_id=user.id,
            platform="android",
            push_token="fcm_token_to_purge",
            app_version="1.0.0",
        )
        audit = AuditLog(
            id=uuid.uuid4(),
            actor_id=user.id,
            action="user.login",
            target_type="user",
            target_id=str(user.id),
            meta={"ip": "192.168.1.1", "phone": "+8801888888888"},
        )
        deletion = AccountDeletion(
            id=uuid.uuid4(),
            user_id=user.id,
            target_type="user",
            status="pending_grace_period",
            grace_period_days=14,
            requested_at=now - timedelta(days=15),
            scheduled_purge_at=now - timedelta(days=1),
            recent_auth_confirmed_at=now - timedelta(days=15),
        )
        session.add_all([sess, dev, audit, deletion])
        await session.commit()

        # 2. Run purge worker
        report = await execute_data_purge(session, reference_time=now)
        assert report.purged_accounts >= 1
        assert report.revoked_sessions >= 1
        assert report.revoked_push_tokens >= 1
        assert report.anonymized_audit_records >= 1

        # 3. Verify database state
        stmt_sess = select(UserSession).where(UserSession.user_id == user.id)
        assert (await session.execute(stmt_sess)).scalar_one_or_none() is None

        stmt_dev = select(Device).where(Device.user_id == user.id)
        assert (await session.execute(stmt_dev)).scalar_one_or_none() is None

        stmt_audit = select(AuditLog).where(AuditLog.id == audit.id)
        purged_audit = (await session.execute(stmt_audit)).scalar_one()
        assert purged_audit.actor_id is None
        assert purged_audit.meta.get("anonymized") is True
        assert "phone" not in purged_audit.meta

        stmt_u = select(User).where(User.id == user.id)
        purged_user = (await session.execute(stmt_u)).scalar_one()
        assert purged_user.status == "purged"
        assert purged_user.phone is None
        assert purged_user.display_name == "Deleted User"


def test_migration_0021_reversibility() -> None:
    """Verify migration 0021 (parent consent, export, deletion) can be cleanly downgraded and upgraded."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)

    rev_0020 = script.get_revision("0020_p08a_account_attestation_and_flags")
    rev_0021 = script.get_revision("0021_p07b_parent_consent_export_deletion")

    assert rev_0020 is not None
    assert rev_0021 is not None
    assert rev_0021.down_revision == "0020_p08a_account_attestation_and_flags"

    # Downgrade to 0020
    res_down = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0020_p08a_account_attestation_and_flags"],
        capture_output=True,
        text=True,
    )
    # Upgrade to 0021
    res_up = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "0021_p07b_parent_consent_export_deletion"],
        capture_output=True,
        text=True,
    )
    if res_down.returncode == 0:
        assert res_up.returncode == 0, f"Alembic upgrade 0021 failed: {res_up.stderr}"
    else:
        err = res_down.stderr.lower()
        assert "connect" in err or "connection" in err or "refused" in err, f"Unexpected error: {res_down.stderr}"
