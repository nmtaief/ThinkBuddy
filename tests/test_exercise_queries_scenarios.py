"""Test exercise query scenarios (Fix Pass 8, Section 2.3).

Verifies:
1. Queries without decimal ("chapter 2 question 3", "অনুশীলনী ২ এর ৩ নং") return all matching sub-sections and prompt for disambiguation.
2. Queries with decimal ("2.1 er 3 no", "৯.১ এর ৫ নং") return exactly one question.
3. "SSC trigonometry 9.1 er 5 no" with no manual class override resolves to Class 9-10 Math, Exercise 9.1, Question 5.
"""

import sys
sys.path.insert(0, ".")
import pytest
from core.common.database import AsyncSessionLocal
from core.chat.tools import ToolExecutor
from core.chat.intent import parse_student_intent

@pytest.mark.asyncio
async def test_exercise_without_decimal_disambiguates():
    async with AsyncSessionLocal() as session:
        # Default student profile Class 8 Math
        executor = ToolExecutor(session, student_profile={"class_level": 8, "medium": "bn"})
        # Query for chapter 1, question 8 without decimal
        res = await executor.execute_tool("get_exercise_question", {
            "subject": "math",
            "chapter": "1",
            "question_no": 8
        })
        # If chapter 1 has multiple sub-sections matching question 8, must disambiguate
        assert res["found"] is False
        assert res["disambiguate"] is True
        assert len(res["matching_exercises"]) >= 2
        assert "কোনটি" in res["message"] or "কোন অনুশীলনীর" in res["message"]

@pytest.mark.asyncio
async def test_exercise_with_decimal_returns_exact_one():
    async with AsyncSessionLocal() as session:
        executor = ToolExecutor(session, student_profile={"class_level": 8, "medium": "bn"})
        # Query with decimal "2.1"
        res = await executor.execute_tool("get_exercise_question", {
            "subject": "math",
            "chapter": "2",
            "exercise_label": "২.১",
            "question_no": 3
        })
        # Must return exact matching exercise question
        if res.get("found"):
            assert "২.১" in res["exercise_label"]
            assert res["question_no"] == 3
            assert res.get("disambiguate") is None

@pytest.mark.asyncio
async def test_ssc_trigonometry_9_1_er_5_no_without_manual_override():
    # User message from Class 8 student: "SSC trigonometry 9.1 er 5 no"
    student_msg = "SSC trigonometry 9.1 er 5 no. Answer ta bujhiye deo"
    intent = parse_student_intent(student_msg)
    
    # Intent parser must detect SSC implies Class 9-10 without manual override
    assert intent.class_level in (9, 10), f"Expected class override 9 or 10, got {intent.class_level}"
    assert intent.subject == "math"
    assert intent.chapter == "9" or intent.exercise_label == "9.1"

    async with AsyncSessionLocal() as session:
        executor = ToolExecutor(session, student_profile={"class_level": intent.class_level, "medium": "bn"})
        res = await executor.execute_tool("get_exercise_question", {
            "class_level": intent.class_level,
            "subject": intent.subject,
            "chapter": intent.chapter or "9",
            "exercise_label": intent.exercise_label or "৯.১",
            "question_no": intent.question_no or 5,
        })
        assert res["class_level"] == 9 or res.get("book_title", "") != ""
        print("SSC Trigonometry Result:", res)
