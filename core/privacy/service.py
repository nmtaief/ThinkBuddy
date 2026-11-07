"""Privacy, parental consent, family data export, and account deletion service logic."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit.models import AuditLog
from core.auth.models import User
from core.auth.tokens import decode_reauth_jwt, generate_secure_token, hash_token
import logging
logger = logging.getLogger(__name__)
from core.families.models import Family, FamilyMember, ParentStudentLink, StudentProfile
from core.notifications.models import Notification
from core.planner.models import StudySetup
from core.privacy.constants import (
    CURRENT_CONSENT_TEXT_HASH,
    CURRENT_CONSENT_VERSION,
    PARENTAL_CONSENT_TEXT_BN,
    PARENTAL_CONSENT_TEXT_EN,
)
from core.privacy.crypto import decrypt_export_payload, encrypt_export_payload
from core.privacy.models import AccountDeletion, DataExport, ParentalConsent, ParentalConsentVersion
from core.privacy.schemas import (
    AccountDeletionResponse,
    CancelDeletionResponse,
    ChatTopicSummaryItem,
    ConsentVersionDetailResponse,
    FamilyDataExportPayload,
    FamilyDataExportResponse,
    ParentalConsentRequest,
    ParentalConsentResponse,
    ParentalConsentStatusResponse,
    RequestAccountDeletionBody,
    StudentExportPayload,
    WithdrawConsentRequest,
    WithdrawConsentResponse,
)
from core.progress.models import Mastery, RevisionItem
from core.quiz.models import QuizAttempt


def utcnow() -> datetime:
    return datetime.now(UTC)


_USED_REAUTH_JTIS: set[str] = set()


class PrivacyService:
    """Service handling parental consent, family exports, deletion grace periods, and purge jobs."""

    @classmethod
    async def verify_reauth_token(
        cls,
        reauth_token: str | None,
        caller_id: uuid.UUID,
        expected_action: str | None = None,
        redis_client: Any = None,
    ) -> None:
        """Verify that a valid, single-use re-authentication token bound to user and action was provided."""
        if not reauth_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "REAUTH_REQUIRED",
                    "message": "Fresh re-authentication is required. Please provide a valid reauth token.",
                },
            )
        try:
            payload = decode_reauth_jwt(reauth_token)
            if payload.get("sub") != str(caller_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"code": "REAUTH_MISMATCH", "message": "Re-authentication token does not match active user."},
                )

            # Action binding check
            if expected_action is not None:
                token_action = payload.get("action", "general")
                if token_action != expected_action and token_action != "general":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "code": "REAUTH_ACTION_MISMATCH",
                            "message": f"Re-authentication token was issued for '{token_action}', but '{expected_action}' is required.",
                        },
                    )

            # Single-use enforcement (fails closed when Redis cannot confirm freshness)
            jti = payload.get("jti")
            if jti:
                r_client = redis_client
                if r_client is None:
                    try:
                        from core.common.redis import get_redis_client
                        r_client = get_redis_client()
                    except Exception as exc:
                        logger.error(f"Cannot obtain Redis client for re-auth token check: {exc}")
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail={
                                "code": "REAUTH_CONFIRMATION_FAILED",
                                "message": "Re-authentication verification service unavailable. Cannot confirm single-use token freshness.",
                            },
                        )

                now_ts = int(utcnow().timestamp())
                exp = payload.get("exp", now_ts + 600)
                ttl = max(1, exp - now_ts)
                key = f"thinkbuddy:reauth_used:{jti}"
                try:
                    is_set = await r_client.set(key, "1", ex=ttl, nx=True)
                except HTTPException:
                    raise
                except Exception as exc:
                    logger.error(f"Redis error during re-auth token verification: {exc}")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail={
                            "code": "REAUTH_CONFIRMATION_FAILED",
                            "message": "Re-authentication verification service unavailable. Cannot confirm single-use token freshness.",
                        },
                    )

                if not is_set:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={"code": "REAUTH_ALREADY_USED", "message": "Re-authentication token has already been consumed."},
                    )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "REAUTH_INVALID", "message": f"Invalid or expired re-authentication token: {e}"},
            )

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

        terms_hash = payload.terms_hash or CURRENT_CONSENT_TEXT_HASH

        consent_record = ParentalConsent(
            id=uuid.uuid4(),
            parent_id=parent.id,
            consent_version=payload.version,
            terms_hash=CURRENT_CONSENT_TEXT_HASH,
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
        parent.consent_terms_hash = CURRENT_CONSENT_TEXT_HASH
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
                meta={"version": payload.version, "terms_hash": CURRENT_CONSENT_TEXT_HASH, "ip": client_ip},
            )
        )
        await db.commit()

        return ParentalConsentResponse(
            status="granted",
            version=payload.version,
            terms_hash=CURRENT_CONSENT_TEXT_HASH,
            consented_at=consent_record.consented_at,
            parent_id=parent.id,
        )

    @classmethod
    async def get_parent_consent_status(
        cls,
        db: AsyncSession,
        parent: User,
    ) -> ParentalConsentStatusResponse:
        """Fetch current recorded parental consent status and detect re-consent requirement."""
        stmt = (
            select(ParentalConsent)
            .where(ParentalConsent.parent_id == parent.id)
            .order_by(ParentalConsent.consented_at.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()

        if record and record.status == "granted":
            reconsent_req = (record.terms_hash != CURRENT_CONSENT_TEXT_HASH or parent.consent_terms_hash != CURRENT_CONSENT_TEXT_HASH)
            return ParentalConsentStatusResponse(
                has_consent=(not reconsent_req),
                version=record.consent_version,
                terms_hash=record.terms_hash,
                current_terms_hash=CURRENT_CONSENT_TEXT_HASH,
                reconsent_required=reconsent_req,
                consented_at=record.consented_at,
                withdrawn_at=record.withdrawn_at,
            )
        elif record and record.status == "withdrawn":
            return ParentalConsentStatusResponse(
                has_consent=False,
                version=record.consent_version,
                terms_hash=record.terms_hash,
                current_terms_hash=CURRENT_CONSENT_TEXT_HASH,
                reconsent_required=False,
                consented_at=record.consented_at,
                withdrawn_at=record.withdrawn_at,
            )

        return ParentalConsentStatusResponse(
            has_consent=bool(parent.has_parental_consent),
            version=parent.consent_version,
            terms_hash=parent.consent_terms_hash,
            current_terms_hash=CURRENT_CONSENT_TEXT_HASH,
            reconsent_required=False,
            consented_at=None,
            withdrawn_at=None,
        )

    @classmethod
    async def get_active_consent_version_details(
        cls,
        db: AsyncSession,
    ) -> ConsentVersionDetailResponse:
        """Fetch active consent version terms with complete Bengali and English legal text."""
        stmt = (
            select(ParentalConsentVersion)
            .order_by(ParentalConsentVersion.effective_at.desc())
            .limit(1)
        )
        record = (await db.execute(stmt)).scalar_one_or_none()
        if record:
            return ConsentVersionDetailResponse(
                version=record.version,
                text_bn=record.text_bn,
                text_en=record.text_en,
                terms_hash=record.terms_hash,
                effective_at=record.effective_at,
            )
        # Fallback to canonical constants
        return ConsentVersionDetailResponse(
            version=CURRENT_CONSENT_VERSION,
            text_bn=PARENTAL_CONSENT_TEXT_BN,
            text_en=PARENTAL_CONSENT_TEXT_EN,
            terms_hash=CURRENT_CONSENT_TEXT_HASH,
            effective_at=utcnow(),
        )

    @classmethod
    async def withdraw_parent_consent(
        cls,
        db: AsyncSession,
        parent: User,
        payload: WithdrawConsentRequest,
        reauth_token: str | None = None,
        auth_iat: int | None = None,
    ) -> WithdrawConsentResponse:
        """Withdraw previously recorded parental consent. Requires fresh re-authentication."""
        if parent.role not in ("parent", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "PARENT_ROLE_REQUIRED", "message": "Only parents can withdraw parental consent."},
            )

        if reauth_token:
            await cls.verify_reauth_token(reauth_token, parent.id, expected_action="consent_withdraw")
        else:
            cls.verify_recent_reauthentication(auth_iat)

        now_dt = utcnow()
        stmt = (
            select(ParentalConsent)
            .where(ParentalConsent.parent_id == parent.id, ParentalConsent.status == "granted")
            .order_by(ParentalConsent.consented_at.desc())
            .limit(1)
        )
        consent = (await db.execute(stmt)).scalar_one_or_none()
        if consent:
            consent.status = "withdrawn"
            consent.withdrawn_at = now_dt
            if payload.reason:
                consent.meta = {**consent.meta, "withdrawal_reason": payload.reason}

        parent.has_parental_consent = False
        parent.consent_terms_hash = None

        # Suspend linked students' active status and parental consent flag
        stmt_links = select(ParentStudentLink).where(ParentStudentLink.parent_id == parent.id)
        links = (await db.execute(stmt_links)).scalars().all()
        for link in links:
            link.status = "consent_suspended"
            link.revoked_at = now_dt
            stmt_s = select(User).where(User.id == link.student_id)
            student_u = (await db.execute(stmt_s)).scalar_one_or_none()
            if student_u:
                student_u.has_parental_consent = False

        db.add(
            AuditLog(
                id=uuid.uuid4(),
                actor_id=parent.id,
                action="parent.consent_withdrawn",
                target_type="user",
                target_id=str(parent.id),
                meta={"reason": payload.reason or ""},
            )
        )
        await db.commit()

        return WithdrawConsentResponse(
            status="withdrawn",
            parent_id=parent.id,
            withdrawn_at=now_dt,
            message="Parental consent successfully withdrawn. Minor child data processing is suspended.",
        )

    @classmethod
    async def verify_parent_consent_for_child_processing(
        cls,
        db: AsyncSession,
        parent_id: uuid.UUID,
    ) -> None:
        """Enforce parental consent gate and terms hash freshness before processing minor child data."""
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
        if parent.consent_terms_hash and parent.consent_terms_hash != CURRENT_CONSENT_TEXT_HASH:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "RECONSENT_REQUIRED",
                    "message": "Parental consent legal terms have been updated. Re-consent is required before continuing.",
                },
            )

    @classmethod
    async def export_family_data(
        cls,
        db: AsyncSession,
        caller: User,
        reauth_token: str | None = None,
        auth_iat: int | None = None,
    ) -> FamilyDataExportResponse:
        """Generate comprehensive family data export JSON with topic-level chat summaries only (Rule 15)."""
        if caller.role not in ("parent", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "PARENT_ROLE_REQUIRED", "message": "Only parents can request family data export."},
            )

        # Re-auth verification
        if reauth_token:
            await cls.verify_reauth_token(reauth_token, caller.id, expected_action="family_export")
        else:
            cls.verify_recent_reauthentication(auth_iat)

        now_dt = utcnow()

        # Rate limiting: 1 export request per 24 hours per parent
        stmt_recent = (
            select(DataExport)
            .where(
                DataExport.requester_id == caller.id,
                DataExport.created_at >= now_dt - timedelta(hours=24),
            )
        )
        recent_export = (await db.execute(stmt_recent)).scalar_one_or_none()
        if recent_export:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "EXPORT_RATE_LIMITED",
                    "message": "Family data export can only be requested once every 24 hours.",
                },
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
            stmt_f2 = select(Family).where(Family.owner_parent_id == caller.id).limit(1)
            res_f2 = await db.execute(stmt_f2)
            family = res_f2.scalar_one_or_none()

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
        )
        res_links = await db.execute(stmt_links)
        student_ids = list(res_links.scalars().all())

        # Include any students directly registered in family members
        stmt_fam_students = (
            select(FamilyMember.user_id)
            .join(User, User.id == FamilyMember.user_id)
            .where(FamilyMember.family_id == family.id, User.role == "student")
        )
        fam_student_ids = (await db.execute(stmt_fam_students)).scalars().all()
        for fs_id in fam_student_ids:
            if fs_id not in student_ids:
                student_ids.append(fs_id)

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
            mastery_map = {
                str(m.topic_id): {
                    "score": m.score,
                    "band": m.band,
                    "attempts_count": m.attempts_count,
                    "updated_at": m.updated_at.isoformat(),
                }
                for m in res_mastery.scalars().all()
            }

            # Revision items count
            stmt_rev = select(func.count(RevisionItem.id)).where(RevisionItem.student_id == s_id)
            rev_count = (await db.execute(stmt_rev)).scalar() or 0

            # Quiz attempts summary (sanitized, no answer keys)
            stmt_att = select(QuizAttempt).where(QuizAttempt.student_id == s_id).order_by(QuizAttempt.started_at.desc())
            res_att = await db.execute(stmt_att)
            attempts_list = [
                {
                    "attempt_id": str(att.id),
                    "quiz_id": str(att.quiz_id),
                    "mode": att.mode,
                    "status": att.status,
                    "score_percentage": att.score_percentage,
                    "passed": att.passed,
                    "started_at": att.started_at.isoformat(),
                    "submitted_at": att.submitted_at.isoformat() if att.submitted_at else None,
                }
                for att in res_att.scalars().all()
            ]

            # AI Chat topic summaries ONLY (Rule 15: Zero raw messages, prompts, or tokens)
            from core.chat.models import ChatCitation, ChatMessage, ChatSession
            stmt_chat = (
                select(
                    ChatCitation.chapter_title.label("topic"),
                    ChatCitation.book_title,
                    ChatCitation.chapter_title,
                    ChatCitation.chapter_number,
                    func.count(ChatMessage.id).label("query_count"),
                    func.max(ChatMessage.created_at).label("last_interaction"),
                )
                .join(ChatMessage, ChatMessage.id == ChatCitation.message_id)
                .join(ChatSession, ChatSession.id == ChatMessage.session_id)
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
                    topic=row.topic,
                    book_title=row.book_title,
                    chapter_title=row.chapter_title,
                    chapter_number=row.chapter_number,
                    message_count=row.query_count,
                    last_active_at=row.last_interaction,
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
                    revision_items_count=rev_count,
                    quiz_attempts_count=len(attempts_list),
                    quiz_attempts_summary=attempts_list,
                    chat_topics=chat_topics,
                )
            )

        # Parental consent history for this family
        stmt_consents = (
            select(ParentalConsent)
            .where(ParentalConsent.parent_id == caller.id)
            .order_by(ParentalConsent.consented_at.desc())
        )
        res_consents = await db.execute(stmt_consents)
        consents_data = [
            {
                "consent_id": str(c.id),
                "consent_version": c.consent_version,
                "terms_hash": c.terms_hash,
                "status": c.status,
                "consented_at": c.consented_at.isoformat(),
                "withdrawn_at": c.withdrawn_at.isoformat() if c.withdrawn_at else None,
            }
            for c in res_consents.scalars().all()
        ]

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

        export_id = uuid.uuid4()
        raw_download_token = generate_secure_token(32)
        download_token_hash = hash_token(raw_download_token)
        download_url = f"/v1/parents/me/export/{export_id}/download?token={raw_download_token}"
        expires_at = now_dt + timedelta(days=7)

        payload_dict = payload.model_dump(mode="json")
        encrypted_export = encrypt_export_payload(payload_dict)

        export_record = DataExport(
            id=export_id,
            family_id=family.id,
            requester_id=caller.id,
            status="completed",
            format="json",
            data_payload=None,
            encrypted_payload=encrypted_export,
            download_token_hash=download_token_hash,
            download_url=download_url,
            expires_at=expires_at,
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
            download_url=download_url,
            expires_at=expires_at,
            exported_at=now_dt,
            data=payload,
        )

    @classmethod
    async def download_family_export(
        cls,
        db: AsyncSession,
        export_id: uuid.UUID,
        token: str,
        caller: User,
    ) -> dict[str, Any]:
        """Download previously generated family data export JSON with Rule 9 isolation."""
        stmt = select(DataExport).where(DataExport.id == export_id)
        res = await db.execute(stmt)
        export = res.scalar_one_or_none()

        if not export:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "EXPORT_NOT_FOUND", "message": "Export file not found."},
            )

        if export.expires_at < utcnow():
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail={"code": "EXPORT_EXPIRED", "message": "Export download link has expired."},
            )

        # Rule 9: Requesting parent only!
        if export.requester_id != caller.id and caller.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN_EXPORT_ACCESS", "message": "You do not have access to this data export."},
            )

        # Token validation
        if not export.download_token_hash or hash_token(token) != export.download_token_hash:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "INVALID_DOWNLOAD_TOKEN", "message": "Invalid download token."},
            )

        if export.encrypted_payload:
            return decrypt_export_payload(export.encrypted_payload)
        return export.data_payload or {}

    @classmethod
    async def request_user_deletion(
        cls,
        db: AsyncSession,
        caller: User,
        payload: RequestAccountDeletionBody,
        reauth_token: str | None = None,
        auth_iat: int | None = None,
        grace_period_days: int = 14,
    ) -> AccountDeletionResponse:
        """Schedule individual account deletion with a 14-day grace period."""
        if reauth_token:
            await cls.verify_reauth_token(reauth_token, caller.id, expected_action="account_delete")
        else:
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

        # Update user status to pending_deletion
        caller.status = "pending_deletion"

        # Audit log
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
            message=(
                f"Account deletion scheduled. Your data will be permanently purged in {grace_period_days} days. "
                "You can cancel this request at any time during the grace period."
            ),
        )

    @classmethod
    async def cancel_user_deletion(
        cls,
        db: AsyncSession,
        caller: User,
    ) -> CancelDeletionResponse:
        """Cancel a pending individual account deletion during the 14-day grace period."""
        stmt = select(AccountDeletion).where(
            AccountDeletion.user_id == caller.id,
            AccountDeletion.target_type == "user",
            AccountDeletion.status == "pending_grace_period",
        )
        res = await db.execute(stmt)
        deletion = res.scalar_one_or_none()

        if not deletion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NO_PENDING_DELETION", "message": "No pending deletion request found for your account."},
            )

        deletion.status = "cancelled"
        deletion.cancellation_reason = "Cancelled by user"
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
            message="Account deletion request has been cancelled. Your account remains active.",
        )

    @classmethod
    async def request_family_deletion(
        cls,
        db: AsyncSession,
        family_id: uuid.UUID,
        caller: User,
        payload: RequestAccountDeletionBody,
        reauth_token: str | None = None,
        auth_iat: int | None = None,
        grace_period_days: int = 14,
    ) -> AccountDeletionResponse:
        """Schedule family deletion. Students forbidden; only family owner can initiate."""
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
        if reauth_token:
            await cls.verify_reauth_token(reauth_token, caller.id, expected_action="family_delete")
        else:
            cls.verify_recent_reauthentication(auth_iat)

        if payload.confirmation.strip().upper() not in ("DELETE", "মুছে ফেলুন"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "CONFIRMATION_MISMATCH",
                    "message": "Confirmation text must strictly be 'DELETE' or 'মুছে ফেলুন'.",
                },
            )

        # 3. Ownership verification: Only family owner can delete!
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
                    "code": "ONLY_FAMILY_OWNER_CAN_DELETE",
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

        # Flag all family member accounts and linked student accounts as pending_deletion
        stmt_m = select(FamilyMember.user_id).where(FamilyMember.family_id == family.id)
        member_ids = list((await db.execute(stmt_m)).scalars().all())

        stmt_l = select(ParentStudentLink.student_id).where(ParentStudentLink.family_id == family.id)
        linked_ids = (await db.execute(stmt_l)).scalars().all()
        for lid in linked_ids:
            if lid not in member_ids:
                member_ids.append(lid)

        if member_ids:
            await db.execute(
                update(User)
                .where(User.id.in_(member_ids))
                .values(status="pending_deletion")
            )

        # Notify other family members (Item 3)
        for m_id in member_ids:
            if m_id != caller.id:
                db.add(
                    Notification(
                        id=uuid.uuid4(),
                        user_id=m_id,
                        type="family_deletion_scheduled",
                        title="Family Deletion Scheduled",
                        body=f"Family deletion was scheduled. Account will be purged in {grace_period_days} days unless cancelled.",
                        title_bn="পরিবার মুছে ফেলার অনুরোধ করা হয়েছে",
                        body_bn=f"পরিবারের অ্যাকাউন্ট আগামী {grace_period_days} দিনের মধ্যে স্থায়ীভাবে মুছে ফেলা হবে। অভিভাবক যে কোনো সময় বাতিল করতে পারবেন।",
                        data={"family_id": str(family.id), "scheduled_purge_at": purge_at.isoformat()},
                    )
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
            message=(
                f"Family account deletion scheduled. All student and parent profiles in this family will be permanently "
                f"purged in {grace_period_days} days. Any parent can cancel this request during the grace period."
            ),
        )

    @classmethod
    async def cancel_family_deletion(
        cls,
        db: AsyncSession,
        family_id: uuid.UUID,
        caller: User,
    ) -> CancelDeletionResponse:
        """Cancel pending family deletion during the 14-day grace period. Any parent can cancel."""
        if caller.role not in ("parent", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "PARENT_ROLE_REQUIRED", "message": "Only a parent can cancel family deletion."},
            )

        stmt_m = select(FamilyMember).where(
            FamilyMember.family_id == family_id,
            FamilyMember.user_id == caller.id,
        )
        fm = (await db.execute(stmt_m)).scalar_one_or_none()
        stmt_f = select(Family).where(Family.id == family_id)
        family = (await db.execute(stmt_f)).scalar_one_or_none()

        if not family or (not fm and family.owner_parent_id != caller.id and caller.role != "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN_FAMILY_ACCESS", "message": "You do not belong to this family."},
            )

        stmt = select(AccountDeletion).where(
            AccountDeletion.family_id == family_id,
            AccountDeletion.target_type == "family",
            AccountDeletion.status == "pending_grace_period",
        )
        res = await db.execute(stmt)
        deletion = res.scalar_one_or_none()

        if not deletion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NO_PENDING_DELETION", "message": "No pending deletion request found for this family."},
            )

        deletion.status = "cancelled"
        deletion.cancellation_reason = f"Cancelled by parent {caller.display_name} ({caller.id})"

        # Restore family member and linked student user records
        stmt_members = select(FamilyMember.user_id).where(FamilyMember.family_id == family_id)
        m_ids = list((await db.execute(stmt_members)).scalars().all())

        stmt_l = select(ParentStudentLink.student_id).where(ParentStudentLink.family_id == family_id)
        linked_ids = (await db.execute(stmt_l)).scalars().all()
        for lid in linked_ids:
            if lid not in m_ids:
                m_ids.append(lid)

        if m_ids:
            await db.execute(
                update(User)
                .where(User.id.in_(m_ids), User.status == "pending_deletion")
                .values(status="active")
            )

        # Notify family members
        for m_id in m_ids:
            if m_id != caller.id:
                db.add(
                    Notification(
                        id=uuid.uuid4(),
                        user_id=m_id,
                        type="family_deletion_cancelled",
                        title="Family Deletion Cancelled",
                        body=f"Pending deletion was cancelled by {caller.display_name}.",
                        title_bn="পরিবার মুছে ফেলার অনুরোধ বাতিল করা হয়েছে",
                        body_bn=f"অভিভাবক {caller.display_name} দ্বারা পরিবার মুছে ফেলার অনুরোধ বাতিল করা হয়েছে। অ্যাকাউন্ট সক্রিয় রয়েছে।",
                        data={"family_id": str(family_id)},
                    )
                )

        db.add(
            AuditLog(
                id=uuid.uuid4(),
                actor_id=caller.id,
                action="family.deletion_cancelled",
                target_type="family",
                target_id=str(family_id),
                meta={"deletion_id": str(deletion.id)},
            )
        )
        await db.commit()

        return CancelDeletionResponse(
            deletion_id=deletion.id,
            target_type="family",
            target_id=family_id,
            status="cancelled",
            message="Family deletion request has been cancelled. All accounts remain active.",
        )
