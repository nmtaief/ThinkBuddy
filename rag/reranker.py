"""Stage-2 Cross-Encoder Reranker using BAAI/bge-reranker-v2-m3 with graceful RRF fallback."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from core.common.config import settings
from rag.bilingual_map import translate_chapter_title_en

logger = logging.getLogger(__name__)


def _has_accelerator() -> bool:
    try:
        import torch

        if torch.cuda.is_available():
            return True
        mps = getattr(torch.backends, "mps", None)
        return bool(mps is not None and mps.is_available())
    except Exception:
        return False


def _resolve_reranker_enabled(enabled: str | bool | None) -> bool:
    val = settings.RAG_RERANKER_ENABLED if enabled is None else enabled
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("true", "1", "yes", "on"):
        return True
    if s in ("false", "0", "no", "off"):
        return False
    # "auto": enable only when CUDA or MPS accelerator is available
    return _has_accelerator()


def _resolve_local_reranker_path(model_name: str) -> str:
    if model_name != "BAAI/bge-reranker-v2-m3":
        return model_name
    env_path = os.getenv("BGE_RERANKER_MODEL_PATH")
    if env_path and os.path.exists(env_path):
        return env_path
    hub_dir = (
        Path.home()
        / ".cache"
        / "huggingface"
        / "hub"
        / "models--BAAI--bge-reranker-v2-m3"
        / "snapshots"
    )
    if hub_dir.is_dir():
        snaps = [p for p in hub_dir.iterdir() if p.is_dir()]
        if snaps:
            return str(snaps[0])
    return model_name


class BgeRerankerProvider:
    """Stage-2 multilingual cross-encoder reranker with lazy initialization & safe fallback."""

    _model: Any = None
    _load_failed: bool = False

    def __init__(self, model_name: str | None = None, enabled: str | bool | None = None) -> None:
        self.model_name = model_name or settings.RAG_RERANKER_MODEL
        self.enabled = _resolve_reranker_enabled(enabled)

    def _ensure_model(self) -> Any | None:
        if not self.enabled or BgeRerankerProvider._load_failed:
            return None
        if BgeRerankerProvider._model is not None:
            return BgeRerankerProvider._model
        try:
            import torch
            from sentence_transformers import CrossEncoder

            resolved = _resolve_local_reranker_path(self.model_name)
            local_only = os.path.exists(resolved)
            use_cuda = torch.cuda.is_available()
            use_mps = (
                getattr(torch.backends, "mps", None) is not None
                and torch.backends.mps.is_available()
            )
            device = "cuda" if use_cuda else ("mps" if use_mps else "cpu")
            model_kwargs = {"torch_dtype": torch.float16} if (use_cuda or use_mps) else {}
            eff_max_len = 512 if (use_cuda or use_mps) else 256

            logger.info(
                "Initializing BgeRerankerProvider from %s (device=%s, max_length=%d, local_only=%s)",
                resolved,
                device,
                eff_max_len,
                local_only,
            )
            BgeRerankerProvider._model = CrossEncoder(
                resolved,
                device=device,
                max_length=eff_max_len,
                local_files_only=local_only,
                model_kwargs=model_kwargs,
            )
            return BgeRerankerProvider._model
        except Exception as exc:
            logger.warning("Reranker unavailable, falling back to pure RRF scores: %s", exc)
            BgeRerankerProvider._load_failed = True
            return None

    @staticmethod
    def build_bilingual_passage(hit: dict[str, Any]) -> str:
        """Assemble bilingual header-enriched passage text for cross-encoder scoring."""
        book_name = str(hit.get("book_name") or "")
        ch_num = hit.get("chapter_number") or 1
        topic = str(hit.get("topic") or "")
        subject = str(hit.get("subject") or "")
        topic_en = translate_chapter_title_en(topic, subject, int(ch_num)) if topic else ""
        header = f"{book_name} | Ch {ch_num} | {topic}"
        if topic_en and topic_en.lower() not in topic.lower():
            header += f" ({topic_en})"
        raw_text = str(hit.get("text", ""))[:800]
        return f"{header}\n{raw_text}".strip()

    def rerank(
        self,
        query: str,
        hits: list[dict[str, Any]],
        top_k: int = 4,
    ) -> list[dict[str, Any]]:
        """Rerank Stage-1 RRF hits by cross-encoder relevance, or fall back to RRF order."""
        if not hits:
            return []
        for h in hits:
            h.setdefault("rrf_score", float(h.get("score", 0.0)))

        model = self._ensure_model()
        if model is None:
            return hits[:top_k]

        pairs = [(query, self.build_bilingual_passage(h)) for h in hits]
        try:
            scores = model.predict(pairs, show_progress_bar=False)
            scored_hits: list[dict[str, Any]] = []
            for h, s in zip(hits, scores, strict=True):
                item = dict(h)
                item["rerank_score"] = float(s)
                item["score"] = float(s)
                scored_hits.append(item)
            scored_hits.sort(key=lambda x: x["rerank_score"], reverse=True)
            return scored_hits[:top_k]
        except Exception as exc:
            logger.warning("Reranker prediction failed, falling back to RRF: %s", exc)
            return hits[:top_k]


_default_reranker: BgeRerankerProvider | None = None


def get_reranker() -> BgeRerankerProvider:
    global _default_reranker
    if _default_reranker is None:
        _default_reranker = BgeRerankerProvider()
    return _default_reranker
