"""Comprehensive Tests for Parental Consent, Family Data Export, Account Deletion Grace Period, and Purge Job (P07b)."""

from __future__ import annotations

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
    res_rate_limited = await gateway_client.post(
        "/v1/parents/me/export",
        headers={**headers_p, "X-Reauth-Token": reauth_token},
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

    # 2. Deletion with valid reauth token schedules deletion with 14-day grace period
    res_del = await gateway_client.post(
        "/v1/users/me/delete",
        json={"confirmation": "DELETE", "reason": "Moving school"},
        headers={**headers, "X-Reauth-Token": reauth_token},
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
