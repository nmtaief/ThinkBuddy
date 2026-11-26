"""Live Production Verification Script for ThinkBuddy Vercel + Backend."""

from __future__ import annotations

import argparse
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify live ThinkBuddy production deployment")
    parser.add_argument("--web-url", default="https://thinkbuddy-web.vercel.app")
    parser.add_argument("--backend-url", required=True)
    parser.add_argument("--service-token", default="")
    args = parser.parse_args()

    backend = args.backend_url.rstrip("/")
    web = args.web_url.rstrip("/")
    headers = {"ngrok-skip-browser-warning": "1"}
    if args.service_token:
        headers["X-Internal-Service-Token"] = args.service_token

    with httpx.Client(timeout=30.0) as client:
        # 1. Frontend live check
        fe = client.get(f"{web}/")
        fe.raise_for_status()
        print(f"1. Frontend {web}/: HTTP {fe.status_code}")

        # 2. GET /health/rag
        h = client.get(f"{backend}/health/rag", headers=headers)
        h.raise_for_status()
        h_json = h.json()
        print("2. /health/rag:", h_json)
        assert h_json["qdrant_connected"] is True
        assert h_json["qdrant_points_count"] >= 40910
        assert h_json["syllabus_chapters_count"] == 167
        assert len(h_json["configured_providers"]) >= 1

        # 3. Bilingual syllabus-scope & Rule 6/8 redaction
        for q in ("কোষ বিভাজন", "Cell Division"):
            r = client.post(
                f"{backend}/v1/rag-tools/syllabus-scope",
                json={"book_name": "", "subject": "science", "topic_query": q},
                headers=headers,
            )
            r.raise_for_status()
            assert r.json()["found"] is True, f"Syllabus scope missed '{q}'"

        bq = client.post(
            f"{backend}/v1/rag-tools/book-questions",
            json={"topic": "প্যাটার্ন", "count": 3},
            headers=headers,
        )
        bq.raise_for_status()
        for item in bq.json():
            assert "answer_key" not in item
            assert "pdf_page_index" not in item
        print("3. Bilingual syllabus-scope & Rule 6/8 redaction: PASSED")

        # 4. Live Voice BFF Proxy checks
        tr = client.post(f"{web}/api/voice/transcribe", json={})
        assert tr.status_code == 400, f"Expected 400 from /api/voice/transcribe, got {tr.status_code}: {tr.text}"

        sp = client.post(
            f"{web}/api/voice/speak",
            json={"text": "Hello, আমি ThinkBuddy!", "mood": "friendly", "language": "mixed"},
        )
        if sp.status_code == 200:
            ct = sp.headers.get("content-type", "")
            assert ct.startswith("audio/"), f"Expected audio/* content-type, got {ct}"
            assert len(sp.content) > 0, "Empty audio response from /api/voice/speak"
            print(f"4. Live Voice BFF (/api/voice/transcribe=400, /api/voice/speak=200 {ct}): PASSED")
        elif sp.status_code == 503:
            sp_json = sp.json()
            assert sp_json.get("fallback") == "browser_tts", f"Unexpected 503 body: {sp_json}"
            print("4. Live Voice BFF (/api/voice/transcribe=400, /api/voice/speak=503 browser_tts fallback): PASSED")
        else:
            raise AssertionError(f"Unexpected /api/voice/speak status {sp.status_code}: {sp.text}")

        # 5. Vercel SSE stream check
        with client.stream(
            "POST",
            f"{web}/api/chat/stream",
            json={"message": "প্যাটার্ন কী?", "class_override": 8, "provider": "gemini"},
        ) as sse:
            sse.raise_for_status()
            body_preview = ""
            for chunk in sse.iter_text():
                body_preview += chunk
                if "event: token" in body_preview or "event: status" in body_preview:
                    break
            assert len(body_preview) > 0, "Empty SSE stream from Vercel"
        print("5. Vercel /api/chat/stream SSE: PASSED")

    print("\n[PASSED] Live production deployment verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
