import os
import re
import pytest

# Specific test phrases and textbook answers that must NEVER be hardcoded into runtime code
BANNED_TEST_PHRASES = [
    r"tan\s*A\s*=\s*\\sqrt\{3\}",
    r"tan\s*A\s*=\s*root\s*3",
    r"A\s*=\s*60\^?\\circ",
    r"A\s*=\s*30\^?\\circ",
    r"১০\s*I1'\s*\+",
    r"সমান্তরাল মূল সমান হবে",
    r"মাথায়\s*মাথায়",
    r"মাথা\s*চাপো",
    r"৬৪২৫",
    r"১০,০৫০",
    r"10,050",
    r"নিচের কোন ফলাফলটি ৯ দ্বারা বিভাজ্য",
]

# Directories that contain runtime logic (excluding test seed scripts and migrations)
RUNTIME_DIRS = [
    "core/chat",
    "core/curriculum",
    "rag"
]

def test_no_hardcoded_math_answers_in_runtime_code():
    """Scans all runtime logic to ensure zero test-specific math answers or overrides exist."""
    violations = []

    for r_dir in RUNTIME_DIRS:
        if not os.path.exists(r_dir):
            continue
        for root, _, files in os.walk(r_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                file_path = os.path.join(root, f)
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read()
                
                for pattern in BANNED_TEST_PHRASES:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        violations.append((file_path, pattern, len(matches)))

    if violations:
        msg = "Hardcoded math answers or test-specific logic detected in runtime code:\n"
        for fpath, pat, count in violations:
            msg += f"  - {fpath}: pattern '{pat}' matched {count} times\n"
        pytest.fail(msg)


def test_tutor_diagnostics_not_hardcoded_to_item_ids():
    """Scans handle_student_math_interaction to ensure diagnostics are driven by mathematical concepts, not hardcoded question IDs or item IDs."""
    math_engine_path = os.path.join("core", "chat", "math_engine.py")
    assert os.path.exists(math_engine_path), "math_engine.py must exist"

    with open(math_engine_path, "r", encoding="utf-8") as f:
        code = f.read()

    # Extract handle_student_math_interaction function body
    match = re.search(r'def handle_student_math_interaction\(.*?\n(?=def |\Z)', code, re.DOTALL)
    assert match, "handle_student_math_interaction function must be present"
    func_body = match.group(0)

    # Invariant: diagnostics must NOT branch on item IDs or specific question numbers
    prohibited_patterns = [
        r'item\["id"\]',
        r'item\.get\("id"\)',
        r'item\["question_no"\]',
        r'item\.get\("question_no"\)',
        r'item\["exercise_label"\]\s*==',
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',  # No literal UUIDs in diagnostics
    ]

    for pat in prohibited_patterns:
        m = re.findall(pat, func_body)
        assert not m, f"Found prohibited hardcoded check in tutor diagnostics: {pat}"

    print("PASS: Tutor diagnostics are strictly driven by mathematical concepts and free of item ID hardcoding!")


if __name__ == "__main__":
    test_no_hardcoded_math_answers_in_runtime_code()
    test_tutor_diagnostics_not_hardcoded_to_item_ids()
    print("PASS: Zero hardcoded math answers found in runtime codebase!")
