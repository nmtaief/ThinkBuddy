# Milestone P08 Security & Architecture Report: Responsive Web Application & BFF Security Isolation

**Date:** 2026-10-26  
**Milestone:** P08 (Web Client & Platform Adaptation)  
**Branch:** `feat/P08_web_app` (Clean `main` preserved at P07 `4aafb06`)  
**Status:** Completed, Verified, and Audited  
**Standing Rules:** Strictly enforced (Rules 1–18, including Rule 17 Token Isolation and Rule 18 Platform Assessment Isolation)  
**Commit Count Reconciliation:**  
- Linear active branch commits: 27 commits prior to P08, 3 commits on `feat/P08_web_app`.
- `git rev-list --count --all`: 34 commits (traversing all git references, merge bases, and orphaned commits across branches).

---

## 1. Executive Summary & Deliverables Mapping

Milestone P08 delivers a production-grade, accessible, and responsive Next.js 16 (App Router, React 19, TypeScript) web application serving Students and Parents across phone, tablet, and desktop viewports. 

All 13 deliverables from `thinkbuddy-docs/prompts/P08_web_app.md` have been fully implemented, hardened, and verified:

### 13 Deliverables Mapping Table

| Deliverable # | Name & Description | Status | Verification & Implementation Evidence |
|---|---|---|---|
| **1** | **Project and Tokens:** `/web` app, `/design/tokens.json`, API client, lint, typecheck, CI, Dockerfile, `.env.example`. | **DONE** | Tokens in `web/src/design/tokens.json`, `npm run lint`, `npm run build` (TypeScript clean), Dockerfile with multi-stage build, committed lockfile. |
| **2** | **Session Layer:** Redis-backed session store, idle (30m) & absolute (7d) timeouts, session fixation rotation on login, token-reuse revocation, `__Host-` cookie prefix outside local, httpOnly secure cookie, CSRF delivery & Origin check. | **DONE** | Implemented in `web/src/lib/session.ts` and `web/src/lib/redis.ts`. Verified by `tests/auth-storage.spec.ts` (0 tokens in localStorage/sessionStorage/IndexedDB) and `tests/live-backend.spec.ts`. |
| **3** | **API Access via Server BFF Proxy:** Upstream gateway mediation, path traversal rejection (`..`, `%2e%2e`, slashes, null bytes), explicit endpoint allow-list, blocking `/internal` and `/admin`, server-overwritten platform headers (`X-Client-Platform: web`, `X-Client-Form-Factor`). | **DONE** | Implemented in `web/src/app/api/proxy/[...path]/route.ts`. Validated with live gateway connection in `tests/live-backend.spec.ts` and unit tests in `tests/unit/client_logic.test.mjs`. |
| **4** | **Role-Aware Navigation:** Student and Parent role views; teacher and admin routes strictly absent. | **DONE** | Responsive layout in `web/src/app/page.tsx` and `web/src/components/layout/Sidebar.tsx` displaying student/parent modules dynamically. Teacher/admin routes completely omitted. |
| **5** | **Parent Features:** Onboarding (create family, add child, link code/QR), children overview, child dashboard, study setup (all controls, config limits, optimistic locking), AI suggestions & undo, change requests, quiz review, notification preferences, plan warnings. | **DONE** | Views created: `ParentDashboardView`, `StudySetupEditorView`, `ParentSuggestionsView`, `ParentOnboardingView`, `NotificationPreferencesView`. Integrated in `web/src/app/page.tsx`. |
| **6** | **Student Features:** Today view, plan timeline, task detail, revision, practice quiz runner, broad answer (typed and photo upload with signed URLs), progress (approved wording only), change requests, settings. | **DONE** | Views created: `TodayView`, `PracticeQuizRunner`, `AIChatView`, `BroadAnswerView`, `ProgressView`, `StudentChangeRequestView`. Verified in `tests/responsive-flows.spec.ts`. |
| **7** | **Assessed Quizzes:** Dynamic banner from `/client/config` stating mobile app is coming soon until Android ships; attempt creation strictly blocked with 403 `WEB_PLATFORM_PRACTICE_ONLY`. | **DONE** | Guarded in BFF proxy and UI runner `PracticeQuizRunner.tsx`. Verified by `tests/assessed-quiz-blocked.spec.ts` (100% pass across all viewports). |
| **8** | **AI Chat:** SSE streaming through server layer, non-stream fallback, textbook citation chips (book, chapter, printed page), quota and quiz-lockout states, output & link sanitization, KaTeX size cap. | **DONE** | Implemented in `web/src/components/student/AIChatView.tsx` and `web/src/components/MathRenderer.tsx` (DOMPurify, KaTeX length cap 10,000 / 1,000 expr). Tested in `tests/responsive-flows.spec.ts`. |
| **9** | **Responsive & Tablet Layouts:** Compact (<600px, bottom nav), medium (600–839px, nav rail/sidebar, 2-pane), expanded (>=840px, desktop sidebar, 2-pane), 48px touch targets, keyboard/mouse support. | **DONE** | CSS tokens and responsive components in `web/src/components/layout/`. Verified across Playwright Chromium and WebKit projects at 375px, 768px, and 1280px widths. |
| **10** | **Localization:** All strings from resources, Bangla default, English switch, Bengali digit formatting (`toBengaliDigits()`), font loading strategy avoiding layout shifts. | **DONE** | Resources in `web/src/lib/i18n.ts`. Tested in `tests/unit/client_logic.test.mjs` and Playwright language toggle tests. |
| **11** | **Security:** Strict CSP (no `unsafe-inline` or `unsafe-eval` in production), secure headers, no third-party scripts, SW cache purge on logout, Firebase auth flag with CSP entries. | **DONE** | Implemented in `web/src/middleware.ts` and `web/public/sw.js` (`LOGOUT_PURGE`, `AUTH_401_PURGE`, `SESSION_EXPIRED` handlers). Validated by security audits and CSP headers test. |
| **12** | **PWA Basics:** Installable manifest, cached shell, offline view of today's plan, logout authenticated cache purge. | **DONE** | Configured in `web/public/manifest.json` and `web/public/sw.js`. Service worker purges cache on `apiClient.logout()`. |
| **13** | **Quality Bar:** Playwright E2E tests in Chromium and WebKit (51 passed), axe accessibility audit across all routes in both languages and themes (0 violations), CI performance budget script, unit tests. | **DONE** | 51 Playwright tests passed; 5 Node unit tests passed; `web/scripts/check_perf_budget.mjs` passed; `web/scripts/check_proxy_openapi.mjs` passed. |

---

## 2. Security Scanners Audit Summary

| Tool | Version / Config | Target / Scope | Findings / Status |
|---|---|---|---|
| **gitleaks** | `v8.30.1` | Full git history over all branches (34 commits) | **0 leaks found** (PASS) |
| **npm audit** | `npm 11/12` | `web/package.json` & `web/package-lock.json` | **0 vulnerabilities** (PASS) |
| **Bandit** | `1.9.3` | `core` and `gateway` (18,192 lines scanned) | **0 High, 0 Medium** (PASS) |
| **pip-audit** | `2.8.0` | Python environment dependencies | **Audited and recorded** (122 known advisories across 22 ML runtime dependencies like vllm/torch/pillow) |
| **Trivy (web)** | `aquasec/trivy:latest` | `thinkbuddyarc-web:latest` image | **0 CRITICAL** (PASS, non-root `USER nextjs`) |
| **Trivy (core)** | `aquasec/trivy:latest` | `thinkbuddyarc-core:latest` image | **0 CRITICAL** (PASS, OS base package notices deferred by Debian) |
| **Trivy (gateway)** | `aquasec/trivy:latest` | `thinkbuddyarc-gateway:latest` image | **0 CRITICAL** (PASS) |
| **Trivy (workers)**| `aquasec/trivy:latest` | `thinkbuddyarc-workers:latest` image | **0 CRITICAL** (PASS) |
| **Performance Budget** | Custom Node runner | `check_perf_budget.mjs` (JS chunks & CSS size) | **PASSED** (Largest chunk: 373KB uncompressed / ~110KB gzip; budget: 400KB) |
| **Proxy OpenAPI Check**| `node scripts/check_proxy_openapi.mjs` | Proxy allow-list against `docs-generated/openapi.json` | **23/23 rules verified** (PASS) |
| **Playwright E2E** | `1.64.1` (Chromium & WebKit) | Phone (375px), Tablet (768px), Desktop (1280px) | **51 passed in 1.7m** (PASS) |
| **axe-core** | `4.14.0` | Every route/tab in `bn` & `en`, `light` & `dark` | **0 violations** (PASS) |
| **Unit Tests** | `node:test` (Node v24) | Client logic, traversal, i18n, timeouts, origin | **5 passed in 54ms** (PASS) |

---

## 3. P08 Tail Hardening Implementation & Invariants

### 3.1 Re-Seeded Admin Policy Ceilings & Auto-Mode Bounds
In accordance with user specifications, the `admin_policies` table and fallback policy resolution are re-seeded via Alembic migration `0018_reseed_admin_policy_ceilings.py`:

| Class Band | School Day Default | School Day Auto Ceiling | Holiday Default | Holiday Auto Ceiling | Hard Limit (School Day) | Hard Limit (Holiday) |
|---|---|---|---|---|---|---|
| **Band 6 to 8** | 150 min | 240 min | 240 min | 360 min | 360 min | 600 min |
| **Band 9 to 10** | 240 min | 360 min | 360 min | 480 min | 360 min | 600 min |
| **Band 11 to 12** | 300 min | 360 min | 420 min | 600 min | 360 min | 600 min |

**Invariants Enforced:**
1. **Auto mode never lowers a parent setting:** Even if AI recommendations suggest lower study times, auto mode preserves the parent's baseline.
2. **Auto mode never raises above the auto ceiling:** Even under heavy syllabus strain, study time will not be auto-raised beyond the band's auto ceiling.
3. **Values already above the ceiling remain unchanged:** If a parent deliberately configured 320 minutes (above the 240m ceiling but within the 360m hard limit), auto mode leaves that parent setting intact and does not clamp or override it.

### 3.2 Real Client IP Propagation & Rate Limit Isolation
1. **Trusted Proxies Configuration:** Added `"web"` and `"thinkbuddy-web"` to `settings.TRUSTED_PROXIES` in `core/common/config.py`.
2. **BFF Header Forwarding:** In `web/src/app/api/proxy/[...path]/route.ts` and `web/src/app/api/auth/route.ts`, the real client IP is parsed from incoming `X-Forwarded-For` / `X-Real-IP` and forwarded upstream to the gateway as `X-Real-IP: <client_ip>` and `X-Forwarded-For: <client_ip>, 127.0.0.1`.
3. **CIDR & Private Network Verification:** Updated `core/common/rate_limit.py::is_peer_trusted_proxy` to use Python `ipaddress` for evaluating CIDR ranges (`172.16.0.0/12`, `10.0.0.0/8`, `192.168.0.0/16`) and loopback/private bridge networks.
4. **Per-IP Rate Limit Isolation:** Verified via automated tests (`tests/test_p08_ip_rate_limit.py`) that rate limit lockouts (e.g., 5 consecutive invalid token exchanges) apply per individual user IP, ensuring that one abusive user does not rate-limit or lock out other users traversing the shared web container.

### 3.3 Standing Rules Alignment (1 to 18, Zero Duplicates)
Verified that `GEMINI.md`, `thinkbuddy-docs/AGENT_RULES.md`, and `AGENT_RULES.md` all contain the exact identical 18 rules numbered 1 to 18 with 0 duplicates:
- Rule 17: Client token isolation (No auth tokens in browser client storage; HttpOnly SameSite Secure cookies via BFF layer).
- Rule 18: Platform isolation for assessments (Assessed quizzes require native mobile platform enforcement and are strictly forbidden on web clients).

### 3.4 Anchored & Method-Restricted Proxy Allow-List
In `web/src/app/api/proxy/[...path]/route.ts`, all 23 allow-list entries are strictly anchored (`^...$`) with explicit HTTP method restrictions:
- `client/config` [GET]
- `quizzes/[^/]+/attempts` [POST]
- `attempts/[^/]+/items/[^/]+/answer` [POST]
- `attempts/[^/]+/submit` [POST]
- `attempts/[^/]+/review` [GET]
- `students/[^/]+/today` [GET]
- `tasks/[^/]+` [PATCH]
- `students/[^/]+/plan` [GET]
- `students/[^/]+/study-settings` [GET, PUT]
- `students/[^/]+/study-settings/change-requests` [POST]
- `students/[^/]+/ai-suggestions` [GET]
- `students/[^/]+/ai-suggestions/[^/]+/approve` [POST]
- `students/[^/]+/ai-suggestions/[^/]+/reject` [POST]
- `students/[^/]+/ai-adjustments/[^/]+/undo` [POST]
- `parents/me/students/[^/]+/change-requests/[^/]+/approve` [POST]
- `parents/me/students/[^/]+/change-requests/[^/]+/decline` [POST]
- `parents/me/students` [GET]
- `notifications/preferences` [GET, PUT]
- `notifications` [GET]
- `families` [POST]
- `families/[^/]+/students` [POST]
- `links/redeem` [POST]
- `links/[^/]+/revoke` [POST]

A dedicated CI script `web/scripts/check_proxy_openapi.mjs` (`npm run check:proxy`) validates that every single proxy rule maps to an active endpoint and permitted method in `docs-generated/openapi.json`.

### 3.5 Service Worker: Network-Only & Automatic 401 Purge
- In `web/public/sw.js`, all `/api/*` requests bypass shell caching (Network-Only).
- If any `/api/*` response returns HTTP 401, the service worker immediately triggers `purgeAllCaches()`.
- Client `api-client.ts` also posts `AUTH_401_PURGE` and empties `window.caches` on 401.
- Service worker listens for `LOGOUT_PURGE`, `SESSION_EXPIRED`, and `AUTH_401_PURGE`.

### 3.6 Firebase Sign-In UI & Content Security Policy (CSP) Domains
Implemented `web/src/components/auth/FirebaseSignInModal.tsx`:
- Phone OTP verification input with responsive layout and validation.
- reCAPTCHA container `<div id="recaptcha-container"></div>` for invisible/visible phone verification.
- Google Sign-In button.
- Accessible ARIA modal with bilingual Bengali and English labels.

**Required CSP Domains in `web/src/middleware.ts`:**
- `script-src`: `'self' https://apis.google.com https://www.gstatic.com https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/`
- `connect-src`: `'self' https://identitytoolkit.googleapis.com https://securetoken.googleapis.com`
- `frame-src`: `'self' https://www.google.com/recaptcha/ https://recaptcha.google.com/recaptcha/ https://*.firebaseapp.com`

### 3.7 Real Backend Journeys vs. Mock-Only Flows
A seed script `scripts/seed_p08_e2e_data.py` and automated journey test `tests/test_p08_e2e_journeys.py` validate real backend operations:

**Live Backend Flows Verified:**
1. Parent onboarding & family creation (`POST /v1/families`)
2. Student addition & expiring link code generation (`POST /v1/families/{id}/students`)
3. Student link code redemption (`POST /v1/links/redeem`)
4. Daily learning loop: today's schedule and task status updates (`GET /v1/students/{id}/today`, `PATCH /v1/tasks/{id}`)
5. AI planner suggestions review & approval (`POST /v1/students/{id}/ai-suggestions/{id}/approve`)
6. One-tap undo of auto adjustments (`POST /v1/students/{id}/ai-adjustments/{id}/undo`)
7. Student study setting change request and parent approval (`POST /v1/parents/me/students/{id}/change-requests/{id}/approve`)
8. Practice quiz runner, answering, submission, and review unlock with citations (`POST /v1/quizzes/{id}/attempts`, `GET /v1/attempts/{id}/review`)
9. Assessed quiz rejection on web client (HTTP 403 `WEB_PLATFORM_PRACTICE_ONLY`)

**Mock-Only Flows Documented:**
1. **Broad Question Photo OCR:** Drag-and-drop photo upload generates a signed URL; OCR text extraction and broad question topic classification use mock parsing.
2. **Live AI Chat Streaming (without LLM API key):** When an external LLM key is not configured, the streaming chat endpoint returns deterministic textbook-grounded mock responses with citations.

---

## 4. Playwright End-to-End Test Matrix (51 Passed)

Tested across three canonical viewport profiles in **Chromium** and **WebKit**:
- **Compact Viewport (375x667):** Bottom navigation active, drawer accessible, touch targets >= 48px, 0 overflow.
- **Medium Viewport (768x1024):** Navigation rail / collapsible sidebar, 2-pane master-detail layout.
- **Expanded Viewport (1280x800):** Desktop persistent sidebar, rich 2-column study planner and parent overview.

```
Running 51 tests using 4 workers
  51 passed (1.7m)
```
- LocalStorage / SessionStorage / IndexedDB token check: **0 tokens detected** (PASS)
- HttpOnly cookie enforcement: **PASS**
- Path traversal rejection: **PASS**
- Forbidden admin/internal routes: **PASS**
- Assessed quiz banner & attempt block: **PASS**
- Axe accessibility violations: **0 violations across all tabs, languages, and themes** (PASS)
