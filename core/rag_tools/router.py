"""FastAPI REST router exposing ThinkBuddy's 3 decoupled retrieval tools.

Endpoints (mounted under /v1/rag-tools):
- POST /rag-tools/syllabus-scope
- POST /rag-tools/topic-concepts
- POST /rag-tools/book-questions
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from rag.retrieval_tools import get_book_questions, get_syllabus_scope, get_topic_concepts

router = APIRouter(prefix="/rag-tools", tags=["RAG Tools"])


class SyllabusScopeRequest(BaseModel):
    book_name: str = Field(..., description="NCTB/HSC textbook name")
    subject: str = Field(..., description="Subject name")
    topic_query: str = Field(..., description="Topic or chapter query")


class TopicConceptsRequest(BaseModel):
    topic: str = Field(..., description="Topic name")
    query: str = Field(..., description="Concept search query")
    language: Literal["bn", "en"] = Field(default="bn", description="Language ('bn' or 'en')")
    top_k: int = Field(default=4, ge=1, le=12, description="Max concept results")


class BookQuestionsRequest(BaseModel):
    topic: str = Field(..., description="Topic name")
    question_category: Literal["gyanmulok", "anudhabon", "cq", "mcq", "numerical"] | None = Field(
        default=None,
        description="Optional question style filter",
    )
    count: int = Field(default=3, ge=1, le=10, description="Number of sample questions")


@router.post("/syllabus-scope", summary="Query Structural Syllabus Map for NCTB/HSC boundaries")
async def api_get_syllabus_scope(payload: SyllabusScopeRequest) -> dict[str, Any]:
    return await get_syllabus_scope(
        book_name=payload.book_name,
        subject=payload.subject,
        topic_query=payload.topic_query,
    )


@router.post("/topic-concepts", summary="Retrieve textbook concepts via Qdrant hybrid search")
async def api_get_topic_concepts(payload: TopicConceptsRequest) -> list[dict[str, Any]]:
    return await get_topic_concepts(
        topic=payload.topic,
        query=payload.query,
        language=payload.language,
        top_k=payload.top_k,
    )


@router.post("/book-questions", summary="Retrieve textbook question stems without answer keys")
async def api_get_book_questions(payload: BookQuestionsRequest) -> list[dict[str, Any]]:
    return await get_book_questions(
        topic=payload.topic,
        question_category=payload.question_category,
        count=payload.count,
    )
