"""Add approved_solution_hash, reviewed_at and trigger to reset approval on solution edit

Revision ID: 0029_math_solution_approval_hash_and_triggers
Revises: 0028_math_items_v2
Create Date: 2026-11-16 19:30:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0029_math_solution_approval_hash_and_triggers"
down_revision: Union[str, None] = "0028_math_items_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add approval tracking columns to math_solutions
    op.add_column("math_solutions", sa.Column("approved_solution_hash", sa.String(64), nullable=True))
    op.add_column("math_solutions", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))

    # 2. Create trigger function to enforce reviewer role authorization and reset approval on edit
    op.execute("""
    CREATE OR REPLACE FUNCTION trg_reset_math_solution_approval_on_edit()
    RETURNS TRIGGER AS $$
    DECLARE
        rev_role VARCHAR;
        rev_status VARCHAR;
    BEGIN
        -- Security Rule: Only an active reviewer, teacher, or admin account can be set in reviewed_by
        IF NEW.reviewed_by IS NOT NULL THEN
            BEGIN
                SELECT role, status INTO rev_role, rev_status
                FROM users
                WHERE id = NEW.reviewed_by::uuid;
            EXCEPTION WHEN invalid_text_representation THEN
                RAISE EXCEPTION 'reviewed_by must be a valid UUID of a user';
            END;

            IF rev_role IS NULL THEN
                RAISE EXCEPTION 'reviewed_by references non-existent user %', NEW.reviewed_by;
            END IF;

            IF rev_role NOT IN ('reviewer', 'teacher', 'admin') THEN
                RAISE EXCEPTION 'User % has role %, but only reviewer, teacher, or admin accounts can approve solutions', NEW.reviewed_by, rev_role;
            END IF;

            IF rev_status != 'active' THEN
                RAISE EXCEPTION 'User % is not active (status: %)', NEW.reviewed_by, rev_status;
            END IF;
        END IF;

        -- If steps, final_answer, or method change, invalidate any existing teacher approval
        IF TG_OP = 'UPDATE' THEN
            IF (NEW.steps::text IS DISTINCT FROM OLD.steps::text) OR 
               (NEW.final_answer IS DISTINCT FROM OLD.final_answer) OR 
               (NEW.method IS DISTINCT FROM OLD.method) THEN
                IF OLD.approved_solution_hash IS NOT NULL THEN
                    NEW.approved_solution_hash := NULL;
                    NEW.reviewed_by := NULL;
                    NEW.reviewed_at := NULL;
                    NEW.verification_status := 'needs_teacher';
                END IF;
            END IF;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    # 3. Attach trigger to math_solutions
    op.execute("""
    CREATE TRIGGER trg_reset_math_solution_approval
    BEFORE INSERT OR UPDATE ON math_solutions
    FOR EACH ROW
    EXECUTE FUNCTION trg_reset_math_solution_approval_on_edit();
    """)


def downgrade() -> None:
    # 1. Drop trigger and function
    op.execute("DROP TRIGGER IF EXISTS trg_reset_math_solution_approval ON math_solutions;")
    op.execute("DROP FUNCTION IF EXISTS trg_reset_math_solution_approval_on_edit();")

    # 2. Remove columns
    op.drop_column("math_solutions", "reviewed_at")
    op.drop_column("math_solutions", "approved_solution_hash")
