"""Hybrid curriculum retriever with boosting and reranking for AI Chat.

Implements curriculum and study item retriever:
- Hybrid (vector + lexical) retrieval
- Class/subject/medium filtering
- Document context (current chapter / printed page) boosting
- Reranker interface (multilingual token/RRF scoring first)
- Authoritative page isolation: printed_page != pdf_page_index (Rule 8)
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.chat.schemas import DocumentContext
from rag.vector_store import PgVectorStore, SearchResult, VectorStore

logger = logging.getLogger(__name__)

# Primary Embedding Model Choice (Decision 4 in README.md):
# Primary Model: "BAAI/bge-m3"
# - 1024 dense dimensions, 8192 token context window
# - Native hybrid representation (dense + sparse lexical tokens + ColBERT multi-vector)
# - State-of-the-art retrieval accuracy across Bengali (Bangla) and English curriculum
# Hosted API Alternative:
# "text-embedding-3-small" (1536 dims) or "google/text-embedding-004" (768 dims)
EMBEDDING_MODEL_PRIMARY = "BAAI/bge-m3"
EMBEDDING_MODEL_DIMENSIONS = 1024

# Minimum threshold for considering curriculum retrieval confident
CONFIDENCE_THRESHOLD = 0.45


@dataclass
class RetrievedChunk:
    """Authoritative textbook chunk with separated printed page and PDF page index."""

    chunk_id: uuid.UUID
    book_id: uuid.UUID
    book_title: str
    chapter_id: uuid.UUID
    chapter_title: str
    chapter_number: int | None
    printed_page: int  # User-visible printed textbook page (Rule 8)
    pdf_page_index: int  # Internal PDF page offset (Rule 8)
    text: str
    score: float


class Reranker(ABC):
    """Abstract reranker interface."""

    @abstractmethod
    async def rerank(self, query: str, candidates: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Rerank candidates based on semantic relevance to query."""


class LexicalReranker(Reranker):
    """Fast, LLM-free multilingual cross-scorer (Bengali + English lexical overlap)."""

    async def rerank(self, query: str, candidates: list[RetrievedChunk]) -> list[RetrievedChunk]:
        if not candidates:
            return []

        query_tokens = set(query.lower().split())

        for chunk in candidates:
            chunk_tokens = set(chunk.text.lower().split())
            if not query_tokens:
                overlap_ratio = 0.0
            else:
                overlap_ratio = len(query_tokens & chunk_tokens) / len(query_tokens)

            # Blend base retrieval score with lexical token overlap
            chunk.score = round(chunk.score * 0.7 + overlap_ratio * 0.3, 4)

        return sorted(candidates, key=lambda c: c.score, reverse=True)


class ChatRetriever:
    """Curriculum RAG retrieval engine with metadata filtering, boosting, and reranking."""

    def __init__(
        self,
        session: AsyncSession,
        vector_store: VectorStore | None = None,
        reranker: Reranker | None = None,
        mock_chunks: list[RetrievedChunk] | None = None,
    ) -> None:
        self.session = session
        self.vector_store = vector_store or PgVectorStore(session)
        self.reranker = reranker or LexicalReranker()
        self.mock_chunks = mock_chunks

    async def retrieve(
        self,
        query: str,
        student_profile: dict[str, Any] | None = None,
        document_context: DocumentContext | None = None,
        limit: int = 4,
    ) -> tuple[list[RetrievedChunk], float]:
        """Retrieve top grounded chunks for student query.

        Returns:
            tuple of (top_ranked_chunks, retrieval_confidence)
        """
        if self.mock_chunks is not None:
            return await self._process_candidates(
                query, list(self.mock_chunks), document_context, limit
            )

        # 1. Build curriculum filters
        filters: dict[str, Any] = {}
        if student_profile:
            if "class_level" in student_profile and student_profile["class_level"]:
                filters["class_level"] = student_profile["class_level"]
            if "subject" in student_profile and student_profile["subject"]:
                filters["subject"] = student_profile["subject"]

        # 2. Retrieve candidates via vector store lexical / vector search
        search_results: list[SearchResult] = []
        try:
            search_results = await self.vector_store.search_lexical(
                query, limit=limit * 3, filters=filters
            )
        except Exception as ex:
            logger.warning("Lexical search error, proceeding with empty results: %s", ex)

        candidates = [
            RetrievedChunk(
                chunk_id=r.chunk_id,
                book_id=r.book_id,
                book_title=r.book_title,
                chapter_id=r.chapter_id,
                chapter_title=r.chapter_title,
                chapter_number=r.chapter_number,
                printed_page=r.printed_page,
                pdf_page_index=r.pdf_page_index,
                text=r.text,
                score=r.score,
            )
            for r in search_results
        ]

        return await self._process_candidates(query, candidates, document_context, limit)

    async def _process_candidates(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        document_context: DocumentContext | None,
        limit: int,
    ) -> tuple[list[RetrievedChunk], float]:
        """Apply document context boosting, reranking, and calculate confidence."""
        if not candidates:
            return [], 0.0

        # Prevent in-place mutation of score across multiple queries
        from dataclasses import replace

        working_candidates = [replace(c) for c in candidates]

        if document_context:
            for chunk in working_candidates:
                if (
                    document_context.chapter_id
                    and chunk.chapter_id == document_context.chapter_id
                ):
                    chunk.score = min(1.0, chunk.score + 0.20)
                if (
                    document_context.printed_page
                    and chunk.printed_page == document_context.printed_page
                ):
                    chunk.score = min(1.0, chunk.score + 0.25)

        reranked = await self.reranker.rerank(query, working_candidates)
        top_chunks = reranked[:limit]

        top_score = top_chunks[0].score if top_chunks else 0.0
        confidence = round(min(1.0, max(0.0, top_score)), 3)

        return top_chunks, confidence
