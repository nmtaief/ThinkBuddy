"""3 Targeted Retrieval Tools for Decoupled Retrieval-as-a-Tool Architecture.

Exposes:
1. get_syllabus_scope(book_name, subject, topic_query) -> dict
2. get_topic_concepts(topic, query, language="bn", top_k=4) -> list[dict]
3. get_book_questions(topic, question_category=None, count=3) -> list[dict]

Standing Rules enforced:
- Rule 6: Never return answer_key / correct_answer from get_book_questions.
- Rule 8: Return only printed_page (never pdf_page_index).
"""

from __future__ import annotations

import logging
from typing import Any

from rag.qdrant_store import QdrantBookStore, get_qdrant_store
from rag.query_normalizer import normalize_query
from rag.syllabus_index import SyllabusIndexStore, get_syllabus_index_store

logger = logging.getLogger(__name__)

# Canonical provider-agnostic tool definitions
DECOUPLED_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_syllabus_scope",
        "description": (
            "Query the Structural Syllabus Map for an NCTB/HSC textbook to inspect chapter "
            "boundaries, allowed subtopics, key formulas, and prerequisite topics. Always call "
            "this first when a student asks about a topic so explanations stay within syllabus depth."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "book_name": {
                    "type": "string",
                    "description": "Textbook name or identifier (e.g. 'HSC Physics 1st Paper', 'Class 8 Math').",
                },
                "subject": {
                    "type": "string",
                    "description": "Subject name (e.g. 'physics', 'math', 'chemistry', 'biology').",
                },
                "topic_query": {
                    "type": "string",
                    "description": "Topic, chapter title, or concept keyword in Bangla or English.",
                },
            },
            "required": ["book_name", "subject", "topic_query"],
        },
    },
    {
        "name": "get_topic_concepts",
        "description": (
            "Run filtered hybrid search (BGE-M3 dense + sparse) on textbook concepts "
            "(content_type == 'concept') to align with exact NCTB/HSC textbook terminology, "
            "notation, and Bangla/English definitions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic name to filter or focus on (e.g. 'ভেক্টর', 'Vector').",
                },
                "query": {
                    "type": "string",
                    "description": "Semantic search query describing the concept or definition needed.",
                },
                "language": {
                    "type": "string",
                    "enum": ["bn", "en"],
                    "description": "Textbook language ('bn' or 'en'). Defaults to 'bn'.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of concept items to return (default 4).",
                },
            },
            "required": ["topic", "query"],
        },
    },
    {
        "name": "get_book_questions",
        "description": (
            "Retrieve sample textbook exercise questions and worked examples "
            "(content_type in ['exercise_question', 'worked_example']) to see how the book "
            "frames CQ, MCQ, Gyanmulok, Anudhabon, or numerical questions. Final answer keys "
            "are stripped by default."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic name to retrieve sample questions for.",
                },
                "question_category": {
                    "type": "string",
                    "enum": ["gyanmulok", "anudhabon", "cq", "mcq", "numerical"],
                    "description": "Optional question style filter.",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of sample questions to return (default 3).",
                },
            },
            "required": ["topic"],
        },
    },
]


class DecoupledRetrievalTools:
    """Implements the 3 decoupled retrieval tools backed by SyllabusIndexStore and QdrantBookStore."""

    def __init__(
        self,
        qdrant_store: QdrantBookStore | None = None,
        syllabus_store: SyllabusIndexStore | None = None,
    ) -> None:
        self.qdrant_store = qdrant_store or get_qdrant_store()
        self.syllabus_store = syllabus_store or get_syllabus_index_store()

    async def get_syllabus_scope(
        self,
        book_name: str,
        subject: str,
        topic_query: str,
    ) -> dict[str, Any]:
        """Query the Structural Syllabus Map for chapter boundaries and allowed formulas."""
        normalized_topic = normalize_query(topic_query)
        logger.debug("get_syllabus_scope raw_query=%r normalized=%r", topic_query, normalized_topic)
        return self.syllabus_store.query_scope(
            book_name=book_name,
            subject=subject,
            topic_query=normalized_topic,
        )

    async def get_topic_concepts(
        self,
        topic: str,
        query: str,
        language: str = "bn",
        top_k: int = 4,
    ) -> list[dict[str, Any]]:
        """Run BGE-M3 hybrid search in Qdrant filtered strictly to content_type == 'concept'."""
        lang = language if language in ("bn", "en") else "bn"
        k = max(1, min(int(top_k), 12))
        raw_search = f"{topic} {query}".strip() if topic else query
        search_query = normalize_query(raw_search)
        logger.debug("get_topic_concepts raw_query=%r normalized=%r", raw_search, search_query)

        # Try exact topic filter first; fall back to unfiltered topic semantic search if sparse
        hits = await self.qdrant_store.hybrid_search(
            query=search_query,
            topic=topic or None,
            language=lang,
            content_types=["concept"],
            top_k=k,
        )
        if not hits and topic:
            hits = await self.qdrant_store.hybrid_search(
                query=search_query,
                language=lang,
                content_types=["concept"],
                top_k=k,
            )

        results: list[dict[str, Any]] = []
        for hit in hits:
            results.append(
                {
                    "id": hit.get("id"),
                    "book_name": hit.get("book_name"),
                    "subject": hit.get("subject"),
                    "chapter_number": hit.get("chapter_number"),
                    "topic": hit.get("topic"),
                    "language": hit.get("language"),
                    "content_type": hit.get("content_type"),
                    "printed_page": hit.get("printed_page"),
                    "concept_summary": hit.get("text", ""),
                    "score": round(float(hit.get("score", 0.0)), 4),
                }
            )
        return results

    async def get_book_questions(
        self,
        topic: str,
        question_category: str | None = None,
        count: int = 3,
    ) -> list[dict[str, Any]]:
        """Retrieve sample question stems/patterns from Qdrant without exposing final answer keys."""
        limit = max(1, min(int(count), 10))
        q_cat = question_category.lower() if question_category else None
        norm_topic = normalize_query(topic or "question")
        logger.debug("get_book_questions raw_topic=%r normalized=%r", topic, norm_topic)

        hits = await self.qdrant_store.hybrid_search(
            query=norm_topic,
            topic=topic or None,
            content_types=["exercise_question", "worked_example"],
            question_category=q_cat,
            top_k=limit,
        )
        if not hits and topic:
            hits = await self.qdrant_store.hybrid_search(
                query=norm_topic,
                content_types=["exercise_question", "worked_example"],
                question_category=q_cat,
                top_k=limit,
            )

        sanitized: list[dict[str, Any]] = []
        for hit in hits:
            # Rule 6 & Rule 8: strip answer_key and pdf_page_index strictly
            sanitized.append(
                {
                    "id": hit.get("id"),
                    "book_name": hit.get("book_name"),
                    "subject": hit.get("subject"),
                    "chapter_number": hit.get("chapter_number"),
                    "topic": hit.get("topic"),
                    "language": hit.get("language"),
                    "content_type": hit.get("content_type"),
                    "question_category": hit.get("question_category"),
                    "printed_page": hit.get("printed_page"),
                    "question_stem": hit.get("text", ""),
                }
            )
        return sanitized

    async def execute(self, tool_name: str, args: dict[str, Any] | None) -> Any:
        """Dispatch a tool call by name."""
        params = args or {}
        if tool_name == "get_syllabus_scope":
            return await self.get_syllabus_scope(
                book_name=str(params.get("book_name", "")),
                subject=str(params.get("subject", "")),
                topic_query=str(params.get("topic_query", "")),
            )
        if tool_name == "get_topic_concepts":
            return await self.get_topic_concepts(
                topic=str(params.get("topic", "")),
                query=str(params.get("query", "")),
                language=str(params.get("language", "bn")),
                top_k=int(params.get("top_k", 4)),
            )
        if tool_name == "get_book_questions":
            return await self.get_book_questions(
                topic=str(params.get("topic", "")),
                question_category=params.get("question_category"),
                count=int(params.get("count", 3)),
            )
        raise ValueError(f"Unknown decoupled retrieval tool: {tool_name}")


_default_tools: DecoupledRetrievalTools | None = None


def get_decoupled_tools() -> DecoupledRetrievalTools:
    global _default_tools
    if _default_tools is None:
        _default_tools = DecoupledRetrievalTools()
    return _default_tools


async def get_syllabus_scope(book_name: str, subject: str, topic_query: str) -> dict[str, Any]:
    return await get_decoupled_tools().get_syllabus_scope(book_name, subject, topic_query)


async def get_topic_concepts(
    topic: str,
    query: str,
    language: str = "bn",
    top_k: int = 4,
) -> list[dict[str, Any]]:
    return await get_decoupled_tools().get_topic_concepts(topic, query, language, top_k)


async def get_book_questions(
    topic: str,
    question_category: str | None = None,
    count: int = 3,
) -> list[dict[str, Any]]:
    return await get_decoupled_tools().get_book_questions(topic, question_category, count)
