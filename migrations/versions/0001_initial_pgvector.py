"""Initial migration: enable pgvector and pg_trgm extensions and baseline schema.

Revision ID: 0001_initial_pgvector
Revises:
Create Date: 2026-10-23 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_pgvector"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pgvector extension for high-dimensional vector search
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    # Enable pg_trgm extension for fast trigram and fuzzy text search over Bangla & English content
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")


def downgrade() -> None:
    # Reversible migration per AGENT_RULES.md Rule 10
    op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
    op.execute("DROP EXTENSION IF EXISTS vector;")
