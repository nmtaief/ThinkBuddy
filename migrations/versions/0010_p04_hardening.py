"""P04 hardening: DB constraints, question pools, accepted answers, and keyless view.

Revision ID: 0010_p04_hardening
Revises: 0009_p04_secure_quiz_tables
Create Date: 2026-10-24 21:00:00.000000

Changes:
1. Denormalize mode on quiz_attempts with server default 'assessed'.
2. Create partial unique index uq_quiz_attempts_active_student_assessed on quiz_attempts (student_id)
   WHERE state = 'active' AND mode = 'assessed' (database-level concurrency protection).
3. Add pool column to questions ('practice', 'assessed', 'both').
4. Add accepted_answers JSONB column to question_keys for alternative short answers.
5. Create keyless SQL view v_questions_public omitting all key/grading columns.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0010_p04_hardening"
down_revision: str | None = "0009_p04_secure_quiz_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add mode column to quiz_attempts
    op.add_column(
        "quiz_attempts",
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="assessed"),
    )

    # 2. Database-level constraint: partial unique index for active assessed attempts
    op.create_index(
        "uq_quiz_attempts_active_student_assessed",
        "quiz_attempts",
        ["student_id"],
        unique=True,
        postgresql_where=sa.text("state = 'active' AND mode = 'assessed'"),
    )

    # 3. Add pool column to questions table
    op.add_column(
        "questions",
        sa.Column("pool", sa.String(length=16), nullable=False, server_default="both"),
    )

    # 4. Add accepted_answers column to question_keys
    op.add_column(
        "question_keys",
        sa.Column("accepted_answers", postgresql.JSONB(), nullable=False, server_default="[]"),
    )

    # 5. Keyless public view: ensures application/reporting queries without keys
    op.execute(
        """
        CREATE OR REPLACE VIEW v_questions_public AS
        SELECT
            id,
            type,
            chapter_id,
            concept_id,
            difficulty,
            language,
            stem,
            options,
            pool,
            origin,
            review_status,
            variant_group_id,
            created_at,
            updated_at
        FROM questions;
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_questions_public;")
    op.drop_column("question_keys", "accepted_answers")
    op.drop_column("questions", "pool")
    op.drop_index("uq_quiz_attempts_active_student_assessed", table_name="quiz_attempts")
    op.drop_column("quiz_attempts", "mode")
