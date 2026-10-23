"""Multilingual embedding provider interfaces and implementations.

Supports:
- EmbeddingProvider abstract interface
- MockMultilingualEmbeddingProvider: fast, deterministic, unit-normalized semantic embeddings
  for tests without heavyweight PyTorch/GPU dependencies
- HostedMultilingualEmbeddingProvider: LiteLLM / OpenAI / HuggingFace compatible API with
  exponential backoff retries, batching, and cost tracking
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
from abc import ABC, abstractmethod

import httpx

from core.common.config import settings

logger = logging.getLogger(__name__)


class EmbeddingStats:
    """Tracks token consumption and invocation counts for cost accounting."""

    total_requests: int = 0
    total_texts: int = 0
    total_tokens_estimated: int = 0
    total_cost_usd: float = 0.0

    @classmethod
    def record(cls, num_texts: int, estimated_tokens: int, cost_usd: float = 0.0) -> None:
        cls.total_requests += 1
        cls.total_texts += num_texts
        cls.total_tokens_estimated += estimated_tokens
        cls.total_cost_usd += cost_usd
        logger.info(
            "Embedding usage: %d texts, ~%d tokens, est_cost=$%.6f (all-time tokens: %d)",
            num_texts,
            estimated_tokens,
            cost_usd,
            cls.total_tokens_estimated,
        )

    @classmethod
    def reset(cls) -> None:
        cls.total_requests = 0
        cls.total_texts = 0
        cls.total_tokens_estimated = 0
        cls.total_cost_usd = 0.0


class EmbeddingProvider(ABC):
    """Abstract base class for text embedding generation."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimension produced by this model."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name / identifier of the embedding model."""

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string for semantic search."""

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of document chunks."""


class MockMultilingualEmbeddingProvider(EmbeddingProvider):
    """Deterministic, unit-normalized embedding provider for testing and offline evaluation.

    Encodes text into a fixed-dimension unit vector. Semantic keywords (Bangla and English)
    influence coordinate projections so semantically similar phrases have high cosine similarity.
    """

    def __init__(self, dimension: int | None = None, model_name: str | None = None) -> None:
        self._dimension = dimension or settings.EMBEDDING_DIMENSION
        self._model_name = model_name or settings.EMBEDDING_MODEL

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def _generate_vector(self, text: str) -> list[float]:
        """Generate a deterministic unit-normalized vector for given text."""
        # Use SHA-512 hashes to produce pseudorandom seed sequence
        text_clean = text.strip().lower()
        vec = [0.0] * self._dimension

        # Base hash seed
        for chunk_idx in range(math.ceil(self._dimension / 8)):
            seed_bytes = f"{text_clean}_{chunk_idx}".encode()
            hash_digest = hashlib.sha512(seed_bytes).digest()
            for i in range(min(8, self._dimension - chunk_idx * 8)):
                val = (hash_digest[i * 4] << 8 | hash_digest[i * 4 + 1]) / 65535.0
                vec[chunk_idx * 8 + i] = (val * 2.0) - 1.0

        # Semantic projection for common curriculum keywords (Bangla + English)
        keywords = {
            "বর্গ": 0,
            "বর্গমূল": 1,
            "square": 0,
            "root": 1,
            "ভগ্নাংশ": 2,
            "fraction": 2,
            "দশমিক": 3,
            "decimal": 3,
            "বীজগণিত": 4,
            "algebra": 4,
            "সমীকরণ": 5,
            "equation": 5,
            "জ্যামিতি": 6,
            "geometry": 6,
            "ত্রিভুজ": 7,
            "triangle": 7,
            "সালোকসংশ্লেষণ": 8,
            "photosynthesis": 8,
            "উদ্ভিদ": 9,
            "plant": 9,
            "কোষ": 10,
            "cell": 10,
            "প্রাণী": 11,
            "animal": 11,
            "শক্তি": 12,
            "energy": 12,
            "তাপ": 13,
            "heat": 13,
            "পদার্থ": 14,
            "matter": 14,
            "পরমাণু": 15,
            "atom": 15,
        }

        for word, idx in keywords.items():
            if word in text_clean:
                target_pos = idx % self._dimension
                vec[target_pos] += 3.5

        # Normalize to unit length (L2 norm = 1.0)
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    async def embed_query(self, text: str) -> list[float]:
        vec = self._generate_vector(text)
        est_tokens = max(1, len(text.split()))
        EmbeddingStats.record(num_texts=1, estimated_tokens=est_tokens)
        return vec

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = [self._generate_vector(t) for t in texts]
        est_tokens = sum(max(1, len(t.split())) for t in texts)
        EmbeddingStats.record(num_texts=len(texts), estimated_tokens=est_tokens)
        return vectors


class HostedMultilingualEmbeddingProvider(EmbeddingProvider):
    """Production provider calling OpenAI-compatible or LiteLLM embedding API with retries."""

    def __init__(
        self,
        api_base: str = "https://api.openai.com/v1",
        api_key: str = "mock-key",
        model_name: str = "text-embedding-3-small",
        dimension: int = 384,
        max_retries: int = 3,
    ) -> None:
        self._api_base = api_base.rstrip("/")
        self._api_key = api_key
        self._model_name = model_name
        self._dimension = dimension
        self._max_retries = max_retries

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        url = f"{self._api_base}/embeddings"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = {
            "model": self._model_name,
            "input": texts,
            "dimensions": self._dimension,
        }

        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    res = await client.post(url, json=payload, headers=headers)
                    res.raise_for_status()
                    data = res.json()
                    vectors = [item["embedding"] for item in data["data"]]
                    tokens = data.get("usage", {}).get("total_tokens", len(" ".join(texts).split()))
                    EmbeddingStats.record(num_texts=len(texts), estimated_tokens=tokens)
                    return vectors
            except Exception as exc:
                last_exc = exc
                wait_time = 0.5 * (2**attempt)
                logger.warning(
                    "Embedding request failed (attempt %d/%d): %s. Retrying in %.1fs",
                    attempt + 1,
                    self._max_retries,
                    exc,
                    wait_time,
                )
                await asyncio.sleep(wait_time)

        raise RuntimeError(
            f"Embedding request failed after {self._max_retries} retries: {last_exc}"
        )

    async def embed_query(self, text: str) -> list[float]:
        res = await self._embed_batch([text])
        return res[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        batch_size = settings.EMBEDDING_BATCH_SIZE
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            emb = await self._embed_batch(chunk)
            all_embeddings.extend(emb)
        return all_embeddings


def get_embedding_provider() -> EmbeddingProvider:
    """Factory returning configured EmbeddingProvider instance."""
    provider_type = settings.EMBEDDING_PROVIDER.lower()
    if provider_type in ("mock", "test", "local"):
        return MockMultilingualEmbeddingProvider(
            dimension=settings.EMBEDDING_DIMENSION,
            model_name=settings.EMBEDDING_MODEL,
        )
    return HostedMultilingualEmbeddingProvider(
        model_name=settings.EMBEDDING_MODEL,
        dimension=settings.EMBEDDING_DIMENSION,
    )
