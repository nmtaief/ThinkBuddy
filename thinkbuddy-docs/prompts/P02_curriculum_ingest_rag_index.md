# P02 – Curriculum & Content Ingestion (Knowledge Factory → Database)

**Read first:** `AGENT_RULES.md`, `docs/01_ARCHITECTURE.md` (§3, §8), `docs/03_DATA_MODEL.md` (§2), the "Introduction to ThinkBuddy" document (Knowledge Factory section).

## Task
Build the importer that loads validated Knowledge Factory output into Postgres and indexes it for hybrid retrieval.

## Deliverables
1. Define an **import manifest format** (JSONL: book metadata, chapter list, chunk records with `printed_page`, `pdf_page_index`, `text`, `text_original`, `language`, `ocr_quality`, `validation_flags`). Document it in `/docs/ingest_format.md`.
2. Importer CLI/worker: idempotent, resumable per book and per page, writes `ingest_batches`, skips chunks failing validation (stores them as `retrievable=false` with reason).
3. Embedding job via an `EmbeddingProvider` interface with a **multilingual** implementation (bge-m3 / multilingual-e5 / hosted). Batch, retry, and cost-log.
4. `VectorStore` interface with a pgvector implementation (HNSW index) and trigram/tsvector lexical index.
5. Curriculum read APIs: books, chapters, chapter detail.
6. **Retrieval evaluation harness:** a small Bangla + English test set file format (`question`, `expected_chapter`, `expected_printed_page`), and a script that reports hit-rate@k and citation-page accuracy.

## Constraints
- Printed page and PDF index are separate columns; never mix them.
- Embedding dimension is read from provider config, not hard-coded in migrations (use a config-driven migration).
- Changing the embedding model must be possible by re-embedding into a new column/version without downtime.

## Acceptance
- Re-running an import does not duplicate chunks.
- Killing the importer mid-book and restarting resumes correctly.
- Eval harness runs and prints a report; add a threshold gate (configurable) for CI.
