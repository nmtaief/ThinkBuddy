"""FastAPI routes for Hybrid Voice Interaction (/v1/voice/transcribe and /v1/voice/speak)."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.common.config import settings
from core.voice.service import ALLOWED_AUDIO_MIMES, VoiceService, VoiceTTSUnavailableError

router = APIRouter(prefix="/voice", tags=["Voice"])

_default_voice_service: VoiceService | None = None
_minute_buckets: dict[str, list[float]] = defaultdict(list)
_day_buckets: dict[str, list[float]] = defaultdict(list)


def _require_internal_token(
    x_internal_service_token: str | None = Header(default=None),
) -> None:
    expected = settings.INTERNAL_SERVICE_TOKEN
    if expected and x_internal_service_token != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Invalid internal service token."},
        )


def _enforce_voice_rate_limit(x_user_id: str | None = Header(default="anonymous")) -> None:
    uid = x_user_id or "anonymous"
    now = time.time()
    per_min = int(os.getenv("VOICE_RATE_LIMIT_PER_MIN", "15"))
    per_day = int(os.getenv("VOICE_RATE_LIMIT_PER_DAY", "200"))

    min_hits = [t for t in _minute_buckets[uid] if now - t < 60.0]
    day_hits = [t for t in _day_buckets[uid] if now - t < 86400.0]
    if len(min_hits) >= per_min or len(day_hits) >= per_day:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "VOICE_RATE_LIMITED",
                "message": "ভয়েস ব্যবহারের সীমা শেষ হয়েছে। কিছুক্ষণ পর আবার চেষ্টা করুন।",
            },
        )
    min_hits.append(now)
    day_hits.append(now)
    _minute_buckets[uid] = min_hits
    _day_buckets[uid] = day_hits


def get_voice_service() -> VoiceService:
    global _default_voice_service
    if _default_voice_service is None:
        _default_voice_service = VoiceService()
    return _default_voice_service


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    mood: Literal["friendly", "encouraging", "curious", "celebrating"] = "friendly"
    language: Literal["bn", "en", "mixed"] = "bn"


@router.post(
    "/transcribe",
    summary="Transcribe student voice audio with NCTB vocabulary biasing",
    dependencies=[Depends(_require_internal_token), Depends(_enforce_voice_rate_limit)],
)
async def transcribe_voice(
    audio: UploadFile = File(...),
    subject: str | None = Form(default=None),
    topic_hint: str | None = Form(default=None),
    duration_seconds: float | None = Form(default=None),
) -> dict[str, object]:
    if duration_seconds is not None and duration_seconds > 60.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "AUDIO_TOO_LONG",
                "message": "অডিও ৬০ সেকেন্ডের বেশি হতে পারবে না।",
            },
        )
    raw_mime = (audio.content_type or "").split(";", 1)[0].strip().lower()
    if raw_mime not in ALLOWED_AUDIO_MIMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_AUDIO_MIME",
                "message": f"Unsupported audio MIME type: {raw_mime}",
            },
        )

    audio_bytes = await audio.read()
    if len(audio_bytes) > settings.VOICE_MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={"code": "AUDIO_TOO_LARGE", "message": "Audio exceeds 10 MB limit."},
        )
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMPTY_AUDIO", "message": "Uploaded audio file is empty."},
        )

    service = get_voice_service()
    return await service.transcribe_audio(
        audio_bytes=audio_bytes,
        mime_type=raw_mime,
        subject=subject,
        topic_hint=topic_hint,
    )


@router.post(
    "/speak",
    summary="Synthesize Buddy mascot speech via Gemini TTS",
    dependencies=[Depends(_require_internal_token), Depends(_enforce_voice_rate_limit)],
)
async def speak_voice(payload: SpeakRequest) -> Response:
    service = get_voice_service()
    try:
        audio_bytes, mime = await service.synthesize_speech(
            text=payload.text,
            mood=payload.mood,
            language=payload.language,
        )
        return Response(
            content=audio_bytes,
            media_type=mime,
            headers={"Cache-Control": "no-store"},
        )
    except VoiceTTSUnavailableError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"fallback": "browser_tts"},
        )
