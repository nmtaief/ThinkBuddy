"""Seed authoritative textbook exercises for Class 8 Math Chapter 3 and 4 directly from printed NCTB textbook."""

import asyncio
import uuid
from sqlalchemy import text
from core.common.database import AsyncSessionLocal

BOOK_CLASS8_MATH_ID = uuid.UUID("6fa85f64-5717-4562-b3fc-2c963f66afa4")
CH3_ID = uuid.UUID("8a1b0003-5717-4562-b3fc-2c963f660003")
CH4_ID = uuid.UUID("8a1b0004-5717-4562-b3fc-2c963f660004")

EXERCISES = [
    # --- Chapter 4: অনুশীলনী ৪.১ ---
    {
        "book_id": BOOK_CLASS8_MATH_ID,
        "chapter_id": CH4_ID,
        "exercise_label": "অনুশীলনী ৪.১",
        "question_no": 4,
        "subpart": None,
        "question_text": "a = 4, b = 6 এবং c = 3 হলে 4a²b² – 16ab²c + 16b²c² এর মান নির্ণয় করো।",
        "printed_page": 54,
        "pdf_page_index": 58,
        "has_figure": False,
        "item_type": "short",
        "ocr_confidence": 1.0,
        "status": "teacher_approved",
        "source": "NCTB 2024 Class 8 Math page 54",
    },
    {
        "book_id": BOOK_CLASS8_MATH_ID,
        "chapter_id": CH4_ID,
        "exercise_label": "অনুশীলনী ৪.১",
        "question_no": 5,
        "subpart": None,
        "question_text": "x – 1/x = 3 হলে, x² + 1/x² এর মান নির্ণয় করো।",
        "printed_page": 54,
        "pdf_page_index": 58,
        "has_figure": False,
        "item_type": "short",
        "ocr_confidence": 1.0,
        "status": "teacher_approved",
        "source": "NCTB 2024 Class 8 Math page 54",
    },
    {
        "book_id": BOOK_CLASS8_MATH_ID,
        "chapter_id": CH4_ID,
        "exercise_label": "অনুশীলনী ৪.১",
        "question_no": 6,
        "subpart": None,
        "question_text": "a + 1/a = 4 হলে, a⁴ + 1/a⁴ এর মান কত?",
        "printed_page": 54,
        "pdf_page_index": 58,
        "has_figure": False,
        "item_type": "short",
        "ocr_confidence": 1.0,
        "status": "teacher_approved",
        "source": "NCTB 2024 Class 8 Math page 54",
    },
    {
        "book_id": BOOK_CLASS8_MATH_ID,
        "chapter_id": CH4_ID,
        "exercise_label": "অনুশীলনী ৪.১",
        "question_no": 7,
        "subpart": None,
        "question_text": "m = 6, n = 7 হলে, 16(m² + n²)² + 56(m² + n²)(3m² – 2n²) + 49(3m² – 2n²)² এর মান নির্ণয় করো।",
        "printed_page": 54,
        "pdf_page_index": 58,
        "has_figure": False,
        "item_type": "short",
        "ocr_confidence": 1.0,
        "status": "teacher_approved",
        "source": "NCTB 2024 Class 8 Math page 54",
    },
    {
        "book_id": BOOK_CLASS8_MATH_ID,
        "chapter_id": CH4_ID,
        "exercise_label": "অনুশীলনী ৪.১",
        "question_no": 8,
        "subpart": None,
        "question_text": "a – 1/a = m হলে, দেখাও যে, a⁴ + 1/a⁴ = m⁴ + 4m² + 2",
        "printed_page": 54,
        "pdf_page_index": 58,
        "has_figure": False,
        "item_type": "proof",
        "ocr_confidence": 1.0,
        "status": "teacher_approved",
        "source": "NCTB 2024 Class 8 Math page 54",
    },
    {
        "book_id": BOOK_CLASS8_MATH_ID,
        "chapter_id": CH4_ID,
        "exercise_label": "অনুশীলনী ৪.১",
        "question_no": 9,
        "subpart": None,
        "question_text": "x – 1/x = 4 হলে, প্রমাণ করো যে, x² + 1/x² = 18",
        "printed_page": 54,
        "pdf_page_index": 58,
        "has_figure": False,
        "item_type": "proof",
        "ocr_confidence": 1.0,
        "status": "teacher_approved",
        "source": "NCTB 2024 Class 8 Math page 54",
    },
    {
        "book_id": BOOK_CLASS8_MATH_ID,
        "chapter_id": CH4_ID,
        "exercise_label": "অনুশীলনী ৪.১",
        "question_no": 10,
        "subpart": None,
        "question_text": "m + 1/m = 2 হলে, প্রমাণ করো যে, m⁴ + 1/m⁴ = 2",
        "printed_page": 54,
        "pdf_page_index": 58,
        "has_figure": False,
        "item_type": "proof",
        "ocr_confidence": 1.0,
        "status": "teacher_approved",
        "source": "NCTB 2024 Class 8 Math page 54",
    },
    {
        "book_id": BOOK_CLASS8_MATH_ID,
        "chapter_id": CH4_ID,
        "exercise_label": "অনুশীলনী ৪.১",
        "question_no": 11,
        "subpart": None,
        "question_text": "x + y = 12 এবং xy = 27 হলে, (x – y)² ও x² + y² এর মান নির্ণয় করো।",
        "printed_page": 54,
        "pdf_page_index": 58,
        "has_figure": False,
        "item_type": "short",
        "ocr_confidence": 1.0,
        "status": "teacher_approved",
        "source": "NCTB 2024 Class 8 Math page 54",
    },
    {
        "book_id": BOOK_CLASS8_MATH_ID,
        "chapter_id": CH4_ID,
        "exercise_label": "অনুশীলনী ৪.১",
        "question_no": 12,
        "subpart": None,
        "question_text": "a + b = 13 এবং a – b = 3 হলে, 2a² + 2b² ও ab এর মান নির্ণয় করো।",
        "printed_page": 54,
        "pdf_page_index": 58,
        "has_figure": False,
        "item_type": "short",
        "ocr_confidence": 1.0,
        "status": "teacher_approved",
        "source": "NCTB 2024 Class 8 Math page 54",
    },

    # --- Chapter 3: অনুশীলনী ৩ / নমুনা প্রশ্ন ---
    {
        "book_id": BOOK_CLASS8_MATH_ID,
        "chapter_id": CH3_ID,
        "exercise_label": "অনুশীলনী ৩",
        "question_no": 4,
        "subpart": None,
        "question_text": "একটি আয়তাকার বাগানের ক্ষেত্রফল ৪০০ বর্গমিটার এবং প্রস্থ ১৬ মিটার। বাগানের পরিসীমা কত মিটার?\nক) ১৬\nখ) ২৫\nগ) ৪১\nঘ) ৮২",
        "printed_page": 45,
        "pdf_page_index": 50,
        "has_figure": False,
        "item_type": "mcq",
        "ocr_confidence": 1.0,
        "status": "teacher_approved",
        "source": "NCTB 2024 Class 8 Math page 45",
        "answer_key": "ঘ) ৮২ মিটার (দৈর্ঘ্য = ৪০০/১৬ = ২৫ মি.। পরিসীমা = ২ × (২৫ + ১৬) = ৮২ মি.)",
    },
    {
        "book_id": BOOK_CLASS8_MATH_ID,
        "chapter_id": CH3_ID,
        "exercise_label": "অনুশীলনী ৩",
        "question_no": 5,
        "subpart": None,
        "question_text": "একটি আয়তাকার বাগানের ক্ষেত্রফল ৪০০ বর্গমিটার এবং প্রস্থ ১৬ মিটার। বাগানের কর্ণ কত মিটার?\nক) ২৯.৬৮\nখ) ২৯.৮৬\nগ) ৩২.৬৮\nঘ) ৪১",
        "printed_page": 45,
        "pdf_page_index": 50,
        "has_figure": False,
        "item_type": "mcq",
        "ocr_confidence": 1.0,
        "status": "teacher_approved",
        "source": "NCTB 2024 Class 8 Math page 45",
        "answer_key": "ক) ২৯.৬৮ মিটার (কর্ণ = √(২৫² + ১৬²) = √(৬২৫ + ২৫৬) = √৮৮১ ≈ ২৯.৬৮ মিটার)",
    },
    {
        "book_id": BOOK_CLASS8_MATH_ID,
        "chapter_id": CH3_ID,
        "exercise_label": "অনুশীলনী ৩",
        "question_no": 7,
        "subpart": None,
        "question_text": "একটি আয়তাকার ক্ষেত্রের দৈর্ঘ্য ৪৮ মিটার এবং প্রস্থ ৩২ মিটার ৮০ সে. মি.। ক্ষেত্রটির বাইরে চারদিকে ৩ মিটার বিস্তৃত একটি রাস্তা আছে। রাস্তাটির ক্ষেত্রফল কত?",
        "printed_page": 44,
        "pdf_page_index": 49,
        "has_figure": False,
        "item_type": "short",
        "ocr_confidence": 1.0,
        "status": "teacher_approved",
        "source": "NCTB 2024 Class 8 Math page 44",
    },
    {
        "book_id": BOOK_CLASS8_MATH_ID,
        "chapter_id": CH3_ID,
        "exercise_label": "অনুশীলনী ৩",
        "question_no": 8,
        "subpart": None,
        "question_text": "একটি বর্গাকার ক্ষেত্রের এক বাহুর দৈর্ঘ্য ৩০০ মিটার এবং বাইরে চারদিকে ৪ মিটার প্রস্থ একটি রাস্তা আছে। রাস্তাটির ক্ষেত্রফল কত?",
        "printed_page": 44,
        "pdf_page_index": 49,
        "has_figure": False,
        "item_type": "short",
        "ocr_confidence": 1.0,
        "status": "teacher_approved",
        "source": "NCTB 2024 Class 8 Math page 44",
    },
    {
        "book_id": BOOK_CLASS8_MATH_ID,
        "chapter_id": CH3_ID,
        "exercise_label": "অনুশীলনী ৩",
        "question_no": 9,
        "subpart": None,
        "question_text": "একটি ত্রিভুজাকৃতি জমির ক্ষেত্রফল ২৬৪ বর্গমিটার। এর ভূমি ২২ মিটার হলে, উচ্চতা নির্ণয় করো।",
        "printed_page": 44,
        "pdf_page_index": 49,
        "has_figure": False,
        "item_type": "short",
        "ocr_confidence": 1.0,
        "status": "teacher_approved",
        "source": "NCTB 2024 Class 8 Math page 44",
    },
    {
        "book_id": BOOK_CLASS8_MATH_ID,
        "chapter_id": CH3_ID,
        "exercise_label": "অনুশীলনী ৩",
        "question_no": 10,
        "subpart": None,
        "question_text": "একটি চৌবাচ্চায় ১৯২০০ লিটার পানি ধরে। এর গভীরতা ২.৫৬ মিটার এবং প্রস্থ ২.৫ মিটার হলে, দৈর্ঘ্য কত?",
        "printed_page": 44,
        "pdf_page_index": 49,
        "has_figure": False,
        "item_type": "short",
        "ocr_confidence": 1.0,
        "status": "teacher_approved",
        "source": "NCTB 2024 Class 8 Math page 44",
    },
]

async def seed():
    async with AsyncSessionLocal() as session:
        for ex in EXERCISES:
            # Delete if exists
            await session.execute(
                text("""
                    DELETE FROM exercise_items 
                    WHERE chapter_id = :chapter_id 
                      AND exercise_label = :exercise_label 
                      AND question_no = :question_no 
                      AND subpart IS NOT DISTINCT FROM :subpart
                """),
                {
                    "chapter_id": ex["chapter_id"],
                    "exercise_label": ex["exercise_label"],
                    "question_no": ex["question_no"],
                    "subpart": ex["subpart"],
                }
            )
            # Insert authoritative record
            await session.execute(
                text("""
                    INSERT INTO exercise_items (
                        id, book_id, chapter_id, exercise_label, question_no, subpart,
                        question_text, printed_page, pdf_page_index, has_figure,
                        item_type, ocr_confidence, status, source, answer_key, created_at, updated_at
                    ) VALUES (
                        :id, :book_id, :chapter_id, :exercise_label, :question_no, :subpart,
                        :question_text, :printed_page, :pdf_page_index, :has_figure,
                        :item_type, :ocr_confidence, :status, :source, :answer_key, NOW(), NOW()
                    )
                """),
                {
                    "id": uuid.uuid4(),
                    "book_id": ex["book_id"],
                    "chapter_id": ex["chapter_id"],
                    "exercise_label": ex["exercise_label"],
                    "question_no": ex["question_no"],
                    "subpart": ex["subpart"],
                    "question_text": ex["question_text"],
                    "printed_page": ex["printed_page"],
                    "pdf_page_index": ex["pdf_page_index"],
                    "has_figure": ex["has_figure"],
                    "item_type": ex["item_type"],
                    "ocr_confidence": ex["ocr_confidence"],
                    "status": ex["status"],
                    "source": ex["source"],
                    "answer_key": ex.get("answer_key"),
                }
            )
        
        # Clean up chunk 54 text OCR garble
        await session.execute(
            text("""
                UPDATE chunks 
                SET text = REPLACE(REPLACE(text, :find1, :rep1), :find2, :rep2)
                WHERE book_id = :book_id AND printed_page = 54
            """),
            {
                "find1": "১০ I11 +",
                "rep1": "১০ । m + 1/m = 2 হলে, প্রমাণ করো যে, m⁴ + 1/m⁴ = 2\n১০ I11 +",
                "find2": "i1' +",
                "rep2": "m⁴ + 1/m⁴",
                "book_id": BOOK_CLASS8_MATH_ID
            }
        )

        await session.commit()
        print(f"Successfully seeded {len(EXERCISES)} authoritative exercises for Chapters 3 and 4!")

if __name__ == "__main__":
    asyncio.run(seed())
