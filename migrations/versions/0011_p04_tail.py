"""P04 tail hardening: pause auto-resume, unverified device, recycled items, and learning signal unique constraint.

Revision ID: 0011_p04_tail
Revises: 0010_p04_hardening
Create Date: 2026-10-25 01:10:00.000000

Changes:
1. Add paused_at and pause_expires_at to quiz_attempts for short auto-resuming pauses.
2. Add unverified_device to quiz_attempts for mastery weight scaling and parent view labeling.
3. Add is_recycled to attempt_items to mark recycled questions from exhausted assessed pools.
4. Add unique constraint uq_learning_signals_student_source_ref on learning_signals (student_id, source, ref_id)
   supporting ON CONFLICT DO NOTHING idempotency.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_p04_tail"
down_revision: str | None = "0010_p04_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add paused_at, pause_expires_at, unverified_device to quiz_attempts
    op.add_column(
        "quiz_attempts",
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "quiz_attempts",
        sa.Column("pause_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "quiz_attempts",
        sa.Column(
            "unverified_device",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # 2. Add is_recycled to attempt_items
    op.add_column(
        "attempt_items",
        sa.Column(
            "is_recycled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # 3. Create unique constraint on learning_signals (student_id, source, ref_id)
    op.create_unique_constraint(
        "uq_learning_signals_student_source_ref",
        "learning_signals",
        ["student_id", "source", "ref_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_learning_signals_student_source_ref",
        "learning_signals",
        type_="unique",
    )
    op.drop_column("attempt_items", "is_recycled")
    op.drop_column("quiz_attempts", "unverified_device")
    op.drop_column("quiz_attempts", "pause_expires_at")
    op.drop_column("quiz_attempts", "paused_at")
