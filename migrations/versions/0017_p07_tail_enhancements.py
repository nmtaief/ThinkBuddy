"""Alembic migration 0017: P07 tail enhancements.

Ceilings by class band and day type in admin policies, deferred pushes until quiet hours end,
token uniqueness and cleanup, change request expiration and setup version tracking.

Revision ID: 0017_p07_tail_enhancements
Revises: 0016_p07_delivery_and_rollout
Create Date: 2026-10-25 22:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0017_p07_tail_enhancements"
down_revision = "0016_p07_delivery_and_rollout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Admin policy ceilings by class band and day type (Item 1)
    op.add_column("admin_policies", sa.Column("school_day_default_minutes", sa.Integer(), server_default=sa.text("60"), nullable=False))
    op.add_column("admin_policies", sa.Column("school_day_ceiling_minutes", sa.Integer(), server_default=sa.text("120"), nullable=False))
    op.add_column("admin_policies", sa.Column("school_day_hard_limit_minutes", sa.Integer(), server_default=sa.text("180"), nullable=False))
    op.add_column("admin_policies", sa.Column("holiday_default_minutes", sa.Integer(), server_default=sa.text("120"), nullable=False))
    op.add_column("admin_policies", sa.Column("holiday_ceiling_minutes", sa.Integer(), server_default=sa.text("180"), nullable=False))
    op.add_column("admin_policies", sa.Column("holiday_hard_limit_minutes", sa.Integer(), server_default=sa.text("240"), nullable=False))

    # Update existing baseline policies aligned with budgets per class band
    op.execute(
        "UPDATE admin_policies SET "
        "school_day_default_minutes = 60, school_day_ceiling_minutes = 120, school_day_hard_limit_minutes = 180, "
        "holiday_default_minutes = 120, holiday_ceiling_minutes = 180, holiday_hard_limit_minutes = 240 "
        "WHERE class_band = '6-8'"
    )
    op.execute(
        "UPDATE admin_policies SET "
        "school_day_default_minutes = 90, school_day_ceiling_minutes = 180, school_day_hard_limit_minutes = 240, "
        "holiday_default_minutes = 150, holiday_ceiling_minutes = 240, holiday_hard_limit_minutes = 300 "
        "WHERE class_band = '9-10'"
    )
    op.execute(
        "UPDATE admin_policies SET "
        "school_day_default_minutes = 120, school_day_ceiling_minutes = 240, school_day_hard_limit_minutes = 300, "
        "holiday_default_minutes = 180, holiday_ceiling_minutes = 300, holiday_hard_limit_minutes = 360 "
        "WHERE class_band = '11-12'"
    )

    # 2. Deferred push tracking in notification_deliveries (Item 2)
    op.add_column("notification_deliveries", sa.Column("deferred_until", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_notification_deliveries_deferred", "notification_deliveries", ["status", "deferred_until"])

    # 3. Change requests setup_version and expires_at with backfill (Item 4)
    op.add_column("student_change_requests", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("student_change_requests", sa.Column("setup_version", sa.Integer(), nullable=True))
    op.execute("UPDATE student_change_requests SET expires_at = created_at + interval '7 days' WHERE expires_at IS NULL")
    op.create_index("ix_student_change_requests_status_expires", "student_change_requests", ["status", "expires_at"])

    # 4. Device push token uniqueness (Item 3)
    op.execute(
        """
        WITH ranked_devices AS (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY push_token ORDER BY updated_at DESC, created_at DESC) as rk
            FROM devices
            WHERE push_token IS NOT NULL
        )
        UPDATE devices
        SET push_token = NULL
        WHERE id IN (SELECT id FROM ranked_devices WHERE rk > 1)
        """
    )
    op.create_index(
        "uq_devices_push_token",
        "devices",
        ["push_token"],
        unique=True,
        postgresql_where=sa.text("push_token IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_devices_push_token", table_name="devices")
    op.drop_index("ix_student_change_requests_status_expires", table_name="student_change_requests")
    op.drop_column("student_change_requests", "setup_version")
    op.drop_column("student_change_requests", "expires_at")
    op.drop_index("ix_notification_deliveries_deferred", table_name="notification_deliveries")
    op.drop_column("notification_deliveries", "deferred_until")
    op.drop_column("admin_policies", "holiday_hard_limit_minutes")
    op.drop_column("admin_policies", "holiday_ceiling_minutes")
    op.drop_column("admin_policies", "holiday_default_minutes")
    op.drop_column("admin_policies", "school_day_hard_limit_minutes")
    op.drop_column("admin_policies", "school_day_ceiling_minutes")
    op.drop_column("admin_policies", "school_day_default_minutes")
