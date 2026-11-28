"""Import teacher grading CSV and record approvals with cryptographic hash and audit log.

Hard constraints:
- Only an active account with role in ('reviewer', 'teacher', 'admin') can approve.
- approved_solution_hash is SHA-256 of sorted steps + final_answer + method.
- Every approval writes to math_solutions AND inserts an audit_log record.
"""

import argparse
import csv
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://thinkbuddy:thinkbuddy_dev_password@127.0.0.1:5432/thinkbuddy"
)


def compute_solution_hash(steps: list | dict | str, final_answer: str, method: str | None) -> str:
    """Compute deterministic SHA-256 hash of solution content."""
    content_str = json.dumps(steps, sort_keys=True) + str(final_answer or "") + str(method or "")
    return hashlib.sha256(content_str.encode("utf-8")).hexdigest()


def import_teacher_approvals(csv_path: str, reviewer_email: str, dry_run: bool = False):
    if not os.path.isfile(csv_path):
        print(f"Error: CSV file not found at {csv_path}", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # 1. Verify reviewer account authorization
        cur.execute(
            "SELECT id, email, role, status, display_name FROM users WHERE email = %s;",
            (reviewer_email,)
        )
        reviewer = cur.fetchone()

        if not reviewer:
            # Check if any reviewer exists with role='reviewer'
            cur.execute(
                "SELECT id, email, role, status, display_name FROM users WHERE role IN ('reviewer', 'teacher') LIMIT 1;"
            )
            reviewer = cur.fetchone()

        if not reviewer:
            raise PermissionError(
                f"No authorized reviewer found with email '{reviewer_email}'. "
                "Only users with role in ('reviewer', 'teacher', 'admin') can approve solutions."
            )

        if reviewer["role"] not in ("reviewer", "teacher", "admin"):
            raise PermissionError(
                f"User '{reviewer['email']}' has role '{reviewer['role']}'. "
                "Only accounts with role in ('reviewer', 'teacher', 'admin') can approve."
            )

        if reviewer["status"] != "active":
            raise PermissionError(
                f"Reviewer account '{reviewer['email']}' is not active (status: {reviewer['status']})."
            )

        reviewer_id = reviewer["id"]
        print(f"Authorized Reviewer: {reviewer['display_name']} ({reviewer['email']}, Role: {reviewer['role']}, ID: {reviewer_id})")

        # 2. Read CSV rows
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        print(f"Total rows in CSV: {len(rows)}")

        approved_count = 0
        rejected_count = 0
        skipped_count = 0
        now = datetime.now(timezone.utc)

        for row in rows:
            item_id_str = row.get("item_id", "").strip()
            teacher_grade = row.get("teacher_grade", "").strip()
            teacher_notes = row.get("teacher_notes", "").strip()

            if not teacher_grade:
                skipped_count += 1
                continue

            # Fetch matching item and solution
            cur.execute("""
                SELECT s.id AS solution_id, s.steps, s.final_answer, s.method, s.verification_status,
                       i.id AS item_id, i.question_no, i.exercise_label
                FROM math_items_v2 i
                JOIN math_solutions s ON s.item_id = i.id
                WHERE i.id = %s;
            """, (item_id_str,))
            match = cur.fetchone()

            if not match:
                print(f"Warning: No solution found for item_id {item_id_str}, skipping.")
                skipped_count += 1
                continue

            sol_id = match["solution_id"]
            sol_hash = compute_solution_hash(match["steps"], match["final_answer"], match["method"])

            grade_upper = teacher_grade.upper()
            is_approved = grade_upper in ("APPROVED", "PASS", "CORRECT", "A", "YES", "VALID")
            is_rejected = grade_upper in ("REJECTED", "FAIL", "INCORRECT", "WRONG", "NO", "INVALID")

            if is_approved:
                new_status = "teacher_approved"
                action_name = "math_solution.teacher_approved"
                review_text = f"Approved by teacher. Grade: {teacher_grade}. Notes: {teacher_notes or 'None'}"

                if not dry_run:
                    # Update math_solutions
                    cur.execute("""
                        UPDATE math_solutions
                        SET verification_status = %s,
                            reviewed_by = %s,
                            reviewed_at = %s,
                            approved_solution_hash = %s,
                            review_notes = %s
                        WHERE id = %s;
                    """, (new_status, str(reviewer_id), now, sol_hash, review_text, sol_id))

                    # Insert audit log entry
                    cur.execute("""
                        INSERT INTO audit_log (id, actor_id, action, target_type, target_id, meta, at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """, (
                        str(uuid.uuid4()),
                        str(reviewer_id),
                        action_name,
                        "math_solution",
                        str(sol_id),
                        json.dumps({
                            "item_id": item_id_str,
                            "approved_solution_hash": sol_hash,
                            "teacher_grade": teacher_grade,
                            "teacher_notes": teacher_notes,
                            "reviewer_email": reviewer["email"],
                        }),
                        now
                    ))
                approved_count += 1

            elif is_rejected:
                new_status = "needs_teacher"
                action_name = "math_solution.teacher_rejected"
                review_text = f"Rejected by teacher. Grade: {teacher_grade}. Notes: {teacher_notes or 'None'}"

                if not dry_run:
                    cur.execute("""
                        UPDATE math_solutions
                        SET verification_status = %s,
                            reviewed_by = %s,
                            reviewed_at = %s,
                            approved_solution_hash = NULL,
                            review_notes = %s
                        WHERE id = %s;
                    """, (new_status, str(reviewer_id), now, review_text, sol_id))

                    cur.execute("""
                        INSERT INTO audit_log (id, actor_id, action, target_type, target_id, meta, at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """, (
                        str(uuid.uuid4()),
                        str(reviewer_id),
                        action_name,
                        "math_solution",
                        str(sol_id),
                        json.dumps({
                            "item_id": item_id_str,
                            "teacher_grade": teacher_grade,
                            "teacher_notes": teacher_notes,
                            "reviewer_email": reviewer["email"],
                        }),
                        now
                    ))
                rejected_count += 1
            else:
                print(f"Unknown grade '{teacher_grade}' for item {item_id_str}, skipping.")
                skipped_count += 1

        if not dry_run:
            conn.commit()
            print("\nDatabase transaction COMMITTED.")
        else:
            conn.rollback()
            print("\nDRY-RUN completed (no changes committed).")

        print(f"Summary: Approved={approved_count}, Rejected={rejected_count}, Skipped={skipped_count}")

    except Exception as e:
        conn.rollback()
        print(f"Transaction failed and rolled back: {e}", file=sys.stderr)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import teacher approvals from CSV into math_solutions and audit_log.")
    parser.add_argument("--csv", default="audit_math/teacher_grading_100_items.csv", help="Path to grading CSV")
    parser.add_argument("--reviewer-email", default="nctb.math.reviewer@thinkbuddy.org", help="Email of authorized reviewer")
    parser.add_argument("--dry-run", action="store_true", help="Simulate import without committing changes")

    args = parser.parse_args()
    import_teacher_approvals(args.csv, args.reviewer_email, dry_run=args.dry_run)
