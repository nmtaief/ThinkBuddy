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
from core.auth.tokens import hash_link_code
from core.common.logging import request_id_ctx
from core.common.rate_limit import RateLimiter, get_trusted_client_ip
from core.curriculum.schemas import (
    BookListResponse,
    BookSummary,
    ChapterDetailResponse,
    ChapterListResponse,
)
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
from core.planner.schemas import (
    DailyMinutesResponse,
    PlanResponse,
    StudentChangeRequestInput,
    StudentChangeRequestResponse,
    StudySetupResponse,
    TaskResponse,
    TodayHomePayloadResponse,
    UpdateDailyMinutesRequest,
    UpdateTaskStatusRequest,
    UpsertStudySetupRequest,
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
    return f"rl:{prefix}:ip:{trusted_ip}"


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

    Strictly rate limited to prevent credential guessing, keyed primarily on server-trusted IP.
    """
    trusted_ip = get_trusted_client_ip(request)
    ip_key = f"rl:auth_exchange:ip:{trusted_ip}"
    allowed, retry_after = await RateLimiter.check_rate_limit(
        ip_key, max_requests=10, window_seconds=60
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

    Enforces multi-layer rate limits keyed on server-trusted values:
    1. Per trusted IP: rl:link_redeem:ip:{trusted_ip}
    2. Per target link code: rl:link_redeem:target:{code_hash}
    3. Global ceiling for link-redemption failures: rl:link_redeem:global_failures
    4. Client-supplied device ID as extra layer: rl:link_redeem:device:{trusted_ip}:{device_id}
    """
    trusted_ip = get_trusted_client_ip(request)
    ip_key = f"rl:link_redeem:ip:{trusted_ip}"

    target_code = payload.link_code.strip().upper()
    code_hash = hash_link_code(target_code)
    target_key = f"rl:link_redeem:target:{code_hash}"

    device_id = request.headers.get("x-device-id", "")
    device_key = f"rl:link_redeem:device:{trusted_ip}:{device_id}" if device_id else None
    global_failures_key = "rl:link_redeem:global_failures"

    # 1. Server-trusted IP rate limit & lockout check
    allowed_ip, retry_ip = await RateLimiter.check_rate_limit(
        ip_key, max_requests=5, window_seconds=60
    )
    if not allowed_ip:
        req_id = request_id_ctx.get() or ""
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_ip)},
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": (
                        "Too many link redemption attempts from this IP. Please try again later."
                    ),
                    "request_id": req_id,
                }
            },
        )

    # 2. Server-trusted target link code rate limit
    allowed_target, retry_target = await RateLimiter.check_rate_limit(
        target_key, max_requests=5, window_seconds=600
    )
    if not allowed_target:
        req_id = request_id_ctx.get() or ""
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_target)},
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many attempts for this link code. Please try again later.",
                    "request_id": req_id,
                }
            },
        )

    # 3. Client device limit (extra layer only)
    if device_key:
        allowed_dev, retry_dev = await RateLimiter.check_rate_limit(
            device_key, max_requests=5, window_seconds=60
        )
        if not allowed_dev:
            req_id = request_id_ctx.get() or ""
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_dev)},
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many link redemption attempts from this device.",
                        "request_id": req_id,
                    }
                },
            )

    res = await forward_to_core(request, json_body=payload.model_dump(mode="json"))
    if res.status_code >= 400:
        # 1. Server-trusted IP failure tracking & 15-min lockout
        is_locked, lockout_seconds = await RateLimiter.record_failure(ip_key)
        # 2. Target code failure tracking
        await RateLimiter.record_failure(target_key)
        # 3. Global failure ceiling
        global_count = await RateLimiter.increment_counter(global_failures_key, window_seconds=60)
        # 4. Device failure tracking (extra layer)
        if device_key:
            await RateLimiter.record_failure(device_key)

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
        if global_count > 100:
            req_id = request_id_ctx.get() or ""
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": "60"},
                content={
                    "error": {
                        "code": "GLOBAL_RATE_LIMIT_EXCEEDED",
                        "message": (
                            "Global link redemption threshold exceeded. Please try again later."
                        ),
                        "request_id": req_id,
                    }
                },
            )
    else:
        await RateLimiter.record_success(ip_key)
        await RateLimiter.record_success(target_key)
        if device_key:
            await RateLimiter.record_success(device_key)

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
# Curriculum & Textbooks
# -------------------------------------------------------------------------
@router.get("/books", response_model=BookListResponse, tags=["Curriculum"])
async def list_books(request: Request) -> Response:
    """Retrieve list of curriculum textbooks."""
    return await forward_to_core(request)


@router.get("/books/{book_id}", response_model=BookSummary, tags=["Curriculum"])
async def get_book(book_id: uuid.UUID, request: Request) -> Response:
    """Get metadata for a specific curriculum textbook."""
    return await forward_to_core(request)


@router.get("/books/{book_id}/chapters", response_model=ChapterListResponse, tags=["Curriculum"])
async def get_book_chapters(book_id: uuid.UUID, request: Request) -> Response:
    """Get ordered list of chapters for a given curriculum textbook."""
    return await forward_to_core(request)


@router.get("/chapters/{chapter_id}", response_model=ChapterDetailResponse, tags=["Curriculum"])
async def get_chapter_detail(chapter_id: uuid.UUID, request: Request) -> Response:
    """Get detailed chapter information including educational concepts and chunk counts."""
    return await forward_to_core(request)


# -------------------------------------------------------------------------
# Planning & Study Setup
# -------------------------------------------------------------------------
@router.put(
    "/students/{student_id}/study-setups/{subject}",
    response_model=StudySetupResponse,
    tags=["Planning"],
)
async def upsert_study_setup(
    student_id: uuid.UUID,
    subject: str,
    payload: UpsertStudySetupRequest,
    request: Request,
) -> Response:
    """Parent configures syllabus, exam date, and chapter order for student."""
    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))


@router.put(
    "/students/{student_id}/daily-minutes",
    response_model=DailyMinutesResponse,
    tags=["Planning"],
)
async def update_student_daily_minutes(
    student_id: uuid.UUID,
    payload: UpdateDailyMinutesRequest,
    request: Request,
) -> Response:
    """Parent updates student-level daily minutes budget."""
    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))


@router.post(
    "/students/{student_id}/study-setups/{subject}/change-requests",
    response_model=StudentChangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Planning"],
)
async def submit_student_change_request(
    student_id: uuid.UUID,
    subject: str,
    payload: StudentChangeRequestInput,
    request: Request,
) -> Response:
    """Student submits proposed schedule adjustment to their study setup."""
    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))


@router.get(
    "/students/{student_id}/plan",
    response_model=PlanResponse,
    tags=["Planning"],
)
async def get_student_plan(student_id: uuid.UUID, request: Request) -> Response:
    """Fetch active versioned study plan and daily tasks."""
    return await forward_to_core(request)


@router.get(
    "/students/{student_id}/today",
    response_model=TodayHomePayloadResponse,
    tags=["Planning"],
)
async def get_today_payload(student_id: uuid.UUID, request: Request) -> Response:
    """Home screen daily learning loop payload."""
    return await forward_to_core(request)


@router.patch(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    tags=["Planning"],
)
async def update_task_status(
    task_id: uuid.UUID,
    payload: UpdateTaskStatusRequest,
    request: Request,
) -> Response:
    """Update task completion status (student only)."""
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
