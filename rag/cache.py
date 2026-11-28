"""Thread-safe bounded LRU + optional Redis cache for normalized query embeddings."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from collections import OrderedDict
from typing import Any

logger = logging.getLogger(__name__)


class QueryEmbeddingCache:
    """Bounded thread-safe LRU cache for dense+sparse query vectors."""

    def __init__(self, max_size: int = 1024, redis_client: Any | None = None) -> None:
        self.max_size = max(1, max_size)
        self._lock = threading.Lock()
        self._cache: OrderedDict[str, tuple[list[float], list[int], list[float]]] = OrderedDict()
        self._redis = redis_client
        self.hits = 0
        self.misses = 0

    def _key(self, normalized_query: str) -> str:
        digest = hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()[:32]
        return f"rag:emb:{digest}"

    def get(self, normalized_query: str) -> tuple[list[float], list[int], list[float]] | None:
        k = self._key(normalized_query)
        with self._lock:
            val = self._cache.get(k)
            if val is not None:
                self._cache.move_to_end(k)
                self.hits += 1
                return val

        if self._redis is not None:
            try:
                raw = self._redis.get(k)
                if raw:
                    parsed = json.loads(raw)
                    tup = (parsed["dense"], parsed["sparse_idx"], parsed["sparse_val"])
                    with self._lock:
                        self._put_lru_unlocked(k, tup)
                        self.hits += 1
                    return tup
            except Exception as exc:
                logger.debug("Redis embedding cache get skipped: %s", exc)

        with self._lock:
            self.misses += 1
        return None

    def _put_lru_unlocked(
        self, key: str, value: tuple[list[float], list[int], list[float]]
    ) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        while len(self._cache) > self.max_size:
            self._cache.popitem(last=False)

    def set(
        self,
        normalized_query: str,
        dense: list[float],
        sparse_idx: list[int],
        sparse_val: list[float],
    ) -> None:
        k = self._key(normalized_query)
        val = (dense, sparse_idx, sparse_val)
        with self._lock:
            self._put_lru_unlocked(k, val)
        if self._redis is not None:
            try:
                self._redis.setex(
                    k,
                    3600,
                    json.dumps(
                        {"dense": dense, "sparse_idx": sparse_idx, "sparse_val": sparse_val}
                    ),
                )
            except Exception as exc:
                logger.debug("Redis embedding cache set skipped: %s", exc)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0


_default_embedding_cache: QueryEmbeddingCache | None = None


def get_embedding_cache() -> QueryEmbeddingCache:
    global _default_embedding_cache
    if _default_embedding_cache is None:
        _default_embedding_cache = QueryEmbeddingCache(max_size=1024)
    return _default_embedding_cache
