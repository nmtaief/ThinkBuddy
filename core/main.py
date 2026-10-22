"""ThinkBuddy Core Service application entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, status
from fastapi.responses import JSONResponse

from core.common.auth import verify_internal_service_token
from core.common.config import settings
from core.common.database import check_database_ready
from core.common.logging import RequestIDMiddleware, setup_logging
from core.common.redis import check_redis_ready, close_redis
from core.common.telemetry import setup_telemetry

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
    title="ThinkBuddy Core Service",
    description="Core business logic, data models, domain modules, and persistence for ThinkBuddy.",
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
    """Liveness probe. Returns 200 OK if service process is alive."""
    return {"status": "ok", "service": "core"}


@app.get("/readyz", tags=["Health"])
async def readyz() -> JSONResponse:
    """Readiness probe. Checks connectivity to PostgreSQL (pgvector) and Redis."""
    db_ok, db_msg = await check_database_ready()
    redis_ok, redis_msg = await check_redis_ready()

    is_ready = db_ok and redis_ok
    payload: dict[str, Any] = {
        "status": "ready" if is_ready else "not_ready",
        "service": "core",
        "checks": {
            "database": {"ok": db_ok, "detail": db_msg},
            "redis": {"ok": redis_ok, "detail": redis_msg},
        },
    }

    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=payload)


# Include domain modules with internal service token protection
# Modules: auth, families, curriculum, planner, questions, quiz, reviews, chat, progress,
#          revision, notifications, devices, entitlements, admin, audit
from core.admin.router import router as admin_router  # noqa: E402
from core.audit.router import router as audit_router  # noqa: E402
from core.auth.router import router as auth_router  # noqa: E402
from core.chat.router import router as chat_router  # noqa: E402
from core.curriculum.router import router as curriculum_router  # noqa: E402
from core.devices.router import router as devices_router  # noqa: E402
from core.entitlements.router import router as entitlements_router  # noqa: E402
from core.families.router import router as families_router  # noqa: E402
from core.notifications.router import router as notifications_router  # noqa: E402
from core.planner.router import router as planner_router  # noqa: E402
from core.progress.router import router as progress_router  # noqa: E402
from core.questions.router import router as questions_router  # noqa: E402
from core.quiz.router import router as quiz_router  # noqa: E402
from core.reviews.router import router as reviews_router  # noqa: E402
from core.revision.router import router as revision_router  # noqa: E402

internal_routers = [
    auth_router,
    families_router,
    curriculum_router,
    planner_router,
    questions_router,
    quiz_router,
    reviews_router,
    chat_router,
    progress_router,
    revision_router,
    notifications_router,
    devices_router,
    entitlements_router,
    admin_router,
    audit_router,
]

for router in internal_routers:
    app.include_router(
        router,
        dependencies=[Depends(verify_internal_service_token)],
    )
