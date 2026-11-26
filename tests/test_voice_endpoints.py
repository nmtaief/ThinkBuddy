"""Tests for /v1/voice/transcribe and /v1/voice/speak."""

from __future__ import annotations

import types as py_types
from typing import Any

import httpx
import pytest

from core.common.config import settings
from core.main import app
from core.voice.service import VoiceService, prepare_text_for_speech


def test_prepare_text_for_speech_strips_markdown_and_latex() -> None:
    raw = "### সূত্র:\n$$\\frac{a}{b} + \\sqrt{x} = y^2$$\n```python\nprint(1)\n```"
    spoken = prepare_text_for_speech(raw)
    assert "```" not in spoken
    assert "$$" not in spoken
    assert "a by b" in spoken
    assert "square root of x" in spoken
    assert "squared" in spoken


@pytest.mark.asyncio
async def test_voice_transcribe_primary_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.voice.router as vr_mod

    # 1. Primary succeeds
    class FakePrimaryModels:
        async def generate_content(self, model: str, contents: Any) -> Any:
            return py_types.SimpleNamespace(text="কোষ বিভাজন কী?")

    primary_svc = VoiceService(
        gemini_client=py_types.SimpleNamespace(
            aio=py_types.SimpleNamespace(models=FakePrimaryModels())
        )
    )
    monkeypatch.setattr(vr_mod, "get_voice_service", lambda: primary_svc)
    headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        r1 = await client.post(
            "/v1/voice/transcribe",
            files={"audio": ("test.webm", b"fake-audio-bytes", "audio/webm")},
            data={"subject": "science"},
            headers=headers,
        )
        assert r1.status_code == 200
        assert r1.json()["transcript"] == "কোষ বিভাজন কী?"
        assert r1.json()["model_used"] == settings.GEMINI_TRANSCRIBE_MODEL

        # Invalid MIME rejected with 400
        r_bad = await client.post(
            "/v1/voice/transcribe",
            files={"audio": ("test.txt", b"hello", "text/plain")},
            headers=headers,
        )
        assert r_bad.status_code == 400

    # 2. Primary fails -> falls back to gemini-3.5-flash-lite
    class FakeFallbackModels:
        async def generate_content(self, model: str, contents: Any) -> Any:
            if model == settings.GEMINI_TRANSCRIBE_MODEL:
                raise RuntimeError("tier unavailable")
            return py_types.SimpleNamespace(text="Pythagoras theorem")

    fb_svc = VoiceService(
        gemini_client=py_types.SimpleNamespace(
            aio=py_types.SimpleNamespace(models=FakeFallbackModels())
        )
    )
    monkeypatch.setattr(vr_mod, "get_voice_service", lambda: fb_svc)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        r2 = await client.post(
            "/v1/voice/transcribe",
            files={"audio": ("test.webm", b"fake-audio-bytes", "audio/webm")},
            headers=headers,
        )
        assert r2.status_code == 200
        assert r2.json()["transcript"] == "Pythagoras theorem"
        assert r2.json()["model_used"] == settings.GEMINI_TRANSCRIBE_FALLBACK_MODEL


@pytest.mark.asyncio
async def test_voice_speak_tts_and_503_browser_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.voice.router as vr_mod

    class FakeTTSModels:
        async def generate_content(self, model: str, contents: Any, config: Any) -> Any:
            part = py_types.SimpleNamespace(
                inline_data=py_types.SimpleNamespace(data=b"RIFFWAVE", mime_type="audio/wav")
            )
            return py_types.SimpleNamespace(
                candidates=[
                    py_types.SimpleNamespace(content=py_types.SimpleNamespace(parts=[part]))
                ]
            )

    tts_svc = VoiceService(
        gemini_client=py_types.SimpleNamespace(aio=py_types.SimpleNamespace(models=FakeTTSModels()))
    )
    monkeypatch.setattr(vr_mod, "get_voice_service", lambda: tts_svc)
    headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        r_ok = await client.post(
            "/v1/voice/speak",
            json={"text": "শাবাশ!", "mood": "celebrating", "language": "bn"},
            headers=headers,
        )
        assert r_ok.status_code == 200
        assert r_ok.content == b"RIFFWAVE"

    # Missing API key -> 503 browser_tts fallback
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    monkeypatch.setattr(vr_mod, "get_voice_service", lambda: VoiceService())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        r_fb = await client.post(
            "/v1/voice/speak",
            json={"text": "Hello", "mood": "friendly", "language": "en"},
            headers=headers,
        )
        assert r_fb.status_code == 503
        assert r_fb.json()["fallback"] == "browser_tts"
