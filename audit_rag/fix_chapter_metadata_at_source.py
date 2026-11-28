"""Authoritative Chapter Metadata Fix at Source (Fix Pass 8, Section 1.2).

Derives true chapter titles, numbers, and page ranges from NCTB textbook Table of Contents (সূচিপত্র).
Updates chapters table and re-maps chapter_id in chunks, structural_chunks, and exercise_items.
"""

import sys
sys.path.insert(0, ".")
import uuid
import asyncio
import asyncpg
import re

DB_URL = "postgresql://thinkbuddy:thinkbuddy_dev_password@127.0.0.1:5432/thinkbuddy"

# Authoritative NCTB Curriculum Chapters and TOC Page Ranges
AUTHORITATIVE_TOC = {
    (6, "math"): [
        {"num": 1, "title": "স্বাভাবিক সংখ্যা ও ভগ্নাংশ", "start": 1, "end": 37},
        {"num": 2, "title": "অনুপাত ও শতকরা", "start": 38, "end": 58},
        {"num": 3, "title": "পূর্ণসংখ্যা", "start": 59, "end": 75},
        {"num": 4, "title": "বীজগণিতীয় রাশি", "start": 76, "end": 94},
        {"num": 5, "title": "সরল সমীকরণ", "start": 95, "end": 105},
        {"num": 6, "title": "জ্যামিতির মৌলিক ধারণা", "start": 106, "end": 123},
        {"num": 7, "title": "ব্যবহারিক জ্যামিতি", "start": 124, "end": 136},
        {"num": 8, "title": "তথ্য ও উপাত্ত", "start": 137, "end": 160},
    ],
    (7, "math"): [
        {"num": 1, "title": "মূলদ ও অমূলদ সংখ্যা", "start": 1, "end": 17},
        {"num": 2, "title": "সমানুপাত ও লাভ-ক্ষতি", "start": 18, "end": 37},
        {"num": 3, "title": "পরিমাপ", "start": 38, "end": 49},
        {"num": 4, "title": "বীজগণিতীয় রাশির গুণ ও ভাগ", "start": 50, "end": 68},
        {"num": 5, "title": "বীজগণিতীয় সূত্রাবলি ও প্রয়োগ", "start": 69, "end": 88},
        {"num": 6, "title": "বীজগণিতীয় ভগ্নাংশ", "start": 89, "end": 101},
        {"num": 7, "title": "সরল সমীকরণ", "start": 102, "end": 118},
        {"num": 8, "title": "সমান্তরাল সরলরেখা", "start": 119, "end": 126},
        {"num": 9, "title": "ত্রিভুজ", "start": 127, "end": 144},
        {"num": 10, "title": "সর্বসমতা ও সদৃশতা", "start": 145, "end": 161},
        {"num": 11, "title": "তথ্য ও উপাত্ত", "start": 162, "end": 180},
    ],
    (7, "science"): [
        {"num": 1, "title": "নিম্নশ্রেণির জীব", "start": 1, "end": 9},
        {"num": 2, "title": "উদ্ভিদ ও প্রাণীর কোষীয় সংগঠন", "start": 10, "end": 21},
        {"num": 3, "title": "উদ্ভিদের বাহ্যিক বৈশিষ্ট্য", "start": 22, "end": 31},
        {"num": 4, "title": "শ্বসন", "start": 32, "end": 40},
        {"num": 5, "title": "পরিপাকতন্ত্র এবং রক্ত সংবহনতন্ত্র", "start": 41, "end": 54},
        {"num": 6, "title": "পদার্থের গঠন", "start": 55, "end": 65},
        {"num": 7, "title": "শক্তির ব্যবহার", "start": 66, "end": 79},
        {"num": 8, "title": " শব্দের কথা", "start": 80, "end": 89},
        {"num": 9, "title": "তাপ ও তাপমাত্রা", "start": 90, "end": 100},
        {"num": 10, "title": "বিদ্যুৎ ও চুম্বকের ঘটনা", "start": 101, "end": 111},
        {"num": 11, "title": "পারিপার্শ্বিক পরিবর্তন ও বিভিন্ন ঘটনা", "start": 112, "end": 122},
        {"num": 12, "title": "সৌরজগৎ ও আমাদের পৃথিবী", "start": 123, "end": 134},
        {"num": 13, "title": "প্রাকৃতিক পরিবেশ এবং দূষণ", "start": 135, "end": 144},
        {"num": 14, "title": "জলবায়ু পরিবর্তন", "start": 145, "end": 160},
    ],
    (8, "math"): [
        {"num": 1, "title": "প্যাটার্ন", "start": 1, "end": 11},
        {"num": 2, "title": "মুনাফা", "start": 12, "end": 27},
        {"num": 3, "title": "পরিমাপ", "start": 28, "end": 46},
        {"num": 4, "title": "বীজগণিতীয় সূত্রাবলি ও প্রয়োগ", "start": 47, "end": 74},
        {"num": 5, "title": "বীজগণিতীয় ভগ্নাংশ", "start": 75, "end": 96},
        {"num": 6, "title": "সরল সহসমীকরণ", "start": 97, "end": 114},
        {"num": 7, "title": "সেট", "start": 115, "end": 124},
        {"num": 8, "title": "চতুর্ভুজ", "start": 125, "end": 140},
        {"num": 9, "title": "পিথাগোরাসের উপপাদ্য", "start": 141, "end": 147},
        {"num": 10, "title": "বৃত্ত", "start": 148, "end": 158},
        {"num": 11, "title": "তথ্য ও উপাত্ত", "start": 159, "end": 180},
    ],
    (8, "science"): [
        {"num": 1, "title": "প্রাণিজগতের শ্রেণিবিন্যাস", "start": 1, "end": 12},
        {"num": 2, "title": "জীবের বৃদ্ধি ও বংশগতি", "start": 13, "end": 23},
        {"num": 3, "title": "ব্যাপন, অভিস্রবণ ও প্রস্বেদন", "start": 24, "end": 33},
        {"num": 4, "title": "উদ্ভিদে বংশবৃদ্ধি", "start": 34, "end": 44},
        {"num": 5, "title": "সমন্বয় ও নিঃসরণ", "start": 45, "end": 54},
        {"num": 6, "title": "পরমাণুর গঠন", "start": 55, "end": 64},
        {"num": 7, "title": "পৃথিবী ও মহাকর্ষ", "start": 65, "end": 74},
        {"num": 8, "title": "রাসায়নিক বিক্রিয়া", "start": 75, "end": 88},
        {"num": 9, "title": "বর্তনী ও চলবিদ্যুৎ", "start": 89, "end": 97},
        {"num": 10, "title": "অম্ল, ক্ষারক ও লবণ", "start": 98, "end": 107},
        {"num": 11, "title": "আলো", "start": 108, "end": 118},
        {"num": 12, "title": "মহাকাশ ও উপগ্রহ", "start": 119, "end": 128},
        {"num": 13, "title": "খাদ্য ও পুষ্টি", "start": 129, "end": 146},
        {"num": 14, "title": "পরিবেশ এবং বাস্তুতন্ত্র", "start": 147, "end": 170},
    ],
    (8, "bgs"): [
        {"num": 1, "title": "ঔপনিবেশিক যুগ ও বাংলার স্বাধীনতা সংগ্রাম", "start": 1, "end": 12},
        {"num": 2, "title": "ঔপনিবেশিক যুগের প্রত্নতাত্ত্বিক ঐতিহ্য", "start": 13, "end": 18},
        {"num": 3, "title": "বাংলাদেশের মুক্তিযুদ্ধ ও গণতান্ত্রিক সংগ্রাম", "start": 19, "end": 38},
        {"num": 4, "title": "বাংলাদেশের অর্থনীতি", "start": 39, "end": 48},
        {"num": 5, "title": "বাংলাদেশ রাষ্ট্র ও সরকার ব্যবস্থা", "start": 49, "end": 62},
        {"num": 6, "title": "বাংলাদেশের বিভিন্ন ক্ষুদ্র নৃ-গোষ্ঠী", "start": 63, "end": 74},
        {"num": 7, "title": "বাংলাদেশের দুর্যোগ", "start": 75, "end": 88},
        {"num": 8, "title": "বাংলাদেশের সামাজিক সমস্যা", "start": 89, "end": 98},
        {"num": 9, "title": "বাংলাদেশের জনসংখ্যা ও উন্নয়ন", "start": 99, "end": 110},
        {"num": 10, "title": "সামাজিকীকরণ ও উন্নয়ন", "start": 111, "end": 122},
        {"num": 11, "title": "বাংলাদেশের প্রাকৃতিক সম্পদ", "start": 123, "end": 134},
        {"num": 12, "title": "বাংলাদেশ ও বিভিন্ন আন্তর্জাতিক সহযোগী সংস্থা", "start": 135, "end": 146},
        {"num": 13, "title": "টেকসই উন্নয়ন অভীষ্ট (SDG)", "start": 147, "end": 170},
    ],
    (8, "ict"): [
        {"num": 1, "title": "তথ্য ও যোগাযোগ প্রযুক্তির গুরুত্ব", "start": 1, "end": 20},
        {"num": 2, "title": "কম্পিউটার নেটওয়ার্ক", "start": 21, "end": 42},
        {"num": 3, "title": "তথ্য ও যোগাযোগ প্রযুক্তির নিরাপদ ও নৈতিক ব্যবহার", "start": 43, "end": 62},
        {"num": 4, "title": "স্প্রেডশিটের ব্যবহার", "start": 63, "end": 80},
        {"num": 5, "title": "শিক্ষা ও দৈনন্দিন জীবনে ইন্টারনেটের ব্যবহার", "start": 81, "end": 100},
    ],
    (8, "islam"): [
        {"num": 1, "title": "আকাইদ", "start": 1, "end": 30},
        {"num": 2, "title": "ইবাদত", "start": 31, "end": 65},
        {"num": 3, "title": "কুরআন ও হাদিস শিক্ষা", "start": 66, "end": 105},
        {"num": 4, "title": "আখলাক", "start": 106, "end": 140},
        {"num": 5, "title": "আদর্শ জীবনচরিত", "start": 141, "end": 180},
    ],
    (9, "math"): [
        {"num": 1, "title": "বাস্তব সংখ্যা", "start": 1, "end": 20},
        {"num": 2, "title": "সেট ও ফাংশন", "start": 21, "end": 42},
        {"num": 3, "title": "বীজগাণিতিক রাশি", "start": 43, "end": 74},
        {"num": 4, "title": "সূচক ও লগারিদম", "start": 75, "end": 92},
        {"num": 5, "title": "এক চলকবিশিষ্ট সমীকরণ", "start": 93, "end": 110},
        {"num": 6, "title": "রেখা, কোণ ও ত্রিভুজ", "start": 111, "end": 135},
        {"num": 7, "title": "ব্যবহারিক জ্যামিতি", "start": 136, "end": 151},
        {"num": 8, "title": "বৃত্ত", "start": 152, "end": 173},
        {"num": 9, "title": "ত্রিকোণমিতিক অনুপাত", "start": 174, "end": 196},
        {"num": 10, "title": "দূরত্ব ও উচ্চতা", "start": 197, "end": 204},
        {"num": 11, "title": "বীজগাণিতিক অনুপাত ও সমানুপাত", "start": 205, "end": 223},
        {"num": 12, "title": "দুই চলকবিশিষ্ট সরল সহসমীকরণ", "start": 224, "end": 248},
        {"num": 13, "title": "সসীম ধারা", "start": 249, "end": 265},
        {"num": 14, "title": "অনুপাত, সদৃশতা ও প্রতিসমতা", "start": 266, "end": 284},
        {"num": 15, "title": "ক্ষেত্রফল সম্পর্কিত উপপাদ্য ও সম্পাদ্য", "start": 285, "end": 293},
        {"num": 16, "title": "পরিমিতি", "start": 294, "end": 325},
        {"num": 17, "title": "পরিসংখ্যান", "start": 326, "end": 360},
    ],
}

BN_NUMS = {'০': 0, '১': 1, '২': 2, '৩': 3, '৪': 4, '৫': 5, '৬': 6, '৭': 7, '৮': 8, '৯': 9}
def bn_to_int(s: str) -> int | None:
    if not s:
        return None
    val = ""
    for c in s.strip():
        if c in BN_NUMS:
            val += str(BN_NUMS[c])
        elif c.isdigit():
            val += c
    return int(val) if val else None

CH_WORDS = {
    'প্রথম': 1, 'দ্বিতীয়': 2, 'দ্বিতীয়': 2, 'তৃতীয়': 3, 'তৃতীয়': 3, 'চতুর্থ': 4,
    'পঞ্চম': 5, 'ষষ্ঠ': 6, 'সপ্তম': 7, 'অষ্টম': 8, 'নবম': 9, 'দশম': 10,
    'একাদশ': 11, 'দ্বাদশ': 12, 'ত্রয়োদশ': 13, 'ত্রয়োদশ': 13, 'চতুর্দশ': 14,
    'পঞ্চদশ': 15, 'ষোড়শ': 16, 'ষোড়শ': 16, 'সপ্তদশ': 17,
}

def extract_heading_chapter(text: str) -> int | None:
    if not text:
        return None
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    heading_text = ' '.join(lines[:3]) if lines else ''

    m = re.search(r'^\s*(?:অধ্যায়|অধ্যায়|Chapter)\s*[:\-]?\s*([০-৯\d]+)', heading_text, re.IGNORECASE)
    if m:
        return bn_to_int(m.group(1))

    earliest_pos = None
    earliest_num = None
    for word, num in CH_WORDS.items():
        for pattern in [f"{word} অধ্যায়", f"{word} অধ্যায়"]:
            pos = heading_text.find(pattern)
            if pos != -1:
                preceding = heading_text[max(0, pos - 15):pos]
                if any(w in preceding for w in ['আমরা', 'দেখাব', 'পড়েছি', 'যেমন', 'এবং']):
                    continue
                if earliest_pos is None or pos < earliest_pos:
                    earliest_pos = pos
                    earliest_num = num
    if earliest_num is not None:
        return earliest_num
    return None

async def run_fix():
    conn = await asyncpg.connect(DB_URL)
    print("=" * 80)
    print("RECONCILING CHAPTER METADATA AT SOURCE")
    print("=" * 80)

    # 1. Update / Insert Authoritative Chapters in `chapters` table
    for (cls, sub), ch_list in AUTHORITATIVE_TOC.items():
        book = await conn.fetchrow("SELECT id, title FROM books WHERE class_level = $1 AND subject = $2", cls, sub)
        if not book:
            continue
        book_id = book["id"]
        print(f"\nReconciling Chapters for Class {cls} {sub} ({book['title']}): {len(ch_list)} chapters")

        for ch_info in ch_list:
            c_num = ch_info["num"]
            c_title = ch_info["title"]
            c_start = ch_info["start"]
            c_end = ch_info["end"]

            existing_ch = await conn.fetchrow(
                "SELECT id FROM chapters WHERE book_id = $1 AND number = $2", book_id, c_num
            )
            if existing_ch:
                await conn.execute("""
                    UPDATE chapters
                    SET title = $1, printed_page_start = $2, printed_page_end = $3
                    WHERE id = $4
                """, c_title, c_start, c_end, existing_ch["id"])
            else:
                new_id = uuid.uuid4()
                await conn.execute("""
                    INSERT INTO chapters (id, book_id, number, title, printed_page_start, printed_page_end, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
                """, new_id, book_id, c_num, c_title, c_start, c_end)

    # 2. Build Fast Lookup: (book_id, printed_page) -> chapter_id
    ch_rows = await conn.fetch("SELECT id, book_id, number, printed_page_start, printed_page_end FROM chapters ORDER BY number")
    
    def resolve_ch_id(b_id, page, heading_ch_num=None):
        book_chs = [c for c in ch_rows if c["book_id"] == b_id]
        if heading_ch_num:
            match = next((c for c in book_chs if c["number"] == heading_ch_num), None)
            if match:
                return match["id"]
        # Match by TOC page range
        if page:
            match = next((c for c in book_chs if c["printed_page_start"] <= page <= c["printed_page_end"]), None)
            if match:
                return match["id"]
        return book_chs[0]["id"] if book_chs else None

    # 3. Remap `chunks` table
    print("\nRemapping `chunks` table chapter_id references...")
    chunks = await conn.fetch("SELECT id, book_id, chapter_id, printed_page, text FROM chunks")
    remapped_chunks = 0
    for c in chunks:
        h_num = extract_heading_chapter(c["text"])
        correct_ch_id = resolve_ch_id(c["book_id"], c["printed_page"], h_num)
        if correct_ch_id and correct_ch_id != c["chapter_id"]:
            await conn.execute("UPDATE chunks SET chapter_id = $1 WHERE id = $2", correct_ch_id, c["id"])
            remapped_chunks += 1
    print(f"  Fixed {remapped_chunks} drifted rows in `chunks` table.")

    # 4. Remap `structural_chunks` table
    print("Remapping `structural_chunks` table chapter_id references...")
    schunks = await conn.fetch("SELECT id, book_id, chapter_id, printed_page, raw_text FROM structural_chunks")
    remapped_sc = 0
    for sc in schunks:
        h_num = extract_heading_chapter(sc["raw_text"])
        correct_ch_id = resolve_ch_id(sc["book_id"], sc["printed_page"], h_num)
        if correct_ch_id and correct_ch_id != sc["chapter_id"]:
            await conn.execute("UPDATE structural_chunks SET chapter_id = $1 WHERE id = $2", correct_ch_id, sc["id"])
            remapped_sc += 1
    print(f"  Fixed {remapped_sc} drifted rows in `structural_chunks` table.")

    # 5. Remap `exercise_items` table
    print("Remapping `exercise_items` table chapter_id references...")
    exercises = await conn.fetch("SELECT id, book_id, chapter_id, printed_page, question_text FROM exercise_items")
    remapped_ex = 0
    for ex in exercises:
        h_num = extract_heading_chapter(ex["question_text"])
        correct_ch_id = resolve_ch_id(ex["book_id"], ex["printed_page"], h_num)
        if correct_ch_id and correct_ch_id != ex["chapter_id"]:
            await conn.execute("UPDATE exercise_items SET chapter_id = $1 WHERE id = $2", correct_ch_id, ex["id"])
            remapped_ex += 1
    print(f"  Fixed {remapped_ex} drifted rows in `exercise_items` table.")

    print("\n" + "=" * 80)
    print("SOURCE CHAPTER RECONCILIATION COMPLETE!")
    print("=" * 80)
    await conn.close()

if __name__ == "__main__":
    asyncio.run(run_fix())

