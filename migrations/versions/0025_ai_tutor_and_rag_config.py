"""Add ai_tutor_configs table for AI Tutor and RAG administrative management

Revision ID: 0025_ai_tutor_and_rag_config
Revises: 0024_chat_idempotency_expires_at
Create Date: 2026-11-09 14:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0025_ai_tutor_and_rag_config"
down_revision: Union[str, None] = "0024_chat_idempotency_expires_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_tutor_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("llm_provider", sa.String(50), nullable=False, server_default="gemini"),
        sa.Column("api_key", sa.String(500), nullable=True),
        sa.Column("api_base", sa.String(255), nullable=True),
        sa.Column("primary_model", sa.String(100), nullable=False, server_default="gemini/gemini-1.5-flash"),
        sa.Column("fallback_model", sa.String(100), nullable=False, server_default="openai/gpt-4o-mini"),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("embedding_provider", sa.String(50), nullable=False, server_default="bge-m3"),
        sa.Column("embedding_api_key", sa.String(500), nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=False, server_default="bge-m3"),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False, server_default="1024"),
        sa.Column("confidence_threshold", sa.Float(), nullable=False, server_default="0.45"),
        sa.Column("max_chunks", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ai_tutor_configs")
