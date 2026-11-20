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
        from core.common.config import settings
        if settings.EMBEDDING_PROVIDER.lower() in ("mock", "test"):
            logger.warning(
                "Dense vector search disabled: EMBEDDING_PROVIDER is '%s'. "
                "Falling back to pure lexical retrieval to prevent mock vector noise.",
                settings.EMBEDDING_PROVIDER
            )
            return await self.search_lexical(query_text, limit=limit, filters=filters)

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
            if "chapter" in filters and filters["chapter"]:
                try:
                    ch_num = int(filters["chapter"])
                    where_clauses.append("ch.number = :filter_chapter_num")
                    params["filter_chapter_num"] = ch_num
                except (ValueError, TypeError):
                    where_clauses.append("ch.title ILIKE :filter_chapter_title")
                    params["filter_chapter_title"] = f"%{filters['chapter']}%"
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
        import re
        from rag.bengali_normalizer import normalize_text, expand_query_for_tsquery

        cleaned_query = normalize_text(query_text)
        if not cleaned_query:
            return []

        # Extract page number mention (e.g. "page 58", "pg 58", "পৃষ্ঠা ৫৮", "৫৮ নং পৃষ্ঠা")
        page_match = re.search(r'(?:page|pg|পৃষ্ঠা|পেইজ)\s*[:=]?\s*(\d+)', cleaned_query, re.IGNORECASE)
        if not page_match:
            page_match = re.search(r'\b(\d+)\s*(?:নং\s*)?(?:পৃষ্ঠা|page)\b', cleaned_query, re.IGNORECASE)
        ext_page = int(page_match.group(1)) if page_match else -1

        # Extract chapter number mention (e.g. "chapter 2", "ch 2", "first chapter", "1st chapter", "অধ্যায় ২", "প্রথম অধ্যায়")
        ordinals = {
            "first": 1, "1st": 1, "প্রথম": 1, "১ম": 1,
            "second": 2, "2nd": 2, "দ্বিতীয়": 2, "দ্বিতীয়": 2, "২য়": 2,
            "third": 3, "3rd": 3, "তৃতীয়": 3, "তৃতীয়": 3, "৩য়": 3,
            "fourth": 4, "4th": 4, "চতুর্থ": 4, "৪র্থ": 4,
            "fifth": 5, "5th": 5, "পঞ্চম": 5, "৫ম": 5,
            "sixth": 6, "6th": 6, "ষষ্ঠ": 6, "৬ষ্ঠ": 6,
            "seventh": 7, "7th": 7, "সপ্তম": 7, "৭ম": 7,
            "eighth": 8, "8th": 8, "অষ্টম": 8, "৮ম": 8,
            "ninth": 9, "9th": 9, "নবম": 9, "৯ম": 9,
            "tenth": 10, "10th": 10, "দশম": 10, "১০ম": 10,
            "eleventh": 11, "11th": 11, "একাদশ": 11, "১১শ": 11,
            "twelfth": 12, "12th": 12, "দ্বাদশ": 12, "১২শ": 12,
            "thirteenth": 13, "13th": 13, "ত্রয়োদশ": 13, "১৩শ": 13,
            "fourteenth": 14, "14th": 14, "চতুর্দশ": 14, "১৪শ": 14,
        }
        chap_match = re.search(r'(?:chapter|ch|অধ্যায়|অধ্যায়|পাঠ)\s*[:=]?\s*(\d+)', cleaned_query, re.IGNORECASE)
        if not chap_match:
            chap_match = re.search(r'\b(\d+)\s*(?:নং\s*)?(?:অধ্যায়|অধ্যায়|chapter|ch)\b', cleaned_query, re.IGNORECASE)
        ext_chapter = int(chap_match.group(1)) if chap_match else -1
        if ext_chapter == -1 and re.search(r'(?:chapter|ch|অধ্যায়|অধ্যায়|পাঠ)', cleaned_query, re.IGNORECASE):
            for word, ch_num in ordinals.items():
                if re.search(rf'(?:\b{word}\s*(?:অধ্যায়|অধ্যায়|chapter|ch)?\b|(?:chapter|ch|অধ্যায়|অধ্যায়)\s*{word}\b)', cleaned_query, re.IGNORECASE):
                    ext_chapter = ch_num
                    break

        if ext_chapter == -1:
            ex_match = re.search(r'(?:অনুশীলনী|onushiloni|exercise|ex)\s*(\d+(?:\.\d+)?)', cleaned_query, re.IGNORECASE)
            if ex_match:
                try:
                    ext_chapter = int(ex_match.group(1).split('.')[0])
                except (ValueError, TypeError):
                    pass
            else:
                dec_match = re.search(r'\b(\d+)\.\d+\b', cleaned_query)
                if dec_match:
                    try:
                        ext_chapter = int(dec_match.group(1))
                    except (ValueError, TypeError):
                        pass

        # Extract class level mention (e.g. "class 8", "class 7", "৮ম শ্রেণি")
        class_match = re.search(r'(?:class|শ্রেণি|শ্রেণী)\s*[:=]?\s*(\d+)', cleaned_query, re.IGNORECASE)
        ext_class = int(class_match.group(1)) if class_match else -1

        # Generic Bengali morphological inflection expansion for tsquery
        expanded_tsquery = expand_query_for_tsquery(cleaned_query)

        # Filter out conversational stopwords for full-text lexical queries
        stopwords = {
            "can", "you", "explain", "me", "tell", "about", "what", "is", "please",
            "help", "with", "the", "a", "an", "book", "of", "in", "for", "to", "how",
            "er", "kon", "konta", "ta", "ki", "je", "te", "kono", "kobe", "kemon",
            "বলো", "বলুন", "আমাকে", "একটু", "সম্পর্কে", "কী", "কি", "বোঝাও", "বুঝিয়ে",
            "দাও", "হলো", "বলতে", "বোঝায়"
        }
        raw_words = [w for w in re.findall(r'[\w]+', cleaned_query) if w.lower() not in stopwords]
        clean_q = " ".join(raw_words) if raw_words else cleaned_query

        where_clauses = ["c.retrievable = true"]
        params: dict[str, Any] = {
            "q": cleaned_query,
            "clean_q": clean_q,
            "expanded_tsquery": expanded_tsquery,
            "ext_page": ext_page,
            "ext_chapter": ext_chapter,
            "ext_class": ext_class,
            "lim": limit,
        }

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
            elif ext_class > 0:
                where_clauses.append("(b.class_level = :ext_class OR :ext_class = -1)")
            if "subject" in filters:
                where_clauses.append("b.subject = :subject")
                params["subject"] = filters["subject"]
            if "chapter" in filters and filters["chapter"]:
                try:
                    ch_num = int(filters["chapter"])
                    where_clauses.append("ch.number = :filter_chapter_num")
                    params["filter_chapter_num"] = ch_num
                except (ValueError, TypeError):
                    where_clauses.append("ch.title ILIKE :filter_chapter_title")
                    params["filter_chapter_title"] = f"%{filters['chapter']}%"
            if "printed_page" in filters:
                where_clauses.append("c.printed_page = :printed_page")
                params["printed_page"] = filters["printed_page"]

        where_sql = " AND ".join(where_clauses)

        # Combines page match, ts_rank, and trigram similarity for high-recall Unicode and Bangla search
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
                    CASE WHEN c.printed_page = :ext_page AND :ext_page > 0 THEN 0.85 ELSE 0.0 END
                    + (CASE WHEN ch.number = :ext_chapter AND :ext_chapter > 0 THEN 0.85 ELSE 0.0 END)
                    + (CASE WHEN (LOWER(b.title) LIKE '%বিজ্ঞান%' OR LOWER(b.subject) LIKE '%science%') AND (LOWER(:q) LIKE '%science%' OR LOWER(:q) LIKE '%বিজ্ঞান%') THEN 0.35 ELSE 0.0 END)
                    + (CASE WHEN (LOWER(b.title) LIKE '%গণিত%' OR LOWER(b.subject) LIKE '%math%') AND (LOWER(:q) LIKE '%math%' OR LOWER(:q) LIKE '%গণিত%') THEN 0.35 ELSE 0.0 END)
                    + (CASE WHEN :expanded_tsquery != '' AND c.tsv @@ to_tsquery('simple', :expanded_tsquery) THEN 0.90
                            WHEN c.tsv @@ plainto_tsquery('simple', :clean_q) OR c.tsv @@ plainto_tsquery('simple', :q) THEN 0.75
                            ELSE 0.0 END)
                    + word_similarity(:clean_q, c.text) * 0.8
                    + word_similarity(:q, c.text) * 0.4
                    + COALESCE(ts_rank_cd(c.tsv, plainto_tsquery('simple', :clean_q)), 0) * 0.5
                ) AS lexical_score
            FROM chunks c
            JOIN books b ON b.id = c.book_id
            JOIN chapters ch ON ch.id = c.chapter_id
            WHERE __WHERE_CLAUSE__
              AND (
                (c.printed_page = :ext_page AND :ext_page > 0)
                OR (ch.number = :ext_chapter AND :ext_chapter > 0)
                OR word_similarity(:clean_q, c.text) > 0.15
                OR word_similarity(:q, c.text) > 0.15
                OR (:expanded_tsquery != '' AND c.tsv @@ to_tsquery('simple', :expanded_tsquery))
                OR c.tsv @@ plainto_tsquery('simple', :clean_q)
                OR c.tsv @@ plainto_tsquery('simple', :q)
              )
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
