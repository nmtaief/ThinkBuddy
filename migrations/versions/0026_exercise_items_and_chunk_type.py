"""Add exercise_items table and chunk_type column to chunks

Revision ID: 0026_exercise_items_and_chunk_type
Revises: 0025_ai_tutor_and_rag_config
Create Date: 2026-11-10 18:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0026_exercise_items_and_chunk_type"
down_revision: Union[str, None] = "0025_ai_tutor_and_rag_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add chunk_type to chunks
    op.add_column(
        "chunks",
        sa.Column(
            "chunk_type",
            sa.String(30),
            nullable=False,
            server_default="explanation",
        ),
    )
    op.create_index("idx_chunks_chunk_type", "chunks", ["chunk_type"])

    # 2. Create exercise_items table
    op.create_table(
        "exercise_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("exercise_label", sa.String(50), nullable=False, index=True),
        sa.Column("question_no", sa.Integer(), nullable=False, index=True),
        sa.Column("subpart", sa.String(10), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("printed_page", sa.Integer(), nullable=False),
        sa.Column("pdf_page_index", sa.Integer(), nullable=False),
        sa.Column("has_figure", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("figure_note", sa.Text(), nullable=True),
        sa.Column("item_type", sa.String(30), nullable=False, server_default="short"),
        sa.Column("ocr_confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="team_checked"),
        sa.Column("source", sa.String(100), nullable=False, server_default="NCTB 2024"),
        sa.Column("answer_key", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "chapter_id",
            "exercise_label",
            "question_no",
            "subpart",
            name="uq_exercise_item_chapter_label_qno_subpart",
        ),
    )
    op.create_index(
        "idx_exercise_items_lookup",
        "exercise_items",
        ["book_id", "exercise_label", "question_no"],
    )


def downgrade() -> None:
    op.drop_index("idx_exercise_items_lookup", table_name="exercise_items")
    op.drop_table("exercise_items")
    op.drop_index("idx_chunks_chunk_type", table_name="chunks")
    op.drop_column("chunks", "chunk_type")

