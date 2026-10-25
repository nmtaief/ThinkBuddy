"""Plan Provider Abstraction Layer & AI Planner Integration (P06a).

Per thinkbuddy-docs/docs/07_AI_PLANNER_API.md §1, §2, §8, §10, §11:
- Provider interface: `PlanProvider` ABC with `DeterministicProvider` and `AiPlannerProvider`.
- `DeterministicProvider`: Pure-Python rule-based baseline (P03).
- `AiPlannerProvider`: HTTP client with short-lived signed service token auth, timeouts,
  retries, Redis-backed circuit breaker, and idempotency key.
- Untrusted AI output validation via `AiProposalValidator`: enforces hard rules, repairs trivially,
  and falls back to `DeterministicProvider` with the reason logged.
- Provable provenance: provider, model version, contract version, settings version, generation reason.
- Stubs for quizzes, revision, question drafts, and parent explanations.
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
from core.common.redis import get_redis_client
from core.contracts.ai_planner import (
    CONTRACT_VERSION_V1_0,
    InsightExplainRequest,
    InsightExplainResponse,
    QuestionDraftRequest,
    QuestionDraftResponse,
    QuizProposeRequest,
    QuizProposeResponse,
    RevisionProposeRequest,
    RevisionProposeResponse,
)
from core.planner.auth import create_ai_service_token
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


class _AsyncSyncAction:
    """Helper enabling CircuitBreaker methods to be used seamlessly in both sync tests and async code."""

    def __init__(self, value: Any, async_fn: Any = None) -> None:
        self.value = value
        self._async_fn = async_fn

    def __bool__(self) -> bool:
        return bool(self.value)

    def __eq__(self, other: Any) -> bool:
        return self.value == other

    def __await__(self):
        async def _runner():
            if self._async_fn:
                try:
                    async_val = await self._async_fn()
                    return async_val if async_val is not None else self.value
                except Exception:
                    return self.value
            return self.value
        return _runner().__await__()


class CircuitBreaker:
    """Circuit breaker backed by Redis with local in-memory fallback for process isolation."""

    def __init__(
        self,
        failure_threshold: int = 3,
        reset_timeout_seconds: float = 30.0,
        key_prefix: str = "thinkbuddy:cb:ai_planner",
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds
        self.key_prefix = key_prefix
        # In-memory fallback
        self._mem_state = CircuitBreakerState.CLOSED
        self._mem_failures = 0
        self._mem_last_failure: float = 0.0

    @property
    def state(self) -> str:
        return self._mem_state

    @property
    def consecutive_failures(self) -> int:
        return self._mem_failures

    def can_execute(self) -> _AsyncSyncAction:
        """Return True if requests are allowed to proceed through the breaker."""
        now = time.time()
        if self._mem_state == CircuitBreakerState.OPEN:
            if now - self._mem_last_failure >= self.reset_timeout_seconds:
                self._mem_state = CircuitBreakerState.HALF_OPEN
                sync_result = True
            else:
                sync_result = False
        else:
            sync_result = True

        async def _redis_check():
            if not sync_result:
                return False
            try:
                redis = get_redis_client()
                state_raw = await redis.get(f"{self.key_prefix}:state")
                state = state_raw if state_raw else self._mem_state
                if state == CircuitBreakerState.OPEN:
                    lf_raw = await redis.get(f"{self.key_prefix}:last_failure")
                    last_failure = float(lf_raw) if lf_raw else self._mem_last_failure
                    if now - last_failure >= self.reset_timeout_seconds:
                        logger.info("Circuit breaker entering HALF_OPEN probe state.")
                        await redis.set(f"{self.key_prefix}:state", CircuitBreakerState.HALF_OPEN)
                        self._mem_state = CircuitBreakerState.HALF_OPEN
                        return True
                    self._mem_state = CircuitBreakerState.OPEN
                    return False
                self._mem_state = state
                return True
            except Exception:
                return sync_result

        return _AsyncSyncAction(sync_result, _redis_check)

    def can_execute_sync(self) -> bool:
        """Synchronous check for unit test harnesses without an async loop."""
        return bool(self.can_execute())

    def record_success(self) -> _AsyncSyncAction:
        """Reset consecutive failures on successful operation."""
        self._mem_failures = 0
        self._mem_state = CircuitBreakerState.CLOSED

        async def _redis_record_success():
            try:
                redis = get_redis_client()
                await redis.set(f"{self.key_prefix}:state", CircuitBreakerState.CLOSED)
                await redis.delete(f"{self.key_prefix}:failures")
            except Exception:
                pass

        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(_redis_record_success())
        except RuntimeError:
            pass

        return _AsyncSyncAction(None, _redis_record_success)

    def record_failure(self) -> _AsyncSyncAction:
        """Increment consecutive failures and trip circuit if threshold reached."""
        now = time.time()
        self._mem_failures += 1
        self._mem_last_failure = now
        if self._mem_failures >= self.failure_threshold:
            self._mem_state = CircuitBreakerState.OPEN

        async def _redis_record_failure():
            try:
                redis = get_redis_client()
                fails = await redis.incr(f"{self.key_prefix}:failures")
                await redis.set(f"{self.key_prefix}:last_failure", str(now))
                if fails >= self.failure_threshold:
                    logger.warning("Circuit breaker tripped to OPEN in Redis (%d failures).", fails)
                    await redis.set(f"{self.key_prefix}:state", CircuitBreakerState.OPEN)
            except Exception:
                pass

        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(_redis_record_failure())
        except RuntimeError:
            pass

        return _AsyncSyncAction(None, _redis_record_failure)

    def reset(self) -> _AsyncSyncAction:
        """Force reset circuit breaker to CLOSED state."""
        self._mem_failures = 0
        self._mem_state = CircuitBreakerState.CLOSED

        async def _redis_reset():
            try:
                redis = get_redis_client()
                await redis.set(f"{self.key_prefix}:state", CircuitBreakerState.CLOSED)
                await redis.delete(f"{self.key_prefix}:failures")
                await redis.delete(f"{self.key_prefix}:last_failure")
            except Exception:
                pass

        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(_redis_reset())
        except RuntimeError:
            pass

        return _AsyncSyncAction(None, _redis_reset)


# Global circuit breaker instance
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
    pinned_tasks: list[dict[str, Any]] | None = None
    mastery_records: list[dict[str, Any]] | None = None
    learning_signals: dict[str, Any] | None = None
    revision_items: list[dict[str, Any]] | None = None


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
    priority_suggestions: list[dict[str, Any]] = field(default_factory=list)
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
        secret_key: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.fallback_provider = fallback_provider or DeterministicProvider()
        self.circuit_breaker = circuit_breaker or _global_ai_circuit_breaker
        self._external_client = client
        # Service URL strictly taken from configuration unless explicitly passed in test harnesses
        self.service_url = service_url or app_settings.AI_PLANNER_URL
        self.secret_key = secret_key or api_key or app_settings.AI_PLANNER_SECRET_KEY
        self.api_key = api_key or self.secret_key
        self.timeout_seconds = timeout_seconds or app_settings.AI_PLANNER_TIMEOUT_SECONDS
        self.max_retries = max_retries or app_settings.AI_PLANNER_MAX_RETRIES

    def _get_service_headers(self, idempotency_key: str, request_id: str) -> dict[str, str]:
        """Generate short-lived signed service token headers for service-to-service communication."""
        token = create_ai_service_token(secret_key=self.secret_key, ttl_seconds=60)
        return {
            "Authorization": f"Bearer {token}",
            "X-ThinkBuddy-Contract-Version": CONTRACT_VERSION_V1_0,
            "X-Idempotency-Key": idempotency_key,
            "X-Request-Id": request_id,
            "Content-Type": "application/json",
        }

    async def generate_plan(self, ctx: PlanProviderContext) -> PlanProviderResult:
        # 1. Circuit breaker check
        can_run = await self.circuit_breaker.can_execute()
        if not can_run:
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
            mastery_records=ctx.mastery_records,
            learning_signals=ctx.learning_signals,
            revision_items=ctx.revision_items,
        )

        headers = self._get_service_headers(str(ctx.idempotency_key), str(ctx.request_id))

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

                if resp.status_code >= 500:
                    last_error_code = f"HTTP_{resp.status_code}"
                    logger.warning(
                        "AI Planner returned server error %d (attempt %d/%d).",
                        resp.status_code,
                        attempt + 1,
                        self.max_retries + 1,
                    )
                else:
                    last_error_code = f"HTTP_{resp.status_code}"
                    logger.warning("AI Planner returned client error %d. Not retrying.", resp.status_code)
                    break

            except (httpx.TimeoutException, httpx.RequestError) as exc:
                last_error_code = type(exc).__name__
                logger.warning(
                    "AI Planner connection error: %s (attempt %d/%d).",
                    exc,
                    attempt + 1,
                    self.max_retries + 1,
                )

            if attempt < self.max_retries:
                await asyncio.sleep(0.05 * (2**attempt))

        if response_json is None:
            await self.circuit_breaker.record_failure()
            logger.warning(
                "All %d AI Planner attempts failed (%s). Falling back to deterministic planner.",
                self.max_retries + 1,
                last_error_code,
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
            pinned_tasks=ctx.pinned_tasks,
        )
        val_res = validator.validate(response_json)

        if not val_res.is_valid:
            await self.circuit_breaker.record_failure()
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
        await self.circuit_breaker.record_success()
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
            priority_suggestions=val_res.sanitized_priority_suggestions,
        )

    # -----------------------------------------------------------------------
    # Helper & Stub Methods for Additional AI Planner Endpoints (P06a)
    # -----------------------------------------------------------------------

    async def _post_with_retries(
        self,
        endpoint: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        """Execute POST call with circuit breaker checks, timeouts, and retries."""
        can_run = await self.circuit_breaker.can_execute()
        if not can_run:
            raise RuntimeError("CIRCUIT_BREAKER_OPEN: Cannot execute request while circuit breaker is OPEN")

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                if self._external_client:
                    resp = await self._external_client.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                        timeout=timeout_seconds,
                    )
                else:
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            endpoint,
                            json=payload,
                            headers=headers,
                            timeout=timeout_seconds,
                        )

                if resp.status_code == 200:
                    await self.circuit_breaker.record_success()
                    return resp.json()

                if resp.status_code >= 500:
                    last_exc = httpx.HTTPStatusError(
                        f"Server error {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                else:
                    # Client errors (4xx) are fatal and should not be retried
                    await self.circuit_breaker.record_failure()
                    resp.raise_for_status()

            except (httpx.TimeoutException, httpx.RequestError) as exc:
                last_exc = exc

            if attempt < self.max_retries:
                await asyncio.sleep(0.05 * (2**attempt))

        await self.circuit_breaker.record_failure()
        if last_exc:
            raise last_exc
        raise RuntimeError("Request failed after retries")

    async def check_health(self, timeout_seconds: float = 2.0) -> dict[str, Any]:
        """Call GET /healthz (docs/07_AI_PLANNER_API.md §3)."""
        endpoint = f"{self.service_url.rstrip('/')}/healthz"
        if self._external_client:
            resp = await self._external_client.get(endpoint, timeout=timeout_seconds)
        else:
            async with httpx.AsyncClient() as client:
                resp = await client.get(endpoint, timeout=timeout_seconds)
        resp.raise_for_status()
        return resp.json()

    async def get_contract(self, timeout_seconds: float = 2.0) -> dict[str, Any]:
        """Call GET /v1/contract (docs/07_AI_PLANNER_API.md §3)."""
        endpoint = f"{self.service_url.rstrip('/')}/v1/contract"
        if self._external_client:
            resp = await self._external_client.get(endpoint, timeout=timeout_seconds)
        else:
            async with httpx.AsyncClient() as client:
                resp = await client.get(endpoint, timeout=timeout_seconds)
        resp.raise_for_status()
        return resp.json()

    async def propose_quizzes(self, req: QuizProposeRequest) -> QuizProposeResponse:
        """Call POST /v1/quizzes/propose (docs/07_AI_PLANNER_API.md §3 - 15s timeout)."""
        headers = self._get_service_headers(req.idempotency_key, req.request_id)
        endpoint = f"{self.service_url.rstrip('/')}/v1/quizzes/propose"
        data = await self._post_with_retries(
            endpoint=endpoint,
            payload=req.model_dump(mode="json"),
            headers=headers,
            timeout_seconds=15.0,
        )
        return QuizProposeResponse.model_validate(data)

    async def propose_revision(self, req: RevisionProposeRequest) -> RevisionProposeResponse:
        """Call POST /v1/revision/propose (docs/07_AI_PLANNER_API.md §3 - 15s timeout)."""
        headers = self._get_service_headers(req.idempotency_key, req.request_id)
        endpoint = f"{self.service_url.rstrip('/')}/v1/revision/propose"
        data = await self._post_with_retries(
            endpoint=endpoint,
            payload=req.model_dump(mode="json"),
            headers=headers,
            timeout_seconds=15.0,
        )
        return RevisionProposeResponse.model_validate(data)

    async def draft_questions(self, req: QuestionDraftRequest) -> QuestionDraftResponse:
        """Call POST /v1/questions/draft (docs/07_AI_PLANNER_API.md §3 - 30s timeout)."""
        headers = self._get_service_headers(req.idempotency_key, req.request_id)
        endpoint = f"{self.service_url.rstrip('/')}/v1/questions/draft"
        data = await self._post_with_retries(
            endpoint=endpoint,
            payload=req.model_dump(mode="json"),
            headers=headers,
            timeout_seconds=30.0,
        )
        return QuestionDraftResponse.model_validate(data)

    async def explain_insights(self, req: InsightExplainRequest) -> InsightExplainResponse:
        """Call POST /v1/insights/explain (docs/07_AI_PLANNER_API.md §3 - 15s timeout)."""
        headers = self._get_service_headers(req.idempotency_key, req.request_id)
        endpoint = f"{self.service_url.rstrip('/')}/v1/insights/explain"
        data = await self._post_with_retries(
            endpoint=endpoint,
            payload=req.model_dump(mode="json"),
            headers=headers,
            timeout_seconds=15.0,
        )
        return InsightExplainResponse.model_validate(data)


def get_plan_provider(
    resolved_settings: ResolvedPlannerSettings,
    client: httpx.AsyncClient | None = None,
) -> PlanProvider:
    """Return appropriate PlanProvider taking into account kill switches, class band rollout, and per-student mode."""
    # 1. Global Kill Switch
    if not app_settings.AI_PLANNER_ENABLED:
        return DeterministicProvider()

    # 2. Per-class-band rollout gate
    if resolved_settings.class_band not in app_settings.AI_PLANNER_ENABLED_CLASS_BANDS:
        logger.info(
            "AI planner not enabled for class band %s (active rollout: %s). Using deterministic.",
            resolved_settings.class_band,
            app_settings.AI_PLANNER_ENABLED_CLASS_BANDS,
        )
        return DeterministicProvider()

    # 3. Per-student override: manual mode forces deterministic planner
    if resolved_settings.adaptive_mode == "manual":
        return DeterministicProvider()

    return AiPlannerProvider(client=client)
