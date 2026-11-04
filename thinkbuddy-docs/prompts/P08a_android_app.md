# P08a – Android App (Phone and Tablet)

Build the native Android application for ThinkBuddy serving Students and Parents across phone and tablet devices.

## 1. Source of Truth & Context
Per `docs/08_CLIENT_PLATFORM_GUIDE.md` and `android/README.md`:
- **Target OS:** Android 15 (API 35), Min SDK 26 (Android 8.0, 99%+ Bangladesh coverage).
- **Language & Framework:** Kotlin 2.0+, Jetpack Compose, Material 3, WindowSizeClass.
- **Architecture:** Clean Architecture + MVVM + Repository pattern with Coroutines, StateFlow, and Hilt DI.
- **Adaptive Form Factors:**
  - *Compact (< 600 dp):* Single pane, bottom navigation.
  - *Medium & Expanded (>= 600 dp):* Navigation rail, adaptive two-pane master-detail layouts.
  - Tested on both Phone (e.g. Pixel 8) and Tablet (e.g. Pixel Tablet) emulators.
- **Design Tokens & Fonts:** Mapped from `/design/tokens.json`. Default Bangla typography (Noto Sans Bengali / Hind Siliguri) with line height >= 1.5, Bengali digit formatting, and English language switch.
- **Hardware-Backed Token Storage:** Modern Android Keystore-backed AES-GCM encrypted storage storing access and refresh tokens (Rule 17).
- **Assessed Quiz Security:** `FLAG_SECURE` window protection, multi-window/split-screen detection & pause, Google Play Integrity token with nonce bound to attempt ID, plus low-trust fallback path for devices without Google Play Services (Rule 18 / `docs/05_SECURE_QUIZ.md`).
- **Push Notifications:** FCM push receiver with generic non-leaking alert text (Rule 15).
- **Network Security:** Strict HTTPS by default; cleartext HTTP to `10.0.2.2` (emulator host) permitted in `debug` builds only via `network_security_config.xml`.
- **Testing:** Unit tests, Compose UI tests, and instrumented tests.

## 2. Checkpoint & Delivery Strategy
**Review Checkpoint:** Stop for review after the app skeleton, auth, and the Today screen run on both phone and tablet emulators, before building the rest.
