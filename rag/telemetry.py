"""Structured RAG Observability Telemetry."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger("thinkbuddy.rag.telemetry")


@dataclass
class RagTelemetryEvent:
    """Structured per-request RAG telemetry payload."""

    request_id: str
    provider: str
    normalized_query: str
    tools_called: list[str] = field(default_factory=list)
    retrieved_point_ids: list[str] = field(default_factory=list)
    rrf_scores: list[float] = field(default_factory=list)
    rerank_scores: list[float] = field(default_factory=list)
    cache_hit: bool = False
    tool_latency_ms: int = 0
    ttft_ms: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


def emit_rag_telemetry(event: RagTelemetryEvent) -> dict[str, Any]:
    """Emit structured JSON log for RAG observability (compatible with OTel/Langfuse hooks)."""
    payload = asdict(event)
    logger.info("rag_turn_telemetry %s", json.dumps(payload, ensure_ascii=False))
    return payload
