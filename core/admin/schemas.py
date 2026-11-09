"""Pydantic schemas for AI Tutor and RAG administrative management."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


def mask_secret(secret: str | None) -> str | None:
    """Mask sensitive API keys, revealing only prefix and trailing 4 characters."""
    if not secret:
        return None
    trimmed = secret.strip()
    if len(trimmed) <= 8:
        return "********"
    prefix = trimmed[:4]
    suffix = trimmed[-4:]
    return f"{prefix}...****...{suffix}"


class AITutorConfigResponse(BaseModel):
    """Admin response for current AI Tutor & RAG configuration."""

    id: uuid.UUID
    llm_provider: str = Field(description="LLM provider: gemini, openai, anthropic, groq, ollama, custom")
    has_api_key: bool = Field(description="Whether a valid LLM API key is configured")
    api_key_masked: str | None = Field(default=None, description="Masked API key for display")
    api_base: str | None = Field(default=None, description="Custom base URL for OpenAI-compatible or local inference")
    primary_model: str = Field(description="Primary model identifier, e.g. gemini/gemini-1.5-flash or openai/gpt-4o-mini")
    fallback_model: str = Field(description="Fallback model identifier when primary fails")
    temperature: float = Field(ge=0.0, le=2.0, description="Generation temperature (0.0 to 2.0)")
    system_prompt: str | None = Field(default=None, description="Custom system prompt instructions for Buddy")
    embedding_provider: str = Field(description="Embedding provider: bge-m3, hosted, openai, gemini, mock")
    has_embedding_api_key: bool = Field(description="Whether an embedding API key is configured")
    embedding_api_key_masked: str | None = Field(default=None, description="Masked embedding API key for display")
    embedding_model: str = Field(description="Embedding model identifier, e.g. bge-m3, text-embedding-3-small")
    embedding_dimensions: int = Field(description="Embedding vector dimensions")
    confidence_threshold: float = Field(ge=0.0, le=1.0, description="Minimum retrieval confidence score threshold")
    max_chunks: int = Field(ge=1, le=10, description="Maximum number of authoritative chunks retrieved per prompt")
    is_enabled: bool = Field(description="Whether AI Tutor Chat is enabled")
    created_at: datetime
    updated_at: datetime


class UpdateAITutorConfigRequest(BaseModel):
    """Admin request to update AI Tutor & RAG configuration."""

    llm_provider: str | None = Field(default=None, description="LLM provider: gemini, openai, anthropic, groq, ollama, custom")
    api_key: str | None = Field(default=None, description="New LLM API key. If empty or None, keeps existing.")
    api_base: str | None = Field(default=None, description="Custom API base URL")
    primary_model: str | None = Field(default=None, description="Primary model identifier")
    fallback_model: str | None = Field(default=None, description="Fallback model identifier")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0, description="Generation temperature")
    system_prompt: str | None = Field(default=None, description="Custom persona instructions for Buddy")
    embedding_provider: str | None = Field(default=None, description="Embedding provider: bge-m3, hosted, openai, gemini, mock")
    embedding_api_key: str | None = Field(default=None, description="New embedding API key")
    embedding_model: str | None = Field(default=None, description="Embedding model identifier")
    embedding_dimensions: int | None = Field(default=None, ge=64, le=4096, description="Embedding vector dimensions")
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0, description="Confidence threshold")
    max_chunks: int | None = Field(default=None, ge=1, le=10, description="Max chunks to retrieve")
    is_enabled: bool | None = Field(default=None, description="Enable or disable AI Tutor")


class TestLLMRequest(BaseModel):
    """Admin test request to ping the LLM API."""

    prompt: str = Field(
        default="Say hello and introduce yourself as ThinkBuddy AI Tutor in one sentence in English and Bangla.",
        description="Prompt to send to the LLM",
    )
    provider: str | None = Field(default=None, description="Optional override provider")
    model: str | None = Field(default=None, description="Optional override model")
    api_key: str | None = Field(default=None, description="Optional override API key")
    api_base: str | None = Field(default=None, description="Optional override API base URL")


class TestLLMResponse(BaseModel):
    """Response from diagnostic LLM ping."""

    success: bool
    content: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    model_used: str
    error: str | None = None


class TestRAGRequest(BaseModel):
    """Admin test request to evaluate RAG retrieval for a curriculum query."""

    query: str = Field(..., description="Query to test retrieval for (e.g. 'সালোকসংশ্লেষণ কি?' or 'What is photosynthesis?')")
    class_level: str | None = Field(default=None, description="Optional class filter (e.g. 'Class 7')")
    subject: str | None = Field(default=None, description="Optional subject filter (e.g. 'Science')")
    limit: int = Field(default=4, ge=1, le=10, description="Max chunks to retrieve")


class RAGTestChunk(BaseModel):
    """Retrieved chunk summary for admin inspection."""

    chunk_id: str
    book_title: str
    chapter_title: str
    chapter_number: int | None
    printed_page: int
    pdf_page_index: int
    score: float
    snippet: str


class TestRAGResponse(BaseModel):
    """Response from diagnostic RAG search."""

    query: str
    confidence: float
    chunks: list[RAGTestChunk]
    latency_ms: int


class AITutorStatsResponse(BaseModel):
    """Knowledge base and AI Tutor statistics."""

    total_books: int
    total_chapters: int
    total_chunks: int
    total_chat_sessions: int
    total_chat_messages: int
    active_llm_provider: str
    active_primary_model: str
    active_embedding_provider: str
    rag_chat_enabled: bool
