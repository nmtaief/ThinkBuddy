"""Automated Tests for Runtime Math Tutor Student Scenarios.

Verifies:
1. Scenario A: Student disagrees with a stored answer -> Tutor defends verified answer, identifies discrepancy step, never alters final answer.
2. Scenario B: Student gives a wrong answer -> Tutor identifies misconception constructively without mockery.
3. Scenario C: Student asks a question with no verified item -> Deterministic polite fallback, no hallucination, NO photo offer.
"""

import asyncio
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath("."))

from core.common.database import AsyncSessionLocal
from core.chat.math_engine import (
    parse_math_query,
    lookup_math_item,
    format_math_engine_response,
    handle_student_math_interaction,
)


@pytest.mark.asyncio
async def test_scenario_a_student_disagrees_with_stored_answer():
    """Verify tutor defends verified answer and dynamically diagnoses student's own working."""
    async with AsyncSessionLocal() as session:
        # SSC General Math Ch 3.1 Q5: x - 1/x = 4 => x^4 + 1/x^4 = 322
        intent = parse_math_query("chapter 3 er 5 no", default_class=9)
        res = await lookup_math_item(session, intent)
        assert res.status == "single_match"
        assert res.item is not None

        item = res.item
        stored_answer = item["solution"]["final_answer"]
        assert "322" in stored_answer or "৩২২" in stored_answer

        # Test Case 1: Student challenges with specific working (subtracted 4 from 324)
        student_challenge_1 = "না, আমার হিসেবে তো ৩২০ আসছে, কারণ ১৮ এর বর্গ ৩২৪ থেকে ৪ বিয়োগ করেছি!"
        tutor_reply_1 = handle_student_math_interaction(item, student_challenge_1)

        print("\n--- Scenario A1: Student Disagreement with Specific Working ---")
        print(tutor_reply_1)

        # 1. Stored answer MUST remain intact in reply
        assert "322" in tutor_reply_1 or "৩২২" in tutor_reply_1
        # 2. Must dynamically address student's specific working (324 and subtracting 4 vs 2)
        assert "৩২৪" in tutor_reply_1
        assert "৪" in tutor_reply_1 or "4" in tutor_reply_1
        assert "তোমার কাজের পর্যালোচনা" in tutor_reply_1

        # Test Case 2: Student challenges with different claim
        student_challenge_2 = "না, উত্তর তো ১৬ হবে কারণ (a+b)² = (a-b)² + 2ab"
        tutor_reply_2 = handle_student_math_interaction(item, student_challenge_2)

        print("\n--- Scenario A2: Student Disagreement with Alternate Working ---")
        print(tutor_reply_2)

        # Reply 2 must differ dynamically from Reply 1 (not a fixed canned reply!)
        assert tutor_reply_1 != tutor_reply_2
        assert "৪ab" in tutor_reply_2 or "4ab" in tutor_reply_2


@pytest.mark.asyncio
async def test_scenario_b_student_gives_wrong_answer():
    """Verify tutor corrects misconception with pedagogical constructive feedback."""
    async with AsyncSessionLocal() as session:
        # Class 8 Ch 1 Q2: ১ থেকে ১০০ এর মধ্যে মৌলিক সংখ্যা কয়টি? (Ans: ২৫)
        intent = parse_math_query("chapter 1 er 2 no", default_class=8)
        res = await lookup_math_item(session, intent)
        assert res.status == "single_match"
        item = res.item
        assert "২৫" in item["solution"]["final_answer"]

        # Student claims 24 prime numbers because 1 is prime
        wrong_student_answer = "১ থেকে ১০০ এর মধ্যে মৌলিক সংখ্যা ২৪টি কারণ ১ ও তো মৌলিক!"
        tutor_reply = handle_student_math_interaction(item, wrong_student_answer)

        print("\n--- Scenario B: Student Wrong Answer Correction ---")
        print(tutor_reply)

        # 1. Corrects the misconception that 1 is prime
        assert "১ কিন্তু মৌলিক সংখ্যা নয়" in tutor_reply
        # 2. Explains the definition of prime numbers
        assert "গুণনীয়ক" in tutor_reply or "উৎপাদক" in tutor_reply
        # 3. Re-affirms the verified correct answer (২৫)
        assert "২৫" in tutor_reply


@pytest.mark.asyncio
async def test_scenario_c_question_with_no_verified_item():
    """Verify system returns clean deterministic fallback with NO photo offer."""
    async with AsyncSessionLocal() as session:
        # Question not indexed in verified dataset: Class 9 Chapter 4.1 Q15
        intent = parse_math_query("class 9 math chapter 4.1 er 15 no", default_class=9)
        res = await lookup_math_item(session, intent)

        # 1. Must return not_found status
        assert res.status == "not_found"
        assert res.item is None

        formatted_msg = format_math_engine_response(res)
        print("\n--- Scenario C: Unverified / Missing Item Response ---")
        print(formatted_msg)

        # 2. Honest notification that item is not indexed yet
        assert "এখনও পাঠ্যবই ডাটাবেসে সূচিত করা হয়নি" in formatted_msg or "খুঁজে পাওয়া যায়নি" in formatted_msg
        # 3. References nearest chapter context
        assert "অধ্যায়" in formatted_msg
        # 4. STRICT RULE: NEVER offer photo upload!
        assert "ছবি" not in formatted_msg
        assert "photo" not in formatted_msg.lower()
        assert "upload" not in formatted_msg.lower()


async def main():
    await test_scenario_a_student_disagrees_with_stored_answer()
    await test_scenario_b_student_gives_wrong_answer()
    await test_scenario_c_question_with_no_verified_item()
    print("\nAll 3 runtime student interaction scenario tests PASSED successfully!")


if __name__ == "__main__":
    asyncio.run(main())
