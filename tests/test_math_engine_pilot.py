import asyncio
import os
import sys

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath("."))

from core.common.database import AsyncSessionLocal
from core.chat.math_engine import parse_math_query, lookup_math_item

async def run_tests():
    print("=== Testing Query Parser ===")
    queries = [
        ("chapter 1 er 3 no", 8, None, 1, "অনুশীলনী ১", 3, None, None),
        ("অনুশীলনী ১ এর ৫ নং", 8, None, 1, "অনুশীলনী ১", 5, None, None),
        ("page 9 er 4 no", 8, None, None, None, 4, None, 9),
        ("6 no ক solve koro", 8, 1, 1, None, 6, "ক", None),
        ("অনুশীলনী ১ এর সবগুলো করে দাও", 8, None, 1, "অনুশীলনী ১", None, None, None),
        ("math chapter 3 er 5 no. math ta korre deo bujhtisi na ami", 8, None, 3, None, 5, None, None),
    ]

    for q, def_cls, cur_ch, exp_ch, exp_ex, exp_q, exp_sub, exp_pg in queries:
        intent = parse_math_query(q, default_class=def_cls, current_chapter=cur_ch)
        print(f"Query: '{q}'")
        print(f"  -> ch={intent.chapter_number}, ex={intent.exercise_label}, q={intent.question_no}, sub={intent.subpart}, pg={intent.printed_page}, whole={intent.is_whole_exercise}")

    print("\n=== Testing Live DB Lookup ===")
    test_lookups = [
        ("chapter 1 er 3 no", "single_match", 3, None),
        ("6 no ক solve koro", "single_match", 6, "ক"),
        ("অনুশীলনী ১ এর ৫ নং", "multiple_matches", 5, None),
        ("page 9 er 4 no", "multiple_matches", 4, None),
        ("অনুশীলনী ১ এর সবগুলো করে দাও", "whole_exercise", None, None),
        ("chapter 99 er 5 no", "not_found", None, None),
    ]

    async with AsyncSessionLocal() as session:
        for q, exp_status, exp_qno, exp_subpart in test_lookups:
            intent = parse_math_query(q, default_class=8, current_chapter=1)
            res = await lookup_math_item(session, intent)
            print(f"\nQuery: '{q}'")
            print(f"  Status: {res.status} (expected {exp_status})")
            if res.status == "single_match":
                print(f"  Item: Q{res.item['question_no']} ({res.item['subpart'] or '-'}) | Verified: {res.item['solution']['is_verified']}")
                print(f"  Question: {res.item['question_text'][:60]}...")
                print(f"  Answer: {res.item['solution']['final_answer']}")
                print(f"  Theory Page: {res.item['solution']['theory_page']}")
            elif res.status == "multiple_matches":
                print(f"  Chips returned ({len(res.chips)}): {[c['label'] for c in res.chips]}")
            elif res.status == "whole_exercise":
                print(f"  Total items: {len(res.exercise_items)} | 1st item: Q{res.exercise_items[0]['question_no']}")
            elif res.status == "not_found":
                print(f"  Fallback message: {res.message[:70]}...")

if __name__ == "__main__":
    asyncio.run(run_tests())
