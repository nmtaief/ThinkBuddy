# 05 – Secure Quiz Architecture & Security Policy

## 1. Core Principles & Server Authority
1. **Server is the Sole Authority (Rule 5):** The server generates quiz questions, manages timers, scores answers, validates nonces, and evaluates mastery. The client is treated as an untrusted presentation layer.
2. **Answer Key Protection (Rule 6):** Answer keys, explanations, and scoring criteria are strictly withheld from client network payloads until after an attempt or item is completed and submitted.
3. **Platform Isolation (Rule 18):** Assessed quizzes require native platform enforcement (`FLAG_SECURE`, hardware attestation, system sandboxing) and must never be permitted on web clients (`WEB_PLATFORM_PRACTICE_ONLY`).

---

## 2. Attestation & Trust Flow
1. **Attempt Creation:** Client requests attempt via `POST /v1/quiz/attempts`. The attempt is initialized in `created` status, and the server returns a cryptographically random, single-use `server_nonce` (stored hashed with a short 5-minute expiry).
2. **Attestation Evaluation:**
   - **Play Integrity Path:** Android client calls Google Play Integrity API with the server nonce bound as request hash. The client presents the integrity token to `POST /v1/quiz/attempts/{id}/attest`.
   - **Low-Trust Path:** For devices without Google Play Services or on non-Google builds, the client presents `X-Device-Attestation-Provider: unsupported`. The backend verifies the device and account attestation history: if the account has previously provided a genuine Play Integrity token, subsequent unsupported claims are flagged and receive lower mastery weights (anti-downgrade policy).
   - **Debug Stub:** Allowed exclusively in local debug builds (`ENV=local` / `ENABLE_FAKE_AUTH=true`).
3. **Activation:** Successful attestation transitions the attempt from `created` to `active`.

---

## 3. Runtime Defense-in-Depth on Android

### A. Window & Screen Protection
- **`FLAG_SECURE`:** Applied in `QuizActivity.onCreate()` before view drawing. Prevents screenshot capture, screen recording, HDMI mirroring, and task switcher previews. Cleared only on activity destruction.
- **Overlay Hiding:** `window.setHideOverlayWindows(true)` invoked on Android 12+ (API 31+) to block third-party overlay/float windows.
- **Filter Obscured Touches:** All interactive quiz controls enable `filterTouchesWhenObscured` to defeat tapjacking.

### B. Multi-Window & Floating Window Policy
- **Detection:** `QuizActivity` checks `AssessedQuizSecurity.isFloatingOrWindowedMode(activity)`:
  - `activity.isInMultiWindowMode`
  - Window bounds vs maximum display bounds on API 30+ (`currentWindowMetrics.bounds` vs `maximumWindowMetrics.bounds`). If width or height ratio is < 0.85, floating/freeform mode is detected.
- **Server Policy:** Follows `multi_window_policy` from `/client/config` (default `"pause"`):
  - When multi-window or floating mode is detected, the attempt is immediately paused, the countdown timer stops, and a full-screen blocking overlay is displayed.
  - Submissions are locked until the user restores the app to full-screen mode.
  - Telemetry event `multi_window` is logged.

### C. Assist Data & Accessibility Services
- **Block Assist Data:** `onProvideAssistData(data)` clears the bundle (`data?.clear()`).
- **Clear Assist Content:** `onProvideAssistContent(outContent)` zeroes intent, clipData, structuredData, and webUri.
- **Accessibility Services:**
  - Legitimate system accessibility tools (TalkBack, BrailleBack, Switch Access) remain 100% usable.
  - Third-party non-system accessibility services are detected and reported as a low-weight telemetry signal (`weight: 0.05`) without invalidating or interrupting the quiz.

### D. Input Fields & Cache Hardening
- **Autofill Disabled:** Input fields use `contentType = ContentType.None` / `importantForAutofill="no"`.
- **Personalized Learning Disabled:** Input fields configure `autoCorrectEnabled = false`, `KeyboardType.Text`, and `privateImeOptions = "nm"` (`EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING`).
- **Zero Logging:** Question text, options, and student typed responses are never logged to Logcat, Console, or Timber.
- **No-Store Cache Control:** Quiz API responses carry `Cache-Control: no-store, no-cache, must-revalidate`.

---

## 4. Software Keyboard Clipboard-History Limit (Documentation)
**Platform Limitation:**
Modern Android virtual keyboards (such as Gboard, Samsung Keyboard, and Microsoft SwiftKey) manage an internal, private clipboard history within their own isolated application processes. The Android OS SDK provides no public API allowing third-party applications to inspect, clear, or modify an external keyboard's private clipboard history cache.

**ThinkBuddy Mitigations:**
1. ThinkBuddy invokes `ClipboardManager.clearPrimaryClip()` on quiz entry, pause, and exit to immediately purge the operating system's system-wide primary clipboard.
2. Setting `IME_FLAG_NO_PERSONALIZED_LEARNING` (`privateImeOptions = "nm"`) explicitly signals compliant virtual keyboards not to store, learn, or suggest text entered into assessment fields.
