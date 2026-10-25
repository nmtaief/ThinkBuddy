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
from core.auth.tokens import decode_access_jwt, hash_link_code
from core.common.logging import request_id_ctx
from core.common.rate_limit import RateLimiter, build_rate_limit_key, get_trusted_client_ip
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
    StudentStudySettingsResponse,
    StudySetupResponse,
    TaskResponse,
    TodayHomePayloadResponse,
    UpdateDailyMinutesRequest,
    UpdateStudentStudySettingsRequest,
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
        "observance_catalog": [
            {"key": "eid_ul_fitr", "name_bn": "ঈদুল ফিতর", "name_en": "Eid-ul-Fitr"},
            {"key": "eid_ul_adha", "name_bn": "ঈদুল আযহা", "name_en": "Eid-ul-Adha"},
            {"key": "durga_puja", "name_bn": "দুর্গাপূজা", "name_en": "Durga Puja"},
            {"key": "christmas", "name_bn": "বড়দিন", "name_en": "Christmas"},
            {"key": "buddha_purnima", "name_bn": "বুদ্ধ পূর্ণিমা", "name_en": "Buddha Purnima"},
            {"key": "shab_e_barat", "name_bn": "শবে বরাত", "name_en": "Shab-e-Barat"},
            {"key": "shab_e_qadr", "name_bn": "শবে কদর", "name_en": "Shab-e-Qadr"},
            {"key": "pohela_boishakh", "name_bn": "পহেলা বৈশাখ", "name_en": "Pohela Boishakh"},
            {"key": "ashura", "name_bn": "আশুরা", "name_en": "Ashura"},
            {"key": "saraswati_puja", "name_bn": "সরস্বতী পূজা", "name_en": "Saraswati Puja"},
        ],
        "planner_config": {
            "weekly_off_days": ["fri", "sat"],
            "class_band_limits": {
                "6-8": {
                    "min_daily_minutes": 0,
                    "max_daily_minutes": 600,
                    "recommended_daily_minutes": 90,
                    "max_block_minutes": 90,
                    "latest_end_time": "22:00",
                },
                "9-10": {
                    "min_daily_minutes": 0,
                    "max_daily_minutes": 600,
                    "recommended_daily_minutes": 150,
                    "max_block_minutes": 90,
                    "latest_end_time": "22:00",
                },
                "11-12": {
                    "min_daily_minutes": 0,
                    "max_daily_minutes": 600,
                    "recommended_daily_minutes": 210,
                    "max_block_minutes": 90,
                    "latest_end_time": "22:00",
                },
            },
            "default_parameters": {
                "study_share": 0.65,
                "revision_share": 0.25,
                "homework_quiz_share": 0.10,
                "max_consecutive_days_per_subject": 2,
                "min_subject_daily_share": 0.10,
            },
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


# -------------------------------------------------------------------------
# Study Settings (Planner v2 Dynamic Configuration Layer)
# -------------------------------------------------------------------------
@router.get(
    "/students/{student_id}/study-settings",
    response_model=StudentStudySettingsResponse,
    tags=["Planning"],
)
async def get_student_study_settings(student_id: uuid.UUID, request: Request) -> Response:
    """Get resolved study settings and admin limits for student."""
    return await forward_to_core(request)


@router.put(
    "/students/{student_id}/study-settings",
    response_model=StudentStudySettingsResponse,
    tags=["Planning"],
)
async def update_student_study_settings(
    student_id: uuid.UUID,
    payload: UpdateStudentStudySettingsRequest,
    request: Request,
) -> Response:
    """Parent updates student study settings."""
    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))


@router.post(
    "/students/{student_id}/study-settings/change-requests",
    response_model=StudentChangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Planning"],
)
async def submit_student_settings_change_request(
    student_id: uuid.UUID,
    payload: StudentChangeRequestInput,
    request: Request,
) -> Response:
    """Student submits proposed adjustments to their study settings."""
    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))


# -------------------------------------------------------------------------
# Quiz Engine (docs/04_API_CONTRACT.md §2, docs/05_SECURE_QUIZ.md)
# -------------------------------------------------------------------------
from core.quiz.schemas import (
    AllowAttemptRequest,
    AnswerItemRequest,
    AnswerItemResponse,
    AttemptEventRequest,
    AttemptEventResponse,
    AttemptReviewResponse,
    CreateAttemptRequest,
    CreateAttemptResponse,
    StartAttemptRequest,
    StartAttemptResponse,
    SubmitAttemptResponse,
)


def _get_authenticated_user_id(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
        try:
            claims = decode_access_jwt(token)
            return claims.get("sub")
        except Exception:
            return None
    return None


@router.api_route("/internal/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@router.api_route("/v1/internal/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def block_gateway_internal_routes(path: str) -> Response:
    """Public gateway strictly refuses to proxy internal routes."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": {"code": "NOT_FOUND", "message": "Resource not found."}},
    )


@router.post(
    "/students/{student_id}/quizzes",
    status_code=status.HTTP_201_CREATED,
    tags=["Quiz"],
)
async def create_student_quiz_gateway(student_id: uuid.UUID, request: Request) -> Response:
    """Create a new quiz session for student."""
    return await forward_to_core(request)


@router.post(
    "/quizzes/{quiz_id}/attempts/create",
    response_model=CreateAttemptResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Quiz"],
)
async def create_quiz_attempt_gateway(
    quiz_id: uuid.UUID,
    payload: CreateAttemptRequest,
    request: Request,
) -> Response:
    """Create a quiz attempt in 'created' state with short expiry for Play Integrity attestation."""
    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))


@router.post(
    "/quizzes/{quiz_id}/attempts",
    response_model=StartAttemptResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Quiz"],
)
async def start_quiz_attempt_gateway(
    quiz_id: uuid.UUID,
    payload: StartAttemptRequest,
    request: Request,
) -> Response:
    """Start a quiz attempt with dual user and IP rate limits."""
    client_ip = get_trusted_client_ip(request)
    device_id = payload.device_id or request.headers.get("X-Device-Id")
    user_id = _get_authenticated_user_id(request)

    # 1. User-level rate limit (5 requests / min per user)
    if user_id:
        user_rate_key = build_rate_limit_key("start_attempt_user", user_id)
        user_ok, user_retry = await RateLimiter.check_rate_limit(
            key=user_rate_key,
            max_requests=5,
            window_seconds=60,
        )
        if not user_ok:
            req_id = request_id_ctx.get() or ""
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(user_retry)},
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many quiz attempt requests for this user account. Please wait.",
                        "request_id": req_id,
                    }
                },
            )

    # 2. IP-level ceiling (25 requests / min per IP)
    ip_rate_key = build_rate_limit_key("start_attempt_ip", client_ip, device_id)
    ip_ok, ip_retry = await RateLimiter.check_rate_limit(
        key=ip_rate_key,
        max_requests=25,
        window_seconds=60,
    )
    if not ip_ok:
        req_id = request_id_ctx.get() or ""
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(ip_retry)},
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests from this IP network. Please wait.",
                    "request_id": req_id,
                }
            },
        )

    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))


@router.post(
    "/attempts/{attempt_id}/items/{position}/answer",
    response_model=AnswerItemResponse,
    tags=["Quiz"],
)
async def answer_quiz_item_gateway(
    attempt_id: uuid.UUID,
    position: int,
    payload: AnswerItemRequest,
    request: Request,
) -> Response:
    """Submit answer for sequential quiz item with dual user and IP rate limits."""
    client_ip = get_trusted_client_ip(request)
    user_id = _get_authenticated_user_id(request)

    # 1. User-level rate limit (20 answers / min per user)
    if user_id:
        user_rate_key = build_rate_limit_key("answer_item_user", user_id)
        user_ok, user_retry = await RateLimiter.check_rate_limit(
            key=user_rate_key,
            max_requests=20,
            window_seconds=60,
        )
        if not user_ok:
            req_id = request_id_ctx.get() or ""
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(user_retry)},
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many answer submissions for this user account. Please slow down.",
                        "request_id": req_id,
                    }
                },
            )

    # 2. IP-level ceiling (60 answers / min per IP)
    ip_rate_key = build_rate_limit_key("answer_item_ip", client_ip, str(attempt_id))
    ip_ok, ip_retry = await RateLimiter.check_rate_limit(
        key=ip_rate_key,
        max_requests=60,
        window_seconds=60,
    )
    if not ip_ok:
        req_id = request_id_ctx.get() or ""
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(ip_retry)},
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many answer submissions from this network. Please slow down.",
                    "request_id": req_id,
                }
            },
        )

    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))


@router.post(
    "/attempts/{attempt_id}/allow",
    tags=["Quiz"],
)
async def allow_quiz_attempt_gateway(
    attempt_id: uuid.UUID,
    payload: AllowAttemptRequest,
    request: Request,
) -> Response:
    """Parent or admin override to allow an attempt that was warned, paused, or invalidated."""
    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))


@router.post(
    "/attempts/{attempt_id}/events",
    response_model=AttemptEventResponse,
    tags=["Quiz"],
)
async def record_attempt_event_gateway(
    attempt_id: uuid.UUID,
    payload: AttemptEventRequest,
    request: Request,
) -> Response:
    """Record anti-cheat event from client."""
    return await forward_to_core(request, json_body=payload.model_dump(mode="json"))


@router.post(
    "/attempts/{attempt_id}/submit",
    response_model=SubmitAttemptResponse,
    tags=["Quiz"],
)
async def submit_quiz_attempt_gateway(
    attempt_id: uuid.UUID,
    request: Request,
) -> Response:
    """Finalize quiz attempt, calculate score, emit learning signals, and unlock review."""
    return await forward_to_core(request)


@router.get(
    "/attempts/{attempt_id}/review",
    response_model=AttemptReviewResponse,
    tags=["Quiz"],
)
async def review_quiz_attempt_gateway(
    attempt_id: uuid.UUID,
    request: Request,
) -> Response:
    """Review completed quiz attempt with explanations and answer keys."""
    return await forward_to_core(request)


# -------------------------------------------------------------------------
# Chat & In-App AI Tutor (docs/04_API_CONTRACT.md §2)
# -------------------------------------------------------------------------


@router.post(
    "/chat/sessions",
    status_code=status.HTTP_201_CREATED,
    tags=["Chat"],
)
async def create_chat_session_gateway(request: Request) -> Response:
    """Create chat session (enforces quiz in-progress lockout)."""
    return await forward_to_core(request)


@router.post(
    "/chat/sessions/{session_id}/messages",
    tags=["Chat"],
)
async def send_chat_message_gateway(session_id: uuid.UUID, request: Request) -> Response:
    """Send chat message (enforces quiz in-progress lockout)."""
    return await forward_to_core(request)


# -------------------------------------------------------------------------
# Admin Configuration & Governance
# -------------------------------------------------------------------------
@router.get("/admin/{path:path}", tags=["Admin"], operation_id="gateway_admin_get")
async def forward_admin_get(path: str, request: Request) -> Response:
    """Forward admin GET requests downstream to Core Service."""
    return await forward_to_core(request)


@router.post("/admin/{path:path}", tags=["Admin"], operation_id="gateway_admin_post")
async def forward_admin_post(path: str, request: Request) -> Response:
    """Forward admin POST requests downstream to Core Service."""
    return await forward_to_core(request)


@router.put("/admin/{path:path}", tags=["Admin"], operation_id="gateway_admin_put")
async def forward_admin_put(path: str, request: Request) -> Response:
    """Forward admin PUT requests downstream to Core Service."""
    return await forward_to_core(request)


@router.patch("/admin/{path:path}", tags=["Admin"], operation_id="gateway_admin_patch")
async def forward_admin_patch(path: str, request: Request) -> Response:
    """Forward admin PATCH requests downstream to Core Service."""
    return await forward_to_core(request)


@router.delete("/admin/{path:path}", tags=["Admin"], operation_id="gateway_admin_delete")
async def forward_admin_delete(path: str, request: Request) -> Response:
    """Forward admin DELETE requests downstream to Core Service."""
    return await forward_to_core(request)
