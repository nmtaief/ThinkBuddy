"""Create secure quiz engine tables for Milestone P04.

Revision ID: 0009_p04_secure_quiz_tables
Revises: 0008_p03_rest_and_p06a_prov
Create Date: 2026-10-24 19:00:00.000000

Per docs/03_DATA_MODEL.md §4, §6 and docs/05_SECURE_QUIZ.md:
- questions
- question_keys (isolated table for grading authority, zero leak to clients)
- quizzes
- quiz_attempts
- attempt_items
- attempt_events
- broad_submissions
- learning_signals
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0009_p04_secure_quiz_tables"
down_revision: str | None = "0008_p03_rest_and_p06a_prov"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. questions table
    op.create_table(
        "questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", sa.String(length=16), nullable=False),  # mcq, short, broad
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("concept_id", sa.String(length=64), nullable=True),
        sa.Column("difficulty", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("language", sa.String(length=8), nullable=False, server_default="bn"),
        sa.Column("stem", postgresql.JSONB(), nullable=False),  # structured content blocks
        sa.Column("options", postgresql.JSONB(), nullable=False, server_default="[]"),  # opaque option list without key
        sa.Column("rubric", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("explanation", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("source_chunk_ids", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("origin", sa.String(length=32), nullable=False, server_default="curated"),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="approved"),
        sa.Column("variant_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_questions_chapter_id", "questions", ["chapter_id"])
    op.create_index("ix_questions_concept_id", "questions", ["concept_id"])
    op.create_index("ix_questions_variant_group_id", "questions", ["variant_group_id"])
    op.create_index("ix_questions_type_review_status", "questions", ["type", "review_status"])

    # 2. question_keys table (strictly isolated for server-side grading authority)
    op.create_table(
        "question_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("correct_option_id", sa.String(length=64), nullable=True),  # for MCQ
        sa.Column("correct_text", sa.Text(), nullable=True),  # for short answer
        sa.Column("grading_rules", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("explanation", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_question_keys_question_id", "question_keys", ["question_id"])

    # 3. quizzes table
    op.create_table(
        "quizzes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False, server_default="Daily Quiz"),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="daily"),  # diagnostic, daily, review, chapter, practice
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="assessed"),  # practice, assessed
        sa.Column("time_limit_s", sa.Integer(), nullable=False, server_default="600"),
        sa.Column("per_question_limit_s", sa.Integer(), nullable=True),
        sa.Column("question_count", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_quizzes_student_id", "quizzes", ["student_id"])
    op.create_index("ix_quizzes_task_id", "quizzes", ["task_id"])

    # 4. quiz_attempts table
    op.create_table(
        "quiz_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("quiz_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="created"),  # created, active, submitted, expired, invalidated
        sa.Column("attempt_token", sa.String(length=128), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("integrity_score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("invalid_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_quiz_attempts_student_state", "quiz_attempts", ["student_id", "state"])
    op.create_index("ix_quiz_attempts_quiz_id", "quiz_attempts", ["quiz_id"])

    # 5. attempt_items table
    op.create_table(
        "attempt_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("served_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response", postgresql.JSONB(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("points", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("time_spent_ms", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_attempt_items_attempt_pos", "attempt_items", ["attempt_id", "position"], unique=True)
    op.create_index("ix_attempt_items_question_id", "attempt_items", ["question_id"])

    # 6. attempt_events table
    op.create_table(
        "attempt_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),  # app_background, focus_lost, screenshot_attempt, chat_attempt, etc.
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("meta", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_attempt_events_attempt_id", "attempt_events", ["attempt_id"])
    op.create_index("ix_attempt_events_type", "attempt_events", ["type"])

    # 7. broad_submissions table
    op.create_table(
        "broad_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("attempt_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("attempt_items.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("image_uris", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("ai_feedback", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("ai_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ai_reviewed"),  # ai_reviewed, teacher_pending, teacher_reviewed
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_broad_submissions_item_id", "broad_submissions", ["attempt_item_id"])

    # 8. learning_signals table
    op.create_table(
        "learning_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),  # quiz_wrong, quiz_slow, ai_question, ai_repeat, teacher_flag, task_skipped
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("concept_id", sa.String(length=64), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("ref_id", sa.String(length=64), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_learning_signals_student_source", "learning_signals", ["student_id", "source"])
    op.create_index("ix_learning_signals_chapter_id", "learning_signals", ["chapter_id"])


def downgrade() -> None:
    op.drop_table("learning_signals")
    op.drop_table("broad_submissions")
    op.drop_table("attempt_events")
    op.drop_table("attempt_items")
    op.drop_table("quiz_attempts")
    op.drop_table("quizzes")
    op.drop_table("question_keys")
    op.drop_table("questions")
