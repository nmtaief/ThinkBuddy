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
- `GET /students/{id}/ai-suggestions` – list pending AI planner priority suggestions for student.
- `POST /students/{id}/ai-suggestions/{suggestion_id}/approve` – parent approves AI suggestion, updating settings and regenerating plan (enforces Rule V09 locked fields).
- `POST /students/{id}/ai-suggestions/{suggestion_id}/reject` – parent rejects AI suggestion.
- `POST /students/{id}/ai-adjustments/{adjustment_id}/undo` – parent one-tap undo to revert an auto-applied minute or priority adjustment and restore previous settings. Enforces optimistic concurrency via `expected_version` (409 on conflict), restricts undo execution strictly to linked parents, and clamps restored values to class band limits.
- **Auto-Mode Numeric Caps & Safety Ceilings:**
  - Total daily minutes are strictly bounded by parent limits and class band recommended ceilings (`6-8`: 120m, `9-10`: 180m, `11-12`: 240m; absolute minimum 15m). Auto mode can never exceed these ceilings.
  - Rate of change limit: adjustments move at most 1 priority level step per cycle (`normal` ↔ `main` ↔ `difficult`) and at most ±20% daily study minutes per cycle.

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
- `GET /admin/ai-planner/status` – operational status of AI Planner (kill switch, circuit breaker state, rollout class bands).
- `POST /admin/ai-planner/circuit-breaker/reset` – force reset AI Planner circuit breaker to CLOSED.
- `PUT /admin/ai-planner/config` – update AI Planner kill switch and rollout class bands.
- `GET /admin/ai-planner/shadow-metrics` – get aggregate shadow-mode comparison metrics and latest run logs.
- `DELETE /admin/ai-planner/shadow-metrics/retention?retention_days=30` – purge shadow run records older than retention threshold (default 30 days) from dedicated `ai_planner_shadow_runs` table. Scheduled daily background task ensures durable retention compliance.

### Quiz & Assessments (P04)
- `POST /students/{id}/quizzes` – create quiz definition for student (student, linked parent, or admin).
- `POST /quizzes/{id}/attempts/create` – create attempt in state `created` with short 5-minute expiry; generates a random single-use server nonce (stored hashed on server) and returns `attempt_id`, `state="created"`, `nonce`, `deadline_at` for client to request Play Integrity attestation.
- `POST /attempts/{id}/attest` – attest and activate a `created` attempt using Play Integrity token bound to the random single-use server nonce; transitions state from `created` to `active`, consumes the nonce, enforces device downgrade protection (a device that has presented a valid token cannot later downgrade to `unsupported`), and returns `attempt_id`, `deadline_at`, `attempt_token`, `current_item`.
- `POST /quizzes/{id}/attempts` – start attempt directly or activate a `created` attempt; returns `attempt_id`, `deadline_at`, `attempt_token`, `current_item` with opaque options and per-item nonce.
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
- `POST /chat/sessions` – create chat session (student only; locked during active assessed quiz with 403 `QUIZ_IN_PROGRESS_CHAT_LOCKED`).
- `GET /chat/sessions` – list active chat sessions for the authenticated student.
- `GET /chat/sessions/{id}` – get chat session details and message history with authoritative citations (ownership verified; 404 if not owned).
- `POST /chat/sessions/{id}/messages` – send prompt to AI tutor.
  - Response Mode: SSE stream if `Accept: text/event-stream` or `stream: true`; full JSON fallback (`ChatMessageResponse`) if `stream: false`.
  - Safeguards & Integrity:
    - Active Assessed Quiz Lockout: Refused with 403 `QUIZ_IN_PROGRESS_CHAT_LOCKED` across all open attempt states (`created`, `active`, `warned`, `paused`); logs `chat_attempt` telemetry infraction.
    - Daily Quota: Enforced against family entitlement (free plan: 20 messages/day, premium: 100 messages/day). Returns 429 `DAILY_CHAT_QUOTA_EXCEEDED` when reached.
    - Rate Limits: 20 requests / min per authenticated student plus 60 requests / min per-IP ceiling.
    - Delimiter Injection Defense: Prompt assembly applies NFKC Unicode normalization and neutralizes spaced, case-insensitive, fullwidth, and lookalike XML/bracket delimiters (`< / context >`, `‹system›`, `＜context＞`) in both user prompts and textbook chunks.
  - Grounded Citations (Rule 7 & 8): Every assistant answer carrying facts terminates with citations (`book_title`, `chapter_title`, `chapter_number`, `printed_page`, `chunk_id`). Authoritative printed page number is strictly rendered to users; internal PDF page index is kept separate.
  - Low Confidence Fallback: If retrieval confidence is below threshold (< 0.45), returns explicit "not found in your textbook" message without guessing or hallucinating citations.

### Progress, Mastery & Spaced Revision (P06)
- `GET /progress/summary?student_id=` – overall mastery score, confidence, and active streak for student or linked parent dashboard.
- `GET /progress/mastery?student_id=` – chapter-by-chapter mastery scores with confidence and parent-safe statuses (`mastered`, `needs_practice`, `not_enough_data`).
- `GET /progress/weak-points?student_id=` – topics needing practice and suggested intervention review types (Requirement 7: strictly parent-safe wording; never labeled "weak").
- `GET /progress/history?student_id=&days=30` – historical study progress, minutes studied, tasks completed, and quiz averages over lookback period.
- `GET /revision/daily?student_id=` – 5-box Leitner spaced repetition items due today, ordered by box priority and capped by available daily revision minutes. Excludes subjects in blackout or past exam dates.
- `POST /revision/{id}/review` – submit revision review result (`result="correct"` promotes to `box + 1`, `result="incorrect"` demotes to `box = 1`).
- `POST /internal/jobs/daily-composition?student_id=` – internal worker endpoint triggering daily adaptive composition and planner regeneration under student advisory lock.
- `POST /internal/jobs/three-day-review?student_id=` – internal worker endpoint triggering 3-day review cycle, assembling P04 review quiz, and regenerating planner.

### Parent & Family (P07)
- `GET /parents/me/students` – list linked children for authenticated parent.
- `GET /parents/me/dashboard` – multi-student overview for the authenticated parent.
- `GET /parents/me/students/{student_id}/dashboard` – consolidated parent view for a linked student (progress, mastery, revision, exams, AI suggestions, recent auto-adjustments, and topic-level AI chat summary; Rule 9 linkage enforced; strictly non-labeling and bilingual).
- `GET /parents/{parent_id}/dashboard` & `GET /parents/{parent_id}/students/{student_id}/dashboard` – explicit parent ID paths. If `{parent_id}` is not `"me"` and does not match the authenticated parent ID, strictly rejected with HTTP 403 Forbidden.
- `POST /parents/me/students/{student_id}/change-requests/{request_id}/approve` – linked parent approves student change request (with optional `comment`); applies changes to study settings/setup, regenerates unified schedule, invalidates cached dashboard, and dispatches in-app and push notifications to student.
- `POST /parents/me/students/{student_id}/change-requests/{request_id}/decline` – linked parent declines student change request (with optional `comment`); records immutable audit log, invalidates cached dashboard, and notifies student.
- `POST /parents/{parent_id}/students/{student_id}/change-requests/{request_id}/approve` & `decline` – explicit parent ID variants with strict ID mismatch checks (HTTP 403).
- **Privacy & Non-Labeling Guarantees:**
  - Topic-Level AI Chat Summary (Rule 15 & Deliverable 12): Parents never receive raw student chat messages or prompt transcripts. Dashboard returns `chat_topics` aggregating chapter/topic activity and query counts from curriculum citations.
  - Approved Reason Templates: 15 approved localized templates map all planner reason codes into constructive growth-oriented language (Bangla & English). Fallback sanitizer ensures zero deficit labeling.
  - Performance & Caching: Dashboard responses cached in Redis (`thinkbuddy:dashboard:{student_id}`, 60s TTL) with deterministic invalidation on changes, bounded query counts.

### Notifications & Push Delivery (P07)
- `GET /notifications?limit=50&offset=0&unread_only=false` – list paginated notifications for authenticated user with unread counts (Rule 9 ownership enforced).
- `POST /notifications/{id}/read` – mark single notification as read (strictly checks `notification.user_id == current_user.id`; returns 403 Forbidden on ownership mismatch).
- `POST /notifications/read-all` – mark all notifications for authenticated user as read.
- `GET /notifications/preferences` – get authenticated user's notification channels and quiet hours configuration.
- `PUT /notifications/preferences` – update authenticated user's notification channels and quiet hours.
- `POST /devices` – register client device with FCM push token, platform, app version, and form factor.
- `PATCH /devices/{id}` – update client device push token or active status.
- **Delivery System Architecture:**
  - Pluggable Sender (`NotificationSender`): Decoupled interface with production `FirebaseNotificationSender` and local `FakeNotificationSender`. Strict allowlist guards fake sender: raises `RuntimeError` if executed in `production`, `staging`, or `prod`.
  - Generic Push Text: Push alerts carry generic, privacy-preserving messages (e.g. "Study reminder", "Quiz ready"), while sensitive academic details and rationales remain exclusively within the authenticated app.
  - Asia/Dhaka Quiet Hours: Quiet hours evaluated in `Asia/Dhaka` timezone (default 22:00–07:00, handling overnight spans); push deliveries during quiet hours are suppressed with `suppressed_quiet_hours`.
  - Coalescing: Push notifications with identical trigger types for the same user within 30 minutes are coalesced (`suppressed_coalesced`).
  - Per-User Daily Caps: Maximum of 5 push notifications per user per calendar day in `Asia/Dhaka` (`suppressed_daily_cap`).
  - Delivery Auditing: Every delivery attempt (in-app and push) is recorded in the `notification_deliveries` table with channel, status, provider message ID, and suppression reasons.
  - System Triggers: `daily_reminder`, `task_missed`, `quiz_ready`, `plan_changed`, `integrity_flag`, and scheduled bilingual `weekly_parent_summary`.

### Privacy, Parental Consent & Data Lifecycle (P07b)
- `POST /v1/auth/reauthenticate` – dedicated re-authentication endpoint validating fresh third-party provider credentials (`auth_time` within 300 seconds / 5 minutes). Issues a short-lived signed JWT re-authentication token (`reauth_token`, TTL 10 minutes). Required for sensitive lifecycle operations: account/family deletion, family data export, and parental consent withdrawal.
- `POST /v1/parents/consent` – record verified parental consent (version, terms hash, timestamp, client IP, user agent). Required before any minor child profile or study data may be processed. Returns `{ "status": "granted", "version": "1.0", "terms_hash": "...", "consented_at": "..." }`.
- `GET /v1/parents/consent` – fetch current recorded parental consent status and version. Detects if terms text has changed by comparing `terms_hash` against `CURRENT_CONSENT_TEXT_HASH`; returns `reconsent_required: true` when terms update, which blocks child data processing until affirmative re-consent is granted.
- `POST /v1/parents/consent/withdraw` – withdraw parental consent. Requires `X-Reauth-Token`. Suspends all minor child study data processing.
- `GET /v1/parents/me/export` & `POST /v1/parents/me/export` – trigger and retrieve family data export. Enforces:
  1. Authorization: Restricted to authenticated parent/family guardian (Rule 9).
  2. Re-authentication: Requires valid `X-Reauth-Token`.
  3. Rate Limiting: Strictly limited to 1 export request per parent per 24 hours (HTTP 429 `EXPORT_RATE_LIMITED`).
  4. Short-Lived Signed Download Link: Generates a signed download URL (`download_url`, TTL 15 minutes) for secure delivery.
  5. Retention: Export archives retained for 7 days before automated cleanup.
  6. Non-Leakage (Rule 15 & Decision 9): Raw chat messages, prompts, and tokens are strictly excluded. Student chat activity is exported as curriculum topic-level summaries only (book, chapter, message count, timestamp).
- `GET /v1/parents/me/export/{export_id}/download` – download family export JSON archive using signed download token. Enforces Rule 9 cross-parent isolation: Parent B requesting Parent A's export gets HTTP 403 `FORBIDDEN_EXPORT_ACCESS`.
- `POST /v1/users/me/delete` – schedule self account deletion. Requires `X-Reauth-Token`. Enters 14-day grace period with scheduled purge timestamp.
- `POST /v1/users/me/cancel-deletion` – cancel pending account deletion within the 14-day grace period, restoring active status.
- `POST /v1/families/{family_id}/delete` – schedule complete family deletion. Enforces:
  1. Role check: Students are strictly forbidden from deleting a family (HTTP 403 `STUDENT_CANNOT_DELETE_FAMILY`).
  2. Ownership check: Only the family owner parent (`owner_parent_id`) may schedule family deletion (HTTP 403 `ONLY_FAMILY_OWNER_CAN_DELETE`).
  3. Re-authentication check: Requires valid `X-Reauth-Token`.
  4. Grace period & processing suspension: 14-day grace period applied across all family members. During the grace period, AI chat is blocked (HTTP 403 `ACCOUNT_PENDING_DELETION`), push notifications are suppressed (`suppressed_pending_deletion`), and study plan regeneration is stopped.
  5. Member Notification: Immediately dispatches `family_deletion_scheduled` push notifications to all other members in the family.
- `POST /v1/families/{family_id}/cancel-deletion` – cancel pending family deletion within the 14-day grace period. Any parent belonging to the family can cancel, which restores all family members to `active` status and sends notification alerts.
- `POST /admin/privacy/purge` – execute data purge job for records past their grace period (`scheduled_purge_at <= now`):
  1. Revokes all active user sessions (`Session`).
  2. Revokes all push tokens and removes device bindings (`Device`).
  3. Purges Redis cache keys for student dashboards, schedules, and sessions.
  4. Deletes personal academic data (profiles, setups, tasks, plans, attempts, broad answers, citations, chat, invitations).
  5. Deletes broad answer images and uploaded media from object storage (S3/MinIO).
  6. Purges notifications, delivery logs, learning signals, and AI planner shadow runs.
  7. Anonymizes compliance audit records (`AuditLog`): nulls `actor_id` and redacts personal PII while retaining audit action types and timestamps for statutory legal compliance.
  8. Idempotency: Executes per-user in isolated nested transactions so failures in one account do not abort batch processing.
  9. Audited: Admin trigger is audited with `AuditLog(action="privacy.purge_triggered")`.
- **Database Backup Retention Policy**: Encrypted disaster-recovery database snapshots (PostgreSQL full dumps and WAL archives) are stored in an encrypted, access-restricted bucket with automated object lifecycle rules enforcing permanent deletion after exactly 30 days. Personal data purged from the live database is therefore guaranteed to be completely expunged from all disaster recovery backups within 30 days.

### Teacher (flagged off in beta)
- `GET /teacher/queue`, `POST /teacher/submissions/{id}/review`, `POST /teacher/topics/flag`.

### Uploads
- `POST /uploads/sign` – signed URL for answer photos; type/size limits enforced.

## 3. SSE event types (chat)
1. `event: meta` – JSON payload with `message_id` and `retrieval_confidence` (0.0 to 1.0).
2. `event: token` – incremental text chunk delta (`{"delta": "..."}`).
3. `event: citation` – authoritative curriculum citation for each used chunk (`{"chunk_id": "...", "book_title": "...", "chapter_title": "...", "chapter_number": ..., "printed_page": ...}`).
4. `event: done` – completion metrics (`{"tokens_in": ..., "tokens_out": ..., "latency_ms": ...}`).
5. Heartbeat comment `: ping\n\n` emitted periodically (every 15s) on long pauses.
Clients must tolerate unknown events. Disconnecting the client terminates token generation immediately.

## 4. Authorization rules
Every route declares: allowed roles, ownership rule (self / linked parent / assigned teacher), and entitlement requirement. Missing declaration fails CI.

## 5. Multi-platform rules
- No field is Android-specific. Platform-dependent behavior is expressed as data in `/client/config`.
- Payload content uses structured blocks: `text`, `math` (LaTeX/MathML string), `image`, `table`, `citation`. Clients render natively.
- Image variants are provided by size class (`sm`, `md`, `lg`) so tablets get larger images and phones save data.
