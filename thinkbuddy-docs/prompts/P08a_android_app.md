# P08a – Android App (Phone and Tablet)

Build the native Android application for ThinkBuddy serving Students and Parents across phone and tablet devices.

## 1. Context & Architecture
Per `thinkbuddy-docs/prompts/08_CLIENT_PLATFORM_GUIDE.md` and `android/README.md`:
- **Language & UI:** Kotlin, Jetpack Compose, Material 3, WindowSizeClass.
- **Architecture:** Clean Architecture + MVVM + Repository pattern with Coroutines & StateFlow.
- **Adaptive Form Factors:**
  - *Compact (< 600 dp):* Single pane, bottom navigation.
  - *Medium (600–839 dp):* Navigation rail, adaptive layouts.
  - *Expanded (>= 840 dp):* Navigation rail/drawer, two-pane master-detail.
- **Design Tokens:** Mapped from `/design/tokens.json` (Bangla typography default with Noto Sans Bengali / Hind Siliguri, light and dark themes).
- **Networking:** Retrofit + OkHttp with `docs-generated/openapi.json` contract adherence.
  - Required headers: `X-Client-Platform: android`, `X-Client-Form-Factor`, `X-App-Version`, `X-Device-Id`, `Accept-Language`.
- **Security & Storage:**
  - Hardware-backed Android Keystore (`EncryptedSharedPreferences` / AndroidX Security Crypto) for JWT storage (Rule 17).
  - Native Assessed Quiz Security: `FLAG_SECURE` window protection, multi-window detection, Play Integrity attestation (Rule 18 / `docs/05_SECURE_QUIZ.md`).
- **Offline & Room:** Room database caching today's schedule and tasks for zero-latency startup and offline learning.
- **Bilingual:** All strings in `res/values/strings.xml` (Bangla) and `res/values-en/strings.xml` (English).

## 2. Deliverables
1. **Project Setup:** Gradle configuration (`settings.gradle.kts`, `build.gradle.kts`, `app/build.gradle.kts`), AndroidManifest, ProGuard/R8 rules.
2. **Design System & Theme:** Compose Material 3 theme generated from `design/tokens.json` supporting light/dark themes and Bengali typography.
3. **Secure Auth & Token Storage:** Keystore-backed repository for tokens, device ID derivation, biometric/session login flow.
4. **Network & OpenAPI Client:** OkHttp client, Retrofit services matching gateway contracts, SSE streaming client for RAG AI Tutor.
5. **Local Data Layer (Room):** Entities and DAOs for offline caching of today's plan, tasks, and study progress.
6. **Student Features:**
   - Today's learning loop (tasks, guidelines, timer, completion toggles)
   - Plan timeline & task details with printed page citations
   - Practice and Assessed Quiz runners (with `FLAG_SECURE` anti-screenshot and multi-window guard)
   - AI Tutor Chat with SSE streaming and textbook citation chips
   - Progress & Mastery overview
7. **Parent Features:**
   - Children overview & dashboard
   - Study setup editor with admin policy limits and optimistic locking
   - AI suggestions review and one-tap undo of automated adjustments
   - Student change requests approval
   - Expiring link code generation and device connection
   - Notification preferences
8. **Verification & Testing:** Unit tests for repositories, viewmodels, and security guards; Android test runners.
