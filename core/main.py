"""ThinkBuddy Core Service application entrypoint."""

import os
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

logger = logging.getLogger(__name__)

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

from core.common.auth import verify_internal_service_token
from core.common.config import settings
from core.common.database import check_database_ready
from core.common.logging import RequestIDMiddleware, request_id_ctx, setup_logging
from core.common.metrics import metrics_endpoint, metrics_middleware
from core.common.redis import check_redis_ready, close_redis
from core.common.sentry import init_sentry
from core.common.telemetry import setup_telemetry
from core.common.database import get_db_session
from rag.embedding import verify_embedding_compatibility

# Setup structured logging
setup_logging(service_name=settings.OTEL_SERVICE_NAME, log_level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown hooks."""
    if settings.ENVIRONMENT == "production":
        pub_domain = getattr(settings, "PUBLIC_DOMAIN", None) or os.getenv("PUBLIC_DOMAIN")
        if not pub_domain or pub_domain.strip() in {"localhost", "127.0.0.1", "placeholder"}:
            raise RuntimeError(
                "Production configuration refuses to start without an explicit PUBLIC_DOMAIN environment variable."
            )
    init_sentry(
        dsn=getattr(settings, "SENTRY_DSN", None),
        environment=settings.ENVIRONMENT,
    )
    setup_telemetry(
        service_name=settings.OTEL_SERVICE_NAME,
        enabled=settings.OTEL_ENABLED,
        endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
    )
    # Fail-loud check for RAG vector embedding dimensions and model compatibility
    app.state.vector_search_enabled = False
    app.state.embedding_model_loaded = False
    app.state.embedding_error = None

    try:
        async for session in get_db_session():
            await verify_embedding_compatibility(session)
            app.state.vector_search_enabled = True
            app.state.embedding_model_loaded = True
            logger.info("RAG vector embeddings and BGE-M3 model verified successfully.")
            break
    except Exception as ex:
        app.state.vector_search_enabled = False
        app.state.embedding_model_loaded = False
        app.state.embedding_error = str(ex)
        logger.critical(
            "CRITICAL: RAG embedding check failed: %s. Vector search is DISABLED. Mock embeddings forbidden.",
            ex,
            exc_info=True,
        )
    yield
    await close_redis()


is_local = settings.is_local

app = FastAPI(
    title="ThinkBuddy Core Service",
    description="Core business logic, data models, domain modules, and persistence for ThinkBuddy.",
    version="0.1.0",
    docs_url="/docs" if is_local else None,
    redoc_url=None,  # Redoc disabled across all environments
    openapi_url="/openapi.json" if is_local else None,
    lifespan=lifespan,
)

# Correlation ID and structured HTTP logging middleware
app.add_middleware(RequestIDMiddleware)
app.middleware("http")(metrics_middleware)


@app.get("/metrics", tags=["Observability"])
async def get_metrics() -> Any:
    """Prometheus metrics scrape endpoint."""
    return metrics_endpoint()


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


@app.get("/health", tags=["Health"])
async def comprehensive_health() -> JSONResponse:
    """Comprehensive health endpoint reporting embedding model, DB, and LLM reachability."""
    db_ok, db_msg = await check_database_ready()
    emb_loaded = bool(getattr(app.state, "embedding_model_loaded", False))
    vec_enabled = bool(getattr(app.state, "vector_search_enabled", False))
    emb_err = getattr(app.state, "embedding_error", None)

    # Check LLM reachability (without leaking key)
    llm_reachable = False
    llm_detail = "unconfigured"
    try:
        from core.chat.llm import get_active_llm_gateway
        async for session in get_db_session():
            gw = await get_active_llm_gateway(session)
            if gw:
                import httpx
                headers = {"Authorization": f"Bearer {gw.api_key}"} if getattr(gw, "api_key", None) else {}
                async with httpx.AsyncClient(timeout=3.0) as client:
                    # Check Ollama / local or OpenRouter
                    if "11434" in str(gw.api_base) or "ollama" in str(gw.api_base):
                        resp = await client.get(f"{gw.api_base}/models", headers=headers)
                    else:
                        resp = await client.get(f"{gw.api_base}/auth/key", headers=headers)
                    if resp.status_code == 200:
                        llm_reachable = True
                        llm_detail = "reachable"
                    elif resp.status_code == 401:
                        llm_detail = "expired_api_key"
                    else:
                        llm_detail = f"http_{resp.status_code}"
            break
    except Exception as ex:
        llm_detail = f"error: {str(ex)[:100]}"

    is_healthy = db_ok and emb_loaded and llm_reachable
    status_str = "healthy" if is_healthy else "degraded"

    payload = {
        "status": status_str,
        "service": "core",
        "db_reachable": db_ok,
        "db_detail": db_msg,
        "embedding_model_loaded": emb_loaded,
        "vector_search_enabled": vec_enabled,
        "embedding_error": emb_err,
        "llm_reachable": llm_reachable,
        "llm_status": llm_detail,
    }
    code = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=code, content=payload)


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
from core.parent.router import router as parent_router  # noqa: E402
from core.privacy.router import router as privacy_router  # noqa: E402
from core.planner.admin_router import router as planner_admin_router  # noqa: E402
from core.planner.router import router as planner_router  # noqa: E402
from core.progress.router import router as progress_router  # noqa: E402
from core.questions.router import router as questions_router  # noqa: E402
from core.quiz.admin_router import router as quiz_admin_router  # noqa: E402
from core.quiz.router import router as quiz_router  # noqa: E402
from core.reviews.router import router as reviews_router  # noqa: E402
from core.revision.router import router as revision_router  # noqa: E402

internal_routers = [
    auth_router,
    families_router,
    curriculum_router,
    planner_router,
    planner_admin_router,
    questions_router,
    quiz_router,
    quiz_admin_router,
    reviews_router,
    chat_router,
    progress_router,
    revision_router,
    notifications_router,
    parent_router,
    privacy_router,
    devices_router,
    entitlements_router,
    admin_router,
    audit_router,
]


@app.exception_handler(HTTPException)
async def core_http_exception_handler(_request: Any, exc: HTTPException) -> JSONResponse:
    request_id = request_id_ctx.get() or ""
    detail: Any = exc.detail
    if isinstance(detail, dict):
        code = detail.get("code", "ERROR")
        message = detail.get("message", str(detail))
    else:
        code = "HTTP_ERROR"
        message = str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message, "request_id": request_id}},
        headers=getattr(exc, "headers", None),
    )


for router in internal_routers:
    # Mount with /v1 prefix per docs/04_API_CONTRACT.md
    app.include_router(
        router,
        prefix="/v1",
        dependencies=[Depends(verify_internal_service_token)],
    )
    # Also mount at root for internal compatibility
    app.include_router(
        router,
        dependencies=[Depends(verify_internal_service_token)],
    )
