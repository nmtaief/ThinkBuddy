"""Alembic migration 0016: notification deliveries and durable ai planner rollout configs.

Revision ID: 0016_p07_delivery_and_rollout
Revises: 0015_p07_parent_notifications
Create Date: 2026-10-25 21:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0016_p07_delivery_and_rollout"
down_revision = "0015_p07_parent_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. notification_deliveries table
    op.create_table(
        "notification_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("notification_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("notifications.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=False),  # push, in_app, email
        sa.Column("status", sa.String(length=32), nullable=False, index=True),  # delivered, suppressed_quiet_hours, suppressed_daily_cap, failed
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, index=True),
    )
    op.create_index("ix_notification_deliveries_user_sent", "notification_deliveries", ["user_id", "sent_at"])

    # 2. ai_planner_rollout_configs table for durable rollout configuration
    op.create_table(
        "ai_planner_rollout_configs",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("enabled_class_bands", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[\"9-10\", \"11-12\"]'::jsonb"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Insert default initial configuration row
    op.execute(
        "INSERT INTO ai_planner_rollout_configs (key, enabled, enabled_class_bands, version, updated_at) "
        "VALUES ('ai_planner', false, '[\"9-10\", \"11-12\"]'::jsonb, 1, now()) "
        "ON CONFLICT (key) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("ai_planner_rollout_configs")
    op.drop_index("ix_notification_deliveries_user_sent", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
