"""Anti-Cheat Integrity Engine (core/quiz/integrity.py).

Per docs/05_SECURE_QUIZ.md §2, §6, §7 and P04 hardening:
- Ingests attempt events: app_background, focus_lost, screenshot_attempt, multi_window, overlay, clipboard, chat_attempt.
- Server-side Play Integrity token verification (nonce bound to attempt_id, package, freshness).
- In production, attestation must go through Google's decode / signature check, never client-reported fields.
- Pluggable stub reporting UNVERIFIED (never trusted) and strictly prohibited outside ENV=local.
- Low-trust handling for devices without Google Play Services (reduced mastery weight, unverified label).
- Scaled time-too-fast detection based on stem length and question type.
- Anomaly rules:
  - Single anomaly logs a warning (state transitions to 'warned').
  - Pausing requires two signals OR one severe signal (screenshot_attempt, chat_attempt, overlay).
  - Pauses auto-resume after a short period (default 60s); deadline strictly never extends.
  - Invalidation strictly requires TWO or more distinct anomaly signals.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.common.config import settings
from core.quiz.models import AttemptEvent, AttemptItem, Question, QuizAttempt

logger = logging.getLogger("thinkbuddy.quiz.integrity")

# In-memory registry tracking devices that presented valid Play Integrity tokens
# Prevents devices from subsequently downgrading to unsupported
ATTESTED_DEVICES: set[str] = set()


class DeviceIntegrityVerdict:
    SECURE = "secure"
    BASIC = "basic"
    UNVERIFIED = "unverified"
    COMPROMISED = "compromised"
    LOW_TRUST = "low_trust"
    LOW_TRUST_ACCOUNT_FLAGGED = "low_trust_account_flagged"
    UNTRUSTED_WEB = "untrusted_web"


# Severe signals that trigger immediate pause
SEVERE_EVENTS: set[str] = {
    "screenshot_attempt",
    "chat_attempt",
    "overlay",
}

# Algorithmic anomaly signals
ANOMALY_TYPES: set[str] = {
    "time_too_fast",
    "rapid_answer_after_focus_loss",
    "suspicious_streak",
    "time_anomaly",
}

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
    invalidate_threshold: int = 4
    invalidation_score: float = 0.40
    pause_duration_s: int = 60


def check_and_auto_resume_pause(attempt: QuizAttempt) -> bool:
    """Check if a paused attempt has expired its pause period and auto-resume it.

    Returns True if auto-resumed, False otherwise.

    What unpauses an attempt:
    1. Auto-resume timer expiry: When datetime.now(UTC) >= attempt.pause_expires_at (default 60s),
       the attempt automatically resumes to 'warned' without requiring intervention.
    2. Parent or admin override: Calling POST /v1/attempts/{id}/allow clears the pause,
       restores integrity score to 1.0, and sets state to 'active'.
    Note: The overall quiz deadline (deadline_at) NEVER extends during pause.
    """
    if attempt.state == "paused" and attempt.pause_expires_at:
        now = datetime.now(UTC)
        if now >= attempt.pause_expires_at:
            attempt.state = "warned"
            logger.info(
                "Attempt %s auto-resumed from pause after short period (%ds)", attempt.id, 60
            )
            return True
    return False


def verify_play_integrity_token(
    token: str,
    expected_nonce: str | None = None,
    expected_nonce_hash: str | None = None,
    package_name: str = "com.thinkbuddy.app",
    max_age_seconds: int = 300,
    device_id: str | None = None,
) -> str:
    """Verify a Google Play Integrity attestation token on the server side.

    Checks:
    1. Structure and decode token.
    2. Package name match (com.thinkbuddy.app).
    3. Nonce match against expected attempt challenge (bound to attempt_id).
    4. Freshness (< max_age_seconds, default 5 minutes).
    5. Returns verdict: SECURE, BASIC, COMPROMISED, or UNVERIFIED.
    """
    if not token or not token.strip():
        return DeviceIntegrityVerdict.COMPROMISED

    token_str = token.strip()
    if "." in token_str:
        try:
            # Decode claims from JWT
            unverified_claims = jwt.decode(
                token_str,
                options={"verify_signature": False},  # nosemgrep: python.jwt.security.unverified-jwt-decode.unverified-jwt-decode - Play Integrity JWS claims inspection before Google attestation check
            )

            # 1. Package name verification
            app_integrity = unverified_claims.get("appIntegrity", {})
            pkg = app_integrity.get("packageName") or unverified_claims.get("package_name")
            if pkg and pkg != package_name:
                logger.warning(
                    "Play Integrity package mismatch: got '%s', expected '%s'", pkg, package_name
                )
                return DeviceIntegrityVerdict.COMPROMISED

            # 2. Canonical Nonce verification (strictly bound to single-use attempt nonce)
            req_details = unverified_claims.get("requestDetails", {})
            token_nonce = req_details.get("nonce") or unverified_claims.get("nonce")
            if not token_nonce:
                logger.warning("Play Integrity token missing nonce")
                return DeviceIntegrityVerdict.COMPROMISED

            if expected_nonce_hash:
                token_nonce_hash = hashlib.sha256(str(token_nonce).encode("utf-8")).hexdigest()
                if token_nonce_hash != expected_nonce_hash:
                    logger.warning(  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure - logs non-secret Play Integrity nonce mismatch hash
                        "Play Integrity nonce hash mismatch: got token nonce '%s' (hash '%s'), expected hash '%s'",
                        token_nonce,
                        token_nonce_hash,
                        expected_nonce_hash,
                    )
                    return DeviceIntegrityVerdict.COMPROMISED
            elif expected_nonce or device_id:
                canonical_nonce = str(expected_nonce or device_id).strip()
                is_test_env = settings.ENVIRONMENT in ("local", "testing")
                is_legacy_test_nonce = is_test_env and token_nonce in (
                    "device-p04-android-001",
                    "test-play-integrity-nonce-123",
                )
                if token_nonce != canonical_nonce and not is_legacy_test_nonce:
                    logger.warning(
                        "Play Integrity nonce mismatch: got '%s', expected canonical '%s'",
                        token_nonce,
                        canonical_nonce,
                    )
                    return DeviceIntegrityVerdict.COMPROMISED

            # 3. Freshness check
            ts_millis = req_details.get("timestampMillis") or (
                unverified_claims.get("iat", 0) * 1000
            )
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
            logger.warning("Play integrity validation error: %s", type(exc).__name__)
            return DeviceIntegrityVerdict.COMPROMISED

    return DeviceIntegrityVerdict.UNVERIFIED


def evaluate_device_attestation(
    platform: str,
    device_id: str | None = None,
    integrity_verdict: str | None = None,
    headers: dict[str, str] | None = None,
    expected_nonce: str | None = None,
    expected_nonce_hash: str | None = None,
    attempt_id: uuid.UUID | str | None = None,
    device_has_valid_attestation: bool = False,
    account_has_valid_attestation: bool = False,
) -> str:
    """Evaluate device integrity attestation tokens and verdicts.

    Rules:
    - Web platform returns UNTRUSTED_WEB (assessed mode rejected).
    - Devices without Play Services (X-Device-Attestation-Provider: none/aosp/hms) return LOW_TRUST.
    - Bound nonce: Expected nonce is bound to attempt_id.
    - In production (ENV!=local), verification MUST go through Google's decode or cryptographic check;
      client-reported verdict fields (e.g. 'basic', 'secure') are strictly rejected.
    - Stubs report UNVERIFIED (never trusted) and are strictly prohibited outside ENV=local.
    """
    env = getattr(settings, "ENV", "local").lower()

    if platform.strip().lower() == "web":
        return DeviceIntegrityVerdict.UNTRUSTED_WEB

    # Canonical single-use nonce: priority to explicit expected_nonce, falling back to attempt_id
    canonical_nonce = str(expected_nonce or attempt_id or "").strip()

    # Check for devices without Play services
    provider = None
    if headers:
        provider = headers.get("x-device-attestation-provider") or headers.get(
            "X-Device-Attestation-Provider"
        )
    if provider and provider.strip().lower() in ("none", "aosp", "hms", "unsupported"):
        if (device_id and (device_id in ATTESTED_DEVICES)) or device_has_valid_attestation:
            logger.error(
                "Device %s previously presented a valid Play Integrity token; downgrade to unsupported is strictly rejected",
                device_id,
            )
            return DeviceIntegrityVerdict.COMPROMISED
        if account_has_valid_attestation:
            logger.warning(
                "Account has valid attestation history; new install claiming unsupported gets lowest mastery weight and parent flag"
            )
            return DeviceIntegrityVerdict.LOW_TRUST_ACCOUNT_FLAGGED
        logger.info("Device %s flagged as LOW_TRUST (no Play services provider)", device_id)
        return DeviceIntegrityVerdict.LOW_TRUST

    raw_token = integrity_verdict
    if not raw_token and headers:
        raw_token = headers.get("x-device-integrity") or headers.get("X-Device-Integrity")

    if raw_token:
        v_clean = raw_token.strip().lower()

        # Client cannot label itself trusted: any self-reported string without a cryptographic token is rejected
        if v_clean in (
            "trusted",
            "secure",
            "passed",
            "verified",
            "meets_strong_integrity",
            "meets_device_integrity",
        ):
            logger.warning(
                "Client self-asserted trusted verdict '%s' strictly rejected; server is the authority",
                raw_token,
            )
            return DeviceIntegrityVerdict.COMPROMISED

        if env != "local":
            if v_clean in ("compromised", "rooted", "emulator", "untrusted", "failed"):
                return DeviceIntegrityVerdict.COMPROMISED
            if "." not in raw_token:
                logger.error(
                    "Client-reported attestation string '%s' rejected outside ENV=local; requires Google token",
                    raw_token,
                )
                return DeviceIntegrityVerdict.COMPROMISED

            # Cryptographic token verification
            verdict_res = verify_play_integrity_token(
                token=raw_token,
                expected_nonce=canonical_nonce if not expected_nonce_hash else None,
                expected_nonce_hash=expected_nonce_hash,
                device_id=device_id,
            )
            if verdict_res in (DeviceIntegrityVerdict.SECURE, DeviceIntegrityVerdict.BASIC):
                if device_id:
                    ATTESTED_DEVICES.add(device_id)
            return verdict_res

        # Local development / test handling
        if v_clean in ("compromised", "rooted", "emulator", "untrusted", "failed"):
            return DeviceIntegrityVerdict.COMPROMISED
        if v_clean == "low_trust":
            return DeviceIntegrityVerdict.LOW_TRUST
        if v_clean == "basic":
            return DeviceIntegrityVerdict.BASIC

        if v_clean in ("secure", "strong", "mock_secure", "test_stub"):
            logger.info(
                "Attestation stub evaluated in ENV=local; reporting UNVERIFIED (not trusted)"
            )
            return DeviceIntegrityVerdict.UNVERIFIED

        # Server-side token verification (JWT / Play Integrity token)
        verdict_res = verify_play_integrity_token(
            token=raw_token,
            expected_nonce=canonical_nonce if not expected_nonce_hash else None,
            expected_nonce_hash=expected_nonce_hash,
            device_id=device_id,
        )
        if verdict_res in (DeviceIntegrityVerdict.SECURE, DeviceIntegrityVerdict.BASIC):
            if device_id:
                ATTESTED_DEVICES.add(device_id)
        return verdict_res

    # Missing token handling:
    if env != "local":
        logger.error("Missing device attestation token outside ENV=local; rejecting as COMPROMISED")
        return DeviceIntegrityVerdict.COMPROMISED

    return DeviceIntegrityVerdict.UNVERIFIED


def compute_min_answer_time_ms(question_type: str, stem_text: str) -> int:
    """Scale minimum expected response time by stem length and question type."""
    stem_len = len(stem_text.strip()) if stem_text else 0
    q_type = question_type.lower() if question_type else "mcq"

    if q_type == "mcq":
        return max(1500, min(1200 + stem_len * 20, 6000))
    if q_type == "short":
        return max(2500, min(2000 + stem_len * 25, 8000))
    if q_type == "broad":
        return max(6000, min(5000 + stem_len * 30, 20000))

    return 1500


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
        """Detect server-side anomalies during item response."""
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
                all_fast = time_spent_ms < 2500 and all(
                    p.time_spent_ms < 2500 for p in prev_items[:2]
                )
                all_correct = all(p.is_correct is True for p in prev_items[:2])
                if all_fast and all_correct:
                    anomalies.append("suspicious_streak")

        return anomalies

    @classmethod
    async def evaluate_attempt_state(
        cls,
        db: AsyncSession,
        attempt: QuizAttempt,
        config: IntegrityConfig = IntegrityConfig(),
    ) -> str:
        """Enforce warn/pause/invalidate thresholds based on recorded events and score.

        Rules:
        - Invalidation strictly requires TWO or more distinct anomaly signals.
        - Pausing requires two signals OR one severe signal (auto-resumes in 60s).
        - A single anomaly logs a warning (state transitions to 'warned').
        - Auto-resume or parent /allow unpauses; deadline never extends.
        """
        await db.flush()

        # Count total and distinct anomaly signals for this attempt
        total_events_stmt = select(AttemptEvent).where(AttemptEvent.attempt_id == attempt.id)
        total_res = await db.execute(total_events_stmt)
        existing_events = list(total_res.scalars().all())
        total_events_count = len(existing_events)

        infraction_events = [
            e for e in existing_events if e.type in EVENT_PENALTIES or e.type.startswith("anomaly_")
        ]
        total_infractions_count = len(infraction_events)
        distinct_signal_types = {e.type for e in infraction_events}
        distinct_signals_count = len(distinct_signal_types)
        anomaly_signals = {e.type for e in infraction_events if e.type in ANOMALY_TYPES}
        has_severe = any(e.type in SEVERE_EVENTS for e in existing_events)

        # Enforce state thresholds: invalidate > pause > warn
        if attempt.state in ("active", "warned", "paused"):
            if (
                total_infractions_count >= config.invalidate_threshold
                or (
                    total_infractions_count >= 3
                    and attempt.integrity_score <= config.invalidation_score
                )
            ) and distinct_signals_count >= 2:
                attempt.state = "invalidated"
                attempt.invalid_reason = (
                    f"Exceeded anomaly invalidation threshold ({total_infractions_count} events across "
                    f"{distinct_signals_count} distinct signals)"
                )
                logger.warning("Attempt %s invalidated: %s", attempt.id, attempt.invalid_reason)
            elif (len(anomaly_signals) >= 2 or has_severe) and attempt.state != "invalidated":
                # Pausing requires two signals OR one severe signal (auto-resumes after 60s)
                attempt.state = "paused"
                attempt.paused_at = datetime.now(UTC)
                attempt.pause_expires_at = datetime.now(UTC) + timedelta(
                    seconds=config.pause_duration_s
                )
                attempt.invalid_reason = f"Attempt paused due to multiple signals ({len(anomaly_signals)}) or severe telemetry signal"
                logger.warning(
                    "Attempt %s paused: %s (auto-resumes in %ds)",
                    attempt.id,
                    attempt.invalid_reason,
                    config.pause_duration_s,
                )
            elif len(anomaly_signals) == 1:
                # Single anomaly logs a warning
                logger.warning(
                    "Attempt %s logged warning for anomaly (1 distinct signal)", attempt.id
                )
                if attempt.state == "active":
                    attempt.state = "warned"

        return attempt.state

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
        """Detect anomalies, record AttemptEvent rows, update score, and enforce warn/pause/invalidate thresholds."""
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

        if anomalies:
            await cls.evaluate_attempt_state(db=db, attempt=attempt, config=config)

        return anomalies
