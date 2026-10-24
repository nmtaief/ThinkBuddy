"""Mock AI Planner Service (P06a).

Implements the contract endpoints defined in docs/07_AI_PLANNER_API.md §3:
- GET /healthz
- GET /v1/contract
- POST /v1/plans/propose

Can be used as a standalone FastAPI app or in tests via httpx.ASGITransport.
Supports test mode toggles to simulate failure scenarios:
- NORMAL: Valid AI proposal conforming to all rules and syllabus bounds.
- TIMEOUT: Sleeps 30s to test timeout handling and fallback.
- ERROR_500: Returns HTTP 500 to test retry and circuit breaker.
- BUDGET_OVERFLOW: Violates V02 (excessive minutes).
- BLACKOUT_VIOLATION: Violates V04 (tasks on blackout days).
- POST_EXAM_VIOLATION: Violates V05 (study after exam).
- INVALID_PAGES: Violates V06 (pages out of bounds).
- OUT_OF_ORDER_CHAPTER: Violates V07 (chapter backwards order).
- INVALID_CONTRACT: Violates V01 (unsupported contract version).
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, Response, status

app = FastAPI(title="Mock AI Planner Service", version="1.0.0")

# Test simulation mode controlled in unit/integration tests
TEST_MODE = "NORMAL"


def set_test_mode(mode: str) -> None:
    """Set the mock service behavior mode."""
    global TEST_MODE
    TEST_MODE = mode


def get_test_mode() -> str:
    """Get current mock service behavior mode."""
    return TEST_MODE


@app.get("/healthz", status_code=status.HTTP_200_OK)
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "mock-ai-planner"}


@app.get("/v1/contract", status_code=status.HTTP_200_OK)
async def contract_info() -> dict[str, Any]:
    return {
        "contract_version": "ai-planner/v1.0",
        "supported_versions": ["ai-planner/v1", "ai-planner/v1.0"],
        "model_info": {
            "model_id": "mock-gemini-2.5-flash",
            "provider": "google",
            "tier": "fast_adaptive",
        },
    }


@app.post("/v1/plans/propose", status_code=status.HTTP_200_OK)
async def propose_plan(
    request: Request,
    authorization: str | None = Header(None),
    x_idempotency_key: str | None = Header(None),
) -> dict[str, Any]:
    # Simulate auth check
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Bearer authorization header",
        )

    mode = get_test_mode()

    if mode == "TIMEOUT":
        await asyncio.sleep(30.0)
        return {}

    if mode == "ERROR_500":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Simulated internal AI service model error",
        )

    payload = await request.json()
    calendar = payload.get("calendar", [])
    syllabus = payload.get("syllabus", [])
    settings = payload.get("settings", {})

    if mode == "INVALID_CONTRACT":
        return {
            "contract_version": "ai-planner/v99.0",
            "days": [],
        }

    # Generate synthetic routine matching calendar and syllabus
    response_days: list[dict[str, Any]] = []

    # Flatten available chapters
    subject_chapters: dict[str, list[dict[str, Any]]] = {}
    for sub in syllabus:
        s_name = sub.get("subject", "")
        subject_chapters[s_name] = sorted(
            sub.get("chapters", []), key=lambda c: c.get("custom_order", 0)
        )

    for cal_day in calendar:
        d_str = cal_day.get("date")
        d_type = cal_day.get("day_type")
        avail_m = cal_day.get("available_minutes", 0)

        day_tasks: list[dict[str, Any]] = []

        if d_type in ("blackout", "rest") or avail_m == 0:
            if mode == "BLACKOUT_VIOLATION":
                # Intentionally schedule a task on blackout day to test V04
                day_tasks.append(
                    {
                        "subject": list(subject_chapters.keys())[0],
                        "type": "study",
                        "minutes": 30,
                        "chapter_id": subject_chapters[list(subject_chapters.keys())[0]][0]["chapter_id"],
                        "page_start": 1,
                        "page_end": 5,
                    }
                )
            response_days.append({"date": d_str, "tasks": day_tasks})
            continue

        if mode == "BUDGET_OVERFLOW":
            # Schedule 300 minutes on a 150m day
            for s_name, chs in subject_chapters.items():
                if chs:
                    day_tasks.append(
                        {
                            "subject": s_name,
                            "type": "study",
                            "minutes": 100,
                            "chapter_id": chs[0]["chapter_id"],
                            "page_start": chs[0]["printed_page_start"],
                            "page_end": chs[0]["printed_page_start"] + 3,
                        }
                    )
            response_days.append({"date": d_str, "tasks": day_tasks})
            continue

        if mode == "POST_EXAM_VIOLATION":
            # Schedule task for the subject after its exam date
            for exam in payload.get("exams", []):
                s_name = exam.get("subject")
                e_date = exam.get("exam_date")
                if d_str >= e_date and s_name in subject_chapters:
                    chs = subject_chapters[s_name]
                    if chs:
                        day_tasks.append(
                            {
                                "subject": s_name,
                                "type": "study",
                                "minutes": 30,
                                "chapter_id": chs[0]["chapter_id"],
                                "page_start": chs[0]["printed_page_start"],
                                "page_end": chs[0]["printed_page_start"] + 2,
                            }
                        )
            response_days.append({"date": d_str, "tasks": day_tasks})
            continue

        if mode == "INVALID_PAGES":
            s_name = list(subject_chapters.keys())[0]
            ch = subject_chapters[s_name][0]
            day_tasks.append(
                {
                    "subject": s_name,
                    "type": "study",
                    "minutes": 30,
                    "chapter_id": ch["chapter_id"],
                    "page_start": 9999,  # Invalid
                    "page_end": 10050,
                }
            )
            response_days.append({"date": d_str, "tasks": day_tasks})
            continue

        # Normal Generation Mode
        rem_budget = avail_m
        for s_name, chs in subject_chapters.items():
            if rem_budget < 25:
                break
            if not chs:
                continue

            ch = chs[0]
            slice_m = min(rem_budget, 45)
            p_st = ch["printed_page_start"]
            p_en = min(ch["printed_page_end"], p_st + 4)

            day_tasks.append(
                {
                    "subject": s_name,
                    "type": "study",
                    "minutes": slice_m,
                    "chapter_id": ch["chapter_id"],
                    "chapter_number": ch["number"],
                    "page_start": p_st,
                    "page_end": p_en,
                    "reason_code": "EXAM_APPROACHING",
                }
            )
            rem_budget -= slice_m

        response_days.append({"date": d_str, "tasks": day_tasks})

    return {
        "contract_version": "ai-planner/v1.0",
        "proposal_id": "prop-mock-ai-12345",
        "model_info": {
            "model_id": "mock-gemini-2.5-flash",
            "provider": "google",
        },
        "confidence": 0.95,
        "days": response_days,
        "rationale": {
            s: "AI balanced syllabus pacing with priority reinforcement and spaced practice."
            for s in subject_chapters
        },
        "warnings": [],
    }
