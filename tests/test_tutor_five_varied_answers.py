"""Automated Tests for 5 Varied Student Answers to One Math Problem.

Problem: SSC General Math Chapter 3.1 Question 3
"a - b = 4 এবং ab = 60 হলে, a + b এর মান কত?"

Tests:
1. Case 1: Wrong formula misconception ((a-b)^2 + 2ab instead of 4ab)
2. Case 2: Linear addition fallacy (4 + 60 = 64)
3. Case 3: Partial / incomplete calculation ((a+b)^2 = 256, square root missing)
4. Case 4: Negative root query (why -16 is also valid)
5. Case 5: DIFFERENT VALID METHOD (Quadratic equation / substitution), which MUST BE ACCEPTED!
"""

import asyncio
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath("."))

from core.common.database import AsyncSessionLocal
from core.chat.math_engine import parse_math_query, lookup_math_item, handle_student_math_interaction


@pytest.mark.asyncio
async def test_five_varied_answers_to_single_problem():
    async with AsyncSessionLocal() as session:
        intent = parse_math_query("chapter 3 er 3 no", default_class=9)
        res = await lookup_math_item(session, intent)
        assert res.status == "single_match"
        assert res.item is not None
        item = res.item

        # Verify problem context
        assert "a - b = 4" in item["question_text"]
        assert "ab = 60" in item["question_text"]

        print("\n" + "=" * 70)
        print("TESTING 5 VARIED STUDENT RESPONSES TO CH 3.1 Q3")
        print("=" * 70)

        # -------------------------------------------------------------
        # CASE 1: Wrong Formula Misconception (+2ab instead of +4ab)
        # -------------------------------------------------------------
        msg_1 = "আমার হিসেবে তো ৮ আসছে কারণ (a-b)² + 2ab = ১৬ + ১২০ = ১৩৬"
        reply_1 = handle_student_math_interaction(item, msg_1)
        print("\n--- CASE 1: Formula Misconception (+2ab) ---")
        print(reply_1)
        assert "২ab" in reply_1 or "2ab" in reply_1
        assert "৪ab" in reply_1 or "4ab" in reply_1
        assert "±16" in reply_1 or "16" in reply_1

        # -------------------------------------------------------------
        # CASE 2: Linear Addition Fallacy (4 + 60 = 64)
        # -------------------------------------------------------------
        msg_2 = "a - b = 4 আর ab = 60 হলে তো a + b = 64 হবে, কারণ ৪ আর ৬০ যোগ করলেই তো হয়"
        reply_2 = handle_student_math_interaction(item, msg_2)
        print("\n--- CASE 2: Linear Addition Fallacy (64) ---")
        print(reply_2)
        assert "গুণফল" in reply_2
        assert "৬৪" in reply_2 or "64" in reply_2
        assert "যোগফল নয়" in reply_2 or "গুণফলকে" in reply_2

        # -------------------------------------------------------------
        # CASE 3: Incomplete / Partial Calculation (Found 256)
        # -------------------------------------------------------------
        msg_3 = "আমার হিসেবে উত্তর ২৫৬ এসেছে, (a-b)² + 4ab = ১৬ + ২৪০ = ২৫৬"
        reply_3 = handle_student_math_interaction(item, msg_3)
        print("\n--- CASE 3: Incomplete Calculation (256) ---")
        print(reply_3)
        assert "২৫৬" in reply_3 or "256" in reply_3
        assert "বর্গমূল" in reply_3
        assert "একদম ঠিকঠাক করেছ" in reply_3 or "(a+b)^2" in reply_3 or "(a+b)²" in reply_3

        # -------------------------------------------------------------
        # CASE 4: Negative Root Neglect Query
        # -------------------------------------------------------------
        msg_4 = "শুধু ১৬ হবে না? -১৬ কেন হবে? বর্গমূল তো ধনাত্মক হওয়ার কথা"
        reply_4 = handle_student_math_interaction(item, msg_4)
        print("\n--- CASE 4: Negative Root Query ---")
        print(reply_4)
        assert "ঋণাত্মক" in reply_4 or "ধনাত্মক" in reply_4
        assert "-16" in reply_4 or "-১৬" in reply_4

        # -------------------------------------------------------------
        # CASE 5: DIFFERENT VALID METHOD (Quadratic Substitution)
        # MUST BE ACCEPTED AND PRAISED!
        # -------------------------------------------------------------
        msg_5 = (
            "আমি সূত্রে যাইনি। আমি বিকল্প পদ্ধতিতে করেছি: ab = 60 এবং a = b + 4, "
            "তাই (b+4)b = 60 => b² + 4b - 60 = 0 => (b+10)(b-6) = 0। "
            "তাহলে b = 6 হলে a = 10, ফলে a+b = 16। আবার b = -10 হলে a = -6, ফলে a+b = -16। উত্তর ±16।"
        )
        reply_5 = handle_student_math_interaction(item, msg_5)
        print("\n--- CASE 5: Different VALID Method (Quadratic Substitution) ---")
        print(reply_5)
        # MUST BE ACCEPTED!
        assert "চমৎকার" in reply_5 or "প্রশংসনীয়" in reply_5
        assert "সম্পূর্ণ সঠিক" in reply_5 or "নির্ভুল" in reply_5
        assert "বিকল্প পদ্ধতি" in reply_5 or "দ্বিঘাত সমীকরণ" in reply_5
        assert "±16" in reply_5 or "16" in reply_5

        print("\n" + "=" * 70)
        print("ALL 5 VARIED CASES TESTED SUCCESSFULLY!")
        print("=" * 70)


async def main():
    await test_five_varied_answers_to_single_problem()


if __name__ == "__main__":
    asyncio.run(main())
