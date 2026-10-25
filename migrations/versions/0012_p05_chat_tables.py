"""P05: Add chat_sessions, chat_messages, chat_citations, and usage_counters tables.

Revision ID: 0012_p05_chat_tables
Revises: 0011_p04_tail
Create Date: 2026-10-25 02:00:00.000000

Changes:
1. Create chat_sessions table for conversational RAG sessions.
2. Create chat_messages table storing user prompts and assistant answers with token usage & latency metrics.
3. Create chat_citations table storing authoritative chunk citations with printed_page and pdf_page_index (Rule 8).
4. Create usage_counters table for daily per-student quota enforcement.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0012_p05_chat_tables"
down_revision: str | None = "0011_p04_tail"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. chat_sessions
    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(255), nullable=False, server_default="New Conversation"),
        sa.Column("subject", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 2. chat_messages
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("language", sa.String(10), nullable=False, server_default="bn"),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retrieval_confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 3. chat_citations
    op.create_table(
        "chat_citations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_messages.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chunks.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("book_title", sa.String(255), nullable=False),
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("chapter_title", sa.String(255), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=True),
        sa.Column("printed_page", sa.Integer(), nullable=False),
        sa.Column("pdf_page_index", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 4. usage_counters
    op.create_table(
        "usage_counters",
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("date", sa.Date(), primary_key=True, nullable=False),
        sa.Column("chat_messages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("usage_counters")
    op.drop_table("chat_citations")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
