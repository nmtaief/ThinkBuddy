"""ThinkBuddy API Gateway application entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core.common.logging import RequestIDMiddleware, request_id_ctx, setup_logging
from core.common.redis import check_redis_ready, close_redis
from core.common.telemetry import setup_telemetry
from gateway.client import core_client
from gateway.config import settings
from gateway.middleware import ClientHeadersMiddleware
from gateway.router import router as v1_router

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


is_local = settings.is_local

app = FastAPI(
    title="ThinkBuddy API Gateway",
    description="Edge API Gateway handling routing, rate limiting, and client config.",
    version="0.1.0",
    docs_url="/docs" if is_local else None,
    redoc_url=None,  # Redoc disabled across all environments
    openapi_url="/openapi.json" if is_local else None,
    lifespan=lifespan,
)

# Correlation ID and structured HTTP logging middleware
app.add_middleware(RequestIDMiddleware)

# Client headers enforcement middleware
app.add_middleware(ClientHeadersMiddleware)


@app.exception_handler(HTTPException)
async def gateway_http_exception_handler(_request: Any, exc: HTTPException) -> JSONResponse:
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


@app.exception_handler(RequestValidationError)
async def gateway_validation_exception_handler(
    _request: Any, exc: RequestValidationError
) -> JSONResponse:
    request_id = request_id_ctx.get() or ""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": exc.errors(),
                "request_id": request_id,
            }
        },
    )


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


@app.api_route("/internal/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
async def block_gateway_internal_direct(path: str) -> JSONResponse:
    """Public gateway strictly refuses to expose internal routes."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": {"code": "NOT_FOUND", "message": "Endpoint not found"}},
    )


# Mount public API routes
app.include_router(v1_router)
