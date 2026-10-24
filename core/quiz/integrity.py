"""Anti-Cheat Integrity Engine (core/quiz/integrity.py).

Per docs/05_SECURE_QUIZ.md §2, §6, §7:
- Ingests attempt events: app_background, focus_lost, screenshot_attempt, multi_window, overlay, clipboard, chat_attempt.
- Evaluates device integrity verdict at attempt start (pluggable stub for Play Integrity / App Attest).
- Server-side anomaly detection: time too fast, answers right after focus loss, perfect streaks.
- Configurable thresholds: warn, pause, invalidate.
- Calculates integrity_score based on event weights and anomalies.
- Flags suspicious attempts for parents/teachers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.quiz.models import AttemptEvent, AttemptItem, QuizAttempt

logger = logging.getLogger("thinkbuddy.quiz.integrity")


class DeviceIntegrityVerdict:
    SECURE = "secure"
    BASIC = "basic"
    COMPROMISED = "compromised"
    UNTRUSTED_WEB = "untrusted_web"


def evaluate_device_attestation(
    platform: str,
    device_id: str | None = None,
    integrity_verdict: str | None = None,
    headers: dict[str, str] | None = None,
) -> str:
    """Pluggable stub for evaluating device integrity attestation tokens / verdicts.

    Can be replaced or extended with Google Play Integrity / Apple App Attest integrations.
    Checks:
    1. Direct verdict parameter (e.g. from attestation service or payload).
    2. 'X-Device-Integrity' header if present.
    3. Detects rooted/emulator signals.
    """
    verdict = integrity_verdict
    if not verdict and headers:
        verdict = headers.get("x-device-integrity") or headers.get("X-Device-Integrity")

    if verdict:
        v_clean = verdict.strip().lower()
        if v_clean in ("compromised", "rooted", "emulator", "untrusted", "failed"):
            return DeviceIntegrityVerdict.COMPROMISED

    if platform.strip().lower() == "web":
        return DeviceIntegrityVerdict.UNTRUSTED_WEB

    return DeviceIntegrityVerdict.SECURE


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
        """Record an integrity event and update attempt state.

        Returns:
            tuple[float, str]: (new_integrity_score, attempt_state)
        """
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
            attempt.invalid_reason = (
                f"Integrity score fell below threshold ({attempt.integrity_score})"
            )
            logger.warning(
                "Attempt %s invalidated: integrity score %.2f", attempt.id, attempt.integrity_score
            )
            return attempt.integrity_score, attempt.state

        return attempt.integrity_score, attempt.state

    @staticmethod
    async def detect_anomalies(
        db: AsyncSession,
        attempt: QuizAttempt,
        item: AttemptItem,
        time_spent_ms: int,
        is_correct: bool,
        config: IntegrityConfig = IntegrityConfig(),
    ) -> list[str]:
        """Detect server-side anomalies during item response:

        1. time_too_fast: Answered suspiciously fast (< min_answer_time_ms).
        2. rapid_answer_after_focus_loss: Answered immediately after a focus loss / app background event.
        3. suspicious_streak: Perfect correct answers submitted suspiciously fast or after anomalies.
        """
        anomalies: list[str] = []

        # 1. Anomaly: Time too fast
        if 0 < time_spent_ms < config.min_answer_time_ms:
            anomalies.append("time_too_fast")

        # 2. Anomaly: Answers right after focus loss
        # Query recent events for this attempt
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

        # 3. Anomaly: Suspicious perfect streak after anomaly
        if is_correct:
            # Check previously answered items
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

            # If previous 2 items were also correct and all answered in < 2500ms
            if len(prev_items) >= 2:
                all_fast = time_spent_ms < 2500 and all(
                    p.time_spent_ms < 2500 for p in prev_items[:2]
                )
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
        config: IntegrityConfig = IntegrityConfig(),
    ) -> list[str]:
        """Detect anomalies, record AttemptEvent rows, update score, and enforce warn/pause/invalidate thresholds."""
        anomalies = await cls.detect_anomalies(
            db=db,
            attempt=attempt,
            item=item,
            time_spent_ms=time_spent_ms,
            is_correct=is_correct,
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

        # Count total events on this attempt to enforce configurable thresholds
        total_events_stmt = select(AttemptEvent).where(AttemptEvent.attempt_id == attempt.id)
        total_res = await db.execute(total_events_stmt)
        total_events_count = len(list(total_res.scalars().all())) + len(anomalies)

        # Enforce state thresholds: invalidate > pause > warn
        if attempt.state == "active":
            if (
                total_events_count >= config.invalidate_threshold
                or attempt.integrity_score <= config.invalidation_score
            ):
                attempt.state = "invalidated"
                attempt.invalid_reason = (
                    f"Exceeded anomaly invalidation threshold ({total_events_count} events)"
                )
                logger.warning("Attempt %s invalidated: %s", attempt.id, attempt.invalid_reason)
            elif total_events_count >= config.pause_threshold:
                attempt.state = "paused"
                attempt.invalid_reason = f"Attempt paused due to repeated telemetry anomalies ({total_events_count} events)"
                logger.warning("Attempt %s paused: %s", attempt.id, attempt.invalid_reason)
            elif total_events_count >= config.warn_threshold:
                logger.info(
                    "Attempt %s warning threshold reached (%d events)",
                    attempt.id,
                    total_events_count,
                )

        return anomalies
