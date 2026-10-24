# ThinkBuddy Security & Hardening Report – Milestone P04 (Secure Quiz & Assessment Engine)

**Date:** 2026-10-25  
**Auditor / Lead Engineer:** ThinkBuddy Lead Engineer (Antigravity)  
**Milestone:** P04 – Secure Quiz & Assessment Engine Hardening  
**Branch:** `feat/P04_secure_quiz`  
**Git Base:** Merged with `feat/P03_planner`  

---

## 1. Executive Summary

Milestone P04 delivers a production-grade, hardened secure quiz and assessment engine for ThinkBuddy, implementing all requirements from `AGENT_RULES.md`, `docs/04_API_CONTRACT.md`, `docs/05_SECURE_QUIZ.md`, and the P04 conditional acceptance criteria.

All 8 hardening and security directives have been implemented and verified with automated test suites:
1. **Open Attempt States & Invariant Enforcement:** Defined open attempt states (`created`, `active`, `warned`, `paused`) and bound them across:
   - Partial unique index `uq_quiz_attempts_active_student_assessed` on `quiz_attempts(student_id) WHERE state IN ('created', 'active', 'warned', 'paused') AND mode = 'assessed'`.
   - AI Chat lockout (`core/chat/router.py`) preventing chatbot assistance while any assessed attempt is in an open state.
   - Internal active attempt endpoint (`/internal/quiz/students/{id}/active-attempt`).
   - Expiration worker (`workers/quiz_tasks.py`).
   - Enforced that attempt deadlines (`deadline_at`) strictly never extend when an attempt is paused.
   - Verified with tests for starting second attempts and chatting while warned or paused.
2. **Server-Side Play Integrity Verification & Low-Trust Device Policy:**
   - Cryptographically verifies Google Play Integrity verdicts on the server (`verify_play_integrity_token` in `core/quiz/integrity.py`), enforcing package name (`com.thinkbuddy.app`), per-device request nonce, and token freshness (< 300 seconds).
   - Mock attestation stubs report `UNVERIFIED` (initial integrity score 0.90, telemetry event `unverified_device_attestation`, never `SECURE`), and are strictly prohibited from loading outside `ENV=local` (returning `COMPROMISED`).
   - Established policy for devices without Google Play services (`X-Device-Attestation-Provider: none/aosp/hms`), granting access under a `LOW_TRUST` scrutiny profile with an initial integrity score of 0.85 and recording `low_trust_device_active`.
3. **Dual-Tiered Rate Limiting:**
   - Implemented per-authenticated-user rate limits on quiz attempts (5 req/min on start, 15 req/min on answer) combined with higher per-IP ceilings (25 req/min on start, 60 req/min on answer), preventing single-user spam while accommodating shared NATs in school environments.
4. **Adaptive Anomaly Detection, Multi-Signal Invalidation & Parent Override:**
   - Scaled minimum reading time thresholds by stem character length and question type (`mcq`: 1200ms + 20ms/char; `short`: 2000ms + 25ms/char; `broad`: 5000ms + 30ms/char).
   - Enforced rule that attempt invalidation strictly requires $\ge 2$ distinct anomaly signals (a single signal pauses the attempt).
   - Implemented parent "mark as allowed" flow (`POST /v1/attempts/{id}/allow`), allowing linked parents to clear invalidations/pauses, restore scores, and log immutable `AuditLog` records.
5. **Database Role Segregation & Column-Level Encryption:**
   - Established discrete PostgreSQL roles: `thinkbuddy_api` (revoked from `question_keys`, restricted to `v_questions_public`) and `thinkbuddy_grading` (authorized for `question_keys`). Verified via automated database permissions tests.
   - Implemented AES-256-GCM column encryption (`core/quiz/crypto.py`) with keys supplied from environment/secrets manager. Documented Beta vs. Production encryption architecture.
6. **Worker Concurrency & Idempotency:**
   - Enforced `with_for_update(skip_locked=True)` in `workers/quiz_tasks.py`, eliminating deadlocks and race conditions.
   - Implemented idempotent grading and learning signal emission against `ref_id`, verified with concurrent `submit_attempt` vs. worker execution.
   - Configured Celery Beat schedule for 30s auto-submission.
7. **Exhausted Assessed Question Pool Fallback:**
   - Implemented LRU (Least Recently Used) recycling in `QuizBuilderService`: recycles oldest-answered assessed questions without ever leaking practice-only questions, shuffling options and generating new cryptographic nonces.
8. **Gateway Internal Route Isolation & Signed Service Tokens:**
   - Hardened Gateway router to strictly block `/internal/*` and `/v1/internal/*` with HTTP 404.
   - Migrated internal inter-service authentication to signed HS256 JWT service tokens (`core/common/service_token.py`) verifying issuer, audience, and expiration.

---

## 2. Deliverables & Verification Matrix

| # | Hardening Requirement | Component / Location | Status | Verification Check |
|---|---|---|---|---|
| **1** | Open attempt states (`created`, `active`, `warned`, `paused`) in unique index & chat lockout; frozen pause deadline | `migrations/versions/0010_p04_hardening.py`, `core/quiz/models.py`, `core/chat/router.py` | **PASS** | `test_open_attempt_states_unique_index_and_lockouts` |
| **2** | Server-side Play Integrity token verification, local stub `UNVERIFIED`, low-trust handling | `core/quiz/integrity.py`, `core/quiz/service.py` | **PASS** | `test_play_integrity_verification_and_low_trust` |
| **3** | Dual-tiered rate limits (authenticated user + IP ceiling) | `gateway/router.py`, `core/common/rate_limit.py` | **PASS** | `test_rate_limits_on_attempt_start_and_answer` |
| **4** | Stem-scaled too-fast rule, $\ge 2$ signals for invalidation, parent "mark as allowed" flow | `core/quiz/integrity.py`, `core/quiz/service.py`, `core/quiz/router.py` | **PASS** | `test_scaled_too_fast_rule_multi_signal_and_parent_allow` |
| **5** | Separate DB roles for API vs. Grading, AES-256-GCM column encryption, API denied `question_keys` | `scripts/setup_roles.py`, `core/quiz/crypto.py` | **PASS** | `test_database_role_separation_and_column_encryption` |
| **6** | `FOR UPDATE SKIP LOCKED` in expiry worker, idempotent grading/signals, concurrent test, Celery schedule | `workers/quiz_tasks.py`, `core/quiz/grading.py`, `workers/celery_app.py` | **PASS** | `test_concurrent_submit_versus_expiry_and_worker_schedule` |
| **7** | Fallback for exhausted assessed pools (LRU recycling, zero practice leakage, option shuffle) | `core/quiz/builder.py` | **PASS** | `test_exhausted_assessed_pool_fallback_lru` |
| **8** | Gateway blocks `/internal/*` with 404, signed JWT service tokens for internal routes | `gateway/main.py`, `gateway/router.py`, `core/common/service_token.py` | **PASS** | `test_gateway_never_proxies_internal_and_signed_jwt_service_token` |

---

## 3. Deep-Dive Security Architecture

### 3.1 Open Attempt State Machine & Deadline Immutability
- **States:** `OPEN_ATTEMPT_STATES = ("created", "active", "warned", "paused")`.
- **Database Unique Constraint:**
  ```sql
  CREATE UNIQUE INDEX uq_quiz_attempts_active_student_assessed 
  ON quiz_attempts (student_id) 
  WHERE state IN ('created', 'active', 'warned', 'paused') AND mode = 'assessed';
  ```
- **Deadline Freeze on Pause:** If an attempt transitions to `paused` due to device instability or repeated warnings, `attempt.deadline_at` is strictly preserved. Pausing freezes the student's ability to answer (`403 ATTEMPT_PAUSED`), but **never extends the exam expiration clock**, eliminating exploitation via artificial disconnects.
- **Lockout Coverage:** Both `warned` and `paused` states actively block starting another quiz (409) and lock out AI tutor chat (403 `QUIZ_IN_PROGRESS_CHAT_LOCKED`).

### 3.2 Device Integrity Verification & Low-Trust Device Policy
- **Play Integrity Token Verification:**
  - Token claims parsed for `appIntegrity.packageName == "com.thinkbuddy.app"`.
  - Nonce checked against `expected_nonce` (bound to device ID).
  - Freshness verified: timestamp age $< 300$ seconds.
  - Verdicts evaluated: `MEETS_STRONG_INTEGRITY` $\to$ `SECURE`, `MEETS_BASIC_INTEGRITY` $\to$ `BASIC`, compromised $\to$ `COMPROMISED`.
- **Local Stub Constraint:**
  - In `ENV=local`, test stubs report `UNVERIFIED` (initial integrity score 0.90, `unverified_device_attestation` event, never `SECURE`).
  - Outside `ENV=local` (e.g. `production`), stub strings return `COMPROMISED` and are blocked with HTTP 403 `DEVICE_INTEGRITY_FAILED`.
- **Low-Trust Handling (Devices without Google Play Services):**
  - Android AOSP, Huawei HMS, and custom ROMs without Google Play Services supply `X-Device-Attestation-Provider: none/aosp/hms`.
  - Backend tags attempt as `LOW_TRUST`, starts with a reduced baseline integrity score of `0.85`, records a `low_trust_device_active` audit event, and flags the attempt for review if any secondary anomaly occurs.

### 3.3 Database Role Separation & At-Rest Encryption Architecture

#### A. Database Role Separation
- **`thinkbuddy_api`:** Role used by API web servers. Granted `SELECT, INSERT, UPDATE, DELETE` across tables, but explicitly `REVOKE ALL ON question_keys`. Permitted to read questions exclusively via `v_questions_public`.
- **`thinkbuddy_grading`:** Role used exclusively by background grading workers. Authorized to query `question_keys`.
- **Verified in CI:** `test_database_role_separation_and_column_encryption` establishes connection as `thinkbuddy_api`:
  - `SELECT count(*) FROM v_questions_public` $\to$ **SUCCESS** (returns count).
  - `SELECT count(*) FROM question_keys` $\to$ **PERMISSION DENIED** (`sqlalchemy.exc.ProgrammingError`).

#### B. Encryption at Rest Statement (Beta vs. Production)
- **Beta Environment:**
  - Underlying database volume is encrypted at the block level using AWS EBS AES-256 (KMS) or Linux LUKS full-disk encryption.
  - Sensitive columns (`question_keys.answer_key`, `rubric`, `explanation`) are encrypted at the application layer via AES-256-GCM (`core/quiz/crypto.py`) using `QUESTION_KEY_ENCRYPTION_KEY`.
- **Production Environment:**
  - Encryption keys are retrieved dynamically at worker bootstrap from a dedicated Secrets Manager (AWS Secrets Manager / GCP Secret Manager / HashiCorp Vault) with automatic key rotation and strict IAM least-privilege policies.

### 3.4 Scaled Anomaly Rules & Parent "Mark as Allowed" Flow
- **Formula for Minimum Answer Time:**
  - $\text{Time}_{\text{mcq}} = \text{clamp}(1500, 6000, 1200 + 20 \times \text{len}(\text{stem})) \text{ ms}$
  - $\text{Time}_{\text{short}} = \text{clamp}(2500, 8000, 2000 + 25 \times \text{len}(\text{stem})) \text{ ms}$
  - $\text{Time}_{\text{broad}} = \text{clamp}(6000, 20000, 5000 + 30 \times \text{len}(\text{stem})) \text{ ms}$
- **Two-Signal Rule for Invalidation:** A single rapid answer or focus event pauses the attempt or emits a warning. The state transition to `invalidated` strictly requires $\ge 2$ distinct anomaly signals (e.g., `time_too_fast` + `rapid_answer_after_focus_loss`).
- **Parent Override:**
  - Route: `POST /v1/attempts/{id}/allow`.
  - Enforces linked parent authorization (unlinked parent or student receives 403 `FORBIDDEN`).
  - Restores attempt state to `active` (or `submitted` if time elapsed), sets integrity score to 1.0, records a `parent_override` event, and logs an immutable `AuditLog` entry with `action="quiz_attempt_allowed"`.

### 3.5 Expiry Worker Concurrency & Idempotency
- **Worker Concurrency:**
  ```python
  stmt = (
      select(QuizAttempt)
      .where(
          QuizAttempt.submitted_at.is_(None),
          QuizAttempt.deadline_at <= now,
          QuizAttempt.state.in_(OPEN_ATTEMPT_STATES),
      )
      .with_for_update(skip_locked=True)
  )
  ```
  `skip_locked=True` ensures multiple worker replicas safely process distinct attempts without blocking or deadlocks.
- **Signal Idempotency:** `QuizGradingService.finalize_and_emit_signals` verifies existing signals on `(source, ref_id)` before writing to `learning_signals`, guaranteeing zero duplicate signals even during concurrent worker/client finalization.
- **Schedule:** Celery Beat runs `auto_submit_expired_attempts` every 30 seconds.

### 3.6 Gateway Isolation & Signed Internal Service Tokens
- **Public Edge Gateway:**
  - Intercepts `/internal/*` and `/v1/internal/*` before routing and returns HTTP 404 `NOT_FOUND`.
- **Inter-Service Authentication:**
  - Internal calls between gateway/chat and core use short-lived HS256 JWTs signed with `INTERNAL_SERVICE_SECRET`.
  - Claims require `iss="thinkbuddy-gateway"`, `aud="thinkbuddy-core"`, `exp`, and `role="internal_service"`.
  - Core validates signatures, expiration, and audience via `require_internal_service_token`.

---

## 4. Test Suite Execution Results

All 134 automated unit, integration, and security tests pass:

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.0, pluggy-1.6.0
rootdir: E:\ThinkBuddy Arc
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.13.0, hypothesis-6.170.8, jaxtyping-0.3.11, platformdirs-4.13.5, asyncio-1.4.0, cov-7.1.0
collected 134 items

tests\test_compose_integration.py ....                                   [  2%]
tests\test_core_health.py .....                                          [  6%]
tests\test_gateway_health.py .....                                       [ 10%]
tests\test_logging_security.py ..                                        [ 11%]
tests\test_openapi_export.py .                                           [ 12%]
tests\test_p01_auth_family.py ..............                             [ 23%]
tests\test_p02_curriculum_rag.py .........                               [ 29%]
tests\test_p03_golden_plans.py ....                                      [ 32%]
tests\test_p03_planner.py .................                              [ 45%]
tests\test_p03_planner_v2.py .....................                       [ 61%]
tests\test_p04_secure_quiz.py ..........................                 [ 80%]
tests\test_p06a_ai_planner.py ..........................                 [100%]

====================== 134 passed, 8 warnings in 10.44s =======================
```

All 26 specific P04 security and hardening test cases pass:
1. `test_zero_answer_key_leakage_during_active_quiz`
2. `test_server_deadline_and_clock_tampering`
3. `test_token_and_nonce_replay_protection`
4. `test_randomization_and_variant_deduplication`
5. `test_web_platform_cannot_start_assessed_attempt`
6. `test_review_route_strictly_protected_until_submit`
7. `test_chat_lockout_during_active_assessed_quiz`
8. `test_integrity_events_and_invalidation`
9. `test_one_active_assessed_attempt_limit`
10. `test_auto_grading_and_learning_signals_emission`
11. `test_admin_question_bank_and_jsonl_import`
12. `test_pool_separation_and_seen_question_exclusion`
13. `test_concurrency_database_constraints_one_active_attempt_and_one_answer`
14. `test_scheduled_job_auto_submits_expired_attempts`
15. `test_device_integrity_attestation_and_anomaly_detection`
16. `test_internal_is_assessed_attempt_active_endpoint`
17. `test_isolation_cross_student_and_parent_access`
18. `test_bangla_normalization_and_accepted_answers`
19. `test_rate_limits_on_attempt_start_and_answer`
20. `test_open_attempt_states_unique_index_and_lockouts`
21. `test_play_integrity_verification_and_low_trust`
22. `test_scaled_too_fast_rule_multi_signal_and_parent_allow`
23. `test_database_role_separation_and_column_encryption`
24. `test_concurrent_submit_versus_expiry_and_worker_schedule`
25. `test_exhausted_assessed_pool_fallback_lru`
26. `test_gateway_never_proxies_internal_and_signed_jwt_service_token`

---

## 5. Conclusion & Review Readiness

All conditional acceptance requirements for Milestone P04 are fully implemented, verified, and tested against live PostgreSQL and Redis services. Database role boundaries are active, AES-256-GCM column encryption protects answer keys at rest, server-side Play Integrity tokens are cryptographically verified, anomaly rules are scaled by stem length with parent override audit logging, and internal routes are isolated behind signed JWT tokens.

Antigravity stops here for review on branch `feat/P04_secure_quiz` prior to Milestone P05.
