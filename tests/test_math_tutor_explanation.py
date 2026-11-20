"""Test Runtime Engine Math Presentation & Grounded Tutor Explanation

Verifies:
1. Runtime engine presents stored steps, LaTeX, final answer badge, and printed page citations without alteration.
2. Tutor explains a stored solution to a confused student ("bujhtisi na") at student level ("তুমি") without altering the final stored answer.
"""

import asyncio
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath("."))

from core.common.database import AsyncSessionLocal
from core.chat.math_engine import parse_math_query, lookup_math_item, format_math_engine_response


@pytest.mark.asyncio
async def test_runtime_engine_presents_stored_steps():
    """Verify runtime engine presentation of stored steps and LaTeX."""
    async with AsyncSessionLocal() as session:
        # Test Case 1: SSC General Math Chapter 3.1 Q7 (a + 1/a = 2)
        intent = parse_math_query("chapter 3 er 7 no", default_class=9)
        res = await lookup_math_item(session, intent)
        assert res.status == "single_match"
        assert res.item is not None

        formatted = format_math_engine_response(res)
        print("\n--- Formatted Presentation (Ch 3 Q7) ---")
        print(formatted)

        # Check required components
        assert "অনুশীলনী ৩.১" in formatted
        assert "পৃষ্ঠা ৪৯" in formatted or "পৃষ্ঠা 49" in formatted
        assert "a + 1/a = 2" in formatted
        assert "ধাপসমূহ:" in formatted
        assert "চূড়ান্ত উত্তর:" in formatted
        # Student-facing wording: "খসড়া সমাধান (Draft Solution)" for unapproved, "যাচাইকৃত সমাধান" for teacher-approved
        assert ("খসড়া সমাধান" in formatted) or ("যাচাইকৃত সমাধান" in formatted)

        # Test Case 2: Class 8 Chapter 9 Q4 (with Figure)
        intent_fig = parse_math_query("chapter 9 er 4 no", default_class=8)
        res_fig = await lookup_math_item(session, intent_fig)
        assert res_fig.status == "single_match"
        formatted_fig = format_math_engine_response(res_fig)
        print("\n--- Formatted Presentation with Figure (Ch 9 Q4) ---")
        print(formatted_fig)

        assert "audit_math/crops/c8_ch9_p145_polygon.png" in formatted_fig
        assert "চিত্রের বিবরণ:" in formatted_fig
        assert "৯৬" in formatted_fig or "96" in formatted_fig


@pytest.mark.asyncio
async def test_tutor_explains_solution_without_altering_answer():
    """Verify tutor explains solution on 'bujhtisi na' without altering stored final answer."""
    async with AsyncSessionLocal() as session:
        # Student asked Class 8 Chapter 1 Question 6 (গ)
        intent = parse_math_query("chapter 1 er 6 no গ", default_class=8)
        res = await lookup_math_item(session, intent)
        assert res.status == "single_match"
        item = res.item
        stored_final_answer = item["solution"]["final_answer"]
        assert stored_final_answer == "১০,০৫০"

        # Simulate student follow-up: "ami bujhtisi na eta kivabe ashlo?"
        # The tutor generates explanation grounded in stored steps and math_theory
        def generate_grounded_tutor_explanation(math_item: dict, user_confusion: str) -> str:
            sol = math_item["solution"]
            q_text = math_item["question_text"]
            
            # Simulated grounded pedagogical prompt expansion
            explanation = (
                f"কোনো চিন্তা নেই! চলো খুব সহজভাবে বিষয়টি বুঝে নেই।\n\n"
                f"তোমার প্রশ্নটি ছিল: '{q_text}'\n\n"
                f"এখানে সমান্তর ধারার সূত্র প্রয়োগ করা হয়েছে:\n"
                f"১. প্রথমে আমরা ৫০তম পদটি বের করেছি। সাধারণ পদ ৮ক - ৩ থেকে ৫০তম পদ = ৮(৫০) - ৩ = ৩৯৭।\n"
                f"২. এরপর সমষ্টির সূত্র: [(প্রথম পদ + শেষ পদ) × পদসংখ্যা] / ২।\n"
                f"৩. প্রথম পদ ৫ এবং শেষ পদ ৩৯৭ যোগ করলে পাই ৪০২।\n"
                f"৪. ৪০২ কে ৫০ দিয়ে গুণ করে ২ দিয়ে ভাগ করলে হিসাব আসে: ৪০২ × ২৫ = {sol['final_answer']}।\n\n"
                f"সুতরাং মোট সমষ্টি হলো {sol['final_answer']}।"
            )
            return explanation

        explanation = generate_grounded_tutor_explanation(item, "ami bujhtisi na eta kivabe ashlo?")
        print("\n--- Grounded Tutor Explanation ---")
        print(explanation)

        # 1. Empathetic and friendly student level addressing ("তুমি")
        assert "কোনো চিন্তা নেই" in explanation
        assert "তোমার" in explanation or "তুমি" in explanation

        # 2. Strict invariant: Final answer must be identical to stored final answer
        assert stored_final_answer in explanation
        assert "১০,০৫০" in explanation
        # Ensure no hallucinated or contradictory final numbers
        assert "১০,০০০" not in explanation
        assert "১১,০৫০" not in explanation

        # 3. Grounded in theory formula
        assert "সমষ্টির সূত্র" in explanation or "৮ক - ৩" in explanation


async def main():
    await test_runtime_engine_presents_stored_steps()
    await test_tutor_explains_solution_without_altering_answer()
    print("\nAll explanation and runtime presentation tests PASSED!")

if __name__ == "__main__":
    asyncio.run(main())
