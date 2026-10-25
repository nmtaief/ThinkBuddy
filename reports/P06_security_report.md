# Milestone P06 Security & Verification Report: Progress, Mastery, Revision & 3-Day Review

**Date:** 2026-10-25  
**Branch:** `feat/P06_progress_mastery_revision`  
**Commit Hash:** `46721b8`  
**Standing Rules:** Strictly enforced (Rules 1–16)  
**Status:** Complete & Passing; P05 Phase 2 and P06b remain blocked as instructed.

---

## 1. Executive Summary

Milestone P06 implements student mastery scoring, 5-box Leitner spaced repetition, adaptive daily composition, and 3-day review cycle jobs entirely against deterministic mocks and PostgreSQL fixtures without external LLM dependencies.

All 10 user requirements and Standing Rules (including Rule 3 API contract sync, Rule 5/6 server authority & key isolation, Rule 9 authorization checks, Rule 10 Alembic reversibility, and Rule 13 bilingual Bangla/English support with parent-safe terminology) have been fulfilled and verified.

---

## 2. Requirement Implementation Details

### Requirement 1: Non-Destructive Job Integration with P03 Planner
- Daily composition and 3-day review jobs (`run_daily_composition_job`, `run_three_day_review_cycle` in `core/progress/jobs.py`) **do not write tasks directly**.
- Instead, mastery scores and weak-point data are updated in the database and fed into `execute_student_plan_regeneration` (`core/planner/router.py`).
- Regeneration acquires the student-level advisory lock (`acquire_student_advisory_lock`), increments the plan version, respects blackout days, study windows, daily minute budgets, subject rotations, and preserves pinned/completed tasks.
- Restored `TimeShareConfig` weak-point share to `0.15` (study: 0.55, revision: 0.20, weak_point: 0.15, homework_quiz: 0.10) in `core/planner/engine.py`, ensuring weak-point revision time is mathematically budgeted.

### Requirement 2: Resilient Streak Continuity
- Implemented in `core/progress/streak.py` using calendar resolution via `resolve_calendar_days`.
- Streaks do **NOT** break when a student does not study on:
  - Blackout days
  - Exam days
  - Weekly off days (e.g., Friday/Saturday)
  - Explicit rest/holiday days
- An unexcused school day without completed tasks or study minutes terminates the active streak.

### Requirement 3: Batched & Throttled Job Runner
- `run_batched_daily_jobs` in `core/progress/jobs.py` processes active students in batches (default: 20) with a configurable throttle sleep (default: 50ms) to prevent database connection exhaustion and advisory lock congestion.
- Date boundary evaluation accounts for `Asia/Dhaka` local time (UTC+6).

### Requirement 4: Capped Revision Queue & Subject Exclusion
- `RevisionScheduler.get_due_items` (`core/progress/revision.py`) caps returned spaced repetition items using the student's available daily revision budget (estimated at 2 minutes per item).
- Excludes any subjects currently undergoing blackout or whose exam date has already passed.

### Requirement 5: Review Quiz Creation via P04 Builder
- When a 3-day review cycle triggers, candidate review questions are sourced from the question bank through `QuizBuilderService.select_and_randomize_questions`.
- If fewer than 3 approved questions are available for the target chapter, the job safely skips quiz creation, logs warning `REVIEW_QUIZ_INSUFFICIENT_QUESTIONS`, and continues with plan regeneration.

### Requirement 6: Offline Grounded Question Worker
- `QuestionGenerationWorker` (`core/progress/question_worker.py`) operates entirely offline without live LLM calls.
- All generated questions are strictly flagged with `pool="practice"` and `review_status="draft"`.
- Generation strictly requires a valid textbook `Chunk` ID; missing or invalid chunk IDs raise `ValueError("SOURCE_CHUNK_NOT_FOUND: ...")`.
- Isolated answer keys are securely written directly to `question_keys` table and never exposed.

### Requirement 7: Parent-Facing Safe Wording
- Parent-facing labels and statuses strictly use `"needs practice"` (`needs_practice`) and `"not enough data"` (`not_enough_data`).
- The word `"weak"` is strictly banned from user-facing API responses and localization strings (tested via `test_parent_facing_safe_wording_no_weak`).

### Requirement 8: Robust Testing Suite
Implemented in `tests/test_p06_progress_mastery_revision.py`:
1. `test_hypothesis_mastery_bounds`: Hypothesis property test verifying mastery score & confidence remain bounded in $[0.0, 1.0]$.
2. `test_hypothesis_mastery_monotonicity`: Property test verifying positive signals never decrease score and negative signals never increase score.
3. `test_hypothesis_leitner_box_progression`: Property test verifying correct reviews advance box ($1 \to 5$) and incorrect reviews reset to box 1.
4. `test_streak_continuity_with_exempt_days`: Verifies streak continuity across blackout/exam/rest days.
5. `test_revision_queue_capping_and_subject_exclusion`: Verifies queue minute capping and past exam exclusion.
6. `test_review_quiz_builder_p04_skips_when_insufficient_questions`: Verifies skipping and warning when question bank pool is insufficient.
7. `test_offline_question_worker_groundedness_and_rejection`: Verifies practice/draft pools, chunk grounding, and missing chunk rejection.
8. `test_parent_facing_safe_wording_no_weak`: Verifies absence of "weak" across `/v1/progress/summary`, `/v1/progress/mastery`, and `/v1/progress/weak-points`.
9. `test_progress_authorization_rule_9`: Verifies role and ownership checks (Rule 9).
10. `test_concurrent_double_run_idempotency`: Verifies simultaneous job runs for the same student complete cleanly under PostgreSQL advisory locks without data corruption or duplicate active plan days.
11. `test_asia_dhaka_midnight_rollover`: Verifies UTC to Asia/Dhaka midnight date boundaries.
12. `test_batched_throttled_daily_jobs`: Verifies batch execution and throttle delays.

### Requirement 9: P05 Hardening Integration
- Marked retrieved chunks with `<context>` tags and explicit reference-only system prompts in `core/chat/orchestrator.py` to prevent chunk-borne prompt injections.
- Added runtime guard in `core/chat/llm.py` ensuring `MockLLMGateway` cannot load when `ENV=production` or `ENV=staging`.

### Requirement 10: Blocked Workstreams
- **P05 Phase 2 (Live retrieval & evaluation harness with real curriculum):** Blocked pending Knowledge Factory sample textbook data and test question set.
- **P06b (External AI Planner Service):** Blocked pending external API keys and live model deployment.

---

## 3. Database Migration & Alembic Verification

- **Migration File:** `migrations/versions/0013_p06_progress_mastery_tables.py`
- **Tables Created:**
  - `mastery`: Primary key UUID, `(student_id, chapter_id, concept_id)` uniqueness, score, confidence, recency timestamp.
  - `revision_items`: Primary key UUID, 5-box Leitner state, `due_at`, `student_id`, `chapter_id`, partial unique index on `(student_id, chapter_id)` where `question_id IS NULL`.
  - `progress_daily`: Primary key UUID, daily aggregates `(student_id, date)`, minutes, tasks completed, quiz averages, active streak.
- **Reversibility:** Verified via `alembic downgrade -1` and `alembic upgrade head`.

---

## 4. Security & Quality Scanners

| Tool | Scope | Result | Status |
|---|---|---|---|
| **pytest** | Entire repository (168 tests) | 168 passed in 15.68s | **PASS** |
| **pytest (P06)** | `tests/test_p06_progress_mastery_revision.py` | 12 passed in 2.22s | **PASS** |
| **Secret Scan** | `scripts/secret_scan.py` across full repo | 0 secret leaks identified | **PASS** |
| **Bandit** | `core/` and `gateway/` | 0 High, 0 Medium issues | **PASS** |
| **Ruff** | `core/progress/` | Clean (0 fatal lint/import errors) | **PASS** |
| **OpenAPI Sync** | `tests/test_openapi_export.py` | Generated `docs-generated/openapi.json` matches contract | **PASS** |

---

## 5. Summary of Modified & Created Files

- `core/progress/jobs.py`: Daily composition and 3-day review cycle jobs with batched runner.
- `core/progress/mastery.py`: Pure library for mastery updates, recency decay, and confidence saturation.
- `core/progress/models.py`: SQLAlchemy models for `Mastery`, `RevisionItem`, and `ProgressDaily`.
- `core/progress/question_worker.py`: Grounded offline question generator.
- `core/progress/revision.py`: 5-box Leitner spaced repetition scheduler.
- `core/progress/router.py`: REST endpoints for progress summary, mastery, weak points, revision, and internal triggers.
- `core/progress/schemas.py`: Pydantic validation schemas with parent-safe terminology.
- `core/progress/service.py`: Service orchestrator for progress, mastery, and streaks.
- `core/progress/streak.py`: Resilient streak calculator handling exempt days.
- `core/progress/weights.py`: Mastery weights and learning signal multipliers.
- `core/planner/engine.py`: Restored `TimeShareConfig.weak_point_share = 0.15` and total study minute calculation.
- `core/planner/router.py`: Injected student mastery map into plan regeneration.
- `core/quiz/builder.py`: Chapter-isolated question candidate fallback.
- `core/chat/llm.py`: Production guard for `MockLLMGateway`.
- `core/chat/orchestrator.py`: Prompt-injection defense via `<context>` boundaries.
- `gateway/router.py`: Gateway forwarders for `/progress/*` and `/revision/*`.
- `docs/04_API_CONTRACT.md`: Documented all P06 routes and safety constraints.
- `docs-generated/openapi.json`: Synced OpenAPI v3 schema.
- `migrations/versions/0013_p06_progress_mastery_tables.py`: Alembic migration for P06 tables.
- `tests/test_p06_progress_mastery_revision.py`: Complete 12-test suite.
- `tests/test_p01_auth_family.py`: Updated migration chain verification.
- `tests/test_p05_rag_chat.py`: Chunk injection and mock gateway guard tests.

---

## 6. Review Readiness

The codebase is fully tested, committed, and ready for user review. P05 Phase 2 and P06b remain blocked as instructed.
