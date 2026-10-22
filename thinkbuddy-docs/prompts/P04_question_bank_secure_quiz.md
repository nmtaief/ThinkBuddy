# P04 – Question Bank & Secure Quiz Engine

**Read first:** `AGENT_RULES.md`, `docs/05_SECURE_QUIZ.md` (all), `docs/03_DATA_MODEL.md` (§4), `docs/04_API_CONTRACT.md` (Quiz), `docs/06_ADAPTIVE_ENGINE.md` (§6).

## Task
Implement the question bank and a server-authoritative quiz engine.

## Deliverables
1. Question bank CRUD for admins (curated import from JSONL), with `variant_group_id`, `origin`, `review_status`. Answer keys in a **separate table** accessible only by the grading service.
2. Quiz builder service: pulls questions by chapter/concept/difficulty, supports variants and randomization per student.
3. Attempt state machine with server deadlines, per-item nonces, `attempt_token`, one-active-assessed-attempt rule.
4. Endpoints: start attempt, answer item, events, submit, review (after submit only).
5. Grading: MCQ/short auto-grade; broad answers queued for AI rubric feedback (stub calling the LLM module later).
6. Integrity: event ingestion, `integrity_score`, configurable policy (warn → pause → invalidate) read from feature flags/config.
7. Chat block during active assessed attempts (provide an `is_assessed_attempt_active(student)` service for the gateway).
8. Integrity verdict handling at start: accept a Play Integrity / App Attest verdict field and enforce policy (verifier can be a pluggable stub in beta).
9. Write `learning_signals` on grading (hand-off to P06).

## Acceptance (automated)
- **Leakage test:** during an active attempt, no student-accessible endpoint returns answer keys, explanations, or rubrics.
- Client clock changes do not extend the deadline; late submissions are rejected or auto-expired.
- Replayed tokens/nonces fail.
- Two students receive different orders/variants.
- Web platform cannot start an assessed attempt.
- Review endpoint returns 403 before submission.
