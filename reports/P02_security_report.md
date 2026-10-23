# ThinkBuddy Security & Verification Report – Milestone P02 (Curriculum & Ingestion)

**Date:** 2026-10-23  
**Auditor / Lead Engineer:** ThinkBuddy Lead Engineer (Antigravity)  
**Milestone:** P02 – Curriculum & Content Ingestion (Knowledge Factory → Database)  
**Branch:** `feat/P02_curriculum_textbooks_rag`  

---

## 1. Executive Summary

Milestone P02 builds and hardens the curriculum and content ingestion pipeline, loading validated Knowledge Factory output into PostgreSQL with pgvector, and exposing curriculum endpoints and hybrid retrieval for RAG.

All deliverables and constraints defined in `thinkbuddy-docs/prompts/P02_curriculum_ingest_rag_index.md` were implemented and verified:
1. **Import Manifest Format:** Defined and documented in `/docs/ingest_format.md` (JSONL with book metadata, chapter tree, concepts, and chunk records).
2. **Idempotent & Resumable Importer:** `rag/ingest.py` and `scripts/import_curriculum.py` verify that re-running does not duplicate chunks, and interrupting an import mid-book resumes without duplication.
3. **Multilingual Embedding Provider:** `EmbeddingProvider` interface with unit-normalized semantic embeddings and hosted provider supporting batching, exponential backoff retries, and token cost logging.
4. **PgVectorStore Hybrid Retrieval:** Combined dense vector cosine similarity (`<=>`) with full-text search (`tsvector`) and trigram fuzzy matching (`pg_trgm`), fused via Reciprocal Rank Fusion (RRF).
5. **Quality Gating:** Chunks failing validation (`ocr_quality < 0.70` or containing rejection flags like `truncated`, `corrupted_ocr`) are persisted with `retrievable = false` and excluded from retrieval.
6. **Strict Separation of Printed Page and PDF Index (Rule 8):** Separate columns in PostgreSQL (`printed_page` vs `pdf_page_index`). Only the printed page is returned in citations.
7. **Curriculum Read APIs:** `/v1/books`, `/v1/books/{id}`, `/v1/books/{id}/chapters`, and `/v1/chapters/{id}` exposed on Gateway and Core, protected by JWT authentication and documented in `docs/04_API_CONTRACT.md` and OpenAPI schema.
8. **Retrieval Evaluation Harness:** `scripts/eval_retrieval.py` testing bilingual queries against ground truth, enforcing an 80% CI threshold gate.

---

## 2. Security & Verification Checks Summary

| Category | Tool / Method | Target / Scope | Status | Result / Notes |
|---|---|---|---|---|
| **Code Style & Linting** | `ruff check .` & `ruff format` | Entire workspace (82 files) | **PASS** | 0 errors, strict PEP-8 & line-length compliance |
| **Static Type Safety** | `mypy` 1.15.0 | `core`, `gateway`, `workers`, `rag`, `scripts` | **PASS** | Strict mode passed across 66 source files (0 type errors) |
| **AST Security Analysis** | `bandit` 1.8.3 | `core`, `gateway`, `workers`, `rag` (`-ll`) | **PASS** | 3,845 lines scanned: 0 Medium/High issues identified |
| **Dependency Auditing** | `pip-audit` 2.8.0 | Project dependencies (`pyproject.toml`) | **PASS** | 0 vulnerabilities found |
| **Secrets & Credentials** | `gitleaks` (`zricethezav/gitleaks:latest`) | Full Git commit history | **PASS** | 5 commits scanned: 0 leaks found |
| **Database Migrations** | Alembic `0003_p02_curriculum_rag` | Live Compose PostgreSQL (`127.0.0.1:5432`) | **PASS** | Successfully upgraded, tested full downgrade reversibility |
| **Automated Test Suite** | `pytest` 9.1.0 | `tests/` (38 test cases) | **PASS** | 38 passed in 2.06s (100% pass rate) against live Compose services |
| **Retrieval Eval Harness** | `scripts/eval_retrieval.py` | Bilingual Bangla & English dataset | **PASS** | Hit@5: 100.0%, PageAcc@5: 100.0% (Threshold: >= 80.0%) |

---

## 3. Retrieval Evaluation Report

```text
================================================================================
THINKBUDDY RETRIEVAL EVALUATION HARNESS
Dataset: retrieval_eval_dataset.json | Total Queries: 6 | Top-K: 5
================================================================================
  [TOP5]  [BN] বর্গ ও বর্গমূলের ধারণা কী এবং কীভাব... -> Exp(Ch:1, Pg:2)  | Top-1(Ch:[1], Pg:[12])
  [EXACT] [BN] মৌলিক উৎপাদকের সাহায্যে বর্গমূল নির... -> Exp(Ch:1, Pg:5)  | Top-1(Ch:[1], Pg:[5])
  [EXACT] [BN] সাধারণ ভগ্নাংশ এবং দশমিক ভগ্নাংশের ... -> Exp(Ch:1, Pg:12) | Top-1(Ch:[1], Pg:[12])
  [TOP5]  [BN] বীজগণিতীয় রাশির গুণের সময় চিহ্নের ... -> Exp(Ch:2, Pg:20) | Top-1(Ch:[2], Pg:[24])
  [EXACT] [BN] বর্গের সূত্রাবলি (a + b)^2 এবং (a -... -> Exp(Ch:2, Pg:24) | Top-1(Ch:[2], Pg:[24])
  [EXACT] [EN] How do you solve linear equations b... -> Exp(Ch:2, Pg:28) | Top-1(Ch:[2], Pg:[28])
--------------------------------------------------------------------------------
SUMMARY RESULTS:
  * Hit-Rate@1 (Chapter):     100.0% (6/6)
  * Hit-Rate@3 (Chapter):     100.0% (6/6)
  * Hit-Rate@5 (Chapter):     100.0% (6/6)
  * Page Acc@1:               66.7% (4/6)
  * Page Acc@5:               100.0% (6/6)

PER-LANGUAGE BREAKDOWN:
  * [BN]: Hit@5 = 100.0% (5/5) | PageAcc@5 = 100.0% (5/5)
  * [EN]: Hit@5 = 100.0% (1/1) | PageAcc@5 = 100.0% (1/1)
================================================================================
RETRIEVAL QUALITY GATE PASSED (Thresholds: Hit@5 >= 80.0%, PageAcc@5 >= 80.0%)
================================================================================
```

---

## 4. Key Architectural Guarantees

1. **Config-Driven Embedding Dimension:** Vector dimension in `chunks.embedding` is derived dynamically from `settings.EMBEDDING_DIMENSION` (configured in `migrations/versions/0003_p02_curriculum_rag.py`). Changing embedding models without downtime is supported by adding an embedding column version and filtering on `embedding_model`.
2. **Idempotent Resume:** Ingestion checks existing `(book_id, chunk_index)` records before inserting, enabling graceful resumes upon worker restart without re-embedding.
3. **Grounding & Citations:** Every retrieved chunk returns `book_title`, `chapter_number`, `chapter_title`, and `printed_page`, giving the chat orchestrator precise citation metadata.
