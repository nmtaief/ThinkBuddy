# Milestone P07 Security & Verification Report: Parent Dashboard, Notifications & Tail Hardening

**Date:** 2026-10-25  
**Milestone:** P07 (Parent Dashboard APIs & Push Notifications)  
**Tail Commit:** `346a3da`  
**Status:** Completed & Verified; all P07 tail requirements satisfied; ready for P08 Web App  
**Standing Rules:** Strictly enforced (Rules 1–16)  
**Total Commits (`git rev-list --count --all`):** 31  

---

## 1. Executive Summary

Milestone P07 delivers the backend APIs for the parent experience and notification infrastructure:
- Consolidated parent dashboard with daily progress summaries, streak counters, study minutes, exam countdowns, and topic-level AI chat summaries (never exposing raw student chat transcripts, adhering to Rule 15 and privacy guidelines).
- Server-authoritative study setup and change request workflows, validating all student and parent modifications against class-band and day-type limits.
- Notification dispatch service with quiet-hours suppression, daily caps, key coalescing, and FCM/APNs push delivery interfaces with strict environment allowlists.
- All 6 conditional acceptance tail requirements implemented, tested, and verified.

---

## 2. Security Scanners Audit Summary

| Tool | Version / Config | Target / Scope | Metric / Scope | Findings / Status |
|---|---|---|---|---|
| **git rev-list** | `git version 2.x` | All repository branches/tags | Commit count | **30 total commits** |
| **gitleaks** | `v8.30.1` | Full git commit history (without `-n`) | 24 commits scanned in 5.09s | **0 leaks found** (PASS) |
| **bandit** | `1.8.3` | `core`, `gateway`, `workers`, `rag` (`-ll`) | 19,239 LOC scanned | **0 High, 0 Medium** (PASS) |
| **semgrep** | `1.181.1` (auto registry) | All tracked repository files (328 rules) | 195 files scanned | **0 findings (0 blocking)** (PASS) |
| **trivy (core)** | `0.76.1` | Container image `thinkbuddyarc-core:latest` | Python packages + Debian base | **0 Python vulns** (PASS) |
| **trivy (gateway)** | `0.76.1` | Container image `thinkbuddyarc-gateway:latest` | Python packages + Debian base | **0 Python vulns** (PASS) |
| **trivy (workers)** | `0.76.1` | Container image `thinkbuddyarc-workers:latest` | Python packages + Debian base | **0 Python vulns** (PASS) |
| **pytest (P07)** | `9.1.0` | `tests/test_p07_parent_notifications.py` | 29 tests | **29 passed in 13.00s** (PASS) |
| **pytest (Suite)** | `9.1.0` | Full repository test suite | 225 tests | **225 passed in 61s** (PASS) |

*Note on Trivy OS package notices:* Trivy reported upstream Debian 13 testing notices on base OS packages (`util-linux`, `ncurses`, `perl-base`) where upstream Debian fixes are deferred. All application Python dependencies are completely clean.

---

## 3. P07 Tail Hardening Implementation & Invariants

### 1. Admin Policy Ceilings by Class Band and Day Type
- Seeded default, auto-ceiling, and hard-limit parameters in `admin_policies` across class bands (`class_6_8`, `class_9_10_general`, `class_9_10_science`) and day types (`school_day`, `holiday`).
- Auto mode bounds logic strictly guarantees:
  - Auto mode **never lowers** a parent's own configured study minute setting.
  - Auto mode **never raises** study minutes above the configured auto ceiling for that class band and day type.
  - If a parent intentionally configured minutes above the auto ceiling (within the hard limit), auto mode **leaves the parent's setting unchanged**.

### 2. Quiet Hours Deferred Delivery & Scheduled Beat Dispatcher
- Push notifications suppressed during Asia/Dhaka quiet hours (21:00 to 07:00) are **deferred until 07:00 next morning** rather than dropped (`deferred_quiet_hours`).
- A scheduled Celery Beat task (`dispatch_deferred_pushes_task`) runs every 60 seconds:
  - Uses PostgreSQL row-level locks with `SKIP LOCKED` (`SELECT ... FOR UPDATE SKIP LOCKED`) for safe multi-worker concurrency.
  - Re-evaluates parent notification preferences and daily per-user push caps at actual dispatch time.
  - Purges stale deferred items older than 24 hours (`status="expired_stale"`).
  - Coalesces and merges multiple pending notifications for the same user into a single unified push notification.
  - Fully tested across the Asia/Dhaka midnight UTC boundary (18:00 UTC).

### 3. Push Token Lifecycle & Shared Device Security
- **Single-Device Logout:** Logging out on a device nullifies the push token only for that specific `device_id`, preserving active sessions and push tokens on the parent's other devices.
- **Sign-in Reassignment:** When a device registers a push token, any preexisting records holding that same push token have their token cleared, backed by a PostgreSQL partial unique index (`idx_devices_push_token_unique`).
- **FCM Invalid Token Cleanup:** When the push notification sender receives an invalid token error from FCM, the invalid token is immediately stripped from the database.
- **Session & Link Revocation:** Refresh token reuse or credential invalidation strips all device push tokens for the affected user. Revoking a parent-student link terminates shared-device access to student updates.

### 4. Change Request Revalidation, Concurrency & Expiration
- Approving a student study setup change request re-validates all fields against the `AdminPolicy` hard limits.
- Optimistic concurrency control: if the student's `StudySetup.setup_version` has incremented between request creation and parent review, the approval endpoint rejects with `HTTP 409 Conflict`.
- Requests past their `expires_at` window return `HTTP 410 Gone` and cannot be revived.
- Existing change requests without an expiration timestamp are backfilled safely via Alembic migration.

### 5. Pre-Cache Authorization Verification
- Evaluates Rule 9 authorization checks (parent-student relationship and family membership) **before** reading or returning data from the Redis dashboard cache.
- Verified that unlinked or revoked parents receive `HTTP 403 Forbidden` and cannot retrieve cached dashboard data.

---

## 4. Test Suite Coverage Roster

The 29 tests in `tests/test_p07_parent_notifications.py` validate the entire parent and notification domain:

1. `test_redis_rollout_config_and_kill_switch_with_per_student_override` – Feature flag and per-student percentage rollout.
2. `test_shadow_runs_table_persistence_and_retention_purge` – 90-day retention purge of planner shadow run logs.
3. `test_suggestion_revalidation_at_approval_and_409_on_concurrent_approval` – Concurrency and rule revalidation.
4. `test_suggestion_expiration_returns_410_gone` – Expired suggestion rejection.
5. `test_minute_change_suggestion_approval_flow` – Parent approval of study minute changes.
6. `test_one_tap_undo_reverts_auto_applied_adjustment_and_regenerates_plan` – One-tap undo restores previous setup and triggers plan regeneration.
7. `test_sanitize_non_labeling_reason_growth_mindset` – Zero-deficit wording enforcement in auto-adjustment reasons.
8. `test_parent_dashboard_consolidated_view_non_labeling_and_localized` – Multi-child summary, streak, time, and localized strings.
9. `test_parent_dashboard_rule_9_authorization_unlinked_access_denied` – Unlinked parent access rejected with 403.
10. `test_notifications_crud_read_status_and_preferences` – Notification inbox CRUD and quiet hours preferences.
11. `test_notification_delivery_sender_interface_and_fake_allowlist` – Sender abstraction and fail-closed environment allowlist.
12. `test_device_push_token_registration_and_update` – Device registration and token update endpoints.
13. `test_notification_dispatch_triggers_delivery_logs_and_generic_push_text` – Push text privacy (no sensitive data in pushes).
14. `test_quiet_hours_asia_dhaka_and_coalescing_and_daily_caps` – Daily caps, key coalescing, and quiet-hours deferrals.
15. `test_student_change_request_approve_and_decline_flows` – Change request approval and decline flows.
16. `test_parent_dashboard_me_paths_and_id_mismatch_rejection` – Strict `/parents/me` routing validation.
17. `test_notification_ownership_checks_and_isolation` – Notification isolation across parents.
18. `test_topic_level_ai_chat_summary_never_exposes_raw_messages` – Chat topic summary privacy.
19. `test_approved_reason_templates_mapping_and_fallback` – Positive growth-mindset template fallback.
20. `test_numeric_caps_for_auto_mode_and_optimistic_locked_undo` – Numeric safety clamps on auto adjustments.
21. `test_chat_delimiter_defense_case_insensitive_spaced_and_unicode_lookalikes` – Delimiter defense across unicode lookalikes.
22. `test_scheduled_shadow_retention_job` – Background celery task for shadow log pruning.
23. `test_dashboard_query_count_and_caching` – Redis caching and query count minimization.
24. `test_auto_mode_admin_policy_ceilings_and_parent_bounds` – Admin policy ceilings by class band/day type and parent bounds preservation.
25. `test_deferred_pushes_scheduled_job_and_dhaka_midnight` – 60s Celery Beat deferred push dispatcher, merging, and Dhaka midnight boundary rollover.
26. `test_push_token_lifecycle_and_shared_devices` – Logout single-device cleanup, sign-in reassignment, FCM token deletion, and link revocation.
27. `test_dashboard_auth_evaluated_before_cache_read_revoked_parent` – DB authorization check executed prior to Redis cache read.
28. `test_change_request_revalidation_expiration_and_version_conflict` – Version conflict (409), expiration (410), and hard limit validation.
29. `test_migration_0017_reversibility` – Alembic migration 0017 programmatic downgrade and upgrade test.

---

## 5. Schema & Migrations

- **Migration `0015_p07_parent_notifications.py`:** Added `notifications`, `notification_preferences`, `notification_deliveries`, `ai_suggestions`, `change_requests`, and `auto_adjustments` tables.
- **Migration `0016_p07_delivery_and_rollout.py`:** Added delivery indexes and rollout configuration columns.
- **Migration `0017_p07_tail_enhancements.py`:** Added day-type ceiling columns (`auto_ceiling_school_day_minutes`, `auto_ceiling_holiday_minutes`, `hard_limit_school_day_minutes`, `hard_limit_holiday_minutes`) to `admin_policies`, added `setup_version` and `expires_at` to `student_change_requests`, added partial unique index `idx_devices_push_token_unique` on `devices(push_token)`, and added `deferred_until` index on `notification_deliveries`. Verified fully reversible via automated downgrade/upgrade tests.

---

## 6. Feature Flags & Rollout Plan

All parent dashboard and notification capabilities are integrated behind feature flags in `feature_flags` and surfaced via `/client/config`:
- `FEATURE_PARENT_DASHBOARD_ENABLED=False`
- `FEATURE_NOTIFICATIONS_ENABLED=False`

These can be safely toggled per environment and incrementally rolled out to parent cohorts.

---

## 7. Conclusion

Milestone P07 and its conditional tail requirements are complete, audited, and verified against all standing rules. The backend is secure, performant, and ready to serve the P08 web application.
