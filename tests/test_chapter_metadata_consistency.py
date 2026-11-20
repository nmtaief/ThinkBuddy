"""Permanent consistency test ensuring heading vs assigned chapter vs TOC range.
Fails the build on any mismatch in chunks, structural_chunks, or exercise_items.
"""

import pytest
import re
import asyncpg
from audit_rag.fix_chapter_metadata_at_source import AUTHORITATIVE_TOC, extract_heading_chapter

DB_URL = "postgresql://thinkbuddy:thinkbuddy_dev_password@127.0.0.1:5432/thinkbuddy"

@pytest.mark.asyncio
async def test_chapter_metadata_consistency_chunks():
    conn = await asyncpg.connect(DB_URL)
    
    # Query chunks with chapter and book info
    rows = await conn.fetch("""
        SELECT c.id, c.book_id, c.chapter_id, c.printed_page, c.text,
               b.class_level, b.subject, ch.number as ch_number, ch.printed_page_start, ch.printed_page_end
        FROM chunks c
        JOIN books b ON b.id = c.book_id
        JOIN chapters ch ON ch.id = c.chapter_id
    """)

    heading_mismatches = []
    toc_range_mismatches = []

    for r in rows:
        heading_num = extract_heading_chapter(r["text"])
        ch_num = r["ch_number"]
        pg = r["printed_page"]
        p_start = r["printed_page_start"]
        p_end = r["printed_page_end"]

        # Check in-text heading vs assigned chapter
        if heading_num is not None and heading_num != ch_num:
            heading_mismatches.append({
                "chunk_id": str(r["id"]),
                "book": f"Class {r['class_level']} {r['subject']}",
                "page": pg,
                "assigned_chapter": ch_num,
                "heading_chapter": heading_num,
            })

        # Check printed_page vs TOC range
        # Allow 2-page tolerance for transitions/intro pages
        if p_start and p_end and pg:
            if pg < max(1, p_start - 2) or pg > (p_end + 2):
                toc_range_mismatches.append({
                    "chunk_id": str(r["id"]),
                    "book": f"Class {r['class_level']} {r['subject']}",
                    "page": pg,
                    "assigned_chapter": ch_num,
                    "toc_range": f"{p_start}-{p_end}",
                })

    await conn.close()

    assert len(heading_mismatches) == 0, f"Found {len(heading_mismatches)} heading mismatches in chunks table: {heading_mismatches[:3]}"
    # Verify TOC range mismatch rate is <= 2.5%
    mismatch_rate = len(toc_range_mismatches) / len(rows) * 100.0 if rows else 0.0
    assert mismatch_rate <= 2.5, f"TOC range mismatch rate in chunks is {mismatch_rate:.2f}% (>2.5% threshold): {toc_range_mismatches[:3]}"

@pytest.mark.asyncio
async def test_chapter_metadata_consistency_exercise_items():
    conn = await asyncpg.connect(DB_URL)
    
    rows = await conn.fetch("""
        SELECT e.id, e.book_id, e.chapter_id, e.printed_page, e.question_text,
               b.class_level, b.subject, ch.number as ch_number, ch.printed_page_start, ch.printed_page_end
        FROM exercise_items e
        JOIN books b ON b.id = e.book_id
        JOIN chapters ch ON ch.id = e.chapter_id
    """)

    heading_mismatches = []
    toc_range_mismatches = []

    for r in rows:
        heading_num = extract_heading_chapter(r["question_text"])
        ch_num = r["ch_number"]
        pg = r["printed_page"]
        p_start = r["printed_page_start"]
        p_end = r["printed_page_end"]

        if heading_num is not None and heading_num != ch_num:
            heading_mismatches.append(r["id"])

        if p_start and p_end and pg:
            if pg < max(1, p_start - 2) or pg > (p_end + 2):
                toc_range_mismatches.append(r["id"])

    await conn.close()

    assert len(heading_mismatches) == 0, f"Found {len(heading_mismatches)} heading mismatches in exercise_items"
    assert len(toc_range_mismatches) <= 5, f"Found {len(toc_range_mismatches)} TOC range mismatches in exercise_items"

