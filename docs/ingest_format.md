# ThinkBuddy – Knowledge Factory Ingest Manifest Format (v1)

This document defines the import manifest specification for ingesting validated NCTB textbooks and curriculum content into ThinkBuddy's PostgreSQL + pgvector storage.

---

## 1. File Specification

- **File Format:** JSON Lines (`.jsonl`), UTF-8 encoded.
- **Record Types:** The manifest begins with a header record defining the book and chapter tree, followed by individual chunk records.

### Record 1: Book & Curriculum Manifest (`type: "book"`)

```json
{
  "type": "book",
  "book": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "title": "গণিত (সপ্তম শ্রেণি)",
    "class_level": 7,
    "subject": "math",
    "medium": "bn",
    "edition": "2024",
    "source_uri": "s3://thinkbuddy-textbooks/class7/math_bn_2024.pdf"
  },
  "chapters": [
    {
      "id": "7ca85f64-5717-4562-b3fc-2c963f66af01",
      "number": 1,
      "title": "মূলদ ও অমূলদ সংখ্যা",
      "printed_page_start": 1,
      "printed_page_end": 18,
      "order_index": 1
    },
    {
      "id": "7ca85f64-5717-4562-b3fc-2c963f66af02",
      "number": 2,
      "title": "বীজগণিতীয় রাশি",
      "printed_page_start": 19,
      "printed_page_end": 35,
      "order_index": 2
    }
  ],
  "concepts": [
    {
      "id": "8ca85f64-5717-4562-b3fc-2c963f66ac01",
      "chapter_id": "7ca85f64-5717-4562-b3fc-2c963f66af01",
      "title": "বর্গ ও বর্গমূলের ধারণা",
      "kind": "concept"
    }
  ]
}
```

### Subsequent Records: Chunk Records (`type: "chunk"`)

```json
{
  "type": "chunk",
  "id": "9ca85f64-5717-4562-b3fc-2c963f66ad01",
  "book_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "chapter_id": "7ca85f64-5717-4562-b3fc-2c963f66af01",
  "concept_id": "8ca85f64-5717-4562-b3fc-2c963f66ac01",
  "chunk_index": 1,
  "text": "যে সংখ্যাকে সেই সংখ্যা দ্বারা গুণ করলে যে গুণফল পাওয়া যায়, তা ঐ সংখ্যার বর্গ এবং সংখ্যাটি গুণফলের বর্গমূল। যেমন: ৩ × ৩ = ৯, সুতরাং ৩ এর বর্গ ৯ এবং ৯ এর বর্গমূল ৩।",
  "text_original": "যে সংখ্যাকে সেই সংখ্যা দ্বারা গুণ করলে...",
  "language": "bn",
  "printed_page": 2,
  "pdf_page_index": 4,
  "ocr_quality": 0.98,
  "validation_flags": ["clean"]
}
```

---

## 2. Field Rules & Constraints

1. **Printed Page vs PDF Page Index:**
   - `printed_page`: The physical page number printed in the NCTB textbook (e.g. Page 2). This is the **only** page number shown in user citations and student-facing UI.
   - `pdf_page_index`: The 0-based or 1-based page index inside the digital PDF document (e.g. Index 4, accounting for preface/cover pages).
   - **Constraint:** These must NEVER be mixed or unified into a single field.

2. **Validation Flags & Retrievability:**
   - A chunk is considered valid and indexed as `retrievable = true` if:
     - `ocr_quality >= 0.70`
     - `validation_flags` contains `"clean"` or does not contain blocking rejection flags (`"corrupted_ocr"`, `"truncated"`, `"profanity"`, `"unreadable"`).
   - Chunks that fail validation are ingested with `retrievable = false` and their rejection reasons logged in `validation_flags`. They are excluded from hybrid retrieval.

3. **Idempotency & Resumability:**
   - The importer uses `(book_id, chunk_index)` or chunk UUID for upsert operations.
   - If an import process terminates unexpectedly, re-running the importer resumes at the unimported chunks without creating duplicate records or corrupting the vector index.

---

## 3. NCTB Curriculum Content Licensing (Open Item)

> [!WARNING]
> **Open Legal & Regulatory Item: NCTB Curriculum Content Licensing**
>
> 1. **Copyright Ownership:** All official national curriculum textbooks, diagrams, exercises, tables, and syllabi are the intellectual property of the **National Curriculum and Textbook Board (NCTB)** under the Ministry of Education, Government of the People's Republic of Bangladesh, governed by the Bangladesh Copyright Act, 2000 (as amended in 2023).
> 2. **Educational Research vs. Commercial Rollout:** Ingestion of textbook content, vector chunking, and student retrieval during private alpha/beta testing and educational research operate under non-commercial fair use principles. However, public deployment, app store publication, and any commercial subscription monetization require formal written authorization, licensing, or public-private partnership (PPP) accreditation from the NCTB / Ministry of Education.
> 3. **Action Required Prior to Public Launch:**
>    - Execute formal copyright clearance or partnership MOU with NCTB for digital textbook distribution and AI tutoring adaptations.
>    - Maintain a digital registry of licensed editions (e.g. 2024–2025 curriculum editions) and establish content update / takedown procedures if syllabi or textbook revisions are mandated by NCTB.
>    - Ensure strict adherence to NCTB curriculum guidelines without unauthorized modifications to national educational standards.
