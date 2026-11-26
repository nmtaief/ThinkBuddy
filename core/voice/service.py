"""Voice Transcription (STT) & Mascot Speech Synthesis (TTS) Service."""

from __future__ import annotations

import functools
import logging
import re
import time
from typing import Any

from core.common.config import settings
from rag.bilingual_map import BN_TO_EN_CHAPTER_MAP
from rag.syllabus_index import get_syllabus_index_store

logger = logging.getLogger(__name__)

ALLOWED_AUDIO_MIMES = {"audio/webm", "audio/mp4", "audio/ogg", "audio/wav"}

MOOD_STYLE_MAP: dict[str, str] = {
    "friendly": "warm, friendly, conversational",
    "encouraging": "warm, encouraging, supportive",
    "curious": "curious, inquisitive, engaged",
    "celebrating": "cheerful, excited, celebrating",
}

FALLBACK_TRANSCRIBE_PROMPT = (
    "Transcribe exactly. Mixed Bangla and English is fine. "
    "Remove filler words like um/uh and fix math symbols and punctuation. "
    "Output only the cleaned transcript text."
)


class VoiceTTSUnavailableError(RuntimeError):
    """Raised when Gemini TTS cannot synthesize audio and browser TTS fallback should be used."""


@functools.lru_cache(maxsize=1)
def build_custom_vocabulary(limit: int = 100) -> tuple[str, ...]:
    """Build cached list of up to 100 high-value NCTB Bangla + English math/science terms."""
    terms: list[str] = [
        "কোষ বিভাজন",
        "মুনাফা",
        "পরিমাপ",
        "প্যাটার্ন",
        "বৃত্ত",
        "পিথাগোরাস",
        "sin 30",
        "cos theta",
        "Pythagoras",
        "photosynthesis",
    ]
    for bn_title, en_title in BN_TO_EN_CHAPTER_MAP.items():
        terms.append(bn_title)
        terms.append(en_title)
    try:
        s_store = get_syllabus_index_store()
        s_store.load()
        for entry in s_store.list_entries():
            for t in entry.topics:
                if t and len(t) <= 60:
                    terms.append(t)
    except Exception as exc:
        logger.debug("Skipping syllabus_index terms in custom_vocabulary: %s", exc)

    deduped = list(dict.fromkeys(t.strip() for t in terms if t and t.strip()))
    return tuple(deduped[:limit])


def prepare_text_for_speech(text: str, max_chars: int = 1200) -> str:
    """Strip Markdown/code fences and convert LaTeX into speakable phrasing."""
    if not text:
        return ""
    cleaned = re.sub(r"```[\s\S]*?```", " ", text)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\$\$|\$", " ", cleaned)
    cleaned = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"\1 by \2", cleaned)
    cleaned = re.sub(r"\\sqrt\{([^{}]+)\}", r"square root of \1", cleaned)
    cleaned = cleaned.replace("^2", " squared").replace("^3", " cubed")
    cleaned = cleaned.replace("\\pi", "pi").replace("\\rightarrow", "gives")
    cleaned = re.sub(r"\\[a-zA-Z]+", " ", cleaned)
    cleaned = re.sub(r"[*_#>~\[\]]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rsplit(" ", 1)[0] + "..."
    return cleaned


class VoiceService:
    """Handles Gemini STT transcription (with fallback) and Gemini TTS synthesis."""

    def __init__(self, gemini_client: Any | None = None) -> None:
        self._gemini_client = gemini_client

    def _get_client(self) -> Any:
        if self._gemini_client is not None:
            return self._gemini_client
        if not settings.GEMINI_API_KEY or not settings.GEMINI_API_KEY.strip():
            raise VoiceTTSUnavailableError("GEMINI_API_KEY is not configured.")
        from google import genai

        self._gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._gemini_client

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        mime_type: str,
        subject: str | None = None,
        topic_hint: str | None = None,
    ) -> dict[str, Any]:
        """Transcribe audio via gemini-3.5-transcribe (smart mode) with fallback to gemini-3.5-flash-lite."""
        from google.genai import types

        client = self._get_client()
        vocab = list(build_custom_vocabulary(100))
        if topic_hint:
            vocab = [topic_hint, *vocab[:99]]
        hint_str = f" Subject: {subject}." if subject else ""
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)

        t0 = time.perf_counter()
        # Primary: gemini-3.5-transcribe
        try:
            primary_prompt = (
                f"Transcribe in smart mode for Bangladeshi NCTB student.{hint_str} "
                f"Bias vocabulary: {', '.join(vocab[:30])}. Output only cleaned transcript text."
            )
            resp = await client.aio.models.generate_content(
                model=settings.GEMINI_TRANSCRIBE_MODEL,
                contents=[audio_part, primary_prompt],
            )
            transcript = (getattr(resp, "text", "") or "").strip()
            if transcript:
                return {
                    "transcript": transcript,
                    "model_used": settings.GEMINI_TRANSCRIBE_MODEL,
                    "latency_ms": int((time.perf_counter() - t0) * 1000),
                }
        except Exception as exc:
            logger.warning(
                "Primary transcribe model '%s' failed (%s); falling back to '%s'.",
                settings.GEMINI_TRANSCRIBE_MODEL,
                exc,
                settings.GEMINI_TRANSCRIBE_FALLBACK_MODEL,
            )

        # Fallback: gemini-3.5-flash-lite
        resp_fb = await client.aio.models.generate_content(
            model=settings.GEMINI_TRANSCRIBE_FALLBACK_MODEL,
            contents=[audio_part, f"{FALLBACK_TRANSCRIBE_PROMPT}{hint_str}"],
        )
        transcript_fb = (getattr(resp_fb, "text", "") or "").strip()
        return {
            "transcript": transcript_fb,
            "model_used": settings.GEMINI_TRANSCRIBE_FALLBACK_MODEL,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }

    async def synthesize_speech(
        self,
        text: str,
        mood: str = "friendly",
        language: str = "bn",
    ) -> tuple[bytes, str]:
        """Synthesize Buddy mascot speech via gemini-3.8-flash-lite-tts."""
        speak_text = prepare_text_for_speech(text)
        if not speak_text:
            raise VoiceTTSUnavailableError("Empty text after speech preparation.")

        try:
            from google.genai import types

            client = self._get_client()
            style_desc = MOOD_STYLE_MAP.get(mood, MOOD_STYLE_MAP["friendly"])
            config = types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=settings.GEMINI_TTS_VOICE
                        )
                    )
                ),
            )
            resp = await client.aio.models.generate_content(
                model=settings.GEMINI_TTS_MODEL,
                contents=speak_text,
                config=config,
            )
            candidates = getattr(resp, "candidates", None) or []
            for cand in candidates:
                content = getattr(cand, "content", None)
                parts = getattr(content, "parts", None) or []
                for part in parts:
                    inline = getattr(part, "inline_data", None)
                    if inline and getattr(inline, "data", None):
                        mime = getattr(inline, "mime_type", None) or "audio/wav"
                        return bytes(inline.data), mime
            raise VoiceTTSUnavailableError(f"No audio returned for style '{style_desc}'.")
        except VoiceTTSUnavailableError:
            raise
        except Exception as exc:
            logger.warning("Gemini TTS unavailable: %s", exc)
            raise VoiceTTSUnavailableError(str(exc)) from exc
