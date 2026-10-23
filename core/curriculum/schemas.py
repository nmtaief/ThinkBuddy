"""Pydantic schemas for curriculum, books, chapters, and concepts."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class ConceptSummary(BaseModel):
    id: uuid.UUID
    chapter_id: uuid.UUID
    title: str
    kind: str


class ChapterSummary(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID
    number: int
    title: str
    printed_page_start: int
    printed_page_end: int
    order_index: int


class BookSummary(BaseModel):
    id: uuid.UUID
    title: str
    class_level: int
    subject: str
    medium: str
    edition: str
    chapters_count: int = Field(default=0)


class BookListResponse(BaseModel):
    items: list[BookSummary]
    total: int


class ChapterListResponse(BaseModel):
    items: list[ChapterSummary]
    total: int


class ChapterDetailResponse(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID
    book_title: str
    number: int
    title: str
    printed_page_start: int
    printed_page_end: int
    order_index: int
    concepts: list[ConceptSummary]
    chunks_count: int
