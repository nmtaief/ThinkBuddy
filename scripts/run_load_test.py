#!/usr/bin/env python3
"""Realistic High-Concurrency Load and Saturation Benchmark for ThinkBuddy.

Deliverable 5 & Acceptance Criteria (Item 2):
- Rerun against real PostgreSQL database with realistic seed data.
- Model stub with realistic latency and token pacing (TTFT ~200-400ms, ~40ms token intervals).
- 100+ concurrent chat streams and real quiz answer submissions (/v1/attempts/{aid}/items/{pos}/answer).
- Tracks and reports: user counts, duration, error rates, resource utilization (CPU & Memory), and the saturation point.
"""

import argparse
import asyncio
import json
import logging
import os
import statistics
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("load_test")

CLIENT_HEADERS = {
    "X-Client-Platform": "android",
    "X-Client-Form-Factor": "phone",
    "X-App-Version": "1.0.0",
    "Accept-Language": "bn",
}


@dataclass
class FlowStats:
    flow_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    error_rate_pct: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    target_p95_ms: float
    passed: bool


async def seed_curriculum_and_questions() -> tuple[str, str, int, str, str]:
    """Ensure authentic curriculum, chunks, questions, and active quiz exist in DB."""
    from core.common.database import AsyncSessionLocal
    from core.curriculum.models import Book, Chapter, Chunk
    from core.quiz.models import Question, QuestionKey
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        # 1. Fetch or create Book & Chapter
        stmt_b = select(Book).where(Book.class_level == 7, Book.subject == "science")
        b = (await session.execute(stmt_b)).scalars().first()
        if not b:
            b = Book(
                id=uuid.uuid4(),
                title="সাধারণ বিজ্ঞান (Science)",
                class_level=7,
                subject="science",
                medium="bn",
                edition="2025-bench",
            )
            session.add(b)
            await session.flush()

        stmt_ch = select(Chapter).where(Chapter.book_id == b.id)
        ch = (await session.execute(stmt_ch)).scalars().first()
        if not ch:
            ch = Chapter(
                id=uuid.uuid4(),
                book_id=b.id,
                number=1,
                title="উদ্ভিদের পুষ্টি ও সালোকসংশ্লেষণ",
                printed_page_start=1,
                printed_page_end=30,
                order_index=1,
            )
            session.add(ch)
            await session.flush()

        # 2. Chunk
        stmt_ck = select(Chunk).where(Chunk.chapter_id == ch.id)
        ck = (await session.execute(stmt_ck)).scalars().first()
        if not ck:
            ck = Chunk(
                id=uuid.uuid4(),
                book_id=b.id,
                chapter_id=ch.id,
                text="সালোকসংশ্লেষণ হলো একটি জৈবরাসায়নিক প্রক্রিয়া যার মাধ্যমে সবুজ উদ্ভিদ সূর্যালোক ও ক্লোরোফিলের সাহায্যে শর্করা তৈরি করে।",
                printed_page=12,
                pdf_page_index=15,
                chunk_index=0,
                ocr_quality=0.99,
                retrievable=True,
                validation_flags=["valid"],
            )
            session.add(ck)
            await session.flush()

        # 3. Question & Options
        stmt_q = select(Question).where(Question.chapter_id == ch.id)
        q = (await session.execute(stmt_q)).scalars().first()
        if not q:
            opt1_id = f"opt_{uuid.uuid4().hex[:6]}"
            opt2_id = f"opt_{uuid.uuid4().hex[:6]}"
            opt3_id = f"opt_{uuid.uuid4().hex[:6]}"
            q = Question(
                id=uuid.uuid4(),
                chapter_id=ch.id,
                type="mcq",
                difficulty=0.5,
                language="bn",
                stem={"text": "সালোকসংশ্লেষণের প্রধান উপাদান কোনটি?"},
                options=[
                    {"id": opt1_id, "text": "সূর্যালোক"},
                    {"id": opt2_id, "text": "নাইট্রোজেন"},
                    {"id": opt3_id, "text": "লবণ"},
                ],
                review_status="approved",
                pool="both",
                source_chunk_ids=[str(ck.id)],
            )
            session.add(q)
            await session.flush()

            q_key = QuestionKey(
                id=uuid.uuid4(),
                question_id=q.id,
                correct_option_id=opt1_id,
            )
            session.add(q_key)
            await session.flush()

        await session.commit()
        return str(b.id), str(ch.id), ck.printed_page, ck.text, str(q.id)


async def setup_bench_user(client: httpx.AsyncClient, idx: int) -> tuple[str, str, dict[str, str]]:
    """Helper creating a test parent, consent, family, and linked student."""
    phone_p = f"+880175{idx:06d}"
    dev_id = f"dev-bench-{idx:04d}"
    sim_ip = f"198.51.100.{(idx % 250) + 1}"
    headers_base = {**CLIENT_HEADERS, "X-Device-Id": dev_id, "X-Forwarded-For": sim_ip}

    res_p = await client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_p}", "role": "parent", "display_name": f"Parent {idx}"},
        headers=headers_base,
    )
    if res_p.status_code != 200:
        raise RuntimeError(f"Parent auth failed: {res_p.text}")
    p_token = res_p.json()["access_token"]
    p_headers = {**headers_base, "Authorization": f"Bearer {p_token}"}

    await client.post("/v1/parents/consent", json={"version": "1.0", "consented": True}, headers=p_headers)
    res_fam = await client.post("/v1/families", json={"name": f"Family {idx}"}, headers=p_headers)
    fam_id = res_fam.json()["id"]

    res_c = await client.post(
        f"/v1/families/{fam_id}/students",
        json={"display_name": f"Student {idx}", "class_level": 7, "medium": "bn", "daily_minutes": 45},
        headers=p_headers,
    )
    link_code = res_c.json()["link_code"]

    phone_s = f"+880176{idx:06d}"
    res_s = await client.post(
        "/v1/auth/exchange",
        json={"provider_token": f"fake:phone:{phone_s}", "role": "student", "link_code": link_code},
        headers=headers_base,
    )
    if res_s.status_code != 200:
        raise RuntimeError(f"Student auth failed: {res_s.text}")
    s_token = res_s.json()["access_token"]
    student_id = res_s.json()["user"]["id"]
    s_headers = {**headers_base, "Authorization": f"Bearer {s_token}"}
    return s_token, student_id, s_headers


async def bench_auth_exchange(client: httpx.AsyncClient, idx: int) -> tuple[float, bool]:
    phone = f"+880177{idx:06d}"
    sim_ip = f"198.51.101.{(idx % 250) + 1}"
    t0 = time.perf_counter()
    try:
        res = await client.post(
            "/v1/auth/exchange",
            json={"provider_token": f"fake:phone:{phone}", "role": "parent", "display_name": f"Auth User {idx}"},
            headers={**CLIENT_HEADERS, "X-Device-Id": f"dev-auth-{idx:04d}", "X-Forwarded-For": sim_ip},
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        return duration_ms, res.status_code == 200
    except Exception:
        return (time.perf_counter() - t0) * 1000, False


async def bench_today_payload(client: httpx.AsyncClient, student_id: str, headers: dict[str, str]) -> tuple[float, bool]:
    t0 = time.perf_counter()
    try:
        res = await client.get(f"/v1/students/{student_id}/today", headers=headers)
        duration_ms = (time.perf_counter() - t0) * 1000
        return duration_ms, res.status_code == 200
    except Exception:
        return (time.perf_counter() - t0) * 1000, False


async def bench_real_quiz_answer(
    client: httpx.AsyncClient,
    student_id: str,
    headers: dict[str, str],
    chapter_id: str,
) -> tuple[float, bool]:
    """Flow 3: Real quiz start and item answer submission (/v1/attempts/{aid}/items/{pos}/answer)."""
    t0 = time.perf_counter()
    try:
        # 1. Create or get student quiz
        res_q = await client.post(
            f"/v1/students/{student_id}/quizzes",
            json={"chapter_ids": [chapter_id], "mode": "practice", "question_count": 3},
            headers=headers,
        )
        if res_q.status_code not in (200, 201):
            return (time.perf_counter() - t0) * 1000, False
        quiz_id = res_q.json()["id"]

        # 2. Start attempt
        res_att = await client.post(
            f"/v1/quizzes/{quiz_id}/attempts",
            json={"mode": "practice"},
            headers=headers,
        )
        if res_att.status_code not in (200, 201):
            return (time.perf_counter() - t0) * 1000, False
        att_data = res_att.json()
        attempt_id = att_data["attempt_id"]
        attempt_token = att_data["attempt_token"]
        current_item = att_data["current_item"]

        # 3. Submit real answer to position 1
        item_headers = {**headers, "X-Attempt-Token": attempt_token}
        selected_opt = current_item["question"]["options"][0]["id"]
        res_ans = await client.post(
            f"/v1/attempts/{attempt_id}/items/{current_item['position']}/answer",
            json={
                "nonce": current_item["nonce"],
                "response": {"selected_option_id": selected_opt},
                "time_spent_ms": 12000,
            },
            headers=item_headers,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        return duration_ms, res_ans.status_code == 200
    except Exception:
        return (time.perf_counter() - t0) * 1000, False


async def bench_chat_streaming(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    book_id: str,
    chapter_id: str,
    printed_page: int,
    query_text: str,
) -> tuple[float, bool]:
    """Flow 4: Concurrent SSE Chat Streaming with realistic token arrival pacing."""
    t0 = time.perf_counter()
    first_token_ms: float | None = None
    success = False

    try:
        # Create session
        res_sess = await client.post("/v1/chat/sessions", json={"title": "Load Session"}, headers=headers)
        if res_sess.status_code not in (200, 201):
            return (time.perf_counter() - t0) * 1000, False
        session_id = res_sess.json()["id"]

        t_stream = time.perf_counter()
        async with client.stream(
            "POST",
            f"/v1/chat/sessions/{session_id}/messages",
            json={
                "content": query_text[:30],
                "stream": True,
                "language": "bn",
                "document_context": {
                    "book_id": book_id,
                    "chapter_id": chapter_id,
                    "printed_page": printed_page,
                },
            },
            headers=headers,
            timeout=15.0,
        ) as response:
            if response.status_code == 200:
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        if first_token_ms is None:
                            first_token_ms = (time.perf_counter() - t_stream) * 1000
                        if "done" in line or "latency_ms" in line:
                            success = True
                            break
    except Exception:
        success = False

    elapsed = first_token_ms if first_token_ms is not None else ((time.perf_counter() - t0) * 1000)
    return elapsed, (success and first_token_ms is not None)


def compute_flow_stats(name: str, results: list[tuple[float, bool]], target_p95: float) -> FlowStats:
    total = len(results)
    if total == 0:
        return FlowStats(name, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, target_p95, True)
    successful = sum(1 for _, ok in results if ok)
    failed = total - successful
    error_rate = (failed / total) * 100.0

    latencies = sorted([d for d, _ in results])
    n = len(latencies)
    p50 = latencies[max(0, int(0.50 * n) - 1)]
    p95 = latencies[max(0, int(0.95 * n) - 1)]
    p99 = latencies[max(0, int(0.99 * n) - 1)]
    max_lat = latencies[-1]

    passed = (p95 <= target_p95) and (error_rate == 0.0)
    return FlowStats(name, total, successful, failed, error_rate, p50, p95, p99, max_lat, target_p95, passed)


async def execute_concurrency_tier(
    concurrency: int,
    base_url: str,
    use_in_process: bool,
    book_id: str,
    chapter_id: str,
    printed_page: int,
    query_text: str,
) -> tuple[dict[str, FlowStats], float, float, float]:
    """Execute load test at specified concurrency level and monitor CPU/RAM."""
    from core.common.rate_limit import RateLimiter

    await RateLimiter.reset()

    if use_in_process:
        from core.main import app as core_app
        from gateway.main import app as gateway_app
        import gateway.client

        gateway.client.core_client.transport = httpx.ASGITransport(app=core_app)
        gateway.client.core_client.base_url = "http://testserver"
        transport = httpx.ASGITransport(app=gateway_app)
        client = httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=30.0)
    else:
        limits = httpx.Limits(max_keepalive_connections=concurrency * 2, max_connections=concurrency * 2)
        client = httpx.AsyncClient(base_url=base_url, limits=limits, timeout=30.0)

    async with client:
        # Pre-seed authenticated students
        logger.info(f"Setting up {concurrency} test student accounts...")
        user_tasks = [setup_bench_user(client, i) for i in range(concurrency)]
        users = await asyncio.gather(*user_tasks)

        # Baseline system metrics
        psutil.cpu_percent(interval=None)
        mem_before = psutil.virtual_memory().percent

        t_start = time.perf_counter()

        # Run concurrent batches across all 4 flows simultaneously
        logger.info(f"Dispatching {concurrency} concurrent requests per flow ({concurrency * 4} total requests)...")

        tasks_auth = [bench_auth_exchange(client, 1000 + i) for i in range(concurrency)]
        tasks_today = [bench_today_payload(client, users[i][1], users[i][2]) for i in range(concurrency)]
        tasks_quiz = [bench_real_quiz_answer(client, users[i][1], users[i][2], chapter_id) for i in range(concurrency)]
        tasks_chat = [
            bench_chat_streaming(client, users[i][2], book_id, chapter_id, printed_page, query_text)
            for i in range(concurrency)
        ]

        # Execute simultaneously
        r_auth, r_today, r_quiz, r_chat = await asyncio.gather(
            asyncio.gather(*tasks_auth),
            asyncio.gather(*tasks_today),
            asyncio.gather(*tasks_quiz),
            asyncio.gather(*tasks_chat),
        )

        test_duration = time.perf_counter() - t_start
        cpu_usage = psutil.cpu_percent(interval=None)
        mem_usage = psutil.virtual_memory().percent

        stats_map = {
            "auth": compute_flow_stats("Auth Exchange (/v1/auth/exchange)", r_auth, 400.0),
            "today": compute_flow_stats("Today Schedule (/students/:id/today)", r_today, 400.0),
            "quiz": compute_flow_stats("Real Quiz Item Answer (/attempts/:id/items/:pos/answer)", r_quiz, 400.0),
            "chat": compute_flow_stats("Chat SSE Streaming First Token (/chat/sessions/:id/messages)", r_chat, 2500.0),
        }
        return stats_map, test_duration, cpu_usage, mem_usage


async def main_async(concurrency_target: int = 100, base_url: str = "http://localhost:8000") -> None:
    logger.info("================================================================================")
    logger.info("THINKBUDDY COMPREHENSIVE LOAD & SATURATION BENCHMARK (REAL DB + PACING)")
    logger.info("================================================================================")
    logger.info(f"Target Concurrency: {concurrency_target}+ concurrent workers")

    # Seed DB
    logger.info("Seeding realistic NCTB curriculum and questions in PostgreSQL...")
    book_id, chapter_id, printed_page, chunk_text, q_id = await seed_curriculum_and_questions()

    tiers = [25, 50, 100]
    if concurrency_target > 100:
        tiers.append(concurrency_target)

    results_by_tier: dict[int, Any] = {}
    saturation_point = "Beyond 100 concurrent workers"

    for c in tiers:
        logger.info(f"\n--- Testing Concurrency Tier: {c} Concurrent Users ---")
        stats_map, duration, cpu, mem = await execute_concurrency_tier(
            concurrency=c,
            base_url=base_url,
            use_in_process=True,
            book_id=book_id,
            chapter_id=chapter_id,
            printed_page=printed_page,
            query_text=chunk_text,
        )

        tier_passed = all(s.passed for s in stats_map.values())
        results_by_tier[c] = {
            "concurrency": c,
            "duration_s": round(duration, 2),
            "cpu_percent": cpu,
            "memory_percent": mem,
            "tier_passed": tier_passed,
            "flows": {k: asdict(v) for k, v in stats_map.items()},
        }

        print("\n" + "=" * 90)
        print(f"TIER {c} CONCURRENT WORKERS (Duration: {duration:.2f}s | CPU: {cpu:.1f}% | Memory: {mem:.1f}%)")
        print("=" * 90)
        print(f"{'User Flow / Endpoint':<45} | {'p50(ms)':<8} | {'p95(ms)':<8} | {'Target':<9} | {'Err%':<5} | {'Status'}")
        print("-" * 90)
        for s in stats_map.values():
            status = "PASS" if s.passed else "FAIL"
            print(f"{s.flow_name:<45} | {s.p50_ms:<8.1f} | {s.p95_ms:<8.1f} | <{s.target_p95_ms:<7.0f} | {s.error_rate_pct:<5.1f} | {status}")
        print("=" * 90)

        if not tier_passed and saturation_point == "Beyond 100 concurrent workers":
            saturation_point = f"{c} concurrent workers (latency or errors degraded)"

    # Save artifact
    out_dir = Path("reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / "load_test_results.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": time.time(),
                "saturation_point": saturation_point,
                "tiers": results_by_tier,
            },
            f,
            indent=2,
        )
    logger.info(f"Detailed benchmark metrics written to {report_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ThinkBuddy Load Benchmark")
    parser.add_argument("--concurrency", type=int, default=100, help="Target concurrency")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Gateway URL")
    args = parser.parse_args()

    asyncio.run(main_async(args.concurrency, args.base_url))


if __name__ == "__main__":
    main()
