# P06 – Progress, Mastery, Spaced Revision, 3-Day Review

**Read first:** `AGENT_RULES.md`, `docs/06_ADAPTIVE_ENGINE.md` (all), `docs/02_PRODUCT_FLOWS.md` (§4.2, §4.5), `docs/03_DATA_MODEL.md` (§6).

## Task
Turn learning signals into mastery, revision items, and dynamically updated plans.

## Deliverables
1. Signal ingestion service (from quiz grading, chat, task skips; teacher later).
2. Mastery calculator (pure library): recency decay, confidence, practice vs assessed weighting. Config in one weights file.
3. Revision scheduler: Leitner boxes with configured intervals; daily revision list endpoint.
4. Daily job: builds each student's next-day composition (study / revision / weak-point practice / homework+quiz) per the share table, writing `tasks` with `source=adaptive`.
5. 3-day review job: builds review quiz (assessed) + broad questions, recomputes mastery, rewrites upcoming adaptive tasks.
6. Grounded question generation worker: generate → validate (second pass) → store as `ai_generated` with `source_chunk_ids` and variants; used for practice only until approved.
7. Progress endpoints: summary, mastery by chapter, weak points, history; "not enough data" state when confidence is low.
8. Idempotent jobs; safe to re-run; per-student locking.

## Acceptance
- Simulation tests: a student who keeps missing a concept sees it in revision within the expected interval; a student with strong mastery gets fewer revision slots.
- Jobs are idempotent (running twice does not duplicate tasks).
- Generated questions without a valid source chunk are rejected.
