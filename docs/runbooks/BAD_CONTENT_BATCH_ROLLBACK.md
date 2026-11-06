# Runbook: Bad Content Batch Rollback

## 1. Trigger & Scope
- **Severity:** P2 (Content Inaccuracy / Defective Textbook Ingest)
- **Symptoms:**
  - Chat citations link to incorrect printed pages or corrupted text chunks.
  - OCR errors or misaligned chapter boundaries reported by parents/students.
  - Question bank items tagged to wrong topics.

---

## 2. Invariants & Rules
- **Rule 7:** Every answer from RAG must carry citations (book, chapter, printed page).
- **Rule 8:** Printed page number ≠ PDF page index.
- **Data Integrity Invariant:** Never delete textbook chunks referenced by active revision items or student attempt histories. Instead, use soft-deprecation (`is_active = False`) or batch versioning.

---

## 3. Rollback Procedure

### Step 1: Identify Defective Ingestion Batch ID
Query the `chunks` or `questions` table for the batch timestamp or ingestion metadata:
```sql
SELECT DISTINCT book_id, chapter_id, count(*), min(created_at), max(created_at)
FROM chunks
WHERE created_at > '2026-11-01'
GROUP BY book_id, chapter_id;
```

### Step 2: Soft-Deprecate Defective Chunks
Mark defective chunks inactive so the hybrid RAG retrieval pipeline ignores them immediately without breaking foreign key constraints on past `chat_citations`:
```sql
UPDATE chunks
SET is_active = false
WHERE book_id = '<defective_book_uuid>'
  AND created_at BETWEEN '<batch_start>' AND '<batch_end>';
```

Flush RAG query cache in Redis:
```bash
redis-cli -a $REDIS_PASSWORD KEYS "rag:cache:*" | xargs redis-cli -a $REDIS_PASSWORD DEL
```

### Step 3: Deprecate Defective Question Bank Batches
If questions generated from the defective batch have not yet been attempted:
```sql
-- For unattempted questions
DELETE FROM questions
WHERE book_id = '<defective_book_uuid>'
  AND id NOT IN (SELECT question_id FROM attempt_items);

-- For attempted questions (preserve historical audit logs)
UPDATE questions
SET is_active = false
WHERE book_id = '<defective_book_uuid>';
```

### Step 4: Re-Ingest Validated Content
Run curriculum re-ingestion with validated PDF and OCR corrections:
```bash
python scripts/import_curriculum.py --book-id <book_uuid> --file <corrected_nctb_book.json>
```

Verify retrieval accuracy:
```bash
python scripts/eval_retrieval.py
```
Confirm retrieval confidence > 0.85 and printed page citations match physical textbooks.

