import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from core.common.database import AsyncSessionLocal
from core.chat.math_engine import parse_math_query, lookup_math_item

async def test_pilot2_lookups():
    test_cases = [
        # (query, default_class, current_chapter, expected_status, exp_q, exp_has_figure)
        ("chapter 9 er 4 no", 8, None, "single_match", 4, True),
        ("অনুশীলনী ৯ এর ১১ নং", 8, None, "single_match", 11, True),
        ("chapter 11 er 10 no", 8, None, "single_match", 10, True),
        ("অনুশীলনী ১১ এর ১ নং", 8, None, "multiple_matches", 1, False), # 1(ক), 1(খ), 1(গ) chips
        ("chapter 9 er 1 no", 9, None, "single_match", 1, False), # Higher Math Ch 9
        ("chapter 3 er 7 no", 9, None, "single_match", 7, False), # General Math Ch 3.1
        ("page 49 er 5 no", 9, None, "single_match", 5, False), # Page 49 Q5: x - 1/x = 4
    ]

    async with AsyncSessionLocal() as session:
        for q, def_cls, cur_ch, exp_st, exp_q, exp_fig in test_cases:
            intent = parse_math_query(q, default_class=def_cls, current_chapter=cur_ch)
            res = await lookup_math_item(session, intent)
            print(f"Query: '{q}' (class {def_cls}) -> Status: {res.status}")
            assert res.status == exp_st, f"Expected {exp_st}, got {res.status} for '{q}'"
            if res.status == "single_match":
                assert res.item["question_no"] == exp_q
                if exp_fig:
                    assert res.item["needs_figure"] is True
                    assert len(res.item["figures"]) > 0
                    print(f"   Matched Q{exp_q} with figure: {res.item['figures'][0]['path']}")
                else:
                    print(f"   Matched Q{exp_q}: {res.item['question_text'][:50]}...")
            elif res.status == "multiple_matches":
                print(f"   Disambiguation chips returned: {len(res.chips)} chips: {[c['label'] for c in res.chips]}")

    print("\nAll Pilot 2 deterministic lookup tests PASSED successfully!")

if __name__ == "__main__":
    asyncio.run(test_pilot2_lookups())
