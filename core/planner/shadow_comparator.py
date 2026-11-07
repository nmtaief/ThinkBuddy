"""Shadow-Mode Comparison Engine & Metrics (P06a).

Per docs/07_AI_PLANNER_API.md §10, §12:
Runs the AI planner alongside the deterministic baseline planner in shadow mode,
comparing outputs on coverage parity, budget discipline, churn, and violations.
"""

from __future__ import annotations

import logging
from typing import Any

from core.planner.engine import MultiSubjectPlanOutput

logger = logging.getLogger("thinkbuddy.planner.shadow")


def compare_plans(
    ai_plan: MultiSubjectPlanOutput,
    baseline_plan: MultiSubjectPlanOutput,
) -> dict[str, Any]:
    """Compare an AI proposal against the deterministic baseline."""
    ai_total_minutes = sum(d.planned_minutes for d in ai_plan.days)
    base_total_minutes = sum(d.planned_minutes for d in baseline_plan.days)
    ai_total_tasks = sum(len(d.tasks) for d in ai_plan.days)
    base_total_tasks = sum(len(d.tasks) for d in baseline_plan.days)

    # Coverage parity check: AI scheduled pages >= baseline scheduled pages
    coverage_comparison: dict[str, dict[str, Any]] = {}
    coverage_parity_met = True

    for sub, b_rep in baseline_plan.coverage_reports.items():
        ai_rep = ai_plan.coverage_reports.get(sub)
        ai_pages = ai_rep.scheduled_pages if ai_rep else 0
        b_pages = b_rep.scheduled_pages

        parity = ai_pages >= b_pages
        if not parity:
            coverage_parity_met = False

        coverage_comparison[sub] = {
            "baseline_pages": b_pages,
            "ai_pages": ai_pages,
            "baseline_coverage_pct": b_rep.coverage_pct,
            "ai_coverage_pct": ai_rep.coverage_pct if ai_rep else 0.0,
            "parity_met": parity,
        }

    # Churn metric: how many days differ in scheduled subjects
    day_differences = 0
    common_dates = min(len(ai_plan.days), len(baseline_plan.days))
    for i in range(common_dates):
        ai_subs = {t.subject for t in ai_plan.days[i].tasks}
        b_subs = {t.subject for t in baseline_plan.days[i].tasks}
        if ai_subs != b_subs:
            day_differences += 1

    churn_rate = (day_differences / max(1, common_dates)) * 100.0

    report: dict[str, Any] = {
        "metrics": {
            "ai_total_minutes": ai_total_minutes,
            "baseline_total_minutes": base_total_minutes,
            "minutes_delta": ai_total_minutes - base_total_minutes,
            "ai_total_tasks": ai_total_tasks,
            "baseline_total_tasks": base_total_tasks,
            "coverage_parity_met": coverage_parity_met,
            "churn_rate_pct": round(churn_rate, 1),
            "ai_warnings_count": len(ai_plan.warnings),
        },
        "coverage_by_subject": coverage_comparison,
        "recommendation": "PASS" if coverage_parity_met else "FAIL_COVERAGE_DROP",
    }

    logger.info(
        "AI Shadow Mode Comparison: Delta=%+dm, Churn=%.1f%%, Parity=%s, Recommendation=%s",
        ai_total_minutes - base_total_minutes,
        churn_rate,
        coverage_parity_met,
        report["recommendation"],
    )

    return report
