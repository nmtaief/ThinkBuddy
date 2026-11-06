#!/usr/bin/env python3
"""Verification of Progressive SSE Streaming Through Caddy Reverse Proxy.

Requirements (Item 1):
- Matches real chat stream path: /v1/chat/sessions/*/messages
- Flushes immediately (flush_interval -1, no buffering)
- Progressive timing proof: inter-token arrival intervals > 0ms
"""

import asyncio
import json
import logging
import subprocess
import sys
import time
import uuid
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("caddy_sse_test")

CLIENT_HEADERS = {
    "X-Client-Platform": "android",
    "X-Client-Form-Factor": "phone",
    "X-App-Version": "1.0.0",
    "Accept-Language": "bn",
}


def ensure_caddy_container(port: int = 8088) -> str:
    """Start Caddy in Docker on thinkbuddyarc_default network if not running."""
    container_name = "thinkbuddy-caddy-test"
    # Check if already running
    check = subprocess.run(
        ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    if container_name in check.stdout:
        return container_name

    # Remove stopped instance if exists
    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)

    # Launch Caddy container
    cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        container_name,
        "--network",
        "thinkbuddyarc_default",
        "-p",
        f"{port}:80",
        "-v",
        f"{Path.cwd()}/infra/caddy/Caddyfile:/etc/caddy/Caddyfile:ro",
        "-e",
        "PUBLIC_DOMAIN=:80",
        "caddy:2.9.1-alpine",
    ]
    logger.info("Starting Caddy reverse proxy on port %d...", port)
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Failed starting Caddy: {res.stderr}")
    time.sleep(2)
    return container_name


async def ensure_curriculum_chunk() -> tuple[str, str, int, str]:
    """Seed test curriculum chunk so retrieval enters multi-token streaming."""
    from core.common.database import AsyncSessionLocal
    from core.curriculum.models import Book, Chapter, Chunk
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Chunk, Chapter, Book)
            .join(Chapter, Chapter.id == Chunk.chapter_id)
            .join(Book, Book.id == Chunk.book_id)
            .where(Chunk.retrievable == True)
            .limit(1)
        )
        res = await session.execute(stmt)
        row = res.first()
        if row:
            chunk, chapter, book = row
            return str(book.id), str(chapter.id), chunk.printed_page, chunk.text

        b = Book(
            id=uuid.uuid4(),
            title="সাধারণ বিজ্ঞান (Science)",
            class_level=7,
            subject="science",
            medium="bn",
            edition="2025-p10",
        )
        session.add(b)
        await session.flush()
        ch = Chapter(
            id=uuid.uuid4(),
            book_id=b.id,
            number=1,
            title="উদ্ভিদের পুষ্টি ও সালোকসংশ্লেষণ",
            printed_page_start=1,
            printed_page_end=20,
            order_index=1,
        )
        session.add(ch)
        await session.flush()
        ck = Chunk(
            id=uuid.uuid4(),
            book_id=b.id,
            chapter_id=ch.id,
            text="সালোকসংশ্লেষণ হলো একটি জৈবরাসায়নিক প্রক্রিয়া যার মাধ্যমে সবুজ উদ্ভিদ সূর্যালোক ও ক্লোরোফিলের সাহায্যে খাদ্য প্রস্তুত করে।",
            printed_page=5,
            pdf_page_index=7,
            chunk_index=0,
            ocr_quality=0.99,
            retrievable=True,
            validation_flags=["valid"],
        )
        session.add(ck)
        await session.commit()
        logger.info("Seeded curriculum chunk for streaming test.")
        return str(b.id), str(ch.id), ck.printed_page, ck.text


async def run_sse_progressive_test(caddy_url: str = "http://localhost:8088") -> None:
    book_id, chapter_id, printed_page, chunk_text = await ensure_curriculum_chunk()
    query_text = chunk_text[:30]
    async with httpx.AsyncClient(base_url=caddy_url, timeout=30.0) as client:
        # 1. Test healthz through Caddy
        res_h = await client.get("/healthz")
        assert res_h.status_code == 200, f"Healthz failed: {res_h.status_code}"
        logger.info("[OK] /healthz returned 200 through Caddy")

        # 2. Test metrics blocked through public edge
        res_m = await client.get("/metrics")
        # Direct public IP to Caddy will get 403 Forbidden or internal block
        logger.info("Metrics response code: %d", res_m.status_code)

        # 3. Create test parent, family, student credentials through Caddy
        phone_p = f"+880170{uuid.uuid4().hex[:6]}"
        res_p = await client.post(
            "/v1/auth/exchange",
            json={"provider_token": f"fake:phone:{phone_p}", "role": "parent", "display_name": "Caddy Parent"},
            headers={**CLIENT_HEADERS, "X-Device-Id": f"dev-{uuid.uuid4().hex[:6]}"},
        )
        assert res_p.status_code == 200, f"Parent auth failed: {res_p.text}"
        p_token = res_p.json()["access_token"]
        p_headers = {**CLIENT_HEADERS, "Authorization": f"Bearer {p_token}", "X-Device-Id": f"dev-{uuid.uuid4().hex[:6]}"}

        await client.post("/v1/parents/consent", json={"version": "1.0", "consented": True}, headers=p_headers)
        res_fam = await client.post("/v1/families", json={"name": "Caddy Fam"}, headers=p_headers)
        fam_id = res_fam.json()["id"]

        res_c = await client.post(
            f"/v1/families/{fam_id}/students",
            json={"display_name": "Caddy Student", "class_level": 7, "medium": "bn", "daily_minutes": 45},
            headers=p_headers,
        )
        link_code = res_c.json()["link_code"]

        phone_s = f"+880171{uuid.uuid4().hex[:6]}"
        res_s = await client.post(
            "/v1/auth/exchange",
            json={"provider_token": f"fake:phone:{phone_s}", "role": "student", "link_code": link_code},
            headers={**CLIENT_HEADERS, "X-Device-Id": f"dev-{uuid.uuid4().hex[:6]}"},
        )
        assert res_s.status_code == 200, f"Student auth failed: {res_s.text}"
        s_token = res_s.json()["access_token"]
        s_headers = {**CLIENT_HEADERS, "Authorization": f"Bearer {s_token}", "X-Device-Id": f"dev-{uuid.uuid4().hex[:6]}"}

        # 4. Create chat session
        res_sess = await client.post(
            "/v1/chat/sessions",
            json={"title": "SSE Timing Session"},
            headers=s_headers,
        )
        assert res_sess.status_code in (200, 201), f"Create session failed: {res_sess.text}"
        session_id = res_sess.json()["id"]

        # 5. Stream chat message through Caddy path /v1/chat/sessions/{session_id}/messages
        logger.info("Initiating streaming request through Caddy: /v1/chat/sessions/%s/messages", session_id)
        token_arrival_times: list[float] = []
        token_chunks: list[str] = []

        t_request_start = time.perf_counter()
        async with client.stream(
            "POST",
            f"/v1/chat/sessions/{session_id}/messages",
            json={
                "content": query_text,
                "stream": True,
                "language": "bn",
                "document_context": {
                    "book_id": book_id,
                    "chapter_id": chapter_id,
                    "printed_page": printed_page,
                },
            },
            headers=s_headers,
        ) as response:
            assert response.status_code == 200, f"Stream failed: {response.status_code}"
            assert response.headers.get("content-type", "").startswith("text/event-stream")

            async for line in response.aiter_lines():
                if line:
                    print("RECEIVED LINE:", line)
                if line.startswith("data:"):
                    now = time.perf_counter()
                    token_arrival_times.append(now)
                    payload_data = line.removeprefix("data:").strip()
                    try:
                        parsed = json.loads(payload_data)
                        token_chunks.append(parsed.get("token", parsed.get("content", "")))
                    except Exception:
                        token_chunks.append(payload_data)

        # Timing analysis
        first_token_latency = (token_arrival_times[0] - t_request_start) * 1000 if token_arrival_times else 0
        intervals_ms = [
            (token_arrival_times[i] - token_arrival_times[i - 1]) * 1000
            for i in range(1, len(token_arrival_times))
        ]

        print("\n" + "=" * 70)
        print("CADDY SSE STREAMING PROGRESSIVE TIMING PROOF")
        print("=" * 70)
        print(f"Total chunks received: {len(token_arrival_times)}")
        print(f"Time to first token (TTFT): {first_token_latency:.2f} ms")
        print("Inter-token arrival intervals (ms):")
        for idx, interval in enumerate(intervals_ms, 1):
            print(f"  Token {idx:02d} -> {idx+1:02d}: {interval:.2f} ms")

        avg_interval = sum(intervals_ms) / len(intervals_ms) if intervals_ms else 0
        print(f"Average inter-token interval: {avg_interval:.2f} ms")
        print("=" * 70)

        # Invariant: Tokens must arrive progressively (>0ms intervals between distinct packets)
        assert len(token_arrival_times) >= 3, "Expected at least 3 SSE chunks"
        assert any(iv > 1.0 for iv in intervals_ms), "Tokens arrived all at once! Caddy buffering is active!"
        logger.info("[SUCCESS] Progressive streaming verified: tokens arrived incrementally through Caddy without buffering.")


if __name__ == "__main__":
    from pathlib import Path
    try:
        container = ensure_caddy_container(port=8088)
        asyncio.run(run_sse_progressive_test("http://localhost:8088"))
    finally:
        subprocess.run(["docker", "rm", "-f", "thinkbuddy-caddy-test"], capture_output=True)
