"""Mock AI Planner HTTP Service (tests/mock_services/ai_planner.py).

Simulates external AI Planner service per docs/07_AI_PLANNER_API.md:
- Implements:
  * GET /healthz
  * GET /v1/contract
  * POST /v1/plans/propose
  * POST /v1/quizzes/propose
  * POST /v1/revision/propose
  * POST /v1/questions/draft
  * POST /v1/insights/explain
- Supports deterministic simulation toggles to exercise all fault and repair modes.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any
from fastapi import FastAPI, Header, HTTPException, Response

from core.contracts.ai_planner import (
    CONTRACT_VERSION_V1_0,
    PlanProposeResponse,
    ProposedDay,
    ProposedTask,
    PrioritySuggestion,
    QuizRequestSpec,
    QuizProposeResponse,
    RevisionProposeResponse,
    RevisionItemProposal,
    QuestionDraftResponse,
    DraftedQuestion,
    InsightExplainResponse,
)

mock_ai_app = FastAPI(title="Mock AI Planner Service", version="1.0.0")


class SimulationMode:
    NORMAL = "NORMAL"
    TIMEOUT = "TIMEOUT"
    ERROR_500 = "ERROR_500"
    BUDGET_OVERFLOW = "BUDGET_OVERFLOW"
    BLACKOUT_VIOLATION = "BLACKOUT_VIOLATION"
    POST_EXAM_VIOLATION = "POST_EXAM_VIOLATION"
    INVALID_PAGES = "INVALID_PAGES"
    OUT_OF_ORDER_CHAPTER = "OUT_OF_ORDER_CHAPTER"
    INVALID_CONTRACT = "INVALID_CONTRACT"
    STUDY_WINDOW_VIOLATION = "STUDY_WINDOW_VIOLATION"
    PINNED_TASK_VIOLATION = "PINNED_TASK_VIOLATION"
    LOCKED_FIELD_VIOLATION = "LOCKED_FIELD_VIOLATION"
    MAX_TASKS_VIOLATION = "MAX_TASKS_VIOLATION"
    MOCK_QUIZ_CAP_VIOLATION = "MOCK_QUIZ_CAP_VIOLATION"
    PII_RATIONALE_VIOLATION = "PII_RATIONALE_VIOLATION"


# Global state for tests to configure mock behavior
CURRENT_MODE = SimulationMode.NORMAL
REQUEST_COUNT = 0
RECEIVED_REQUESTS: list[dict[str, Any]] = []


def set_simulation_mode(mode: str) -> None:
    global CURRENT_MODE, REQUEST_COUNT, RECEIVED_REQUESTS
    CURRENT_MODE = mode
    REQUEST_COUNT = 0
    RECEIVED_REQUESTS = []


@mock_ai_app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "mock-ai-planner"}


@mock_ai_app.get("/v1/contract")
async def get_contract_info() -> dict[str, Any]:
    return {
        "supported_versions": ["ai-planner/v1", "ai-planner/v1.0"],
        "active_version": CONTRACT_VERSION_V1_0,
        "model_id": "mock-thinkbuddy-ai-planner-v1.0",
    }


@mock_ai_app.post("/v1/plans/propose")
async def propose_plan(
    payload: dict[str, Any],
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    global REQUEST_COUNT
    REQUEST_COUNT += 1
    RECEIVED_REQUESTS.append(payload)

    if CURRENT_MODE == SimulationMode.TIMEOUT:
        import asyncio
        await asyncio.sleep(25.0)  # Exceeds 20s timeout
        return {}

    if CURRENT_MODE == SimulationMode.ERROR_500:
        raise HTTPException(status_code=500, detail="Internal AI Model Engine Failure")

    contract_version = payload.get("contract_version", CONTRACT_VERSION_V1_0)
    if CURRENT_MODE == SimulationMode.INVALID_CONTRACT:
        contract_version = "ai-planner/unsupported-v999"

    calendar = payload.get("calendar", [])
    syllabus = payload.get("syllabus", [])
    limits = payload.get("limits", {})
    pinned = payload.get("pinned", [])

    # Synthesize proposed days
    proposed_days: list[dict[str, Any]] = []

    for day in calendar:
        d_str = day.get("date")
        avail_mins = day.get("available_minutes", 0)
        d_type = day.get("day_type", "school_day")
        cur_d = date.fromisoformat(str(d_str))

        tasks: list[dict[str, Any]] = []

        # Fault Mode: Blackout violation
        if CURRENT_MODE == SimulationMode.BLACKOUT_VIOLATION and avail_mins == 0:
            ch_item = syllabus[0]["chapters"][0] if syllabus and syllabus[0]["chapters"] else {}
            tasks.append({
                "temp_id": str(uuid.uuid4()),
                "type": "study",
                "subject": syllabus[0]["subject"] if syllabus else "Mathematics",
                "chapter_id": ch_item.get("chapter_id") or ch_item.get("id"),
                "page_start": 1,
                "page_end": 10,
                "minutes": 30,
                "reason_code": "ILLEGAL_BLACKOUT_TASK",
            })

        elif avail_mins > 0:
            # Fault Mode: Study window violation (e.g. scheduling 300m when day capacity is 180m)
            if CURRENT_MODE == SimulationMode.STUDY_WINDOW_VIOLATION:
                avail_mins = 600

            # Fault Mode: Budget overflow
            if CURRENT_MODE == SimulationMode.BUDGET_OVERFLOW:
                ch_item = syllabus[0]["chapters"][0] if syllabus and syllabus[0]["chapters"] else {}
                tasks.append({
                    "temp_id": str(uuid.uuid4()),
                    "type": "study",
                    "subject": syllabus[0]["subject"] if syllabus else "Mathematics",
                    "chapter_id": ch_item.get("chapter_id") or ch_item.get("id"),
                    "page_start": 1,
                    "page_end": 10,
                    "minutes": avail_mins + 45,  # Exceeds budget by 45m
                    "reason_code": "EXCESSIVE_OVERFLOW",
                })
            elif CURRENT_MODE == SimulationMode.MAX_TASKS_VIOLATION:
                # Exceed max tasks per day (e.g. 10 tasks)
                ch_item = syllabus[0]["chapters"][0] if syllabus and syllabus[0]["chapters"] else {}
                for t_i in range(10):
                    tasks.append({
                        "temp_id": str(uuid.uuid4()),
                        "type": "study",
                        "subject": syllabus[0]["subject"] if syllabus else "Mathematics",
                        "chapter_id": ch_item.get("chapter_id") or ch_item.get("id"),
                        "page_start": 1,
                        "page_end": 5,
                        "minutes": 20,
                        "reason_code": f"TASK_{t_i}",
                    })
            elif CURRENT_MODE == SimulationMode.MOCK_QUIZ_CAP_VIOLATION:
                # 2 mock quizzes on consecutive days
                tasks.append({
                    "temp_id": str(uuid.uuid4()),
                    "type": "quiz",
                    "subject": syllabus[0]["subject"] if syllabus else "Mathematics",
                    "chapter_id": None,
                    "minutes": 20,
                    "reason_code": "MOCK_QUIZ",
                })
            else:
                # Normal schedule generation across syllabus
                rem_mins = avail_mins
                for sub in syllabus:
                    sub_name = sub.get("subject", "Mathematics")
                    chs = sub.get("chapters", [])
                    if not chs or rem_mins < 20:
                        break

                    chosen_ch = chs[0]

                    # Fault Mode: Out of order chapter
                    if CURRENT_MODE == SimulationMode.OUT_OF_ORDER_CHAPTER and len(chs) > 1:
                        # Schedule chapter 2 before chapter 1
                        chosen_ch = chs[-1]

                    p_start = chosen_ch.get("printed_page_start", 1)
                    p_end = min(chosen_ch.get("printed_page_end", 20), p_start + 10)

                    # Fault Mode: Invalid pages
                    if CURRENT_MODE == SimulationMode.INVALID_PAGES:
                        p_start = 9999
                        p_end = 10050

                    t_mins = min(rem_mins, 45)
                    tasks.append({
                        "temp_id": str(uuid.uuid4()),
                        "type": "study",
                        "subject": sub_name,
                        "chapter_id": chosen_ch.get("chapter_id") or chosen_ch.get("id"),
                        "page_start": p_start,
                        "page_end": p_end,
                        "minutes": t_mins,
                        "reason_code": "CATCH_UP_MISSED",
                    })
                    rem_mins -= t_mins
                    break

        proposed_days.append({
            "date": d_str,
            "tasks": tasks,
        })

    # Priority suggestions
    priority_suggestions: list[dict[str, Any]] = []
    if CURRENT_MODE == SimulationMode.LOCKED_FIELD_VIOLATION:
        # Suggesting priority change on locked field or jumping 2 levels
        priority_suggestions.append({
            "subject": "Mathematics",
            "current_level": "normal",
            "suggested_level": "difficult",  # 2-level jump
            "evidence_codes": ["ACCURACY_LOW"],
            "rationale": "Jump 2 levels",
        })
    elif CURRENT_MODE == SimulationMode.NORMAL:
        priority_suggestions.append({
            "subject": "Physics",
            "current_level": "normal",
            "suggested_level": "main",  # 1-level jump
            "evidence_codes": ["APPROACHING_EXAM"],
            "rationale": "Physics exam approaching in 30 days.",
        })

    # Rationale
    rationale = {
        "Mathematics": "Focusing on fundamental algebraic definitions and formula practice.",
        "Physics": "Reviewing motion equations and velocity definitions before the upcoming test.",
    }
    if CURRENT_MODE == SimulationMode.PII_RATIONALE_VIOLATION:
        rationale["Mathematics"] = "Student John Doe (john@example.com, 01711000000) from Dhaka High School needs help."

    resp = {
        "proposal_id": str(uuid.uuid4()),
        "contract_version": contract_version,
        "model_info": {
            "model_id": "mock-gemini-2.5-flash",
            "version": "1.0.0",
        },
        "confidence": 0.94,
        "data_sufficiency": "ok",
        "days": proposed_days,
        "quiz_requests": [
            {
                "request_ref": str(uuid.uuid4()),
                "kind": "daily",
                "target_concepts": ["concept-1"],
                "item_count": 5,
                "difficulty_mix": {"easy": 0.3, "medium": 0.5, "hard": 0.2},
                "item_types": ["mcq", "short"],
                "mode": "practice",
                "time_limit_s": 600,
            }
        ],
        "priority_suggestions": priority_suggestions,
        "rationale": rationale,
        "warnings": [],
    }

    return resp


@mock_ai_app.post("/v1/quizzes/propose")
async def propose_quizzes(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "proposal_id": str(uuid.uuid4()),
        "contract_version": CONTRACT_VERSION_V1_0,
        "quiz_specs": [
            {
                "request_ref": str(uuid.uuid4()),
                "kind": payload.get("kind", "daily"),
                "target_concepts": payload.get("concept_pool", [])[:3],
                "item_count": 5,
                "difficulty_mix": {"easy": 0.2, "medium": 0.6, "hard": 0.2},
                "item_types": ["mcq", "short"],
                "mode": "practice",
                "time_limit_s": 600,
            }
        ],
    }


@mock_ai_app.post("/v1/revision/propose")
async def propose_revision(payload: dict[str, Any]) -> dict[str, Any]:
    today = date.today()
    return {
        "proposal_id": str(uuid.uuid4()),
        "contract_version": CONTRACT_VERSION_V1_0,
        "revision_items": [
            {
                "chapter_id": str(uuid.uuid4()),
                "concept_id": "concept-rev-1",
                "box": 1,
                "due_date": (today + timedelta(days=2)).isoformat(),
                "reason_code": "SPACED_REVIEW_DUE",
            }
        ],
    }


@mock_ai_app.post("/v1/questions/draft")
async def draft_questions(payload: dict[str, Any]) -> dict[str, Any]:
    chunks = payload.get("source_chunks", [])
    source_ids = [c["chunk_id"] for c in chunks] if chunks else [str(uuid.uuid4())]
    return {
        "proposal_id": str(uuid.uuid4()),
        "contract_version": CONTRACT_VERSION_V1_0,
        "questions": [
            {
                "temp_id": str(uuid.uuid4()),
                "type": "mcq",
                "stem": {"type": "text", "text": "নিচের কোনটি মৌলিক সংখ্যা?"},
                "options": [
                    {"id": str(uuid.uuid4()), "text": "২"},
                    {"id": str(uuid.uuid4()), "text": "৪"},
                    {"id": str(uuid.uuid4()), "text": "৬"},
                    {"id": str(uuid.uuid4()), "text": "৮"},
                ],
                "answer_key": {"correct_option_index": 0},
                "explanation": {"text": "২ হলো একমাত্র জোড় মৌলিক সংখ্যা।"},
                "rubric": {},
                "source_chunk_ids": source_ids,
                "status": "draft",
            }
        ],
    }


@mock_ai_app.post("/v1/insights/explain")
async def explain_insights(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "proposal_id": str(uuid.uuid4()),
        "contract_version": CONTRACT_VERSION_V1_0,
        "explanations": {
            "Mathematics": "গণিতে ধারণাগত অনুশীলন বাড়ানো হয়েছে যাতে পরীক্ষার আগে আত্মবিশ্বাস বৃদ্ধি পায়।",
            "General Science": "বিজ্ঞানের অধ্যায়গুলোতে সূত্র এবং ডায়াগ্রাম পর্যবেক্ষণে মনোযোগ দেওয়া হচ্ছে।",
        },
    }
