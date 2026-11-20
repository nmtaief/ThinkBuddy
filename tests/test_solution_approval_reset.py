"""Test cryptographic solution approval and automatic reset on solution modification.
"""

import hashlib
import json
import uuid
import psycopg2

def test_approval_and_trigger_reset():
    conn = psycopg2.connect("postgresql://thinkbuddy:thinkbuddy_dev_password@127.0.0.1:5432/thinkbuddy")
    cur = conn.cursor()

    # 1. Ensure a reviewer account exists in users table
    cur.execute("SELECT id FROM users WHERE role = 'reviewer' LIMIT 1;")
    row = cur.fetchone()
    if row:
        reviewer_id = row[0]
    else:
        reviewer_id = uuid.uuid4()
        cur.execute("""
        INSERT INTO users (id, auth_provider, auth_uid, email, role, status, display_name, locale, has_valid_attestation, has_parental_consent)
        VALUES (%s, 'system_reviewer', 'rev_nctb_001', 'nctb.math.reviewer@thinkbuddy.org', 'reviewer', 'active', 'NCTB Certified Math Reviewer', 'bn', TRUE, TRUE);
        """, (str(reviewer_id),))
        conn.commit()
    print(f"Reviewer Account Verified: {reviewer_id}")

    # 2. Pick a test solution row
    cur.execute("SELECT id, steps, final_answer, method FROM math_solutions LIMIT 1;")
    sol_id, steps, final_ans, method = cur.fetchone()

    # 3. Compute hash and approve solution
    content_str = json.dumps(steps, sort_keys=True) + str(final_ans) + str(method or "")
    sol_hash = hashlib.sha256(content_str.encode('utf-8')).hexdigest()

    cur.execute("""
    UPDATE math_solutions
    SET verification_status = 'teacher_approved',
        reviewed_by = %s,
        reviewed_at = NOW(),
        approved_solution_hash = %s,
        review_notes = 'Verified step-by-step by NCTB certified teacher.'
    WHERE id = %s;
    """, (str(reviewer_id), sol_hash, sol_id))
    conn.commit()

    # Verify approved state
    cur.execute("SELECT verification_status, reviewed_by, reviewed_at, approved_solution_hash FROM math_solutions WHERE id = %s;", (sol_id,))
    v_stat, r_by, r_at, app_hash = cur.fetchone()
    assert v_stat == 'teacher_approved', f"Expected teacher_approved, got {v_stat}"
    assert app_hash == sol_hash, f"Expected {sol_hash}, got {app_hash}"
    assert str(r_by) == str(reviewer_id), f"Expected {reviewer_id}, got {r_by}"
    print(f"Approval Applied Successfully: status={v_stat}, hash={app_hash[:12]}...")

    # 4. Modify solution content (simulate edit)
    cur.execute("""
    UPDATE math_solutions
    SET final_answer = 'Altered Answer for Test'
    WHERE id = %s;
    """, (sol_id,))
    conn.commit()

    # 5. Check trigger reset
    cur.execute("SELECT verification_status, reviewed_by, reviewed_at, approved_solution_hash FROM math_solutions WHERE id = %s;", (sol_id,))
    v_stat_after, r_by_after, r_at_after, app_hash_after = cur.fetchone()

    print(f"Post-Edit State: status={v_stat_after}, reviewed_by={r_by_after}, hash={app_hash_after}")
    assert v_stat_after == 'needs_teacher', f"Expected status reset to needs_teacher, got {v_stat_after}"
    assert r_by_after is None, f"Expected reviewed_by reset to None, got {r_by_after}"
    assert r_at_after is None, f"Expected reviewed_at reset to None, got {r_at_after}"
    assert app_hash_after is None, f"Expected approved_solution_hash reset to None, got {app_hash_after}"
    print("Trigger Security Check PASSED: Approval was automatically revoked on solution edit!")

    # Restore original solution
    cur.execute("""
    UPDATE math_solutions
    SET final_answer = %s,
        verification_status = 'verified_symbolic'
    WHERE id = %s;
    """, (final_ans, sol_id))
    conn.commit()

    cur.close()
    conn.close()

if __name__ == "__main__":
    test_approval_and_trigger_reset()
