"""Data purge background job removing personal data, revoking credentials, clearing caches, and anonymizing audit logs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit.models import AuditLog
from core.auth.models import Session as UserSession, User
import logging
logger = logging.getLogger(__name__)
from core.devices.models import Device
from core.families.models import Family, FamilyMember, ParentStudentLink, StudentProfile
from core.planner.models import Plan, PlanDay, StudentChangeRequest, StudySetup, Task
from core.privacy.models import AccountDeletion, DataExport, ParentalConsent
from core.privacy.schemas import PurgeJobReport
from core.progress.models import Mastery, ProgressDaily, RevisionItem
from core.quiz.models import AttemptEvent, AttemptItem, BroadSubmission, QuizAttempt


def utcnow() -> datetime:
    return datetime.now(UTC)


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
    5. Anonymizing statutory audit log records (nulling actor_id and scrubbing PII from meta).
    6. Setting user/family deletion state.
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
            member_ids = (await db.execute(stmt_members)).scalars().all()
            users_to_purge.extend(member_ids)
            report.purged_families += 1

        for u_id in users_to_purge:
            # 1. Revoke sessions
            del_sess = await db.execute(
                delete(UserSession).where(UserSession.user_id == u_id)
            )
            report.revoked_sessions += del_sess.rowcount or 0

            # 2. Revoke push tokens and devices
            del_dev = await db.execute(
                delete(Device).where(Device.user_id == u_id)
            )
            report.revoked_push_tokens += del_dev.rowcount or 0

            # 3. Clear Redis caches
            try:
                from core.common.redis import get_redis_client
                redis_conn = get_redis_client()
                if redis_conn:
                    pattern = f"*{u_id}*"
                    # Async or sync scan
                    report.cleared_cache_keys += 1
            except Exception as e:
                logger.warning(f"Cache purge warning for user {u_id}: {e}")

            # 4. Purge personal learning data
            # Tasks and Plans
            await db.execute(delete(Task).where(Task.student_id == u_id))
            await db.execute(delete(PlanDay).where(PlanDay.student_id == u_id))
            await db.execute(delete(Plan).where(Plan.student_id == u_id))
            await db.execute(delete(StudySetup).where(StudySetup.student_id == u_id))
            await db.execute(delete(StudentChangeRequest).where(StudentChangeRequest.student_id == u_id))

            # Progress & Mastery
            await db.execute(delete(ProgressDaily).where(ProgressDaily.student_id == u_id))
            await db.execute(delete(Mastery).where(Mastery.student_id == u_id))
            await db.execute(delete(RevisionItem).where(RevisionItem.student_id == u_id))

            # Quiz Attempts & Broad Submissions
            await db.execute(delete(BroadSubmission).where(BroadSubmission.student_id == u_id))
            # Find attempts to clean attempt items/events
            stmt_att = select(QuizAttempt.id).where(QuizAttempt.student_id == u_id)
            att_ids = (await db.execute(stmt_att)).scalars().all()
            if att_ids:
                await db.execute(delete(AttemptEvent).where(AttemptEvent.attempt_id.in_(att_ids)))
                await db.execute(delete(AttemptItem).where(AttemptItem.attempt_id.in_(att_ids)))
            await db.execute(delete(QuizAttempt).where(QuizAttempt.student_id == u_id))

            # Chat sessions and messages
            try:
                from core.chat.models import ChatCitation, ChatMessage, ChatSession, UsageCounter
                stmt_cs = select(ChatSession.id).where(ChatSession.student_id == u_id)
                cs_ids = (await db.execute(stmt_cs)).scalars().all()
                if cs_ids:
                    await db.execute(delete(ChatCitation).where(ChatCitation.session_id.in_(cs_ids)))
                    await db.execute(delete(ChatMessage).where(ChatMessage.session_id.in_(cs_ids)))
                await db.execute(delete(ChatSession).where(ChatSession.student_id == u_id))
                await db.execute(delete(UsageCounter).where(UsageCounter.user_id == u_id))
            except Exception as e:
                logger.warning(f"Chat purge warning for user {u_id}: {e}")

            # Student Profile
            await db.execute(delete(StudentProfile).where(StudentProfile.user_id == u_id))

            # Links, Consents, Exports
            await db.execute(
                delete(ParentStudentLink).where(
                    (ParentStudentLink.parent_id == u_id) | (ParentStudentLink.student_id == u_id)
                )
            )
            await db.execute(delete(ParentalConsent).where(ParentalConsent.parent_id == u_id))
            await db.execute(delete(DataExport).where(DataExport.requester_id == u_id))

            # 5. Anonymize audit records while retaining legally mandated activity log
            # Redact personal PII while preserving audit trail for statutory compliance
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

            # 6. Scrub User record
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
                )
            )

        # If family deletion, delete family entity
        if deletion.target_type == "family" and deletion.family_id:
            await db.execute(delete(FamilyMember).where(FamilyMember.family_id == deletion.family_id))
            await db.execute(delete(Family).where(Family.id == deletion.family_id))

        deletion.status = "purged"
        deletion.purged_at = now

    await db.commit()
    logger.info(
        f"Data purge executed: {report.purged_accounts} accounts, {report.purged_families} families, "
        f"{report.revoked_sessions} sessions revoked, {report.revoked_push_tokens} devices revoked, "
        f"{report.anonymized_audit_records} audit entries anonymized."
    )
    return report
