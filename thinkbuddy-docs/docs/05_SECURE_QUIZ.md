# 05 – Secure Quiz System

## 1. Honest scope
No app can fully stop a student from photographing a screen with a second device or asking a friend. The goal is to **remove the easy paths** (screenshot, Circle to Search, copy-paste into Gemini/ChatGPT, in-app AI help), **make cheating detectable**, and **make the result less valuable to cheat on**. Defence in depth: server rules first, client hardening second, analytics third.

## 2. Threats and controls
| Threat | Control (layer) |
|---|---|
| Copy question text into an AI | Non-selectable text, clipboard blocked/cleared in quiz screens (client); questions are served one at a time (server); variants make copied text less reusable |
| Circle to Search / screenshots / screen recording | Android `FLAG_SECURE` on all quiz windows (blocks screenshots, recents thumbnails, and most screen-capture assistants); iOS: detect capture and screenshot notifications and hide content on capture (client) |
| Assistant overlays / split-screen | Detect multi-window, PiP, overlay and focus loss; log `attempt_events`; configurable auto-pause or invalidate after N events (client + server) |
| Using the in-app AI during a quiz | Chat endpoint rejects while the student has an `active` assessed attempt; logs `chat_attempt` (server) |
| Reading answers from network/local storage | Answer keys never leave the server before item submission; correctness for assessed mode is withheld until submit (server) |
| Replay / tampering / scripted clients | Short-lived `attempt_token`, per-item server-issued nonce, TLS pinning (optional), Play Integrity / App Attest verdict at attempt start (server + client) |
| Taking time off the clock | Server-side deadline (`deadline_at`) and per-question timers; the client timer is cosmetic (server) |
| Same quiz shared among friends | Per-student randomized question order, option order, and question **variants** from `variant_group_id`; pool larger than quiz length (server) |
| Rooted/emulated devices | Integrity verdict stored in `devices.integrity_status`; assessed mode blocked or downgraded to practice (server) |
| Odd behaviour (too fast, perfect streaks, answers right after app-switch) | `integrity_score` computed from events and timing; low score flags the attempt for parent/teacher and excludes it from mastery (server) |

## 3. Modes
- **Practice mode:** immediate feedback, explanations allowed, AI help allowed. Counts lightly toward mastery.
- **Assessed mode:** secure rules above; correctness hidden until submit; counts fully toward mastery and parent reports.
Daily quiz and 3-day review quiz default to **assessed** on mobile app builds that pass integrity; web is **practice-only** because browsers cannot block screenshots, clipboard, or assistants reliably.

## 4. Attempt state machine
`created → active → submitted` or `→ expired` (deadline passed, auto-submitted with answers so far) or `→ invalidated` (integrity rule tripped).
Rules:
- One active assessed attempt per student at a time.
- Starting requires: online, valid integrity verdict, within allowed window, not already completed for the day.
- Items served one by one; each answer must reference the current position and nonce.
- Late or out-of-order answers are rejected with stable error codes.
- On submit/expiry: grade, write `learning_signals`, update `mastery`, then unlock `/review`.

## 5. Question serving rules
- Response bodies for questions contain **no** answer keys, explanations, or rubric.
- Options are sent with opaque IDs, not letters in key order.
- `GET /attempts/{id}/review` is the only route that returns keys/explanations, and only for `submitted` attempts.
- Automated test: crawl every student-accessible endpoint during an active attempt and assert no key material appears.

## 6. Client behavior (Android MVP)
- Quiz screens set `FLAG_SECURE`; text uses non-selectable composables; clipboard cleared on entering and leaving.
- Lifecycle observers report background/foreground, window focus loss, multi-window mode, and overlay detection to `/attempts/{id}/events`.
- Grace policy comes from `/client/config` (e.g., 1 warning, then pause, then invalidate) so you can tune without app updates.
- Never store the correct answer or full question bank locally.
- On a rooted/emulator verdict, show a clear message and offer practice mode.

## 7. Privacy and fairness
- Tell students and parents what is monitored (events, not screen content or camera).
- Invalidation is never silent: the student sees why; the parent sees the flagged reason.
- A false positive path: parent can mark an attempt as "allowed" (e.g., phone call interruption), and the system excludes it from integrity penalties.

## 8. Acceptance tests
- Answer-key leakage test passes.
- Client clock tampering does not extend deadline.
- Chat is blocked during an active assessed attempt.
- Replaying an old `attempt_token` fails.
- Two students get different orders/variants for the same quiz.
- Web build cannot start an assessed attempt.
