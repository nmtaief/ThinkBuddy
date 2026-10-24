"""P03 migration: add plan_version to student_profiles.

Revision ID: 0005_p03_student_plan_version
Revises: 0004_p03_study_planner
Create Date: 2026-10-23 16:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_p03_student_plan_version"
down_revision: str | None = "0004_p03_study_planner"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "student_profiles",
        sa.Column("plan_version", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("student_profiles", "plan_version")
