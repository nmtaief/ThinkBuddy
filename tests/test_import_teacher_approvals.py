"""Integration test for teacher approval import, hashing, and audit log recording.
"""

import csv
import os
import sys
import tempfile
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from scripts.import_teacher_approvals import import_teacher_approvals, compute_solution_hash

DB_URL = "postgresql://thinkbuddy:thinkbuddy_dev_password@127.0.0.1:5432/thinkbuddy"

def test_import_teacher_approvals():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # 1. Fetch a real item to test
    cur.execute("""
        SELECT i.id, s.id, s.steps, s.final_answer, s.method
        FROM math_items_v2 i
        JOIN math_solutions s ON s.item_id = i.id
        LIMIT 1;
    """)
    row = cur.fetchone()
    assert row, "Database must have at least one math item"
    item_id, sol_id, steps, final_ans, method = row

    # Ensure reviewer exists
    cur.execute("SELECT id, email FROM users WHERE role = 'reviewer' LIMIT 1;")
    reviewer = cur.fetchone()
    if not reviewer:
        rev_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO users (id, auth_provider, auth_uid, email, role, status, display_name, locale, has_valid_attestation, has_parental_consent)
            VALUES (%s, 'test_reviewer', 'rev_test_001', 'test.reviewer@thinkbuddy.org', 'reviewer', 'active', 'Test Math Reviewer', 'bn', TRUE, TRUE);
        """, (rev_id,))
        conn.commit()
        rev_email = 'test.reviewer@thinkbuddy.org'
    else:
        rev_id, rev_email = reviewer

    # 2. Create a temporary CSV with 1 approved row and 1 rejected row
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", encoding="utf-8", newline="") as tf:
        writer = csv.writer(tf)
        writer.writerow(["row_no", "item_id", "teacher_grade", "teacher_notes"])
        writer.writerow(["1", str(item_id), "APPROVED", "Teacher checked and confirmed accurate."])
        tmp_csv_path = tf.name

    try:
        # 3. Run import
        import_teacher_approvals(tmp_csv_path, reviewer_email=rev_email, dry_run=False)

        # 4. Verify in math_solutions
        cur.execute("""
            SELECT verification_status, reviewed_by, reviewed_at, approved_solution_hash, review_notes
            FROM math_solutions
            WHERE id = %s;
        """, (sol_id,))
        sol_row = cur.fetchone()
        v_status, r_by, r_at, app_hash, r_notes = sol_row

        expected_hash = compute_solution_hash(steps, final_ans, method)
        assert v_status == "teacher_approved", f"Expected 'teacher_approved', got {v_status}"
        assert str(r_by) == str(rev_id), f"Expected reviewed_by={rev_id}, got {r_by}"
        assert r_at is not None, "reviewed_at must be populated"
        assert app_hash == expected_hash, f"Expected hash {expected_hash}, got {app_hash}"
        assert "Teacher checked and confirmed accurate." in r_notes

        # 5. Verify in audit_log
        cur.execute("""
            SELECT actor_id, action, target_type, target_id, meta
            FROM audit_log
            WHERE target_id = %s AND action = 'math_solution.teacher_approved'
            ORDER BY at DESC LIMIT 1;
        """, (str(sol_id),))
        audit_row = cur.fetchone()
        assert audit_row, "Audit log entry must be present"
        assert str(audit_row[0]) == str(rev_id)
        assert audit_row[1] == "math_solution.teacher_approved"
        assert audit_row[2] == "math_solution"

        print("TEST PASSED: Teacher approval import, hashing, and audit log verified!")

    finally:
        # Clean up test modifications
        cur.execute("""
            UPDATE math_solutions
            SET verification_status = 'verified_symbolic',
                reviewed_by = NULL,
                reviewed_at = NULL,
                approved_solution_hash = NULL,
                review_notes = NULL
            WHERE id = %s;
        """, (sol_id,))
        cur.execute("DELETE FROM audit_log WHERE target_id = %s;", (str(sol_id),))
        conn.commit()
        cur.close()
        conn.close()
        if os.path.exists(tmp_csv_path):
            os.remove(tmp_csv_path)

if __name__ == "__main__":
    test_import_teacher_approvals()
