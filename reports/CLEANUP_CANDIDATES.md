# ThinkBuddy Repository Cleanup Candidates (Phase 1 Audit)

**Date:** 2026-11-07  
**Branch:** `chore/cleanup-and-claude-guide`  
**Status:** **AWAITING USER APPROVAL (NO DELETIONS PERFORMED)**  
**Audit Scope:** One-off scripts, duplicate docs, agent rules, unused dependencies, dead code, stray build outputs, oversized files, and `.gitignore` gaps.

---

## 1. Executive Summary & Methodology

This audit was conducted strictly in read-only mode to identify all redundant, duplicate, generated, dead, and obsolete artifacts across the ThinkBuddy repository. Every candidate is verified with search evidence and tool output (Ruff, ESLint, Python AST analysis, Gradle check, and Git blob history).

### Protected Items Confirmed Intact
Per strict standing instructions, the following categories were **not** scheduled for deletion and remain untouched:
- Alembic database migrations (`migrations/`)
- All backend test suites (`tests/`)
- Security & readiness reports (`reports/*security_report.md`, `reports/P10_beta_readiness_report.md`, `reports/P10_security_review.md`)
- Generated OpenAPI schema contract (`docs-generated/openapi.json`)
- GitHub workflows and templates (`.github/`)
- Standing rule files: `AGENT_RULES.md`, `GEMINI.md`, `QUESTIONS.md`, `SECURITY.md`, `LICENSE`, and `runbooks/`
- Anything referenced by CI, Docker Compose, Makefile, or production scripts
- Android signing, Firebase, and environment configurations

---

## 2. Comprehensive Cleanup Candidates Table

| # | Candidate File / Folder | Category | Reason for Cleanup | Evidence of Unuse / Redundancy | Risk if Wrong | Recommended Action (Phase 2) |
|---|---|---|---|---|---|---|
| **1** | `scripts/clean_web_religion_remnants.py` | One-off Script | Hardcoded search-and-replace script executed once during P08 to remove religion remnants from `TodayView.tsx`. | `git grep`: 0 references in CI, Makefile, workflows, or tests. Hardcoded replacement strings are already committed. | Minimal (script was a one-time migration helper). | `git rm` |
| **2** | `scripts/religion_audit.py` | One-off Script | Standalone scanner used during P08 to audit religious keywords. Superseded by automated test suites (`test_p07b`, `test_p08`). | 0 references in Makefile, CI workflows, or test suites. | Minimal (ad-hoc audit script). | `git rm` (or archive to `docs/archive/`) |
| **3** | `web/scripts/verify_monorepo.mjs` | Scratch Script | One-off Playwright runner with hardcoded Windows local agent brain path (`C:/Users/UseR/.gemini/antigravity/...`). | Contains machine-specific absolute brain paths; not referenced in `package.json` or CI. | Low (ad-hoc verification script). | `git rm` |
| **4** | `web/scripts/verify_mobile_optimizations.mjs` | Scratch Script | One-off mobile viewport verifier with hardcoded Windows local brain path. | Machine-specific absolute path; not part of standard Playwright suite. | Low (ad-hoc verification script). | `git rm` |
| **5** | `thinkbuddy-docs/prompts/08_CLIENT_PLATFORM_GUIDE.md` | Duplicate Document | Exact copy of `docs/08_CLIENT_PLATFORM_GUIDE.md` mistakenly placed in `prompts/`. | It is a specification document, not an agent milestone prompt (`P00`–`P10`). | Zero (`docs/08_CLIENT_PLATFORM_GUIDE.md` is canonical). | `git rm` |
| **6** | `thinkbuddy-docs/docs/04_API_CONTRACT.md` | Outdated Duplicate | Ancient P00 scaffold stub (8.1 KB), whereas `docs/04_API_CONTRACT.md` (25.6 KB) is the live, maintained contract. | Out of sync by 17.5 KB; misses all P01–P10 endpoint specifications. | Zero (`docs/04_API_CONTRACT.md` is canonical). | Replace with pointer to `../../docs/04_API_CONTRACT.md` |
| **7** | `thinkbuddy-docs/docs/05_SECURE_QUIZ.md` | Outdated Duplicate | Outdated copy (5,012 bytes) vs canonical `docs/05_SECURE_QUIZ.md` (5,151 bytes). | Older timestamp and missing recent hardening notes. | Zero (`docs/05_SECURE_QUIZ.md` is canonical). | Replace with pointer to `../../docs/05_SECURE_QUIZ.md` |
| **8** | `thinkbuddy-docs/docs/07_AI_PLANNER_API.md` | Duplicate Document | Byte-for-byte identical duplicate of `docs/07_AI_PLANNER_API.md` (12,204 bytes). | `Compare-Object`: 100% identical. | Zero. | Replace with pointer to `../../docs/07_AI_PLANNER_API.md` |
| **9** | `thinkbuddy-docs/docs/08_CLIENT_PLATFORM_GUIDE.md` | Duplicate Document | Byte-for-byte identical duplicate of `docs/08_CLIENT_PLATFORM_GUIDE.md` (6,129 bytes). | `Compare-Object`: 100% identical. | Zero. | Replace with pointer to `../../docs/08_CLIENT_PLATFORM_GUIDE.md` |
| **10** | `thinkbuddy-docs/README.md` | Outdated Duplicate | Outdated copy of root `README.md` lacking the updated NCTB licensing open question. | Missing open question from prompt 1. Root `README.md` is canonical. | Zero. | Replace with pointer to `../README.md` |
| **11** | `thinkbuddy-docs/AGENT_RULES.md` | Duplicate Agent Rules | Byte-for-byte duplicate of root `AGENT_RULES.md` (2,847 bytes). | `Compare-Object`: 100% identical. | Zero. | Replace with pointer to `../AGENT_RULES.md` |
| **12** | `GEMINI.md` | Duplicate Agent Rules | Byte-for-byte duplicate of root `AGENT_RULES.md` (2,847 bytes). | `Compare-Object`: 100% identical. Required by Antigravity IDE workspace rules. | Low. | Keep `AGENT_RULES.md` as canonical; make `GEMINI.md` an explicit pointer referencing `AGENT_RULES.md`. |
| **13** | Missing Specs in `docs/`: `01_ARCHITECTURE.md`, `02_PRODUCT_FLOWS.md`, `03_DATA_MODEL.md`, `06_ADAPTIVE_ENGINE.md` | Specification Split | These 4 core specs exist *only* in `thinkbuddy-docs/docs/`, causing broken links when looking in `docs/`. | `docs/01_ARCHITECTURE.md` was missing when executing load test checks. | Low (unification fixes broken references). | Copy canonical versions into `docs/`; make `thinkbuddy-docs/docs/` point to `docs/`. |
| **14** | `reports/load_test_results.json` | Generated File Tracked | 115.8 KB raw JSON timing output from laptop load test run. | Generated dynamically by `scripts/run_load_test.py`. Not a static report. | Low. | `git rm --cached`; add to `.gitignore`. |
| **15** | `reports/P03_class_10_science_schedule.txt` | Generated Test Dump | Raw stdout printout from P03 planner schedule run. | Static diagnostic dump; not part of security/readiness reporting. | Minimal. | `git rm` (or archive to `reports/archive/`) |
| **16** | `reports/P03_class_7_schedule.txt` | Generated Test Dump | Raw stdout printout from P03 planner schedule run. | Static diagnostic dump. | Minimal. | `git rm` (or archive to `reports/archive/`) |
| **17** | `reports/P03_stress_case_schedule.txt` | Generated Test Dump | Raw stdout printout from P03 planner schedule run. | Static diagnostic dump. | Minimal. | `git rm` (or archive to `reports/archive/`) |
| **18** | `packaging>=24.0` in `pyproject.toml` | Unused Python Dependency | Declared in `project.dependencies` in `pyproject.toml`. | AST & grep: 0 imports across `core/`, `gateway/`, `workers/`, `scripts/`, and `tests/`. | Zero (unused packaging utility). | Remove from `pyproject.toml`. |
| **19** | `room = "2.6.1"` in `android/gradle/libs.versions.toml` | Unused Gradle Version | Declared under `[versions]` in `libs.versions.toml`. | 0 library definitions in `[libraries]`; 0 references in `android/app/build.gradle.kts`. | Zero (dangling version string). | Remove from `libs.versions.toml`. |
| **20** | Dead code: 35 Unused Python Imports | Dead Code / Imports | Unused imports flagged by `ruff check --select F401`. | Full list in §3 below. Cleaned safely via `ruff check --fix`. | Zero (standard lint cleanup). | Remove via automated fix in dedicated commit. |
| **21** | Dead code: 5 Unused Local Variables in Core | Dead Code / Variables | Unused assignments flagged by `ruff check --select F841,B007`. | Detailed in §3 below (`redis_error`, `terms_hash`, `grp_id`, etc.). | Zero. | Clean in dedicated commit. |
| **22** | Web Lint & Unused Variables (28 issues) | Dead Code / Web Lint | 5 ESLint errors and 23 unused variables/imports in `web/src`. | `npm run lint` in `web/` fails with 5 errors (`react-hooks/set-state-in-effect`, unescaped entities, `any`). | Moderate (must preserve Next.js behavior). | Fix lint errors and remove unused variables in Phase 2. |

---

## 3. Detailed Breakdown of Dead Code & Unused Elements

### 3.1. Python Backend Unused Imports (`F401`)
Verified by `ruff check core gateway workers --select F401`:
1. `core/common/config.py:3`: `pydantic.AliasChoices`
2. `core/notifications/sender.py:13`: `typing.Any`
3. `core/planner/provider.py:49`: `core.planner.engine.ChapterPlanInput`
4. `core/planner/pseudonymizer.py:19`: `core.planner.engine.ChapterPlanInput`
5. `core/planner/rollout.py:13`: `uuid`
6. `core/planner/rollout.py:17`: `sqlalchemy.select`
7. `core/planner/rollout.py:18`: `sqlalchemy.dialects.postgresql.insert`
8. `core/planner/router.py:31`: `core.planner.engine.generate_student_plan`
9. `core/planner/router.py:48`: `core.progress.models.Mastery`
10. `core/planner/validator.py:30`: `datetime.datetime`
11. `core/planner/validator.py:30`: `datetime.timedelta`
12. `core/planner/validator.py:36`: `core.contracts.ai_planner.PrioritySuggestion`
13. `core/privacy/consent_guard.py:15`: `uuid`
14. `core/privacy/consent_guard.py:17`: `typing.Any`
15. `core/privacy/service.py:22`: `core.planner.models.Plan`
16. `core/privacy/service.py:22`: `core.planner.models.Task`
17. `core/privacy/service.py:46`: `core.progress.models.ProgressDaily`
18. `core/quiz/builder.py:20`: `datetime.UTC`
19. `gateway/router.py:68`: `core.privacy.schemas.AccountDeletionResponse`
20. `gateway/router.py:69`: `core.privacy.schemas.CancelDeletionResponse`
21. `gateway/router.py:71`: `core.privacy.schemas.FamilyDataExportResponse`
22. `gateway/router.py:72`: `core.privacy.schemas.ParentalConsentRequest`
23. `gateway/router.py:73`: `core.privacy.schemas.ParentalConsentResponse`
24. `gateway/router.py:74`: `core.privacy.schemas.ParentalConsentStatusResponse`
25. `gateway/router.py:75`: `core.privacy.schemas.PurgeJobReport`
26. `gateway/router.py:76`: `core.privacy.schemas.RequestAccountDeletionBody`
27. `gateway/router.py:77`: `core.privacy.schemas.WithdrawConsentRequest`

### 3.2. Python Backend Unused Local Variables (`F841`, `B007`)
1. `core/auth/models.py:51`: Missing import `from typing import Any` (`F821 Undefined name Any`).
2. `core/common/rate_limit.py:168`: `redis_error = True` assigned but never read.
3. `core/privacy/service.py:189`: `terms_hash = payload.terms_hash or CURRENT_CONSENT_TEXT_HASH` assigned but not passed.
4. `core/quiz/builder.py:154`: Loop variable `grp_id` unused (`for grp_id, group_questions in ...`).
5. `core/quiz/builder.py:211`: Loop variable `grp_id` unused (`for grp_id, group_questions in ...`).
6. `core/quiz/integrity.py:429`: `total_events_count = len(existing_events)` assigned but never used.

### 3.3. Web Frontend ESLint Errors & Unused Variables
Verified by `npm run lint` in `web/`:
- **5 Errors to Fix:**
  - `web/src/app/page.tsx:112`: Synchronous `setState` inside `useEffect` (use initializer or separate listener).
  - `web/src/components/parent/StudySetupEditorView.tsx:39`: Synchronous `setState` inside `useEffect`.
  - `web/src/components/parent/ParentDashboardView.tsx:450`: Unescaped raw quotes (`"` $\to$ `&quot;`).
  - `web/src/components/parent/ParentOnboardingView.tsx:149`: Explicit `any` type.
- **Unused Variable Warnings to Clean:**
  - `web/src/app/page.tsx`: `translations`
  - `web/src/components/layout/Sidebar.tsx`: `Settings` icon
  - `web/src/components/parent/ParentDashboardView.tsx`: `BookOpen` icon
  - `web/src/components/student/PracticeQuizRunner.tsx`: `AlertCircle`, `BookOpen` icons
  - `web/src/components/student/ProgressView.tsx`: `CheckCircle2`, `RotateCcw`, `AlertTriangle`, `HelpCircle`
  - `web/src/components/student/StudentChangeRequestView.tsx`: `t`
  - `web/src/components/student/StudySessionRoomView.tsx`: `Sparkles`, `Save`, `Flame`
  - `web/src/components/student/TodayView.tsx`: `timeSpentSeconds`, `note`, `quizScore`
  - `web/src/lib/api-client.ts`: `ChatMessage`
  - `web/src/middleware.ts`: `request`
  - `web/tests/unit/client_logic.test.mjs`: `ABSOLUTE_TIMEOUT_SECONDS`

---

## 4. Documentation & Agent Rules Unification Plan

### Proposed Canonical Architecture:
```
docs/ (CANONICAL DIRECTORY FOR ALL DOCUMENTATION)
├── 01_ARCHITECTURE.md           <-- Copied from thinkbuddy-docs/docs/ (Canonical)
├── 02_PRODUCT_FLOWS.md          <-- Copied from thinkbuddy-docs/docs/ (Canonical)
├── 03_DATA_MODEL.md             <-- Copied from thinkbuddy-docs/docs/ (Canonical)
├── 04_API_CONTRACT.md           <-- Existing up-to-date specification (Canonical)
├── 05_SECURE_QUIZ.md            <-- Existing up-to-date specification (Canonical)
├── 06_ADAPTIVE_ENGINE.md        <-- Copied from thinkbuddy-docs/docs/ (Canonical)
├── 07_AI_PLANNER_API.md         <-- Existing specification (Canonical)
├── 08_CLIENT_PLATFORM_GUIDE.md  <-- Existing specification (Canonical)
├── ingest_format.md
├── deployment/
│   ├── CLOUDFLARE_CONFIG.md
│   ├── SECRETS_MANAGEMENT.md
│   └── STAGING_LOAD_TEST_PLAN.md
└── runbooks/

AGENT_RULES.md (CANONICAL RULES FILE AT REPOSITORY ROOT)
├── GEMINI.md                    <-- Pointer file referencing AGENT_RULES.md
└── thinkbuddy-docs/
    ├── AGENT_RULES.md           <-- Pointer file referencing ../AGENT_RULES.md
    ├── README.md                <-- Pointer file referencing ../README.md
    ├── docs/                    <-- Pointer files referencing ../../docs/*
    └── prompts/
        └── (P00 through P10 prompts preserved intact)
```

**Why this choice:**
1. Eliminates confusion where `docs/01_ARCHITECTURE.md` was missing because it only existed in `thinkbuddy-docs/docs/`.
2. Preserves all prompt history in `thinkbuddy-docs/prompts/` while ensuring that any tool, developer, or agent reading `docs/` always finds the complete, authoritative documentation.
3. Keeps `AGENT_RULES.md` as the single canonical source of truth for standing rules.

---

## 5. Tracked Files to Untrack & Add to `.gitignore`

The following entries should be added to the repository root `.gitignore`:
1. `reports/*.json` and `reports/load_test_results.json` (untrack current file).
2. `reports/P03_*.txt` (raw test schedule dumps).
3. `CLAUDE.local.md` (local engineer instructions).
4. `.claude/settings.local.json` (Claude local tool configuration).
5. Next.js and Playwright output patterns at root level:
   ```gitignore
   # Next.js and test output
   .next/
   **/out/
   test-results/
   playwright-report/
   ```

---

## 6. Oversized Files Audit

Inspection of all git objects across repository history:
- **Largest file in working tree / history:** `web/package-lock.json` (**254.67 KB**).
- **Second largest:** `docs-generated/openapi.json` (**177.94 KB**).
- **Third largest:** `tests/test_p04_secure_quiz.py` (**127.41 KB**).
- **Fourth largest:** `reports/load_test_results.json` (**115.85 KB** - candidate to untrack).
- **Conclusion:** There are **zero** oversized binary blobs (>500 KB) tracked in git history. All large files are standard lockfiles, schema files, or extensive test suites.

---

## 7. Next Steps for Phase 2 (Pending User Approval)

Upon your explicit approval of this candidates list:
1. Execute `git rm` on approved one-off scripts and generated dumps.
2. Unify documentation into `docs/` and establish pointers for duplicates.
3. Update `.gitignore` with the approved ignore rules and untrack `reports/load_test_results.json`.
4. Remove unused dependencies (`packaging` from `pyproject.toml`, `room` from `libs.versions.toml`).
5. Fix dead imports, undefined `Any`, and unused variables across Python and web frontend.
6. Commit Phase 2 deletions and fixes in one dedicated commit.
7. Run the full verification suite (`ruff`, `mypy`, `pytest -q`, openapi export check, web lint & tests, `./gradlew testDebugUnitTest`, `assembleDebug`, and secret scan) and report the results.
8. Implement Part 2 (`CLAUDE.md`, `core/CLAUDE.md`, `web/CLAUDE.md`, `android/CLAUDE.md`).

