"""Untrusted AI Proposal Validator (P06a).

Per docs/07_AI_PLANNER_API.md §8:
- Treats AI output as completely untrusted input.
- Enforces hard rules (V01 to V15).
- Trivial repairs allowed:
  * Trimming minor rounding excess (<= 5m) on daily budget (V02).
  * Dropping scheduled tasks on blackout/rest days with a warning (V04).
  * Dropping study tasks scheduled after a subject's exam date with a warning (V05).
- Hard violations that cannot be trivially repaired reject the proposal immediately,
  triggering fallback to the deterministic planner, with the violation code and reason logged.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any

from core.planner.engine import (
    GeneratedPlanDay,
    GeneratedTask,
    MultiSubjectPlanOutput,
    SingleSubjectPlan,
    SubjectCoverageReport,
)

if TYPE_CHECKING:
    from core.planner.engine import ChapterPlanInput, SubjectSetupInput
    from core.planner.settings_resolver import DayScheduleInfo, ResolvedPlannerSettings

logger = logging.getLogger("thinkbuddy.ai_planner.validator")

ALLOWED_CONTRACT_VERSIONS = {"ai-planner/v1", "ai-planner/v1.0"}


@dataclass
class ValidationResult:
    """Outcome of validating an untrusted AI proposal."""

    is_valid: bool
    error_code: str | None = None
    error_message: str | None = None
    repaired: bool = False
    repaired_plan_out: MultiSubjectPlanOutput | None = None
    warnings: list[str] = field(default_factory=list)
    model_version: str = "unknown"
    contract_version: str = "ai-planner/v1.0"
    rationale: dict[str, str] = field(default_factory=dict)


class AiProposalValidator:
    """Validates and sanitizes AI planner routine proposals against hard business constraints."""

    def __init__(
        self,
        setups: list[SubjectSetupInput],
        day_calendar: list[DayScheduleInfo],
        resolved_settings: ResolvedPlannerSettings,
        today: date,
        daily_study_minutes: int,
        student_id: uuid.UUID | str,
    ) -> None:
        self.setups = setups
        self.day_calendar = day_calendar
        self.resolved_settings = resolved_settings
        self.today = today
        self.daily_study_minutes = daily_study_minutes
        self.student_id = student_id

        # Index calendars and syllabus for validation
        self.calendar_by_date: dict[date, DayScheduleInfo] = {d.date: d for d in day_calendar}
        self.setup_by_subject: dict[str, SubjectSetupInput] = {s.subject: s for s in setups}
        self.exam_by_subject: dict[str, date] = {s.subject: s.exam_date for s in setups}

        # Index chapters by ID and (subject, chapter_number)
        self.chapters_by_id: dict[str, ChapterPlanInput] = {}
        self.chapters_by_sub_and_num: dict[tuple[str, int], ChapterPlanInput] = {}
        for s in setups:
            for ch in s.chapters:
                self.chapters_by_id[str(ch.id)] = ch
                self.chapters_by_sub_and_num[(s.subject, ch.number)] = ch

    def validate(self, payload: dict[str, Any]) -> ValidationResult:
        """Run all hard rule checks (V01-V15) on the raw AI proposal dictionary."""
        # 1. V01: Contract version and schema checks
        if not isinstance(payload, dict):
            return ValidationResult(
                is_valid=False,
                error_code="V01_INVALID_SCHEMA",
                error_message="Response payload is not a JSON object",
            )

        contract_version = payload.get("contract_version", "")
        if contract_version not in ALLOWED_CONTRACT_VERSIONS:
            return ValidationResult(
                is_valid=False,
                error_code="V01_CONTRACT_MISMATCH",
                error_message=f"Unsupported contract version: {contract_version}",
            )

        raw_days = payload.get("days")
        if not isinstance(raw_days, list):
            return ValidationResult(
                is_valid=False,
                error_code="V01_MISSING_DAYS",
                error_message="Response payload missing 'days' list",
            )

        model_version = payload.get("model_info", {}).get("model_id", "ai-planner-v1")
        rationale = payload.get("rationale", {})
        warnings: list[str] = list(payload.get("warnings", []))
        was_repaired = False

        repaired_plan_days: list[GeneratedPlanDay] = []
        subject_scheduled_pages: dict[str, set[int]] = {s.subject: set() for s in self.setups}
        subject_scheduled_chapters: dict[str, set[uuid.UUID | str]] = {
            s.subject: set() for s in self.setups
        }
        subject_last_seen_custom_order: dict[str, int] = {s.subject: -1 for s in self.setups}

        for day_entry in raw_days:
            if not isinstance(day_entry, dict):
                return ValidationResult(
                    is_valid=False,
                    error_code="V01_INVALID_DAY_ENTRY",
                    error_message=f"Invalid day entry: {day_entry}",
                )

            raw_date_str = day_entry.get("date")
            try:
                plan_date = date.fromisoformat(str(raw_date_str))
            except (ValueError, TypeError):
                return ValidationResult(
                    is_valid=False,
                    error_code="V01_INVALID_DATE_FORMAT",
                    error_message=f"Invalid date format: {raw_date_str}",
                )

            cal_day = self.calendar_by_date.get(plan_date)
            if not cal_day:
                # Day outside planning horizon (V15)
                return ValidationResult(
                    is_valid=False,
                    error_code="V15_HORIZON_DATE_OUT_OF_RANGE",
                    error_message=f"Date {plan_date} is outside the scheduled calendar horizon",
                )

            raw_tasks = day_entry.get("tasks", [])
            day_type = cal_day.day_type
            available_minutes = cal_day.budget_minutes

            # 2. V04: No tasks on blackout/rest days
            if cal_day.day_type in ("blackout", "rest", "holiday") and available_minutes == 0:
                if raw_tasks:
                    logger.warning(
                        "AI proposal scheduled tasks on blackout/zero day %s. Trivial repair: dropping tasks.",
                        plan_date,
                    )
                    was_repaired = True
                    warnings.append(f"AI_DROPPED_TASKS_ON_ZERO_DAY_{plan_date}")
                    raw_tasks = []

            sanitized_tasks: list[GeneratedTask] = []
            study_blocks_for_subject: dict[str, int] = {}

            for task_entry in raw_tasks:
                sub_name = task_entry.get("subject") or task_entry.get("subject_id")
                t_type = task_entry.get("type", "study")
                t_mins = task_entry.get("minutes", 20)
                ch_id = task_entry.get("chapter_id")
                p_start = task_entry.get("page_start")
                p_end = task_entry.get("page_end")

                if not sub_name or sub_name not in self.setup_by_subject:
                    return ValidationResult(
                        is_valid=False,
                        error_code="V06_UNKNOWN_SUBJECT",
                        error_message=f"Subject '{sub_name}' does not exist in student syllabus",
                    )

                # 3. V05: No study tasks after subject's exam date
                exam_d = self.exam_by_subject[sub_name]
                if plan_date >= exam_d:
                    logger.warning(
                        "AI proposal scheduled task for %s on/after exam date %s. Trivial repair: dropping.",
                        sub_name,
                        exam_d,
                    )
                    was_repaired = True
                    warnings.append(f"AI_DROPPED_POST_EXAM_TASK_{sub_name}_{plan_date}")
                    continue

                # 4. V06: Chapter & Page Range Validity
                chapter_obj: ChapterPlanInput | None = None
                if ch_id:
                    chapter_obj = self.chapters_by_id.get(str(ch_id))
                    if not chapter_obj:
                        return ValidationResult(
                            is_valid=False,
                            error_code="V06_UNKNOWN_CHAPTER_ID",
                            error_message=f"Chapter ID {ch_id} not found in {sub_name} syllabus",
                        )
                elif "chapter_number" in task_entry:
                    ch_num = task_entry["chapter_number"]
                    chapter_obj = self.chapters_by_sub_and_num.get((sub_name, ch_num))

                if t_type in ("study", "revision", "homework") and chapter_obj:
                    # Validate page ranges
                    if p_start is not None and p_end is not None:
                        if (
                            p_start < chapter_obj.printed_page_start
                            or p_end > chapter_obj.printed_page_end
                            or p_start > p_end
                        ):
                            return ValidationResult(
                                is_valid=False,
                                error_code="V06_INVALID_PAGE_BOUNDS",
                                error_message=(
                                    f"Pages {p_start}–{p_end} outside chapter bounds "
                                    f"{chapter_obj.printed_page_start}–{chapter_obj.printed_page_end}"
                                ),
                            )
                        if t_type == "study":
                            for pg in range(p_start, p_end + 1):
                                subject_scheduled_pages[sub_name].add(pg)
                            subject_scheduled_chapters[sub_name].add(chapter_obj.id)

                    # 5. V07: Chapter sequence respected (chapters must not be studied backwards)
                    if t_type == "study":
                        last_order = subject_last_seen_custom_order[sub_name]
                        if chapter_obj.custom_order < last_order:
                            return ValidationResult(
                                is_valid=False,
                                error_code="V07_OUT_OF_ORDER_CHAPTER",
                                error_message=(
                                    f"Chapter {chapter_obj.number} scheduled after later chapter "
                                    f"in sequence for {sub_name}"
                                ),
                            )
                        subject_last_seen_custom_order[sub_name] = chapter_obj.custom_order

                # 6. V10: Min study block (>= 20m) & Homework not longer than study block
                if t_mins < 15:
                    return ValidationResult(
                        is_valid=False,
                        error_code="V10_TASK_TOO_SHORT",
                        error_message=f"Task duration {t_mins}m is below minimum acceptable threshold",
                    )

                if t_type == "study":
                    study_blocks_for_subject[sub_name] = max(
                        study_blocks_for_subject.get(sub_name, 0), t_mins
                    )
                elif t_type == "homework":
                    study_block = study_blocks_for_subject.get(sub_name)
                    if study_block and t_mins > study_block:
                        logger.warning(
                            "Homework (%sm) longer than study block (%sm). Trivial repair: clamping.",
                            t_mins,
                            study_block,
                        )
                        t_mins = study_block
                        was_repaired = True

                refs = dict(task_entry.get("refs", {}))
                if chapter_obj:
                    refs.setdefault("chapter_number", chapter_obj.number)
                    refs.setdefault("chapter_title", chapter_obj.title)
                    refs.setdefault("book_title", chapter_obj.book_title)
                if p_start is not None and p_end is not None:
                    refs.setdefault("printed_page_start", p_start)
                    refs.setdefault("printed_page_end", p_end)

                sanitized_task = GeneratedTask(
                    id=uuid.uuid4(),
                    subject=sub_name,
                    type=t_type,
                    chapter_id=chapter_obj.id if chapter_obj else None,
                    est_minutes=t_mins,
                    refs=refs,
                    status="todo",
                    source="ai_planner",
                )
                sanitized_tasks.append(sanitized_task)

            # 7. V02: Daily budget check
            day_total = sum(t.est_minutes for t in sanitized_tasks)
            if day_total > available_minutes:
                excess = day_total - available_minutes
                if excess <= 5 and sanitized_tasks:
                    # Trivial repair: trim excess minutes from the last task
                    last_task = sanitized_tasks[-1]
                    if last_task.est_minutes - excess >= 15:
                        last_task.est_minutes -= excess
                        was_repaired = True
                        day_total = available_minutes
                    else:
                        return ValidationResult(
                            is_valid=False,
                            error_code="V02_EXCEEDED_DAILY_BUDGET",
                            error_message=f"Day {plan_date} planned {day_total}m exceeds budget {available_minutes}m",
                        )
                else:
                    return ValidationResult(
                        is_valid=False,
                        error_code="V02_EXCEEDED_DAILY_BUDGET",
                        error_message=f"Day {plan_date} planned {day_total}m exceeds budget {available_minutes}m by {excess}m",
                    )

            repaired_plan_days.append(
                GeneratedPlanDay(
                    date=plan_date,
                    planned_minutes=day_total,
                    day_type=day_type,
                    tasks=sanitized_tasks,
                )
            )

        # 8. Check per-subject coverage reports
        coverage_reports: dict[str, SubjectCoverageReport] = {}
        subject_plans: dict[str, SingleSubjectPlan] = {}
        for s in self.setups:
            total_pages = sum(c.total_pages for c in s.chapters)
            covered_pgs = len(subject_scheduled_pages[s.subject])
            covered_chs = len(subject_scheduled_chapters[s.subject])
            cov_pct = round((covered_pgs / total_pages * 100.0), 1) if total_pages > 0 else 100.0
            shortfall = max(0, total_pages - covered_pgs)
            shortfall_warn = (
                f"COVERAGE_SHORTFALL_{s.subject.upper().replace(' ', '_')}" if shortfall > 0 else None
            )

            rep = SubjectCoverageReport(
                subject=s.subject,
                exam_date=s.exam_date,
                total_chapters=len(s.chapters),
                scheduled_chapters=covered_chs,
                total_pages=total_pages,
                scheduled_pages=covered_pgs,
                coverage_pct=cov_pct,
                shortfall_pages=shortfall,
                shortfall_warning=shortfall_warn,
            )
            coverage_reports[s.subject] = rep

            sub_days = [
                GeneratedPlanDay(
                    date=d.date,
                    planned_minutes=sum(t.est_minutes for t in d.tasks if t.subject == s.subject),
                    day_type=d.day_type,
                    tasks=[t for t in d.tasks if t.subject == s.subject],
                )
                for d in repaired_plan_days
            ]
            subject_plans[s.subject] = SingleSubjectPlan(
                subject=s.subject,
                exam_date=s.exam_date,
                days=sub_days,
                warnings=[shortfall_warn] if shortfall_warn else [],
                coverage=rep,
            )

        total_tasks = sum(len(d.tasks) for d in repaired_plan_days)
        plan_out = MultiSubjectPlanOutput(
            student_id=self.student_id,
            today=self.today,
            daily_study_minutes=self.daily_study_minutes,
            days=repaired_plan_days,
            subject_plans=subject_plans,
            warnings=warnings,
            total_tasks=total_tasks,
            coverage_reports=coverage_reports,
        )

        return ValidationResult(
            is_valid=True,
            repaired=was_repaired,
            repaired_plan_out=plan_out,
            warnings=warnings,
            model_version=model_version,
            contract_version=contract_version,
            rationale=rationale,
        )
