"""Mastery calculation weights and configuration per docs/06_ADAPTIVE_ENGINE.md §2.

Deliverable 2: Config in one weights file for transparent tuning and testability.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MasteryWeightsConfig:
    """Configurable weights and thresholds for learning signals and mastery."""

    # Learning signal score impacts
    assessed_quiz_correct: float = 0.20
    assessed_quiz_wrong: float = -0.25
    practice_quiz_correct: float = 0.08
    practice_quiz_wrong: float = -0.10
    quiz_slow_correct: float = -0.05
    ai_question: float = -0.05
    ai_repeat: float = -0.15
    task_skipped: float = -0.08
    teacher_flag: float = -0.30

    # Device trust penalty (P04 anti-cheat hand-off)
    unverified_device_multiplier: float = 0.70

    # Recency decay: half-life in days (14.0 days default)
    half_life_days: float = 14.0

    # Confidence scaling: number of signals required for 1.0 confidence
    confidence_saturation_signals: float = 10.0

    # Categorization thresholds (Requirement 7: never label as 'weak')
    min_confidence_threshold: float = 0.35  # Below this -> "not_enough_data"
    mastery_threshold: float = 0.80  # At or above -> "mastered"
    needs_practice_threshold: float = 0.50  # Below this -> "needs_practice"


DEFAULT_MASTERY_CONFIG = MasteryWeightsConfig()
