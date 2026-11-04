"""p07b_parent_consent_export_deletion

Revision ID: 0021_p07b_parent_consent_export_deletion
Revises: 0020_p08a_account_attestation_and_flags
Create Date: 2026-11-04 17:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0021_p07b_parent_consent_export_deletion"
down_revision = "0020_p08a_account_attestation_and_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add parental consent tracking columns to users table
    op.add_column(
        "users",
        sa.Column("has_parental_consent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "users",
        sa.Column("consent_version", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("consent_terms_hash", sa.String(length=64), nullable=True),
    )

    # 2. Create parental_consents table
    op.create_table(
        "parental_consents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=False),
        sa.Column("consent_version", sa.String(length=20), nullable=False),
        sa.Column("terms_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="granted"),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["parent_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parental_consents_parent_id", "parental_consents", ["parent_id"], unique=False)
    op.create_index("ix_parental_consents_consented_at", "parental_consents", ["consented_at"], unique=False)

    # 3. Create data_exports table
    op.create_table(
        "data_exports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("family_id", sa.UUID(), nullable=False),
        sa.Column("requester_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("format", sa.String(length=10), nullable=False, server_default="json"),
        sa.Column("data_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("download_token_hash", sa.String(length=64), nullable=True),
        sa.Column("download_url", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_exports_family_id", "data_exports", ["family_id"], unique=False)
    op.create_index("ix_data_exports_requester_id", "data_exports", ["requester_id"], unique=False)
    op.create_index("ix_data_exports_expires_at", "data_exports", ["expires_at"], unique=False)

    # 4. Create account_deletions table
    op.create_table(
        "account_deletions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("family_id", sa.UUID(), nullable=True),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending_grace_period"),
        sa.Column("grace_period_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("scheduled_purge_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recent_auth_confirmed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_deletions_user_id", "account_deletions", ["user_id"], unique=False)
    op.create_index("ix_account_deletions_family_id", "account_deletions", ["family_id"], unique=False)
    op.create_index("ix_account_deletions_purge_queue", "account_deletions", ["status", "scheduled_purge_at"], unique=False)


def downgrade() -> None:
    op.drop_table("account_deletions")
    op.drop_table("data_exports")
    op.drop_table("parental_consents")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS consent_terms_hash")
    op.drop_column("users", "consent_version")
    op.drop_column("users", "has_parental_consent")

