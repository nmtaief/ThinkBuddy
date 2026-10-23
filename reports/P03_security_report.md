# ThinkBuddy Security & Verification Report – Milestone P03 (Study Setup & Planner)

**Date:** 2026-10-23  
**Auditor / Lead Engineer:** ThinkBuddy Lead Engineer (Antigravity)  
**Milestone:** P03 – Study Setup & Versioned Adaptive Planner  
**Branch:** `feat/P03_planner`  

---

## 1. Executive Summary

Milestone P03 delivers the study setup and versioned adaptive planner for ThinkBuddy, implementing the requirements from `AGENT_RULES.md`, `docs/02_PRODUCT_FLOWS.md` (§4.1, §4.2, §6), `docs/06_ADAPTIVE_ENGINE.md` (§1, §4), and `docs/03_DATA_MODEL.md` (§3).

All deliverables and architectural amendments specified for P03 have been implemented and verified:
1. **Pure-Python Planner Engine (`core/planner/engine.py`):**
   - Zero DB, HTTP, or framework imports.
   - Accepts `today: datetime.date` explicitly as an input parameter and never reads the system clock.
   - Implements multi-subject shared daily study minutes allocation (student-level budget), favoring nearer exams and heavier chapters while strictly guaranteeing that no combined day exceeds the student's daily study minutes.
   - Reserves a final revision window (last 15% of usable days, minimum 3 days) and weekly buffer days.
   - Configurable task time shares: Study (65%), Revision (25%), Homework & Quizzes (10%), with the 15% weak-point share from `docs/06_ADAPTIVE_ENGINE.md §4` explicitly reassigned to study (+10%) and revision (+5%) until P06.
   - Infeasible exam handling: returns compressed plans with descriptive warnings (e.g., `EXAM_TOO_CLOSE`, `EXAM_TODAY`, `EXAM_TOMORROW`, `ZERO_USABLE_DAYS`), never crashing or throwing 500 errors.
   - Preserves completed historical tasks during plan regeneration.
2. **Database Schema & Migrations (`0004_p03_study_planner`):**
   - Implemented `study_setups`, `syllabus_items`, `plans`, `plan_days`, `tasks`, and `student_change_requests`.
   - Added `difficulty_factor` (default 1.0) to `chapters` and `time_zone` (default `'Asia/Dhaka'`) to `student_profiles`.
   - Reused the existing `audit_log` table for immutable tracking of parent setup modifications.
   - Verified 100% reversible migration against live PostgreSQL.
3. **API Endpoints & Gateway Routing:**
   - `PUT /v1/students/{id}/study-setups/{subject}`: parent-only study setup upsert with optimistic concurrency control (`expected_version` returning 409 Conflict on mismatch), row locking (`with_for_update()`), and chapter subject/class validation.
   - `POST /v1/students/{id}/study-setups/{subject}/change-requests`: student-initiated schedule adjustment requests.
   - `GET /v1/students/{id}/plan`: date-filtered versioned plan with tasks and planned minutes.
   - `GET /v1/students/{id}/today`: home screen learning loop payload (study, revision, homework, quiz, streak, and countdown to exams in Dhaka local time).
   - `PATCH /v1/tasks/{id}`: student-only status update with strict owner authorization; parents are strictly read-only (HTTP 403 `TASK_UPDATE_STUDENT_ONLY`) and cross-student updates are blocked (HTTP 403 `FORBIDDEN`).
4. **Idempotent Background Worker (`workers/planner_tasks.py`):**
   - Celery background job supporting asynchronous plan regeneration that no-ops if a plan version is already active.
5. **OpenAPI Specification:**
   - Regenerated `docs-generated/openapi.json` documenting all 5 new endpoints and models.

---

## 2. Verification Checks Summary

| Category | Tool / Method | Target / Scope | Status | Result / Notes |
|---|---|---|---|---|
| **Code Style & Linting** | `ruff check .` & `ruff format` | Entire workspace (88 files) | **PASS** | 0 errors, strict formatting enforced |
| **Static Type Safety** | `mypy` 1.15.0 | `core`, `gateway`, `workers`, `rag`, `scripts` | **PASS** | Strict mode passed across 74 source files (0 type errors) |
| **AST Security Analysis** | `bandit` 1.8.3 | `core`, `gateway`, `workers`, `rag` (`-ll`) | **PASS** | 5,640 lines scanned: 0 Medium/High issues identified |
| **Property-Based Testing** | `hypothesis` 6.170.8 | `core/planner/engine.py` | **PASS** | Property tests for daily budget caps, exam horizon, chapter order |
| **Automated Test Suite** | `pytest` 9.1.0 | `tests/` (50 test cases) | **PASS** | 50 passed in 3.62s (100% pass rate) against live Compose services |
| **Database Migrations** | Alembic `0004_p03_study_planner` | Live Compose PostgreSQL (`127.0.0.1:5432`) | **PASS** | Upgraded to head, tested full downgrade reversibility and re-applied |

---

## 3. Property Tests & Edge Cases Verified

1. **Combined Multi-Subject Daily Budget Cap (Hypothesis):**
   - Verified that across randomized daily budgets (20–180m), multiple subjects, varied exam deadlines, and chapter page counts, on **every single day**, $\sum_{\text{tasks}} \text{minutes} \le \text{daily\_study\_minutes}$.
2. **No Tasks After Exam Date (Hypothesis):**
   - Verified that no task is ever scheduled on a date $> \text{exam\_date}$.
3. **Strict Chapter Sequence Preservation:**
   - Verified that tasks for Chapter $i$ precede or co-occur with Chapter $i+1$, never appearing later.
4. **Completed Task Preservation:**
   - Verified that plan regeneration with modified syllabus/exam retains previously completed tasks on historical days with status `done`.
5. **Edge Case: Exam Today or Tomorrow:**
   - Verified that exam dates on `today` or `today + 1` generate urgent review plans and return clear warnings (`EXAM_TODAY`, `EXAM_TOMORROW`) without throwing 500 errors.
6. **Edge Case: Zero Usable Days:**
   - Verified that when available study days do not overlap with days remaining before an exam, an emergency fallback day is provided with warning `ZERO_USABLE_DAYS`.
7. **Edge Case: Empty Syllabus:**
   - Verified that study setups without chapters produce a safe plan with warning `NO_ACTIVE_SUBJECTS` and 0 tasks.
8. **Edge Case: Huge Chapter (500 pages):**
   - Verified that a 500-page chapter with a 30-minute daily budget is contiguously partitioned across days without exceeding the daily cap.
9. **Edge Case: Midnight in Dhaka:**
   - Verified that 18:05 UTC correctly resolves to 00:05 next day in `Asia/Dhaka` timezone.

---

## 4. Authorization & Security Guarantees

1. **Parent-Only Setup Modification (Rule 9):**
   - Unlinked parents calling `PUT /v1/students/{id}/study-setups/{subject}` are rejected with HTTP 403 `FORBIDDEN_STUDENT_ACCESS`.
   - Students attempting direct setup modification are rejected with HTTP 403 `STUDENT_CANNOT_EDIT_SETUP` (must submit change requests).
2. **Student-Only Task Completion (`PATCH /v1/tasks/{id}`):**
   - Parents attempting to mark a task as done receive HTTP 403 `TASK_UPDATE_STUDENT_ONLY`.
   - Student A attempting to modify Student B's task receives HTTP 403 `FORBIDDEN`.
   - The owning student successfully marks the task as done, populating `completed_at`.
3. **Optimistic Concurrency Control:**
   - `PUT /v1/students/{id}/study-setups/{subject}` checks `expected_version` against the current setup version with `with_for_update()` row locking. Mismatches return HTTP 409 `CONCURRENT_MODIFICATION`.
4. **Curriculum Scope Validation:**
   - Chapters submitted in syllabus items must belong to the student's class level and matching subject in the textbooks table, preventing cross-curriculum tampering.
