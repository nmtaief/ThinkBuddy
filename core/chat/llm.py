"""LLM gateway implementation connecting to OpenRouter.ai API with streaming and tool calling.

Implements ThinkBuddy AI Tutor requirements:
- Single direct OpenRouter async HTTP gateway (OpenRouterGateway)
- Multi-turn tool calling with search_textbook, get_chapter_list, get_page, get_concepts
- Streaming SSE support with client-disconnect cancellation
- Privacy & data protection: provider {"data_collection": "deny"} for paid models
- Real model, provider, token accounting, and latency metrics persisted
- Fallback chain: primary model -> verified fallback model -> Bangla error message
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class LLMGenerationResult:
    """Full generation result for non-streaming calls."""

    content: str
    tokens_in: int
    tokens_out: int
    model: str
    latency_ms: int
    provider: str | None = None


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
        tools: list[dict[str, Any]] | None = None,
        tool_executor: Any | None = None,
    ) -> AsyncIterator[str]:
        """Stream response tokens as an asynchronous generator."""

    @abstractmethod
    async def generate_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        timeout: float = 30.0,
        tools: list[dict[str, Any]] | None = None,
        tool_executor: Any | None = None,
    ) -> LLMGenerationResult:
        """Generate complete response synchronously (non-streaming)."""


ERROR_MESSAGE_BANGLA = "একটু সমস্যা হয়েছে, আবার চেষ্টা করো"


class OpenRouterGateway(LLMGateway):
    """Unified OpenRouter LLM gateway with streaming, tool calling, and token accounting."""

    def __init__(
        self,
        primary_model: str = "openai/gpt-4o-mini",
        fallback_model: str = "google/gemini-2.5-flash",
        classifier_model: str = "openai/gpt-4o-mini",
        api_key: str | None = None,
        api_base: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 1200,
    ) -> None:
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.classifier_model = classifier_model
        self.api_key = api_key
        self.api_base = (api_base or "https://openrouter.ai/api/v1").rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Metrics for the last completed turn
        self.last_provider: str | None = None
        self.last_model_used: str | None = None
        self.last_tokens_in: int = 0
        self.last_tokens_out: int = 0
        self.last_latency_ms: int = 0

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": "https://thinkbuddy.app",
            "X-Title": "ThinkBuddy AI Tutor",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def classify_query(self, query: str) -> str:
        q_lower = query.lower().strip()
        clean_q = "".join(c for c in q_lower if c.isalnum() or c.isspace()).strip()

        # Check prompt injection, jailbreaks, and adversarial attacks
        injection_terms = [
            "ignore previous",
            "ignore all previous",
            "system prompt",
            "reveal system prompt",
            "reveal instructions",
            "dan mode",
            "developer mode",
            "simulate developer",
            "jailbreak",
            "system override",
            "unconstrained terminal",
            "roleplay game",
            "no rules",
            "emergency authorization",
            "system instructions",
            "internal instructions",
            "base64",
            "drop table",
            "select * from",
            "do not reveal your",
            "never reveal your",
            "ignorez les instructions",
            "vergiss alle vorherigen",
            "забудь все предыдущие",
            "পূর্বের নির্দেশ",
            "পূর্বের সকল নিয়ম",
            "পূর্বের নিয়ম",
            "সিস্টেম প্রম্পট",
            "অভ্যন্তরীণ নির্দেশনা",
        ]
        if any(term in q_lower for term in injection_terms):
            return "prompt_injection"

        # Check full textbook scraping / bulk dump requests
        if any(
            term in q_lower
            for term in [
                "dump the entire",
                "dump the whole",
                "word for word from start to finish",
                "সবগুলো পাতা একসাথে",
            ]
        ):
            return "off_topic"

        quiz_keywords = [
            "quiz",
            "test",
            "exam",
            "answer to question",
            "কুইজের উত্তর",
            "পরীক্ষার উত্তর",
            "answer key",
            "exam choltese",
            "shob answer key",
            "mcq er answer",
            "direct mcq answer",
        ]
        if any(term in q_lower for term in quiz_keywords):
            return "quiz_integrity"

        if any(term in q_lower for term in ["kill", "bomb", "attack", "sex", "vulgar"]):
            return "unsafe"

        # Check study guidance questions BEFORE general study topic checks
        guidance_triggers = [
            "what should i study",
            "what to study",
            "where should i start",
            "where to start",
            "help me study",
            "make a study plan",
            "study plan",
            "suggest a topic",
            "suggest what to study",
            "what can i study",
            "how should i prepare",
            "routine",
            "timetable",
            "how can i improve",
            "how to improve",
            "how do i improve",
            "how to get better",
            "how do i get better",
            "improve my",
            "tips for",
            "advice for",
            "how to learn",
            "how to master",
            "how to study",
            "how can i do better",
            "how to get good marks",
            "how to get a+",
            "আজ কী পড়ব",
            "আজ কি পড়া উচিত",
            "আজকে কী পড়ব",
            "আজকে কি পড়ব",
            "কোন বিষয় পড়ব",
            "পড়ার রুটিন",
            "পড়ালেখা কীভাবে করব",
            "কোন অধ্যায় পড়ব",
            "কীভাবে ভালো করব",
            "কিভাবে ভালো করব",
            "কীভাবে পড়া উচিত",
            "উন্নতি করার উপায়",
            "ভালো করার উপায়",
            "পড়ার নিয়ম",
            "ভীতি কাটানোর উপায়",
            "ভালো রেজাল্ট করার উপায়",
            "ভালো নম্বর পাওয়ার উপায়",
            "সহজে শেখার উপায়",
        ]
        if any(trig in clean_q for trig in guidance_triggers):
            return "study_guidance"

        # Check greetings before strict checks
        study_indicators = [
            "page",
            "pg",
            "পৃষ্ঠা",
            "chapter",
            "অধ্যায়",
            "বই",
            "book",
            "explain",
            "বিজ্ঞান",
            "গণিত",
            "math",
            "science",
            "নিউরন",
            "অক্সিন",
            "photosynthesis",
            "সালোকসংশ্লেষণ",
            "পরমাণু",
            "মহাকর্ষ",
            "gravity",
            "formula",
            "সূত্র",
        ]
        has_study_topic = any(topic in clean_q for topic in study_indicators)
        greeting_words = {
            "hi",
            "hii",
            "hiii",
            "hello",
            "helo",
            "hey",
            "heyy",
            "hey buddy",
            "hi buddy",
            "hello buddy",
            "good morning",
            "good afternoon",
            "good evening",
            "greetings",
            "how are you",
            "who are you",
            "what is your name",
            "what can you do",
            "introduce yourself",
            "assalamualaikum",
            "assalamu alaikum",
            "as-salamu alaykum",
            "সালাম",
            "আসসালামু আলাইকুম",
            "নমস্কার",
            "হ্যালো",
            "হাই",
            "কেমন আছো",
            "কেমন আছেন",
            "তুমি কে",
            "আপনি কে",
            "তোমার নাম কি",
            "কী করতে পারো",
            "কি করতে পারো",
            "সাহায্য করো",
        }
        if not has_study_topic:
            if clean_q in greeting_words or (
                len(clean_q.split()) <= 3
                and any(
                    clean_q.startswith(g)
                    for g in ["hi", "hii", "hello", "hey", "হ্যালো", "হাই", "সালাম"]
                )
            ):
                return "greeting"

        return "study_question"

    def _build_payload(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        include_privacy: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": stream,
            "frequency_penalty": 0.5,
            "presence_penalty": 0.2,
            "num_ctx": 8192,
            "options": {
                "num_ctx": 8192,
                "num_predict": self.max_tokens or 1024,
                "temperature": self.temperature,
                "repeat_penalty": 1.15,
                "top_p": 0.9,
            },
        }
        # Cap reasoning tokens on reasoning models to avoid token exhaustion
        if "nemotron" in model.lower() or "reasoning" in model.lower():
            payload["reasoning"] = {"max_tokens": 250}

        # Data collection protection: Strict fail-closed privacy enforcement
        if include_privacy:
            payload["provider"] = {"data_collection": "deny"}

        if tools:
            payload["tools"] = tools

        return payload

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        timeout: float | httpx.Timeout = 120.0,
        tools: list[dict[str, Any]] | None = None,
        tool_executor: Any | None = None,
    ) -> AsyncIterator[str]:
        target_model = model or self.primary_model
        chat_url = f"{self.api_base}/chat/completions"
        headers = self._get_headers()
        current_messages: list[dict[str, Any]] = list(messages)
        start_time = time.perf_counter()

        client_timeout = (
            timeout
            if isinstance(timeout, httpx.Timeout)
            else httpx.Timeout(connect=10.0, read=float(timeout), write=20.0, pool=30.0)
        )
        async with httpx.AsyncClient(timeout=client_timeout) as client:
            # 1. Multi-turn Tool Calling Execution Loop (cap max 3 iterations)
            if tools and tool_executor:
                tool_iterations = 0
                while tool_iterations < 3:
                    payload = self._build_payload(
                        target_model, current_messages, tools=tools, stream=False
                    )
                    try:
                        resp = await client.post(chat_url, headers=headers, json=payload)
                        if resp.status_code == 404 and "data policy" in resp.text.lower():
                            logger.error(
                                "Privacy violation: Model %s rejected due to data policy. Failing closed.",
                                target_model,
                            )
                            break

                        if resp.is_success:
                            res_json = resp.json()
                            msg = res_json.get("choices", [{}])[0].get("message", {})
                            tool_calls = msg.get("tool_calls")
                            if not tool_calls:
                                # Direct answer provided without tools
                                direct_text = msg.get("content") or ""
                                if direct_text:
                                    self.last_model_used = res_json.get("model", target_model)
                                    self.last_provider = res_json.get("provider", "OpenRouter")
                                    words = direct_text.split(" ")
                                    for w in words[:-1]:
                                        yield w + " "
                                        await asyncio.sleep(0.01)
                                    if words:
                                        yield words[-1]
                                    return
                                break

                            clean_msg: dict[str, Any] = {
                                "role": msg.get("role", "assistant"),
                                "content": msg.get("content") or "",
                            }
                            if "tool_calls" in msg and msg["tool_calls"]:
                                clean_msg["tool_calls"] = msg["tool_calls"]
                            current_messages.append(clean_msg)
                            for tc in tool_calls:
                                fn = tc.get("function", {})
                                fn_name = fn.get("name", "")
                                try:
                                    fn_args = (
                                        json.loads(fn.get("arguments", "{}"))
                                        if isinstance(fn.get("arguments"), str)
                                        else fn.get("arguments", {})
                                    )
                                except Exception:
                                    fn_args = {}
                                try:
                                    tool_result = await tool_executor.execute_tool(fn_name, fn_args)
                                except Exception as tool_ex:
                                    logger.exception(
                                        "Tool execution failed for '%s': %s", fn_name, tool_ex
                                    )
                                    tool_result = {
                                        "status": "error",
                                        "error": f"Tool '{fn_name}' execution failed: {str(tool_ex)}",
                                        "message": "পাঠ্যবই অনুসন্ধানে কারিগরি ত্রুটি হয়েছে। বইটি সরাসরি যাচাই করা সম্ভব হয়নি।",
                                    }
                                current_messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tc.get("id", str(uuid.uuid4())),
                                        "name": fn_name,
                                        "content": json.dumps(tool_result, ensure_ascii=False),
                                    }
                                )
                            tool_iterations += 1
                        else:
                            logger.warning(
                                "Tool calling request returned status %s: %s",
                                resp.status_code,
                                resp.text,
                            )
                            break
                    except Exception as ex:
                        logger.warning("Tool iteration failed on %s: %s", target_model, ex)
                        break

            # If tools were executed, guide the model to formulate its final tutor answer cleanly
            if tools and tool_executor and len(current_messages) > len(messages):
                has_tool_error = any(
                    m.get("role") == "tool"
                    and (
                        '"status": "error"' in m.get("content", "")
                        or '"error"' in m.get("content", "")
                    )
                    for m in current_messages
                )
                if has_tool_error:
                    current_messages.append(
                        {
                            "role": "system",
                            "content": (
                                "WARNING: A textbook search tool encountered an error or failed. "
                                "You must explain from your general knowledge if helpful, but you MUST explicitly "
                                "tell the student that you could NOT check or verify the textbook right now due to a "
                                "technical error ('পাঠ্যবই যাচাই করা সম্ভব হয়নি'). You MUST NEVER claim that you verified "
                                "this from the book ('বই থেকে যাচাই করেছি' or similar) when the tool failed. Do not invent page citations."
                            ),
                        }
                    )
                else:
                    current_messages.append(
                        {
                            "role": "system",
                            "content": "You have retrieved textbook information above. Now formulate a warm, clear, structured tutor explanation in Bengali. Include the printed page number citation. Do not call any more tools.",
                        }
                    )

            # 2. Final Answer Token Streaming Loop
            for active_model in [target_model, self.fallback_model]:
                payload = self._build_payload(
                    active_model, current_messages, tools=None, stream=True, include_privacy=True
                )
                try:
                    tokens_yielded = 0
                    async with client.stream(
                        "POST", chat_url, headers=headers, json=payload
                    ) as resp:
                        if resp.status_code != 200:
                            logger.error(
                                "Streaming request failed on model %s with status %s: %s",
                                active_model,
                                resp.status_code,
                                (await resp.aread()).decode("utf-8", errors="ignore")[:300],
                            )
                            continue

                        if resp.status_code == 200:
                            self.last_model_used = active_model
                            self.last_provider = "OpenRouter"
                            async for line in resp.aiter_lines():
                                if line.startswith("data: "):
                                    data_str = line[6:].strip()
                                    if data_str == "[DONE]":
                                        break
                                    try:
                                        chunk_data = json.loads(data_str)
                                        delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                                        content_token = delta.get("content")
                                        if content_token:
                                            tokens_yielded += 1
                                            yield content_token
                                        if "model" in chunk_data:
                                            self.last_model_used = chunk_data["model"]
                                    except Exception:
                                        continue

                            if tokens_yielded > 0:
                                self.last_tokens_out = tokens_yielded
                                self.last_latency_ms = int(
                                    (time.perf_counter() - start_time) * 1000
                                )
                                return
                        else:
                            err_body = (await resp.aread()).decode("utf-8", errors="ignore")
                            logger.warning(
                                "Stream attempt on %s returned %s: %s",
                                active_model,
                                resp.status_code,
                                err_body,
                            )
                except (asyncio.CancelledError, Exception) as ex:
                    if isinstance(ex, asyncio.CancelledError):
                        logger.info("Client disconnected during OpenRouter streaming")
                        raise
                    logger.warning("Streaming failed for %s: %s", active_model, ex)

        # Fallback error when all attempts fail
        logger.error("All OpenRouter generation attempts failed.")
        self.last_model_used = "error-fallback"
        yield ERROR_MESSAGE_BANGLA

    async def generate_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        timeout: float | httpx.Timeout = 120.0,
        tools: list[dict[str, Any]] | None = None,
        tool_executor: Any | None = None,
    ) -> LLMGenerationResult:
        target_model = model or self.primary_model
        chat_url = f"{self.api_base}/chat/completions"
        headers = self._get_headers()
        current_messages: list[dict[str, Any]] = list(messages)
        start_time = time.perf_counter()

        client_timeout = (
            timeout
            if isinstance(timeout, httpx.Timeout)
            else httpx.Timeout(connect=10.0, read=float(timeout), write=20.0, pool=30.0)
        )
        async with httpx.AsyncClient(timeout=client_timeout) as client:
            # 1. Multi-turn Tool Calling Execution Loop
            if tools and tool_executor:
                tool_iterations = 0
                while tool_iterations < 3:
                    payload = self._build_payload(
                        target_model, current_messages, tools=tools, stream=False
                    )
                    try:
                        resp = await client.post(chat_url, headers=headers, json=payload)
                        if resp.status_code == 404 and "data policy" in resp.text.lower():
                            logger.error(
                                "Privacy violation: Model %s rejected due to data policy. Failing closed.",
                                target_model,
                            )
                            break

                        if resp.is_success:
                            res_json = resp.json()
                            msg = res_json.get("choices", [{}])[0].get("message", {})
                            tool_calls = msg.get("tool_calls")
                            if not tool_calls:
                                content = msg.get("content") or ""
                                usage = res_json.get("usage", {})
                                lat = int((time.perf_counter() - start_time) * 1000)
                                self.last_model_used = res_json.get("model", target_model)
                                self.last_provider = res_json.get("provider", "OpenRouter")
                                return LLMGenerationResult(
                                    content=content,
                                    tokens_in=usage.get("prompt_tokens", 20),
                                    tokens_out=usage.get("completion_tokens", len(content.split())),
                                    model=self.last_model_used,
                                    latency_ms=lat,
                                    provider=self.last_provider,
                                )

                            clean_msg: dict[str, Any] = {
                                "role": msg.get("role", "assistant"),
                                "content": msg.get("content") or "",
                            }
                            if "tool_calls" in msg and msg["tool_calls"]:
                                clean_msg["tool_calls"] = msg["tool_calls"]
                            current_messages.append(clean_msg)
                            for tc in tool_calls:
                                fn = tc.get("function", {})
                                fn_name = fn.get("name", "")
                                try:
                                    fn_args = (
                                        json.loads(fn.get("arguments", "{}"))
                                        if isinstance(fn.get("arguments"), str)
                                        else fn.get("arguments", {})
                                    )
                                except Exception:
                                    fn_args = {}
                                try:
                                    tool_result = await tool_executor.execute_tool(fn_name, fn_args)
                                except Exception as tool_ex:
                                    logger.exception(
                                        "Tool execution failed for '%s': %s", fn_name, tool_ex
                                    )
                                    tool_result = {
                                        "status": "error",
                                        "error": f"Tool '{fn_name}' execution failed: {str(tool_ex)}",
                                        "message": "পাঠ্যবই অনুসন্ধানে কারিগরি ত্রুটি হয়েছে। বইটি সরাসরি যাচাই করা সম্ভব হয়নি।",
                                    }
                                current_messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tc.get("id", str(uuid.uuid4())),
                                        "name": fn_name,
                                        "content": json.dumps(tool_result, ensure_ascii=False),
                                    }
                                )
                            tool_iterations += 1
                        else:
                            break
                    except Exception as ex:
                        logger.warning("Tool iteration failed: %s", ex)
                        break

            if tools and tool_executor and len(current_messages) > len(messages):
                has_tool_error = any(
                    m.get("role") == "tool"
                    and (
                        '"status": "error"' in m.get("content", "")
                        or '"error"' in m.get("content", "")
                    )
                    for m in current_messages
                )
                if has_tool_error:
                    current_messages.append(
                        {
                            "role": "system",
                            "content": (
                                "WARNING: A textbook search tool encountered an error or failed. "
                                "You must explain from your general knowledge if helpful, but you MUST explicitly "
                                "tell the student that you could NOT check or verify the textbook right now due to a "
                                "technical error ('পাঠ্যবই যাচাই করা সম্ভব হয়নি'). You MUST NEVER claim that you verified "
                                "this from the book ('বই থেকে যাচাই করেছি' or similar) when the tool failed. Do not invent page citations."
                            ),
                        }
                    )
                else:
                    current_messages.append(
                        {
                            "role": "system",
                            "content": "Formulate a warm, clear, structured tutor explanation in Bengali based on the textbook data above. Include printed page citation. Do not call any tools.",
                        }
                    )

            for active_model in [target_model, self.fallback_model]:
                payload = self._build_payload(
                    active_model, current_messages, tools=None, stream=False, include_privacy=True
                )
                try:
                    resp = await client.post(chat_url, headers=headers, json=payload)

                    if resp.is_success:
                        res_json = resp.json()
                        msg = res_json.get("choices", [{}])[0].get("message", {})
                        content = msg.get("content") or ""
                        usage = res_json.get("usage", {})
                        lat = int((time.perf_counter() - start_time) * 1000)
                        self.last_model_used = res_json.get("model", active_model)
                        self.last_provider = res_json.get("provider", "OpenRouter")
                        return LLMGenerationResult(
                            content=content,
                            tokens_in=usage.get("prompt_tokens", 20),
                            tokens_out=usage.get("completion_tokens", len(content.split())),
                            model=self.last_model_used,
                            latency_ms=lat,
                            provider=self.last_provider,
                        )
                except Exception as ex:
                    logger.warning("Generation attempt failed for %s: %s", active_model, ex)

        return LLMGenerationResult(
            content=ERROR_MESSAGE_BANGLA,
            tokens_in=0,
            tokens_out=0,
            model="upstream-error",
            latency_ms=int((time.perf_counter() - start_time) * 1000),
        )


# Backward compatibility alias
LiteLLMGateway = OpenRouterGateway


async def get_active_llm_gateway(db: Any | None = None) -> LLMGateway | None:
    """Resolve active LLM gateway from database configuration or environment."""
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
                return OpenRouterGateway(
                    primary_model=config.primary_model,
                    fallback_model=config.fallback_model,
                    api_key=config.api_key,
                    api_base=base_url,
                    temperature=config.temperature,
                )

            import os

            env_key = os.getenv("OPENROUTER_API_KEY")
            if env_key:
                return OpenRouterGateway(
                    primary_model=os.getenv(
                        "DEFAULT_LLM_MODEL", "nvidia/nemotron-3.5-super-vl:free"
                    ),
                    fallback_model="nvidia/nemotron-3.5-lightning:free",
                    api_key=env_key,
                    api_base="https://openrouter.ai/api/v1",
                    temperature=0.4,
                )
        except Exception as ex:
            logger.debug("Could not load AITutorConfig for LLMGateway: %s", ex)

    logger.warning("No active LLM API key configured in database or environment.")
    return None
