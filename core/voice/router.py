"""FastAPI routes for Hybrid Voice Interaction (/v1/voice/transcribe and /v1/voice/speak)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.common.config import settings
from core.voice.service import ALLOWED_AUDIO_MIMES, VoiceService, VoiceTTSUnavailableError

router = APIRouter(prefix="/voice", tags=["Voice"])

_default_voice_service: VoiceService | None = None


def get_voice_service() -> VoiceService:
    global _default_voice_service
    if _default_voice_service is None:
        _default_voice_service = VoiceService()
    return _default_voice_service


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    mood: Literal["friendly", "encouraging", "curious", "celebrating"] = "friendly"
    language: Literal["bn", "en", "mixed"] = "bn"


@router.post("/transcribe", summary="Transcribe student voice audio with NCTB vocabulary biasing")
async def transcribe_voice(
    audio: UploadFile = File(...),
    subject: str | None = Form(default=None),
    topic_hint: str | None = Form(default=None),
) -> dict[str, object]:
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


@router.post("/speak", summary="Synthesize Buddy mascot speech via Gemini TTS")
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
