# 04 – API Contract (v1)

Base: `https://api.thinkbuddy.<domain>/v1`. JSON over HTTPS. OpenAPI generated from code is the source of truth; this file defines conventions and the endpoint inventory.

## 1. Conventions
- **Auth:** `Authorization: Bearer <access_jwt>` (short-lived, ~15 min) + refresh token endpoint.
- **Client headers (required):** `X-Client-Platform`, `X-Client-Form-Factor`, `X-App-Version`, `X-Device-Id`; plus `Accept-Language` (`bn`, `en`).
- **Idempotency:** `Idempotency-Key` on all POST that create/submit.
- **Pagination:** cursor-based (`?cursor=&limit=`), response `{items, next_cursor}`.
- **Errors:** `{ "error": { "code": "QUIZ_EXPIRED", "message": "...", "request_id": "..." } }`. Codes are stable strings; messages are localized.
- **Time:** ISO-8601 UTC; clients localize. Server clock is authoritative.
- **Versioning:** breaking change → `/v2`. `min_supported_version` in client config lets you force upgrade.
- **Rate limits:** return `429` with `Retry-After`.

## 2. Endpoint inventory

### Client & config
- `GET /client/config` – flags, entitlements, min version, quiz security mode, layout hints, observance catalog, and planner defaults & limits (no admin internals).
- `POST /devices` / `PATCH /devices/{id}` – register push token, app version.

### Auth & identity
- `POST /auth/exchange` – exchange provider token for backend session.
- `POST /auth/refresh`, `POST /auth/logout`.
- `GET /me`.
- `POST /families`, `POST /families/{id}/students` (parent adds child).
- `POST /links/redeem` (student enters code), `POST /links/{id}/revoke`.

### Curriculum
- `GET /books?class_level=&subject=&medium=` – list textbooks with chapter counts.
- `GET /books/{id}` – get textbook details.
- `GET /books/{id}/chapters` – get ordered chapter list for textbook.
- `GET /chapters/{id}` – get chapter details with concepts and chunk count.

### Planning & Study Settings
- `GET /students/{id}/study-settings` – get resolved study settings, parent preferences, and admin policy constraints.
- `PUT /students/{id}/study-settings` – parent updates study settings (school_day_minutes, holiday_minutes, study window, unavailable blocks, blocked observances, coarse blackout dates, subject priorities) with optimistic locking (409) and limit clamping.
- `POST /students/{id}/study-settings/change-requests` – student proposes study settings adjustments.
- `PUT /students/{id}/study-setups/{subject}` – exam date, syllabus selection, chapter order (parent, with optimistic locking via `version`).
- `GET /students/{id}/study-setups` – list all study setups for a student.
- `POST /students/{id}/study-setups/{subject}/change-requests` (student submits change request for subject setup).
- `POST /students/{id}/generate-plan` – generate or recalculate unified schedule across all active setups.
- `PUT /students/{id}/daily-minutes` – parent updates legacy student-level daily minutes budget.
- `GET /students/{id}/plan?from=&to=` – days + tasks with day types (`school_day`, `holiday`, `blackout`, `exam_day`), coverage reports, and plan provenance (`provider`, `model_version`, `contract_version`, `settings_version`, `generation_reason`; see `docs/07_AI_PLANNER_API.md`).
- `GET /students/{id}/today` – home screen payload (tasks, revision, streak, exam countdown, remaining budget, student timezone, and `plan_provenance` with parent-facing rationale).
- `PATCH /tasks/{id}` – status update (student only; parents read-only; ownership verified).

### Admin Governance & Configuration (`/admin/*`, role: admin)
- `GET /admin/policies` – list admin policies across class bands and groups.
- `POST /admin/policies` – create draft policy for class band (`6-8`, `9-10`, `11-12`) and group.
- `PUT /admin/policies/{id}` – update draft policy limits and planner parameters (audit logged).
- `GET /admin/policies/{id}/preview` – preview affected students and active plans before publishing.
- `POST /admin/policies/{id}/publish` – publish policy; queues throttled idempotent regeneration for affected students.
- `GET /admin/holidays` – list holiday calendar entries.
- `POST /admin/holidays` – create draft holiday (audit logged).
- `POST /admin/holidays/import` – bulk import unverified draft holidays from JSON file (audit logged).
- `PUT /admin/holidays/{id}` – update holiday (dates, type, blackout, verification, audit logged).
- `GET /admin/holidays/{id}/preview` – preview affected plans and students for holiday date range.
- `POST /admin/holidays/{id}/publish` – publish holiday calendar change; queues throttled idempotent regeneration.
- `GET /admin/observances` – list observance catalog entries.

### Quiz & Assessments (P04)
- `POST /students/{id}/quizzes` – create quiz definition for student (student, linked parent, or admin).
- `POST /quizzes/{id}/attempts/create` – create attempt in state `created` with short 5-minute expiry; returns `attempt_id`, `state="created"`, `nonce` (bound to `attempt_id`) for client to request Play Integrity attestation.
- `POST /quizzes/{id}/attempts` – start attempt or activate a `created` attempt; returns `attempt_id`, `deadline_at`, `attempt_token`, `current_item` with opaque options and per-item nonce.
  - Restrictions: Web platform practice-only (403 `WEB_PLATFORM_PRACTICE_ONLY`); one-active-assessed-attempt limit across all open states (`created`, `active`, `warned`, `paused`) via 409 `ACTIVE_ATTEMPT_ALREADY_EXISTS`.
  - Device Integrity: Evaluates Play Integrity tokens with package name (`com.thinkbuddy.app`), nonce bound to `attempt_id`, and freshness (< 5 min) checks; in production, client-reported verdict fields are rejected in favor of cryptographic verification; unverified or self-declared-provider devices receive reduced mastery weight (0.7x) and an `unverified_device` flag.
  - Dual Rate limits: 5 requests / min per authenticated user plus higher 25 requests / min per-IP ceiling.
- `POST /attempts/{id}/items/{position}/answer` – submit one answer sequentially; returns `next_item` and `has_more`.
  - In assessed mode, correctness feedback is strictly withheld until submit (`is_correct: null`).
  - Server-side anomaly detection: single anomaly logs a warning (state enters `warned`); pausing requires $\ge 2$ signals or 1 severe signal (`screenshot_attempt`, `chat_attempt`, `overlay`) and auto-resumes after 60s; deadline strictly never extends on pause. Invalidation strictly requires $\ge 2$ distinct anomaly signals.
  - Errors: 401 `INVALID_ATTEMPT_TOKEN`, 403 `ATTEMPT_PAUSED`, 409 `INVALID_ITEM_NONCE`, 409 `ITEM_ALREADY_ANSWERED`, 410 `ATTEMPT_EXPIRED`.
  - Dual Rate limits: 15 requests / min per authenticated user plus 60 requests / min per-IP ceiling.
- `POST /attempts/{id}/events` – record anti-cheat telemetry events (`app_background`, `focus_lost`, `screenshot_attempt`, `multi_window`, `overlay`, `clipboard`). Returns updated `integrity_score` and `state`.
- `POST /attempts/{id}/allow` – linked parent or admin override to allow an attempt that was warned, paused, or invalidated (verifies linked parent ownership; unpauses attempt, resets state, restores score, and records immutable `AuditLog` entry). Expired attempts cannot be revived (409 `CANNOT_REVIVE_EXPIRED_ATTEMPT`).
- `POST /attempts/{id}/submit` – finalize attempt; evaluates score, updates attempt state, and emits `learning_signals` (`quiz_wrong`, `quiz_slow`) idempotently via unique constraint with `ON CONFLICT DO NOTHING`.
- `GET /attempts/{id}/review` – get attempt review with correct answers, explanations, and `unverified_device` status.
  - Strictly blocked with 403 `ATTEMPT_NOT_SUBMITTED` while attempt is active/unsubmitted!
- `GET /internal/quiz/students/{id}/active-attempt` – internal service route checking whether student has an open assessed attempt (`created`, `active`, `warned`, `paused`). Strictly rejected by gateway with 404; requires signed HS256 JWT service token.

### Admin Question Bank (`/admin/questions*`, role: admin)
- `POST /admin/questions` – create question item and isolated question key in `question_keys` table (zero leak to student routes, audit logged).
- `POST /admin/questions/import` – bulk import questions and isolated question keys from JSONL (audit logged).
- `GET /admin/questions?chapter_id=&review_status=` – list question bank items.

### Broad questions
- `POST /attempt-items/{id}/broad` (text or image upload refs), `GET /submissions/{id}`.

### Chat (RAG)
- `POST /chat/sessions`, `GET /chat/sessions`, `GET /chat/sessions/{id}`.
- `POST /chat/sessions/{id}/messages` – SSE if `Accept: text/event-stream`, else JSON.

### Progress & parent
- `GET /students/{id}/progress/summary`, `/progress/mastery`, `/progress/weak-points`, `/progress/history`.
- `GET /parents/me/students` – list of linked children.
- `GET/PATCH /notifications/settings`.

### Teacher (flagged off in beta)
- `GET /teacher/queue`, `POST /teacher/submissions/{id}/review`, `POST /teacher/topics/flag`.

### Uploads
- `POST /uploads/sign` – signed URL for answer photos; type/size limits enforced.

## 3. SSE event types (chat)
`event: meta` (message id, retrieval confidence) → `event: token` (text delta) → `event: citation` (book, chapter, printed page, chunk id) → `event: done` (usage) | `event: error`.
Clients must tolerate unknown events. Heartbeat comment every 15 s.

## 4. Authorization rules
Every route declares: allowed roles, ownership rule (self / linked parent / assigned teacher), and entitlement requirement. Missing declaration fails CI.

## 5. Multi-platform rules
- No field is Android-specific. Platform-dependent behavior is expressed as data in `/client/config`.
- Payload content uses structured blocks: `text`, `math` (LaTeX/MathML string), `image`, `table`, `citation`. Clients render natively.
- Image variants are provided by size class (`sm`, `md`, `lg`) so tablets get larger images and phones save data.
