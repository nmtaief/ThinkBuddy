"""Deterministic Mock LLM Gateway for automated test suites only.

NEVER imported or instantiated in production code.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from core.chat.llm import LLMGenerationResult, LLMGateway
from core.common.config import settings


class MockLLMGateway(LLMGateway):
    """Deterministic mock LLM gateway for test suites and CI.
    
    Strictly forbidden in production environments.
    """

    def __init__(
        self,
        default_stream_tokens: list[str] | None = None,
        classification_result: str = "study_question",
        token_delay_s: float = 0.01,
        simulate_disconnect_after_tokens: int | None = None,
        fail_primary: bool = False,
        fallback_stream_tokens: list[str] | None = None,
    ) -> None:
        env = getattr(settings, "ENV", "").lower()
        environment = getattr(settings, "ENVIRONMENT", "").lower()
        if env != "local" and environment != "local":
            raise RuntimeError("MockLLMGateway is strictly forbidden unless ENV=local")

        self.default_stream_tokens = default_stream_tokens or [
            "উদ্ভিদ ",
            "সূর্যালোকের সাহায্যে ",
            "খাদ্য তৈরি করে।",
        ]
        self.classification_result = classification_result
        self.token_delay_s = token_delay_s
        self.simulate_disconnect_after_tokens = simulate_disconnect_after_tokens
        self.fail_primary = fail_primary
        self.fallback_stream_tokens = fallback_stream_tokens or [
            "বিকল্প ",
            "মডেলের ",
            "উত্তর।",
        ]
        self.total_tokens_generated = 0
        self.was_cancelled = False
        self.fallback_used = False

    async def classify_query(self, query: str) -> str:
        q_lower = query.lower().strip()
        if any(term in q_lower for term in ["ignore previous", "system prompt", "jailbreak"]):
            return "prompt_injection"
        if any(term in q_lower for term in ["quiz", "exam", "test"]):
            return "quiz_integrity"
        return self.classification_result

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        timeout: float = 30.0,
        tools: list[dict[str, Any]] | None = None,
        tool_executor: Any | None = None,
    ) -> AsyncIterator[str]:
        tokens = self.fallback_stream_tokens if self.fail_primary else self.default_stream_tokens
        if self.fail_primary:
            self.fallback_used = True

        for i, token in enumerate(tokens):
            if (
                self.simulate_disconnect_after_tokens is not None
                and i >= self.simulate_disconnect_after_tokens
            ):
                self.was_cancelled = True
                raise asyncio.CancelledError("Client disconnected")

            if self.token_delay_s > 0:
                await asyncio.sleep(self.token_delay_s)

            self.total_tokens_generated += 1
            yield token

    async def generate_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        timeout: float = 30.0,
        tools: list[dict[str, Any]] | None = None,
        tool_executor: Any | None = None,
    ) -> LLMGenerationResult:
        content = "".join(self.fallback_stream_tokens if self.fail_primary else self.default_stream_tokens)
        return LLMGenerationResult(
            content=content,
            tokens_in=10,
            tokens_out=len(content.split()),
            model="mock-test-gateway",
            latency_ms=10,
        )
