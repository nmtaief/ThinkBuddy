# P08 – Web App (Student + Parent), responsive for phone, tablet and desktop

**Read first:** `AGENT_RULES.md`, `docs/02_PRODUCT_FLOWS.md`, `docs/04_API_CONTRACT.md`, `docs/05_SECURE_QUIZ.md`, `docs/07_AI_PLANNER_API.md` (suggestions only), `docs/08_CLIENT_PLATFORM_GUIDE.md`, `docs-generated/openapi.json`.

## Role
Senior frontend engineer. Build the first client of ThinkBuddy: a web app for students and parents.

## Stack
Next.js (React, TypeScript) with a server-side layer (backend for frontend), Tailwind or CSS modules driven by the shared design tokens, a client generated from OpenAPI, i18n for Bangla and English, KaTeX for math, Playwright and axe for tests, containerized with Docker behind the existing reverse proxy.

## Deliverables
1. **Project and tokens:** `/web` app, `/design/tokens.json`, generated API client, lint, typecheck, CI, Dockerfile, `.env.example`.
2. **Session layer:** sign-in with the Firebase web SDK (phone OTP with reCAPTCHA or App Check, Google), exchange through the backend, refresh token kept in an httpOnly secure cookie, access token only on the server side. No tokens in localStorage or sessionStorage. CSRF protection for cookie-authenticated routes. In local development use the backend's fake auth provider.
3. **API access through the server layer** so browsers never call the core API directly (no CORS needed). Set `X-Client-Platform=web`, `X-Client-Form-Factor` from the viewport, `X-App-Version`, `X-Device-Id`, `Accept-Language`. Load `/client/config` and honor limits, flags, observances, and `min_supported_version`.
4. **Role-aware navigation** for Student and Parent; teacher and admin routes absent.
5. **Parent features:** onboarding (create family, add child, link code or QR), children overview, child dashboard, full study setup (every control listed in the guide, validated against limits from `/client/config`, with optimistic concurrency conflict handling), AI suggestions with approve and decline, auto-adjustments with one-tap undo, student change requests, quiz review after submission, notification preferences, plan warnings.
6. **Student features:** Today, plan timeline, task detail, revision, practice quiz runner, broad answer (typed and photo upload with signed URLs), progress (approved wording only), change request, settings.
7. **Assessed quizzes:** show "available in the ThinkBuddy app" with a placeholder store link; never start an assessed attempt from web.
8. **AI chat:** SSE streaming through the server layer, non-stream fallback, citation chips (book, chapter, printed page), "not found in your textbook" state, quota and quiz-lockout error states, cancel on navigation.
9. **Responsive and tablet-optimized layouts** per `docs/08_CLIENT_PLATFORM_GUIDE.md §4`: compact, medium and expanded classes, two-pane patterns on tablets and desktop, keyboard and mouse support, landscape, container queries or breakpoints from tokens.
10. **Localization:** all strings from resources, Bangla default, Bangla number formatting where appropriate, font loading strategy that avoids layout shift.
11. **Security:** strict CSP, secure headers, no third-party scripts, input validation, no answer keys cached, error pages that leak nothing.
12. **PWA basics:** installable, cached shell, offline view of today's plan.
13. **Quality:** Playwright end-to-end tests at phone, tablet, and desktop viewports for sign-in, parent setup, student day, chat streaming, and practice quiz; axe accessibility checks; Lighthouse or equivalent budget checks in CI; unit tests for state logic.

## Constraints
- No business rules in the client; the server decides limits, plans, grading, and entitlements.
- No analytics SDKs that identify children; first-party events only.
- Every user-visible string is a resource, positive in tone, and uses approved wording for progress ("needs practice", "not enough data").

## Acceptance
- All flows work in a Chromium and a WebKit run at three viewport sizes; layouts switch at the specified breakpoints.
- No token appears in browser storage or JavaScript-readable cookies (automated check).
- Assessed attempt cannot be started from web (test).
- Bangla renders correctly with conjuncts; long strings do not break layouts.
- Chat streams progressively and shows citations.
- Security scans and `reports/P08_security_report.md` per standing rules. Stop for review.
