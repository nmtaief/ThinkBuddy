"""Separate verified math data model

Revision ID: 0028_math_items_v2
Revises: 0027_rag_v8_schema_and_bge_m3_1024
Create Date: 2026-11-16 13:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0028_math_items_v2"
down_revision: Union[str, None] = "0027_rag_v8_schema_and_bge_m3_1024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. math_books
    op.create_table(
        "math_books",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("class_level", sa.Integer(), nullable=False, index=True),
        sa.Column("medium", sa.String(20), nullable=False, default="bangla"),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("version_year", sa.Integer(), nullable=False, default=2026),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("class_level", "medium", "title", name="uq_math_books_class_medium_title"),
    )

    # 2. math_chapters
    op.create_table(
        "math_chapters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("math_books.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("class_level", sa.Integer(), nullable=False, index=True),
        sa.Column("medium", sa.String(20), nullable=False, default="bangla"),
        sa.Column("chapter_number", sa.Integer(), nullable=False, index=True),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("title_ascii", sa.String(150), nullable=True),
        sa.Column("printed_page_start", sa.Integer(), nullable=False),
        sa.Column("printed_page_end", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("book_id", "chapter_number", name="uq_math_chapters_book_number"),
    )

    # 3. math_theory
    op.create_table(
        "math_theory",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("math_chapters.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("theory_type", sa.String(30), nullable=False),  # definition, formula, worked_example, rule
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("printed_page", sa.Integer(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # 4. math_exercises
    op.create_table(
        "math_exercises",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("math_chapters.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("exercise_label", sa.String(50), nullable=False),  # e.g. "অনুশীলনী ১", "অনুশীলনী ৩.১"
        sa.Column("exercise_label_ascii", sa.String(50), nullable=False),  # e.g. "1", "3.1"
        sa.Column("printed_page_start", sa.Integer(), nullable=False),
        sa.Column("printed_page_end", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("chapter_id", "exercise_label", name="uq_math_exercises_chap_label"),
    )

    # 5. math_items_v2 (extended separate math items)
    op.create_table(
        "math_items_v2",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("math_books.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("math_chapters.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("exercise_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("math_exercises.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("class_level", sa.Integer(), nullable=False, index=True),
        sa.Column("chapter_number", sa.Integer(), nullable=False, index=True),
        sa.Column("exercise_label", sa.String(50), nullable=False, index=True),
        sa.Column("item_type", sa.String(30), nullable=False, default="short"),  # mcq, short, creative, example, activity
        sa.Column("question_no", sa.Integer(), nullable=False, index=True),
        sa.Column("question_no_display", sa.String(20), nullable=False),  # Printed Bangla digits e.g. "১", "৩"
        sa.Column("subpart", sa.String(20), nullable=True),  # ক, খ, গ, ঘ
        sa.Column("stimulus_text", sa.Text(), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_text_ascii", sa.Text(), nullable=True),  # Normalized ASCII digits & text for fast regex lookup
        sa.Column("mcq_options", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("printed_page", sa.Integer(), nullable=False, index=True),
        sa.Column("pdf_page_index", sa.Integer(), nullable=False),
        sa.Column("needs_figure", sa.Boolean(), nullable=False, default=False),
        sa.Column("source_image_ref", sa.String(255), nullable=True),
        sa.Column("uncertain_chars", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("internal_answer_key", sa.Text(), nullable=True),  # From official উত্তরমালা
        sa.Column("read_1_text", sa.Text(), nullable=True),
        sa.Column("read_2_text", sa.Text(), nullable=True),
        sa.Column("diff_disagreement", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "chapter_id",
            "exercise_label",
            "question_no",
            "subpart",
            name="uq_math_items_v2_chap_label_qno_subpart",
        ),
    )
    op.create_index(
        "idx_math_items_v2_lookup",
        "math_items_v2",
        ["class_level", "chapter_number", "exercise_label", "question_no"],
    )
    op.create_index(
        "idx_math_items_v2_page_lookup",
        "math_items_v2",
        ["class_level", "printed_page", "question_no"],
    )

    # 6. math_figures
    op.create_table(
        "math_figures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("math_items_v2.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("crop_path", sa.String(255), nullable=False),
        sa.Column("structured_description", postgresql.JSON(astext_type=sa.Text()), nullable=True),  # shapes, labelled points, angles, measures
        sa.Column("needs_teacher_review", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 7. math_solutions
    op.create_table(
        "math_solutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("math_items_v2.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("steps", postgresql.JSON(astext_type=sa.Text()), nullable=False),  # Ordered list of explanation steps with KaTeX
        sa.Column("final_answer", sa.Text(), nullable=False),
        sa.Column("final_answer_ascii", sa.Text(), nullable=True),
        sa.Column("method", sa.Text(), nullable=False),  # e.g. "বীজগণিতীয় সূত্রাবলি", "জ্যামিতিক প্রমাণ"
        sa.Column("theory_page", sa.Integer(), nullable=True),  # Citation to textbook theory page
        sa.Column("model_version", sa.String(50), nullable=False, default="gemini-agent-v1"),
        sa.Column("prompt_version", sa.String(50), nullable=False, default="p15-tutor-v1"),
        sa.Column("verification_status", sa.String(30), nullable=False, default="unverified"),  # verified_symbolic, verified_double_solve, verified_answer_key, needs_teacher, unverified
        sa.Column("verifier_details", postgresql.JSON(astext_type=sa.Text()), nullable=True),  # SymPy evaluation result, answer key diff
        sa.Column("reviewed_by", sa.String(100), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("idx_math_solutions_status", "math_solutions", ["verification_status"])

    # 8. math_hints
    op.create_table(
        "math_hints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("math_items_v2.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("level", sa.Integer(), nullable=False),  # 1 (gentle nudging), 2 (key formula), 3 (breakdown)
        sa.Column("hint_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("item_id", "level", name="uq_math_hints_item_level"),
    )

    # 9. math_concepts
    op.create_table(
        "math_concepts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 10. math_item_concepts
    op.create_table(
        "math_item_concepts",
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("math_items_v2.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("concept_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("math_concepts.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("math_item_concepts")
    op.drop_table("math_concepts")
    op.drop_table("math_hints")
    op.drop_index("idx_math_solutions_status", table_name="math_solutions")
    op.drop_table("math_solutions")
    op.drop_table("math_figures")
    op.drop_index("idx_math_items_v2_page_lookup", table_name="math_items_v2")
    op.drop_index("idx_math_items_v2_lookup", table_name="math_items_v2")
    op.drop_table("math_items_v2")
    op.drop_table("math_exercises")
    op.drop_table("math_theory")
    op.drop_table("math_chapters")
    op.drop_table("math_books")
