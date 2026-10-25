# Standing Rules for Every Agent Session

1. **Read first.** Before any task read `README.md` and the docs the prompt names. If code and docs disagree, stop and report; do not silently pick one.
2. **Plan before code.** Output a short plan (files to create, tables to change, risks), then implement.
3. **API-first.** The OpenAPI schema is the contract. Never add an endpoint without updating `docs/04_API_CONTRACT.md` and the generated OpenAPI.
4. **Platform-agnostic backend.** No endpoint, response shape, or business rule may assume Android. Platform differences are handled only through client headers and the `/v1/client/config` response.
5. **Server is the authority.** Quiz timing, scoring, answer keys, entitlements, and parent/student permissions are enforced on the server. The client is untrusted.
6. **Never send answer keys to clients** before an attempt item is submitted (see `docs/05_SECURE_QUIZ.md`).
7. **Every answer from RAG must carry citations** (book, chapter, printed page). If retrieval confidence is low, say so instead of guessing.
8. **Printed page number ≠ PDF page index.** Store both; show only the printed number to users.
9. **Authorization on every route.** Use role checks plus ownership checks (a parent can only access linked students; a student only their own data).
10. **Migrations only through Alembic.** No manual schema edits. Every migration reversible.
11. **Tests are part of done.** Unit tests for rules, integration tests for each endpoint, and the acceptance checks in the prompt. No prompt is complete with failing tests.
12. **No secrets in the repo.** Use environment variables and a `.env.example`.
13. **Bangla and English everywhere.** All user-facing strings come from localization resources; all text columns must handle Unicode (Bangla) correctly. Test with Bangla input.
14. **Small, reviewable changes.** One prompt = one branch/PR. Do not refactor unrelated code.
15. **Log, don't leak.** Structured logs with request IDs. Never log tokens, OTPs, answer keys, or full student chat content.
16. **Ask by writing a `QUESTIONS.md` entry** when a requirement is ambiguous, then proceed with the documented default.
17. **Client token isolation.** Never store auth tokens (access, refresh, or session) in browser-accessible client storage (localStorage, sessionStorage, IndexedDB). Web clients must store sessions in HttpOnly, SameSite, Secure cookies managed via a server BFF layer. Mobile clients must use hardware-backed secure storage (Android Keystore, iOS Keychain).
18. **Platform isolation for assessments.** Assessed quizzes require native platform enforcement (`FLAG_SECURE`, Play Integrity, app attestation) and must never be permitted on web clients. The backend and BFF must restrict web clients to practice quizzes only (`WEB_PLATFORM_PRACTICE_ONLY`).

