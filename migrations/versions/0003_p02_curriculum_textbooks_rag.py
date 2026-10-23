"""P02 migration: add curriculum, textbooks, chapters, concepts, ingest_batches, and chunks tables.

Revision ID: 0003_p02_curriculum_textbooks_rag
Revises: 0002_p01_auth_roles_family
Create Date: 2026-10-23 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from core.common.config import settings

# revision identifiers, used by Alembic.
revision: str = "0003_p02_curriculum_rag"
down_revision: str | None = "0002_p01_auth_roles_family"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Ensure extensions exist
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 1. Books table
    op.create_table(
        "books",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("class_level", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("medium", sa.String(10), nullable=False, server_default="bn"),
        sa.Column("edition", sa.String(50), nullable=False, server_default="2024"),
        sa.Column("source_uri", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "class_level", "subject", "medium", "edition", name="uq_books_curriculum"
        ),
    )
    op.create_index("idx_books_class_subject", "books", ["class_level", "subject"])

    # 2. Chapters table
    op.create_table(
        "chapters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("printed_page_start", sa.Integer(), nullable=False),
        sa.Column("printed_page_end", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("book_id", "number", name="uq_chapters_book_number"),
    )
    op.create_index("idx_chapters_book_order", "chapters", ["book_id", "order_index"])

    # 3. Concepts table
    op.create_table(
        "concepts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False, server_default="concept"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("idx_concepts_chapter_id", "concepts", ["chapter_id"])

    # 4. Ingest Batches table
    op.create_table(
        "ingest_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_manifest", sa.String(500), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="in_progress"),
        sa.Column(
            "stats", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # 5. Chunks table
    # Embedding dimension is read from provider configuration dynamically
    embed_dim = settings.EMBEDDING_DIMENSION
    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "concept_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("concepts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "ingest_batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingest_batches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_original", sa.Text(), nullable=True),
        sa.Column("language", sa.String(10), nullable=False, server_default="bn"),
        sa.Column("printed_page", sa.Integer(), nullable=False),
        sa.Column("pdf_page_index", sa.Integer(), nullable=False),
        sa.Column("ocr_quality", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column(
            "validation_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("retrievable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "embedding_model",
            sa.String(100),
            nullable=False,
            server_default=settings.EMBEDDING_MODEL,
        ),
        sa.Column("embedding", Vector(embed_dim), nullable=True),
        sa.Column("tsv", postgresql.TSVECTOR(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("book_id", "chunk_index", name="uq_chunks_book_chunk_index"),
    )

    op.create_index("idx_chunks_book_chapter", "chunks", ["book_id", "chapter_id"])
    op.create_index("idx_chunks_chapter_printed_page", "chunks", ["chapter_id", "printed_page"])
    op.create_index("idx_chunks_retrievable", "chunks", ["retrievable"])

    # HNSW Index for vector cosine similarity search
    op.execute(
        "CREATE INDEX idx_chunks_embedding_hnsw ON chunks "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64);"
    )

    # GIN Index for full-text search
    op.execute("CREATE INDEX idx_chunks_tsv ON chunks USING gin (tsv);")

    # Trigram GIN index for fuzzy lexical matching across Bangla/English text
    op.execute("CREATE INDEX idx_chunks_text_trgm ON chunks USING gin (text gin_trgm_ops);")


def downgrade() -> None:
    op.drop_table("chunks")
    op.drop_table("ingest_batches")
    op.drop_table("concepts")
    op.drop_table("chapters")
    op.drop_table("books")
