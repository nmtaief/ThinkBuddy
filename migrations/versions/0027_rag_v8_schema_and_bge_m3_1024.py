"""Migrate chunks embedding to 1024 dimensions (BGE-M3), add glossary and guided_answers tables

Revision ID: 0027_rag_v8_schema_and_bge_m3_1024
Revises: 0026_exercise_items_and_chunk_type
Create Date: 2026-11-10 20:30:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0027_rag_v8_schema_and_bge_m3_1024"
down_revision: Union[str, None] = "0026_exercise_items_and_chunk_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop existing HNSW index on 384-dim vector
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding_hnsw;")

    # 2. Clear old 384-dim mock embeddings from quarantined chunks
    op.execute("UPDATE chunks SET embedding = NULL WHERE embedding IS NOT NULL;")

    # 3. Alter chunks.embedding to vector(1024)
    op.execute("ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(1024);")

    # 4. Add embedding_dimension and status columns to chunks
    op.add_column(
        "chunks",
        sa.Column("embedding_dimension", sa.Integer(), nullable=False, server_default="1024"),
    )
    op.add_column(
        "chunks",
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
    )
    op.create_index("idx_chunks_status", "chunks", ["status"])

    # 5. Re-create HNSW index for vector(1024)
    op.execute(
        "CREATE INDEX idx_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);"
    )

    # 6. Create glossary table (Dataset C)
    op.create_table(
        "glossary",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("term_bn", sa.String(100), nullable=False, index=True),
        sa.Column("term_en", sa.String(100), nullable=True, index=True),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("subject", sa.String(50), nullable=False, index=True),
        sa.Column("class_level", sa.Integer(), nullable=True, index=True),
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
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
    )

    # 7. Create guided_answers table (Dataset D)
    op.create_table(
        "guided_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "exercise_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("exercise_items.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
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
        sa.Column("question_title", sa.String(250), nullable=False),
        sa.Column("steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("common_mistakes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("final_answer", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
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
    )


def downgrade() -> None:
    op.drop_table("guided_answers")
    op.drop_table("glossary")
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding_hnsw;")
    op.drop_index("idx_chunks_status", table_name="chunks")
    op.drop_column("chunks", "status")
    op.drop_column("chunks", "embedding_dimension")
    op.execute("UPDATE chunks SET embedding = NULL;")
    op.execute("ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(384);")
    op.execute(
        "CREATE INDEX idx_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);"
    )

