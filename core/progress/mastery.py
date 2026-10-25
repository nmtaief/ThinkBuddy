"""Pure functional library for calculating student mastery and confidence.

Deliverable 2 & Requirement 7:
- Deterministic, pure library (no DB or clock dependencies).
- Exponential recency decay toward baseline.
- Confidence tracking based on signal count and decay.
- Never labels as 'weak' in parent-facing output: returns 'needs_practice' or 'not_enough_data'.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from core.progress.schemas import MasteryStatus
from core.progress.weights import DEFAULT_MASTERY_CONFIG, MasteryWeightsConfig


@dataclass(frozen=True)
class SignalInput:
    """Learning signal representation for pure mastery calculation."""

    source: str
    weight: float = 1.0
    at: datetime | None = None
    is_unverified_device: bool = False


@dataclass(frozen=True)
class MasteryResult:
    """Pure calculation result with bounded scores and localized labels."""

    score: float
    confidence: float
    status: MasteryStatus
    status_label_bn: str
    suggested_action: str
    suggested_action_bn: str


def compute_mastery(
    signals: list[SignalInput],
    initial_score: float = 0.5,
    initial_confidence: float = 0.0,
    last_updated_at: datetime | None = None,
    evaluation_time: datetime | None = None,
    config: MasteryWeightsConfig = DEFAULT_MASTERY_CONFIG,
) -> MasteryResult:
    """Compute bounded mastery score and confidence with recency decay.

    Formula:
    1. Apply exponential decay to prior score toward baseline (0.5) over elapsed time:
       decay = exp(-ln(2) / half_life_days * elapsed_days)
    2. Sum net signal impacts scaled by signal weight and unverified device multipliers.
    3. Clamp final score strictly between [0.0, 1.0].
    4. Compute confidence between [0.0, 1.0].
    """
    current_score = initial_score
    current_conf = initial_confidence

    eval_t = evaluation_time or datetime.now()

    # 1. Apply recency decay from last update to evaluation time
    if last_updated_at is not None and eval_t > last_updated_at:
        elapsed_days = max(0.0, (eval_t - last_updated_at).total_seconds() / 86400.0)
        decay_constant = math.log(2) / max(0.1, config.half_life_days)
        decay_factor = math.exp(-decay_constant * elapsed_days)

        # Score decays toward neutral baseline (0.5)
        current_score = 0.5 + (current_score - 0.5) * decay_factor
        current_conf = current_conf * decay_factor

    # 2. Ingest learning signals
    # Map sources to configured delta impacts
    signal_impact_map = {
        "quiz_correct": config.assessed_quiz_correct,
        "quiz_wrong": config.assessed_quiz_wrong,
        "practice_correct": config.practice_quiz_correct,
        "practice_wrong": config.practice_quiz_wrong,
        "quiz_slow": config.quiz_slow_correct,
        "ai_question": config.ai_question,
        "ai_repeat": config.ai_repeat,
        "task_skipped": config.task_skipped,
        "teacher_flag": config.teacher_flag,
    }

    total_signal_weight = 0.0
    for sig in signals:
        base_impact = signal_impact_map.get(sig.source, 0.0)
        effective_impact = base_impact * sig.weight

        if sig.is_unverified_device:
            effective_impact *= config.unverified_device_multiplier

        current_score += effective_impact
        total_signal_weight += abs(sig.weight)

    # 3. Clamp score strictly to [0.0, 1.0]
    final_score = round(max(0.0, min(1.0, current_score)), 4)

    # 4. Confidence scaling based on accumulated signal weight
    added_conf = total_signal_weight / max(1.0, config.confidence_saturation_signals)
    final_conf = round(max(0.0, min(1.0, current_conf + added_conf)), 4)

    # 5. Determine parent-safe status (Requirement 7: never label as 'weak')
    if final_conf < config.min_confidence_threshold:
        status: MasteryStatus = "not_enough_data"
        label_bn = "পর্যাপ্ত তথ্য নেই"
        action_en = "Complete study and daily quiz to establish mastery."
        action_bn = "দক্ষতা মূল্যায়নের জন্য পড়াশোনা ও কুইজ সম্পন্ন করো।"
    elif final_score >= config.mastery_threshold:
        status = "mastered"
        label_bn = "দক্ষতা অর্জিত"
        action_en = "Maintain mastery with spaced repetition reviews."
        action_bn = "ধারাবাহিক রিভিশনের মাধ্যমে অর্জিত দক্ষতা ধরে রাখো।"
    elif final_score < config.needs_practice_threshold:
        status = "needs_practice"
        label_bn = "আরও অনুশীলনের প্রয়োজন"
        action_en = "Review textbook chapter summary and practice key questions."
        action_bn = "পাঠ্যবইয়ের সারসংক্ষেপ পর্যালোচনা ও নমুনা প্রশ্ন অনুশীলন করো।"
    else:
        status = "in_progress"
        label_bn = "চলমান"
        action_en = "Continue regular daily study and homework practice."
        action_bn = "নিয়মিত পড়াশোনা ও বাড়ির কাজ অনুশীলন চালিয়ে যাও।"

    return MasteryResult(
        score=final_score,
        confidence=final_conf,
        status=status,
        status_label_bn=label_bn,
        suggested_action=action_en,
        suggested_action_bn=action_bn,
    )
