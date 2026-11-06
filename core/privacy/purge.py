"""Data purge background job removing personal data, revoking credentials, clearing caches, and anonymizing audit logs."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit.models import AuditLog
from core.auth.models import Session as UserSession, User
from core.chat.models import ChatCitation, ChatMessage, ChatSession, UsageCounter
from core.common.config import settings
from core.devices.models import Device
from core.families.models import Family, FamilyMember, ParentStudentLink, StudentProfile
from core.notifications.models import Notification, NotificationDelivery, NotificationPreference
from core.planner.models import (
    AiPlannerShadowRun as AIPlannerShadowRun,
    Plan,
    PlanDay,
    StudentChangeRequest,
    StudentStudySettings,
    StudySetup,
    Task,
)
from core.privacy.models import AccountDeletion, DataExport, DeletionLedger, ParentalConsent
from core.privacy.schemas import PurgeJobReport
from core.progress.models import Mastery, ProgressDaily, RevisionItem
from core.quiz.models import AttemptEvent, AttemptItem, BroadSubmission, LearningSignal, Quiz, QuizAttempt

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(UTC)


async def delete_s3_media(media_url: str) -> bool:
    """Safely delete object storage file via MinIO/S3."""
    if not media_url:
        return False
    try:
        import minio

        parsed = urlparse(media_url)
        key = parsed.path.lstrip("/")
        bucket = settings.S3_BUCKET_NAME
        if key.startswith(f"{bucket}/"):
            key = key.removeprefix(f"{bucket}/")

        endpoint = settings.S3_ENDPOINT_URL.replace("http://", "").replace("https://", "")
        client = minio.Minio(
            endpoint=endpoint,
            access_key=settings.S3_ACCESS_KEY_ID,
            secret_key=settings.S3_SECRET_ACCESS_KEY,
            secure=settings.S3_USE_SSL,
        )
        client.remove_object(bucket, key)
        return True
    except Exception as e:
        logger.warning(f"Could not remove object storage item {media_url}: {e}")
        return False


async def execute_data_purge(
    db: AsyncSession,
    reference_time: datetime | None = None,
) -> PurgeJobReport:
    """Execute permanent data purge for accounts and families past their 14-day grace period.

    Performs:
    1. Revoking and deleting active user sessions and refresh tokens.
    2. Revoking FCM push tokens and deleting client device bindings.
    3. Clearing volatile Redis cache entries (dashboards, plans, active sessions).
    4. Purging personal academic learning records (profiles, setups, tasks, plans, attempts, chat).
    5. Deleting broad submission upload photos from object storage (MinIO/S3).
    6. Scrubbing notifications, deliveries, preferences, learning signals, and shadow runs.
    7. Anonymizing statutory audit log records (nulling actor_id and scrubbing PII from meta).
    8. Setting user/family deletion state with isolated per-user transactions.
    """
    now = reference_time or utcnow()

    # Query pending deletions past scheduled purge timestamp
    stmt = select(AccountDeletion).where(
        AccountDeletion.status == "pending_grace_period",
        AccountDeletion.scheduled_purge_at <= now,
    )
    res = await db.execute(stmt)
    pending_deletions = res.scalars().all()

    report = PurgeJobReport(executed_at=now)

    for deletion in pending_deletions:
        users_to_purge: list[uuid.UUID] = []

        if deletion.target_type == "user":
            users_to_purge.append(deletion.user_id)
            report.purged_accounts += 1
        elif deletion.target_type == "family" and deletion.family_id:
            stmt_members = select(FamilyMember.user_id).where(
                FamilyMember.family_id == deletion.family_id
            )
            member_ids = list((await db.execute(stmt_members)).scalars().all())
            stmt_l = select(ParentStudentLink.student_id).where(
                ParentStudentLink.family_id == deletion.family_id
            )
            linked_ids = (await db.execute(stmt_l)).scalars().all()
            for lid in linked_ids:
                if lid not in member_ids:
                    member_ids.append(lid)
            users_to_purge.extend(member_ids)
            report.purged_families += 1

        for u_id in users_to_purge:
            try:
                async with db.begin_nested():
                    # 1. Learning signals & Shadow runs
                    del_ls = await db.execute(delete(LearningSignal).where(LearningSignal.student_id == u_id))
                    report.deleted_learning_signals += del_ls.rowcount or 0

                    del_sr = await db.execute(delete(AIPlannerShadowRun).where(AIPlannerShadowRun.student_id == u_id))
                    report.deleted_shadow_runs += del_sr.rowcount or 0

                    # 2. Notifications, deliveries, and preferences
                    stmt_n = select(Notification.id).where(Notification.user_id == u_id)
                    n_ids = (await db.execute(stmt_n)).scalars().all()
                    if n_ids:
                        await db.execute(delete(NotificationDelivery).where(NotificationDelivery.notification_id.in_(n_ids)))
                    del_n = await db.execute(delete(Notification).where(Notification.user_id == u_id))
                    report.deleted_notifications += del_n.rowcount or 0
                    await db.execute(delete(NotificationPreference).where(NotificationPreference.user_id == u_id))

                    # 3. Object-storage submissions and quiz attempts
                    stmt_att = select(QuizAttempt.id).where(QuizAttempt.student_id == u_id)
                    att_ids = (await db.execute(stmt_att)).scalars().all()
                    if att_ids:
                        stmt_items = select(AttemptItem.id).where(AttemptItem.attempt_id.in_(att_ids))
                        item_ids = (await db.execute(stmt_items)).scalars().all()
                        if item_ids:
                            stmt_bs = select(BroadSubmission).where(BroadSubmission.attempt_item_id.in_(item_ids))
                            bs_items = (await db.execute(stmt_bs)).scalars().all()
                            for bs in bs_items:
                                for uri in (bs.image_uris or []):
                                    if await delete_s3_media(uri):
                                        report.deleted_s3_objects += 1
                            await db.execute(delete(BroadSubmission).where(BroadSubmission.attempt_item_id.in_(item_ids)))
                            await db.execute(delete(AttemptItem).where(AttemptItem.id.in_(item_ids)))
                        await db.execute(delete(AttemptEvent).where(AttemptEvent.attempt_id.in_(att_ids)))
                        await db.execute(delete(QuizAttempt).where(QuizAttempt.id.in_(att_ids)))
                    await db.execute(delete(Quiz).where(Quiz.student_id == u_id))

                    # 4. Planner tasks, plan days, plans, study setups, student change requests, study settings
                    await db.execute(delete(Task).where(Task.student_id == u_id))
                    stmt_plans = select(Plan.id).where(Plan.student_id == u_id)
                    plan_ids = (await db.execute(stmt_plans)).scalars().all()
                    if plan_ids:
                        await db.execute(delete(PlanDay).where(PlanDay.plan_id.in_(plan_ids)))
                    await db.execute(delete(Plan).where(Plan.student_id == u_id))
                    await db.execute(delete(StudySetup).where(StudySetup.student_id == u_id))
                    await db.execute(delete(StudentChangeRequest).where(StudentChangeRequest.student_id == u_id))
                    await db.execute(delete(StudentStudySettings).where(StudentStudySettings.student_id == u_id))

                    # 5. Progress, mastery, and revision items
                    await db.execute(delete(ProgressDaily).where(ProgressDaily.student_id == u_id))
                    await db.execute(delete(Mastery).where(Mastery.student_id == u_id))
                    await db.execute(delete(RevisionItem).where(RevisionItem.student_id == u_id))

                    # 6. AI Chat sessions, messages, citations, usage counters
                    stmt_cs = select(ChatSession.id).where(ChatSession.student_id == u_id)
                    cs_ids = (await db.execute(stmt_cs)).scalars().all()
                    if cs_ids:
                        await db.execute(delete(ChatCitation).where(ChatCitation.session_id.in_(cs_ids)))
                        await db.execute(delete(ChatMessage).where(ChatMessage.session_id.in_(cs_ids)))
                    await db.execute(delete(ChatSession).where(ChatSession.student_id == u_id))
                    await db.execute(delete(UsageCounter).where(UsageCounter.student_id == u_id))

                    # 7. Student Profile, Parent-Student Links (clearing invitation codes)
                    await db.execute(delete(StudentProfile).where(StudentProfile.user_id == u_id))
                    await db.execute(
                        delete(ParentStudentLink).where(
                            (ParentStudentLink.parent_id == u_id) | (ParentStudentLink.student_id == u_id)
                        )
                    )
                    await db.execute(delete(ParentalConsent).where(ParentalConsent.parent_id == u_id))
                    await db.execute(delete(DataExport).where(DataExport.requester_id == u_id))

                    # 8. Revoke sessions and device tokens
                    del_sess = await db.execute(delete(UserSession).where(UserSession.user_id == u_id))
                    report.revoked_sessions += del_sess.rowcount or 0
                    del_dev = await db.execute(delete(Device).where(Device.user_id == u_id))
                    report.revoked_push_tokens += del_dev.rowcount or 0

                    # 9. Volatile Redis cache clearance
                    try:
                        from core.common.redis import get_redis_client
                        redis_conn = get_redis_client()
                        if redis_conn:
                            keys = await redis_conn.keys(f"*{u_id}*")
                            if keys:
                                await redis_conn.delete(*keys)
                                report.cleared_cache_keys += len(keys)
                    except Exception as redis_e:
                        logger.warning(f"Cache purge warning for user {u_id}: {redis_e}")

                    # 10. Anonymize audit records (PII scrubbing while retaining compliance audit trail)
                    anon_meta: dict[str, Any] = {
                        "anonymized": True,
                        "reason": "gdpr_privacy_purge",
                        "purged_at": now.isoformat(),
                    }
                    res_anon_actor = await db.execute(
                        update(AuditLog)
                        .where(AuditLog.actor_id == u_id)
                        .values(actor_id=None, meta=anon_meta)
                    )
                    res_anon_target = await db.execute(
                        update(AuditLog)
                        .where(AuditLog.target_id == str(u_id))
                        .values(meta=anon_meta)
                    )
                    report.anonymized_audit_records += (res_anon_actor.rowcount or 0) + (res_anon_target.rowcount or 0)

                    # 11. Scrub User record
                    await db.execute(
                        update(User)
                        .where(User.id == u_id)
                        .values(
                            status="purged",
                            deleted_at=now,
                            phone=None,
                            email=None,
                            display_name="Deleted User",
                            has_parental_consent=False,
                            consent_version=None,
                            consent_terms_hash=None,
                        )
                    )

                    # 12. Minimal Deletion Ledger (hashed ID for restore replay)
                    u_hash = hashlib.sha256(str(u_id).encode("utf-8")).hexdigest()
                    db.add(
                        DeletionLedger(
                            id=uuid.uuid4(),
                            user_id_hash=u_hash,
                            target_type="user",
                            purged_at=now,
                        )
                    )
            except Exception as user_err:
                logger.error(f"Error purging user {u_id}: {user_err}", exc_info=True)
                report.failed_user_ids.append(str(u_id))

        # If family deletion, delete family entity
        if deletion.target_type == "family" and deletion.family_id:
            await db.execute(delete(FamilyMember).where(FamilyMember.family_id == deletion.family_id))
            await db.execute(delete(Family).where(Family.id == deletion.family_id))
            fam_hash = hashlib.sha256(str(deletion.family_id).encode("utf-8")).hexdigest()
            db.add(
                DeletionLedger(
                    id=uuid.uuid4(),
                    user_id_hash=fam_hash,
                    target_type="family",
                    purged_at=now,
                )
            )

        deletion.status = "purged"
        deletion.purged_at = now

    # Sweep expired data exports older than 7 days
    await db.execute(delete(DataExport).where(DataExport.expires_at <= now))

    await db.commit()
    logger.info(
        f"Data purge executed: {report.purged_accounts} accounts, {report.purged_families} families, "
        f"{report.revoked_sessions} sessions revoked, {report.revoked_push_tokens} devices revoked, "
        f"{report.deleted_notifications} notifications deleted, {report.deleted_learning_signals} signals deleted, "
        f"{report.deleted_shadow_runs} shadow runs deleted, {report.anonymized_audit_records} audit entries anonymized."
    )
    return report
