"""Automated tests for 5 held-out math problems with varied, messy student answers.

These 5 problems were NOT used in development:
1. Class 8 Ch 1 Q4(খ): Pattern series (6, 17, 28, 39, 50...) -> Student claims +10 increment
2. Class 8 Ch 9 Q1: Geometry acute angle difference (diff 5°) -> Student calculation error (claims 40°)
3. Class 8 Ch 11 Q1(ক): Statistics mean of 25 scores -> Student sum calculation error (claims 1800 / 72)
4. SSC Higher Math Ch 9.1 Q4(ক): Exponent identity (a^(1/3) - b^(1/3)) -> Student power confusion (claims a^3 - b^3)
5. SSC General Math Ch 3.1 Q6: Algebra (2x + 2/x = 3) -> Student provides valid alternative method (MUST BE ACCEPTED!)
"""

import asyncio
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath("."))

from core.common.database import AsyncSessionLocal
from core.chat.math_engine import parse_math_query, lookup_math_item, handle_student_math_interaction


@pytest.mark.asyncio
async def test_heldout_1_pattern_progression_misconception():
    """Held-out Problem 1: Class 8 Ch 1 Q4(খ) - Series difference misconception."""
    async with AsyncSessionLocal() as session:
        intent = parse_math_query("class 8 math chapter 1 er 4 no kh", default_class=8)
        res = await lookup_math_item(session, intent)
        assert res.status == "single_match"
        item = res.item
        assert "৬, ১৭, ২৮" in item["question_text"]

        student_msg = "পরের দুইটা তো ৫০ আর ৬০ হবে, ১০ করে বাড়ছে না?"
        reply = handle_student_math_interaction(item, student_msg)

        print("\n--- Held-out 1: Pattern Progression Misconception ---")
        print(reply)
        assert "১১" in reply or "11" in reply
        assert "১০ নয়" in reply or "১০ করে" in reply
        assert "৬১" in reply or "61" in reply
        assert "৭২" in reply or "72" in reply


@pytest.mark.asyncio
async def test_heldout_2_geometry_acute_angle_error():
    """Held-out Problem 2: Class 8 Ch 9 Q1 - Geometry calculation slip."""
    async with AsyncSessionLocal() as session:
        intent = parse_math_query("class 8 math chapter 9 er 1 no", default_class=8)
        res = await lookup_math_item(session, intent)
        assert res.status == "single_match"
        item = res.item
        assert "সূক্ষ্মকোণদ্বয়ের" in item["question_text"]

        student_msg = "ছোট কোণটা ৪০ হবে, ৯০ থেকে ৫ বিয়োগ করে ২ দিয়ে ভাগ করেছি"
        reply = handle_student_math_interaction(item, student_msg)

        print("\n--- Held-out 2: Geometry Acute Angle Error ---")
        print(reply)
        assert "৮৫" in reply or "85" in reply
        assert "৪২.৫" in reply or "42.5" in reply
        assert "৪০ নয়" in reply or "40" in reply


@pytest.mark.asyncio
async def test_heldout_3_statistics_mean_summation_error():
    """Held-out Problem 3: Class 8 Ch 11 Q1(ক) - Statistics summation slip."""
    async with AsyncSessionLocal() as session:
        intent = parse_math_query("class 8 math chapter 11 er 1 no ka", default_class=8)
        res = await lookup_math_item(session, intent)
        assert res.status == "single_match"
        item = res.item
        assert "গড়" in item["question_text"]

        student_msg = "যোগফল তো ১৮০০ আসছে, গড় ৭২ হবে"
        reply = handle_student_math_interaction(item, student_msg)

        print("\n--- Held-out 3: Statistics Mean Summation Slip ---")
        print(reply)
        assert "১৮০০" in reply or "1800" in reply
        assert "১৮৭৫" in reply or "1875" in reply
        assert "৭৫" in reply or "75" in reply


@pytest.mark.asyncio
async def test_heldout_4_higher_math_fractional_exponent_confusion():
    """Held-out Problem 4: SSC Higher Math Ch 9.1 Q4(ক) - Exponent power confusion."""
    async with AsyncSessionLocal() as session:
        intent = parse_math_query("class 9 higher math chapter 9.1 er 4 no ka", default_class=9)
        res = await lookup_math_item(session, intent)
        assert res.status == "single_match"
        item = res.item
        assert "a^(1/3)" in item["question_text"]

        student_msg = "এখানে তো a^3 - b^3 সূত্র হবে, তাই উত্তর a^3 - b^3 হবে না? a - b কেন?"
        reply = handle_student_math_interaction(item, student_msg)

        print("\n--- Held-out 4: Higher Math Exponent Power Confusion ---")
        print(reply)
        assert "সূচক" in reply or "ঘাত" in reply or "x^3" in reply or "x³" in reply
        assert "a - b" in reply
        assert "a^3 - b^3" in reply and "নয়" in reply


@pytest.mark.asyncio
async def test_heldout_5_algebra_different_valid_method():
    """Held-out Problem 5: SSC General Math Ch 3.1 Q6 - Valid alternative method."""
    async with AsyncSessionLocal() as session:
        intent = parse_math_query("chapter 3 er 6 no", default_class=9)
        res = await lookup_math_item(session, intent)
        assert res.status == "single_match"
        item = res.item
        assert "2x + 2/x = 3" in item["question_text"]

        student_msg = (
            "আমি ২ কমন নিয়ে x + 1/x = 3/2 করেছি, "
            "তারপর (x + 1/x)² - 2 = (3/2)² - 2 = 9/4 - 2 = 1/4 পেয়েছি। উত্তর ১/৪।"
        )
        reply = handle_student_math_interaction(item, student_msg)

        print("\n--- Held-out 5: Algebra Valid Alternative Method ---")
        print(reply)
        # MUST BE ACCEPTED AND PRAISED!
        assert "চমৎকার" in reply or "প্রশংসনীয়" in reply
        assert "বিকল্প পদ্ধতি" in reply
        assert "নির্ভুল" in reply or "সঠিক" in reply
