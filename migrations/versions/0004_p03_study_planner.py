"""P03 migration: add study_setups, syllabus_items, plans, plan_days, tasks, and change_requests.

Revision ID: 0004_p03_study_planner
Revises: 0003_p02_curriculum_rag
Create Date: 2026-10-23 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004_p03_study_planner"
down_revision: str | None = "0003_p02_curriculum_rag"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add difficulty_factor to chapters
    op.add_column(
        "chapters",
        sa.Column("difficulty_factor", sa.Float(), server_default="1.0", nullable=False),
    )

    # 2. Add time_zone to student_profiles
    op.add_column(
        "student_profiles",
        sa.Column(
            "time_zone",
            sa.String(50),
            server_default="Asia/Dhaka",
            nullable=False,
        ),
    )

    # 3. Create study_setups table
    op.create_table(
        "study_setups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("subject", sa.String(100), nullable=False, index=True),
        sa.Column("exam_name", sa.String(255), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=False),
        sa.Column(
            "set_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("active_plan_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("student_id", "subject", name="uq_study_setups_student_subject"),
    )

    # 4. Create syllabus_items table
    op.create_table(
        "syllabus_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "setup_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("study_setups.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("included", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("custom_order", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("custom_difficulty", sa.Float(), nullable=True),
        sa.UniqueConstraint("setup_id", "chapter_id", name="uq_syllabus_items_setup_chapter"),
    )
    op.create_index("ix_syllabus_setup_order", "syllabus_items", ["setup_id", "custom_order"])

    # 5. Create plans table
    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "setup_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("study_setups.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.UniqueConstraint("setup_id", "version", name="uq_plans_setup_version"),
    )
    op.create_index(
        "ix_plans_student_setup_version", "plans", ["student_id", "setup_id", "version"]
    )

    # 6. Create plan_days table
    op.create_table(
        "plan_days",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("plans.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("planned_minutes", sa.Integer(), nullable=False),
        sa.Column("day_type", sa.String(20), server_default="study", nullable=False),
        sa.UniqueConstraint("plan_id", "date", name="uq_plan_days_plan_date"),
    )
    op.create_index("ix_plan_days_plan_date", "plan_days", ["plan_id", "date"])

    # 7. Create tasks table
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "plan_day_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("plan_days.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "refs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("est_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="todo", nullable=False),
        sa.Column("source", sa.String(30), server_default="planner", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_tasks_student_status", "tasks", ["student_id", "status"])
    op.create_index("ix_tasks_plan_day", "tasks", ["plan_day_id"])

    # 8. Create student_change_requests table
    op.create_table(
        "student_change_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "setup_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("study_setups.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("requested_changes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reviewed_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_change_requests_setup_status", "student_change_requests", ["setup_id", "status"]
    )


def downgrade() -> None:
    op.drop_table("student_change_requests")
    op.drop_table("tasks")
    op.drop_table("plan_days")
    op.drop_table("plans")
    op.drop_table("syllabus_items")
    op.drop_table("study_setups")
    op.drop_column("student_profiles", "time_zone")
    op.drop_column("chapters", "difficulty_factor")
