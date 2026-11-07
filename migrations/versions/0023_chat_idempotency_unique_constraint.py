"""chat_idempotency_unique_constraint

Revision ID: 0023_chat_idempotency_unique_constraint
Revises: 0022_p07b_consent_versions_and_deletion_ledger
Create Date: 2026-11-06 20:10:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0023_chat_idempotency_unique_constraint"
down_revision = "0022_p07b_consent_versions_and_deletion_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_idempotency_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "student_id",
            "session_id",
            "idempotency_key",
            name="uq_chat_idempotency_key",
        ),
    )
    op.create_index(
        "ix_chat_idempotency_lookup",
        "chat_idempotency_records",
        ["student_id", "session_id", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_chat_idempotency_lookup", table_name="chat_idempotency_records")
    op.drop_table("chat_idempotency_records")

