"""Pseudonymization module for AI Planner requests (P06a).

Per docs/07_AI_PLANNER_API.md §4, §5 & §11:
- Never sends: student name, phone numbers, email, school, free text notes, chat content, device IDs.
- Generates pseudonymous `student_ref` using SHA-256 HMAC of student_id with a rotation salt.
- Encapsulates only necessary academic context (class band, curriculum chapters, page bounds,
  mastery, exam dates, daily budget).
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.planner.engine import ChapterPlanInput, SubjectSetupInput
    from core.planner.models import Task
    from core.planner.settings_resolver import DayScheduleInfo, ResolvedPlannerSettings

PSEUDONYMIZATION_SALT = "thinkbuddy_ai_planner_pseudonym_salt_v1"


def generate_student_ref(student_id: uuid.UUID | str) -> str:
    """Generate a pseudonymous, opaque reference ID for a student."""
    raw_bytes = str(student_id).encode("utf-8")
    salt_bytes = PSEUDONYMIZATION_SALT.encode("utf-8")
    digest = hmac.new(salt_bytes, raw_bytes, hashlib.sha256).hexdigest()
    return f"anon-{digest[:16]}"


def build_pseudonymous_snapshot(
    student_id: uuid.UUID | str,
    today: date,
    now_dhaka: datetime,
    resolved_settings: ResolvedPlannerSettings,
    day_calendar: list[DayScheduleInfo],
    setups: list[SubjectSetupInput],
    completed_tasks: list[Task] | None = None,
    idempotency_key: uuid.UUID | str | None = None,
    request_id: uuid.UUID | str | None = None,
    mode: str | None = None,
    locale: str = "bn",
    mastery_records: list[dict[str, Any]] | None = None,
    learning_signals: dict[str, Any] | None = None,
    revision_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Construct a minimal, pseudonymous request payload conforming to docs/07_AI_PLANNER_API.md §4 & §5."""
    student_ref = generate_student_ref(student_id)
    req_id = str(request_id) if request_id else str(uuid.uuid4())
    idem_key = str(idempotency_key) if idempotency_key else str(uuid.uuid4())
    effective_mode = mode or resolved_settings.adaptive_mode or "suggest"

    # Profile & hard limits
    profile_block = {
        "class_band": resolved_settings.class_band,
        "group": resolved_settings.group,
        "medium": "bangla",
        "time_zone": "Asia/Dhaka",
    }

    min_block = (
        resolved_settings.planner_parameters.get("min_study_block_minutes", 20)
        if resolved_settings.planner_parameters
        else 20
    )
    limits_block = {
        "min_study_block_minutes": min_block,
        "max_tasks_per_day": 8,
        "max_consecutive_days_per_subject": 2,
        "mock_quiz_max_frequency_days": 2,
        "school_day_minutes": resolved_settings.school_day_minutes,
        "holiday_minutes": resolved_settings.holiday_minutes,
    }

    settings_block = {
        "priorities": dict(resolved_settings.subject_priorities),
        "rest_weekday": resolved_settings.rest_weekday,
        "study_window": {
            "start": resolved_settings.study_window_start,
            "end": resolved_settings.study_window_end,
        },
        "locked_fields": list(resolved_settings.parent_locked_fields),
        "settings_version": resolved_settings.settings_version,
    }

    # Calendar horizon
    calendar_block = [
        {
            "date": d.date.isoformat(),
            "day_type": d.day_type,
            "available_minutes": d.budget_minutes,
            "zero_day_reason": d.zero_reason,
            "is_exam_day": d.day_type == "exam_day",
            "exam_subjects": list(d.subject_exams),
        }
        for d in day_calendar
    ]

    # Exams & syllabus
    exams_block = []
    syllabus_block = []
    for s in setups:
        exams_block.append(
            {
                "subject": s.subject,
                "exam_date": s.exam_date.isoformat(),
                "weightage": 1.0,
            }
        )
        ch_list = []
        for c in s.chapters:
            ch_list.append(
                {
                    "chapter_id": str(c.id),
                    "number": c.number,
                    "title": c.title,
                    "book_title": c.book_title,
                    "printed_page_start": c.printed_page_start,
                    "printed_page_end": c.printed_page_end,
                    "total_pages": c.total_pages,
                    "difficulty_factor": c.difficulty_factor,
                    "effective_mastery": c.effective_mastery,
                    "custom_order": c.custom_order,
                }
            )
        syllabus_block.append(
            {
                "subject": s.subject,
                "chapters": ch_list,
            }
        )

    # Progress and pinned historical tasks
    progress_block: list[dict[str, Any]] = []
    pinned_block: list[str] = []
    if completed_tasks:
        for t in completed_tasks:
            pinned_block.append(str(t.id))
            if t.refs and "printed_page_start" in t.refs and "printed_page_end" in t.refs:
                progress_block.append(
                    {
                        "task_id": str(t.id),
                        "type": t.type,
                        "chapter_id": str(t.chapter_id) if t.chapter_id else None,
                        "printed_page_start": t.refs.get("printed_page_start"),
                        "printed_page_end": t.refs.get("printed_page_end"),
                        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                    }
                )

    # Real Mastery & Learning Signals (docs/07_AI_PLANNER_API.md §5)
    mastery_block: list[dict[str, Any]] = []
    if mastery_records:
        for m in mastery_records:
            mastery_block.append(
                {
                    "chapter_id": str(m.get("chapter_id", "")),
                    "concept_id": str(m.get("concept_id", "")) if m.get("concept_id") else None,
                    "score": float(m.get("score", 0.0)),
                    "confidence": float(m.get("confidence", 0.0)),
                    "last_seen": m.get("last_seen"),
                }
            )

    signals_block: dict[str, Any] = {}
    if learning_signals:
        signals_block = {
            "quiz_accuracy": float(learning_signals.get("quiz_accuracy", 0.0)),
            "speed_vs_expected": float(learning_signals.get("speed_vs_expected", 1.0)),
            "repeated_chat_topics": list(learning_signals.get("repeated_chat_topics", [])),
            "skipped_tasks_count": int(learning_signals.get("skipped_tasks_count", 0)),
            "self_rated_difficulty": learning_signals.get("self_rated_difficulty"),
        }

    revision_block: list[dict[str, Any]] = []
    if revision_items:
        for r in revision_items:
            revision_block.append(
                {
                    "chapter_id": str(r.get("chapter_id", "")),
                    "concept_id": str(r.get("concept_id", "")) if r.get("concept_id") else None,
                    "box": int(r.get("box", 1)),
                    "due_at": r.get("due_at"),
                }
            )

    return {
        "contract_version": "ai-planner/v1.0",
        "request_id": req_id,
        "idempotency_key": idem_key,
        "student_ref": student_ref,
        "as_of": now_dhaka.isoformat(),
        "locale": locale,
        "mode": effective_mode,
        "profile": profile_block,
        "limits": limits_block,
        "settings": settings_block,
        "calendar": calendar_block,
        "exams": exams_block,
        "syllabus": syllabus_block,
        "progress": progress_block,
        "mastery": mastery_block,
        "signals": signals_block,
        "revision": revision_block,
        "pinned": pinned_block,
        "options": {
            "planning_goal": "balanced",
            "horizon_days": len(day_calendar),
        },
    }
