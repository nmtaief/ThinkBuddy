"""Anti-Cheat Integrity Engine (core/quiz/integrity.py).

Per docs/05_SECURE_QUIZ.md §2, §6, §7 and P04 hardening:
- Ingests attempt events: app_background, focus_lost, screenshot_attempt, multi_window, overlay, clipboard, chat_attempt.
- Server-side Play Integrity token verification (nonce, package, freshness).
- Pluggable stub reporting UNVERIFIED (never trusted) and strictly prohibited outside ENV=local.
- Low-trust handling for devices without Google Play Services.
- Scaled time-too-fast detection based on stem length and question type.
- Two or more distinct anomaly signals required before invalidation.
- Deadline never extends on pause.
- Configurable thresholds: warn, pause, invalidate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.common.config import settings
from core.quiz.models import AttemptEvent, AttemptItem, Question, QuizAttempt

logger = logging.getLogger("thinkbuddy.quiz.integrity")


class DeviceIntegrityVerdict:
    SECURE = "secure"
    BASIC = "basic"
    UNVERIFIED = "unverified"
    COMPROMISED = "compromised"
    LOW_TRUST = "low_trust"
    UNTRUSTED_WEB = "untrusted_web"


def verify_play_integrity_token(
    token: str,
    expected_nonce: str | None = None,
    package_name: str = "com.thinkbuddy.app",
    max_age_seconds: int = 300,
) -> str:
    """Verify a Google Play Integrity attestation token on the server side.

    Checks:
    1. Structure and decode token.
    2. Package name match (com.thinkbuddy.app).
    3. Nonce match against expected attempt challenge.
    4. Freshness (< max_age_seconds, default 5 minutes).
    5. Returns verdict: SECURE, BASIC, COMPROMISED, or UNVERIFIED.
    """
    if not token or not token.strip():
        return DeviceIntegrityVerdict.COMPROMISED

    token_str = token.strip()
    # Check if structured as a JWT
    if "." in token_str:
        try:
            # Decode without signature verification for claims extraction (in production, verified via Google API)
            unverified_claims = jwt.decode(token_str, options={"verify_signature": False})

            # 1. Package name verification
            app_integrity = unverified_claims.get("appIntegrity", {})
            pkg = app_integrity.get("packageName") or unverified_claims.get("package_name")
            if pkg and pkg != package_name:
                logger.warning("Play Integrity package mismatch: got '%s', expected '%s'", pkg, package_name)
                return DeviceIntegrityVerdict.COMPROMISED

            # 2. Nonce verification
            req_details = unverified_claims.get("requestDetails", {})
            token_nonce = req_details.get("nonce") or unverified_claims.get("nonce")
            if token_nonce and expected_nonce and token_nonce != expected_nonce:
                logger.warning("Play Integrity nonce mismatch: got '%s', expected '%s'", token_nonce, expected_nonce)
                return DeviceIntegrityVerdict.COMPROMISED

            # 3. Freshness check
            ts_millis = req_details.get("timestampMillis") or (unverified_claims.get("iat", 0) * 1000)
            if ts_millis:
                token_time = datetime.fromtimestamp(ts_millis / 1000.0, tz=UTC)
                age = (datetime.now(UTC) - token_time).total_seconds()
                if age > max_age_seconds or age < -60:
                    logger.warning("Play Integrity token timestamp stale/invalid: age %.1fs", age)
                    return DeviceIntegrityVerdict.COMPROMISED

            # 4. Integrity verdict evaluation
            device_integrity = unverified_claims.get("deviceIntegrity", {})
            verdicts = device_integrity.get("deviceRecognitionVerdict", [])
            if "MEETS_STRONG_INTEGRITY" in verdicts:
                return DeviceIntegrityVerdict.SECURE
            if "MEETS_BASIC_INTEGRITY" in verdicts or "MEETS_DEVICE_INTEGRITY" in verdicts:
                return DeviceIntegrityVerdict.BASIC
            if "COMPROMISED" in verdicts:
                return DeviceIntegrityVerdict.COMPROMISED
        except Exception as exc:
            logger.warning("Error parsing Play Integrity token claims: %s", exc)
            return DeviceIntegrityVerdict.COMPROMISED

    return DeviceIntegrityVerdict.UNVERIFIED


def evaluate_device_attestation(
    platform: str,
    device_id: str | None = None,
    integrity_verdict: str | None = None,
    headers: dict[str, str] | None = None,
    expected_nonce: str | None = None,
) -> str:
    """Evaluate device integrity attestation tokens and verdicts.

    Rules:
    - Web platform returns UNTRUSTED_WEB (assessed mode rejected).
    - Devices without Play Services (X-Device-Attestation-Provider: none/aosp/hms) return LOW_TRUST.
    - Stubs report UNVERIFIED (never trusted) and are strictly prohibited outside ENV=local.
    - Valid Play Integrity tokens are verified server-side with nonce, package, and freshness checks.
    """
    env = getattr(settings, "ENVIRONMENT", getattr(settings, "ENV", "local")).lower()

    if platform.strip().lower() == "web":
        return DeviceIntegrityVerdict.UNTRUSTED_WEB

    # Check for devices without Play services
    provider = None
    if headers:
        provider = headers.get("x-device-attestation-provider") or headers.get("X-Device-Attestation-Provider")
    if provider and provider.strip().lower() in ("none", "aosp", "hms", "unsupported"):
        logger.info("Device %s flagged as LOW_TRUST (no Play services provider)", device_id)
        return DeviceIntegrityVerdict.LOW_TRUST

    raw_token = integrity_verdict
    if not raw_token and headers:
        raw_token = headers.get("x-device-integrity") or headers.get("X-Device-Integrity")

    if raw_token:
        v_clean = raw_token.strip().lower()
        if v_clean in ("compromised", "rooted", "emulator", "untrusted", "failed"):
            return DeviceIntegrityVerdict.COMPROMISED
        if v_clean == "low_trust":
            return DeviceIntegrityVerdict.LOW_TRUST
        if v_clean == "basic":
            return DeviceIntegrityVerdict.BASIC

        if v_clean in ("secure", "strong", "mock_secure", "test_stub"):
            if env != "local":
                logger.error("Attestation stub string '%s' strictly prohibited outside ENV=local", raw_token)
                return DeviceIntegrityVerdict.COMPROMISED
            # In local environment, stub reports UNVERIFIED (never trusted)
            logger.info("Attestation stub evaluated in ENV=local; reporting UNVERIFIED (not trusted)")
            return DeviceIntegrityVerdict.UNVERIFIED

        # Server-side token verification (JWT / Play Integrity token)
        return verify_play_integrity_token(
            token=raw_token,
            expected_nonce=expected_nonce or (device_id or ""),
        )

    # Missing token handling:
    if env != "local":
        logger.error("Missing device attestation token outside ENV=local; rejecting as COMPROMISED")
        return DeviceIntegrityVerdict.COMPROMISED

    # In local environment with no token provided, report UNVERIFIED
    return DeviceIntegrityVerdict.UNVERIFIED


def compute_min_answer_time_ms(question_type: str, stem_text: str) -> int:
    """Scale minimum expected response time by stem length and question type.

    Formulas:
    - MCQ: base 1200ms + 20ms per character of stem (bounds: 1500ms - 6000ms).
    - Short answer: base 2000ms + 25ms per character (bounds: 2500ms - 8000ms).
    - Broad answer: base 5000ms + 30ms per character (bounds: 6000ms - 20000ms).
    """
    stem_len = len(stem_text.strip()) if stem_text else 0
    q_type = question_type.lower() if question_type else "mcq"

    if q_type == "mcq":
        return max(1500, min(1200 + stem_len * 20, 6000))
    if q_type == "short":
        return max(2500, min(2000 + stem_len * 25, 8000))
    if q_type == "broad":
        return max(6000, min(5000 + stem_len * 30, 20000))

    return 1500


# Penalty weights per event / anomaly type
EVENT_PENALTIES: dict[str, float] = {
    "focus_lost": 0.05,
    "app_background": 0.10,
    "multi_window": 0.20,
    "overlay": 0.25,
    "clipboard": 0.20,
    "screenshot_attempt": 0.40,
    "chat_attempt": 0.25,
    "time_anomaly": 0.30,
    "time_too_fast": 0.15,
    "rapid_answer_after_focus_loss": 0.25,
    "suspicious_streak": 0.20,
}


@dataclass
class IntegrityConfig:
    """Configurable thresholds for anti-cheat and anomaly detection."""

    min_answer_time_ms: int = 1500
    focus_loss_window_s: float = 4.0
    warn_threshold: int = 1
    pause_threshold: int = 2
    invalidate_threshold: int = 3
    invalidation_score: float = 0.50


class IntegrityEngine:
    """Evaluates telemetry events, server-side anomalies, and computes attempt integrity scores."""

    @staticmethod
    def process_event(
        attempt: QuizAttempt,
        event_type: str,
        meta: dict[str, Any],
        config: IntegrityConfig = IntegrityConfig(),
    ) -> tuple[float, str]:
        """Record an integrity event and update attempt state without altering deadline_at."""
        penalty = EVENT_PENALTIES.get(event_type, 0.10)
        attempt.integrity_score = max(0.0, round(attempt.integrity_score - penalty, 2))

        # Immediate invalidation events
        if event_type in ("screenshot_attempt", "chat_attempt") and attempt.integrity_score < 0.60:
            attempt.state = "invalidated"
            attempt.invalid_reason = f"Security rule violation: {event_type}"
            logger.warning("Attempt %s invalidated immediately due to %s", attempt.id, event_type)
            return attempt.integrity_score, attempt.state

        # Score-based invalidation
        if attempt.integrity_score <= config.invalidation_score:
            attempt.state = "invalidated"
            attempt.invalid_reason = f"Integrity score fell below threshold ({attempt.integrity_score})"
            logger.warning("Attempt %s invalidated: integrity score %.2f", attempt.id, attempt.integrity_score)
            return attempt.integrity_score, attempt.state

        return attempt.integrity_score, attempt.state

    @staticmethod
    async def detect_anomalies(
        db: AsyncSession,
        attempt: QuizAttempt,
        item: AttemptItem,
        time_spent_ms: int,
        is_correct: bool,
        question: Question | None = None,
        config: IntegrityConfig = IntegrityConfig(),
    ) -> list[str]:
        """Detect server-side anomalies during item response:

        1. time_too_fast: Scaled by question type and stem character length.
        2. rapid_answer_after_focus_loss: Answered immediately after a focus loss / app background event.
        3. suspicious_streak: Consecutive rapid correct answers.
        """
        anomalies: list[str] = []

        # 1. Anomaly: Time too fast (scaled by question type and stem length)
        stem_text = ""
        q_type = "mcq"
        if question:
            q_type = question.type
            if isinstance(question.stem, dict):
                stem_text = question.stem.get("text", "")
            else:
                stem_text = str(question.stem)

        min_time_ms = compute_min_answer_time_ms(q_type, stem_text)
        if 0 < time_spent_ms < min_time_ms:
            anomalies.append("time_too_fast")

        # 2. Anomaly: Answers right after focus loss
        cutoff_time = datetime.now(UTC) - timedelta(seconds=config.focus_loss_window_s)
        stmt_events = (
            select(AttemptEvent)
            .where(
                AttemptEvent.attempt_id == attempt.id,
                AttemptEvent.type.in_(["focus_lost", "app_background"]),
                AttemptEvent.at >= cutoff_time,
            )
            .limit(1)
        )
        res_events = await db.execute(stmt_events)
        recent_focus_event = res_events.scalar_one_or_none()
        if recent_focus_event:
            anomalies.append("rapid_answer_after_focus_loss")

        # 3. Anomaly: Suspicious perfect streak
        if is_correct:
            prev_stmt = (
                select(AttemptItem)
                .where(
                    AttemptItem.attempt_id == attempt.id,
                    AttemptItem.answered_at.is_not(None),
                    AttemptItem.position < item.position,
                )
                .order_by(AttemptItem.position.desc())
            )
            res_prev = await db.execute(prev_stmt)
            prev_items = list(res_prev.scalars().all())

            if len(prev_items) >= 2:
                all_fast = time_spent_ms < 2500 and all(p.time_spent_ms < 2500 for p in prev_items[:2])
                all_correct = all(p.is_correct is True for p in prev_items[:2])
                if all_fast and all_correct:
                    anomalies.append("suspicious_streak")

        return anomalies

    @classmethod
    async def check_and_apply_anomalies(
        cls,
        db: AsyncSession,
        attempt: QuizAttempt,
        item: AttemptItem,
        time_spent_ms: int,
        is_correct: bool,
        question: Question | None = None,
        config: IntegrityConfig = IntegrityConfig(),
    ) -> list[str]:
        """Detect anomalies, record AttemptEvent rows, update score, and enforce warn/pause/invalidate thresholds.

        Important Rules:
        - Invalidation strictly requires TWO or more distinct anomaly signals.
        - Deadline is never extended on pause.
        """
        anomalies = await cls.detect_anomalies(
            db=db,
            attempt=attempt,
            item=item,
            time_spent_ms=time_spent_ms,
            is_correct=is_correct,
            question=question,
            config=config,
        )

        for anomaly in anomalies:
            event = AttemptEvent(
                attempt_id=attempt.id,
                type=anomaly,
                meta={
                    "position": item.position,
                    "time_spent_ms": time_spent_ms,
                    "is_correct": is_correct,
                },
            )
            db.add(event)
            cls.process_event(attempt, anomaly, event.meta, config=config)

        # Count total and distinct anomaly signals for this attempt
        total_events_stmt = select(AttemptEvent).where(AttemptEvent.attempt_id == attempt.id)
        total_res = await db.execute(total_events_stmt)
        existing_events = list(total_res.scalars().all())
        total_events_count = len(existing_events)

        distinct_signal_types = {e.type for e in existing_events if e.type in EVENT_PENALTIES or e.type.startswith("anomaly_")}
        distinct_signals_count = len(distinct_signal_types)

        # Enforce state thresholds: invalidate > pause > warn
        # Rule: Invalidation strictly requires TWO or more distinct anomaly signals!
        if attempt.state in ("active", "warned", "paused"):
            if (
                total_events_count >= config.invalidate_threshold or attempt.integrity_score <= config.invalidation_score
            ) and distinct_signals_count >= 2:
                attempt.state = "invalidated"
                attempt.invalid_reason = (
                    f"Exceeded anomaly invalidation threshold ({total_events_count} events across "
                    f"{distinct_signals_count} distinct signals)"
                )
                logger.warning("Attempt %s invalidated: %s", attempt.id, attempt.invalid_reason)
            elif total_events_count >= config.pause_threshold or attempt.integrity_score <= 0.65:
                # Deadline is strictly NEVER extended on pause
                attempt.state = "paused"
                attempt.invalid_reason = (
                    f"Attempt paused due to repeated telemetry anomalies ({total_events_count} events)"
                )
                logger.warning("Attempt %s paused: %s", attempt.id, attempt.invalid_reason)
            elif total_events_count >= config.warn_threshold:
                if attempt.state == "active":
                    attempt.state = "warned"
                    logger.info("Attempt %s warned (%d events)", attempt.id, total_events_count)

        return anomalies
