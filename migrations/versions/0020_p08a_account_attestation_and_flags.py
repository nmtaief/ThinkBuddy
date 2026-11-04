"""p08a_account_attestation_and_flags

Revision ID: 0020_p08a_account_attestation_and_flags
Revises: 0019_p08a_nonce_hash_and_attestation
Create Date: 2026-11-02 20:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0020_p08a_account_attestation_and_flags"
down_revision = "0019_p08a_nonce_hash_and_attestation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add has_valid_attestation to users table
    op.add_column(
        "users",
        sa.Column("has_valid_attestation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # 2. Add mastery_weight, parent_flag, and parent_flag_reason to quiz_attempts table
    op.add_column(
        "quiz_attempts",
        sa.Column("mastery_weight", sa.Float(), nullable=False, server_default=sa.text("1.0")),
    )
    op.add_column(
        "quiz_attempts",
        sa.Column("parent_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "quiz_attempts",
        sa.Column("parent_flag_reason", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("quiz_attempts", "parent_flag_reason")
    op.drop_column("quiz_attempts", "parent_flag")
    op.drop_column("quiz_attempts", "mastery_weight")
    op.drop_column("users", "has_valid_attestation")

