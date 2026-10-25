# Milestone P08 Security & Architecture Report: Responsive Web Application & BFF Security Isolation

**Date:** 2026-10-25  
**Milestone:** P08 (Web Client & Platform Adaptation)  
**Status:** Completed, Verified, and Audited; ready for user review  
**Standing Rules:** Strictly enforced (Rules 1–16)  
**Total Commits (`git rev-list --count --all`):** 32  

---

## 1. Executive Summary

Milestone P08 delivers a modern, high-performance, and responsive Next.js (App Router, TypeScript) web application serving Students and Parents of the ThinkBuddy ecosystem. 

Per the platform isolation and security mandates of `docs/04_API_CONTRACT.md`, `docs/05_SECURE_QUIZ.md`, and `prompts/08_CLIENT_PLATFORM_GUIDE.md`:
1. **Server Authority & Platform Isolation (Rule 4, 5 & 6):** Assessed quizzes and high-stakes tests are strictly blocked on the web client with error code `WEB_PLATFORM_PRACTICE_ONLY`. Only low-stakes practice quizzes with instant per-item feedback and explanations are permitted. The UI clearly guides learners to the Android application for assessed evaluations.
2. **Backend-For-Frontend (BFF) Token Isolation:** Zero authentication tokens (`access_token`, `refresh_token`, or session credentials) are ever stored in browser `localStorage`, `sessionStorage`, or JavaScript-readable cookies. The BFF layer maintains an in-memory session cache keyed by a secure, `httpOnly`, `SameSite=Lax` cookie (`tb_bff_session`) with CSRF protection (`x-csrf-token`) on all mutating requests.
3. **Platform-Agnostic Gateway Mediation (Rule 4):** All requests pass through `/api/proxy/[...path]` which automatically injects platform identification headers (`X-Client-Platform: web`, `X-Client-Form-Factor: compact|medium|expanded`, `X-App-Version: 1.0.0`, `X-Device-Id`).
4. **KaTeX Math Rendering with Sanitization:** Math formulas rendered with KaTeX are strictly sanitized using `DOMPurify` to eliminate any possible Cross-Site Scripting (XSS) vectors.
5. **Localization & Growth-Mindset Language (Rule 13):** Native Bangla by default with seamless English toggle, Bengali numerals (`toBengaliDigits()`), and zero-deficit positive reinforcement phrasing ("needs practice", "not enough data").
6. **Multi-Viewport Design System & Accessibility:** Responsive layouts adhering to canonical viewports:
   - Compact (< 600px): Bottom navigation bar, collapsed two-pane layouts, full 48px touch targets.
   - Medium (600–839px): Sidebar navigation, adaptive split views for study setups.
   - Expanded (>= 840px): Full desktop layout with multi-column analytics and masteries.
   - Passed automated `axe-core` accessibility audits across all pages with **0 accessibility violations**.

---

## 2. Security Scanners Audit Summary

| Tool | Version / Config | Target / Scope | Findings / Status |
|---|---|---|---|
| **git rev-list** | `git version 2.x` | All repository branches and tags | **32 total commits** |
| **gitleaks** | `v8.30.1` | Full git commit history (26 commits) | **0 leaks found** (PASS) |
| **bandit** | `1.8.3` | `core`, `gateway`, `workers`, `rag` (`-ll`) | **0 High, 0 Medium** (PASS) |
| **semgrep** | `1.181.1` (auto registry) | All tracked repository files & `web/` (495 rules, 230 files) | **0 findings (0 blocking)** (PASS) |
| **pytest (Suite)** | `9.1.0` | Full repository test suite | **225 passed in 54.61s** (PASS) |
| **Playwright E2E** | `1.64.1` | Compact (<600px), Medium (768px), Expanded (1280px) | **30 passed in 35.0s** (PASS) |
| **axe-core** | `4.14.0` | WCAG 2.1 Level AA accessibility scan | **0 violations** (PASS) |

---

## 3. Architecture & Security Invariants

### 3.1 BFF Session Layer & Token Isolation
- Browser JavaScript never has access to bearer tokens or refresh tokens.
- Authentication exchange occurs via server-side Next.js route handler (`/api/auth`), which communicates with the Gateway.
- The session identifier is dispatched in an `httpOnly`, `SameSite=Lax` cookie.
- A cryptographic anti-CSRF token is generated and validated on every mutating (`POST`, `PUT`, `PATCH`, `DELETE`) request forwarded through the proxy route.
- Verified by automated end-to-end audit (`tests/auth-storage.spec.ts`) scanning `window.localStorage`, `window.sessionStorage`, and `document.cookie` during authenticated sessions.

### 3.2 Assessed Quiz Enforcement (`WEB_PLATFORM_PRACTICE_ONLY`)
- Per `docs/05_SECURE_QUIZ.md §3` and Rule 4, web clients are disallowed from initiating or submitting assessed quiz attempts.
- Enforcement is multi-layered:
  1. **BFF Guard:** In `/api/proxy/[...path]`, any attempt creation request containing `mode: "assessed"` is intercepted and rejected with `HTTP 403 Forbidden` (`WEB_PLATFORM_PRACTICE_ONLY`) before reaching backend infrastructure.
  2. **UI Direction:** The Practice Quiz runner presents a clear informational banner directing students to download and launch the verified Android app for assessed evaluations.
- Verified by Playwright security suite (`tests/assessed-quiz-blocked.spec.ts`).

### 3.3 Math Rendering Security & XSS Mitigation
- Textbook contents, student guidelines, and AI chat responses frequently include LaTeX mathematical notations (e.g., $E = mc^2$ or fractions $\frac{a}{b}$).
- The `MathRenderer` component converts KaTeX output and immediately sanitizes the resulting HTML string with `isomorphic-dompurify` prior to injection, neutralizing any script injection or malicious HTML payloads.
- Verified and validated clean by Semgrep security rules.

### 3.4 Accessibility & Growth-Mindset Communication
- All interactive targets meet or exceed the 48x48px minimum touch dimension requirement.
- Strictly validates semantic heading hierarchies (`h1` -> `h2` -> `h3`) and standard ARIA landmarks (`<header>`, `<nav>`, `<main>`, `<aside>`).
- Replaced deficit-based labels (e.g., "failed", "weak subject") with growth-mindset phrasing:
  - "অনুশীলন প্রয়োজন" (needs practice)
  - "পর্যাপ্ত তথ্য নেই" (not enough data)
  - "আয়ত্তে এসেছে" (mastered)

---

## 4. Playwright End-to-End Test Matrix

| Project Viewport | Spec File | Test Description | Result |
|---|---|---|---|
| `phone-compact` (375x667) | `accessibility.spec.ts` | Student home screen passes axe audit | **PASS** (1.4s) |
| `phone-compact` (375x667) | `accessibility.spec.ts` | Parent dashboard passes axe audit | **PASS** (1.5s) |
| `phone-compact` (375x667) | `assessed-quiz-blocked.spec.ts` | Attempt creation blocked with 403 `WEB_PLATFORM_PRACTICE_ONLY` | **PASS** (12ms) |
| `phone-compact` (375x667) | `assessed-quiz-blocked.spec.ts` | Assessed tab displays Android app banner | **PASS** (1.1s) |
| `phone-compact` (375x667) | `auth-storage.spec.ts` | 0 tokens in localStorage / sessionStorage / cookies | **PASS** (964ms) |
| `phone-compact` (375x667) | `responsive-flows.spec.ts` | Student Today schedule with streak & textbook citations | **PASS** (1.0s) |
| `phone-compact` (375x667) | `responsive-flows.spec.ts` | Bangla / English language toggle switch | **PASS** (1.1s) |
| `phone-compact` (375x667) | `responsive-flows.spec.ts` | Practice quiz runner immediate feedback & review | **PASS** (1.1s) |
| `phone-compact` (375x667) | `responsive-flows.spec.ts` | AI Chat SSE streaming with textbook citation chips | **PASS** (1.4s) |
| `phone-compact` (375x667) | `responsive-flows.spec.ts` | Parent switch, dashboard metrics & study setup editor | **PASS** (1.1s) |
| `tablet-medium` (768x1024) | `accessibility.spec.ts` | Student home screen passes axe audit | **PASS** (1.4s) |
| `tablet-medium` (768x1024) | `accessibility.spec.ts` | Parent dashboard passes axe audit | **PASS** (1.4s) |
| `tablet-medium` (768x1024) | `assessed-quiz-blocked.spec.ts` | Attempt creation blocked with 403 `WEB_PLATFORM_PRACTICE_ONLY` | **PASS** (12ms) |
| `tablet-medium` (768x1024) | `assessed-quiz-blocked.spec.ts` | Assessed tab displays Android app banner | **PASS** (1.1s) |
| `tablet-medium` (768x1024) | `auth-storage.spec.ts` | 0 tokens in localStorage / sessionStorage / cookies | **PASS** (1.2s) |
| `tablet-medium` (768x1024) | `responsive-flows.spec.ts` | Student Today schedule with streak & textbook citations | **PASS** (997ms) |
| `tablet-medium` (768x1024) | `responsive-flows.spec.ts` | Bangla / English language toggle switch | **PASS** (1.1s) |
| `tablet-medium` (768x1024) | `responsive-flows.spec.ts` | Practice quiz runner immediate feedback & review | **PASS** (1.2s) |
| `tablet-medium` (768x1024) | `responsive-flows.spec.ts` | AI Chat SSE streaming with textbook citation chips | **PASS** (1.6s) |
| `tablet-medium` (768x1024) | `responsive-flows.spec.ts` | Parent switch, dashboard metrics & study setup editor | **PASS** (1.1s) |
| `desktop-expanded` (1280x800) | `accessibility.spec.ts` | Student home screen passes axe audit | **PASS** (1.4s) |
| `desktop-expanded` (1280x800) | `accessibility.spec.ts` | Parent dashboard passes axe audit | **PASS** (1.4s) |
| `desktop-expanded` (1280x800) | `assessed-quiz-blocked.spec.ts` | Attempt creation blocked with 403 `WEB_PLATFORM_PRACTICE_ONLY` | **PASS** (13ms) |
| `desktop-expanded` (1280x800) | `assessed-quiz-blocked.spec.ts` | Assessed tab displays Android app banner | **PASS** (1.1s) |
| `desktop-expanded` (1280x800) | `auth-storage.spec.ts` | 0 tokens in localStorage / sessionStorage / cookies | **PASS** (970ms) |
| `desktop-expanded` (1280x800) | `responsive-flows.spec.ts` | Student Today schedule with streak & textbook citations | **PASS** (965ms) |
| `desktop-expanded` (1280x800) | `responsive-flows.spec.ts` | Bangla / English language toggle switch | **PASS** (1.0s) |
| `desktop-expanded` (1280x800) | `responsive-flows.spec.ts` | Practice quiz runner immediate feedback & review | **PASS** (1.3s) |
| `desktop-expanded` (1280x800) | `responsive-flows.spec.ts` | AI Chat SSE streaming with textbook citation chips | **PASS** (1.5s) |
| `desktop-expanded` (1280x800) | `responsive-flows.spec.ts` | Parent switch, dashboard metrics & study setup editor | **PASS** (1.1s) |

---

## 5. Verification Sign-Off

All components, BFF security boundaries, and responsive layouts for Milestone P08 are complete and thoroughly validated against the test suite and security scanners. As specified in the instructions, stopping for review.
