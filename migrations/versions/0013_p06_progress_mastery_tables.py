"""P06 progress, mastery, revision, and daily progress tables.

Revision ID: 0013_p06_progress_mastery
Revises: 0012_p05_chat_tables
Create Date: 2026-10-25 13:05:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "0013_p06_progress_mastery"
down_revision: Union[str, None] = "0012_p05_chat_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. mastery table
    op.create_table(
        "mastery",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "student_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "chapter_id",
            UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("concept_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_mastery_student_chapter",
        "mastery",
        ["student_id", "chapter_id"],
        unique=False,
    )
    op.create_index(
        "uq_mastery_student_chapter_null_concept",
        "mastery",
        ["student_id", "chapter_id"],
        unique=True,
        postgresql_where=sa.text("concept_id IS NULL"),
    )
    op.create_index(
        "uq_mastery_student_chapter_concept",
        "mastery",
        ["student_id", "chapter_id", "concept_id"],
        unique=True,
        postgresql_where=sa.text("concept_id IS NOT NULL"),
    )

    # 2. revision_items table (Leitner boxes)
    op.create_table(
        "revision_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "student_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "chapter_id",
            UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("concept_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "question_id",
            UUID(as_uuid=True),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("box", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("last_result", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_revision_items_student_due",
        "revision_items",
        ["student_id", "due_at"],
    )
    op.create_index(
        "uq_revision_items_student_chapter_null_q",
        "revision_items",
        ["student_id", "chapter_id"],
        unique=True,
        postgresql_where=sa.text("question_id IS NULL"),
    )
    op.create_index(
        "uq_revision_items_student_chapter_question",
        "revision_items",
        ["student_id", "chapter_id", "question_id"],
        unique=True,
        postgresql_where=sa.text("question_id IS NOT NULL"),
    )

    # 3. progress_daily table
    op.create_table(
        "progress_daily",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "student_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("date", sa.Date(), nullable=False, index=True),
        sa.Column("minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tasks_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tasks_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quiz_avg", sa.Float(), nullable=True),
        sa.Column("streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_unique_constraint(
        "uq_progress_daily_student_date",
        "progress_daily",
        ["student_id", "date"],
    )


def downgrade() -> None:
    op.drop_table("progress_daily")
    op.drop_table("revision_items")
    op.drop_table("mastery")
