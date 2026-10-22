"""Structured JSON logging with request ID tracing and sensitive data masking."""

import contextvars
import json
import logging
import sys
import time
import uuid
from collections.abc import Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable to track the active request ID across async tasks
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

SENSITIVE_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "internal_service_token",
    "secret",
    "otp",
    "answer_key",
}


def mask_sensitive_data(data: Any) -> Any:
    """Recursively mask sensitive values in logs."""
    if isinstance(data, dict):
        return {
            k: ("***MASKED***" if k.lower() in SENSITIVE_KEYS else mask_sensitive_data(v))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [mask_sensitive_data(item) for item in data]
    return data


class JSONFormatter(logging.Formatter):
    """Formats log records as structured single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get() or getattr(record, "request_id", None),
        }

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        # Attach custom attributes if any
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            log_obj["extra"] = mask_sensitive_data(record.extra_fields)

        return json.dumps(log_obj, ensure_ascii=False)


def setup_logging(service_name: str, log_level: str = "INFO") -> None:
    """Configure root logger to use structured JSON logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)

    # Set specific third-party logger levels
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """FastAPI / Starlette middleware for request correlation ID tracking and request logging."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        token = request_id_ctx.set(req_id)
        start_time = time.perf_counter()

        logger = logging.getLogger("http_access")
        try:
            response: Response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            response.headers["X-Request-Id"] = req_id

            logger.info(
                f"{request.method} {request.url.path} - {response.status_code} ({duration_ms}ms)",
                extra={"request_id": req_id},
            )
            return response
        finally:
            request_id_ctx.reset(token)
