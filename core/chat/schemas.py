"""Pydantic schemas for Chat sessions, messages, citations, and SSE events."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentContext(BaseModel):
    """Contextual textbook location currently open on the student's screen."""

    book_id: uuid.UUID | None = Field(default=None, description="Book UUID")
    chapter_id: uuid.UUID | None = Field(default=None, description="Chapter UUID")
    printed_page: int | None = Field(
        default=None,
        description="Authoritative printed textbook page number (Rule 8)",
    )


class ChatSessionCreateRequest(BaseModel):
    """Payload to initiate a new chat session."""

    title: str = Field(default="New Conversation", max_length=255)
    subject: str | None = Field(default=None, max_length=100)


class ChatCitationItem(BaseModel):
    """Public textbook citation item.

    Per Standing Rule 8:
    Printed page number != PDF page index.
    Only printed_page is exposed to students and parents; pdf_page_index remains strictly internal.
    """

    model_config = ConfigDict(from_attributes=True)

    chunk_id: uuid.UUID | None = None
    book_title: str
    chapter_title: str
    chapter_number: int | None = None
    printed_page: int = Field(description="Printed textbook page number")
    score: float = Field(default=0.0, description="Relevance / groundedness confidence score")


class ChatMessageCreateRequest(BaseModel):
    """Incoming user message payload."""

    content: str = Field(min_length=1, max_length=4000, description="Student's query text")
    document_context: DocumentContext | None = Field(
        default=None,
        description="Optional current textbook page context for retrieval boosting",
    )
    stream: bool = Field(
        default=True,
        description="Whether to stream response via SSE (True) or return single JSON (False)",
    )
    language: str | None = Field(
        default=None,
        description="Preferred language code ('bn' or 'en'); defaults to student preference",
    )


class ChatMessageResponse(BaseModel):
    """Assistant or user message item with citations and metrics."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    language: str
    model: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    retrieval_confidence: float = 0.0
    citations: list[ChatCitationItem] = Field(default_factory=list)
    created_at: datetime


class ChatSessionResponse(BaseModel):
    """Metadata summary of a chat session."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: uuid.UUID
    title: str
    subject: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ChatSessionDetailResponse(ChatSessionResponse):
    """Complete chat session including full message history and citations."""

    messages: list[ChatMessageResponse] = Field(default_factory=list)


# --- SSE Event Payloads ---


class SSEMetaPayload(BaseModel):
    """Payload for 'event: meta'."""

    message_id: uuid.UUID
    retrieval_confidence: float


class SSETokenPayload(BaseModel):
    """Payload for 'event: token'."""

    delta: str


class SSECitationPayload(BaseModel):
    """Payload for 'event: citation'."""

    chunk_id: uuid.UUID
    book_title: str
    chapter_title: str
    chapter_number: int | None = None
    printed_page: int


class SSEDonePayload(BaseModel):
    """Payload for 'event: done'."""

    tokens_in: int
    tokens_out: int
    latency_ms: int
