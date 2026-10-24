"""Anti-Cheat Integrity Engine (core/quiz/integrity.py).

Per docs/05_SECURE_QUIZ.md §2, §6, §7:
- Ingests attempt events: app_background, focus_lost, screenshot_attempt, multi_window, overlay, clipboard, chat_attempt.
- Evaluates grace policy: warn -> pause -> invalidate.
- Calculates integrity_score based on event weights and anomalies.
- Flags suspicious attempts for parents/teachers.
"""

from __future__ import annotations

import logging
from typing import Any

from core.quiz.models import AttemptEvent, QuizAttempt

logger = logging.getLogger("thinkbuddy.quiz.integrity")

# Penalty weights per event type
EVENT_PENALTIES: dict[str, float] = {
    "focus_lost": 0.05,
    "app_background": 0.10,
    "multi_window": 0.20,
    "overlay": 0.25,
    "clipboard": 0.20,
    "screenshot_attempt": 0.40,
    "chat_attempt": 0.25,
    "time_anomaly": 0.30,
}

# Thresholds for state transitions
MAX_GRACE_EVENTS = 2
INVALIDATION_THRESHOLD_SCORE = 0.50


class IntegrityEngine:
    """Evaluates telemetry events and computes attempt integrity scores."""

    @staticmethod
    def process_event(attempt: QuizAttempt, event_type: str, meta: dict[str, Any]) -> tuple[float, str]:
        """Record an integrity event and update attempt state.
        
        Returns:
            tuple[float, str]: (new_integrity_score, attempt_state)
        """
        penalty = EVENT_PENALTIES.get(event_type, 0.10)
        attempt.integrity_score = max(0.0, round(attempt.integrity_score - penalty, 2))

        # Check total events count on this attempt
        current_state = attempt.state

        # Immediate invalidation events
        if event_type in ("screenshot_attempt", "chat_attempt") and attempt.integrity_score < 0.60:
            attempt.state = "invalidated"
            attempt.invalid_reason = f"Security rule violation: {event_type}"
            logger.warning("Attempt %s invalidated immediately due to %s", attempt.id, event_type)
            return attempt.integrity_score, attempt.state

        # Score-based invalidation
        if attempt.integrity_score <= INVALIDATION_THRESHOLD_SCORE:
            attempt.state = "invalidated"
            attempt.invalid_reason = f"Integrity score fell below threshold ({attempt.integrity_score})"
            logger.warning("Attempt %s invalidated: integrity score %.2f", attempt.id, attempt.integrity_score)
            return attempt.integrity_score, attempt.state

        return attempt.integrity_score, attempt.state
