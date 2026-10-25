"""P06 tail: AI planner shadow runs table and student settings override.

Revision ID: 0014_p06_tail_shadow_runs
Revises: 0013_p06_progress_mastery
Create Date: 2026-10-25 17:15:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "0014_p06_tail_shadow_runs"
down_revision: Union[str, None] = "0013_p06_progress_mastery"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add ai_planner_override to student_study_settings
    op.add_column(
        "student_study_settings",
        sa.Column("ai_planner_override", sa.Boolean(), nullable=True),
    )

    # 2. Create ai_planner_shadow_runs table (strictly metrics, no payload/prompt data)
    op.create_table(
        "ai_planner_shadow_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "student_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"), index=True),
        sa.Column("recommendation", sa.String(length=32), nullable=False),
        sa.Column("coverage_parity_met", sa.Boolean(), nullable=False),
        sa.Column("churn_rate_pct", sa.Float(), nullable=False),
        sa.Column("minutes_delta", sa.Integer(), nullable=False),
        sa.Column("ai_warnings_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metrics", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_ai_planner_shadow_runs_student_at",
        "ai_planner_shadow_runs",
        ["student_id", "at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_planner_shadow_runs_student_at", table_name="ai_planner_shadow_runs")
    op.drop_table("ai_planner_shadow_runs")
    op.drop_column("student_study_settings", "ai_planner_override")
