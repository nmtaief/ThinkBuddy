"""Privacy, parental consent, family data export, and account deletion service logic."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit.models import AuditLog
from core.auth.models import Session as UserSession, User
from core.common.database import get_db_session
import logging
logger = logging.getLogger(__name__)
from core.devices.models import Device
from core.families.models import Family, FamilyMember, ParentStudentLink, StudentProfile
from core.planner.models import Plan, StudySetup, Task
from core.privacy.models import AccountDeletion, DataExport, ParentalConsent
from core.privacy.schemas import (
    AccountDeletionResponse,
    CancelDeletionResponse,
    ChatTopicSummaryItem,
    FamilyDataExportPayload,
    FamilyDataExportResponse,
    ParentalConsentRequest,
    ParentalConsentResponse,
    ParentalConsentStatusResponse,
    RequestAccountDeletionBody,
    StudentExportPayload,
)
from core.progress.models import Mastery, ProgressDaily, RevisionItem
from core.quiz.models import QuizAttempt


def utcnow() -> datetime:
    return datetime.now(UTC)


class PrivacyService:
    """Service handling parental consent, family exports, deletion grace periods, and purge jobs."""

    @staticmethod
    def verify_recent_reauthentication(auth_iat: int | None, max_age_seconds: int = 900) -> None:
        """Verify the caller's JWT access token was issued within max_age_seconds (default 15 mins)."""
        if auth_iat is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "REAUTH_REQUIRED",
                    "message": "Recent re-authentication required for sensitive account actions.",
                },
            )
        now_ts = int(utcnow().timestamp())
        if (now_ts - auth_iat) > max_age_seconds:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "REAUTH_REQUIRED",
                    "message": "Your session is too old for this sensitive action. Please re-authenticate.",
                },
            )

    @classmethod
    async def record_parent_consent(
        cls,
        db: AsyncSession,
        parent: User,
        payload: ParentalConsentRequest,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> ParentalConsentResponse:
        """Record explicit, versioned parental consent and gate child onboarding."""
        if parent.role not in ("parent", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "PARENT_ROLE_REQUIRED", "message": "Only parents can provide parental consent."},
            )

        if not payload.consented:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "CONSENT_NOT_GRANTED", "message": "Explicit consent must be granted."},
            )

        consent_record = ParentalConsent(
            id=uuid.uuid4(),
            parent_id=parent.id,
            consent_version=payload.version,
            status="granted",
            consented_at=utcnow(),
            ip_address=client_ip,
            user_agent=user_agent,
            meta={"consent_type": "onboarding_parental_consent"},
        )
        db.add(consent_record)

        # Update parent user model
        parent.has_parental_consent = True
        parent.consent_version = payload.version
        await db.flush()

        # Update any existing parent-student links for this parent
        await db.execute(
            update(ParentStudentLink)
            .where(ParentStudentLink.parent_id == parent.id, ParentStudentLink.consent_at.is_(None))
            .values(consent_at=consent_record.consented_at)
        )

        # Audit log
        db.add(
            AuditLog(
                id=uuid.uuid4(),
                actor_id=parent.id,
                action="parent.consent_recorded",
                target_type="user",
                target_id=str(parent.id),
                meta={"version": payload.version, "ip": client_ip},
            )
        )
        await db.commit()

        return ParentalConsentResponse(
            status="granted",
            version=payload.version,
            consented_at=consent_record.consented_at,
            parent_id=parent.id,
        )

    @classmethod
    async def get_parent_consent_status(
        cls,
        db: AsyncSession,
        parent: User,
    ) -> ParentalConsentStatusResponse:
        """Fetch current recorded parental consent status."""
        stmt = (
            select(ParentalConsent)
            .where(ParentalConsent.parent_id == parent.id, ParentalConsent.status == "granted")
            .order_by(ParentalConsent.consented_at.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()

        if record:
            return ParentalConsentStatusResponse(
                has_consent=True,
                version=record.consent_version,
                consented_at=record.consented_at,
            )
        return ParentalConsentStatusResponse(
            has_consent=bool(parent.has_parental_consent),
            version=parent.consent_version,
            consented_at=None,
        )

    @classmethod
    async def verify_parent_consent_for_child_processing(
        cls,
        db: AsyncSession,
        parent_id: uuid.UUID,
    ) -> None:
        """Enforce parental consent gate before creating or processing minor child data."""
        stmt = select(User).where(User.id == parent_id)
        res = await db.execute(stmt)
        parent = res.scalar_one_or_none()
        if not parent or not parent.has_parental_consent:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PARENTAL_CONSENT_REQUIRED",
                    "message": "Parental consent must be recorded before child data can be processed.",
                },
            )

    @classmethod
    async def export_family_data(
        cls,
        db: AsyncSession,
        caller: User,
    ) -> FamilyDataExportResponse:
        """Generate comprehensive family data export JSON with topic-level chat summaries only (Rule 15)."""
        if caller.role not in ("parent", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "PARENT_ROLE_REQUIRED", "message": "Only parents can request family data export."},
            )

        # Locate caller's family
        stmt_fam = (
            select(Family)
            .join(FamilyMember, FamilyMember.family_id == Family.id)
            .where(FamilyMember.user_id == caller.id)
            .limit(1)
        )
        res_fam = await db.execute(stmt_fam)
        family = res_fam.scalar_one_or_none()

        if not family:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "FAMILY_NOT_FOUND", "message": "No family found associated with your account."},
            )

        # Family members
        stmt_m = (
            select(FamilyMember, User)
            .join(User, User.id == FamilyMember.user_id)
            .where(FamilyMember.family_id == family.id)
        )
        res_m = await db.execute(stmt_m)
        members_data = []
        for fm, u in res_m.all():
            members_data.append({
                "user_id": str(u.id),
                "display_name": u.display_name,
                "role": u.role,
                "relation": fm.relation,
                "created_at": fm.created_at.isoformat(),
            })

        # Linked students
        stmt_links = select(ParentStudentLink.student_id).where(
            ParentStudentLink.family_id == family.id,
            ParentStudentLink.status == "active",
        )
        res_links = await db.execute(stmt_links)
        student_ids = res_links.scalars().all()

        students_payload: list[StudentExportPayload] = []
        for s_id in student_ids:
            # Student profile & user
            stmt_s = (
                select(StudentProfile, User)
                .join(User, User.id == StudentProfile.user_id)
                .where(StudentProfile.user_id == s_id)
            )
            res_s = await db.execute(stmt_s)
            s_row = res_s.first()
            if not s_row:
                continue
            sp, su = s_row

            # Study setups
            stmt_setups = select(StudySetup).where(StudySetup.student_id == s_id)
            res_setups = await db.execute(stmt_setups)
            setups_list = [
                {
                    "setup_id": str(st.id),
                    "class_level": st.class_level,
                    "target_exam_date": st.target_exam_date.isoformat() if st.target_exam_date else None,
                    "daily_study_minutes": st.daily_study_minutes,
                    "daily_revision_minutes": st.daily_revision_minutes,
                    "priorities": st.priorities,
                }
                for st in res_setups.scalars().all()
            ]

            # Mastery summary
            stmt_mastery = select(Mastery).where(Mastery.student_id == s_id)
            res_mastery = await db.execute(stmt_mastery)
            mastery_items = res_mastery.scalars().all()
            mastery_map: dict[str, Any] = {}
            for m in mastery_items:
                mastery_map[m.subject_id] = {
                    "score": m.score,
                    "total_attempts": m.total_attempts,
                    "retention_strength": m.retention_strength,
                    "last_activity_at": m.last_activity_at.isoformat() if m.last_activity_at else None,
                }

            # Revision items count
            stmt_rev_cnt = select(func.count(RevisionItem.id)).where(RevisionItem.student_id == s_id)
            rev_cnt = (await db.execute(stmt_rev_cnt)).scalar() or 0

            # Quiz attempts summary
            stmt_quiz = (
                select(QuizAttempt)
                .where(QuizAttempt.student_id == s_id)
                .order_by(QuizAttempt.created_at.desc())
                .limit(20)
            )
            res_quiz = await db.execute(stmt_quiz)
            quiz_list = [
                {
                    "attempt_id": str(qa.id),
                    "quiz_id": str(qa.quiz_id),
                    "mode": qa.mode,
                    "status": qa.status,
                    "score_percent": qa.score_percent,
                    "started_at": qa.started_at.isoformat() if qa.started_at else None,
                    "submitted_at": qa.submitted_at.isoformat() if qa.submitted_at else None,
                }
                for qa in res_quiz.scalars().all()
            ]

            # Chat Topics: Strictly aggregated topic summaries; ZERO raw chat transcripts per Rule 15
            # We import ChatCitation and ChatSession dynamically or aggregate from DB
            from core.chat.models import ChatCitation, ChatSession
            stmt_chat = (
                select(
                    ChatCitation.book_title,
                    ChatCitation.chapter_title,
                    ChatCitation.chapter_number,
                    func.count(ChatCitation.id).label("cnt"),
                    func.max(ChatCitation.created_at).label("last_active"),
                )
                .join(ChatSession, ChatSession.id == ChatCitation.session_id)
                .where(ChatSession.student_id == s_id)
                .group_by(
                    ChatCitation.book_title,
                    ChatCitation.chapter_title,
                    ChatCitation.chapter_number,
                )
            )
            res_chat = await db.execute(stmt_chat)
            chat_topics = [
                ChatTopicSummaryItem(
                    topic=f"{row.chapter_title} ({row.book_title})",
                    book_title=row.book_title,
                    chapter_title=row.chapter_title,
                    chapter_number=row.chapter_number,
                    message_count=row.cnt,
                    last_active_at=row.last_active or utcnow(),
                )
                for row in res_chat.all()
            ]

            students_payload.append(
                StudentExportPayload(
                    student_id=su.id,
                    display_name=su.display_name,
                    class_level=sp.class_level,
                    medium=sp.medium,
                    group=sp.group,
                    school=sp.school,
                    daily_minutes=sp.daily_minutes,
                    study_setups=setups_list,
                    mastery_summary=mastery_map,
                    revision_items_count=rev_cnt,
                    quiz_attempts_count=len(quiz_list),
                    quiz_attempts_summary=quiz_list,
                    chat_topics=chat_topics,
                )
            )

        # Consents history
        stmt_c = (
            select(ParentalConsent)
            .where(ParentalConsent.parent_id == caller.id)
            .order_by(ParentalConsent.consented_at.desc())
        )
        res_c = await db.execute(stmt_c)
        consents_data = [
            {
                "version": c.consent_version,
                "status": c.status,
                "consented_at": c.consented_at.isoformat(),
            }
            for c in res_c.scalars().all()
        ]

        now_dt = utcnow()
        payload = FamilyDataExportPayload(
            family_id=family.id,
            family_name=family.name,
            owner_parent_id=family.owner_parent_id,
            created_at=family.created_at,
            requester_id=caller.id,
            members=members_data,
            students=students_payload,
            parental_consents=consents_data,
            exported_at=now_dt,
        )

        export_record = DataExport(
            id=uuid.uuid4(),
            family_id=family.id,
            requester_id=caller.id,
            status="completed",
            format="json",
            data_payload=payload.model_dump(mode="json"),
            expires_at=now_dt + timedelta(days=7),
            created_at=now_dt,
        )
        db.add(export_record)

        # Audit log
        db.add(
            AuditLog(
                id=uuid.uuid4(),
                actor_id=caller.id,
                action="family.data_exported",
                target_type="family",
                target_id=str(family.id),
                meta={"export_id": str(export_record.id)},
            )
        )
        await db.commit()

        return FamilyDataExportResponse(
            export_id=export_record.id,
            family_id=family.id,
            exported_at=now_dt,
            data=payload,
        )

    @classmethod
    async def request_user_deletion(
        cls,
        db: AsyncSession,
        caller: User,
        payload: RequestAccountDeletionBody,
        auth_iat: int | None,
        grace_period_days: int = 14,
    ) -> AccountDeletionResponse:
        """Schedule user account deletion with recent re-auth verification and a 14-day grace period."""
        cls.verify_recent_reauthentication(auth_iat)

        if payload.confirmation.strip().upper() not in ("DELETE", "মুছে ফেলুন"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "CONFIRMATION_MISMATCH",
                    "message": "Confirmation text must strictly be 'DELETE' or 'মুছে ফেলুন'.",
                },
            )

        now_dt = utcnow()
        purge_at = now_dt + timedelta(days=grace_period_days)

        deletion = AccountDeletion(
            id=uuid.uuid4(),
            user_id=caller.id,
            family_id=None,
            target_type="user",
            status="pending_grace_period",
            grace_period_days=grace_period_days,
            requested_at=now_dt,
            scheduled_purge_at=purge_at,
            recent_auth_confirmed_at=now_dt,
            meta={"reason": payload.reason or ""},
        )
        db.add(deletion)
        caller.status = "pending_deletion"

        db.add(
            AuditLog(
                id=uuid.uuid4(),
                actor_id=caller.id,
                action="user.deletion_requested",
                target_type="user",
                target_id=str(caller.id),
                meta={"scheduled_purge_at": purge_at.isoformat(), "grace_days": grace_period_days},
            )
        )
        await db.commit()

        return AccountDeletionResponse(
            deletion_id=deletion.id,
            target_type="user",
            target_id=caller.id,
            status="pending_grace_period",
            grace_period_days=grace_period_days,
            requested_at=now_dt,
            scheduled_purge_at=purge_at,
            message=f"Account scheduled for permanent deletion in {grace_period_days} days. You may cancel anytime before this date.",
        )

    @classmethod
    async def request_family_deletion(
        cls,
        db: AsyncSession,
        family_id: uuid.UUID,
        caller: User,
        payload: RequestAccountDeletionBody,
        auth_iat: int | None,
        grace_period_days: int = 14,
    ) -> AccountDeletionResponse:
        """Schedule family deletion. Students are strictly forbidden from deleting the family account."""
        # 1. Authorization check: Student cannot delete the family!
        if caller.role == "student":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "STUDENT_CANNOT_DELETE_FAMILY",
                    "message": "Students are not permitted to delete the family account.",
                },
            )

        # 2. Re-authentication verification
        cls.verify_recent_reauthentication(auth_iat)

        if payload.confirmation.strip().upper() not in ("DELETE", "মুছে ফেলুন"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "CONFIRMATION_MISMATCH",
                    "message": "Confirmation text must strictly be 'DELETE' or 'মুছে ফেলুন'.",
                },
            )

        # 3. Ownership verification
        stmt = select(Family).where(Family.id == family_id)
        res = await db.execute(stmt)
        family = res.scalar_one_or_none()

        if not family:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "FAMILY_NOT_FOUND", "message": "Family account not found."},
            )

        if family.owner_parent_id != caller.id and caller.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN_FAMILY_ACCESS",
                    "message": "Only the family owner parent can schedule family deletion.",
                },
            )

        now_dt = utcnow()
        purge_at = now_dt + timedelta(days=grace_period_days)

        deletion = AccountDeletion(
            id=uuid.uuid4(),
            user_id=caller.id,
            family_id=family.id,
            target_type="family",
            status="pending_grace_period",
            grace_period_days=grace_period_days,
            requested_at=now_dt,
            scheduled_purge_at=purge_at,
            recent_auth_confirmed_at=now_dt,
            meta={"reason": payload.reason or ""},
        )
        db.add(deletion)

        # Flag all family member accounts as pending_deletion
        stmt_m = select(FamilyMember.user_id).where(FamilyMember.family_id == family.id)
        member_ids = (await db.execute(stmt_m)).scalars().all()
        if member_ids:
            await db.execute(
                update(User)
                .where(User.id.in_(member_ids))
                .values(status="pending_deletion")
            )

        db.add(
            AuditLog(
                id=uuid.uuid4(),
                actor_id=caller.id,
                action="family.deletion_requested",
                target_type="family",
                target_id=str(family.id),
                meta={"scheduled_purge_at": purge_at.isoformat(), "grace_days": grace_period_days},
            )
        )
        await db.commit()

        return AccountDeletionResponse(
            deletion_id=deletion.id,
            target_type="family",
            target_id=family.id,
            status="pending_grace_period",
            grace_period_days=grace_period_days,
            requested_at=now_dt,
            scheduled_purge_at=purge_at,
            message=f"Family account scheduled for permanent deletion in {grace_period_days} days. You may cancel anytime before this date.",
        )

    @classmethod
    async def cancel_user_deletion(
        cls,
        db: AsyncSession,
        caller: User,
    ) -> CancelDeletionResponse:
        """Cancel pending account deletion during the 14-day grace period."""
        stmt = (
            select(AccountDeletion)
            .where(
                AccountDeletion.user_id == caller.id,
                AccountDeletion.target_type == "user",
                AccountDeletion.status == "pending_grace_period",
            )
            .order_by(AccountDeletion.requested_at.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        deletion = res.scalar_one_or_none()

        if not deletion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NO_PENDING_DELETION", "message": "No pending deletion request found for this account."},
            )

        deletion.status = "cancelled"
        deletion.cancellation_reason = "Cancelled by user during grace period."
        caller.status = "active"

        db.add(
            AuditLog(
                id=uuid.uuid4(),
                actor_id=caller.id,
                action="user.deletion_cancelled",
                target_type="user",
                target_id=str(caller.id),
                meta={"deletion_id": str(deletion.id)},
            )
        )
        await db.commit()

        return CancelDeletionResponse(
            deletion_id=deletion.id,
            target_type="user",
            target_id=caller.id,
            status="cancelled",
            message="Account deletion successfully cancelled. Your account remains active.",
        )

    @classmethod
    async def cancel_family_deletion(
        cls,
        db: AsyncSession,
        family_id: uuid.UUID,
        caller: User,
    ) -> CancelDeletionResponse:
        """Cancel pending family deletion during the 14-day grace period."""
        stmt_f = select(Family).where(Family.id == family_id)
        res_f = await db.execute(stmt_f)
        family = res_f.scalar_one_or_none()

        if not family or (family.owner_parent_id != caller.id and caller.role != "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN_FAMILY_ACCESS", "message": "Only the family owner can cancel deletion."},
            )

        stmt = (
            select(AccountDeletion)
            .where(
                AccountDeletion.family_id == family.id,
                AccountDeletion.target_type == "family",
                AccountDeletion.status == "pending_grace_period",
            )
            .order_by(AccountDeletion.requested_at.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        deletion = res.scalar_one_or_none()

        if not deletion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NO_PENDING_DELETION", "message": "No pending deletion request found for this family."},
            )

        deletion.status = "cancelled"
        deletion.cancellation_reason = "Cancelled by owner parent during grace period."

        # Restore family member statuses to active
        stmt_m = select(FamilyMember.user_id).where(FamilyMember.family_id == family.id)
        member_ids = (await db.execute(stmt_m)).scalars().all()
        if member_ids:
            await db.execute(
                update(User)
                .where(User.id.in_(member_ids), User.status == "pending_deletion")
                .values(status="active")
            )

        db.add(
            AuditLog(
                id=uuid.uuid4(),
                actor_id=caller.id,
                action="family.deletion_cancelled",
                target_type="family",
                target_id=str(family.id),
                meta={"deletion_id": str(deletion.id)},
            )
        )
        await db.commit()

        return CancelDeletionResponse(
            deletion_id=deletion.id,
            target_type="family",
            target_id=family.id,
            status="cancelled",
            message="Family deletion successfully cancelled. All family accounts remain active.",
        )
