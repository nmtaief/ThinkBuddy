"""Unified Multi-Provider LLM Tool Router (Gemini, DeepSeek, Claude).

Binds the exact same 3 decoupled retrieval tools (`get_syllabus_scope`,
`get_topic_concepts`, `get_book_questions`) across:
- Google Gemini (`google-genai` SDK)
- DeepSeek (`openai` SDK with DeepSeek base URL)
- Anthropic Claude (`anthropic` SDK)
and executes multi-turn tool-call loops automatically.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from core.chat.prompts import build_decoupled_system_prompt
from core.common.config import settings
from rag.query_normalizer import normalize_query
from rag.retrieval_tools import (
    DECOUPLED_TOOL_DEFINITIONS,
    DecoupledRetrievalTools,
    get_decoupled_tools,
)
from rag.telemetry import RagTelemetryEvent, emit_rag_telemetry

logger = logging.getLogger(__name__)

ProviderName = Literal["gemini", "deepseek", "claude"]

TOOL_STATUS_MESSAGES: dict[str, str] = {
    "get_syllabus_scope": "Checking NCTB syllabus scope...",
    "get_topic_concepts": "Reviewing textbook concepts...",
    "get_book_questions": "Checking book question styles...",
}


@dataclass
class ToolCallTrace:
    """Record of a single tool invocation during an orchestration turn."""

    tool_name: str
    arguments: dict[str, Any]
    result_preview: str


@dataclass
class ToolOrchestrationResult:
    """Complete result from a multi-provider tool-calling turn."""

    content: str
    provider: ProviderName
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    tool_calls: list[ToolCallTrace] = field(default_factory=list)


def _to_gemini_tools() -> list[Any]:
    """Convert canonical tool definitions to google-genai types.Tool."""
    from google.genai import types

    declarations = []
    for tool_def in DECOUPLED_TOOL_DEFINITIONS:
        declarations.append(
            types.FunctionDeclaration(
                name=tool_def["name"],
                description=tool_def["description"],
                parameters_json_schema=tool_def["parameters"],
            )
        )
    return [types.Tool(function_declarations=declarations)]


def _to_openai_tools() -> list[dict[str, Any]]:
    """Convert canonical tool definitions to OpenAI/DeepSeek function tool schema."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        }
        for t in DECOUPLED_TOOL_DEFINITIONS
    ]


def _to_anthropic_tools() -> list[dict[str, Any]]:
    """Convert canonical tool definitions to Anthropic Claude input_schema format."""
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["parameters"],
        }
        for t in DECOUPLED_TOOL_DEFINITIONS
    ]


class LLMToolOrchestrator:
    """Model-agnostic tool-calling orchestrator for Gemini, DeepSeek, and Claude."""

    def __init__(
        self,
        retrieval_tools: DecoupledRetrievalTools | None = None,
        *,
        gemini_client: Any | None = None,
        deepseek_client: Any | None = None,
        claude_client: Any | None = None,
        max_tool_rounds: int | None = None,
        tool_timeout_sec: float | None = None,
    ) -> None:
        self.retrieval_tools = retrieval_tools or get_decoupled_tools()
        self._gemini_client = gemini_client
        self._deepseek_client = deepseek_client
        self._claude_client = claude_client
        self.max_tool_rounds = (
            max_tool_rounds if max_tool_rounds is not None else settings.RAG_MAX_TOOL_ITERATIONS
        )
        self.tool_timeout_sec = (
            tool_timeout_sec if tool_timeout_sec is not None else settings.RAG_TOOL_TIMEOUT_SEC
        )

    def _get_gemini_client(self) -> Any:
        if self._gemini_client is not None:
            return self._gemini_client
        from google import genai

        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")
        self._gemini_client = genai.Client(api_key=api_key)
        return self._gemini_client

    def _get_deepseek_client(self) -> Any:
        if self._deepseek_client is not None:
            return self._deepseek_client
        from openai import AsyncOpenAI

        api_key = settings.DEEPSEEK_API_KEY
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is not configured.")
        self._deepseek_client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
        return self._deepseek_client

    def _get_claude_client(self) -> Any:
        if self._claude_client is not None:
            return self._claude_client
        from anthropic import AsyncAnthropic

        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured.")
        self._claude_client = AsyncAnthropic(api_key=api_key)
        return self._claude_client

    async def _execute_tool(
        self,
        name: str,
        args: dict[str, Any],
        traces: list[ToolCallTrace],
        on_status: Callable[[str], Awaitable[None]] | None = None,
        seen_chunk_keys: set[str] | None = None,
        telemetry_acc: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if on_status is not None:
            status_msg = TOOL_STATUS_MESSAGES.get(name, f"Running {name}...")
            await on_status(status_msg)
        try:
            result: Any = await asyncio.wait_for(
                self.retrieval_tools.execute(name, args),
                timeout=self.tool_timeout_sec,
            )
        except TimeoutError:
            logger.warning("Tool '%s' timed out after %.1fs", name, self.tool_timeout_sec)
            result = {"error": f"Tool '{name}' timed out after {self.tool_timeout_sec}s"}
        except Exception as exc:
            logger.warning("Tool '%s' failed with args %s: %s", name, args, exc)
            result = {"error": f"Tool execution failed: {exc}"}

        # Deduplicate retrieved chunks across multi-turn tool calls within a single request
        if isinstance(result, list) and seen_chunk_keys is not None:
            deduped: list[Any] = []
            for item in result:
                if isinstance(item, dict):
                    pt_id = item.get("id")
                    txt = (
                        item.get("concept_summary")
                        or item.get("question_stem")
                        or item.get("text")
                        or ""
                    )
                    dedup_key = (
                        str(pt_id)
                        if pt_id
                        else hashlib.sha256(str(txt).encode("utf-8")).hexdigest()[:16]
                    )
                    if dedup_key in seen_chunk_keys:
                        continue
                    seen_chunk_keys.add(dedup_key)
                    if telemetry_acc is not None:
                        if pt_id:
                            telemetry_acc["point_ids"].append(str(pt_id))
                        if "rrf_score" in item:
                            telemetry_acc["rrf_scores"].append(float(item["rrf_score"]))
                        if "rerank_score" in item:
                            telemetry_acc["rerank_scores"].append(float(item["rerank_score"]))
                    deduped.append(item)
                else:
                    deduped.append(item)
            result = deduped

        if telemetry_acc is not None and getattr(
            self.retrieval_tools.qdrant_store, "last_cache_hit", False
        ):
            telemetry_acc["cache_hit"] = True

        serialized = json.dumps(result, ensure_ascii=False)
        traces.append(
            ToolCallTrace(
                tool_name=name,
                arguments=args,
                result_preview=serialized[:250],
            )
        )
        return {"result": result}

    async def run(
        self,
        query: str,
        *,
        provider: ProviderName | None = None,
        model: str | None = None,
        student_profile: dict[str, Any] | None = None,
        language: str = "bn",
        history: list[dict[str, str]] | None = None,
        on_status: Callable[[str], Awaitable[None]] | None = None,
    ) -> ToolOrchestrationResult:
        """Execute a full tool-calling turn on the requested LLM provider."""
        selected: ProviderName = (provider or settings.DEFAULT_LLM_PROVIDER or "gemini").lower()  # type: ignore[assignment]
        if selected not in ("gemini", "deepseek", "claude"):
            raise ValueError(
                f"Unsupported provider '{selected}'. Expected gemini, deepseek, or claude."
            )

        system_prompt = build_decoupled_system_prompt(student_profile, language=language)
        start = time.perf_counter()
        seen_chunk_keys: set[str] = set()
        telemetry_acc: dict[str, Any] = {
            "point_ids": [],
            "rrf_scores": [],
            "rerank_scores": [],
            "cache_hit": False,
        }

        if selected == "gemini":
            res = await self._run_gemini(
                query=query,
                system_prompt=system_prompt,
                model=model or "gemini-2.5-flash",
                history=history,
                on_status=on_status,
                seen_chunk_keys=seen_chunk_keys,
                telemetry_acc=telemetry_acc,
            )
        elif selected == "deepseek":
            res = await self._run_deepseek(
                query=query,
                system_prompt=system_prompt,
                model=model or "deepseek-chat",
                history=history,
                on_status=on_status,
                seen_chunk_keys=seen_chunk_keys,
                telemetry_acc=telemetry_acc,
            )
        else:
            res = await self._run_claude(
                query=query,
                system_prompt=system_prompt,
                model=model or "claude-3-5-sonnet-latest",
                history=history,
                on_status=on_status,
                seen_chunk_keys=seen_chunk_keys,
                telemetry_acc=telemetry_acc,
            )

        res.latency_ms = int((time.perf_counter() - start) * 1000)
        emit_rag_telemetry(
            RagTelemetryEvent(
                request_id=str(uuid.uuid4()),
                provider=selected,
                normalized_query=normalize_query(query),
                tools_called=[tc.tool_name for tc in res.tool_calls],
                retrieved_point_ids=telemetry_acc["point_ids"],
                rrf_scores=telemetry_acc["rrf_scores"],
                rerank_scores=telemetry_acc["rerank_scores"],
                cache_hit=bool(telemetry_acc["cache_hit"]),
                tool_latency_ms=res.latency_ms,
                ttft_ms=res.latency_ms,
            )
        )
        return res

    async def _run_gemini(
        self,
        *,
        query: str,
        system_prompt: str,
        model: str,
        history: list[dict[str, str]] | None = None,
        on_status: Callable[[str], Awaitable[None]] | None = None,
        seen_chunk_keys: set[str] | None = None,
        telemetry_acc: dict[str, Any] | None = None,
    ) -> ToolOrchestrationResult:
        from google.genai import types

        client = self._get_gemini_client()
        tools = _to_gemini_tools()
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=tools,
            temperature=0.4,
        )

        contents: list[Any] = []
        for msg in history or []:
            role = "model" if msg.get("role") == "assistant" else "user"
            contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=msg.get("content", ""))])
            )
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=query)]))

        traces: list[ToolCallTrace] = []
        tokens_in = 0
        tokens_out = 0
        final_text = ""

        for _ in range(self.max_tool_rounds):
            response = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            usage = getattr(response, "usage_metadata", None)
            if usage:
                tokens_in += int(getattr(usage, "prompt_token_count", 0) or 0)
                tokens_out += int(getattr(usage, "candidates_token_count", 0) or 0)

            function_calls = getattr(response, "function_calls", None) or []
            if not function_calls:
                final_text = getattr(response, "text", "") or ""
                break

            # Append model turn
            candidates = getattr(response, "candidates", None) or []
            if candidates and getattr(candidates[0], "content", None):
                contents.append(candidates[0].content)

            # Execute each function call and append function responses
            response_parts = []
            for fc in function_calls:
                fn_name = fc.name
                fn_args = dict(fc.args or {})
                tool_out = await self._execute_tool(
                    fn_name,
                    fn_args,
                    traces,
                    on_status=on_status,
                    seen_chunk_keys=seen_chunk_keys,
                    telemetry_acc=telemetry_acc,
                )
                response_parts.append(
                    types.Part.from_function_response(name=fn_name, response=tool_out)
                )
            contents.append(types.Content(role="user", parts=response_parts))

        return ToolOrchestrationResult(
            content=final_text,
            provider="gemini",
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            tool_calls=traces,
        )

    async def _run_deepseek(
        self,
        *,
        query: str,
        system_prompt: str,
        model: str,
        history: list[dict[str, str]] | None = None,
        on_status: Callable[[str], Awaitable[None]] | None = None,
        seen_chunk_keys: set[str] | None = None,
        telemetry_acc: dict[str, Any] | None = None,
    ) -> ToolOrchestrationResult:
        client = self._get_deepseek_client()
        tools = _to_openai_tools()

        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for msg in history or []:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages.append({"role": "user", "content": query})

        traces: list[ToolCallTrace] = []
        tokens_in = 0
        tokens_out = 0
        final_text = ""

        for _ in range(self.max_tool_rounds):
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                temperature=0.4,
            )
            usage = getattr(response, "usage", None)
            if usage:
                tokens_in += int(getattr(usage, "prompt_tokens", 0) or 0)
                tokens_out += int(getattr(usage, "completion_tokens", 0) or 0)

            choice = response.choices[0]
            msg = choice.message
            tool_calls = getattr(msg, "tool_calls", None) or []
            if not tool_calls:
                final_text = getattr(msg, "content", "") or ""
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": getattr(msg, "content", None),
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )
            for tc in tool_calls:
                raw_args = tc.function.arguments
                if isinstance(raw_args, str):
                    try:
                        fn_args = json.loads(raw_args) if raw_args.strip() else {}
                    except json.JSONDecodeError:
                        logger.warning("Malformed JSON tool arguments from DeepSeek: %s", raw_args)
                        fn_args = {}
                else:
                    fn_args = dict(raw_args or {})
                tool_out = await self._execute_tool(
                    tc.function.name,
                    fn_args,
                    traces,
                    on_status=on_status,
                    seen_chunk_keys=seen_chunk_keys,
                    telemetry_acc=telemetry_acc,
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(tool_out["result"], ensure_ascii=False),
                    }
                )

        return ToolOrchestrationResult(
            content=final_text,
            provider="deepseek",
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            tool_calls=traces,
        )

    async def _run_claude(
        self,
        *,
        query: str,
        system_prompt: str,
        model: str,
        history: list[dict[str, str]] | None = None,
        on_status: Callable[[str], Awaitable[None]] | None = None,
        seen_chunk_keys: set[str] | None = None,
        telemetry_acc: dict[str, Any] | None = None,
    ) -> ToolOrchestrationResult:
        client = self._get_claude_client()
        tools = _to_anthropic_tools()

        messages: list[dict[str, Any]] = []
        for msg in history or []:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages.append({"role": "user", "content": query})

        traces: list[ToolCallTrace] = []
        tokens_in = 0
        tokens_out = 0
        final_text = ""

        for _ in range(self.max_tool_rounds):
            response = await client.messages.create(
                model=model,
                system=system_prompt,
                messages=messages,
                tools=tools,
                max_tokens=1200,
                temperature=0.4,
            )
            usage = getattr(response, "usage", None)
            if usage:
                tokens_in += int(getattr(usage, "input_tokens", 0) or 0)
                tokens_out += int(getattr(usage, "output_tokens", 0) or 0)

            tool_use_blocks = [
                b for b in response.content if getattr(b, "type", None) == "tool_use"
            ]
            if not tool_use_blocks:
                text_parts = [
                    getattr(b, "text", "")
                    for b in response.content
                    if getattr(b, "type", None) == "text"
                ]
                final_text = "".join(text_parts)
                break

            messages.append({"role": "assistant", "content": response.content})
            tool_results: list[dict[str, Any]] = []
            for block in tool_use_blocks:
                fn_args = dict(getattr(block, "input", None) or {})
                tool_out = await self._execute_tool(
                    block.name,
                    fn_args,
                    traces,
                    on_status=on_status,
                    seen_chunk_keys=seen_chunk_keys,
                    telemetry_acc=telemetry_acc,
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(tool_out["result"], ensure_ascii=False),
                    }
                )
            messages.append({"role": "user", "content": tool_results})

        return ToolOrchestrationResult(
            content=final_text,
            provider="claude",
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            tool_calls=traces,
        )
