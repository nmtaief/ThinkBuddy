# 08 – Client Platform Guide (web, Android, iOS; phone, tablet, desktop)

## 1. Build order
1. **Web app** (P08): one codebase for phone, tablet and desktop browsers.
2. **Android** (P08a): phone and tablet.
3. **iOS** (P08b): iPhone and iPad.

Why web first: fastest iteration, no store review, parents often use laptops, and it validates every backend contract before native work starts.

Consequence you must plan for: **browsers cannot enforce secure quizzes.** Assessed quizzes are available only in the native apps (Android first, then iOS). Until Android ships, daily and review quizzes on web run in practice mode, which counts less toward mastery (see `05_SECURE_QUIZ.md §3`). The web app shows assessed quizzes as "available in the ThinkBuddy app".

## 2. Capability matrix
| Capability | Web | Android | iOS |
|---|---|---|---|
| Student and parent features | Full | Full | Full |
| AI chat with streaming and citations | Yes | Yes | Yes |
| Practice quizzes | Yes | Yes | Yes |
| Assessed quizzes | No (practice only) | Yes (`FLAG_SECURE`, Play Integrity) | Yes, best effort (capture detection, App Attest) |
| Push notifications | Later (web push) | FCM | APNs (via FCM or direct) |
| Offline | Today's plan cached | Today's plan cached (Room) | Today's plan cached |
| Tablet / large screen | Responsive, two-pane | Adaptive, two-pane | iPad split view, multitasking |
| Device attestation | None | Play Integrity | App Attest |

## 3. Screen inventory (shared across platforms)
**Student:** Today, Plan timeline (week and month), Task detail (guideline, pages, minutes), Revision, Quiz runner (practice or assessed), Broad answer (typed or photo), AI chat (streaming, citation chips, current-page context), Progress ("needs practice" and "not enough data" wording only), Change request, Settings (language, notifications).

**Parent:** Children overview, Child dashboard (completion, streak, time, mastery, upcoming exams, review quiz results), Study setup (subjects, syllabus, chapter order, exam dates, minutes for school days and holidays, study window, recurring unavailable time, observances to block, custom blackout dates, subject priorities, rest weekday, adaptive mode), AI suggestions and auto-adjustments with one-tap undo, Student change requests, Quiz review after submission, Notifications and preferences, Link a child (code or QR), Plan warnings (for example coverage at risk).

**Admin** (internal web panel, separate and later): holiday calendar, observance catalog, planner policies, rollout, question bank, shadow metrics.

## 4. Responsive and adaptive rules (all platforms)
| Size class | Width | Layout |
|---|---|---|
| Compact (phone) | under 600 | Single pane, bottom navigation |
| Medium (small tablet, large phone landscape) | 600 to 839 | Navigation rail, optional two panes |
| Expanded (tablet, desktop) | 840 and above | Navigation rail or sidebar, two or three panes, capped content width |

- **Two-pane patterns on tablets and desktop:** plan list and task detail, chat sessions and conversation, children list and dashboard, question list and explanation (review).
- Orientation change and window resize keep state and scroll position.
- Touch targets at least 48 dp (Android and web) or 44 pt (iOS); hardware keyboard and mouse supported on web, iPad and Android tablets.
- Images: request the `sm`, `md` or `lg` variant by size class.
- Bangla typography: body at least 16 px, line height at least 1.5, fonts with full conjunct support (for example Noto Sans Bengali or Hind Siliguri); test long strings and mixed Bangla and English.
- **Multitasking:** study screens work in split view and multi-window. Assessed quizzes require full screen: detect multi-window (Android) or reduced window size (iPad Split View, Slide Over, Stage Manager), warn, pause or log per server policy in `/client/config`.
- Stylus or Apple Pencil is welcome for broad answers; the result is uploaded as an image.

## 5. Shared design tokens
One token file (`/design/tokens.json`: colors, spacing, radii, typography, elevation, light and dark) is the single source; each platform generates its theme from it. Default language Bangla, with English switch. Math: KaTeX on web; test the chosen renderer on real Class 9 and 10 formulas on each platform.

## 6. Networking and data
- Generate clients from `docs-generated/openapi.json`; never hand-write endpoint code that can drift.
- Send `X-Client-Platform`, `X-Client-Form-Factor` (derived from the size class), `X-App-Version`, `X-Device-Id`, and `Accept-Language`.
- Load `/client/config` at startup and on resume; render limits, observance catalog, quiz mode, and feature flags from it. Honor `min_supported_version`.
- Chat uses SSE with the non-stream fallback. Writes use idempotency keys and retry safely.
- Token storage: web uses httpOnly cookies behind a server-side layer (no tokens in browser storage); Android uses Keystore-backed storage; iOS uses Keychain.

## 7. Security and privacy (clients)
- No secrets in client code. First-party analytics only, with no third-party trackers, ad SDKs, or identifiers of children.
- Collect the minimum: camera only when the student chooses to photograph an answer; no location.
- Parental consent screen at onboarding; data export and deletion entry points for parents.
- Web: strict Content Security Policy, CSRF protection for cookie sessions, secure headers.
- Never cache answer keys or full question banks.

## 8. Quality bars
- Low-end devices (2 GB RAM Android) and 3G: web largest content paint under 3 s on a mid-range phone over 4G, JavaScript budget set and enforced in CI; native cold start under 3 s on a low-end phone.
- Accessibility: labels in Bangla and English, contrast, focus order, dynamic text size.
- Test matrix: phone, small tablet, large tablet, desktop; Bangla and English; light and dark; slow network; offline.

## 9. Release
Web: staging, then production behind the reverse proxy. Android: internal test track first. iOS: TestFlight first. Every build reports its version to `/client/config`.
