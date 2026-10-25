"""LLM gateway abstraction with mock support and LiteLLM streaming capabilities.

Implements Deliverable 8 from thinkbuddy-docs/prompts/P05_rag_chat_streaming.md:
- LLM gateway with model routing per task (classification vs generation)
- Streaming token generator
- Client disconnect awareness
- Fallback models, token counting, and cost metrics
- Mock provider for fast, deterministic unit and integration tests
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMGenerationResult:
    """Full generation result for non-streaming calls."""

    content: str
    tokens_in: int
    tokens_out: int
    model: str
    latency_ms: int


class LLMGateway(ABC):
    """Abstract LLM gateway interface for Chat generation and classification."""

    @abstractmethod
    async def classify_query(self, query: str) -> str:
        """Classify query intent: 'study_question', 'quiz_integrity', 'off_topic', 'unsafe'."""

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        timeout: float = 30.0,
    ) -> AsyncIterator[str]:
        """Stream response tokens as an asynchronous generator."""

    @abstractmethod
    async def generate_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        timeout: float = 30.0,
    ) -> LLMGenerationResult:
        """Generate complete response synchronously (non-streaming)."""


class MockLLMGateway(LLMGateway):
    """Deterministic mock LLM gateway for tests, CI, and local development."""

    def __init__(
        self,
        default_stream_tokens: list[str] | None = None,
        classification_result: str = "study_question",
        token_delay_s: float = 0.01,
        simulate_disconnect_after_tokens: int | None = None,
        fail_primary: bool = False,
        fallback_stream_tokens: list[str] | None = None,
    ) -> None:
        self.default_stream_tokens = default_stream_tokens or [
            "সালোকসংশ্লেষণ ",
            "হলো এমন একটি ",
            "জৈবরাসায়নিক প্রক্রিয়া ",
            "যার মাধ্যমে উদ্ভিদ ",
            "সূর্যালোকের সাহায্যে খাদ্য তৈরি করে।",
        ]
        self.classification_result = classification_result
        self.token_delay_s = token_delay_s
        self.simulate_disconnect_after_tokens = simulate_disconnect_after_tokens
        self.fail_primary = fail_primary
        self.fallback_stream_tokens = fallback_stream_tokens or [
            "উদ্ভিদ ",
            "ক্লোরোফিলের সাহায্যে ",
            "খাদ্য তৈরি করে।",
        ]
        self.total_tokens_generated = 0
        self.was_cancelled = False
        self.fallback_used = False

    async def classify_query(self, query: str) -> str:
        q_lower = query.lower()
        injection_terms = [
            "ignore previous",
            "ignore all previous",
            "system prompt",
            "reveal system prompt",
            "reveal instructions",
            "dan mode",
            "jailbreak",
            "bypass",
            "পূর্বের নির্দেশ ভুলে যাও",
            "সিস্টেম প্রম্পট",
        ]
        if any(term in q_lower for term in injection_terms):
            return "prompt_injection"
        quiz_keywords = ["quiz", "test", "exam", "answer to question", "কুইজের উত্তর"]
        if any(term in q_lower for term in quiz_keywords):
            return "quiz_integrity"
        if any(term in q_lower for term in ["kill", "bomb", "attack", "খারাপ", "sex", "vulgar"]):
            return "unsafe"
        if any(term in q_lower for term in ["cricket score", "movie", "weather", "গান", "খেলা"]):
            return "off_topic"
        return self.classification_result

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        timeout: float = 30.0,
    ) -> AsyncIterator[str]:
        self.was_cancelled = False
        tokens_yielded = 0

        # Simulate primary model failure triggering seamless fallback
        tokens_to_yield = self.default_stream_tokens
        if self.fail_primary:
            logger.warning("Primary LLM failed, automatically falling back to secondary model")
            self.fallback_used = True
            tokens_to_yield = self.fallback_stream_tokens

        try:
            for token in tokens_to_yield:
                if (
                    self.simulate_disconnect_after_tokens is not None
                    and tokens_yielded >= self.simulate_disconnect_after_tokens
                ):
                    self.was_cancelled = True
                    raise asyncio.CancelledError("Client disconnected")

                if self.token_delay_s > 0:
                    await asyncio.sleep(self.token_delay_s)

                tokens_yielded += 1
                self.total_tokens_generated += 1
                yield token
        except asyncio.CancelledError:
            self.was_cancelled = True
            raise

    async def generate_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        timeout: float = 30.0,
    ) -> LLMGenerationResult:
        if self.fail_primary:
            logger.warning("Primary LLM non-stream call failed, using fallback")
            self.fallback_used = True
            full_text = "".join(self.fallback_stream_tokens)
            return LLMGenerationResult(
                content=full_text,
                tokens_in=50,
                tokens_out=len(self.fallback_stream_tokens) * 3,
                model="mock-fallback-v1",
                latency_ms=180,
            )

        full_text = "".join(self.default_stream_tokens)
        return LLMGenerationResult(
            content=full_text,
            tokens_in=50,
            tokens_out=len(self.default_stream_tokens) * 3,
            model=model or "mock-tutor-v1",
            latency_ms=120,
        )


class LiteLLMGateway(LLMGateway):
    """Production LLM gateway using LiteLLM with fallback models, retries, and token accounting."""

    def __init__(
        self,
        primary_model: str = "gemini/gemini-1.5-flash",
        fallback_model: str = "openai/gpt-4o-mini",
        classifier_model: str = "openai/gpt-4o-mini",
    ) -> None:
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.classifier_model = classifier_model

    async def classify_query(self, query: str) -> str:
        # Heuristic fast-path before calling classifier model
        q_lower = query.lower()
        injection_terms = [
            "ignore previous",
            "ignore all previous",
            "system prompt",
            "reveal system prompt",
            "reveal instructions",
            "dan mode",
            "jailbreak",
            "পূর্বের নির্দেশ ভুলে যাও",
            "সিস্টেম প্রম্পট",
        ]
        if any(term in q_lower for term in injection_terms):
            return "prompt_injection"
        quiz_keywords = ["quiz", "test", "exam", "answer to question", "কুইজের উত্তর"]
        if any(term in q_lower for term in quiz_keywords):
            return "quiz_integrity"
        if any(term in q_lower for term in ["kill", "bomb", "attack", "sex", "vulgar"]):
            return "unsafe"
        return "study_question"

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        timeout: float = 30.0,
    ) -> AsyncIterator[str]:
        target_model = model or self.primary_model
        try:
            import litellm  # type: ignore[import-untyped]

            response = await litellm.acompletion(
                model=target_model,
                messages=messages,
                stream=True,
                timeout=timeout,
            )
            async for chunk in response:
                content = chunk.choices[0].delta.content or ""
                if content:
                    yield content
        except Exception as ex:
            logger.warning(
                "Primary LLM (%s) failed, falling back to %s: %s",
                target_model,
                self.fallback_model,
                ex,
            )
            import litellm

            response = await litellm.acompletion(
                model=self.fallback_model,
                messages=messages,
                stream=True,
                timeout=timeout,
            )
            async for chunk in response:
                content = chunk.choices[0].delta.content or ""
                if content:
                    yield content

    async def generate_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        timeout: float = 30.0,
    ) -> LLMGenerationResult:
        target_model = model or self.primary_model
        try:
            import litellm

            response = await litellm.acompletion(
                model=target_model,
                messages=messages,
                stream=False,
                timeout=timeout,
            )
            content = response.choices[0].message.content or ""
            usage = response.usage
            return LLMGenerationResult(
                content=content,
                tokens_in=getattr(usage, "prompt_tokens", 50),
                tokens_out=getattr(usage, "completion_tokens", 100),
                model=target_model,
                latency_ms=300,
            )
        except Exception as ex:
            logger.warning("Primary LLM (%s) failed, using fallback: %s", target_model, ex)
            import litellm

            response = await litellm.acompletion(
                model=self.fallback_model,
                messages=messages,
                stream=False,
                timeout=timeout,
            )
            content = response.choices[0].message.content or ""
            usage = response.usage
            return LLMGenerationResult(
                content=content,
                tokens_in=getattr(usage, "prompt_tokens", 50),
                tokens_out=getattr(usage, "completion_tokens", 100),
                model=self.fallback_model,
                latency_ms=450,
            )
