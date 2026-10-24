"""Plan Provider Abstraction Layer & AI Planner Integration (P06a).

Per docs/07_AI_PLANNER_API.md §1, §2, §8, §10:
- Provider interface: `PlanProvider` ABC with `DeterministicProvider` and `AiPlannerProvider`.
- `DeterministicProvider`: Pure-Python rule-based baseline (P03).
- `AiPlannerProvider`: HTTP client with auth, timeouts, retries, circuit breaker, idempotency key.
- Untrusted AI output validation via `AiProposalValidator`: enforces hard rules, repairs trivially,
  and falls back to `DeterministicProvider` with the reason logged.
- Provable provenance: provider, model version, contract version, settings version, generation reason.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

import httpx

from core.common.config import settings as app_settings
from core.planner.engine import (
    MultiSubjectPlanOutput,
    generate_student_plan,
)
from core.planner.pseudonymizer import build_pseudonymous_snapshot
from core.planner.validator import AiProposalValidator

if TYPE_CHECKING:
    from core.planner.engine import ChapterPlanInput, SubjectSetupInput
    from core.planner.models import Task
    from core.planner.settings_resolver import DayScheduleInfo, ResolvedPlannerSettings

logger = logging.getLogger("thinkbuddy.planner.provider")


class CircuitBreakerState:
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """In-memory Circuit Breaker to prevent cascading external AI service failures."""

    def __init__(
        self,
        failure_threshold: int = 3,
        reset_timeout_seconds: float = 30.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds
        self.state = CircuitBreakerState.CLOSED
        self.consecutive_failures = 0
        self.last_failure_time: float = 0.0

    def can_execute(self) -> bool:
        """Return True if requests are allowed to proceed through the breaker."""
        now = time.monotonic()
        if self.state == CircuitBreakerState.OPEN:
            if now - self.last_failure_time >= self.reset_timeout_seconds:
                logger.info("Circuit breaker entering HALF_OPEN state; allowing probe request.")
                self.state = CircuitBreakerState.HALF_OPEN
                return True
            return False
        return True

    def record_success(self) -> None:
        """Reset consecutive failures on successful operation."""
        self.consecutive_failures = 0
        if self.state != CircuitBreakerState.CLOSED:
            logger.info("Circuit breaker closed after successful operation.")
            self.state = CircuitBreakerState.CLOSED

    def record_failure(self) -> None:
        """Increment consecutive failures and trip circuit if threshold reached."""
        self.consecutive_failures += 1
        self.last_failure_time = time.monotonic()
        if self.consecutive_failures >= self.failure_threshold:
            if self.state != CircuitBreakerState.OPEN:
                logger.warning(
                    "Circuit breaker tripped to OPEN after %d consecutive failures.",
                    self.consecutive_failures,
                )
            self.state = CircuitBreakerState.OPEN


# Shared circuit breaker instance across calls
_global_ai_circuit_breaker = CircuitBreaker(
    failure_threshold=app_settings.AI_PLANNER_CIRCUIT_BREAKER_FAILURES,
    reset_timeout_seconds=app_settings.AI_PLANNER_CIRCUIT_BREAKER_RESET_SECONDS,
)


@dataclass
class PlanProviderContext:
    """Input context for plan generation."""

    student_id: uuid.UUID | str
    today: date
    now_dhaka: datetime
    daily_study_minutes: int
    setups: list[SubjectSetupInput]
    available_days: list[str] | list[int] | set[int]
    completed_tasks: list[Task] | None
    resolved_settings: ResolvedPlannerSettings
    day_calendar: list[DayScheduleInfo]
    idempotency_key: uuid.UUID | str = field(default_factory=uuid.uuid4)
    request_id: uuid.UUID | str = field(default_factory=uuid.uuid4)


@dataclass
class PlanProviderResult:
    """Result of plan generation with complete provenance metadata."""

    plan_out: MultiSubjectPlanOutput
    provider: str  # "deterministic" | "ai" | "ai_fallback_deterministic"
    model_version: str
    contract_version: str
    settings_version: int
    generation_reason: str
    rationale: dict[str, str] = field(default_factory=dict)
    shadow_comparison: dict[str, Any] | None = None


class PlanProvider(ABC):
    """Abstract interface for study routine generation engines."""

    @abstractmethod
    async def generate_plan(self, ctx: PlanProviderContext) -> PlanProviderResult:
        """Generate a complete multi-subject study plan for a student."""
        pass


class DeterministicProvider(PlanProvider):
    """Pure-Python deterministic adaptive study planner engine (P03)."""

    async def generate_plan(self, ctx: PlanProviderContext) -> PlanProviderResult:
        plan_out = generate_student_plan(
            student_id=ctx.student_id,
            today=ctx.today,
            daily_study_minutes=ctx.daily_study_minutes,
            setups=ctx.setups,
            available_days=ctx.available_days,
            completed_tasks=ctx.completed_tasks,
            resolved_settings=ctx.resolved_settings,
            day_calendar=ctx.day_calendar,
        )

        return PlanProviderResult(
            plan_out=plan_out,
            provider="deterministic",
            model_version="v2-rules",
            contract_version="p03-engine",
            settings_version=ctx.resolved_settings.settings_version,
            generation_reason="deterministic_baseline",
            rationale={
                s.subject: "Deterministic priority pacing and spaced revision rules applied."
                for s in ctx.setups
            },
        )


class AiPlannerProvider(PlanProvider):
    """External AI Planner service client with auth, timeouts, retries, and fallback."""

    def __init__(
        self,
        fallback_provider: PlanProvider | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        client: httpx.AsyncClient | None = None,
        service_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.fallback_provider = fallback_provider or DeterministicProvider()
        self.circuit_breaker = circuit_breaker or _global_ai_circuit_breaker
        self._external_client = client
        self.service_url = service_url or app_settings.AI_PLANNER_URL
        self.api_key = api_key or app_settings.AI_PLANNER_API_KEY
        self.timeout_seconds = timeout_seconds or app_settings.AI_PLANNER_TIMEOUT_SECONDS
        self.max_retries = max_retries or app_settings.AI_PLANNER_MAX_RETRIES

    async def generate_plan(self, ctx: PlanProviderContext) -> PlanProviderResult:
        # 1. Circuit breaker check
        if not self.circuit_breaker.can_execute():
            logger.warning(
                "Circuit breaker is OPEN. Falling back to deterministic planner for student %s.",
                ctx.student_id,
            )
            fallback_res = await self.fallback_provider.generate_plan(ctx)
            fallback_res.provider = "ai_fallback_deterministic"
            fallback_res.generation_reason = "fallback:circuit_breaker_open"
            return fallback_res

        # 2. Build minimal pseudonymous request payload (no PII)
        payload = build_pseudonymous_snapshot(
            student_id=ctx.student_id,
            today=ctx.today,
            now_dhaka=ctx.now_dhaka,
            resolved_settings=ctx.resolved_settings,
            day_calendar=ctx.day_calendar,
            setups=ctx.setups,
            completed_tasks=ctx.completed_tasks,
            idempotency_key=ctx.idempotency_key,
            request_id=ctx.request_id,
            mode=ctx.resolved_settings.adaptive_mode,
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Idempotency-Key": str(ctx.idempotency_key),
            "X-Request-Id": str(ctx.request_id),
            "Content-Type": "application/json",
        }

        # 3. HTTP call with retries and exponential backoff
        endpoint = f"{self.service_url.rstrip('/')}/v1/plans/propose"
        response_json: dict[str, Any] | None = None
        last_error_code: str = "UNKNOWN_ERROR"

        for attempt in range(self.max_retries + 1):
            try:
                if self._external_client:
                    resp = await self._external_client.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                        timeout=self.timeout_seconds,
                    )
                else:
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            endpoint,
                            json=payload,
                            headers=headers,
                            timeout=self.timeout_seconds,
                        )

                if resp.status_code == 200:
                    response_json = resp.json()
                    break
                elif resp.status_code >= 500:
                    last_error_code = f"HTTP_{resp.status_code}"
                    logger.warning(
                        "AI Planner HTTP %d (attempt %d/%d)",
                        resp.status_code,
                        attempt + 1,
                        self.max_retries + 1,
                    )
                else:
                    last_error_code = f"HTTP_{resp.status_code}"
                    logger.error(
                        "AI Planner HTTP %d client error. Rejecting without retry.",
                        resp.status_code,
                    )
                    break
            except httpx.TimeoutException:
                last_error_code = "TIMEOUT"
                logger.warning(
                    "AI Planner timeout after %ss (attempt %d/%d)",
                    self.timeout_seconds,
                    attempt + 1,
                    self.max_retries + 1,
                )
            except Exception as exc:
                last_error_code = "NETWORK_ERROR"
                logger.warning(
                    "AI Planner network error: %s (attempt %d/%d)",
                    exc,
                    attempt + 1,
                    self.max_retries + 1,
                )

            if attempt < self.max_retries:
                await asyncio.sleep(0.2 * (2**attempt))

        if response_json is None:
            self.circuit_breaker.record_failure()
            logger.info(
                "AI Planner call failed with %s. Falling back to deterministic provider for student %s.",
                last_error_code,
                ctx.student_id,
            )
            fallback_res = await self.fallback_provider.generate_plan(ctx)
            fallback_res.provider = "ai_fallback_deterministic"
            fallback_res.generation_reason = f"fallback:{last_error_code}"
            return fallback_res

        # 4. Untrusted AI Output Validation
        validator = AiProposalValidator(
            setups=ctx.setups,
            day_calendar=ctx.day_calendar,
            resolved_settings=ctx.resolved_settings,
            today=ctx.today,
            daily_study_minutes=ctx.daily_study_minutes,
            student_id=ctx.student_id,
        )
        val_res = validator.validate(response_json)

        if not val_res.is_valid:
            self.circuit_breaker.record_failure()
            logger.warning(
                "AI proposal rejected by validator (%s: %s). Falling back to deterministic planner.",
                val_res.error_code,
                val_res.error_message,
            )
            fallback_res = await self.fallback_provider.generate_plan(ctx)
            fallback_res.provider = "ai_fallback_deterministic"
            fallback_res.generation_reason = f"fallback:{val_res.error_code}"
            return fallback_res

        # 5. Success
        self.circuit_breaker.record_success()
        gen_reason = (
            "ai_adaptive_routine_repaired" if val_res.repaired else "ai_adaptive_routine"
        )
        return PlanProviderResult(
            plan_out=val_res.repaired_plan_out,  # type: ignore[arg-type]
            provider="ai",
            model_version=val_res.model_version,
            contract_version=val_res.contract_version,
            settings_version=ctx.resolved_settings.settings_version,
            generation_reason=gen_reason,
            rationale=val_res.rationale,
        )


def get_plan_provider(
    resolved_settings: ResolvedPlannerSettings,
    client: httpx.AsyncClient | None = None,
) -> PlanProvider:
    """Return appropriate PlanProvider taking into account kill switches and per-student mode."""
    # Global Kill Switch
    if not app_settings.AI_PLANNER_ENABLED:
        return DeterministicProvider()

    # Per-student override: manual mode forces deterministic planner
    if resolved_settings.adaptive_mode == "manual":
        return DeterministicProvider()

    return AiPlannerProvider(client=client)
