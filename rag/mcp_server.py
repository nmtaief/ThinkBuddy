"""FastMCP Server exposing ThinkBuddy's 3 Decoupled Retrieval Tools.

Run standalone via:
    python -m rag.mcp_server
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from rag.retrieval_tools import (
    get_book_questions as _get_book_questions,
)
from rag.retrieval_tools import (
    get_syllabus_scope as _get_syllabus_scope,
)
from rag.retrieval_tools import (
    get_topic_concepts as _get_topic_concepts,
)

mcp = FastMCP("ThinkBuddy Curriculum RAG Tools")


@mcp.tool()
async def get_syllabus_scope(book_name: str, subject: str, topic_query: str) -> dict[str, Any]:
    """Query the NCTB/HSC Structural Syllabus Map for chapter boundaries and allowed formulas."""
    return await _get_syllabus_scope(
        book_name=book_name,
        subject=subject,
        topic_query=topic_query,
    )


@mcp.tool()
async def get_topic_concepts(
    topic: str,
    query: str,
    language: str = "bn",
    top_k: int = 4,
) -> list[dict[str, Any]]:
    """Run hybrid BGE-M3 search in Qdrant filtered by content_type='concept'."""
    return await _get_topic_concepts(
        topic=topic,
        query=query,
        language=language,
        top_k=top_k,
    )


@mcp.tool()
async def get_book_questions(
    topic: str,
    question_category: str | None = None,
    count: int = 3,
) -> list[dict[str, Any]]:
    """Retrieve sample textbook questions (CQ/MCQ/Gyanmulok/Anudhabon) without answer keys."""
    return await _get_book_questions(
        topic=topic,
        question_category=question_category,
        count=count,
    )


if __name__ == "__main__":
    mcp.run()
