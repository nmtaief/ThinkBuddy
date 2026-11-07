## Description
<!-- Brief 1-3 sentence summary of changes and user-facing impact -->

## Related Prompt / Milestone
<!-- e.g. P10 Hardening, P08a Android App -->

## Standing Rules Compliance Checklist (GEMINI.md)
- [ ] **Rule 1 (Read First):** Relevant docs and specifications read prior to coding.
- [ ] **Rule 3 (API-First):** OpenAPI contract verified or updated (`docs/04_API_CONTRACT.md`).
- [ ] **Rule 4 (Platform-Agnostic Backend):** No per-platform forks; platform handled via client headers / config.
- [ ] **Rule 5 & 6 (Server Authority & Zero Leakage):** Quiz scoring, timing, and deadlines server-enforced; zero answer keys leaked prior to submission.
- [ ] **Rule 7 & 8 (Citations & Printed Pages):** RAG answers cite book, chapter, and printed page. Printed page != PDF page index.
- [ ] **Rule 9 (Authorization & Isolation):** Role checks and strict tenant/family isolation enforced on every route.
- [ ] **Rule 10 (Reversible Migrations):** Database schema modified solely via reversible Alembic migrations.
- [ ] **Rule 11 (Tests Included):** Unit and integration tests added; zero skipped tests.
- [ ] **Rule 12 (No Secrets):** No credentials, private keys, or tokens committed; `.env.example` updated.
- [ ] **Rule 13 (Bangla/English Localization):** Full Unicode fidelity; user-facing strings externalized.
- [ ] **Rule 15 (Log, Don't Leak):** Structured logs with request IDs; no secrets, tokens, OTPs, or PII logged.
- [ ] **Rule 17 (Client Token Isolation):** No tokens in browser storage; HttpOnly cookies on web; hardware Keystore on mobile.
- [ ] **Rule 18 (Platform Isolation for Assessments):** Assessed quizzes require native hardware attestation; web restricted to practice-only.

## Testing & Verification
- **Backend Test Suite:** `pytest tests/`
- **Android Tests:** `gradlew testDebugUnitTest` / `connectedDebugAndroidTest`
- **Security Scanners:** `gitleaks dir .`, `bandit`, `semgrep`, `trivy`

