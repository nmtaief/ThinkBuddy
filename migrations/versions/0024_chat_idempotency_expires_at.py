"""Add expires_at column to chat_idempotency_records table

Revision ID: 0024_chat_idempotency_expires_at
Revises: 0023_chat_idempotency_unique_constraint
Create Date: 2026-11-06 23:23:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0024_chat_idempotency_expires_at"
down_revision: Union[str, None] = "0023_chat_idempotency_unique_constraint"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_idempotency_records",
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW() + INTERVAL '24 hours'"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_chat_idempotency_records_expires_at",
        "chat_idempotency_records",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_chat_idempotency_records_expires_at",
        table_name="chat_idempotency_records",
    )
    op.drop_column("chat_idempotency_records", "expires_at")

