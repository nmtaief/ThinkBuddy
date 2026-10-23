"""VectorStore interface and PostgreSQL + pgvector hybrid retrieval implementation."""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Individual retrieval hit with complete citation metadata."""

    chunk_id: uuid.UUID
    book_id: uuid.UUID
    chapter_id: uuid.UUID
    concept_id: uuid.UUID | None
    book_title: str
    chapter_number: int
    chapter_title: str
    printed_page: int
    pdf_page_index: int
    text: str
    language: str
    score: float
    dense_score: float
    lexical_score: float


class VectorStore(ABC):
    """Abstract interface for dense and hybrid curriculum chunk storage."""

    @abstractmethod
    async def search_hybrid(
        self,
        query_text: str,
        query_vector: list[float],
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Perform hybrid search combining dense vector similarity and lexical matching."""

    @abstractmethod
    async def search_vector(
        self,
        query_vector: list[float],
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Perform pure dense vector cosine similarity search."""

    @abstractmethod
    async def search_lexical(
        self,
        query_text: str,
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Perform pure lexical full-text and trigram search."""


class PgVectorStore(VectorStore):
    """PostgreSQL + pgvector implementation with HNSW and trigram/tsvector lexical fusion."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search_hybrid(
        self,
        query_text: str,
        query_vector: list[float],
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Execute hybrid search using Reciprocal Rank Fusion (RRF) over dense and lexical hits."""
        # 1. Fetch dense candidates
        dense_hits = await self.search_vector(query_vector, limit=limit * 3, filters=filters)

        # 2. Fetch lexical candidates
        lexical_hits = await self.search_lexical(query_text, limit=limit * 3, filters=filters)

        # 3. Reciprocal Rank Fusion (RRF) with k=60
        k = 60.0
        rrf_scores: dict[uuid.UUID, float] = {}
        all_hits: dict[uuid.UUID, SearchResult] = {}

        for rank, hit in enumerate(dense_hits):
            all_hits[hit.chunk_id] = hit
            rrf_scores[hit.chunk_id] = rrf_scores.get(hit.chunk_id, 0.0) + (1.0 / (k + rank + 1))

        for rank, hit in enumerate(lexical_hits):
            if hit.chunk_id in all_hits:
                existing = all_hits[hit.chunk_id]
                existing.lexical_score = hit.lexical_score
            else:
                all_hits[hit.chunk_id] = hit
            rrf_scores[hit.chunk_id] = rrf_scores.get(hit.chunk_id, 0.0) + (1.0 / (k + rank + 1))

        # Sort by final fused RRF score descending
        sorted_chunk_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

        results: list[SearchResult] = []
        for cid in sorted_chunk_ids[:limit]:
            item = all_hits[cid]
            item.score = round(rrf_scores[cid] * 100.0, 4)  # scale for readability
            results.append(item)

        return results

    async def search_vector(
        self,
        query_vector: list[float],
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Perform dense vector cosine similarity search."""
        vector_str = f"[{','.join(f'{x:.6f}' for x in query_vector)}]"

        where_clauses = ["c.retrievable = true", "c.embedding IS NOT NULL"]
        params: dict[str, Any] = {"vec": vector_str, "lim": limit}

        if filters:
            if "book_id" in filters:
                where_clauses.append("c.book_id = :book_id")
                params["book_id"] = str(filters["book_id"])
            if "chapter_id" in filters:
                where_clauses.append("c.chapter_id = :chapter_id")
                params["chapter_id"] = str(filters["chapter_id"])
            if "class_level" in filters:
                where_clauses.append("b.class_level = :class_level")
                params["class_level"] = filters["class_level"]
            if "subject" in filters:
                where_clauses.append("b.subject = :subject")
                params["subject"] = filters["subject"]
            if "printed_page" in filters:
                where_clauses.append("c.printed_page = :printed_page")
                params["printed_page"] = filters["printed_page"]

        where_sql = " AND ".join(where_clauses)

        query_template = """
            SELECT
                c.id AS chunk_id,
                c.book_id,
                c.chapter_id,
                c.concept_id,
                b.title AS book_title,
                ch.number AS chapter_number,
                ch.title AS chapter_title,
                c.printed_page,
                c.pdf_page_index,
                c.text,
                c.language,
                1 - (c.embedding <=> CAST(:vec AS vector)) AS dense_score
            FROM chunks c
            JOIN books b ON b.id = c.book_id
            JOIN chapters ch ON ch.id = c.chapter_id
            WHERE __WHERE_CLAUSE__
            ORDER BY c.embedding <=> CAST(:vec AS vector) ASC
            LIMIT :lim
        """
        sql = query_template.replace("__WHERE_CLAUSE__", where_sql)

        result = await self.session.execute(text(sql), params)
        rows = result.fetchall()

        return [
            SearchResult(
                chunk_id=row.chunk_id,
                book_id=row.book_id,
                chapter_id=row.chapter_id,
                concept_id=row.concept_id,
                book_title=row.book_title,
                chapter_number=row.chapter_number,
                chapter_title=row.chapter_title,
                printed_page=row.printed_page,
                pdf_page_index=row.pdf_page_index,
                text=row.text,
                language=row.language,
                score=round(float(row.dense_score), 4),
                dense_score=round(float(row.dense_score), 4),
                lexical_score=0.0,
            )
            for row in rows
        ]

    async def search_lexical(
        self,
        query_text: str,
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Perform lexical full-text (tsvector) and trigram similarity search."""
        cleaned_query = query_text.strip()
        if not cleaned_query:
            return []

        where_clauses = ["c.retrievable = true"]
        params: dict[str, Any] = {"q": cleaned_query, "lim": limit}

        if filters:
            if "book_id" in filters:
                where_clauses.append("c.book_id = :book_id")
                params["book_id"] = str(filters["book_id"])
            if "chapter_id" in filters:
                where_clauses.append("c.chapter_id = :chapter_id")
                params["chapter_id"] = str(filters["chapter_id"])
            if "class_level" in filters:
                where_clauses.append("b.class_level = :class_level")
                params["class_level"] = filters["class_level"]
            if "subject" in filters:
                where_clauses.append("b.subject = :subject")
                params["subject"] = filters["subject"]
            if "printed_page" in filters:
                where_clauses.append("c.printed_page = :printed_page")
                params["printed_page"] = filters["printed_page"]

        where_sql = " AND ".join(where_clauses)

        # Combines ts_rank with trigram similarity for high-recall Unicode and Bangla search
        lexical_template = """
            SELECT
                c.id AS chunk_id,
                c.book_id,
                c.chapter_id,
                c.concept_id,
                b.title AS book_title,
                ch.number AS chapter_number,
                ch.title AS chapter_title,
                c.printed_page,
                c.pdf_page_index,
                c.text,
                c.language,
                (
                    similarity(c.text, :q) * 0.7
                    + COALESCE(ts_rank_cd(c.tsv, plainto_tsquery('simple', :q)), 0) * 0.3
                ) AS lexical_score
            FROM chunks c
            JOIN books b ON b.id = c.book_id
            JOIN chapters ch ON ch.id = c.chapter_id
            WHERE __WHERE_CLAUSE__
              AND (similarity(c.text, :q) > 0.05 OR c.tsv @@ plainto_tsquery('simple', :q))
            ORDER BY lexical_score DESC
            LIMIT :lim
        """
        sql = lexical_template.replace("__WHERE_CLAUSE__", where_sql)

        result = await self.session.execute(text(sql), params)
        rows = result.fetchall()

        return [
            SearchResult(
                chunk_id=row.chunk_id,
                book_id=row.book_id,
                chapter_id=row.chapter_id,
                concept_id=row.concept_id,
                book_title=row.book_title,
                chapter_number=row.chapter_number,
                chapter_title=row.chapter_title,
                printed_page=row.printed_page,
                pdf_page_index=row.pdf_page_index,
                text=row.text,
                language=row.language,
                score=round(float(row.lexical_score), 4),
                dense_score=0.0,
                lexical_score=round(float(row.lexical_score), 4),
            )
            for row in rows
        ]
