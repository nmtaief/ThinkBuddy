"""Layer 2: Typed Hybrid Vector Collection in Qdrant (BGE-M3 dense + sparse).

Provides:
- Collection provisioning with named dense (1024-dim Cosine) + sparse vectors
- Payload indexes on book_name, subject, chapter_number, content_type, question_category, language, topic
- Strict payload schema validation
- Filtered hybrid search using Qdrant RRF fusion
"""

from __future__ import annotations

import logging
import re
import time
import uuid
import zlib
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from qdrant_client import QdrantClient, models

from core.common.config import settings
from rag.cache import QueryEmbeddingCache, get_embedding_cache
from rag.embedding import EmbeddingProvider, get_embedding_provider
from rag.query_normalizer import normalize_query
from rag.reranker import BgeRerankerProvider, get_reranker

logger = logging.getLogger(__name__)


def make_deterministic_point_id(source_table: str, source_id: str, chunk_index: int = 0) -> str:
    """Generate a deterministic UUIDv5 Qdrant point ID for idempotent upserts & tombstones."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{source_table}:{source_id}:{chunk_index}"))


ContentType = Literal["concept", "worked_example", "exercise_question"]
QuestionCategory = Literal["gyanmulok", "anudhabon", "cq", "mcq", "numerical", "none"]
LanguageCode = Literal["bn", "en"]

VALID_CONTENT_TYPES = {"concept", "worked_example", "exercise_question"}
VALID_QUESTION_CATEGORIES = {"gyanmulok", "anudhabon", "cq", "mcq", "numerical", "none"}
VALID_LANGUAGES = {"bn", "en"}


@dataclass
class BookChunkPayload:
    """Typed Qdrant payload for a textbook chunk."""

    book_name: str
    subject: str
    chapter_number: int
    topic: str
    language: str
    content_type: str
    question_category: str
    text: str
    printed_page: int = 1
    pdf_page_index: int = 1
    answer_key: str | None = None
    chunk_id: str | None = None
    curriculum_year: int | None = None
    schema_version: str = "2.0"
    updated_at: str | None = None
    figure_caption: str | None = None
    embedding_text: str | None = None
    source_table: str = "chunks"
    chunk_index: int = 0

    def validate(self) -> None:
        if not self.book_name:
            raise ValueError("book_name is required")
        if not self.subject:
            raise ValueError("subject is required")
        if self.language not in VALID_LANGUAGES:
            raise ValueError(
                f"Invalid language '{self.language}'. Must be one of {VALID_LANGUAGES}"
            )
        if self.content_type not in VALID_CONTENT_TYPES:
            raise ValueError(
                f"Invalid content_type '{self.content_type}'. Must be one of {VALID_CONTENT_TYPES}"
            )
        if self.question_category not in VALID_QUESTION_CATEGORIES:
            raise ValueError(
                f"Invalid question_category '{self.question_category}'. "
                f"Must be one of {VALID_QUESTION_CATEGORIES}"
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "book_name": self.book_name,
            "subject": self.subject.lower(),
            "chapter_number": int(self.chapter_number),
            "topic": self.topic,
            "language": self.language,
            "content_type": self.content_type,
            "question_category": self.question_category,
            "text": self.text,
            "printed_page": int(self.printed_page),
            "pdf_page_index": int(self.pdf_page_index),
            "answer_key": self.answer_key,
            "curriculum_year": self.curriculum_year,
            "schema_version": self.schema_version,
            "updated_at": self.updated_at,
            "figure_caption": self.figure_caption,
        }


def compute_sparse_vector(text: str) -> tuple[list[int], list[float]]:
    """Compute deterministic multilingual (Bangla + English) sparse lexical weights.

    Produces sorted unique integer token hashes and sublinear TF weights compatible
    with Qdrant's SparseVector.
    """
    if not text:
        return [], []
    cleaned = re.sub(r"[^\w\u0980-\u09FF\s]", " ", text.lower())
    tokens = [tok for tok in cleaned.split() if len(tok) >= 2]
    if not tokens:
        return [], []
    counts = Counter(tokens)
    index_weights: dict[int, float] = {}
    for tok, freq in counts.items():
        # Deterministic 31-bit positive integer index
        idx = zlib.crc32(tok.encode("utf-8")) & 0x7FFFFFFF
        weight = 1.0 + (freq - 1) * 0.5
        index_weights[idx] = index_weights.get(idx, 0.0) + weight
    sorted_items = sorted(index_weights.items(), key=lambda x: x[0])
    return [k for k, _ in sorted_items], [float(v) for _, v in sorted_items]


class QdrantBookStore:
    """Manages the Qdrant hybrid vector collection for ThinkBuddy decoupled retrieval."""

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        collection_name: str | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        client: QdrantClient | None = None,
        reranker: BgeRerankerProvider | None = None,
        embedding_cache: QueryEmbeddingCache | None = None,
    ) -> None:
        self.url = url or settings.QDRANT_URL
        self.api_key = api_key if api_key is not None else settings.QDRANT_API_KEY
        self.collection_name = collection_name or settings.QDRANT_COLLECTION_NAME
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.reranker = reranker or get_reranker()
        self.embedding_cache = embedding_cache or get_embedding_cache()
        self.last_cache_hit: bool = False
        self.last_timings: dict[str, float | bool] = {
            "embed_ms": 0.0,
            "qdrant_ms": 0.0,
            "rerank_ms": 0.0,
            "cache_hit": False,
        }
        self._collection_ensured = False
        if client is not None:
            self.client = client
        elif self.url == ":memory:":
            self.client = QdrantClient(":memory:")
        else:
            self.client = QdrantClient(url=self.url, api_key=self.api_key or None)

    def ensure_collection(self) -> None:
        """Create the typed hybrid collection and payload indexes if not already present."""
        if self._collection_ensured:
            return
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in existing:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": models.VectorParams(
                        size=self.embedding_provider.dimension,
                        distance=models.Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    "sparse": models.SparseVectorParams(
                        index=models.SparseIndexParams(on_disk=False)
                    )
                },
            )
            logger.info("Created Qdrant hybrid collection '%s'", self.collection_name)

        # Ensure payload indexes exist for fast filtered hybrid search
        keyword_fields = [
            "book_name",
            "subject",
            "content_type",
            "question_category",
            "language",
            "topic",
            "schema_version",
        ]
        for field_name in keyword_fields:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name=field_name,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        for int_field in ("chapter_number", "curriculum_year"):
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name=int_field,
                field_schema=models.PayloadSchemaType.INTEGER,
            )
        self._collection_ensured = True

    def _is_missing_collection_error(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return "not found" in msg or "doesn't exist" in msg or "404" in msg

    async def upsert_chunks(self, chunks: list[BookChunkPayload]) -> int:
        """Embed (dense + sparse) and upsert typed textbook chunks into Qdrant."""
        if not chunks:
            return 0
        self.ensure_collection()
        texts = [c.embedding_text or c.text for c in chunks]
        dense_vectors = await self.embedding_provider.embed_documents(texts)

        points: list[models.PointStruct] = []
        for chunk, dense_vec in zip(chunks, dense_vectors, strict=True):
            sparse_idx, sparse_val = compute_sparse_vector(chunk.embedding_text or chunk.text)
            point_id = (
                make_deterministic_point_id(chunk.source_table, chunk.chunk_id, chunk.chunk_index)
                if chunk.chunk_id
                else str(uuid.uuid4())
            )
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector={
                        "dense": dense_vec,
                        "sparse": models.SparseVector(indices=sparse_idx, values=sparse_val),
                    },
                    payload=chunk.to_dict(),
                )
            )

        for i in range(0, len(points), 100):
            batch = points[i : i + 100]
            try:
                self.client.upsert(collection_name=self.collection_name, points=batch)
            except Exception as exc:
                if self._is_missing_collection_error(exc):
                    self._collection_ensured = False
                    self.ensure_collection()
                    self.client.upsert(collection_name=self.collection_name, points=batch)
                else:
                    raise
        return len(points)

    def _build_filter(
        self,
        *,
        book_name: str | None = None,
        subject: str | None = None,
        chapter_number: int | None = None,
        topic: str | None = None,
        language: str | None = None,
        content_types: list[str] | None = None,
        question_category: str | None = None,
    ) -> models.Filter | None:
        must: list[models.Condition] = []
        if book_name:
            must.append(
                models.FieldCondition(key="book_name", match=models.MatchValue(value=book_name))
            )
        if subject:
            must.append(
                models.FieldCondition(key="subject", match=models.MatchValue(value=subject.lower()))
            )
        if chapter_number is not None:
            must.append(
                models.FieldCondition(
                    key="chapter_number", match=models.MatchValue(value=int(chapter_number))
                )
            )
        if topic:
            must.append(models.FieldCondition(key="topic", match=models.MatchValue(value=topic)))
        if language:
            must.append(
                models.FieldCondition(key="language", match=models.MatchValue(value=language))
            )
        if content_types:
            if len(content_types) == 1:
                must.append(
                    models.FieldCondition(
                        key="content_type", match=models.MatchValue(value=content_types[0])
                    )
                )
            else:
                must.append(
                    models.FieldCondition(
                        key="content_type", match=models.MatchAny(any=content_types)
                    )
                )
        if question_category:
            must.append(
                models.FieldCondition(
                    key="question_category", match=models.MatchValue(value=question_category)
                )
            )
        return models.Filter(must=must) if must else None

    async def hybrid_search(
        self,
        query: str,
        *,
        book_name: str | None = None,
        subject: str | None = None,
        chapter_number: int | None = None,
        topic: str | None = None,
        language: str | None = None,
        content_types: list[str] | None = None,
        question_category: str | None = None,
        top_k: int = 4,
        use_reranker: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Run filtered hybrid search (BGE-M3 dense + sparse RRF fusion + Stage-2 reranking)."""
        self.ensure_collection()
        norm_query = normalize_query(query)
        qfilter = self._build_filter(
            book_name=book_name,
            subject=subject,
            chapter_number=chapter_number,
            topic=topic,
            language=language,
            content_types=content_types,
            question_category=question_category,
        )

        t_embed_start = time.perf_counter()
        cached_vec = self.embedding_cache.get(norm_query)
        if cached_vec is not None:
            dense_vec, sparse_idx, sparse_val = cached_vec
            self.last_cache_hit = True
            embed_ms = 0.0
        else:
            dense_vec = await self.embedding_provider.embed_query(norm_query)
            sparse_idx, sparse_val = compute_sparse_vector(norm_query)
            self.embedding_cache.set(norm_query, dense_vec, sparse_idx, sparse_val)
            self.last_cache_hit = False
            embed_ms = (time.perf_counter() - t_embed_start) * 1000.0

        should_rerank = self.reranker.enabled if use_reranker is None else bool(use_reranker)
        default_cand_k = settings.RAG_RERANKER_CANDIDATE_K if should_rerank else max(top_k, 1)
        candidate_k = max(top_k, default_cand_k) if should_rerank else max(top_k, 1)

        prefetch = [
            models.Prefetch(
                query=dense_vec,
                using="dense",
                filter=qfilter,
                limit=max(candidate_k * 2, 25),
            )
        ]
        if sparse_idx:
            prefetch.append(
                models.Prefetch(
                    query=models.SparseVector(indices=sparse_idx, values=sparse_val),
                    using="sparse",
                    filter=qfilter,
                    limit=max(candidate_k * 2, 25),
                )
            )

        t_qdrant_start = time.perf_counter()
        try:
            res = self.client.query_points(
                collection_name=self.collection_name,
                prefetch=prefetch,
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=candidate_k,
                with_payload=True,
            )
        except Exception as exc:
            if self._is_missing_collection_error(exc):
                self._collection_ensured = False
                self.ensure_collection()
                res = self.client.query_points(
                    collection_name=self.collection_name,
                    prefetch=prefetch,
                    query=models.FusionQuery(fusion=models.Fusion.RRF),
                    limit=candidate_k,
                    with_payload=True,
                )
            else:
                raise
        qdrant_ms = (time.perf_counter() - t_qdrant_start) * 1000.0

        hits: list[dict[str, Any]] = []
        for pt in res.points:
            payload = dict(pt.payload or {})
            payload["id"] = str(pt.id)
            payload["rrf_score"] = float(pt.score or 0.0)
            payload["score"] = float(pt.score or 0.0)
            hits.append(payload)

        t_rerank_start = time.perf_counter()
        if should_rerank:
            final_hits = self.reranker.rerank(norm_query, hits, top_k=top_k)
        else:
            final_hits = hits[:top_k]
        rerank_ms = (time.perf_counter() - t_rerank_start) * 1000.0

        self.last_timings = {
            "embed_ms": embed_ms,
            "qdrant_ms": qdrant_ms,
            "rerank_ms": rerank_ms,
            "cache_hit": self.last_cache_hit,
        }
        return final_hits

    def delete_points(self, point_ids: list[str]) -> int:
        """Delete points by deterministic ID (quarantine/soft-delete tombstoning)."""
        if not point_ids:
            return 0
        self.ensure_collection()
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.PointIdsList(points=point_ids),
        )
        return len(point_ids)

    def scroll_filtered(
        self,
        *,
        book_name: str | None = None,
        subject: str | None = None,
        chapter_number: int | None = None,
        topic: str | None = None,
        language: str | None = None,
        content_types: list[str] | None = None,
        question_category: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Pure metadata-filtered scroll for retrieving structured questions or concepts."""
        self.ensure_collection()
        qfilter = self._build_filter(
            book_name=book_name,
            subject=subject,
            chapter_number=chapter_number,
            topic=topic,
            language=language,
            content_types=content_types,
            question_category=question_category,
        )
        try:
            points, _ = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=qfilter,
                limit=limit,
                with_payload=True,
            )
        except Exception as exc:
            if self._is_missing_collection_error(exc):
                self._collection_ensured = False
                self.ensure_collection()
                points, _ = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=qfilter,
                    limit=limit,
                    with_payload=True,
                )
            else:
                raise
        results: list[dict[str, Any]] = []
        for pt in points:
            payload = dict(pt.payload or {})
            payload["id"] = str(pt.id)
            results.append(payload)
        return results


_default_qdrant_store: QdrantBookStore | None = None


def get_qdrant_store(
    url: str | None = None,
    collection_name: str | None = None,
) -> QdrantBookStore:
    """Return singleton QdrantBookStore or a custom instance."""
    global _default_qdrant_store
    if url is not None or collection_name is not None:
        return QdrantBookStore(url=url, collection_name=collection_name)
    if _default_qdrant_store is None:
        _default_qdrant_store = QdrantBookStore()
    return _default_qdrant_store
