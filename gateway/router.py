"""API Gateway routing and forwarder to Core Service.

Defines client-facing endpoints according to docs/04_API_CONTRACT.md, enforces rate limiting,
and routes requests downstream to the Core Service via internal service client.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Header, Request, Response, status
from fastapi.responses import JSONResponse

from core.auth.router import (
    AuthExchangeRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
)
from core.common.logging import request_id_ctx
from core.common.rate_limit import RateLimiter, build_rate_limit_key, get_trusted_client_ip
from core.devices.router import (
    DeviceResponse,
    RegisterDeviceRequest,
    UpdateDeviceRequest,
)
from core.families.router import (
    AddChildRequest,
    AddChildResponse,
    CreateFamilyRequest,
    FamilyResponse,
    LinkedStudentResponse,
    RedeemLinkRequest,
    RedeemLinkResponse,
)
from core.reviews.router import FlagTopicRequest, ReviewSubmissionRequest
from gateway.client import core_client

router = APIRouter(prefix="/v1")


async def forward_to_core(request: Request, json_body: Any = None) -> Response:
    """Forward incoming Gateway request to Core service and relay response."""
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)

    if json_body is None and request.method in {"POST", "PUT", "PATCH"}:
        try:
            json_body = await request.json()
        except Exception:
            json_body = None

    core_res = await core_client.request(
        method=request.method,
        path=request.url.path,
        params=dict(request.query_params),
        json_data=json_body,
        headers=headers,
    )

    response_headers: dict[str, str] = {}
    for k, v in core_res.headers.items():
        if k.lower() not in {"content-length", "content-encoding", "transfer-encoding"}:
            response_headers[k] = v

    return Response(
        content=core_res.content,
        status_code=core_res.status_code,
        headers=response_headers,
        media_type=core_res.headers.get("content-type", "application/json"),
    )


def _get_client_rate_key(request: Request, prefix: str) -> str:
    trusted_ip = get_trusted_client_ip(request)
    device_id = request.headers.get("x-device-id", "")
    ident = device_id if device_id else "anonymous"
    return build_rate_limit_key(prefix, trusted_ip, ident)


# -------------------------------------------------------------------------
# Client & Config
# -------------------------------------------------------------------------
@router.get("/client/config", tags=["Client & Config"])
async def get_client_config(
    x_client_platform: str = Header(default="android", alias="X-Client-Platform"),
    x_client_form_factor: str = Header(default="phone", alias="X-Client-Form-Factor"),
    x_app_version: str = Header(default="1.0.0", alias="X-App-Version"),
) -> dict[str, Any]:
    """Dynamic client configuration endpoint per docs/04_API_CONTRACT.md §1 & §5.

    Returns server-driven settings, minimum version thresholds, active feature flags,
    and quiz security modes allowed per platform without code branching.
    Aligned with docs/05_SECURE_QUIZ.md §3 ('assessed' on mobile, 'practice_only' on web).
    """
    platform = x_client_platform.lower()
    form_factor = x_client_form_factor.lower()

    if platform in ("android", "ios"):
        quiz_security_mode = "assessed"
    else:
        quiz_security_mode = "practice_only"

    return {
        "min_supported_version": "1.0.0",
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
            "flag_secure": (platform == "android"),
            "heartbeat_interval_seconds": 15,
        },
        "polling_intervals": {
            "plan_poll_seconds": 300,
            "notifications_poll_seconds": 60,
        },
        "layout_hints": {
            "dashboard_cards_order": ["today_tasks", "spaced_revision", "streak", "exam_countdown"],
            "image_size_class": "lg" if form_factor in ("tablet", "desktop") else "md",
        },
    }


# -------------------------------------------------------------------------
# Auth & Identity
# -------------------------------------------------------------------------
@router.post("/auth/exchange", response_model=TokenResponse, tags=["Auth"])
async def exchange_auth_token(payload: AuthExchangeRequest, request: Request) -> Response:
    """Exchange third-party provider credential for ThinkBuddy session tokens.

    Strictly rate limited to prevent credential guessing.
    """
    rate_key = _get_client_rate_key(request, "auth_exchange")
    allowed, retry_after = await RateLimiter.check_rate_limit(
        rate_key, max_requests=10, window_seconds=60
    )
    if not allowed:
        req_id = request_id_ctx.get() or ""
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many authentication attempts. Please try again later.",
                    "request_id": req_id,
                }
            },
        )
    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))


@router.post("/auth/refresh", response_model=TokenResponse, tags=["Auth"])
async def refresh_auth_token(payload: RefreshTokenRequest, request: Request) -> Response:
    """Rotate refresh token and issue a new access token."""
    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))


@router.post("/auth/logout", tags=["Auth"])
async def logout(payload: RefreshTokenRequest, request: Request) -> Response:
    """Revoke refresh token session."""
    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))


@router.get("/me", response_model=UserResponse, tags=["Auth"])
async def get_me(request: Request) -> Response:
    """Return profile of currently authenticated user."""
    return await forward_to_core(request)


# -------------------------------------------------------------------------
# Families & Linking
# -------------------------------------------------------------------------
@router.post(
    "/families",
    response_model=FamilyResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Families"],
)
async def create_family(payload: CreateFamilyRequest, request: Request) -> Response:
    """Parent creates a new family unit."""
    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))


@router.post(
    "/families/{family_id}/students",
    response_model=AddChildResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Families"],
)
async def add_child(family_id: uuid.UUID, payload: AddChildRequest, request: Request) -> Response:
    """Parent adds child profile and generates expiring link code."""
    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))


@router.post("/links/redeem", response_model=RedeemLinkResponse, tags=["Families"])
async def redeem_link_code(payload: RedeemLinkRequest, request: Request) -> Response:
    """Student redeems link code to establish family connection.

    Strictly rate limited to prevent brute-force attacks on link codes.
    """
    rate_key = _get_client_rate_key(request, "link_redeem")
    allowed, retry_after = await RateLimiter.check_rate_limit(
        rate_key, max_requests=5, window_seconds=60
    )
    if not allowed:
        req_id = request_id_ctx.get() or ""
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many link redemption attempts. Please try again later.",
                    "request_id": req_id,
                }
            },
        )

    res = await forward_to_core(request, json_body=payload.model_dump(mode="json"))
    if res.status_code >= 400:
        is_locked, lockout_seconds = await RateLimiter.record_failure(rate_key)
        if is_locked:
            req_id = request_id_ctx.get() or ""
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(lockout_seconds)},
                content={
                    "error": {
                        "code": "LOCKED_OUT",
                        "message": (
                            "Repeated failed link redemption attempts. "
                            "15-minute security lockout active."
                        ),
                        "request_id": req_id,
                    }
                },
            )
    else:
        await RateLimiter.record_success(rate_key)

    return res


@router.post("/links/{link_id}/revoke", tags=["Families"])
async def revoke_link(link_id: uuid.UUID, request: Request) -> Response:
    """Parent revokes student link, immediately cutting off access."""
    return await forward_to_core(request)


@router.get("/parents/me/students", response_model=list[LinkedStudentResponse], tags=["Families"])
async def list_parent_students(request: Request) -> Response:
    """List all active linked children for authenticated parent."""
    return await forward_to_core(request)


@router.get("/students/{student_id}", tags=["Families"])
async def get_student_details(student_id: uuid.UUID, request: Request) -> Response:
    """Fetch student profile; requires ownership (student or linked parent)."""
    return await forward_to_core(request)


# -------------------------------------------------------------------------
# Devices
# -------------------------------------------------------------------------
@router.post(
    "/devices", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED, tags=["Devices"]
)
async def register_device(payload: RegisterDeviceRequest, request: Request) -> Response:
    """Register or refresh client device registration."""
    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))


@router.patch("/devices/{device_id}", response_model=DeviceResponse, tags=["Devices"])
async def update_device(
    device_id: uuid.UUID, payload: UpdateDeviceRequest, request: Request
) -> Response:
    """Update device push token or app version."""
    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))


# -------------------------------------------------------------------------
# Teacher Reviews (Feature Flagged Off in Beta)
# -------------------------------------------------------------------------
@router.get("/teacher/queue", tags=["Teacher Reviews (Feature Flagged)"])
async def get_teacher_queue(request: Request) -> Response:
    """Retrieve queue of broad submissions awaiting review."""
    return await forward_to_core(request)


@router.post(
    "/teacher/submissions/{submission_id}/review", tags=["Teacher Reviews (Feature Flagged)"]
)
async def submit_teacher_review(
    submission_id: uuid.UUID, payload: ReviewSubmissionRequest, request: Request
) -> Response:
    """Submit teacher evaluation and score."""
    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))


@router.post("/teacher/topics/flag", tags=["Teacher Reviews (Feature Flagged)"])
async def flag_teacher_topic(payload: FlagTopicRequest, request: Request) -> Response:
    """Flag a difficult topic to adjust adaptive revision weights."""
    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))
