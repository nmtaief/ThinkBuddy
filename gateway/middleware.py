"""Gateway middleware for client header enforcement.

Enforces docs/01_ARCHITECTURE.md §5 and docs/04_API_CONTRACT.md §1:
- Required headers: X-Client-Platform, X-Client-Form-Factor,
  X-App-Version, X-Device-Id, Accept-Language
- Returns standardized 400 response with code: INVALID_CLIENT_HEADERS
"""

from __future__ import annotations

from fastapi import status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from core.common.logging import request_id_ctx
from gateway.config import settings

VALID_PLATFORMS = {"android", "ios", "web"}
VALID_FORM_FACTORS = {"phone", "tablet", "desktop"}

EXEMPT_PATHS = {
    "/healthz",
    "/readyz",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
}


class ClientHeadersMiddleware(BaseHTTPMiddleware):
    """Enforce required client headers on all external client-facing API requests."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Bypass health, probe, doc endpoints, or internal service calls
        if path in EXEMPT_PATHS or any(path.startswith(p) for p in ("/docs", "/redoc")):
            return await call_next(request)

        # Allow bypass if internal service token matches
        internal_token = request.headers.get("x-internal-service-token")
        if internal_token and internal_token == settings.INTERNAL_SERVICE_TOKEN:
            return await call_next(request)

        # Extract client headers
        platform = request.headers.get("x-client-platform", "").strip().lower()
        form_factor = request.headers.get("x-client-form-factor", "").strip().lower()
        app_version = request.headers.get("x-app-version", "").strip()
        device_id = request.headers.get("x-device-id", "").strip()
        accept_language = request.headers.get("accept-language", "").strip().lower()

        # Validate headers
        is_platform_valid = platform in VALID_PLATFORMS
        is_form_factor_valid = form_factor in VALID_FORM_FACTORS
        is_version_valid = bool(app_version)
        is_device_valid = bool(device_id)
        is_lang_valid = bool(accept_language) and (
            "bn" in accept_language or "en" in accept_language
        )

        if not (
            is_platform_valid
            and is_form_factor_valid
            and is_version_valid
            and is_device_valid
            and is_lang_valid
        ):
            req_id = request_id_ctx.get() or request.headers.get("x-request-id", "")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": {
                        "code": "INVALID_CLIENT_HEADERS",
                        "message": (
                            "Missing or invalid required client headers. "
                            "Required: X-Client-Platform (android|ios|web), "
                            "X-Client-Form-Factor (phone|tablet|desktop), "
                            "X-App-Version, X-Device-Id, Accept-Language (bn|en)."
                        ),
                        "request_id": req_id,
                    }
                },
            )

        return await call_next(request)
