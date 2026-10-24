"""Add rest_weekday to student_study_settings and provenance metadata to plans.

Revision ID: 0008_p03_rest_and_p06a_prov
Revises: 0007_p03_v2_adaptive_blackout
Create Date: 2026-10-24 17:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_p03_rest_and_p06a_prov"
down_revision: str | None = "0007_p03_v2_adaptive_blackout"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add rest_weekday to student_study_settings
    op.add_column(
        "student_study_settings",
        sa.Column(
            "rest_weekday",
            sa.String(length=16),
            nullable=True,
        ),
    )

    # 2. Add provenance fields to plans
    op.add_column(
        "plans",
        sa.Column(
            "provider",
            sa.String(length=32),
            nullable=False,
            server_default="deterministic",
        ),
    )
    op.add_column(
        "plans",
        sa.Column(
            "model_version",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.add_column(
        "plans",
        sa.Column(
            "contract_version",
            sa.String(length=16),
            nullable=False,
            server_default="1.0.0",
        ),
    )
    op.add_column(
        "plans",
        sa.Column(
            "settings_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "plans",
        sa.Column(
            "generation_reason",
            sa.String(length=255),
            nullable=True,
            server_default="Standard deterministic plan generated",
        ),
    )


def downgrade() -> None:
    op.drop_column("plans", "generation_reason")
    op.drop_column("plans", "settings_version")
    op.drop_column("plans", "contract_version")
    op.drop_column("plans", "model_version")
    op.drop_column("plans", "provider")
    op.drop_column("student_study_settings", "rest_weekday")
