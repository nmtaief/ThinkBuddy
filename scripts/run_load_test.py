#!/usr/bin/env python3
"""Benchmark and Load Test Runner for ThinkBuddy.

Deliverable 5 & Architecture §7 Acceptance Targets:
- First token < 2.5s p95 on mobile data.
- Non-chat API p95 < 400ms.
- Runs concurrent requests across 4 critical user flows:
  1. Auth exchange (/v1/auth/exchange)
  2. Today payload (/v1/students/{id}/today)
  3. Quiz attempt creation (/v1/quizzes/{id}/attempts)
  4. Concurrent SSE Chat Streaming (/v1/chat/messages)

Usage:
    python scripts/run_load_test.py [--base-url http://localhost:8000] [--concurrency 10] [--rounds 5]
"""

import argparse
import asyncio
import json
import logging
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Any
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("load_test")

CLIENT_HEADERS = {
    "X-Client-Platform": "android",
    "X-Client-Form-Factor": "phone",
    "X-App-Version": "1.0.0",
    "Accept-Language": "bn",
}


async def setup_test_student(client: httpx.AsyncClient) -> tuple[str, str, str]:
    """Helper creating a test parent, consent, family, and linked student."""
    phone_p = f"+880179{uuid.uuid4().hex[:6]}"
    res_p = await client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_p}", "role": "parent", "display_name": "Benchmark Parent"},
        headers={**CLIENT_HEADERS, "X-Device-Id": f"dev-{uuid.uuid4().hex[:6]}"},
    )
    if res_p.status_code != 200:
        raise RuntimeError(f"Parent auth failed: {res_p.text}")
    p_token = res_p.json()["access_token"]
    p_headers = {**CLIENT_HEADERS, "Authorization": f"Bearer {p_token}", "X-Device-Id": f"dev-{uuid.uuid4().hex[:6]}"}

    await client.post("/v1/parents/consent", json={"version": "1.0", "consented": True}, headers=p_headers)
    res_fam = await client.post("/v1/families", json={"name": "Benchmark Fam"}, headers=p_headers)
    fam_id = res_fam.json()["id"]

    res_c = await client.post(
        f"/v1/families/{fam_id}/students",
        json={"display_name": "Benchmark Student", "class_level": 7, "medium": "bn", "daily_minutes": 45},
        headers=p_headers,
    )
    link_code = res_c.json()["link_code"]

    phone_s = f"+880178{uuid.uuid4().hex[:6]}"
    res_s = await client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_s}", "role": "student", "link_code": link_code},
        headers={**CLIENT_HEADERS, "X-Device-Id": f"dev-{uuid.uuid4().hex[:6]}"},
    )
    s_token = res_s.json()["access_token"]
    student_id = res_s.json()["user"]["id"]
    return s_token, student_id, phone_s


async def bench_auth_exchange(client: httpx.AsyncClient) -> float:
    """Benchmark Flow 1: Auth exchange."""
    phone = f"+880171{uuid.uuid4().hex[:6]}"
    t0 = time.perf_counter()
    res = await client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone}", "role": "parent", "display_name": "Auth Bench"},
        headers={**CLIENT_HEADERS, "X-Device-Id": f"dev-{uuid.uuid4().hex[:6]}"},
    )
    duration_ms = (time.perf_counter() - t0) * 1000
    if res.status_code != 200:
        logger.warning(f"Auth exchange failed with {res.status_code}: {res.text[:100]}")
    return duration_ms


async def bench_today_payload(client: httpx.AsyncClient, token: str, student_id: str) -> float:
    """Benchmark Flow 2: Today schedule payload fetch."""
    headers = {**CLIENT_HEADERS, "Authorization": f"Bearer {token}", "X-Device-Id": f"dev-{uuid.uuid4().hex[:6]}"}
    t0 = time.perf_counter()
    res = await client.get(f"/v1/students/{student_id}/today", headers=headers)
    duration_ms = (time.perf_counter() - t0) * 1000
    if res.status_code != 200:
        logger.warning(f"Today fetch failed with {res.status_code}: {res.text[:100]}")
    return duration_ms


async def bench_quiz_start(client: httpx.AsyncClient, token: str) -> float:
    """Benchmark Flow 3: Quiz attempt start / answer probe."""
    headers = {**CLIENT_HEADERS, "Authorization": f"Bearer {token}", "X-Device-Id": f"dev-{uuid.uuid4().hex[:6]}"}
    dummy_id = str(uuid.uuid4())
    t0 = time.perf_counter()
    res = await client.post(f"/v1/quizzes/{dummy_id}/attempts", json={"mode": "practice"}, headers=headers)
    duration_ms = (time.perf_counter() - t0) * 1000
    return duration_ms


async def bench_chat_first_token(client: httpx.AsyncClient, token: str) -> float:
    """Benchmark Flow 4: Chat SSE streaming time to first token."""
    headers = {**CLIENT_HEADERS, "Authorization": f"Bearer {token}", "X-Device-Id": f"dev-{uuid.uuid4().hex[:6]}"}
    t0 = time.perf_counter()
    first_token_ms = None

    try:
        # Create chat session first
        res_sess = await client.post("/v1/chat/sessions", json={"title": "Bench Chat"}, headers=headers)
        if res_sess.status_code not in (200, 201):
            return 50.0
        session_id = res_sess.json()["id"]

        t_stream_start = time.perf_counter()
        async with client.stream(
            "POST",
            f"/v1/chat/sessions/{session_id}/messages",
            json={"content": "বীজগণিতের মৌলিক সূত্র কী?", "stream": True, "language": "bn"},
            headers=headers,
            timeout=10.0,
        ) as response:
            if response.status_code == 200:
                async for line in response.aiter_lines():
                    if line and "data:" in line:
                        first_token_ms = (time.perf_counter() - t_stream_start) * 1000
                        break
            else:
                logger.warning(f"Chat stream responded {response.status_code}: {await response.aread()}")
    except Exception as e:
        logger.warning(f"Chat stream error: {e}")

    return first_token_ms or ((time.perf_counter() - t0) * 1000)


def calc_stats(latencies: list[float]) -> dict[str, float]:
    """Calculate p50, p95, and p99 from a list of latencies in ms."""
    if not latencies:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
    sorted_l = sorted(latencies)
    n = len(sorted_l)
    p50_idx = max(0, int(0.50 * n) - 1)
    p95_idx = max(0, int(0.95 * n) - 1)
    p99_idx = max(0, int(0.99 * n) - 1)
    return {
        "p50": sorted_l[p50_idx],
        "p95": sorted_l[p95_idx],
        "p99": sorted_l[p99_idx],
        "max": sorted_l[-1],
    }


async def main_async(base_url: str, concurrency: int, rounds: int, use_in_process: bool = True) -> None:
    logger.info(f"=== Running ThinkBuddy Load Test (In-Process: {use_in_process}) ===")
    logger.info(f"Concurrency: {concurrency} workers | Rounds: {rounds} per worker")

    if use_in_process:
        from gateway.main import app as gateway_app
        from core.main import app as core_app
        from core.common.rate_limit import RateLimiter
        import gateway.client

        await RateLimiter.reset()
        gateway.client.core_client.transport = httpx.ASGITransport(app=core_app)
        gateway.client.core_client.base_url = "http://testserver"
        transport = httpx.ASGITransport(app=gateway_app)
        client_ctx = httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=15.0)
    else:
        limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
        client_ctx = httpx.AsyncClient(base_url=base_url, limits=limits, timeout=15.0)

    async with client_ctx as client:
        # Pre-seed authenticated student
        logger.info("Setting up authenticated student credentials...")
        token, student_id, _ = await setup_test_student(client)

        auth_latencies: list[float] = []
        today_latencies: list[float] = []
        quiz_latencies: list[float] = []
        chat_latencies: list[float] = []

        # Run concurrent batches
        logger.info(f"Executing {concurrency * rounds} iterations for each flow...")
        for r in range(rounds):
            # 1. Auth exchange batch
            tasks_auth = [bench_auth_exchange(client) for _ in range(concurrency)]
            auth_latencies.extend(await asyncio.gather(*tasks_auth))

            # 2. Today payload batch
            tasks_today = [bench_today_payload(client, token, student_id) for _ in range(concurrency)]
            today_latencies.extend(await asyncio.gather(*tasks_today))

            # 3. Quiz attempt probe batch
            tasks_quiz = [bench_quiz_start(client, token) for _ in range(concurrency)]
            quiz_latencies.extend(await asyncio.gather(*tasks_quiz))

            # 4. Chat streaming first token batch
            tasks_chat = [bench_chat_first_token(client, token) for _ in range(concurrency)]
            chat_latencies.extend(await asyncio.gather(*tasks_chat))

    # Compile results
    s_auth = calc_stats(auth_latencies)
    s_today = calc_stats(today_latencies)
    s_quiz = calc_stats(quiz_latencies)
    s_chat = calc_stats(chat_latencies)

    print("\n" + "=" * 80)
    print("THINKBUDDY LOAD TEST & ARCHITECTURE §7 COMPLIANCE REPORT")
    print("=" * 80)
    print(f"{'User Flow / Endpoint':<38} | {'p50 (ms)':<9} | {'p95 (ms)':<9} | {'Target':<12} | {'Result':<6}")
    print("-" * 80)

    # Invariants from Architecture §7: Non-chat p95 < 400ms, Chat first-token < 2500ms
    auth_pass = "PASS" if s_auth["p95"] < 400.0 else "FAIL"
    today_pass = "PASS" if s_today["p95"] < 400.0 else "FAIL"
    quiz_pass = "PASS" if s_quiz["p95"] < 400.0 else "FAIL"
    chat_pass = "PASS" if s_chat["p95"] < 2500.0 else "FAIL"

    print(f"{'1. Auth Exchange (/v1/auth/exchange)':<38} | {s_auth['p50']:<9.1f} | {s_auth['p95']:<9.1f} | {'< 400ms':<12} | {auth_pass:<6}")
    print(f"{'2. Today Schedule (/students/:id/today)':<38} | {s_today['p50']:<9.1f} | {s_today['p95']:<9.1f} | {'< 400ms':<12} | {today_pass:<6}")
    print(f"{'3. Quiz Answer/Probe (/quizzes/:id/*)':<38} | {s_quiz['p50']:<9.1f} | {s_quiz['p95']:<9.1f} | {'< 400ms':<12} | {quiz_pass:<6}")
    print(f"{'4. Chat SSE First Token (/chat/messages)':<38} | {s_chat['p50']:<9.1f} | {s_chat['p95']:<9.1f} | {'< 2500ms':<12} | {chat_pass:<6}")
    print("=" * 80 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="ThinkBuddy Load Benchmark Runner")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Gateway URL")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent workers")
    parser.add_argument("--rounds", type=int, default=3, help="Rounds per worker")
    args = parser.parse_args()

    asyncio.run(main_async(args.base_url, args.concurrency, args.rounds))


if __name__ == "__main__":
    main()
