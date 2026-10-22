"""ThinkBuddy API Gateway application entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, status
from fastapi.responses import JSONResponse

from core.common.logging import RequestIDMiddleware, setup_logging
from core.common.redis import check_redis_ready, close_redis
from core.common.telemetry import setup_telemetry
from gateway.client import core_client
from gateway.config import settings

# Setup structured logging
setup_logging(service_name=settings.OTEL_SERVICE_NAME, log_level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown hooks."""
    setup_telemetry(
        service_name=settings.OTEL_SERVICE_NAME,
        enabled=settings.OTEL_ENABLED,
        endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
    )
    yield
    await close_redis()


app = FastAPI(
    title="ThinkBuddy API Gateway",
    description="Edge API Gateway handling routing, rate limiting, and client config.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Correlation ID and structured HTTP logging middleware
app.add_middleware(RequestIDMiddleware)


@app.get("/healthz", tags=["Health"])
async def healthz() -> dict[str, str]:
    """Liveness probe. Returns 200 OK if gateway process is alive."""
    return {"status": "ok", "service": "gateway"}


@app.get("/readyz", tags=["Health"])
async def readyz() -> JSONResponse:
    """Readiness probe. Checks Redis connection and downstream Core service connectivity."""
    redis_ok, redis_msg = await check_redis_ready()
    core_ok, core_msg = await core_client.check_core_ready()

    is_ready = redis_ok and core_ok
    payload: dict[str, Any] = {
        "status": "ready" if is_ready else "not_ready",
        "service": "gateway",
        "checks": {
            "redis": {"ok": redis_ok, "detail": redis_msg},
            "core": {"ok": core_ok, "detail": core_msg},
        },
    }

    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=payload)


@app.get("/v1/client/config", tags=["Client & Config"])
async def get_client_config(
    x_client_platform: str = Header(default="android", alias="X-Client-Platform"),
    x_client_form_factor: str = Header(default="phone", alias="X-Client-Form-Factor"),
    x_app_version: str = Header(default="0.1.0", alias="X-App-Version"),
) -> dict[str, Any]:
    """Dynamic client configuration endpoint per docs/04_API_CONTRACT.md §1 & §5.

    Returns server-driven settings, minimum version thresholds, active feature flags,
    and quiz security modes allowed per platform without code branching.
    """
    # Practice allowed everywhere; assessed quizzes restricted to hardened mobile apps
    quiz_security_mode = (
        "secure_app" if x_client_platform in ("android", "ios") else "practice_only"
    )

    return {
        "min_supported_version": "0.1.0",
        "force_update": False,
        "feature_flags": {
            "teacher_reviews": False,  # Beta flag: teacher features flagged off per architecture
            "broad_questions_ai_assist": True,
            "bangla_voice_input": False,
        },
        "entitlements": {
            "daily_chat_quota": 50,
            "max_active_subjects": 5,
        },
        "quiz_security": {
            "allowed_mode": quiz_security_mode,
            "screen_pinning_required": (x_client_platform == "android"),
            "heartbeat_interval_seconds": 15,
        },
        "layout_hints": {
            "dashboard_cards_order": ["today_tasks", "spaced_revision", "streak", "exam_countdown"],
            "image_size_class": "lg" if x_client_form_factor in ("tablet", "desktop") else "md",
        },
    }
