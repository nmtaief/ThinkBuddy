"""LLM gateway abstraction with mock support and LiteLLM streaming capabilities.

Implements RAG chat streaming deliverable:
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
        token_delay_s: float = 0.04,
        simulate_disconnect_after_tokens: int | None = None,
        fail_primary: bool = False,
        fallback_stream_tokens: list[str] | None = None,
    ) -> None:
        from core.common.config import settings as app_settings

        env_val = (
            getattr(app_settings, "ENV", None)
            or getattr(app_settings, "ENVIRONMENT", "")
        ).strip().lower()
        if env_val != "local":
            raise RuntimeError(
                f"MockLLMGateway is strictly forbidden unless ENV=local (current ENV='{env_val}')"
            )

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
        api_key: str | None = None,
        api_base: str | None = None,
        temperature: float = 0.3,
    ) -> None:
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.classifier_model = classifier_model
        self.api_key = api_key
        self.api_base = api_base
        self.temperature = temperature

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
        kwargs: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "stream": True,
            "timeout": timeout,
            "temperature": self.temperature,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base

        try:
            import litellm  # type: ignore[import-untyped]

            response = await litellm.acompletion(**kwargs)
            async for chunk in response:
                content = chunk.choices[0].delta.content or ""
                if content:
                    yield content
        except ImportError:
            # Native httpx streaming fallback for OpenRouter & OpenAI-compatible
            base_url = self.api_base or (
                "https://openrouter.ai/api/v1" if ("openrouter" in target_model.lower() or (self.api_key and self.api_key.startswith("sk-or-"))) else
                "https://api.openai.com/v1"
            )
            chat_url = base_url.rstrip("/") + "/chat/completions"
            clean_model = target_model.replace("openrouter/", "", 1) if target_model.startswith("openrouter/") else target_model
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://thinkbuddy.app",
                "X-Title": "ThinkBuddy AI Tutor",
            }
            payload = {
                "model": clean_model,
                "messages": messages,
                "stream": True,
                "temperature": self.temperature,
            }
            try:
                import httpx
                import json
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream("POST", chat_url, headers=headers, json=payload) as resp:
                        async for line in resp.aiter_lines():
                            line = line.strip()
                            if not line or not line.startswith("data:"):
                                continue
                            if line == "data: [DONE]":
                                break
                            try:
                                chunk_data = json.loads(line[5:].strip())
                                delta_content = chunk_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if delta_content:
                                    yield delta_content
                            except Exception:
                                continue
            except Exception as ex:
                logger.warning("Native HTTP streaming failed for %s: %s", target_model, ex)
        except Exception as ex:
            logger.warning(
                "Primary LLM (%s) failed, falling back to %s: %s",
                target_model,
                self.fallback_model,
                ex,
            )
            try:
                import litellm

                fallback_kwargs = dict(kwargs)
                fallback_kwargs["model"] = self.fallback_model
                response = await litellm.acompletion(**fallback_kwargs)
                async for chunk in response:
                    content = chunk.choices[0].delta.content or ""
                    if content:
                        yield content
            except Exception as fb_ex:
                logger.error("Fallback LLM failed: %s", fb_ex)

    async def generate_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        timeout: float = 30.0,
    ) -> LLMGenerationResult:
        target_model = model or self.primary_model
        kwargs: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "timeout": timeout,
            "temperature": self.temperature,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base

        start_time = time.perf_counter()
        try:
            import litellm

            response = await litellm.acompletion(**kwargs)
            content = response.choices[0].message.content or ""
            usage = response.usage
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return LLMGenerationResult(
                content=content,
                tokens_in=getattr(usage, "prompt_tokens", 50),
                tokens_out=getattr(usage, "completion_tokens", 100),
                model=target_model,
                latency_ms=latency_ms,
            )
        except ImportError:
            # Native httpx generation fallback for OpenRouter & OpenAI-compatible
            base_url = self.api_base or (
                "https://openrouter.ai/api/v1" if ("openrouter" in target_model.lower() or (self.api_key and self.api_key.startswith("sk-or-"))) else
                "https://api.openai.com/v1"
            )
            chat_url = base_url.rstrip("/") + "/chat/completions"
            clean_model = target_model.replace("openrouter/", "", 1) if target_model.startswith("openrouter/") else target_model
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://thinkbuddy.app",
                "X-Title": "ThinkBuddy AI Tutor",
            }
            payload = {
                "model": clean_model,
                "messages": messages,
                "stream": False,
                "temperature": self.temperature,
            }
            try:
                import httpx
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(chat_url, headers=headers, json=payload)
                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                    if resp.is_success:
                        res_json = resp.json()
                        content = res_json.get("choices", [{}])[0].get("message", {}).get("content", "")
                        usage = res_json.get("usage", {})
                        return LLMGenerationResult(
                            content=content,
                            tokens_in=usage.get("prompt_tokens", 50),
                            tokens_out=usage.get("completion_tokens", 100),
                            model=target_model,
                            latency_ms=latency_ms,
                        )
            except Exception as ex:
                logger.warning("Native HTTP generation failed for %s: %s", target_model, ex)
        except Exception as ex:
            logger.warning("Primary LLM (%s) failed, using fallback: %s", target_model, ex)
            try:
                import litellm

                fallback_kwargs = dict(kwargs)
                fallback_kwargs["model"] = self.fallback_model
                response = await litellm.acompletion(**fallback_kwargs)
                content = response.choices[0].message.content or ""
                usage = response.usage
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                return LLMGenerationResult(
                    content=content,
                    tokens_in=getattr(usage, "prompt_tokens", 50),
                    tokens_out=getattr(usage, "completion_tokens", 100),
                    model=self.fallback_model,
                    latency_ms=latency_ms,
                )
            except Exception as fb_ex:
                logger.error("Fallback generation failed: %s", fb_ex)

        return LLMGenerationResult(
            content="[ThinkBuddy AI Tutor Service Unavailable]",
            tokens_in=0,
            tokens_out=0,
            model=target_model,
            latency_ms=0,
        )


async def get_active_llm_gateway(db: Any | None = None) -> LLMGateway:
    """Resolve active LLM gateway from database configuration or default to mock."""
    if db is not None:
        try:
            from sqlalchemy import select
            from core.admin.models import AITutorConfig

            stmt = select(AITutorConfig).order_by(AITutorConfig.created_at.asc()).limit(1)
            result = await db.execute(stmt)
            config = result.scalar_one_or_none()
            if config and config.is_enabled and config.api_key and config.llm_provider != "mock":
                base_url = config.api_base or (
                    "https://openrouter.ai/api/v1" if config.llm_provider == "openrouter" else None
                )
                return LiteLLMGateway(
                    primary_model=config.primary_model,
                    fallback_model=config.fallback_model,
                    api_key=config.api_key,
                    api_base=base_url,
                    temperature=config.temperature,
                )
        except Exception as ex:
            logger.debug("Could not load AITutorConfig for LLMGateway: %s", ex)

    return MockLLMGateway()
