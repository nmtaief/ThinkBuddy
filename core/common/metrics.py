"""Prometheus metrics collector and exporter for ThinkBuddy.

Deliverable 3:
Tracks:
- HTTP request duration (p50, p95, p99) and status codes.
- LLM token usage (prompt and completion tokens) and estimated cost in USD.
- AI chat quota exhaustions and latency.
- Active quiz attempts by mode (assessed vs practice).
- Background worker job execution metrics.
"""

from __future__ import annotations

import time
from typing import Callable
from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# 1. HTTP Metrics
HTTP_REQUESTS_TOTAL = Counter(
    "thinkbuddy_http_requests_total",
    "Total HTTP requests processed",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "thinkbuddy_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.4, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# 2. LLM & Tutoring Metrics
LLM_TOKENS_TOTAL = Counter(
    "thinkbuddy_llm_tokens_total",
    "Total tokens consumed by LLM operations",
    ["model", "token_type"],  # token_type: prompt | completion
)

LLM_COST_USD_TOTAL = Counter(
    "thinkbuddy_llm_cost_usd_total",
    "Total estimated LLM serving cost in USD",
    ["model"],
)

CHAT_FIRST_TOKEN_LATENCY_SECONDS = Histogram(
    "thinkbuddy_chat_first_token_latency_seconds",
    "Time to first streaming token in AI tutoring chat (Target < 2.5s p95)",
    ["model"],
    buckets=[0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0],
)

CHAT_QUOTA_EXHAUSTED_TOTAL = Counter(
    "thinkbuddy_chat_quota_exhausted_total",
    "Total number of daily AI tutoring quotas reached",
    ["class_band"],
)

# 3. Quiz & Assessment Metrics
QUIZ_ATTEMPTS_ACTIVE = Gauge(
    "thinkbuddy_quiz_attempts_active",
    "Number of currently active quiz attempts",
    ["mode"],  # mode: assessed | practice
)

QUIZ_INTEGRITY_FLAGS_TOTAL = Counter(
    "thinkbuddy_quiz_integrity_flags_total",
    "Total security anomalies or integrity flags logged during assessed quizzes",
    ["flag_type"],
)

# 4. Background Workers Metrics
CELERY_TASK_DURATION_SECONDS = Histogram(
    "thinkbuddy_celery_task_duration_seconds",
    "Celery background job duration in seconds",
    ["task_name", "status"],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)


async def metrics_middleware(request: Request, call_next: Callable) -> Response:
    """FastAPI middleware tracking HTTP request duration and status."""
    start_time = time.perf_counter()
    endpoint = request.url.path
    method = request.method

    try:
        response = await call_next(request)
        status_code = str(response.status_code)
    except Exception:
        status_code = "500"
        raise
    finally:
        duration = time.perf_counter() - start_time
        route = request.scope.get("route")
        if route and hasattr(route, "path"):
            normalized_path = route.path
        else:
            # Normalize variable UUIDs or numeric IDs in endpoint path to avoid metric cardinality explosion
            norm_parts = []
            for part in endpoint.split("/"):
                if len(part) in (32, 36) and ("-" in part or any(c.isdigit() for c in part)):
                    norm_parts.append(":id")
                elif part.isdigit():
                    norm_parts.append(":id")
                else:
                    norm_parts.append(part)
            normalized_path = "/".join(norm_parts) or "/"

        HTTP_REQUESTS_TOTAL.labels(
            method=method, endpoint=normalized_path, status_code=status_code
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=method, endpoint=normalized_path
        ).observe(duration)

    return response


def metrics_endpoint() -> Response:
    """Handler returning Prometheus-formatted text metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

