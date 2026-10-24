"""Tests for Milestone P06a: AI Planner Integration.

Verifies:
1. docs/07_AI_PLANNER_API.md versioned contract adherence.
2. PlanProvider interface: DeterministicProvider and AiPlannerProvider.
3. Pseudonymization: minimal, pseudonymous data in requests (Rule 15, no PII).
4. Untrusted AI output validation (rules V01 to V15):
   - Hard rule violations reject and fall back to deterministic plan.
   - Trivial repairs (minor rounding, blackout/post-exam task drops) succeed with warnings.
5. Circuit Breaker state machine (CLOSED -> OPEN -> HALF_OPEN -> CLOSED).
6. Timeout and HTTP error retries and deterministic fallback.
7. Feature flags and kill switch (AI_PLANNER_ENABLED, per-student adaptive_mode).
8. Provenance persistence (provider, model_version, contract_version, settings_version, generation_reason)
   and visibility in API responses.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from httpx import ASGITransport

from core.common.config import settings as app_settings
from core.planner.engine import (
    ChapterPlanInput,
    SubjectSetupInput,
    generate_student_plan,
)
from core.planner.mock_ai_service import app as mock_ai_app, set_test_mode
from core.planner.provider import (
    AiPlannerProvider,
    CircuitBreaker,
    CircuitBreakerState,
    DeterministicProvider,
    PlanProviderContext,
    get_plan_provider,
)
from core.planner.pseudonymizer import (
    build_pseudonymous_snapshot,
    generate_student_ref,
)
from core.planner.settings_resolver import (
    DayScheduleInfo,
    ResolvedPlannerSettings,
    resolve_calendar_days,
)
from core.planner.validator import AiProposalValidator


# Helper to build a standard test context
def build_test_context(
    student_id: uuid.UUID | None = None,
    adaptive_mode: str = "suggest",
    daily_minutes: int = 150,
) -> tuple[PlanProviderContext, list[SubjectSetupInput], ResolvedPlannerSettings]:
    stud_id = student_id or uuid.uuid4()
    today = date(2026, 10, 23)
    now_dt = datetime(2026, 10, 23, 16, 0, tzinfo=ZoneInfo("Asia/Dhaka"))
    exam_date = today + timedelta(days=20)

    chapters = [
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=1,
            title="Sets and Functions",
            book_title="General Mathematics",
            printed_page_start=1,
            printed_page_end=30,
            difficulty_factor=1.0,
            custom_order=1,
        ),
        ChapterPlanInput(
            id=uuid.uuid4(),
            number=2,
            title="Algebraic Expressions",
            book_title="General Mathematics",
            printed_page_start=31,
            printed_page_end=60,
            difficulty_factor=1.2,
            custom_order=2,
        ),
    ]

    setups = [
        SubjectSetupInput(
            subject="Mathematics",
            exam_name="Term Final Exam",
            exam_date=exam_date,
            chapters=chapters,
        )
    ]

    resolved_settings = ResolvedPlannerSettings(
        class_band="9-10",
        group="science",
        school_day_minutes=daily_minutes,
        holiday_minutes=210,
        study_window_start="16:30",
        study_window_end="22:00",
        weekly_off_days=["fri", "sat"],
        recurring_unavailable_blocks=[],
        blocked_observance_keys=[],
        custom_blackout_dates=[],
        subject_priorities={"Mathematics": "difficult"},
        adaptive_mode=adaptive_mode,
        rest_weekday=None,
        planner_parameters={"min_study_block_minutes": 20},
        settings_version=2,
    )

    calendar_days = resolve_calendar_days(
        start_date=today,
        end_date=exam_date,
        now=now_dt,
        resolved_settings=resolved_settings,
        published_holidays={},
        exam_dates={exam_date: ["Mathematics"]},
        completed_minutes_today=0,
    )

    ctx = PlanProviderContext(
        student_id=stud_id,
        today=today,
        now_dhaka=now_dt,
        daily_study_minutes=daily_minutes,
        setups=setups,
        available_days=["fri", "sat"],
        completed_tasks=None,
        resolved_settings=resolved_settings,
        day_calendar=calendar_days,
    )
    return ctx, setups, resolved_settings


# ============================================================================
# 1. DeterministicProvider Tests
# ============================================================================


@pytest.mark.asyncio
async def test_deterministic_provider_execution() -> None:
    """DeterministicProvider generates valid plan with standard provenance."""
    ctx, _, _ = build_test_context()
    provider = DeterministicProvider()
    result = await provider.generate_plan(ctx)

    assert result.provider == "deterministic"
    assert result.model_version == "v2-rules"
    assert result.contract_version == "p03-engine"
    assert result.settings_version == 2
    assert result.generation_reason == "deterministic_baseline"
    assert result.plan_out is not None
    assert len(result.plan_out.days) > 0


# ============================================================================
# 2. Pseudonymization Tests (Rule 15 - Log, don't leak; No PII)
# ============================================================================


def test_pseudonymization_snapshot_contains_zero_pii() -> None:
    """Request snapshot must be strictly pseudonymous and contain zero identifying information."""
    ctx, setups, settings = build_test_context()

    payload = build_pseudonymous_snapshot(
        student_id=ctx.student_id,
        today=ctx.today,
        now_dhaka=ctx.now_dhaka,
        resolved_settings=settings,
        day_calendar=ctx.day_calendar,
        setups=setups,
    )

    # 1. Contract envelope
    assert payload["contract_version"] == "ai-planner/v1.0"
    assert "student_ref" in payload
    assert payload["student_ref"].startswith("anon-")
    # Real UUID must not appear as plaintext
    assert str(ctx.student_id) != payload["student_ref"]

    # 2. Assert zero PII keys anywhere in snapshot
    raw_str = str(payload).lower()
    for forbidden in ["student_name", "parent_name", "email", "phone", "school_name", "institution", "chat", "device", "password"]:
        assert forbidden not in raw_str, f"Found forbidden PII keyword '{forbidden}' in snapshot"

    # 3. Academic context intact
    assert payload["profile"]["class_band"] == "9-10"
    assert payload["profile"]["group"] == "science"
    assert len(payload["syllabus"]) == 1
    assert payload["syllabus"][0]["subject"] == "Mathematics"
    assert len(payload["syllabus"][0]["chapters"]) == 2
    assert len(payload["calendar"]) == len(ctx.day_calendar)


# ============================================================================
# 3. Untrusted AI Proposal Validator Tests (Rules V01 - V15)
# ============================================================================


def test_validator_rejects_unsupported_contract_version() -> None:
    """V01: Unsupported contract version is rejected as hard violation."""
    ctx, setups, settings = build_test_context()
    validator = AiProposalValidator(
        setups=setups,
        day_calendar=ctx.day_calendar,
        resolved_settings=settings,
        today=ctx.today,
        daily_study_minutes=ctx.daily_study_minutes,
        student_id=ctx.student_id,
    )

    res = validator.validate({"contract_version": "unsupported/v99", "days": []})
    assert not res.is_valid
    assert res.error_code == "V01_CONTRACT_MISMATCH"


def test_validator_rejects_excessive_daily_budget_overflow() -> None:
    """V02: Scheduling tasks that grossly exceed daily budget is rejected."""
    ctx, setups, settings = build_test_context(daily_minutes=150)
    validator = AiProposalValidator(
        setups=setups,
        day_calendar=ctx.day_calendar,
        resolved_settings=settings,
        today=ctx.today,
        daily_study_minutes=150,
        student_id=ctx.student_id,
    )

    ch = setups[0].chapters[0]
    raw_proposal = {
        "contract_version": "ai-planner/v1.0",
        "days": [
            {
                "date": ctx.today.isoformat(),
                "tasks": [
                    {
                        "subject": "Mathematics",
                        "type": "study",
                        "minutes": 250,  # Exceeds 150m budget by 100m
                        "chapter_id": str(ch.id),
                        "page_start": 1,
                        "page_end": 10,
                    }
                ],
            }
        ],
    }

    res = validator.validate(raw_proposal)
    assert not res.is_valid
    assert res.error_code == "V02_EXCEEDED_DAILY_BUDGET"


def test_validator_trivially_repairs_minor_budget_rounding() -> None:
    """V02: Minor rounding overflow (<= 5m) is trivially trimmed."""
    ctx, setups, settings = build_test_context(daily_minutes=150)
    validator = AiProposalValidator(
        setups=setups,
        day_calendar=ctx.day_calendar,
        resolved_settings=settings,
        today=ctx.today,
        daily_study_minutes=150,
        student_id=ctx.student_id,
    )

    ch = setups[0].chapters[0]
    cal_budget = ctx.day_calendar[0].budget_minutes
    raw_proposal = {
        "contract_version": "ai-planner/v1.0",
        "days": [
            {
                "date": ctx.today.isoformat(),
                "tasks": [
                    {
                        "subject": "Mathematics",
                        "type": "study",
                        "minutes": cal_budget + 3,  # 3m overflow -> should be trimmed to cal_budget
                        "chapter_id": str(ch.id),
                        "page_start": 1,
                        "page_end": 10,
                    }
                ],
            }
        ],
    }

    res = validator.validate(raw_proposal)
    assert res.is_valid
    assert res.repaired
    assert res.repaired_plan_out is not None
    assert res.repaired_plan_out.days[0].planned_minutes == cal_budget


def test_validator_trivially_repairs_blackout_day_violation() -> None:
    """V04: Tasks scheduled on a blackout day are dropped with a warning."""
    ctx, setups, settings = build_test_context()
    # Mark first day as blackout
    ctx.day_calendar[0] = DayScheduleInfo(
        date=ctx.today,
        day_type="blackout",
        budget_minutes=0,
        zero_reason="calendar blackout",
    )

    validator = AiProposalValidator(
        setups=setups,
        day_calendar=ctx.day_calendar,
        resolved_settings=settings,
        today=ctx.today,
        daily_study_minutes=150,
        student_id=ctx.student_id,
    )

    ch = setups[0].chapters[0]
    raw_proposal = {
        "contract_version": "ai-planner/v1.0",
        "days": [
            {
                "date": ctx.today.isoformat(),
                "tasks": [
                    {
                        "subject": "Mathematics",
                        "type": "study",
                        "minutes": 30,
                        "chapter_id": str(ch.id),
                        "page_start": 1,
                        "page_end": 5,
                    }
                ],
            }
        ],
    }

    res = validator.validate(raw_proposal)
    assert res.is_valid
    assert res.repaired
    assert any("AI_DROPPED_TASKS_ON_ZERO_DAY" in w for w in res.warnings)
    # The blackout day must have 0 planned minutes and 0 tasks
    assert res.repaired_plan_out.days[0].planned_minutes == 0
    assert len(res.repaired_plan_out.days[0].tasks) == 0


def test_validator_rejects_page_bounds_out_of_range() -> None:
    """V06: Page numbers outside the chapter's printed pages are rejected."""
    ctx, setups, settings = build_test_context()
    validator = AiProposalValidator(
        setups=setups,
        day_calendar=ctx.day_calendar,
        resolved_settings=settings,
        today=ctx.today,
        daily_study_minutes=150,
        student_id=ctx.student_id,
    )

    ch = setups[0].chapters[0]  # pages 1..30
    raw_proposal = {
        "contract_version": "ai-planner/v1.0",
        "days": [
            {
                "date": ctx.today.isoformat(),
                "tasks": [
                    {
                        "subject": "Mathematics",
                        "type": "study",
                        "minutes": 30,
                        "chapter_id": str(ch.id),
                        "page_start": 25,
                        "page_end": 45,  # Exceeds 30
                    }
                ],
            }
        ],
    }

    res = validator.validate(raw_proposal)
    assert not res.is_valid
    assert res.error_code == "V06_INVALID_PAGE_BOUNDS"


def test_validator_rejects_backwards_chapter_order() -> None:
    """V07: Scheduling Chapter 2 before Chapter 1 in study is rejected."""
    ctx, setups, settings = build_test_context()
    validator = AiProposalValidator(
        setups=setups,
        day_calendar=ctx.day_calendar,
        resolved_settings=settings,
        today=ctx.today,
        daily_study_minutes=150,
        student_id=ctx.student_id,
    )

    ch1 = setups[0].chapters[0]  # order 1
    ch2 = setups[0].chapters[1]  # order 2
    d1 = ctx.today
    d2 = ctx.today + timedelta(days=1)

    raw_proposal = {
        "contract_version": "ai-planner/v1.0",
        "days": [
            {
                "date": d1.isoformat(),
                "tasks": [
                    {
                        "subject": "Mathematics",
                        "type": "study",
                        "minutes": 30,
                        "chapter_id": str(ch2.id),
                        "page_start": 31,
                        "page_end": 40,
                    }
                ],
            },
            {
                "date": d2.isoformat(),
                "tasks": [
                    {
                        "subject": "Mathematics",
                        "type": "study",
                        "minutes": 30,
                        "chapter_id": str(ch1.id),  # Chapter 1 scheduled after Chapter 2
                        "page_start": 1,
                        "page_end": 10,
                    }
                ],
            },
        ],
    }

    res = validator.validate(raw_proposal)
    assert not res.is_valid
    assert res.error_code == "V07_OUT_OF_ORDER_CHAPTER"


# ============================================================================
# 4. AiPlannerProvider with Mock Service & Fallback Tests
# ============================================================================


@pytest.mark.asyncio
async def test_ai_planner_provider_normal_success() -> None:
    """AiPlannerProvider successfully communicates with mock AI service and validates output."""
    set_test_mode("NORMAL")
    ctx, _, _ = build_test_context()

    transport = ASGITransport(app=mock_ai_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock-ai") as client:
        provider = AiPlannerProvider(
            client=client,
            service_url="http://mock-ai",
            api_key="valid-key",
        )
        result = await provider.generate_plan(ctx)

    assert result.provider == "ai"
    assert result.model_version == "mock-gemini-2.5-flash"
    assert result.contract_version == "ai-planner/v1.0"
    assert result.generation_reason in ("ai_adaptive_routine", "ai_adaptive_routine_repaired")
    assert result.plan_out is not None
    assert len(result.plan_out.days) > 0


@pytest.mark.asyncio
async def test_ai_planner_provider_fallback_on_500_error() -> None:
    """AiPlannerProvider gracefully falls back to deterministic engine on HTTP 500 error."""
    set_test_mode("ERROR_500")
    ctx, _, _ = build_test_context()

    transport = ASGITransport(app=mock_ai_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock-ai") as client:
        provider = AiPlannerProvider(
            client=client,
            service_url="http://mock-ai",
            api_key="valid-key",
            max_retries=1,
        )
        result = await provider.generate_plan(ctx)

    assert result.provider == "ai_fallback_deterministic"
    assert "fallback:HTTP_500" in result.generation_reason
    assert result.plan_out is not None


@pytest.mark.asyncio
async def test_ai_planner_provider_fallback_on_untrusted_hard_violation() -> None:
    """AiPlannerProvider rejects invalid AI output and falls back to deterministic engine."""
    set_test_mode("INVALID_PAGES")
    ctx, _, _ = build_test_context()

    transport = ASGITransport(app=mock_ai_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock-ai") as client:
        provider = AiPlannerProvider(
            client=client,
            service_url="http://mock-ai",
            api_key="valid-key",
        )
        result = await provider.generate_plan(ctx)

    assert result.provider == "ai_fallback_deterministic"
    assert result.generation_reason == "fallback:V06_INVALID_PAGE_BOUNDS"
    assert result.plan_out is not None


# ============================================================================
# 5. Circuit Breaker State Machine Tests
# ============================================================================


def test_circuit_breaker_transitions() -> None:
    """Circuit breaker trips to OPEN after threshold and enters HALF_OPEN after timeout."""
    cb = CircuitBreaker(failure_threshold=3, reset_timeout_seconds=0.1)
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.can_execute()

    # 1. First failure
    cb.record_failure()
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.can_execute()

    # 2. Second failure
    cb.record_failure()
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.can_execute()

    # 3. Third failure -> Trips OPEN
    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN
    assert not cb.can_execute()

    # 4. Fast-fail during cooldown
    assert not cb.can_execute()

    # 5. After timeout -> HALF_OPEN probe allowed
    import time
    time.sleep(0.12)
    assert cb.can_execute()
    assert cb.state == CircuitBreakerState.HALF_OPEN

    # 6. Success closes breaker
    cb.record_success()
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.consecutive_failures == 0


@pytest.mark.asyncio
async def test_circuit_breaker_fast_fails_when_open() -> None:
    """When circuit breaker is OPEN, provider immediately falls back without HTTP calls."""
    cb = CircuitBreaker(failure_threshold=1, reset_timeout_seconds=60.0)
    cb.record_failure()  # Trips breaker to OPEN
    assert cb.state == CircuitBreakerState.OPEN

    ctx, _, _ = build_test_context()
    provider = AiPlannerProvider(circuit_breaker=cb)
    result = await provider.generate_plan(ctx)

    assert result.provider == "ai_fallback_deterministic"
    assert result.generation_reason == "fallback:circuit_breaker_open"


# ============================================================================
# 6. Feature Flag & Per-Student Mode Switching
# ============================================================================


def test_provider_factory_respects_global_kill_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    """When AI_PLANNER_ENABLED is False, provider is always DeterministicProvider."""
    monkeypatch.setattr(app_settings, "AI_PLANNER_ENABLED", False)
    ctx, _, settings = build_test_context(adaptive_mode="suggest")

    provider = get_plan_provider(settings)
    assert isinstance(provider, DeterministicProvider)


def test_provider_factory_respects_per_student_manual_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """When student is in manual mode, provider is always DeterministicProvider."""
    monkeypatch.setattr(app_settings, "AI_PLANNER_ENABLED", True)
    ctx, _, settings = build_test_context(adaptive_mode="manual")

    provider = get_plan_provider(settings)
    assert isinstance(provider, DeterministicProvider)


def test_provider_factory_activates_ai_planner(monkeypatch: pytest.MonkeyPatch) -> None:
    """When AI_PLANNER_ENABLED is True and mode is suggest, provider is AiPlannerProvider."""
    monkeypatch.setattr(app_settings, "AI_PLANNER_ENABLED", True)
    ctx, _, settings = build_test_context(adaptive_mode="suggest")

    provider = get_plan_provider(settings)
    assert isinstance(provider, AiPlannerProvider)


# ============================================================================
# 7. Live Database Provenance and API Responses Test
# ============================================================================


@pytest.mark.asyncio
async def test_live_db_provenance_and_api_responses(
    gateway_client: httpx.AsyncClient,
) -> None:
    """Verify that plans generated in live PostgreSQL store provenance and expose them via API."""
    from sqlalchemy import select
    from core.common.database import AsyncSessionLocal
    from core.planner.models import Plan

    client_headers = {
        "X-Client-Platform": "android",
        "X-Client-Form-Factor": "phone",
        "X-App-Version": "1.0.0",
        "X-Device-Id": "device-test-p06a-001",
        "Accept-Language": "bn",
    }

    # 1. Setup Parent & Student
    p_phone = f"+880171{uuid.uuid4().hex[:6]}"
    res_p = await gateway_client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{p_phone}", "role": "parent"},
        headers=client_headers,
    )
    assert res_p.status_code == 200
    p_token = res_p.json()["access_token"]
    p_headers = {**client_headers, "Authorization": f"Bearer {p_token}"}

    res_fam = await gateway_client.post(
        "/v1/families", json={"name": "P06a Family"}, headers=p_headers
    )
    assert res_fam.status_code == 201
    fam_id = res_fam.json()["id"]

    res_child = await gateway_client.post(
        f"/v1/families/{fam_id}/students",
        json={
            "display_name": "P06a Student",
            "class_level": 7,
            "medium": "bn",
            "daily_minutes": 90,
        },
        headers=p_headers,
    )
    assert res_child.status_code == 201
    link_code = res_child.json()["link_code"]

    # Student links account with link_code
    s_phone = f"+880181{uuid.uuid4().hex[:6]}"
    res_s = await gateway_client.post(
        "/v1/auth/exchange",
        json={
            "provider_token": f"fake:phone:{s_phone}",
            "role": "student",
            "link_code": link_code,
        },
        headers=client_headers,
    )
    assert res_s.status_code == 200
    s_id = res_s.json()["user"]["id"]

    # 2. Get curriculum book & chapters
    res_books = await gateway_client.get("/v1/books?class_level=7&subject=math", headers=p_headers)
    assert res_books.status_code == 200
    book_id = res_books.json()["items"][0]["id"]

    res_ch = await gateway_client.get(f"/v1/books/{book_id}/chapters", headers=p_headers)
    assert res_ch.status_code == 200
    chapters = res_ch.json()["items"]

    # 3. Parent configures study setup
    exam_date = (date.today() + timedelta(days=25)).isoformat()
    setup_payload = {
        "exam_name": "Finals",
        "exam_date": exam_date,
        "daily_study_minutes": 90,
        "available_days": ["sat", "sun", "mon", "tue", "wed", "thu", "fri"],
        "syllabus": [
            {"chapter_id": chapters[0]["id"], "included": True, "custom_order": 1, "weight": 1.0},
        ],
    }

    res_setup = await gateway_client.put(
        f"/v1/students/{s_id}/study-setups/math",
        json=setup_payload,
        headers=p_headers,
    )
    assert res_setup.status_code == 200

    # 4. Check DB row has provenance columns populated
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Plan)
            .where(Plan.student_id == uuid.UUID(s_id), Plan.status == "active")
            .order_by(Plan.version.desc())
        )
        res_db = await session.execute(stmt)
        plan_row = res_db.scalars().first()
        assert plan_row is not None
        assert plan_row.provider in ("deterministic", "ai", "ai_fallback_deterministic")
        assert plan_row.model_version is not None
        assert plan_row.contract_version is not None
        assert plan_row.settings_version is not None
        assert plan_row.generation_reason is not None

    # 5. Check GET /v1/students/{id}/plan API response
    res_plan = await gateway_client.get(f"/v1/students/{s_id}/plan", headers=p_headers)
    assert res_plan.status_code == 200
    plan_data = res_plan.json()
    assert plan_data["provider"] == plan_row.provider
    assert plan_data["model_version"] == plan_row.model_version
    assert plan_data["contract_version"] == plan_row.contract_version
    assert plan_data["generation_reason"] == plan_row.generation_reason
    assert "rationale" in plan_data

    # 6. Check GET /v1/students/{id}/today API response
    res_today = await gateway_client.get(f"/v1/students/{s_id}/today", headers=p_headers)
    assert res_today.status_code == 200
    today_data = res_today.json()
    assert today_data["provider"] == plan_row.provider
    assert today_data["generation_reason"] == plan_row.generation_reason
    assert today_data["reason_for_parents"] is not None
    assert len(today_data["reason_for_parents"]) > 0
