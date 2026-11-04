"""Alembic migration 0019: Add nonce_hash to quiz_attempts and has_valid_attestation to devices.

Supports P08a attestation hardening:
- Random single-use server nonce stored hashed on quiz_attempts.
- Device attestation history tracking on devices table to prevent downgrade attacks.

Revision ID: 0019_p08a_nonce_hash_and_attestation
Revises: 0018_reseed_admin_policy_ceilings
Create Date: 2026-11-02 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_p08a_nonce_hash_and_attestation"
down_revision: str | None = "0018_reseed_admin_policy_ceilings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "quiz_attempts",
        sa.Column("nonce_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "devices",
        sa.Column(
            "has_valid_attestation",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("devices", "has_valid_attestation")
    op.drop_column("quiz_attempts", "nonce_hash")

