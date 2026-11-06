"""p07b_consent_versions_and_deletion_ledger

Revision ID: 0022_p07b_consent_versions_and_deletion_ledger
Revises: 0021_p07b_parent_consent_export_deletion
Create Date: 2026-11-06 07:15:00.000000

"""
from __future__ import annotations

import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from core.privacy.constants import (
    CURRENT_CONSENT_TEXT_HASH,
    CURRENT_CONSENT_VERSION,
    PARENTAL_CONSENT_TEXT_BN,
    PARENTAL_CONSENT_TEXT_EN,
)

# revision identifiers, used by Alembic.
revision = "0022_p07b_consent_versions_and_deletion_ledger"
down_revision = "0021_p07b_parent_consent_export_deletion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create parental_consent_versions table
    op.create_table(
        "parental_consent_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.String(length=20), unique=True, nullable=False),
        sa.Column("text_bn", sa.Text(), nullable=False),
        sa.Column("text_en", sa.Text(), nullable=False),
        sa.Column("terms_hash", sa.String(length=64), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_parental_consent_versions_version",
        "parental_consent_versions",
        ["version"],
        unique=True,
    )

    # Seed initial canonical v1.0 consent text
    bind = op.get_bind()
    consent_versions_table = sa.table(
        "parental_consent_versions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("version", sa.String),
        sa.column("text_bn", sa.Text),
        sa.column("text_en", sa.Text),
        sa.column("terms_hash", sa.String),
    )
    bind.execute(
        consent_versions_table.insert().values(
            id=uuid.uuid4(),
            version=CURRENT_CONSENT_VERSION,
            text_bn=PARENTAL_CONSENT_TEXT_BN,
            text_en=PARENTAL_CONSENT_TEXT_EN,
            terms_hash=CURRENT_CONSENT_TEXT_HASH,
        )
    )

    # 2. Create deletion_ledger table
    op.create_table(
        "deletion_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id_hash", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("purged_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_deletion_ledger_user_id_hash", "deletion_ledger", ["user_id_hash"])
    op.create_index("ix_deletion_ledger_purged_at", "deletion_ledger", ["purged_at"])

    # 3. Add encrypted_payload column to data_exports
    op.add_column(
        "data_exports",
        sa.Column("encrypted_payload", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    # 3. Drop encrypted_payload from data_exports
    op.drop_column("data_exports", "encrypted_payload")

    # 2. Drop deletion_ledger
    op.drop_index("ix_deletion_ledger_purged_at", table_name="deletion_ledger")
    op.drop_index("ix_deletion_ledger_user_id_hash", table_name="deletion_ledger")
    op.drop_table("deletion_ledger")

    # 1. Drop parental_consent_versions
    op.drop_index("ix_parental_consent_versions_version", table_name="parental_consent_versions")
    op.drop_table("parental_consent_versions")

