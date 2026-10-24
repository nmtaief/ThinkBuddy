"""P03 fix round: adaptive hook, settings precedence, and blackout reasons update.

Revision ID: 0007_p03_v2_adaptive_and_blackout
Revises: 0006_p03_planner_v2_config
Create Date: 2026-10-23 23:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007_p03_v2_adaptive_blackout"
down_revision: str | None = "0006_p03_planner_v2_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add adaptive_mode, ai_adjustments, and parent_locked_fields to student_study_settings
    op.add_column(
        "student_study_settings",
        sa.Column(
            "adaptive_mode",
            sa.String(length=32),
            nullable=False,
            server_default="suggest",
        ),
    )
    op.add_column(
        "student_study_settings",
        sa.Column(
            "ai_adjustments",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "student_study_settings",
        sa.Column(
            "parent_locked_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )

    # 2. Migrate existing blackout dates with reason 'illness' to 'other'
    op.execute("""
        UPDATE student_study_settings
        SET custom_blackout_dates = (
            SELECT COALESCE(
                jsonb_agg(
                    CASE 
                        WHEN elem->>'reason' = 'illness' 
                        THEN jsonb_set(elem, '{reason}', '"other"')
                        ELSE elem
                    END
                ),
                '[]'::jsonb
            )
            FROM jsonb_array_elements(custom_blackout_dates) elem
        )
        WHERE custom_blackout_dates @> '[{"reason": "illness"}]';
    """)


def downgrade() -> None:
    op.drop_column("student_study_settings", "parent_locked_fields")
    op.drop_column("student_study_settings", "ai_adjustments")
    op.drop_column("student_study_settings", "adaptive_mode")
