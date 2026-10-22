# P08 – Android App (Kotlin + Jetpack Compose), Phone & Tablet

**Read first:** `AGENT_RULES.md`, `docs/02_PRODUCT_FLOWS.md`, `docs/04_API_CONTRACT.md`, `docs/05_SECURE_QUIZ.md` (§6), generated OpenAPI.

## Task
Build the MVP Android client for Student and Parent roles, adaptive to phones and tablets, driven by `/client/config`.

## Deliverables
1. Project setup: Kotlin, Compose, Material 3, Hilt, Retrofit/OkHttp (generated client from OpenAPI), Room, DataStore, WorkManager, Navigation, FCM.
2. Layout adaptivity with `WindowSizeClass` (compact/medium/expanded): bottom nav on phones, navigation rail and two-pane screens on tablets.
3. Auth flows (phone OTP, Google), role-aware navigation (Student vs Parent), device registration, header injection, token refresh.
4. **Parent app:** add child, link code/QR, study setup (syllabus, exam date, chapter order), progress dashboard, notifications settings, change-request approvals.
5. **Student app:** Today screen, plan timeline, task detail with guidelines, revision, homework, quiz runner, broad answer (typed + photo), AI chat with SSE streaming and citation chips, progress view.
6. **Secure quiz runner:** `FLAG_SECURE`, non-selectable text, clipboard clearing, lifecycle/multi-window/overlay event reporting to the server, server-driven timer sync, integrity verdict request at start, graceful messages for invalidation.
7. Offline: Room cache of plan/today; quiz and chat require connectivity with clear messages.
8. Localization (Bangla default, English), Bangla fonts tested, math rendering for formulas.
9. Accessibility basics and dark mode.

## Constraints
- No business rules in the client; no answer keys or full question banks stored locally.
- Every user-facing string is a resource.
- Feature visibility (teacher, premium) comes from `/client/config`.

## Acceptance
- Runs on a phone emulator and a tablet emulator with appropriate layouts.
- Screenshot attempts in the quiz screen are blocked; the recents thumbnail is blank.
- Backgrounding during an assessed quiz creates an integrity event on the server.
- Chat streams tokens progressively and shows citations.
