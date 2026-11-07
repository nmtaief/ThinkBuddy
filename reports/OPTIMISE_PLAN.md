# ThinkBuddy Optimisation Plan — `chore/optimise`

> Generated: 2026-11-07  
> Branch: `chore/optimise` (from `chore/cleanup-and-claude-guide` via `git stash + checkout -b`)  
> Measurement commands are shown with each item so before/after numbers can be reproduced.

---

## Ranked Items (max 15)

### Priority 1 — Slow Endpoints: query count / blocking work

---

#### 1 — `execute_student_plan_regeneration`: double Mastery query (N+1 on planner hot path)

| | |
|---|---|
| **File** | [`core/planner/router.py`](../core/planner/router.py#L174-L276) |
| **Problem** | `Mastery` is queried **twice** in the same function: first at L174 (`select(Mastery.chapter_id, Mastery.score)`) to build `student_mastery_map`, then again at L266 (`select(Mastery)`) to build the full `mastery_records` list for the planner. Both rows originate from the same table with the same `student_id` filter. This costs one extra DB round-trip on every plan regeneration (upsert-study-setup, task-update-triggered regen, etc.). |
| **Measured** | 2 sequential `SELECT mastery …` queries per plan-regen call. Tool: `db_query_count_ctx` already tracked in `core/common/database.py`. |
| **Fix** | Fetch the full `Mastery` objects once; derive `student_mastery_map` from the same result set. |
| **Risk** | Low — pure read consolidation, no logic change. |

---

#### 2 — `get_today_payload` (Today endpoint): separate `StudySetup` query is avoidable

| | |
|---|---|
| **File** | [`core/planner/router.py`](../core/planner/router.py#L1142-L1273) |
| **Problem** | The endpoint already JOINs `Task → PlanDay → Plan → StudySetup` in the tasks query (L1182–1194). Then at L1231 it fires a **separate** `SELECT StudySetup WHERE student_id=…` just to compute exam countdowns. The `exam_date` column is already available on the `StudySetup` rows that come back from the first JOIN. Additionally, the active-plan provenance query at L1242 (`SELECT Plan WHERE student_id=… ORDER BY version DESC`) loads a full `Plan` record just to read two string fields. Total: **4 DB queries** where **2** are sufficient. |
| **Measured** | 4 queries counted via `db_query_count_ctx`. Target: 2. |
| **Fix** | (a) Collect `(subject, exam_date)` from the task JOIN result. (b) Pull `Plan.provider`, `Plan.generation_reason`, and `Plan.params` as a `.only(columns)` or `.with_only_columns()` narrowed SELECT. |
| **Risk** | Low. The countdown dict construction changes slightly; the response schema stays identical. |

---

#### 3 — `exchange_token` (sign-in): `get_auth_provider()` called on every request with no caching

| | |
|---|---|
| **File** | [`core/auth/router.py`](../core/auth/router.py#L78) · [`core/auth/provider.py`](../core/auth/provider.py) |
| **Problem** | `get_auth_provider()` is a module-level factory called inside `exchange_token`, `reauthenticate_user`, and presumably `gateway/router.py`. If the factory constructs a new Firebase Admin SDK client object on each call (common pattern), that is wasted CPU + memory on every sign-in. Firebase Admin SDK clients are designed to be singletons. |
| **Measured** | Static analysis: factory called 2–3× per sign-in flow (exchange + re-auth). Needs profiling with `cProfile` or `time.perf_counter` around `provider.verify_token` to confirm SDK init overhead. |
| **Fix** | Cache the provider instance at module import time (or use `functools.lru_cache(maxsize=1)`) so the Firebase Admin App is initialized once per process. |
| **Risk** | Low. Firebase Admin SDK is thread/async-safe when used as a singleton. |

---

#### 4 — `start_attempt` (quiz attempt start): two separate `Quiz` fetches on the two-step create→attest path

| | |
|---|---|
| **File** | [`core/quiz/service.py`](../core/quiz/service.py#L224) and [`core/quiz/router.py`](../core/quiz/router.py#L202) |
| **Problem** | The two-step attempt flow (`create_attempt` → `attest_quiz_attempt`) fetches `Quiz` from DB in **both** steps. `create_attempt` fetches the `Quiz` (L140), `start_attempt` fetches it again (L224). On the single-step legacy path (`start_quiz_attempt`), `is_assessed_attempt_active()` also does a full `Quiz` JOIN (L101–108), and then `start_attempt()` refetches `Quiz` again (L224). Additionally `answer_item` refetches the `Quiz` at L626 and L689 — two separate round-trips per answered question just to read `quiz.mode`. |
| **Measured** | `start_attempt` path: 3 Quiz fetches (is_active check JOIN + create_attempt fetch + start_attempt fetch). `answer_item` path: up to 2 extra Quiz fetches. |
| **Fix** | (a) Pass the already-loaded `quiz` object through `is_assessed_attempt_active → start_attempt`, or join `Quiz` once in `start_attempt` and pass it down. (b) In `answer_item`, join `Quiz` with the `attempt` in the initial query instead of a second fetch. |
| **Risk** | Medium. Requires changing method signatures; must verify no security guard is bypassed. The `mode` field on `QuizAttempt` is already mirrored from `Quiz.mode` at creation time — `attempt.mode` can be used directly at L628/L691 instead of re-fetching `Quiz`. |

---

#### 5 — `get_current_user` dependency: DB lookup on every authenticated request with no short-circuit

| | |
|---|---|
| **File** | [`core/auth/dependencies.py`](../core/auth/dependencies.py#L19-L90) |
| **Problem** | Every endpoint that depends on `get_current_user` issues a `SELECT users WHERE id=… AND deleted_at IS NULL` after JWT decode. The access token already contains `role` in the payload (emitted by `create_access_jwt`). For the vast majority of requests where the user is active and not deleted, this query adds latency for no security gain beyond the JWT signature. For high-frequency routes (chat message send, task update, Today polling), this is the single most repeated query. |
| **Measured** | 1 DB query per authenticated request. With 15-minute JWT TTL, the user record does not change meaningfully during the token lifetime for >99% of requests. |
| **Fix** | Add a **short Redis cache** keyed `user:{user_id}:status` with a TTL of `ACCESS_TOKEN_EXPIRE_MINUTES * 60` seconds (15 min, matching the JWT TTL). The cached value is a minimal JSON `{"status": "active", "role": "student", "has_parental_consent": true}`. On account suspension or consent withdrawal, Redis key is deleted (or a tombstone written) to force the next request back to DB. This preserves security: a suspended user is locked out within seconds, not hours. |
| **Risk** | Medium. Redis must be invalidated on: account status change (`status = "suspended"`, `"pending_deletion"`), consent withdrawal, and account deletion. These events already go through `privacy/service.py` and `admin/router.py` — add cache-clear calls there. Do **not** cache `has_parental_consent=False` — always re-read from DB when consent is withdrawn (or delete the key). |

---

### Priority 2 — Planner / Chat Hot Paths

---

#### 6 — `execute_student_plan_regeneration`: flush after every `PlanDay` insert in a loop

| | |
|---|---|
| **File** | [`core/planner/router.py`](../core/planner/router.py#L641-L671) |
| **Problem** | The inner loop at L651–671 calls `await db.flush()` **after each `PlanDay`** (L653). For a 60-day plan horizon across 3 subjects, this triggers ~180 sequential DB round-trips during plan write. Flushing is only needed to get the PK of `PlanDay` so it can be assigned to `Task.plan_day_id`. |
| **Measured** | For a 3-subject, 60-day plan: 3 (plans) × 60 (days) = 180 `flush()` calls → 180 round-trips just for the write phase. |
| **Fix** | Use `RETURNING id` via SQLAlchemy's `returning()` clause, or use a pre-generated UUID for `PlanDay.id` (since the ORM model uses server-default only if not provided). Assign `p_day.id = uuid.uuid4()` before `db.add(p_day)`, then use that ID directly for `Task.plan_day_id` without flushing. Batch all inserts and flush once per plan (or once total at the end). |
| **Risk** | Medium. Must verify `PlanDay.id` column accepts client-provided UUIDs (not `server_default` only). Check the Alembic migration for the column definition. No schema change required. |

---

#### 7 — `can_access_student` called redundantly in Today and Plan endpoints

| | |
|---|---|
| **File** | [`core/common/policy.py`](../core/common/policy.py#L23-L50) · [`core/planner/router.py`](../core/planner/router.py#L1149) |
| **Problem** | `can_access_student` issues a `SELECT parent_student_links WHERE parent_id=… AND student_id=… AND status=active` DB query. For student self-access, it returns early without a DB hit. But for parent access, it's one extra query. The `Today` and `Plan` endpoints both call it at the top; then if the user is the student, `current_user.id == student_id` check could have short-circuited with zero DB calls. |
| **Measured** | 0 DB queries for student self-access (already short-circuits). 1 DB query for parent access on Today + Plan each. |
| **Fix** | No change needed for the student path. For parent path: consider caching the link lookup in Redis (`parent:{parent_id}:linked_students` set, TTL 5 min, cleared on link revoke/activation). |
| **Risk** | Low for the student short-circuit path (already works). Medium for Redis caching — must invalidate on `ParentStudentLink` status changes. |

---

#### 8 — `is_assessed_attempt_active()` called twice on the chat send path

| | |
|---|---|
| **File** | [`core/chat/router.py`](../core/chat/router.py#L72) · [`core/chat/orchestrator.py`](../core/chat/orchestrator.py) |
| **Problem** | `create_chat_session` calls `orchestrator.assert_no_active_assessed_quiz(current_user.id)` (L72), and `send_chat_message` calls it again at L206. Each call issues a `SELECT quiz_attempts JOIN quizzes WHERE student_id=… AND state IN (…)`. Since a new session is created before a message is sent, both endpoints check the same condition in the same request flow. |
| **Measured** | 2 DB queries per chat-turn initiation. |
| **Fix** | The `send_chat_message` check at L206 is correct and mandatory. The `create_chat_session` check can pass a session-scoped flag forward, or the session creation can skip it since the user will check again on first message. Alternatively, cache the `is_active` boolean for 10 seconds in Redis (keyed by student_id). The worst-case security gap is 10 seconds of chat access after an assessed quiz starts — acceptable given the client also enforces the lockout. |
| **Risk** | Low-Medium. The 10-second cache window must be clearly documented. |

---

### Priority 3 — Web Bundle Size

---

#### 9 — No manual code-splitting in Vite config; all app code in one chunk (628 KB student, 551 KB parent)

| | |
|---|---|
| **File** | [`apps/student/vite.config.ts`](../apps/student/vite.config.ts) · [`apps/parent/vite.config.ts`](../apps/parent/vite.config.ts) |
| **Problem** | Both apps ship a single `index-*.js` chunk: student 628 KB, parent 551 KB (measured from `dist/assets/`). The Firebase ESM chunks (`index.esm-47bNWHSS.js` 440 KB, `index.esm-kSH3vLEB.js` 193 KB) are already split. The app bundle includes all views eagerly: `TodayMergedView`, `AIChatView`, `PracticeQuizRunner`, `ProgressView`, `BroadAnswerView`, `StudentChangeRequestView`, etc. — all loaded on initial paint. `AIChatView` alone would only be needed if the user opens the chat tab. KaTeX (`katex` dep, ~200 KB minified) is included eagerly in `MathRenderer`. |
| **Measured** | `index-DmPN5Xpv.js` = 628 KB (student); `index-B3zJDU9e.js` = 551 KB (parent). Command: `Get-Item apps/student/dist/assets/*.js \| Select-Object Name, Length`. |
| **Fix** | (a) Add `rollupOptions.output.manualChunks` in `vite.config.ts` to split `katex` into its own chunk. (b) `React.lazy()` + `Suspense` for `AIChatView`, `PracticeQuizRunner`, `ProgressView`, `BroadAnswerView`, `StudentChangeRequestView` in `App.tsx`. Each lazy chunk loads only when the user navigates to that tab. Expected reduction: ~150–200 KB from initial JS parse. (c) Same for `ParentDashboard` and `ParentProfileDrawer` in parent app. |
| **Risk** | Low. Standard Vite/React pattern. The existing tab-switching guard (`currentTab === "chat" && <AIChatView …>`) already prevents render; lazy just moves the network load too. |

---

#### 10 — `MathRenderer.tsx` loads KaTeX eagerly; `AlertCircle` imported but never used in `AIChatView.tsx`

| | |
|---|---|
| **File** | [`apps/student/src/components/AIChatView.tsx`](../apps/student/src/components/AIChatView.tsx#L3) · `MathRenderer.tsx` |
| **Problem** | `AlertCircle` is imported from `lucide-react` at L3 of `AIChatView.tsx` but never rendered. While lucide-react uses named exports and tree-shaking should eliminate it, the icon import still contributes to bundle analysis noise and could prevent full tree-shaking in edge cases. KaTeX is loaded unconditionally in `MathRenderer` even for messages with no math. |
| **Measured** | `lucide-react`: 36 icons imported total across both apps. Unused: `AlertCircle` confirmed in `AIChatView.tsx`. KaTeX: ~200 KB minified. |
| **Fix** | (a) Remove `AlertCircle` from `AIChatView.tsx` import. (b) In `MathRenderer`, check whether the content contains `$` or `$$` before calling `katex.renderToString` to avoid CPU cost on prose messages. |
| **Risk** | Negligible. Import removal is safe. The math heuristic check is a cheap string scan. |

---

### Priority 4 — Dead Code and Unused Imports

---

#### 11 — 36 unused imports across `core/`, `gateway/`; 1 redefined import (`StudentProfile`)

| | |
|---|---|
| **File** | Multiple — full list from `ruff check --select=F401,F811`. Key offenders: |
| **Problem** | (a) `core/planner/router.py` L31: `generate_student_plan` imported but unused (the router delegates to `execute_student_plan_regeneration` instead). L33: `StudentProfile` **redefined** (F811) — it's already imported from `core/families/models` at L25 via the `from core.families.models import …` block; the second import at L33 replaces the first silently. L48: `Mastery` imported at module level but only used inside function bodies via local `from … import`. (b) `gateway/router.py` L68–77: 8 privacy schema types imported and not used in the gateway (they're only needed in core). (c) `core/planner/rollout.py` L13: `uuid` unused; L17: `select` unused; L18: `insert` unused. (d) `core/common/config.py` L3: `AliasChoices` unused. (e) `core/quiz/builder.py` L20: `UTC` unused. |
| **Measured** | `python -m ruff check core/ gateway/ workers/ --select=F401,F811 --statistics` → 36 F401 + 1 F811. |
| **Fix** | `python -m ruff check core/ gateway/ workers/ --select=F401,F811 --fix` (auto-fix all 36). Then verify no `NameError` at import time. |
| **Risk** | Low. Ruff auto-fix only removes imports, never code that uses them. The `StudentProfile` F811 fix removes the duplicate import — the first import from `core/families/models` already covers it. |

---

#### 12 — `core/main.py` mounts every router **twice** (once at `/v1/…` and once at root)

| | |
|---|---|
| **File** | [`core/main.py`](../core/main.py#L158-L169) |
| **Problem** | Lines 158–169 include each router twice: once with `prefix="/v1"` and once without. This doubles the OpenAPI route count, doubles FastAPI's routing overhead, and doubles the number of routes in middleware matching. The root-prefixless mounts exist for "internal compatibility" per the comment, but all documented endpoints use `/v1`. If no route under the root prefix is called in production, this doubles route-matching cost for no value. |
| **Measured** | 18 routers × 2 mounts = 36 router registrations. FastAPI iterates all routes for each request in middleware. |
| **Fix** | Audit whether any internal service (gateway, workers) calls the root-prefixed paths. If not, remove the second `app.include_router` block. If some paths are still needed, alias only those specific paths. |
| **Risk** | Medium. This requires confirming gateway and worker call sites. Removing without auditing could break internal routing. **Do not apply until gateway/router.py and worker call sites are verified.** |

---

#### 13 — `PERF401` / `PERF403`: 7 manual list/dict comprehensions that copy data twice

| | |
|---|---|
| **File** | Various in `core/` — reported by `ruff --select=PERF401,PERF403` |
| **Problem** | 5 `PERF401` (manual list-comprehension using `for` + `append`) and 2 `PERF403` (manual dict-comprehension using `for` + `dict[k] = v`). These are minor but accumulate on hot paths. |
| **Measured** | `ruff check --select=PERF --statistics` → 5 PERF401, 2 PERF402 (incorrect dict iter), 2 PERF403. |
| **Fix** | Manual rewrite to list/dict comprehensions. `ruff --select=PERF401,PERF402 --fix` handles some automatically. |
| **Risk** | Negligible. Purely syntactic. |

---

#### 14 — Android: `BengaliDigits.kt` utility appears to be unused in production code

| | |
|---|---|
| **File** | [`android/app/src/main/java/com/thinkbuddy/app/core/utils/BengaliDigits.kt`](../android/app/src/main/java/com/thinkbuddy/app/core/utils/BengaliDigits.kt) |
| **Problem** | Static analysis (reading `MainActivity.kt`, `TodayScreen.kt`, `ChatViewModel.kt`) shows no import of `BengaliDigits`. Needs `grep` confirmation across all Kotlin sources. If confirmed unused, it adds compilation overhead and APK size for no benefit. |
| **Measured** | Needs: `Select-String -Path android/…/**/*.kt -Pattern "BengaliDigits" -Recurse`. |
| **Fix** | Delete file if confirmed unused. |
| **Risk** | Low if confirmed by grep. Do not delete until confirmed. |

---

#### 15 — `SIM102` / `SIM114`: 18 collapsible/mergeable `if` branches across core

| | |
|---|---|
| **File** | Various — reported by `ruff --select=SIM102,SIM114` |
| **Problem** | 13 `SIM102` (nested `if` that can be collapsed with `and`) and 5 `SIM114` (`if` with identical arms). Minor readability and very minor performance issue (one fewer branch evaluation). |
| **Measured** | `ruff --select=SIM102,SIM114 --statistics` → 13 + 5 = 18 occurrences. |
| **Fix** | `ruff check --select=SIM102,SIM114 --fix` for the auto-fixable ones. Manual review for SIM102 where the nesting is intentional (e.g., early-exit guard style). |
| **Risk** | Low. Must not collapse `if` guards that have different side-effects (e.g., logging) between the outer and inner condition. |

---

## Unnecessary / Possibly Redundant Files

> These files are **not deleted by this plan**. They are listed for review only.

| File | Reason |
|---|---|
| `docs-generated/openapi.json` | Auto-generated from code. Should not be committed; belongs in CI artifact, not source tree. Adds diff noise. |
| `backups/` directory | Appears to contain one-off backup copies of source files. Likely never read by any entry point. |
| `thinkbuddy-docs/` | Architecture prompt pack used during initial build. No runtime dependency. Could live outside the repo or in a `docs/` archive sub-folder. |
| `design/` | Static design assets; not referenced by any build or runtime path. |
| `android_phone_auth.png`, `android_phone_today.png`, `android_tablet_auth.png`, `android_tablet_today.png` | Screenshot images at repo root. Not referenced in code. |
| `apps/student/dist/` and `apps/parent/dist/` | Build output committed to source tree. Should be in `.gitignore`. |
| `web/scripts/verify_mobile_optimizations.mjs`, `web/scripts/verify_monorepo.mjs` | Untracked verification scripts — unclear if they are needed in CI or are one-off. |
| `core/reviews/router.py` | Contains only a single stub route. If the teacher-review feature is permanently feature-flagged off, this router adds routing overhead for a dead path. |
| `core/revision/router.py` | Same concern as reviews — appears to be a thin stub. |

---

## Implementation Order (Step 2, after your approval)

1. **Commit 1**: Items 11+15 — `ruff --fix` unused imports and collapsible ifs (zero risk, auto-verified)
2. **Commit 2**: Item 1 — merge double Mastery query in `execute_student_plan_regeneration`
3. **Commit 3**: Item 2 — Today endpoint query reduction (4 → 2 queries)
4. **Commit 4**: Item 6 — batch PlanDay/Task inserts (remove per-row flush)
5. **Commit 5**: Item 4 — answer_item Quiz re-fetch removal (use `attempt.mode`)
6. **Commit 6**: Item 3 — provider singleton cache
7. **Commit 7**: Item 9+10 — Vite manual chunks + React.lazy + dead import removal
8. **Commit 8**: Item 12 — dual router mount audit + removal (pending gateway callsite review)
9. **Commit 9**: Item 5 — Redis user-status cache (most invasive; last)
10. Items 7, 8, 13, 14 — incremental, can be interleaved

---

## Measurement Commands

```bash
# Backend query count (add to test or manual curl with DEBUG=1):
# db_query_count_ctx is exposed via core/common/database.py

# Ruff issues:
python -m ruff check core/ gateway/ workers/ --select=F401,F811,SIM,PERF --statistics

# Bundle sizes (before / after):
Get-Item apps/student/dist/assets/*.js | Select-Object Name, @{N='KB';E={[math]::Round($_.Length/1KB,1)}}
Get-Item apps/parent/dist/assets/*.js  | Select-Object Name, @{N='KB';E={[math]::Round($_.Length/1KB,1)}}

# Android APK size:
# cd android && ./gradlew assembleDebug
# Get-Item app/build/outputs/apk/debug/app-debug.apk | Select-Object Length

# Backend tests (Docker required):
# pytest -q --tb=short -x (zero skips required)

# Web lint + build:
# npm --workspace=apps/student run build
# npm --workspace=apps/parent run build

# Android unit tests:
# cd android && ./gradlew testDebugUnitTest
```

---

> **Waiting for your approval before making any code changes.**

