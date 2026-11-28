"""Quiz Execution Service and State Machine Authority (core/quiz/service.py).

Per docs/05_SECURE_QUIZ.md:
- Enforces one-active-assessed-attempt per student.
- Web platform blocked from assessed attempts.
- Server-authoritative timing and deadline enforcement.
- Per-item nonce validation preventing replay / out-of-order answers.
- Review endpoint strictly guarded until after submit.
- Chat lockout integration: is_assessed_attempt_active().
"""

from __future__ import annotations

import hashlib
import logging
import random
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.models import User
from core.devices.models import Device
from core.quiz.builder import QuizBuilderService
from core.quiz.grading import QuizGradingService
from core.quiz.integrity import (
    ATTESTED_DEVICES,
    DeviceIntegrityVerdict,
    IntegrityEngine,
    check_and_auto_resume_pause,
    evaluate_device_attestation,
)
from core.quiz.models import (
    OPEN_ATTEMPT_STATES,
    AttemptEvent,
    AttemptItem,
    Question,
    QuestionKey,
    Quiz,
    QuizAttempt,
)
from core.quiz.schemas import (
    AnswerItemResponse,
    AttemptItemPublic,
    AttemptItemReview,
    AttemptReviewResponse,
    QuestionOptionPublic,
    QuestionPublic,
    StartAttemptResponse,
    SubmitAttemptResponse,
)

logger = logging.getLogger("thinkbuddy.quiz.service")


def utcnow() -> datetime:
    return datetime.now(UTC)


def _format_attempt_question_public(q: Question, attempt_id: uuid.UUID) -> QuestionPublic:
    """Format a question for public serving with per-attempt option shuffling and zero key leakage."""
    opts = list(q.options)
    if opts:
        # Deterministic shuffle per attempt item so different attempts receive different option order
        seed_str = f"{attempt_id}:{q.id}"
        random.Random(seed_str).shuffle(opts)  # noqa: S311

    return QuestionPublic(
        id=q.id,
        type=q.type,  # type: ignore[arg-type]
        chapter_id=q.chapter_id,
        concept_id=q.concept_id,
        difficulty=q.difficulty,
        language=q.language,
        stem=q.stem,
        options=[QuestionOptionPublic(id=opt["id"], text=opt["text"]) for opt in opts],
    )


class QuizService:
    """Manages the full lifecycle of quiz attempts, anti-cheat, and grading."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.builder = QuizBuilderService(db)
        self.grading = QuizGradingService(db)

    async def get_active_assessed_attempt(self, student_id: uuid.UUID) -> QuizAttempt | None:
        """Return active assessed attempt for student if one is currently open."""
        stmt = select(QuizAttempt).where(
            QuizAttempt.student_id == student_id,
            QuizAttempt.state.in_(OPEN_ATTEMPT_STATES),
            QuizAttempt.mode == "assessed",
        )
        res = await self.db.execute(stmt)
        active_attempt = res.scalar_one_or_none()
        if not active_attempt:
            return None

        # Check if pause has expired and auto-resume if so
        if active_attempt.state == "paused":
            if check_and_auto_resume_pause(active_attempt):
                await self.db.commit()

        # Check if expired by server deadline (deadline never extends on pause)
        now = utcnow()
        if active_attempt.deadline_at and now > active_attempt.deadline_at:
            active_attempt.state = "expired"
            active_attempt.submitted_at = active_attempt.deadline_at
            await self.grading.finalize_and_emit_signals(active_attempt)
            await self.db.commit()
            return None

        return active_attempt

    async def is_assessed_attempt_active(self, student_id: uuid.UUID) -> bool:
        """Return True if student currently has an open assessed attempt (created, active, warned, paused).

        Used by chat and assistant endpoints to enforce anti-cheat lockout.
        """
        attempt = await self.get_active_assessed_attempt(student_id)
        return attempt is not None

    async def create_attempt(
        self,
        quiz_id: uuid.UUID,
        student_id: uuid.UUID,
        client_platform: str,
        device_id: str | None = None,
    ) -> QuizAttempt:
        """Create a new attempt in state 'created' with short 5-minute expiry.

        Binds the Play Integrity nonce to attempt.id.
        """
        quiz_res = await self.db.execute(select(Quiz).where(Quiz.id == quiz_id))
        quiz = quiz_res.scalar_one_or_none()
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "QUIZ_NOT_FOUND", "message": "Quiz not found."},
            )

        if client_platform.lower() == "web" and quiz.mode == "assessed":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "WEB_PLATFORM_PRACTICE_ONLY",
                    "message": "Assessed mode quizzes are mobile-only. Web is practice-only.",
                },
            )

        if quiz.mode == "assessed":
            is_active = await self.is_assessed_attempt_active(student_id)
            if is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "ACTIVE_ATTEMPT_ALREADY_EXISTS",
                        "message": "You already have an active assessed attempt in progress.",
                    },
                )

        now = utcnow()
        # Created attempts get a short expiry (5 minutes) per P04 requirement 6
        deadline = now + timedelta(minutes=5)
        attempt_id = uuid.uuid4()
        # Generate random single-use server nonce stored hashed
        raw_nonce = secrets.token_urlsafe(32)
        nonce_hash = hashlib.sha256(raw_nonce.encode("utf-8")).hexdigest()
        attempt = QuizAttempt(
            id=attempt_id,
            quiz_id=quiz.id,
            student_id=student_id,
            device_id=device_id,
            state="created",
            mode=quiz.mode,
            attempt_token=f"att_{secrets.token_hex(24)}",
            started_at=now,
            deadline_at=deadline,
            integrity_score=1.0,
            unverified_device=False,
            nonce_hash=nonce_hash,
        )
        attempt._raw_nonce = raw_nonce
        try:
            self.db.add(attempt)
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "ACTIVE_ATTEMPT_ALREADY_EXISTS",
                    "message": "You already have an active assessed attempt in progress.",
                },
            ) from None

        questions = await self.builder.select_and_randomize_questions(
            question_count=quiz.question_count,
            student_id=student_id,
            mode=quiz.mode,
        )
        await self.builder.initialize_attempt_items(attempt, questions)
        await self.db.commit()
        return attempt

    async def start_attempt(
        self,
        quiz_id: uuid.UUID,
        student_id: uuid.UUID,
        client_platform: str,
        device_id: str | None = None,
        integrity_verdict: str | None = None,
        headers: dict[str, str] | None = None,
        attempt_id: uuid.UUID | None = None,
    ) -> StartAttemptResponse:
        """Start a new attempt or activate a created attempt, binding nonce to attempt_id."""
        # 1. Fetch quiz definition
        quiz_res = await self.db.execute(select(Quiz).where(Quiz.id == quiz_id))
        quiz = quiz_res.scalar_one_or_none()
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "QUIZ_NOT_FOUND", "message": "Quiz not found."},
            )

        # 2. Check web platform restriction (docs/05_SECURE_QUIZ.md §3)
        if client_platform.lower() == "web" and quiz.mode == "assessed":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "WEB_PLATFORM_PRACTICE_ONLY",
                    "message": "Assessed mode quizzes are mobile-only. Web is practice-only.",
                },
            )

        now = utcnow()

        # Handle existing created attempt
        if attempt_id:
            attempt_res = await self.db.execute(
                select(QuizAttempt).where(QuizAttempt.id == attempt_id)
            )
            attempt = attempt_res.scalar_one_or_none()
            if not attempt:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "ATTEMPT_NOT_FOUND", "message": "Attempt not found."},
                )
            if attempt.student_id != student_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "ATTEMPT_NOT_FOUND", "message": "Attempt not found."},
                )

            # Check created attempt short expiry (5 minutes)
            if attempt.deadline_at and now > attempt.deadline_at:
                attempt.state = "expired"
                attempt.submitted_at = attempt.deadline_at
                await self.grading.finalize_and_emit_signals(attempt)
                await self.db.commit()
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail={
                        "code": "ATTEMPT_EXPIRED",
                        "message": "Quiz attempt deadline has passed.",
                    },
                )

            # Verify device integrity bound to attempt_id
            init_integrity_score = 1.0
            is_unverified = False
            if quiz.mode == "assessed":
                # Check DB for account and device attestation history
                usr_stmt = select(User).where(User.id == student_id)
                u_res = await self.db.execute(usr_stmt)
                u_obj = u_res.scalar_one_or_none()
                account_attested = bool(u_obj and u_obj.has_valid_attestation)

                target_dev_id = device_id or attempt.device_id
                device_attested = target_dev_id in ATTESTED_DEVICES if target_dev_id else False
                if target_dev_id and not device_attested:
                    try:
                        d_uuid = uuid.UUID(str(target_dev_id))
                        d_res = await self.db.execute(select(Device).where(Device.id == d_uuid))
                        d_obj = d_res.scalar_one_or_none()
                        device_attested = bool(d_obj and d_obj.has_valid_attestation)
                    except ValueError:
                        pass

                attestation = evaluate_device_attestation(
                    platform=client_platform,
                    device_id=target_dev_id,
                    integrity_verdict=integrity_verdict,
                    headers=headers,
                    expected_nonce=str(attempt.id) if not attempt.nonce_hash else None,
                    expected_nonce_hash=attempt.nonce_hash,
                    attempt_id=attempt.id,
                    device_has_valid_attestation=device_attested,
                    account_has_valid_attestation=account_attested,
                )
                if attestation == DeviceIntegrityVerdict.COMPROMISED:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "code": "DEVICE_INTEGRITY_FAILED",
                            "message": (
                                "Assessed mode is not permitted on rooted or emulated devices. "
                                "Please use practice mode."
                            ),
                        },
                    )
                elif attestation == DeviceIntegrityVerdict.LOW_TRUST_ACCOUNT_FLAGGED:
                    init_integrity_score = 0.70
                    is_unverified = True
                    attempt.mastery_weight = 0.2
                    attempt.parent_flag = True
                    attempt.parent_flag_reason = "downgrade_unsupported_claim"
                    self.db.add(
                        AttemptEvent(
                            attempt_id=attempt.id,
                            event_type="downgrade_unsupported_flag",
                            data={
                                "reason": "account_previously_attested",
                                "device_id": str(target_dev_id),
                            },
                        )
                    )
                elif attestation == DeviceIntegrityVerdict.LOW_TRUST:
                    init_integrity_score = 0.85
                    is_unverified = True
                elif attestation == DeviceIntegrityVerdict.UNVERIFIED:
                    init_integrity_score = 0.90
                    is_unverified = True
                elif attestation in (DeviceIntegrityVerdict.SECURE, DeviceIntegrityVerdict.BASIC):
                    if u_obj:
                        u_obj.has_valid_attestation = True
                    if target_dev_id:
                        ATTESTED_DEVICES.add(str(target_dev_id))
                        try:
                            d_uuid = uuid.UUID(str(target_dev_id))
                            d_res = await self.db.execute(select(Device).where(Device.id == d_uuid))
                            d_obj = d_res.scalar_one_or_none()
                            if d_obj:
                                d_obj.has_valid_attestation = True
                        except ValueError:
                            pass

            attempt.state = "active"
            attempt.started_at = now
            attempt.deadline_at = now + timedelta(seconds=quiz.time_limit_s)
            attempt.integrity_score = init_integrity_score
            attempt.unverified_device = is_unverified
            attempt.nonce_hash = None  # Single-use nonce consumed upon activation
            await self.db.commit()

            items_res = await self.db.execute(
                select(AttemptItem, Question)
                .join(Question, AttemptItem.question_id == Question.id)
                .where(AttemptItem.attempt_id == attempt.id)
                .order_by(AttemptItem.position.asc())
            )
            item_rows = list(items_res.all())
            first_item_public: AttemptItemPublic | None = None
            if item_rows:
                first_item, q_first = item_rows[0]
                first_item_public = AttemptItemPublic(
                    position=first_item.position,
                    nonce=first_item.nonce,
                    time_limit_s=quiz.per_question_limit_s,
                    question=_format_attempt_question_public(q_first, attempt.id),
                )

            return StartAttemptResponse(
                attempt_id=attempt.id,
                quiz_id=quiz.id,
                state=attempt.state,
                mode=quiz.mode,
                started_at=attempt.started_at,  # type: ignore[arg-type]
                deadline_at=attempt.deadline_at,  # type: ignore[arg-type]
                attempt_token=attempt.attempt_token,
                total_items=len(item_rows),
                current_item=first_item_public,
            )

        # 3. Check one-active-assessed-attempt rule across all open states
        if quiz.mode == "assessed":
            is_active = await self.is_assessed_attempt_active(student_id)
            if is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "ACTIVE_ATTEMPT_ALREADY_EXISTS",
                        "message": "You already have an active assessed attempt in progress.",
                    },
                )

        target_attempt_id = uuid.uuid4()

        # 4. Check device integrity verdict for assessed mode (Play Integrity / App Attest)
        init_integrity_score = 1.0
        init_event_type: str | None = None
        is_unverified_device = False
        if quiz.mode == "assessed":
            attestation = evaluate_device_attestation(
                platform=client_platform,
                device_id=device_id,
                integrity_verdict=integrity_verdict,
                headers=headers,
                expected_nonce=str(target_attempt_id),
                attempt_id=target_attempt_id,
            )
            if attestation == DeviceIntegrityVerdict.COMPROMISED:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "DEVICE_INTEGRITY_FAILED",
                        "message": (
                            "Assessed mode is not permitted on rooted or emulated devices. "
                            "Please use practice mode."
                        ),
                    },
                )
            elif attestation == DeviceIntegrityVerdict.LOW_TRUST:
                # Device without Google Play services: allowed under low-trust policy with scrutiny
                init_integrity_score = 0.85
                init_event_type = "low_trust_device_active"
                is_unverified_device = True
            elif attestation == DeviceIntegrityVerdict.UNVERIFIED:
                # Attestation unverified: recorded as unverified device
                init_integrity_score = 0.90
                init_event_type = "unverified_device_attestation"
                is_unverified_device = True

        deadline = now + timedelta(seconds=quiz.time_limit_s)
        attempt_token = f"att_{secrets.token_hex(24)}"

        attempt = QuizAttempt(
            id=target_attempt_id,
            quiz_id=quiz.id,
            student_id=student_id,
            device_id=device_id,
            state="active",
            mode=quiz.mode,
            attempt_token=attempt_token,
            started_at=now,
            deadline_at=deadline,
            integrity_score=init_integrity_score,
            unverified_device=is_unverified_device,
        )
        try:
            self.db.add(attempt)
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "ACTIVE_ATTEMPT_ALREADY_EXISTS",
                    "message": "You already have an active assessed attempt in progress.",
                },
            ) from None

        if init_event_type:
            event = AttemptEvent(
                attempt_id=attempt.id,
                type=init_event_type,
                meta={"device_id": device_id, "platform": client_platform},
            )
            self.db.add(event)

        # 5. Select questions & initialize items
        questions = await self.builder.select_and_randomize_questions(
            question_count=quiz.question_count,
            student_id=student_id,
            mode=quiz.mode,
        )
        items = await self.builder.initialize_attempt_items(attempt, questions)
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "ACTIVE_ATTEMPT_ALREADY_EXISTS",
                    "message": "You already have an active assessed attempt in progress.",
                },
            ) from None
        first_item_public: AttemptItemPublic | None = None
        if items and questions:
            q_first = questions[0]
            first_item_public = AttemptItemPublic(
                position=items[0].position,
                nonce=items[0].nonce,
                time_limit_s=quiz.per_question_limit_s,
                question=_format_attempt_question_public(q_first, attempt.id),
            )

        return StartAttemptResponse(
            attempt_id=attempt.id,
            quiz_id=quiz.id,
            state=attempt.state,
            mode=quiz.mode,
            started_at=attempt.started_at,  # type: ignore[arg-type]
            deadline_at=attempt.deadline_at,  # type: ignore[arg-type]
            attempt_token=attempt.attempt_token,
            total_items=len(items),
            current_item=first_item_public,
        )

    async def answer_item(
        self,
        attempt_id: uuid.UUID,
        position: int,
        student_id: uuid.UUID,
        nonce: str,
        response: dict[str, Any],
        time_spent_ms: int,
        token: str,
    ) -> AnswerItemResponse:
        """Submit one answer in sequence with nonce & server deadline enforcement."""
        # 1. Fetch attempt and check ownership
        stmt = (
            select(QuizAttempt)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(QuizAttempt.id == attempt_id)
        )
        res = await self.db.execute(stmt)
        attempt = res.scalar_one_or_none()
        if not attempt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ATTEMPT_NOT_FOUND", "message": "Attempt not found."},
            )
        if attempt.student_id != student_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ATTEMPT_NOT_FOUND", "message": "Attempt not found."},
            )

        if attempt.attempt_token != token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_ATTEMPT_TOKEN", "message": "Invalid attempt token."},
            )

        # 2. Check server deadline
        now = utcnow()
        if attempt.deadline_at and now > attempt.deadline_at:
            attempt.state = "expired"
            attempt.submitted_at = attempt.deadline_at
            await self.grading.finalize_and_emit_signals(attempt)
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail={"code": "ATTEMPT_EXPIRED", "message": "Quiz deadline has passed."},
            )

        # Auto-resume pause if pause timeout has expired
        if attempt.state == "paused":
            if check_and_auto_resume_pause(attempt):
                await self.db.commit()

        if attempt.state == "paused":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "ATTEMPT_PAUSED",
                    "message": "Quiz attempt is paused due to integrity review.",
                },
            )

        if attempt.state == "invalidated":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "ATTEMPT_INVALIDATED",
                    "message": "Quiz attempt has been invalidated.",
                },
            )

        if attempt.state not in ("active", "warned"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "ATTEMPT_NOT_ACTIVE", "message": f"Attempt is {attempt.state}."},
            )

        # 3. Fetch item by position with row-level lock
        item_stmt = (
            select(AttemptItem)
            .where(
                AttemptItem.attempt_id == attempt.id,
                AttemptItem.position == position,
            )
            .with_for_update()
        )
        item_res = await self.db.execute(item_stmt)
        item = item_res.scalar_one_or_none()
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ITEM_NOT_FOUND", "message": f"No item at position {position}."},
            )

        # Check if item already answered
        # (idempotent return on retry with matching nonce & answer)
        if item.answered_at is not None:
            if item.nonce == nonce:
                if item.response != response:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={
                            "code": "ANSWER_MISMATCH",
                            "message": "Resubmitted answer does not match original submission.",
                        },
                    )
                next_stmt = select(AttemptItem).where(
                    AttemptItem.attempt_id == attempt.id,
                    AttemptItem.position == position + 1,
                )
                next_res = await self.db.execute(next_stmt)
                next_item = next_res.scalar_one_or_none()
                next_item_public: AttemptItemPublic | None = None
                if next_item:
                    q_res = await self.db.execute(
                        select(Question).where(Question.id == next_item.question_id)
                    )
                    q_next = q_res.scalar_one()
                    next_item_public = AttemptItemPublic(
                        position=next_item.position,
                        nonce=next_item.nonce,
                        question=_format_attempt_question_public(q_next, attempt.id),
                    )
                feedback_correct = item.is_correct if attempt.mode == "practice" else None
                return AnswerItemResponse(
                    position=position,
                    answered=True,
                    is_correct=feedback_correct,
                    next_item=next_item_public,
                    has_more=next_item is not None,
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "ITEM_ALREADY_ANSWERED",
                    "message": f"Item at position {position} has already been answered.",
                },
            )

        # Nonce verification
        if item.nonce != nonce:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "INVALID_ITEM_NONCE", "message": "Item nonce invalid or replayed."},
            )

        # 4. Grade item
        is_correct = await self.grading.grade_item(item, response, time_spent_ms)
        await self.db.flush()

        # 5. Check server-side anomalies scaled by stem length and question type
        if attempt.mode == "assessed":
            q_res = await self.db.execute(select(Question).where(Question.id == item.question_id))
            q_current = q_res.scalar_one_or_none()
            await IntegrityEngine.check_and_apply_anomalies(
                db=self.db,
                attempt=attempt,
                item=item,
                time_spent_ms=time_spent_ms,
                is_correct=is_correct,
                question=q_current,
            )

        # 6. Fetch next item
        next_stmt = select(AttemptItem).where(
            AttemptItem.attempt_id == attempt.id,
            AttemptItem.position == position + 1,
        )
        next_res = await self.db.execute(next_stmt)
        next_item = next_res.scalar_one_or_none()

        next_item_public: AttemptItemPublic | None = None
        if next_item:
            q_res = await self.db.execute(
                select(Question).where(Question.id == next_item.question_id)
            )
            q_next = q_res.scalar_one()
            next_item_public = AttemptItemPublic(
                position=next_item.position,
                nonce=next_item.nonce,
                question=_format_attempt_question_public(q_next, attempt.id),
            )

        # Check quiz mode for feedback: Assessed mode strictly withholds correctness until submit
        feedback_correct = is_correct if attempt.mode == "practice" else None

        await self.db.commit()

        return AnswerItemResponse(
            position=position,
            answered=True,
            is_correct=feedback_correct,
            next_item=next_item_public,
            has_more=next_item is not None,
        )

    async def record_event(
        self,
        attempt_id: uuid.UUID,
        student_id: uuid.UUID,
        event_type: str,
        meta: dict[str, Any],
        token: str,
    ) -> tuple[bool, float, str]:
        """Record anti-cheat event and evaluate grace / invalidation policy."""
        stmt = select(QuizAttempt).where(QuizAttempt.id == attempt_id)
        res = await self.db.execute(stmt)
        attempt = res.scalar_one_or_none()
        if not attempt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ATTEMPT_NOT_FOUND", "message": "Attempt not found."},
            )
        if attempt.student_id != student_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ATTEMPT_NOT_FOUND", "message": "Attempt not found."},
            )

        event = AttemptEvent(
            attempt_id=attempt.id,
            type=event_type,
            meta=meta,
        )
        self.db.add(event)

        IntegrityEngine.process_event(attempt, event_type, meta)
        await IntegrityEngine.evaluate_attempt_state(self.db, attempt)
        await self.db.commit()
        return True, attempt.integrity_score, attempt.state

    async def submit_attempt(
        self,
        attempt_id: uuid.UUID,
        student_id: uuid.UUID,
        token: str,
    ) -> SubmitAttemptResponse:
        """Finalize attempt, grade all items, emit learning signals, and unlock review."""
        stmt = select(QuizAttempt).where(QuizAttempt.id == attempt_id)
        res = await self.db.execute(stmt)
        attempt = res.scalar_one_or_none()
        if not attempt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ATTEMPT_NOT_FOUND", "message": "Attempt not found."},
            )
        if attempt.student_id != student_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ATTEMPT_NOT_FOUND", "message": "Attempt not found."},
            )

        if attempt.attempt_token != token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_ATTEMPT_TOKEN", "message": "Invalid attempt token."},
            )

        if attempt.submitted_at is not None:
            # Idempotent response if already submitted
            score = attempt.score or 0.0
            return SubmitAttemptResponse(
                attempt_id=attempt.id,
                state=attempt.state,
                score=score,
                total_possible_score=100.0,
                integrity_score=attempt.integrity_score,
                is_flagged=attempt.integrity_score < 0.70 or attempt.state == "invalidated",
                invalid_reason=attempt.invalid_reason,
                submitted_at=attempt.submitted_at,
            )

        attempt.submitted_at = utcnow()
        if attempt.state in OPEN_ATTEMPT_STATES:
            attempt.state = "submitted"

        final_score = await self.grading.finalize_and_emit_signals(attempt)
        await self.db.commit()
        await self.db.refresh(attempt)

        is_flagged = attempt.integrity_score < 0.70 or attempt.state == "invalidated"

        return SubmitAttemptResponse(
            attempt_id=attempt.id,
            state=attempt.state,
            score=final_score,
            total_possible_score=100.0,
            integrity_score=attempt.integrity_score,
            is_flagged=is_flagged,
            invalid_reason=attempt.invalid_reason,
            submitted_at=attempt.submitted_at,  # type: ignore[arg-type]
        )

    async def review_attempt(
        self,
        attempt_id: uuid.UUID,
        user: Any,
    ) -> AttemptReviewResponse:
        """Get full attempt review with correct keys. Strictly forbidden while attempt is active.

        Enforces Standing Rule 9:
        - Student themself: allowed (if attempt is submitted/expired).
        - Linked parent: allowed (if attempt is submitted/expired). Unlinked parent: 403 FORBIDDEN.
        - Cross-student access: 403 FORBIDDEN.
        - Active attempt: 403 ATTEMPT_NOT_SUBMITTED (for both student and parent).
        """
        stmt = (
            select(QuizAttempt)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(QuizAttempt.id == attempt_id)
        )
        res = await self.db.execute(stmt)
        attempt = res.scalar_one_or_none()
        if not attempt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ATTEMPT_NOT_FOUND", "message": "Attempt not found."},
            )

        user_role = getattr(user, "role", "student")
        user_id = getattr(user, "id", None)
        if user_role != "admin" and attempt.student_id != user_id:
            if user_role == "parent":
                from core.families.models import ParentStudentLink

                link_stmt = select(ParentStudentLink).where(
                    ParentStudentLink.parent_id == user_id,
                    ParentStudentLink.student_id == attempt.student_id,
                    ParentStudentLink.status == "active",
                    ParentStudentLink.revoked_at.is_(None),
                )
                link_res = await self.db.execute(link_stmt)
                if not link_res.scalar_one_or_none():
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail={
                            "code": "ATTEMPT_NOT_FOUND",
                            "message": "Attempt not found.",
                        },
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "ATTEMPT_NOT_FOUND",
                        "message": "Attempt not found.",
                    },
                )

        # Rule 6 & docs/05_SECURE_QUIZ.md §5: Strictly reject if not submitted/expired!
        if attempt.state not in ("submitted", "expired", "invalidated"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "ATTEMPT_NOT_SUBMITTED",
                    "message": (
                        "Review and answer keys are accessible only after the attempt is submitted."
                    ),
                },
            )

        quiz_res = await self.db.execute(select(Quiz).where(Quiz.id == attempt.quiz_id))
        quiz = quiz_res.scalar_one()

        items_res = await self.db.execute(
            select(AttemptItem)
            .where(AttemptItem.attempt_id == attempt.id)
            .order_by(AttemptItem.position.asc())
        )
        items = list(items_res.scalars().all())

        review_items: list[AttemptItemReview] = []
        for it in items:
            q_res = await self.db.execute(select(Question).where(Question.id == it.question_id))
            q = q_res.scalar_one()

            key_res = await self.db.execute(
                select(QuestionKey).where(QuestionKey.question_id == q.id)
            )
            q_key = key_res.scalar_one_or_none()

            correct_ans: dict[str, Any] = {}
            if q_key:
                if q_key.correct_option_id:
                    correct_ans["correct_option_id"] = q_key.correct_option_id
                if q_key.correct_text:
                    correct_ans["correct_text"] = q_key.correct_text

            explanation = q_key.explanation if q_key else q.explanation

            review_items.append(
                AttemptItemReview(
                    position=it.position,
                    question=QuestionPublic(
                        id=q.id,
                        type=q.type,  # type: ignore[arg-type]
                        chapter_id=q.chapter_id,
                        concept_id=q.concept_id,
                        difficulty=q.difficulty,
                        language=q.language,
                        stem=q.stem,
                        options=[
                            QuestionOptionPublic(id=opt["id"], text=opt["text"])
                            for opt in q.options
                        ],
                    ),
                    student_response=it.response,
                    is_correct=it.is_correct,
                    points=it.points,
                    correct_answer=correct_ans,
                    explanation=explanation,
                )
            )

        return AttemptReviewResponse(
            attempt_id=attempt.id,
            quiz_id=quiz.id,
            quiz_title=quiz.title,
            mode=quiz.mode,
            state=attempt.state,
            score=attempt.score or 0.0,
            total_possible_score=100.0,
            integrity_score=attempt.integrity_score,
            unverified_device=getattr(attempt, "unverified_device", False),
            started_at=attempt.started_at,
            submitted_at=attempt.submitted_at,
            items=review_items,
        )

    async def allow_attempt(
        self,
        attempt_id: uuid.UUID,
        actor_user: Any,
        reason: str,
    ) -> QuizAttempt:
        """Parent or admin override to allow an attempt that was warned, paused, or invalidated."""
        from core.audit.models import AuditLog
        from core.families.models import ParentStudentLink

        stmt = select(QuizAttempt).where(QuizAttempt.id == attempt_id)
        res = await self.db.execute(stmt)
        attempt = res.scalar_one_or_none()
        if not attempt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ATTEMPT_NOT_FOUND", "message": "Attempt not found."},
            )

        user_role = getattr(actor_user, "role", "student")
        user_id = getattr(actor_user, "id", None)
        if user_role not in ("parent", "admin"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ATTEMPT_NOT_FOUND", "message": "Attempt not found."},
            )

        if user_role == "parent":
            link_stmt = select(ParentStudentLink).where(
                ParentStudentLink.parent_id == user_id,
                ParentStudentLink.student_id == attempt.student_id,
                ParentStudentLink.status == "active",
            )
            link_res = await self.db.execute(link_stmt)
            if not link_res.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "ATTEMPT_NOT_FOUND", "message": "Attempt not found."},
                )

        prev_state = attempt.state
        prev_score = attempt.integrity_score

        now = utcnow()
        # Requirement 6: Parent allow cannot revive an expired attempt
        if attempt.state == "expired" or (attempt.deadline_at and now >= attempt.deadline_at):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "CANNOT_REVIVE_EXPIRED_ATTEMPT",
                    "message": "Parent or admin override cannot revive an expired attempt.",
                },
            )

        if attempt.submitted_at is None and attempt.deadline_at and now < attempt.deadline_at:
            attempt.state = "active"
        elif attempt.submitted_at is not None:
            attempt.state = "submitted"

        attempt.integrity_score = 1.0
        attempt.paused_at = None
        attempt.pause_expires_at = None
        attempt.invalid_reason = f"Override allowed by parent: {reason}"

        event = AttemptEvent(
            attempt_id=attempt.id,
            type="parent_override",
            meta={"reason": reason, "parent_id": str(user_id)},
        )
        self.db.add(event)

        audit = AuditLog(
            actor_id=user_id,
            action="quiz_attempt_allowed",
            target_type="quiz_attempt",
            target_id=str(attempt.id),
            meta={
                "reason": reason,
                "previous_state": prev_state,
                "previous_integrity_score": prev_score,
                "student_id": str(attempt.student_id),
            },
        )
        self.db.add(audit)
        await self.db.commit()
        await self.db.refresh(attempt)
        return attempt
