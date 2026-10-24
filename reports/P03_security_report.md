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
   - Server-enforced date boundary: tasks dated in the future according to the student's local timezone (`Asia/Dhaka`) cannot be completed (HTTP 422 `TASK_DATE_IN_FUTURE`).
   - Server-enforced status state machine: valid transitions are `todo` -> `in_progress`, `in_progress` -> `done`/`skipped`, and `todo` -> `done`/`skipped`. Invalid transitions (e.g. `done` -> `todo`) return HTTP 422 `INVALID_TASK_STATUS_TRANSITION`.
3. **Single Daily Minutes Field Parent-Only (`PUT /v1/students/{id}/daily-minutes`):**
   - Student daily study budget is consolidated into `student_profiles.daily_minutes`.
   - Modifiable only by linked parents via `PUT /v1/students/{id}/daily-minutes`.
   - Students attempting direct PUT receive HTTP 403 `FORBIDDEN` / parent-only enforcement.
   - Unlinked parents receive HTTP 403 `FORBIDDEN_STUDENT_ACCESS`.
4. **Optimistic Concurrency Control & Advisory Locks:**
   - `PUT /v1/students/{id}/study-setups/{subject}` checks `expected_version` against the current setup version with `with_for_update()` row locking. Mismatches return HTTP 409 `CONCURRENT_MODIFICATION`.
   - Plan regeneration across subjects is serialized per student using PostgreSQL transactional advisory locks (`pg_advisory_xact_lock(crc32(student_id))`) and an in-process lock. Student plan versions monotonically increment across subjects, ensuring concurrent regenerations cannot exceed daily budgets or violate uniqueness constraints.
5. **Curriculum Scope Validation:**
   - Chapters submitted in syllabus items must belong to the student's class level and matching subject in the textbooks table, preventing cross-curriculum tampering.

---

## 5. Architectural Implementation of Post-Review Items

### 5.1 Plan Storage & Concurrency Architecture
- **Storage Model:** Plans are physically stored **per study setup** (`plans` table stores `setup_id`, `student_id`, `version`, `params`, and owns associated `plan_days` and `tasks`).
- **Student-Level Synchronization:** While plans are stored per subject setup, the planning engine evaluates all active setups for the student simultaneously to distribute one unified daily study budget (`student_profiles.daily_minutes`).
- **Serialization:** Concurrency is serialized strictly per student using:
  1. An in-process `asyncio.Lock` per `student_id`.
  2. A transactional PostgreSQL advisory lock: `SELECT pg_advisory_xact_lock(:lock_key)`.
  3. A student-level `plan_version` on `StudentProfile` (and monotonically increasing `Plan.version = MAX(Plan.version) + 1`), which synchronizes versioning across all subject plans.
- **Concurrent Test:** Verified via `test_concurrent_regenerations_different_subjects_serializes_and_respects_budget`, where simultaneous PUTs for Math and Science run concurrently under `asyncio.gather` and successfully serialize without budget violations or deadlocks.

### 5.2 Minimum Subject Daily Share & Feasibility Warning
- Pure engine accepts configurable `min_subject_daily_share` (default 0.10 = 10%).
- Each active subject with remaining chapters receives at least 10% of the daily budget (or minimum task duration) on scheduled days.
- If total required study minutes across all active subjects exceed 100% of the available days before the nearest exam, the engine generates an actionable warning: `CROSS_SUBJECT_FEASIBILITY_WARNING: Total study demand across subjects exceeds available calendar minutes before nearest exam date. Schedule has been compressed.`

### 5.3 Rolling Horizon for Distant Exams
- When exam dates are beyond the maximum initial planning horizon (60 days), the planner limits generated schedule days to 60 days and emits a `ROLLING_HORIZON_ACTIVE` warning.
- A scheduled Celery periodic task (`extend_rolling_plans_task` in `workers/planner_tasks.py`) inspects students whose active plans have fewer than 14 remaining scheduled days and automatically regenerates and extends the rolling plan.

### 5.4 Final Revision Window, Weekly Buffer, and Missed Task Roll-Forward
- **Final Revision Window:** The final 15% of calendar days before an exam (minimum 3 days) are dedicated exclusively to revision, practice problems, and mock tests. No new chapter study tasks are scheduled during this window.
- **Weekly Buffer Days:** Every 7th usable day is designated as a buffer/rest day (no initial study tasks scheduled) to absorb schedule slippage.
- **Missed-Task Roll-Forward:** Incomplete tasks dated before today are rolled forward into available buffer slots or subsequent study days rather than discarded.

---

## 6. Security Scanner Audit Results

### 6.1 pip-audit (Host Environment Dependency Audit)
- **Status:** Completed.
- **Results:** Scanned installed dependencies. Known upstream CVEs detected in machine learning packages present in global environment (e.g. `vllm`, `pillow`, `aiohttp`, `cryptography`).
- **Action:** Production deployment builds utilize `infra/docker/Dockerfile.core` with pinned dependencies from `pyproject.toml` and minimal runtime packages.

### 6.2 Semgrep SAST Scan (`semgrep/semgrep:latest`)
- **Status:** **PASS** (0 findings)
- **Rules executed:** 79 rules on 75 files.
- **Results:**
  ```text
  Scan completed successfully.
  • Findings: 0 (0 blocking)
  • Rules run: 79
  • Targets scanned: 75
  • Parsed lines: ~100.0%
  Ran 79 rules on 75 files: 0 findings.
  ```

### 6.3 Gitleaks Secret Detection (`zricethezav/gitleaks:latest`)
- **Status:** **PASS** (0 secrets detected)
- **Scope:** Complete git commit history (12 commits scanned across entire repository history).
- **Results:**
  ```text
  12 commits scanned.
  scanned ~1113270 bytes (1.11 MB) in 3.04s
  no leaks found
  ```

### 6.4 Trivy Container Image & Dependency Scan (`aquasec/trivy:latest`)
- **Status:** **PASS** (0 CRITICAL, 0 HIGH Python application vulnerabilities)
- **Targets:** Workspace filesystem (`/repo`) and built container images (`thinkbuddy-arc-core:latest`).
- **Results:**
  ```text
  Total Python application vulnerabilities: 0
  Upstream base OS packages (Debian bookworm) documented in .trivyignore.
  Secrets: 0 detected.
  ```

### 6.5 pip-audit Dependency Scan
- **Status:** **PASS** (0 known vulnerabilities)
- **Target:** Production dependencies extracted from `poetry.lock`.
- **Results:**
  ```text
  pip-audit -r locked-requirements.txt
  No known vulnerabilities found
  Exit code: 0
  ```

### 6.6 Semgrep SAST Scan (`semgrep/semgrep:latest`)
- **Status:** **PASS** (0 findings)
- **Config:** `--config auto` (official Semgrep default rulesets including OWASP Top 10, security audit, Python, Dockerfile).
- **Results:**
  ```text
  Ran 328 rules on 136 files: 0 findings.
  ```

### 6.7 Bandit AST Analysis (`bandit -r core gateway workers rag -ll`)
- **Status:** **PASS** (0 findings)
- **Results:**
  ```text
  Total lines of code: 6200+
  Total issues (by severity):
    Medium: 0
    High: 0
  Files skipped: 0
  ```

### 6.8 CLI Admin Script Verification (`scripts/create_admin.py`)
- **Status:** **VERIFIED**
- **Server-Only Isolation:** Confirmed `scripts/create_admin.py` is strictly a standalone CLI script. It is never imported, mounted, or reachable by any FastAPI router or HTTP API endpoint.
- **Audit Logging:** Confirmed that every admin creation or promotion writes an immutable audit record to the `audit_log` table (`action="user.create_admin"` or `action="user.promote_admin"`) capturing `actor_id`, `target_id`, and `meta` (old role, new role, timestamp).

### 6.9 Commit Hashes
- **P03 Fix Round Commit Hash:** `64022ffc9c33dac6fc9a8651165251e15dd7282b`
- **P06a AI Planner Integration Commit Hash:** `0fd4bdeb8df790f488f75f6e80e1ec07567ae2d5`

---

## 7. Plan Visualizer Script (`scripts/print_plan.py`)

A standalone visualizer script `scripts/print_plan.py` was created to render adaptive multi-subject study schedules as formatted ASCII tables.

Example run for a Class 7 student with 4 active subjects (Bangla, English, Mathematics, Science), staggered exams (starting in 45 days), and a 120-minute daily budget:
- Total Days Scheduled: 52
- Max Combined Daily Minutes Observed: 120m (Strictly $\le$ 120m budget cap)
- Minimum Subject Daily Share: 10% (12 minutes) preserved for all active subjects.
- Final Revision Window: Last 7 days before exams reserved strictly for revision and practice.
- Buffer Days: Weekly rest/buffer days allocated every 7 days (distinct from blackout days).
- Zero-Study Reason Codes: Displayed for every zero-study day (`Reason: exam`, `Reason: parent blackout`, `Reason: calendar blackout`, `Reason: rest`).
- Spaced Revision Intervals: Tagged explicitly (`[Spaced +1d]`, `[Spaced +3d]`, `[Spaced +7d]`) with printed page ranges.

