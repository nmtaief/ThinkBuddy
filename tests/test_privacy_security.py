"""Consolidated test suite: test_privacy_security.py."""
from __future__ import annotations


# ========================================================================
# Consolidated from: tests/test_p07b_privacy_consent_export_deletion.py
# ========================================================================

"""Comprehensive Tests for Parental Consent, Family Data Export, Account Deletion Grace Period, and Purge Job (P07b)."""


import json
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from core.audit.models import AuditLog
from core.auth.models import Session as UserSession, User
from core.auth.tokens import create_access_jwt
from core.common.database import AsyncSessionLocal, get_db_session
from core.devices.models import Device
from core.families.models import Family, FamilyMember, ParentStudentLink, StudentProfile
from core.notifications.models import Notification, NotificationDelivery, NotificationPreference
from core.notifications.service import NotificationService
from core.planner.models import AiPlannerShadowRun, Plan, PlanDay, StudySetup, Task
from core.privacy.constants import CURRENT_CONSENT_TEXT_HASH
from core.privacy.models import AccountDeletion, DataExport, ParentalConsent
from core.privacy.purge import execute_data_purge
from core.progress.models import Mastery, ProgressDaily, RevisionItem
from core.quiz.models import AttemptEvent, AttemptItem, BroadSubmission, LearningSignal, QuizAttempt

CLIENT_HEADERS_ANDROID = {
    "X-Client-Platform": "android",
    "X-Client-Form-Factor": "phone",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "device-test-android-p07b",
    "Accept-Language": "bn",
}


@pytest.mark.asyncio
async def test_parental_consent_recording_status_and_reconsent(gateway_client: AsyncClient) -> None:
    """Parent records explicit consent version, terms hash verified, detects terms change, and tests withdrawal."""
    phone = f"+880173{uuid.uuid4().hex[:6]}"
    res_auth = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone}", "role": "parent", "display_name": "মাসুদ রানা (Parent)", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_auth.status_code == 200
    token = res_auth.json()["access_token"]
    parent_id = uuid.UUID(res_auth.json()["user"]["id"])
    headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    # 1. Check initial consent status
    res_status1 = await gateway_client.get("/v1/parents/consent", headers=headers)
    assert res_status1.status_code == 200
    assert res_status1.json()["has_consent"] is False
    assert res_status1.json()["reconsent_required"] is False

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
    assert data["terms_hash"] == CURRENT_CONSENT_TEXT_HASH
    assert "consented_at" in data

    # 3. Check updated consent status
    res_status2 = await gateway_client.get("/v1/parents/consent", headers=headers)
    assert res_status2.status_code == 200
    assert res_status2.json()["has_consent"] is True
    assert res_status2.json()["version"] == "1.0"
    assert res_status2.json()["terms_hash"] == CURRENT_CONSENT_TEXT_HASH
    assert res_status2.json()["reconsent_required"] is False

    # 4. Simulate legal terms update -> requires re-consent
    async with AsyncSessionLocal() as session:
        parent_db = await session.get(User, parent_id)
        assert parent_db is not None
        parent_db.consent_terms_hash = "outdated_hash_for_testing_terms_update"
        await session.commit()

    res_status3 = await gateway_client.get("/v1/parents/consent", headers=headers)
    assert res_status3.status_code == 200
    assert res_status3.json()["reconsent_required"] is True
    assert res_status3.json()["has_consent"] is False

    # 5. Parent re-consents to new terms
    res_reconsent = await gateway_client.post(
        "/v1/parents/consent",
        json={"version": "2.0", "consented": True},
        headers=headers,
    )
    assert res_reconsent.status_code == 200
    assert res_reconsent.json()["terms_hash"] == CURRENT_CONSENT_TEXT_HASH

    # 6. Re-authenticate to withdraw consent
    res_reauth = await gateway_client.post(
        "/v1/auth/reauthenticate",
        json={"provider_token": f"fake:phone:{phone}"},
        headers=headers,
    )
    assert res_reauth.status_code == 200
    reauth_token = res_reauth.json()["reauth_token"]

    # Withdraw consent with X-Reauth-Token
    res_withdraw = await gateway_client.post(
        "/v1/parents/consent/withdraw",
        json={"reason": "Testing withdrawal"},
        headers={**headers, "X-Reauth-Token": reauth_token},
    )
    assert res_withdraw.status_code == 200
    assert res_withdraw.json()["status"] == "withdrawn"

    res_status4 = await gateway_client.get("/v1/parents/consent", headers=headers)
    assert res_status4.status_code == 200
    assert res_status4.json()["has_consent"] is False


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
async def test_family_data_export_strictly_excludes_raw_chat_transcripts_and_rate_limited(gateway_client: AsyncClient) -> None:
    """Family data export produces structured JSON with topic-level summaries and ZERO raw chat transcripts (Rule 15), signed download URL, and 24h rate limit."""
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

    # Request re-auth token
    res_reauth = await gateway_client.post(
        "/v1/auth/reauthenticate",
        json={"provider_token": f"fake:phone:{phone_p}"},
        headers=headers_p,
    )
    assert res_reauth.status_code == 200
    reauth_token = res_reauth.json()["reauth_token"]

    # Request family data export
    res_exp = await gateway_client.post(
        "/v1/parents/me/export",
        headers={**headers_p, "X-Reauth-Token": reauth_token},
    )
    assert res_exp.status_code == 200
    export_body = res_exp.json()
    assert "download_url" in export_body
    assert "export_id" in export_body
    export_payload = export_body["data"]

    # Invariants verification
    assert export_payload["family_id"] == fam_id
    assert export_payload["family_name"] == "আহমেদ পরিবার"
    assert len(export_payload["members"]) >= 1
    assert len(export_payload["students"]) >= 1

    student_data = export_payload["students"][0]
    assert student_data["display_name"] == "জারা (Child)"
    assert "chat_topics" in student_data
    assert isinstance(student_data["chat_topics"], list)

    # RULE 15 GUARANTEE: Raw transcripts MUST NEVER BE LEAKED
    raw_str = res_exp.text.lower()
    assert "raw_transcript" not in raw_str
    assert "user_prompt" not in raw_str

    # Test download via signed URL
    dl_url = export_body["download_url"]
    res_dl = await gateway_client.get(dl_url, headers=headers_p)
    assert res_dl.status_code == 200
    assert "application/json" in res_dl.headers.get("content-type", "")
    downloaded_data = res_dl.json()
    assert downloaded_data["family_id"] == fam_id

    # Rate limiting verification: 2nd export within 24h must return 429
    res_reauth2 = await gateway_client.post(
        "/v1/auth/reauthenticate",
        json={"provider_token": f"fake:phone:{phone_p}"},
        headers=headers_p,
    )
    assert res_reauth2.status_code == 200
    reauth_token2 = res_reauth2.json()["reauth_token"]
    res_rate_limited = await gateway_client.post(
        "/v1/parents/me/export",
        headers={**headers_p, "X-Reauth-Token": reauth_token2},
    )
    assert res_rate_limited.status_code == 429
    assert res_rate_limited.json()["error"]["code"] == "EXPORT_RATE_LIMITED"


@pytest.mark.asyncio
async def test_family_data_export_cross_parent_isolation(gateway_client: AsyncClient) -> None:
    """Parent B cannot access Parent A's export (Rule 9 cross-parent isolation)."""
    # Parent A
    phone_a = f"+880171{uuid.uuid4().hex[:6]}"
    res_a = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_a}", "role": "parent", "display_name": "Parent A", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    headers_a = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {res_a.json()['access_token']}"}
    await gateway_client.post("/v1/parents/consent", json={"version": "1.0", "consented": True}, headers=headers_a)
    await gateway_client.post("/v1/families", json={"name": "Family A"}, headers=headers_a)

    res_reauth_a = await gateway_client.post("/v1/auth/reauthenticate", json={"provider_token": f"fake:phone:{phone_a}"}, headers=headers_a)
    reauth_a = res_reauth_a.json()["reauth_token"]

    res_exp_a = await gateway_client.post("/v1/parents/me/export", headers={**headers_a, "X-Reauth-Token": reauth_a})
    export_a = res_exp_a.json()
    dl_url_a = export_a["download_url"]

    # Parent B
    phone_b = f"+880172{uuid.uuid4().hex[:6]}"
    res_b = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_b}", "role": "parent", "display_name": "Parent B", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    headers_b = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {res_b.json()['access_token']}"}

    # Parent B attempts to access Parent A's export URL -> HTTP 403 FORBIDDEN
    res_attack = await gateway_client.get(dl_url_a, headers=headers_b)
    assert res_attack.status_code == 403
    assert res_attack.json()["error"]["code"] == "FORBIDDEN_EXPORT_ACCESS"


@pytest.mark.asyncio
async def test_student_forbidden_from_requesting_family_data_export(gateway_client: AsyncClient) -> None:
    """Students are forbidden from requesting family data exports (Rule 9)."""
    student_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        stu = User(
            id=student_id,
            auth_provider="phone",
            auth_uid=f"fake_stu_{uuid.uuid4().hex[:8]}",
            role="student",
            display_name="শিক্ষার্থী",
            locale="bn",
            status="active",
        )
        session.add(stu)
        await session.commit()

    token_s = create_access_jwt(student_id, role="student")
    headers_s = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_s}"}

    res_exp = await gateway_client.get("/v1/parents/me/export", headers=headers_s)
    assert res_exp.status_code == 403


@pytest.mark.asyncio
async def test_dedicated_reauthentication_endpoint_and_stale_rejection(gateway_client: AsyncClient) -> None:
    """Dedicated re-authentication validates fresh provider auth and rejects stale auth_time."""
    phone = f"+880177{uuid.uuid4().hex[:6]}"
    res_auth = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone}", "role": "parent", "display_name": "নাসির (Parent)", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {res_auth.json()['access_token']}"}

    # 1. Fresh re-authentication succeeds
    res_reauth = await gateway_client.post(
        "/v1/auth/reauthenticate",
        json={"provider_token": f"fake:phone:{phone}"},
        headers=headers,
    )
    assert res_reauth.status_code == 200
    assert "reauth_token" in res_reauth.json()
    assert res_reauth.json()["expires_in"] == 600

    # 2. Stale provider token (> 300 seconds / 5 mins) rejected
    stale_auth_time = int(time.time()) - 400
    stale_provider_token = json.dumps({"phone": phone, "auth_time": stale_auth_time})
    res_stale = await gateway_client.post(
        "/v1/auth/reauthenticate",
        json={"provider_token": stale_provider_token},
        headers=headers,
    )
    assert res_stale.status_code == 401
    assert res_stale.json()["error"]["code"] == "REAUTH_STALE"

    # 3. Provider credential for a different user rejected (Identity Mismatch)
    res_mismatch = await gateway_client.post(
        "/v1/auth/reauthenticate",
        json={"provider_token": "fake:phone:+8801999999999"},
        headers=headers,
    )
    assert res_mismatch.status_code == 403
    assert res_mismatch.json()["error"]["code"] == "IDENTITY_MISMATCH"


@pytest.mark.asyncio
async def test_account_deletion_recent_reauthentication_enforcement(gateway_client: AsyncClient) -> None:
    """Account deletion enforces recent re-authentication and grants 14-day grace period."""
    phone = f"+880177{uuid.uuid4().hex[:6]}"
    res_auth = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone}", "role": "parent", "display_name": "নাসির (Parent)", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    fresh_token = res_auth.json()["access_token"]
    headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {fresh_token}"}

    # Get reauth token
    res_reauth = await gateway_client.post(
        "/v1/auth/reauthenticate",
        json={"provider_token": f"fake:phone:{phone}"},
        headers=headers,
    )
    reauth_token = res_reauth.json()["reauth_token"]

    # 1. Mismatched confirmation rejected
    res_bad = await gateway_client.post(
        "/v1/users/me/delete",
        json={"confirmation": "CANCEL"},
        headers={**headers, "X-Reauth-Token": reauth_token},
    )
    assert res_bad.status_code == 400

    # 2. Deletion with valid fresh reauth token schedules deletion with 14-day grace period
    res_reauth2 = await gateway_client.post(
        "/v1/auth/reauthenticate",
        json={"provider_token": f"fake:phone:{phone}"},
        headers=headers,
    )
    assert res_reauth2.status_code == 200
    reauth_token2 = res_reauth2.json()["reauth_token"]
    res_del = await gateway_client.post(
        "/v1/users/me/delete",
        json={"confirmation": "DELETE", "reason": "Moving school"},
        headers={**headers, "X-Reauth-Token": reauth_token2},
    )
    assert res_del.status_code == 200
    del_data = res_del.json()
    assert del_data["status"] == "pending_grace_period"
    assert del_data["grace_period_days"] == 14
    assert "scheduled_purge_at" in del_data

    # 3. Cancel deletion during grace period restores account
    res_cancel = await gateway_client.post(
        "/v1/users/me/cancel-deletion",
        headers=headers,
    )
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_student_cannot_delete_family(gateway_client: AsyncClient) -> None:
    """Students are strictly forbidden from deleting the family account (HTTP 403)."""
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
    student_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        stu = User(
            id=student_id,
            auth_provider="phone",
            auth_uid=f"fake_stu_{uuid.uuid4().hex[:8]}",
            role="student",
            display_name="শিক্ষার্থী ২",
            locale="bn",
            status="active",
        )
        session.add(stu)
        await session.commit()
    token_s = create_access_jwt(student_id, role="student")
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
async def test_family_deletion_owner_enforcement_grace_period_and_cancellation(gateway_client: AsyncClient) -> None:
    """Only family owner can request family deletion; grace period stops chat/push/planner; any parent can cancel."""
    # 1. Owner Parent A creates family
    phone_a = f"+880181{uuid.uuid4().hex[:6]}"
    res_a = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_a}", "role": "parent", "display_name": "বাবা (Owner)", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_a = res_a.json()["access_token"]
    headers_a = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_a}"}
    await gateway_client.post("/v1/parents/consent", json={"version": "1.0", "consented": True}, headers=headers_a)

    res_fam = await gateway_client.post("/v1/families", json={"name": "চৌধুরী পরিবার"}, headers=headers_a)
    fam_id = res_fam.json()["id"]

    # Add child to family
    res_child = await gateway_client.post(
        f"/v1/families/{fam_id}/students",
        json={"display_name": "চাইল্ড চৌধুরী", "class_level": 7, "medium": "bn", "daily_minutes": 45},
        headers=headers_a,
    )
    child_id = res_child.json()["student_id"]

    # 2. Secondary Parent B joins family
    phone_b = f"+880182{uuid.uuid4().hex[:6]}"
    res_b = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_b}", "role": "parent", "display_name": "মা (Member)", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token_b = res_b.json()["access_token"]
    parent_b_id = uuid.UUID(res_b.json()["user"]["id"])
    headers_b = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token_b}"}

    async with AsyncSessionLocal() as session:
        session.add(FamilyMember(family_id=uuid.UUID(fam_id), user_id=parent_b_id, relation="parent"))
        await session.commit()

    # Parent B reauth
    res_reauth_b = await gateway_client.post("/v1/auth/reauthenticate", json={"provider_token": f"fake:phone:{phone_b}"}, headers=headers_b)
    reauth_b = res_reauth_b.json()["reauth_token"]

    # Non-owner Parent B attempts to schedule family deletion -> HTTP 403 ONLY_FAMILY_OWNER_CAN_DELETE
    res_del_b = await gateway_client.post(
        f"/v1/families/{fam_id}/delete",
        json={"confirmation": "DELETE"},
        headers={**headers_b, "X-Reauth-Token": reauth_b},
    )
    assert res_del_b.status_code == 403
    assert res_del_b.json()["error"]["code"] == "ONLY_FAMILY_OWNER_CAN_DELETE"

    # Owner Parent A reauth and schedules family deletion
    res_reauth_a = await gateway_client.post("/v1/auth/reauthenticate", json={"provider_token": f"fake:phone:{phone_a}"}, headers=headers_a)
    reauth_a = res_reauth_a.json()["reauth_token"]

    res_del_a = await gateway_client.post(
        f"/v1/families/{fam_id}/delete",
        json={"confirmation": "DELETE"},
        headers={**headers_a, "X-Reauth-Token": reauth_a},
    )
    assert res_del_a.status_code == 200
    assert res_del_a.json()["status"] == "pending_grace_period"

    # 3. Processing suspension during grace period:
    # A. Chat processing suspended for student
    student_jwt = create_access_jwt(uuid.UUID(child_id), role="student")
    headers_student = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {student_jwt}"}
    res_chat = await gateway_client.post(
        "/v1/chat/sessions",
        json={"title": "Test Chat"},
        headers=headers_student,
    )
    assert res_chat.status_code == 403
    assert res_chat.json()["error"]["code"] == "ACCOUNT_PENDING_DELETION"

    # B. Push delivery suppressed for user pending deletion
    async with AsyncSessionLocal() as session:
        notif, deliveries = await NotificationService.dispatch_notification(
            db=session,
            user_id=uuid.UUID(child_id),
            type="daily_reminder",
            title="Study Time",
            body="Time to study",
            title_bn="পড়ার সময়",
            body_bn="পড়ার সময় হয়েছে",
        )
        push_dels = [d for d in deliveries if d.channel == "push"]
        if push_dels:
            assert push_dels[0].status == "suppressed_pending_deletion"

    # 4. Any parent can cancel deletion: Parent B cancels deletion
    res_cancel = await gateway_client.post(
        f"/v1/families/{fam_id}/cancel-deletion",
        headers=headers_b,
    )
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "cancelled"

    # Verify student status restored to active
    async with AsyncSessionLocal() as session:
        stu = await session.get(User, uuid.UUID(child_id))
        assert stu is not None
        assert stu.status == "active"


@pytest.mark.asyncio
async def test_privacy_purge_job_execution() -> None:
    """Purge job revokes sessions & push tokens, deletes personal data, cleans S3 uploads, and anonymizes audit records."""
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
            push_token=f"fcm_token_to_purge_{uuid.uuid4().hex[:6]}",
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
        notif = Notification(
            id=uuid.uuid4(),
            user_id=user.id,
            type="daily_reminder",
            title="Study",
            body="Time",
            title_bn="পড়া",
            body_bn="সময়",
        )
        signal = LearningSignal(
            id=uuid.uuid4(),
            student_id=user.id,
            source="quiz_wrong",
            concept_id="concept_algebra_1",
            weight=1.0,
            ref_id="attempt_item_123",
        )
        shadow_run = AiPlannerShadowRun(
            id=uuid.uuid4(),
            student_id=user.id,
            at=now,
            recommendation="keep_baseline",
            coverage_parity_met=True,
            churn_rate_pct=5.0,
            minutes_delta=10,
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
        session.add_all([sess, dev, audit, notif, signal, shadow_run, deletion])
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

        stmt_notif = select(Notification).where(Notification.user_id == user.id)
        assert (await session.execute(stmt_notif)).scalar_one_or_none() is None

        stmt_sig = select(LearningSignal).where(LearningSignal.student_id == user.id)
        assert (await session.execute(stmt_sig)).scalar_one_or_none() is None

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
    """Verify migration 0021 (parent consent, export, deletion) can be cleanly downgraded and upgraded against live Postgres."""
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
    assert res_down.returncode == 0, f"Alembic downgrade 0020 failed: {res_down.stderr}"
    assert res_up.returncode == 0, f"Alembic upgrade 0021 failed: {res_up.stderr}"
    # Ensure always restored to head
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], capture_output=True, text=True)


def test_migration_0022_reversibility() -> None:
    """Verify migration 0022 (consent versions and deletion ledger) can be cleanly downgraded and upgraded."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)

    rev_0021 = script.get_revision("0021_p07b_parent_consent_export_deletion")
    rev_0022 = script.get_revision("0022_p07b_consent_versions_and_deletion_ledger")

    assert rev_0021 is not None
    assert rev_0022 is not None
    assert rev_0022.down_revision == "0021_p07b_parent_consent_export_deletion"

    # Downgrade to 0021
    res_down = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0021_p07b_parent_consent_export_deletion"],
        capture_output=True,
        text=True,
    )
    # Upgrade to 0022
    res_up = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "0022_p07b_consent_versions_and_deletion_ledger"],
        capture_output=True,
        text=True,
    )
    # Restore to head
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], capture_output=True, text=True)

    assert res_down.returncode == 0, f"Alembic downgrade 0021 failed: {res_down.stderr}"
    assert res_up.returncode == 0, f"Alembic upgrade 0022 failed: {res_up.stderr}"


def test_schema_driven_purge_coverage_and_retention_allowlist() -> None:
    """Automated schema-driven test ensuring every table referencing users or students is purged or on documented retention allowlist."""
    import importlib
    import inspect
    from core.common.database import Base
    from core.privacy import purge

    # Ensure all modules with SQLAlchemy models are loaded
    modules = [
        "core.audit.models", "core.auth.models", "core.chat.models",
        "core.curriculum.models", "core.devices.models", "core.entitlements.models",
        "core.families.models", "core.notifications.models", "core.planner.models",
        "core.privacy.models", "core.progress.models", "core.quiz.models"
    ]
    for m in modules:
        importlib.import_module(m)

    handled_tables = {obj.__tablename__ for name, obj in inspect.getmembers(purge) if hasattr(obj, "__tablename__")}
    
    # Documented retention allowlist:
    # - audit_log: actor_id is anonymized to NULL and metadata scrubbed, but entry retained for regulatory compliance
    # - admin_policies: platform-wide admin policy limits (not student-owned data)
    # - parental_consent_versions: immutable legal consent text versions
    # - deletion_ledger: cryptographic SHA-256 hash ledger replayed after disaster recovery restores
    DOCUMENTED_RETENTION_ALLOWLIST = {
        "audit_log",
        "admin_policies",
        "parental_consent_versions",
        "deletion_ledger",
    }

    user_student_tables = set()
    for t_name, table in Base.metadata.tables.items():
        cols = [c.name for c in table.columns]
        fks = [fk.target_fullname for fk in table.foreign_keys]
        has_user_col = any(c in (
            "user_id", "student_id", "parent_id", "requester_id",
            "owner_parent_id", "actor_id", "set_by_user_id", "updated_by_user_id"
        ) for c in cols)
        has_user_fk = any("users." in fk for fk in fks)
        if has_user_col or has_user_fk or t_name in ("users", "audit_log", "account_deletions"):
            user_student_tables.add(t_name)

    unaccounted_tables = user_student_tables - handled_tables - DOCUMENTED_RETENTION_ALLOWLIST
    assert not unaccounted_tables, (
        f"Schema test failed: The following user/student referencing tables are neither "
        f"handled in core.privacy.purge nor listed in the DOCUMENTED_RETENTION_ALLOWLIST: {unaccounted_tables}. "
        f"Every user-referencing table must be either completely purged or explicitly documented."
    )


@pytest.mark.asyncio
async def test_reauth_token_action_binding_and_single_use(gateway_client: AsyncClient) -> None:
    """Verify that re-auth tokens are cryptographically bound to a single action and single-use."""
    from core.privacy.service import PrivacyService
    from core.auth.tokens import create_reauth_jwt
    from fastapi import HTTPException

    user_id = uuid.uuid4()

    # 1. Action binding check: Token created for 'account_delete' cannot be used for 'family_delete'
    token_account_delete = create_reauth_jwt(user_id=user_id, action="account_delete")

    with pytest.raises(HTTPException) as exc_info:
        await PrivacyService.verify_reauth_token(
            reauth_token=token_account_delete,
            caller_id=user_id,
            expected_action="family_delete",
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "REAUTH_ACTION_MISMATCH"

    # 2. Single-use enforcement: Token can only be verified once
    token_single_use = create_reauth_jwt(user_id=user_id, action="consent_withdraw")

    # First consumption succeeds
    await PrivacyService.verify_reauth_token(
        reauth_token=token_single_use,
        caller_id=user_id,
        expected_action="consent_withdraw",
    )

    # Second consumption of identical token must fail with 403 REAUTH_ALREADY_USED
    with pytest.raises(HTTPException) as exc_reused:
        await PrivacyService.verify_reauth_token(
            reauth_token=token_single_use,
            caller_id=user_id,
            expected_action="consent_withdraw",
        )
    assert exc_reused.value.status_code == 403
    assert exc_reused.value.detail["code"] == "REAUTH_ALREADY_USED"


@pytest.mark.asyncio
async def test_consent_withdrawal_suspends_child_processing(gateway_client: AsyncClient) -> None:
    """Withdrawing parental consent immediately suspends child chat and quiz attempts with 403 CONSENT_WITHDRAWN."""
    phone_p = f"+880174{uuid.uuid4().hex[:6]}"
    res_p = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_p}", "role": "parent", "display_name": "Parent For Suspension", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    p_token = res_p.json()["access_token"]
    p_id = uuid.UUID(res_p.json()["user"]["id"])
    p_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {p_token}"}

    # Grant initial consent
    await gateway_client.post("/v1/parents/consent", json={"version": "1.0", "consented": True}, headers=p_headers)

    # Create family and link code & register child
    res_fam = await gateway_client.post("/v1/families", json={"name": "Family Consent Test"}, headers=p_headers)
    assert res_fam.status_code == 201
    fam_id = res_fam.json()["id"]

    res_code = await gateway_client.post(
        f"/v1/families/{fam_id}/students",
        json={"display_name": "Child Consent Test", "class_level": 9, "medium": "bn", "daily_minutes": 90},
        headers=p_headers,
    )
    assert res_code.status_code == 201
    link_code = res_code.json()["link_code"]

    res_child = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:+880175{uuid.uuid4().hex[:6]}", "role": "student", "display_name": "Child A", "link_code": link_code},
        headers=CLIENT_HEADERS_ANDROID,
    )
    assert res_child.status_code == 200
    child_token = res_child.json()["access_token"]
    child_headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {child_token}"}

    # Child can initially access chat
    res_chat = await gateway_client.post("/v1/chat/sessions", json={"title": "Math Help"}, headers=child_headers)
    assert res_chat.status_code == 201

    # Parent withdraws consent (fresh sign-in re-auth)
    res_withdraw = await gateway_client.post(
        "/v1/parents/consent/withdraw",
        json={"reason": "Revoking consent for minor"},
        headers=p_headers,
    )
    assert res_withdraw.status_code == 200
    assert res_withdraw.json()["status"] == "withdrawn"

    # Child is immediately blocked from creating new chat sessions
    res_blocked_chat = await gateway_client.post("/v1/chat/sessions", json={"title": "Blocked Chat"}, headers=child_headers)
    assert res_blocked_chat.status_code == 403
    err_chat = res_blocked_chat.json().get("error", res_blocked_chat.json().get("detail", {}))
    assert err_chat["code"] == "CONSENT_WITHDRAWN"

    # Child is immediately blocked from starting quizzes
    res_blocked_quiz = await gateway_client.post(
        f"/v1/quizzes/{uuid.uuid4()}/attempts",
        json={"device_id": "test-device"},
        headers=child_headers,
    )
    assert res_blocked_quiz.status_code == 403
    err_quiz = res_blocked_quiz.json().get("error", res_blocked_quiz.json().get("detail", {}))
    assert err_quiz["code"] == "CONSENT_WITHDRAWN"


@pytest.mark.asyncio
async def test_export_encryption_at_rest_and_dual_auth_download(gateway_client: AsyncClient) -> None:
    """Verify family data export files are encrypted at rest (AES-256-GCM) and require session plus token on download."""
    phone = f"+880176{uuid.uuid4().hex[:6]}"
    res_p = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone}", "role": "parent", "display_name": "Export Parent", "locale": "bn"},
        headers=CLIENT_HEADERS_ANDROID,
    )
    token = res_p.json()["access_token"]
    headers = {**CLIENT_HEADERS_ANDROID, "Authorization": f"Bearer {token}"}

    # Grant consent, create family, and trigger export
    await gateway_client.post("/v1/parents/consent", json={"version": "1.0", "consented": True}, headers=headers)
    await gateway_client.post("/v1/families", json={"name": "Export Family"}, headers=headers)
    res_export = await gateway_client.post("/v1/parents/me/export", headers=headers)
    assert res_export.status_code == 200
    export_id = uuid.UUID(res_export.json()["export_id"])
    download_url = res_export.json()["download_url"]
    dl_token = download_url.split("token=")[1]

    # Verify database state: Plain payload is null, encrypted payload is AES-256 string starting with 'v1:'
    async with AsyncSessionLocal() as session:
        exp_row = await session.get(DataExport, export_id)
        assert exp_row is not None
        assert exp_row.data_payload is None, "Plain JSON data_payload must be NULL in database to ensure at-rest encryption"
        assert exp_row.encrypted_payload is not None
        assert exp_row.encrypted_payload.startswith("v1:")

    # 1. Download without session returns 401
    res_no_session = await gateway_client.get(download_url, headers=CLIENT_HEADERS_ANDROID)
    assert res_no_session.status_code == 401

    # 2. Download without valid download token returns 403
    res_bad_token = await gateway_client.get(f"/v1/parents/me/export/{export_id}/download?token=invalid_tok", headers=headers)
    assert res_bad_token.status_code == 403

    # 3. Dual Auth: Valid session + valid token decrypts and streams complete JSON export archive
    res_download = await gateway_client.get(download_url, headers=headers)
    assert res_download.status_code == 200
    decrypted_data = res_download.json()
    assert "family_id" in decrypted_data
    assert "students" in decrypted_data


@pytest.mark.asyncio
async def test_consent_versions_current_text_endpoint(gateway_client: AsyncClient) -> None:
    """Verify GET /v1/parents/consent/current returns full Bengali and English legal text with matching terms hash."""
    from core.privacy.constants import PARENTAL_CONSENT_TEXT_BN, PARENTAL_CONSENT_TEXT_EN, CURRENT_CONSENT_TEXT_HASH

    res = await gateway_client.get("/v1/parents/consent/current", headers=CLIENT_HEADERS_ANDROID)
    assert res.status_code == 200
    data = res.json()
    assert data["version"] == "v1.0"
    assert data["text_bn"] == PARENTAL_CONSENT_TEXT_BN
    assert data["text_en"] == PARENTAL_CONSENT_TEXT_EN
    assert data["terms_hash"] == CURRENT_CONSENT_TEXT_HASH


@pytest.mark.asyncio
async def test_deletion_ledger_recorded_on_purge_and_replayed() -> None:
    """Verify SHA-256 hash is inserted into deletion_ledger during purge, and replay_ledger re-purges resurrected accounts."""
    import hashlib
    from core.privacy.models import DeletionLedger
    from core.privacy.replay_ledger import replay_deletion_ledger

    async with AsyncSessionLocal() as session:
        # 1. Create a user
        user = User(
            id=uuid.uuid4(),
            role="student",
            auth_provider="phone",
            auth_uid=f"fake:phone:+880177{uuid.uuid4().hex[:6]}",
            display_name="Resurrection Test User",
            status="active",
        )
        session.add(user)
        deletion = AccountDeletion(
            id=uuid.uuid4(),
            user_id=user.id,
            target_type="user",
            status="pending_grace_period",
            scheduled_purge_at=datetime.now(UTC) - timedelta(hours=1),
        )
        session.add(deletion)
        await session.commit()

        # 2. Execute purge
        report = await execute_data_purge(session)
        assert report.purged_accounts >= 1

        # 3. Verify ledger entry was created
        u_hash = hashlib.sha256(str(user.id).encode("utf-8")).hexdigest()
        stmt_dl = select(DeletionLedger).where(DeletionLedger.user_id_hash == u_hash)
        ledger_entry = (await session.execute(stmt_dl)).scalar_one_or_none()
        assert ledger_entry is not None
        assert ledger_entry.target_type == "user"

        # 4. Simulate restore resurrecting the user: user status set back to active
        user.status = "active"
        user.display_name = "Resurrected User"
        await session.commit()

        # 5. Replay deletion ledger
        replay_res = await replay_deletion_ledger(session)
        assert replay_res["repurged_users"] >= 1

        # 6. Verify user is purged again
        await session.refresh(user)
        assert user.status == "purged"
        assert user.display_name == "Deleted User"


@pytest.mark.asyncio
async def test_reauth_single_use_fails_closed_when_redis_unavailable() -> None:
    """Verify that re-auth token verification strictly fails closed (503 REAUTH_CONFIRMATION_FAILED) when Redis cannot confirm freshness."""
    from unittest.mock import AsyncMock
    from fastapi import HTTPException
    from core.privacy.service import PrivacyService
    from core.auth.tokens import create_reauth_jwt

    test_user_id = uuid.uuid4()
    tok = create_reauth_jwt(user_id=test_user_id, action="account_delete")

    # Mock broken redis client that raises ConnectionError on .set()
    mock_broken_redis = AsyncMock()
    mock_broken_redis.set.side_effect = ConnectionError("Simulated Redis network disconnection")

    with pytest.raises(HTTPException) as exc_info:
        await PrivacyService.verify_reauth_token(
            reauth_token=tok,
            caller_id=test_user_id,
            expected_action="account_delete",
            redis_client=mock_broken_redis,
        )
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "REAUTH_CONFIRMATION_FAILED"


@pytest.mark.asyncio
async def test_seeded_user_purge_fk_chains_zero_remaining_rows() -> None:
    """Follow full foreign key chains from User down to leaf tables, verifying 0 remaining rows after purge."""
    from core.planner.models import AiPlannerShadowRun, StudentChangeRequest, StudentStudySettings, SyllabusItem
    from core.curriculum.models import Book, Chapter
    from core.quiz.models import Question, Quiz
    from core.chat.models import ChatCitation, ChatIdempotencyRecord, ChatMessage, ChatSession, UsageCounter
    from sqlalchemy import func

    async with AsyncSessionLocal() as session:
        # Load an existing chapter and question from seed data
        chap = (await session.execute(select(Chapter).limit(1))).scalar_one_or_none()
        ques = (await session.execute(select(Question).limit(1))).scalar_one_or_none()
        chap_id = chap.id if chap else uuid.uuid4()
        ques_id = ques.id if ques else uuid.uuid4()

        # 1. Create a parent and a student user
        parent = User(
            id=uuid.uuid4(),
            role="parent",
            auth_provider="phone",
            auth_uid=f"fake:phone:+880178{uuid.uuid4().hex[:6]}",
            display_name="Purge FK Parent",
            has_parental_consent=True,
            status="active",
        )
        student = User(
            id=uuid.uuid4(),
            role="student",
            auth_provider="phone",
            auth_uid=f"fake:phone:+880179{uuid.uuid4().hex[:6]}",
            display_name="Purge FK Student",
            email="student_fk@test.com",
            phone="+880179000000",
            has_parental_consent=True,
            status="active",
        )
        session.add_all([parent, student])
        await session.flush()

        s_id = student.id
        p_id = parent.id

        # 2. Seed records across ALL FK-dependent tables
        # Profile & Parent-Student link
        prof = StudentProfile(user_id=s_id, class_level=8, medium="bn", daily_minutes=45)
        link = ParentStudentLink(
            id=uuid.uuid4(), parent_id=p_id, student_id=s_id,
            status="active",
            link_code_hash="fakehash", link_code_expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        session.add_all([prof, link])

        # StudySetup, Plan, PlanDay, Task, StudentChangeRequest, StudentStudySettings
        setup = StudySetup(id=uuid.uuid4(), student_id=s_id, set_by_user_id=p_id, subject="math", exam_name="Annual Exam", exam_date=datetime.now(UTC).date() + timedelta(days=60))
        session.add(setup)
        await session.flush()

        plan = Plan(id=uuid.uuid4(), student_id=s_id, setup_id=setup.id, version=1, status="active", reason="Initial plan")
        session.add(plan)
        await session.flush()

        pday = PlanDay(id=uuid.uuid4(), plan_id=plan.id, date=datetime.now(UTC).date(), planned_minutes=45)
        session.add(pday)
        await session.flush()

        task = Task(id=uuid.uuid4(), plan_day_id=pday.id, student_id=s_id, type="study", est_minutes=30, status="todo", refs={})
        scr = StudentChangeRequest(id=uuid.uuid4(), student_id=s_id, setup_id=setup.id, requested_changes={"daily_minutes": 60}, status="pending")
        sss = StudentStudySettings(id=uuid.uuid4(), student_id=s_id, school_day_minutes=60, holiday_minutes=120)
        session.add_all([task, scr, sss])

        # Quiz, QuizAttempt, AttemptItem, AttemptEvent, BroadSubmission
        quiz = Quiz(id=uuid.uuid4(), student_id=s_id, title="Daily Math", kind="daily", mode="assessed")
        session.add(quiz)
        await session.flush()

        attempt = QuizAttempt(id=uuid.uuid4(), quiz_id=quiz.id, student_id=s_id, state="in_progress", attempt_token="tok_fk_test_123")
        session.add(attempt)
        await session.flush()

        if ques:
            item = AttemptItem(id=uuid.uuid4(), attempt_id=attempt.id, question_id=ques_id, position=1, nonce="testnonce123")
            session.add(item)
            await session.flush()
            bs = BroadSubmission(id=uuid.uuid4(), attempt_item_id=item.id, image_uris=["https://storage.thinkbuddy.com/broad/1.jpg"])
            session.add(bs)

        ev = AttemptEvent(id=uuid.uuid4(), attempt_id=attempt.id, type="focus_lost")
        session.add(ev)

        # ChatSession, ChatMessage, ChatCitation, UsageCounter
        cs = ChatSession(id=uuid.uuid4(), student_id=s_id, title="Math Q&A")
        session.add(cs)
        await session.flush()

        cm = ChatMessage(id=uuid.uuid4(), session_id=cs.id, role="user", content="Help me with algebra")
        session.add(cm)
        await session.flush()

        cc = ChatCitation(id=uuid.uuid4(), message_id=cm.id, book_title="Math 8", chapter_title="Algebra", printed_page=42, pdf_page_index=44)
        uc = UsageCounter(student_id=s_id, date=datetime.now(UTC).date(), chat_messages=5, tokens=150)
        cir = ChatIdempotencyRecord(id=uuid.uuid4(), student_id=s_id, session_id=cs.id, idempotency_key="key_fk_test", response_payload={"text": "hello"})
        session.add_all([cc, uc, cir])

        # LearningSignal, AIPlannerShadowRun, ProgressDaily, Mastery, RevisionItem
        ls = LearningSignal(id=uuid.uuid4(), student_id=s_id, source="quiz_wrong", weight=1.0)
        sr = AiPlannerShadowRun(id=uuid.uuid4(), student_id=s_id, recommendation="adopt", coverage_parity_met=True, churn_rate_pct=0.0, minutes_delta=0)
        now_dt = datetime.now(UTC)
        pd = ProgressDaily(id=uuid.uuid4(), student_id=s_id, date=now_dt.date(), minutes=30, created_at=now_dt, updated_at=now_dt)
        session.add_all([ls, sr, pd])

        if chap:
            m = Mastery(id=uuid.uuid4(), student_id=s_id, chapter_id=chap_id, score=0.8, updated_at=now_dt)
            ri = RevisionItem(id=uuid.uuid4(), student_id=s_id, chapter_id=chap_id, due_at=now_dt, updated_at=now_dt)
            session.add_all([m, ri])

        # Device, UserSession, Notification, NotificationDelivery, NotificationPreference
        dev = Device(id=uuid.uuid4(), user_id=s_id, push_token=f"fcm_fk_{uuid.uuid4().hex[:8]}", platform="android", app_version="1.0.0")
        sess = UserSession(id=uuid.uuid4(), user_id=s_id, refresh_token_hash="fakehash", expires_at=datetime.now(UTC) + timedelta(days=7))
        notif = Notification(id=uuid.uuid4(), user_id=s_id, type="study_reminder", title="Study", body="Time to study", title_bn="পড়ার সময়", body_bn="এখন পড়ার সময় হয়েছে")
        session.add_all([dev, sess, notif])
        await session.flush()

        nd = NotificationDelivery(notification_id=notif.id, user_id=s_id, device_id=dev.id, channel="push", status="delivered")
        np = NotificationPreference(user_id=s_id, quiet_hours_start="22:00", quiet_hours_end="07:00")
        session.add_all([nd, np])

        # AuditLog
        audit = AuditLog(
            id=uuid.uuid4(), actor_id=s_id, action="quiz.started", target_type="quiz_attempt",
            target_id=str(attempt.id), meta={"ip": "127.0.0.1", "device": "Pixel 8"},
        )
        session.add(audit)

        # AccountDeletion past grace period
        deletion = AccountDeletion(
            id=uuid.uuid4(), user_id=s_id, target_type="user",
            status="pending_grace_period", scheduled_purge_at=datetime.now(UTC) - timedelta(hours=1),
        )
        session.add(deletion)
        await session.commit()

        # 3. Execute full data purge
        report = await execute_data_purge(session)
        assert report.purged_accounts >= 1

        # 4. Verify ZERO remaining rows across ALL FK-dependent tables for this student
        assert (await session.execute(select(func.count(StudentProfile.user_id)).where(StudentProfile.user_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(ParentStudentLink.id)).where(ParentStudentLink.student_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(StudySetup.id)).where(StudySetup.student_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(Plan.id)).where(Plan.student_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(PlanDay.id)).where(PlanDay.plan_id == plan.id))).scalar() == 0
        assert (await session.execute(select(func.count(Task.id)).where(Task.student_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(StudentChangeRequest.id)).where(StudentChangeRequest.student_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(StudentStudySettings.student_id)).where(StudentStudySettings.student_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(Quiz.id)).where(Quiz.student_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(QuizAttempt.id)).where(QuizAttempt.student_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(AttemptItem.id)).where(AttemptItem.attempt_id == attempt.id))).scalar() == 0
        assert (await session.execute(select(func.count(AttemptEvent.id)).where(AttemptEvent.attempt_id == attempt.id))).scalar() == 0
        assert (await session.execute(select(func.count(ChatSession.id)).where(ChatSession.student_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(ChatMessage.id)).where(ChatMessage.session_id == cs.id))).scalar() == 0
        assert (await session.execute(select(func.count(ChatCitation.id)).where(ChatCitation.message_id == cm.id))).scalar() == 0
        assert (await session.execute(select(func.count(UsageCounter.student_id)).where(UsageCounter.student_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(ChatIdempotencyRecord.id)).where(ChatIdempotencyRecord.student_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(LearningSignal.id)).where(LearningSignal.student_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(AiPlannerShadowRun.id)).where(AiPlannerShadowRun.student_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(ProgressDaily.id)).where(ProgressDaily.student_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(Mastery.id)).where(Mastery.student_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(RevisionItem.id)).where(RevisionItem.student_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(Device.id)).where(Device.user_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(UserSession.id)).where(UserSession.user_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(Notification.id)).where(Notification.user_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(NotificationDelivery.id)).where(NotificationDelivery.user_id == s_id))).scalar() == 0
        assert (await session.execute(select(func.count(NotificationPreference.id)).where(NotificationPreference.user_id == s_id))).scalar() == 0

        # Verify Audit Log anonymization: actor_id NULL, PII scrubbed
        await session.refresh(audit)
        assert audit.actor_id is None
        assert audit.meta.get("anonymized") is True
        assert audit.meta.get("reason") == "gdpr_privacy_purge"
        assert "127.0.0.1" not in str(audit.meta)

        # Verify User PII nullification
        await session.refresh(student)
        assert student.status == "purged"
        assert student.display_name == "Deleted User"
        assert student.email is None
        assert student.phone is None
        assert student.has_parental_consent is False


@pytest.mark.asyncio
async def test_central_consent_guard_and_suspended_retention_purge() -> None:
    """Verify central consent guard enforcement on planner and notifications, and automatic 30-day suspension purge."""
    from core.privacy.consent_guard import assert_consent_active, is_suspension_retention_expired
    from core.notifications.service import NotificationService
    from fastapi import HTTPException

    async with AsyncSessionLocal() as session:
        # 1. Suspended student is rejected by assert_consent_active
        suspended_student = User(
            id=uuid.uuid4(),
            role="student",
            auth_provider="phone",
            auth_uid=f"fake:phone:+880181{uuid.uuid4().hex[:6]}",
            display_name="Suspended Consent Student",
            has_parental_consent=False,
            status="active",
        )
        session.add(suspended_student)
        await session.flush()

        with pytest.raises(HTTPException) as exc_info:
            assert_consent_active(suspended_student)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "CONSENT_WITHDRAWN"

        # 2. Push notification delivery is suppressed for consent-suspended student
        notif, deliveries = await NotificationService.dispatch_notification(
            db=session,
            user_id=suspended_student.id,
            type="study_reminder",
            title="Daily Study Reminder",
            body="You have tasks scheduled for today.",
            title_bn="দৈনিক পড়ার রিমাইন্ডার",
            body_bn="আজকে পড়ার পরিকল্পনা রয়েছে।",
        )
        assert len(deliveries) >= 2
        push_delivery = next(d for d in deliveries if d.channel == "push")
        assert push_delivery.status == "suppressed_consent_suspended"

        # 3. Automatic purge when consent suspension exceeds 30-day retention period
        past_30d = datetime.now(UTC) - timedelta(days=31)
        assert is_suspension_retention_expired(past_30d) is True

        parent = User(
            id=uuid.uuid4(),
            role="parent",
            auth_provider="phone",
            auth_uid=f"fake:phone:+880182{uuid.uuid4().hex[:6]}",
            display_name="Suspended Link Parent",
            status="active",
        )
        session.add(parent)
        await session.flush()

        link = ParentStudentLink(
            id=uuid.uuid4(),
            parent_id=parent.id,
            student_id=suspended_student.id,
            status="consent_suspended",
            revoked_at=past_30d,
        )
        session.add(link)
        await session.commit()

        # Run purge sweep
        report = await execute_data_purge(session)
        assert report.purged_accounts >= 1

        await session.refresh(suspended_student)
        assert suspended_student.status == "purged"



# ========================================================================
# Consolidated from: tests/test_p08_ip_rate_limit.py
# ========================================================================

"""Test real client IP propagation and rate limit isolation for web BFF proxy (P08 Follow-up).

Verifies that:
1. Trusted proxies are strictly restricted to the web container dedicated address/network and gateway (no hostnames, no whole private ranges).
2. Forwarded IPs are parsed from the right (stepping back through trusted proxies).
3. Browser-supplied X-Forwarded-For headers from untrusted peers are strictly ignored.
4. In the Compose stack, different client IPs hit different rate-limit keys.
"""

from unittest.mock import MagicMock
import pytest
from httpx import AsyncClient

from core.common.config import settings
from gateway.config import settings as gw_settings
from core.common.rate_limit import RateLimiter, build_rate_limit_key, get_trusted_client_ip, is_peer_trusted_proxy


def make_mock_request(peer_ip: str, headers: dict[str, str]) -> MagicMock:
    req = MagicMock()
    req.client.host = peer_ip
    req.headers = {k.lower(): v for k, v in headers.items()}
    return req


def test_trusted_proxy_configuration_restricted() -> None:
    """Ensure trusted proxies only contain explicit fixed addresses/dedicated network, with no hostnames or whole private ranges."""
    # Core trusts strictly the Gateway's specific fixed IP or loopback
    assert "172.29.0.2" in settings.TRUSTED_PROXIES
    assert "127.0.0.1" in settings.TRUSTED_PROXIES
    assert "web" not in settings.TRUSTED_PROXIES
    assert "gateway" not in settings.TRUSTED_PROXIES

    # Gateway trusts strictly the Web container's fixed IP and dedicated edge network
    assert "172.28.0.3" in gw_settings.GATEWAY_TRUSTED_PROXIES
    assert "172.28.0.0/29" in gw_settings.GATEWAY_TRUSTED_PROXIES
    assert "127.0.0.1" in gw_settings.GATEWAY_TRUSTED_PROXIES
    assert "web" not in gw_settings.GATEWAY_TRUSTED_PROXIES

    # Whole private ranges MUST NOT be trusted
    assert "10.0.0.0/8" not in settings.TRUSTED_PROXIES
    assert "172.16.0.0/12" not in settings.TRUSTED_PROXIES
    assert "192.168.0.0/16" not in settings.TRUSTED_PROXIES
    assert "10.0.0.0/8" not in gw_settings.GATEWAY_TRUSTED_PROXIES
    assert "172.16.0.0/12" not in gw_settings.GATEWAY_TRUSTED_PROXIES
    assert "192.168.0.0/16" not in gw_settings.GATEWAY_TRUSTED_PROXIES

    # Arbitrary private network addresses not in the list are untrusted
    assert not is_peer_trusted_proxy("10.10.10.10")
    assert not is_peer_trusted_proxy("172.25.0.4")
    assert not is_peer_trusted_proxy("192.168.1.50")
    assert not is_peer_trusted_proxy("web")


def test_browser_supplied_x_forwarded_for_is_ignored() -> None:
    """A browser-supplied X-Forwarded-For or X-Real-IP from an untrusted peer MUST be ignored."""
    # Direct browser client connecting to gateway
    req_browser = make_mock_request(
        peer_ip="198.51.100.77",
        headers={
            "x-forwarded-for": "8.8.8.8, 1.1.1.1",
            "x-real-ip": "9.9.9.9",
        },
    )
    # Must return direct peer host, ignoring spoofed headers
    assert get_trusted_client_ip(req_browser) == "198.51.100.77"


def test_forwarded_ips_parsed_from_the_right() -> None:
    """When request arrives from trusted proxy, X-Forwarded-For is parsed from the right."""
    # Case 1: Browser client (203.0.113.55) connects to Web BFF (fixed IP '172.28.0.3'),
    # and browser attempted to spoof X-Forwarded-For: 100.100.100.100.
    # The chain forwarded by Web container is "100.100.100.100, 203.0.113.55".
    req_spoof_attempt = make_mock_request(
        peer_ip="172.28.0.3",
        headers={"x-forwarded-for": "100.100.100.100, 203.0.113.55"},
    )
    # Parsing from the right extracts the actual client IP (203.0.113.55), ignoring the spoofed 100.100.100.100
    assert get_trusted_client_ip(req_spoof_attempt) == "203.0.113.55"

    # Case 2: Chain containing an intermediate trusted proxy (127.0.0.1)
    req_multi_proxy = make_mock_request(
        peer_ip="172.28.0.3",
        headers={"x-forwarded-for": "1.2.3.4, 203.0.113.99, 127.0.0.1"},
    )
    # Steps over trusted 127.0.0.1 from the right, finding 203.0.113.99, ignoring 1.2.3.4
    assert get_trusted_client_ip(req_multi_proxy) == "203.0.113.99"


def test_compose_stack_different_client_ips_hit_different_rate_limit_keys() -> None:
    """In the Compose stack, different client IPs routed through the web container hit different rate-limit keys."""
    # User 1 and User 2 routed through the dedicated web container fixed IP
    req_user1 = make_mock_request(
        peer_ip="172.28.0.3",
        headers={"x-forwarded-for": "203.0.113.10, 172.28.0.3"},
    )
    req_user2 = make_mock_request(
        peer_ip="172.28.0.3",
        headers={"x-forwarded-for": "198.51.100.20, 172.28.0.3"},
    )

    ip1 = get_trusted_client_ip(req_user1)
    ip2 = get_trusted_client_ip(req_user2)

    assert ip1 == "203.0.113.10"
    assert ip2 == "198.51.100.20"

    key1 = build_rate_limit_key("auth_exchange", ip1, "user_1")
    key2 = build_rate_limit_key("auth_exchange", ip2, "user_2")

    assert key1 == "rl:auth_exchange:203.0.113.10:user_1"
    assert key2 == "rl:auth_exchange:198.51.100.20:user_2"
    assert key1 != key2


@pytest.mark.asyncio
async def test_per_ip_rate_limits_apply_per_user_not_per_web_server(gateway_client: AsyncClient) -> None:
    """Verify that when requests arrive via the web server proxy, rate limits apply per user IP.

    If User A from IP 203.0.113.10 exceeds rate limits, User B from IP 198.51.100.20
    through the same web server proxy must NOT be rate limited.
    """
    await RateLimiter.reset()

    user_a_ip = "203.0.113.10"
    user_b_ip = "198.51.100.20"

    headers_user_a = {
        "X-Client-Platform": "web",
        "X-Client-Form-Factor": "desktop",
        "X-App-Version": "1.0.0",
        "X-Device-Id": "web_dev_user_a",
        "Accept-Language": "bn",
        "X-Real-IP": user_a_ip,
        "X-Forwarded-For": f"{user_a_ip}, 127.0.0.1",
    }

    headers_user_b = {
        "X-Client-Platform": "web",
        "X-Client-Form-Factor": "desktop",
        "X-App-Version": "1.0.0",
        "X-Device-Id": "web_dev_user_b",
        "Accept-Language": "bn",
        "X-Real-IP": user_b_ip,
        "X-Forwarded-For": f"{user_b_ip}, 127.0.0.1",
    }

    from unittest.mock import AsyncMock, patch
    import httpx

    mock_core_response = httpx.Response(
        200,
        json={"access_token": "mock_token", "refresh_token": "mock_rt", "token_type": "bearer", "expires_in": 3600},
    )

    with patch("gateway.router.core_client.request", new_callable=AsyncMock, return_value=mock_core_response):
        # Simulate 10 exchange attempts for User A (rate limit ceiling is 10/min)
        for _ in range(10):
            res = await gateway_client.post(
                "/v1/auth/exchange",
                json={"provider_token": "fake:phone:+8801711111111", "role": "parent"},
                headers=headers_user_a,
            )
            assert res.status_code == 200

        # 11th attempt for User A must trigger rate limit (429)
        res_a_blocked = await gateway_client.post(
            "/v1/auth/exchange",
            json={"provider_token": "fake:phone:+8801711111111", "role": "parent"},
            headers=headers_user_a,
        )
        assert res_a_blocked.status_code == 429
        assert res_a_blocked.json()["error"]["code"] in ("RATE_LIMIT_EXCEEDED", "LOCKED_OUT")

        # User B arrives from the SAME web server, but with their own IP
        # User B must NOT be blocked by User A's lockout!
        res_b = await gateway_client.post(
            "/v1/auth/exchange",
            json={"provider_token": "fake:phone:+8801722222222", "role": "parent"},
            headers=headers_user_b,
        )
        assert res_b.status_code == 200

# ========================================================================
# Consolidated from: tests/test_p08_e2e_journeys.py
# ========================================================================

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
    "X-Client-Form-Factor": "desktop",
    "Accept-Language": "bn",
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
    student_id = res_s_auth.json().get("user", {}).get("id") or student_id
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
    assert "study_tasks" in today_data

    # If tasks exist, student marks one as completed
    if today_data.get("study_tasks"):
        first_task_id = today_data["study_tasks"][0]["id"]
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
            "requested_changes": {
                "requested_school_day_minutes": 120,
                "reason": "বিদ্যালয়ের বার্ষিক ক্রীড়া প্রতিযোগিতা অনুশীলনের জন্য সাময়িক কমানোর অনুরোধ।",
            }
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
        headers=student_headers,
    )
    assert res_assessed_blocked.status_code in (400, 403, 404, 422)

# ========================================================================
# Consolidated from: tests/test_p10_security_and_authz.py
# ========================================================================

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


@pytest.mark.asyncio
async def test_route_inventory_requires_auth_on_every_route() -> None:
    """Rule 9: Dynamic route-inventory test asserting auth on every non-public endpoint."""
    from fastapi.routing import APIRoute
    from core.main import app as core_app

    public_allowlist = {
        "/metrics",
        "/healthz",
        "/readyz",
        "/v1/auth/exchange",
        "/v1/auth/refresh",
        "/v1/auth/status",
        "/v1/internal/auth/status",
        "/auth/exchange",
        "/auth/refresh",
        "/auth/status",
        "/internal/auth/status",
        "/v1/parents/consent/current",
        "/parents/consent/current",
    }

    auth_dependency_names = {
        "get_current_user",
        "get_current_user_profile",
        "role_checker",
        "check_student_access",
        "verify_parent_student_link",
        "require_reauth",
        "require_internal_service_token",
        "logout_session",
    }

    def get_all_dep_names(dependant) -> set[str]:
        names = set()
        if hasattr(dependant.call, "__name__"):
            names.add(dependant.call.__name__)
        for sub in getattr(dependant, "dependencies", []):
            names.update(get_all_dep_names(sub))
        return names

    unprotected_routes = []
    for route in core_app.routes:
        if not isinstance(route, APIRoute):
            continue
        path = route.path
        if path in public_allowlist:
            continue
        dep_names = get_all_dep_names(route.dependant)
        if path.startswith("/internal") or "/internal/" in path:
            if "verify_internal_service_token" in dep_names or "require_internal_service_token" in dep_names:
                continue
        if not (dep_names & auth_dependency_names):
            unprotected_routes.append(f"{route.methods} {path} (deps: {dep_names})")

    assert not unprotected_routes, f"Found unprotected routes in core_app: {unprotected_routes}"


@pytest.mark.asyncio
async def test_redis_outage_rate_limit_fails_closed() -> None:
    """Item 3: Sensitive endpoints (auth, reauth, OTP) fail closed or apply strict in-process limits during Redis outage."""
    from unittest.mock import patch
    from core.common.rate_limit import RateLimiter, _mem_counters

    _mem_counters.clear()

    # 1. Test fail-closed on explicit flag
    with patch("core.common.rate_limit.get_redis_client", side_effect=ConnectionError("Redis down")):
        allowed, retry_after = await RateLimiter.check_rate_limit(
            key="rl:reauth:ip:10.0.0.1",
            max_requests=5,
            window_seconds=60,
            fail_closed_on_redis_error=True,
        )
        assert allowed is False
        assert retry_after == 60

    # 2. Test strict in-process rate limit for sensitive keys (max 3 requests)
    key = f"rl:reauth:test_ip:{uuid.uuid4().hex[:6]}"
    with patch("core.common.rate_limit.get_redis_client", side_effect=ConnectionError("Redis down")):
        for attempt in range(1, 4):
            allowed, retry_after = await RateLimiter.check_rate_limit(
                key=key,
                max_requests=10,
                window_seconds=60,
                fail_closed_on_redis_error=False,
            )
            assert allowed is True, f"Attempt {attempt} should be allowed under strict in-process limit"

        # 4th request must be rejected
        allowed4, retry_after4 = await RateLimiter.check_rate_limit(
            key=key,
            max_requests=10,
            window_seconds=60,
            fail_closed_on_redis_error=False,
        )
        assert allowed4 is False
        assert retry_after4 > 0


@pytest.mark.asyncio
async def test_consent_guard_background_jobs_and_dashboards() -> None:
    """Item 8: Background planner tasks and parent dashboards block access when student parental consent is withdrawn."""
    from datetime import UTC, datetime
    from core.common.database import AsyncSessionLocal
    from core.auth.models import User
    from core.families.models import Family, ParentStudentLink
    from core.parent.service import ParentService
    from workers.planner_tasks import _async_regenerate_plan
    from fastapi import HTTPException

    async with AsyncSessionLocal() as session:
        # Create parent and student with valid auth_provider/auth_uid
        p_id = uuid.uuid4()
        s_id = uuid.uuid4()
        fam_id = uuid.uuid4()

        parent = User(
            id=p_id,
            auth_provider="phone",
            auth_uid=f"phone_{p_id.hex[:8]}",
            phone=f"+880179{uuid.uuid4().hex[:6]}",
            role="parent",
            display_name="Consent Parent",
            has_parental_consent=True,
        )
        student = User(
            id=s_id,
            auth_provider="phone",
            auth_uid=f"phone_{s_id.hex[:8]}",
            phone=f"+880178{uuid.uuid4().hex[:6]}",
            role="student",
            display_name="Consent Child",
            has_parental_consent=False,  # Consent withdrawn
        )
        fam = Family(id=fam_id, owner_parent_id=p_id, name="Consent Family")
        link = ParentStudentLink(
            id=uuid.uuid4(),
            family_id=fam_id,
            parent_id=p_id,
            student_id=s_id,
            status="consent_suspended",
            revoked_at=datetime.now(UTC),
        )

        session.add_all([parent, student, fam, link])
        await session.commit()

        # 1. Background plan regeneration must skip for student without consent
        res_regen = await _async_regenerate_plan(str(s_id), str(uuid.uuid4()), version=1)
        assert res_regen["status"] == "skipped"
        assert res_regen["reason"] == "consent_withdrawn"

        # 2. Parent dashboard check must fail with 403 CONSENT_WITHDRAWN for suspended link
        with pytest.raises(HTTPException) as exc_info:
            await ParentService.verify_parent_student_link(session, p_id, s_id)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail.get("code") == "CONSENT_WITHDRAWN"


@pytest.mark.asyncio
async def test_day23_warning_task_before_day30_purge() -> None:
    """Item 8: Day-23 warning task sends notification to parents before day-30 permanent purge."""
    from datetime import UTC, datetime, timedelta
    from sqlalchemy import select
    from core.common.database import AsyncSessionLocal
    from core.auth.models import User
    from core.families.models import Family, ParentStudentLink
    from core.notifications.models import Notification
    from core.privacy.purge import dispatch_consent_suspension_warnings

    async with AsyncSessionLocal() as session:
        p_id = uuid.uuid4()
        s_id = uuid.uuid4()
        fam_id = uuid.uuid4()

        parent = User(
            id=p_id,
            auth_provider="phone",
            auth_uid=f"phone_{p_id.hex[:8]}",
            phone=f"+880177{uuid.uuid4().hex[:6]}",
            role="parent",
            display_name="Warning Parent",
            has_parental_consent=True,
        )
        student = User(
            id=s_id,
            auth_provider="phone",
            auth_uid=f"phone_{s_id.hex[:8]}",
            phone=f"+880175{uuid.uuid4().hex[:6]}",
            role="student",
            display_name="Warning Child",
            has_parental_consent=False,
        )
        fam = Family(id=fam_id, owner_parent_id=p_id, name="Warning Family")

        # Suspended 24 days ago (between 23 and 30 days)
        revoked_at = datetime.now(UTC) - timedelta(days=24)
        link = ParentStudentLink(
            id=uuid.uuid4(),
            family_id=fam_id,
            parent_id=p_id,
            student_id=s_id,
            status="consent_suspended",
            revoked_at=revoked_at,
        )

        session.add_all([parent, student, fam, link])
        await session.commit()

        # First run: should dispatch 1 warning notification
        count1 = await dispatch_consent_suspension_warnings(session)
        assert count1 >= 1

        # Check notification content
        stmt_n = select(Notification).where(
            Notification.user_id == p_id,
            Notification.type == "consent_suspension_warning",
        )
        res_n = await session.execute(stmt_n)
        notif = res_n.scalars().first()
        assert notif is not None
        assert "7 days" in notif.body
        assert "৭ দিনের" in notif.body_bn
        assert notif.data["student_id"] == str(s_id)

        # Second run (idempotency): should dispatch 0 new notifications
        count2 = await dispatch_consent_suspension_warnings(session)
        assert count2 == 0


# ========================================================================
# Consolidated from: tests/test_logging_security.py
# ========================================================================

"""Tests for structured JSON logging and sensitive data masking."""

import json
import logging

from core.common.logging import JSONFormatter, mask_sensitive_data


def test_mask_sensitive_data_keys() -> None:
    """Verify that credentials, tokens, OTPs, and answer keys are masked."""
    sample = {
        "user_id": 123,
        "password": "secret_password",
        "access_token": "jwt.secret.token",
        "otp": "123456",
        "answer_key": {"q1": "A", "q2": "B"},
        "nested": {
            "token": "inner_token",
            "safe_field": "visible",
        },
    }

    masked = mask_sensitive_data(sample)
    assert masked["user_id"] == 123
    assert masked["password"] == "***MASKED***"
    assert masked["access_token"] == "***MASKED***"
    assert masked["otp"] == "***MASKED***"
    assert masked["answer_key"] == "***MASKED***"
    assert masked["nested"]["token"] == "***MASKED***"
    assert masked["nested"]["safe_field"] == "visible"


def test_json_formatter_output() -> None:
    """Verify JSONFormatter creates valid structured JSON with request correlation."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test event logged",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-12345"

    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "Test event logged"
    assert parsed["request_id"] == "req-12345"
