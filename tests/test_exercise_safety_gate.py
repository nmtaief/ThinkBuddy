"""Test exercise safety gate.
Verifies that get_exercise_question never returns one confident question
when several sub-sections match, returning all candidates so the model asks which one.
"""

import pytest
from core.chat.exercise_safety import resolve_exercise_candidates

def test_safety_gate_multiple_subsections_ambiguous():
    matched = [
        {"id": "1", "exercise_label": "অনুশীলনী ২.১", "question_no": 3, "question_text": "Q3 in 2.1"},
        {"id": "2", "exercise_label": "অনুশীলনী ২.২", "question_no": 3, "question_text": "Q3 in 2.2"},
    ]
    # Generic query without decimal
    result = resolve_exercise_candidates(matched, requested_label="অনুশীলনী ২", requested_qno=3)
    assert result["status"] == "ambiguous"
    assert result["question"] is None
    assert len(result["candidates"]) == 2
    assert "অনুশীলনী ২.১" in result["distinct_labels"]
    assert "অনুশীলনী ২.২" in result["distinct_labels"]
    assert "কোন অনুশীলনীর" in result["message"]

def test_safety_gate_specific_decimal_exact():
    matched = [
        {"id": "1", "exercise_label": "অনুশীলনী ২.১", "question_no": 3, "question_text": "Q3 in 2.1"},
        {"id": "2", "exercise_label": "অনুশীলনী ২.২", "question_no": 3, "question_text": "Q3 in 2.2"},
    ]
    # Specific query with decimal
    result = resolve_exercise_candidates(matched, requested_label="2.1", requested_qno=3)
    assert result["status"] == "exact"
    assert result["question"]["exercise_label"] == "অনুশীলনী ২.১"

def test_safety_gate_bangla_decimal_exact():
    matched = [
        {"id": "1", "exercise_label": "অনুশীলনী ৯.১", "question_no": 5, "question_text": "Q5 in 9.1"},
        {"id": "2", "exercise_label": "অনুশীলনী ৯.২", "question_no": 5, "question_text": "Q5 in 9.2"},
    ]
    # Specific query with Bangla decimal
    result = resolve_exercise_candidates(matched, requested_label="৯.১", requested_qno=5)
    assert result["status"] == "exact"
    assert result["question"]["exercise_label"] == "অনুশীলনী ৯.১"

def test_safety_gate_single_match_exact():
    matched = [
        {"id": "1", "exercise_label": "অনুশীলনী ১", "question_no": 3, "question_text": "Q3 in 1"},
    ]
    result = resolve_exercise_candidates(matched, requested_label=None, requested_qno=3)
    assert result["status"] == "exact"
    assert result["question"]["exercise_label"] == "অনুশীলনী ১"

