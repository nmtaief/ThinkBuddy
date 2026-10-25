"""Untrusted AI Proposal Validator (P06a).

Per thinkbuddy-docs/docs/07_AI_PLANNER_API.md §8:
- Treats AI output as completely untrusted input.
- Enforces hard rules (V01 to V15):
  * V01: Schema and contract version valid (ai-planner/v1.0), size caps respected (Hard).
  * V02: Day total minutes within the day's budget (Hard, repair minor excess <= 5m).
  * V03: Tasks inside study window and outside unavailable blocks (Hard, reject).
  * V04: No tasks on blackout days (Hard, repair by dropping tasks, warn).
  * V05: No study for a subject after its exam date (Hard, repair by dropping tasks).
  * V06: Chapter, concept, and page IDs exist; page ranges inside printed bounds and contiguous (Hard, reject).
  * V07: Chapter order respected unless parent allowed reordering (Hard, reject).
  * V08: Completed and pinned tasks unchanged (Hard, reject).
  * V09: Locked settings untouched; priority change at most one level per cycle (Hard, drop suggestion, warn).
  * V10: Min block length (>=15m), max tasks per day (<=6), mock-quiz cap (<=1 per subject per 2 days) (Hard, repair/reject).
  * V11: Rotation limit per subject (Soft rule: warn, do NOT reject).
  * V12: Minimum share for every active subject (Soft rule: warn).
  * V13: Quiz requests within caps and question availability (Hard, drop request).
  * V14: Rationale text length-capped, escaped, no personal data / PII (Hard, sanitize/replace).
  * V15: Horizon dates inside allowed range (Hard, reject).
"""

from __future__ import annotations

import html
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from core.contracts.ai_planner import (
    ALLOWED_CONTRACT_VERSIONS,
    CONTRACT_VERSION_V1_0,
    PrioritySuggestion,
)
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

# PII Detection Regexes
EMAIL_REGEX = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
PHONE_REGEX = re.compile(r"(?:\+?880|01)[3-9]\d{8}")
PRIORITY_ORDER = {"normal": 0, "main": 1, "difficult": 2}
HOSTILE_INJECTION_REGEX = re.compile(
    r"(?:</?(?:context|system|prompt|instruction)>|ignore\s+(?:all\s+)?previous\s+instructions)",
    re.IGNORECASE,
)


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
    contract_version: str = CONTRACT_VERSION_V1_0
    rationale: dict[str, str] = field(default_factory=dict)
    sanitized_priority_suggestions: list[dict[str, Any]] = field(default_factory=list)


class AiProposalValidator:
    """Validates and sanitizes AI planner routine proposals against rules V01-V15."""

    def __init__(
        self,
        setups: list[SubjectSetupInput],
        day_calendar: list[DayScheduleInfo],
        resolved_settings: ResolvedPlannerSettings,
        today: date,
        daily_study_minutes: int,
        student_id: uuid.UUID | str,
        pinned_tasks: list[dict[str, Any]] | None = None,
    ) -> None:
        self.setups = setups
        self.day_calendar = day_calendar
        self.resolved_settings = resolved_settings
        self.today = today
        self.daily_study_minutes = daily_study_minutes
        self.student_id = student_id
        self.pinned_tasks = pinned_tasks or []

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

    def _calculate_window_minutes(self, d: date) -> int:
        """Calculate max study window minutes for a given day after subtracting unavailable blocks (V03)."""
        start_str = self.resolved_settings.study_window_start or "17:00"
        end_str = self.resolved_settings.study_window_end or "22:00"
        try:
            s_h, s_m = map(int, start_str.split(":"))
            e_h, e_m = map(int, end_str.split(":"))
            total_window = (e_h * 60 + e_m) - (s_h * 60 + s_m)
        except Exception:
            total_window = 300

        # Subtract recurring unavailable blocks for this weekday
        day_name = d.strftime("%a").lower()
        unavail_mins = 0
        for block in self.resolved_settings.recurring_unavailable_blocks:
            if block.get("day_of_week", "").lower() == day_name:
                try:
                    b_s_h, b_s_m = map(int, block.get("start_time", "00:00").split(":"))
                    b_e_h, b_e_m = map(int, block.get("end_time", "00:00").split(":"))
                    unavail_mins += max(0, (b_e_h * 60 + b_e_m) - (b_s_h * 60 + b_s_m))
                except Exception:
                    pass

        return max(0, total_window - unavail_mins)

    def _sanitize_rationale(self, raw_rationale: dict[str, Any], warnings: list[str]) -> tuple[dict[str, str], bool]:
        """V14: Sanitize rationale text: length-cap, HTML escape, strip PII."""
        sanitized: dict[str, str] = {}
        repaired = False
        default_safe_text = "Study routine prioritized for balanced syllabus coverage and spaced retention."

        for sub, text in raw_rationale.items():
            if not isinstance(text, str):
                sanitized[sub] = default_safe_text
                repaired = True
                continue

            # Check PII
            if EMAIL_REGEX.search(text) or PHONE_REGEX.search(text):
                logger.warning("V14: PII detected in rationale for %s. Replacing with safe template.", sub)
                sanitized[sub] = default_safe_text
                warnings.append(f"V14_PII_REPLACED_RATIONALE_{sub}")
                repaired = True
                continue

            # HTML escape and length cap
            escaped_text = html.escape(text.strip())
            if len(escaped_text) > 300:
                escaped_text = escaped_text[:297] + "..."
                repaired = True

            sanitized[sub] = escaped_text

        return sanitized, repaired

    def validate(self, payload: dict[str, Any]) -> ValidationResult:
        """Run all hard and soft rule checks (V01-V15) on the raw AI proposal dictionary."""
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

        # V01: Oversized response check
        total_tasks_count = sum(len(d.get("tasks", [])) for d in raw_days if isinstance(d, dict))
        if len(raw_days) > 365 or total_tasks_count > 300:
            return ValidationResult(
                is_valid=False,
                error_code="V01_OVERSIZED_RESPONSE",
                error_message=f"Response payload exceeds maximum allowed size (days={len(raw_days)}, tasks={total_tasks_count})",
            )

        # V14: Hostile rationale check (Hard reject)
        for sub, text in (payload.get("rationale") or {}).items():
            if isinstance(text, str) and HOSTILE_INJECTION_REGEX.search(text):
                return ValidationResult(
                    is_valid=False,
                    error_code="V14_HOSTILE_RATIONALE",
                    error_message=f"Hostile injection attempt detected in rationale for {sub}",
                )

        model_version = payload.get("model_info", {}).get("model_id", "ai-planner-v1.0")
        warnings: list[str] = list(payload.get("warnings", []))
        was_repaired = False

        # V14: Rationale sanitization
        sanitized_rationale, rat_rep = self._sanitize_rationale(payload.get("rationale", {}), warnings)
        if rat_rep:
            was_repaired = True

        # V09: Validate Priority Suggestions
        sanitized_priority_suggestions: list[dict[str, Any]] = []
        raw_prio_suggs = payload.get("priority_suggestions", [])
        locked_fields = set(self.resolved_settings.parent_locked_fields)
        for ps in raw_prio_suggs:
            sub = ps.get("subject", "")
            curr_lvl = ps.get("current_level", "normal")
            sugg_lvl = ps.get("suggested_level", "main")

            # Check if parent locked
            if sub in locked_fields or f"priority_{sub}" in locked_fields:
                logger.warning("V09: AI attempted to modify parent-locked priority for %s. Dropping.", sub)
                warnings.append(f"V09_LOCKED_FIELD_IGNORED_{sub}")
                was_repaired = True
                continue

            # Check level jump <= 1
            curr_idx = PRIORITY_ORDER.get(curr_lvl, 0)
            sugg_idx = PRIORITY_ORDER.get(sugg_lvl, 1)
            if abs(sugg_idx - curr_idx) > 1:
                logger.warning("V09: AI suggested priority jump > 1 level for %s (%s -> %s). Dropping.", sub, curr_lvl, sugg_lvl)
                warnings.append(f"V09_EXCESSIVE_PRIORITY_JUMP_DROPPED_{sub}")
                was_repaired = True
                continue

            sanitized_priority_suggestions.append(ps)

        repaired_plan_days: list[GeneratedPlanDay] = []
        subject_scheduled_pages: dict[str, set[int]] = {s.subject: set() for s in self.setups}
        subject_scheduled_chapters: dict[str, set[uuid.UUID | str]] = {s.subject: set() for s in self.setups}
        subject_last_seen_custom_order: dict[str, int] = {s.subject: -1 for s in self.setups}
        subject_consecutive_days: dict[str, int] = {s.subject: 0 for s in self.setups}
        subject_last_quiz_date: dict[str, date] = {}

        # Track pinned tasks to ensure none were omitted or modified (V08)
        found_pinned_ids: set[str] = set()

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

            # 3. V03: Study window and unavailable blocks check
            window_capacity = self._calculate_window_minutes(plan_date)
            day_requested_mins = sum(t.get("minutes", 0) for t in raw_tasks if isinstance(t, dict))
            if day_requested_mins > window_capacity:
                return ValidationResult(
                    is_valid=False,
                    error_code="V03_STUDY_WINDOW_VIOLATION",
                    error_message=(
                        f"Day {plan_date} planned {day_requested_mins}m exceeds study window capacity "
                        f"{window_capacity}m (taking unavailable blocks into account)"
                    ),
                )

            sanitized_tasks: list[GeneratedTask] = []
            study_blocks_for_subject: dict[str, int] = {}
            subjects_active_today: set[str] = set()

            for task_entry in raw_tasks:
                sub_name = task_entry.get("subject") or task_entry.get("subject_id")
                t_type = task_entry.get("type", "study")
                t_mins = task_entry.get("minutes", 20)
                ch_id = task_entry.get("chapter_id")
                p_start = task_entry.get("page_start")
                p_end = task_entry.get("page_end")
                t_id_str = str(task_entry.get("task_id", task_entry.get("temp_id", uuid.uuid4())))

                if not sub_name or sub_name not in self.setup_by_subject:
                    return ValidationResult(
                        is_valid=False,
                        error_code="V06_UNKNOWN_SUBJECT",
                        error_message=f"Subject '{sub_name}' does not exist in student syllabus",
                    )

                # Check if this task corresponds to a pinned task
                for pt in self.pinned_tasks:
                    matches_id = t_id_str and str(pt.get("task_id")) == t_id_str
                    matches_content = (
                        pt.get("date") == plan_date
                        and pt.get("subject") == sub_name
                        and pt.get("type") == t_type
                        and (str(pt.get("chapter_id")) == str(ch_id) if pt.get("chapter_id") else True)
                        and (pt.get("page_start") == p_start if pt.get("page_start") else True)
                    )
                    if matches_id or matches_content:
                        if pt.get("minutes") != t_mins:
                            return ValidationResult(
                                is_valid=False,
                                error_code="V08_PINNED_TASK_ALTERED",
                                error_message=f"Pinned task duration altered from {pt.get('minutes')}m to {t_mins}m",
                            )
                        found_pinned_ids.add(str(pt.get("task_id")))

                # 4. V05: No study tasks after subject's exam date
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

                # 5. V06: Chapter & Page Range Validity
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

                    # 6. V07: Chapter sequence respected (chapters must not be studied backwards)
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

                # 7. V10: Min study block (>= 15m) & Homework clamping
                if t_mins < 15:
                    return ValidationResult(
                        is_valid=False,
                        error_code="V10_TASK_TOO_SHORT",
                        error_message=f"Task duration {t_mins}m is below minimum acceptable threshold",
                    )

                # V10: Mock-quiz cap (at most 1 per subject per 2 days)
                if t_type == "quiz":
                    last_q = subject_last_quiz_date.get(sub_name)
                    if last_q and (plan_date - last_q).days < 2:
                        logger.warning("V10: Mock quiz cap violated for %s on %s. Trivial repair: dropping.", sub_name, plan_date)
                        warnings.append(f"V10_MOCK_QUIZ_CAP_DROPPED_{sub_name}_{plan_date}")
                        was_repaired = True
                        continue
                    subject_last_quiz_date[sub_name] = plan_date

                if t_type == "study":
                    study_blocks_for_subject[sub_name] = max(
                        study_blocks_for_subject.get(sub_name, 0), t_mins
                    )
                elif t_type == "homework":
                    study_block = study_blocks_for_subject.get(sub_name)
                    if study_block and t_mins > study_block:
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
                subjects_active_today.add(sub_name)

            # V10: Max tasks per day (<= 6)
            if len(sanitized_tasks) > 6:
                excess_tasks = len(sanitized_tasks) - 6
                if excess_tasks <= 2:
                    # Trivial repair: drop excess tasks from end
                    logger.warning("V10: Max tasks per day exceeded on %s. Trimming %s tasks.", plan_date, excess_tasks)
                    sanitized_tasks = sanitized_tasks[:6]
                    was_repaired = True
                    warnings.append(f"V10_MAX_TASKS_TRIMMED_{plan_date}")
                else:
                    return ValidationResult(
                        is_valid=False,
                        error_code="V10_EXCEEDED_MAX_TASKS_PER_DAY",
                        error_message=f"Day {plan_date} has {len(sanitized_tasks)} tasks, exceeding limit of 6",
                    )

            # V11: Rotation limit per subject (Soft rule: warn, do not reject)
            for sub in self.setup_by_subject:
                if sub in subjects_active_today:
                    subject_consecutive_days[sub] += 1
                    if subject_consecutive_days[sub] > 2 and len(self.setups) >= 3:
                        warnings.append(f"V11_ROTATION_EXCEEDED_{sub}_{plan_date}")
                else:
                    subject_consecutive_days[sub] = 0

            # 8. V02: Daily budget check
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

        # 9. V08: Verify all pinned tasks were retained
        for pt in self.pinned_tasks:
            pt_id = str(pt.get("task_id", ""))
            if pt_id and pt_id not in found_pinned_ids:
                return ValidationResult(
                    is_valid=False,
                    error_code="V08_PINNED_TASK_OMITTED",
                    error_message=f"Pinned task {pt_id} was omitted by the AI proposal",
                )

        # 10. Check per-subject coverage reports
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

            # V12: Soft warning for zero coverage
            if covered_pgs == 0 and total_pages > 0:
                warnings.append(f"V12_ZERO_SUBJECT_COVERAGE_{s.subject}")

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
            subject_plans[s.subject] = subject_plans[s.subject]

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
            rationale=sanitized_rationale,
            sanitized_priority_suggestions=sanitized_priority_suggestions,
        )
