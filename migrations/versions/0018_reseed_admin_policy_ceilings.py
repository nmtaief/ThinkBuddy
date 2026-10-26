"""Alembic migration 0018: Reseed admin policy ceilings.

Updates admin policy table with calibrated ceilings and limits per class band:
- Band 6-8: school default 150m, ceiling 240m, hard limit 360m; holiday default 240m, ceiling 360m, hard limit 600m
- Band 9-10: school default 240m, ceiling 360m, hard limit 360m; holiday default 360m, ceiling 480m, hard limit 600m
- Band 11-12: school default 300m, ceiling 360m, hard limit 360m; holiday default 420m, ceiling 600m, hard limit 600m

Revision ID: 0018_reseed_admin_policy_ceilings
Revises: 0017_p07_tail_enhancements
Create Date: 2026-10-26 14:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0018_reseed_admin_policy_ceilings"
down_revision = "0017_p07_tail_enhancements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE admin_policies SET "
        "school_day_default_minutes = 150, school_day_ceiling_minutes = 240, school_day_hard_limit_minutes = 360, "
        "holiday_default_minutes = 240, holiday_ceiling_minutes = 360, holiday_hard_limit_minutes = 600 "
        "WHERE class_band = '6-8'"
    )
    op.execute(
        "UPDATE admin_policies SET "
        "school_day_default_minutes = 240, school_day_ceiling_minutes = 360, school_day_hard_limit_minutes = 360, "
        "holiday_default_minutes = 360, holiday_ceiling_minutes = 480, holiday_hard_limit_minutes = 600 "
        "WHERE class_band = '9-10'"
    )
    op.execute(
        "UPDATE admin_policies SET "
        "school_day_default_minutes = 300, school_day_ceiling_minutes = 360, school_day_hard_limit_minutes = 360, "
        "holiday_default_minutes = 420, holiday_ceiling_minutes = 600, holiday_hard_limit_minutes = 600 "
        "WHERE class_band = '11-12'"
    )


def downgrade() -> None:
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
