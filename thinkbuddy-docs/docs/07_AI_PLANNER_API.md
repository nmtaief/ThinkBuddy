# 07 – AI Planner API (contract `ai-planner/v1`)

The AI Planner is a **separate, stateless service** that proposes each student's routine, quizzes, and revision from their needs, weaknesses, and strengths.
Rule of the whole design: **the AI proposes, the backend disposes.** The ThinkBuddy core backend validates every proposal against hard rules, applies only what passes, and falls back to the deterministic planner otherwise.

## 1. Roles
| Component | Owns | Never does |
|---|---|---|
| Core backend | Students, settings, plans, tasks, mastery, signals, quiz grading, answer keys, notifications | Trusts AI output without validation |
| AI Planner service | Turning a snapshot into proposals (routine, quiz specs, revision queue, question drafts, explanations) | Reads/writes the ThinkBuddy database, sees identities, grades assessed quizzes, holds answer keys, messages families |
| Deterministic planner (P03) | Fallback and validation baseline | |

## 2. What the AI may and may not decide
| The AI decides | The AI can never |
|---|---|
| Which subjects, chapters, concepts on which days | Exceed daily budgets, study windows, or admin/parent limits |
| Minutes per task (within limits) | Change parent-locked values |
| Mix of study / revision / practice / homework | Touch completed or pinned tasks |
| Quiz composition: concepts, difficulty, count, item mix | Schedule on blackout days or after a subject's exam |
| Revision queue order and intervals | Invent chapters, pages, or IDs |
| Suggested priority changes (with evidence) | Apply priority/minute changes in `suggest` mode without parent approval |
| Short explanations of its choices | Receive names, phone numbers, school, chat text, or any free text about the child |

## 3. Endpoints (service side)
| Method and path | Purpose | Timeout |
|---|---|---|
| `GET /healthz` | Liveness | 2 s |
| `GET /v1/contract` | Supported contract versions, model info | 2 s |
| `POST /v1/plans/propose` | Routine for a horizon (day by day tasks) | 20 s |
| `POST /v1/quizzes/propose` | Quiz specifications (what to ask, not the questions) | 15 s |
| `POST /v1/revision/propose` | Revision queue and due dates | 15 s |
| `POST /v1/questions/draft` | Draft questions grounded in supplied textbook chunks | 30 s |
| `POST /v1/insights/explain` | Parent-facing reasons per subject, in Bangla or English | 15 s |

All requests are idempotent via `idempotency_key`. Calls come from backend workers (Celery), never directly from clients.

## 4. Common envelope (every request)
| Field | Meaning |
|---|---|
| `contract_version` | e.g. `ai-planner/v1.0` |
| `request_id`, `idempotency_key` | Tracing and safe retries |
| `student_ref` | Pseudonymous ID (not the user ID), rotated per environment |
| `as_of` | Current local timestamp and time zone (never read from the AI service clock) |
| `locale` | `bn` or `en` for any text |
| `mode` | `manual` (insights only), `suggest`, `auto_within_limits` |
| `seed` | Optional, for reproducible output |

## 5. Request snapshot for `plans/propose`
| Block | Contents |
|---|---|
| `profile` | class level, group, medium (Bangla or English version), time zone |
| `limits` | Resolved hard limits: daily minute bounds per day type, max block length, latest end time, min block, max tasks per day, max consecutive days per subject, mock-quiz cap, change caps per cycle |
| `settings` | Resolved parent settings: minutes per day type, study window, unavailable blocks, priorities, **locked fields list**, rest weekday |
| `calendar` | Each date in the horizon: day type, available minutes, zero-day reason code |
| `exams` | Per subject: date, weightage, target grade |
| `syllabus` | Per subject, ordered chapters: chapter ID, printed page range, difficulty factor, included flag, concept IDs |
| `progress` | Completed slices, missed tasks, rolled-forward tasks, spaced-revision state per slice (box, last seen, due) |
| `mastery` | Per subject, chapter, concept: score 0 to 1, confidence, last seen |
| `signals` | Summaries only: quiz accuracy and speed vs expected, repeated AI-chat topics by concept, skipped tasks, self-rated difficulty |
| `pinned` | Tasks that must not change (completed, started, or fixed by parent) |
| `previous_plan` | Version and a compact summary, for stability |
| `options` | Horizon length, planning goal (`balanced`, `exam_focus`, `catch_up`) |

Never sent: names, phone numbers, email, school, free text, chat content, device IDs.

## 6. Response from `plans/propose`
| Field | Meaning |
|---|---|
| `proposal_id`, `contract_version`, `model_info` | Provenance |
| `confidence` | 0 to 1, plus `data_sufficiency` (`low`, `ok`) |
| `days[]` | Per date: tasks |
| task fields | `temp_id`, `type` (`study`, `revision`, `homework`, `practice`, `quiz`, `broad`, `buffer`), `subject_id`, `chapter_id`, `page_start`, `page_end` (printed pages), `concept_ids`, `minutes`, `reason_code`, `spaced_interval_days` (revision), `quiz_request_ref` |
| `quiz_requests[]` | Kind (`diagnostic`, `daily`, `review`, `chapter`), target concepts, item count, difficulty mix, item types, mode (`practice`, `assessed`), time limit |
| `priority_suggestions[]` | Subject or chapter, current level, suggested level, evidence codes. Never applied in `suggest` mode without parent approval |
| `rationale` | Structured reason codes with short localized text per subject |
| `warnings[]` | e.g. `COVERAGE_AT_RISK`, `LOW_DATA`, `EXAM_TOO_CLOSE` |

Reason codes (initial set): `WEAK_CONCEPT`, `EXAM_APPROACHING`, `SPACED_REVIEW_DUE`, `STRENGTH_MAINTENANCE`, `CATCH_UP_MISSED`, `PRIORITY_PARENT`, `LOW_DATA_DEFAULT`, `RECENT_ERRORS`, `REPEATED_QUESTIONS`, `BALANCE_ROTATION`.

## 7. Other endpoints (fields)
| Endpoint | Request adds | Response |
|---|---|---|
| `quizzes/propose` | Target date, kind, concept pool, question-bank availability counts | Quiz spec(s) only |
| `revision/propose` | Revision state, mastery, window | Revision items (concept or question refs, box, due date) |
| `questions/draft` | Source chunks (textbook text, printed page, IDs), type mix, difficulty, language | Draft questions with options, answer key, explanation, rubric, `source_chunk_ids`, status `draft` |
| `insights/explain` | Mastery trends, plan diff summary | Short, positive, localized explanation per subject; never labels a child as weak or bad |

Drafted questions enter the question bank as `ai_generated` / `draft`, pass a validation step, and are used for practice only until approved (see `06_ADAPTIVE_ENGINE.md §6`). Answer keys never leave the backend.

## 8. Backend validation (applied to every proposal)
| Code | Rule | Severity | Action on violation |
|---|---|---|---|
| V01 | Schema and contract version valid, size caps respected | Hard | Reject, fall back |
| V02 | Day total minutes within the day's budget | Hard | Repair by trimming lowest-priority tasks, else reject |
| V03 | Tasks inside the study window and outside unavailable blocks | Hard | Reject |
| V04 | No tasks on blackout days | Hard | Drop tasks, warn |
| V05 | No study for a subject after its exam date | Hard | Drop tasks |
| V06 | Chapter, concept, and page IDs exist; page ranges inside chapter's printed pages and contiguous | Hard | Reject |
| V07 | Chapter order respected unless parent allowed reordering | Hard | Reject |
| V08 | Completed and pinned tasks unchanged | Hard | Reject |
| V09 | Locked settings untouched; priority change at most one level per cycle | Hard | Drop suggestion |
| V10 | Min block length, max tasks per day, mock-quiz cap | Hard | Repair or reject |
| V11 | Rotation limit per subject | Soft | Warn |
| V12 | Minimum share for every active subject; coverage vs deterministic plan not worse | Soft | Warn, may fall back |
| V13 | Quiz requests within caps and question availability | Hard | Drop request |
| V14 | Rationale text length-capped, escaped, no personal data | Hard | Replace with template |
| V15 | Horizon dates inside allowed range | Hard | Reject |

Rejected or heavily repaired proposals trigger the deterministic planner for that student; the reason code is logged. Repairs are limited to trimming and dropping; the backend never invents content.

## 9. Autonomy modes
| Mode | Routine content within existing limits | Priority changes, minute changes, exam strategy |
|---|---|---|
| `manual` | Deterministic planner only; AI provides insights | Parent only |
| `suggest` (default) | Applied automatically after validation | Stored as suggestions; parent approves |
| `auto_within_limits` | Applied automatically | Applied automatically within limits and caps; parent notified, one tap to undo |

Parent-locked values are never changed in any mode.

## 10. Reliability
- Calls are made by background workers; users never wait on the AI.
- Timeouts per endpoint above; 2 retries with backoff; the same idempotency key on retries.
- Circuit breaker: opens after 5 failures in 60 s, probes after 30 s.
- Global kill switch, per-class-band rollout, per-student override.
- **Shadow mode:** the AI runs beside the deterministic planner and its output is only scored, not applied.
- Deterministic fallback is always available.
- Metrics: acceptance rate, repair rate, fallback rate, latency, cost per student per day, coverage vs baseline, parent override rate, plan churn.

## 11. Security and privacy
- Service-to-service authentication (mTLS or short-lived signed token with a service identity); internal network only.
- Pseudonymous `student_ref`; no free text about the child; textbook chunks are treated as data, not instructions.
- AI service stores no payloads beyond a short retention window (default 7 days, debugging only) and sends nothing to hosted LLMs that identifies a child. Confirm each provider's data-use terms before enabling.
- All outputs are untrusted input to the backend (V01 to V15).
- Audit log in the backend for every applied proposal: provider, model and contract versions, settings version, validation outcome.

## 12. Rollout gates
| From to | Gate |
|---|---|
| Offline simulation | 0 hard violations across 1,000 synthetic students; coverage at least equal to the deterministic planner |
| Shadow | 2 weeks, hard-violation rate 0 after repair, fallback rate under 2%, latency within targets |
| `suggest` | Parent acceptance and override rates reviewed by you; no safety complaints |
| `auto_within_limits` | Opt-in per family after at least 4 weeks of good `suggest` results |

## 13. Reference design for the AI Planner service
Stateless inference service with these stages:
1. **Feature builder:** turns the snapshot into per-subject and per-chapter features.
2. **Need model:** estimates need = mastery gap, forgetting risk, exam proximity, weightage, target-grade gap, confidence. Tiers:
   - v0 rule-based scoring (works from day one),
   - v1 mastery-aware (Elo or Bayesian knowledge tracing, with class-level priors for cold start),
   - v2 learned from aggregated, consented data (for example gradient-boosted models predicting the chance of a correct answer after N days). Do not build v2 until you have thousands of student-days.
3. **Scheduler:** a constraint solver (for example OR-Tools CP-SAT) maximizes expected learning gain subject to the same hard rules as section 8, so proposals are valid by construction. A greedy fallback is used if the solver times out.
4. **Quiz and revision composer:** concept sampling weighted by need, with difficulty ramp and variant support.
5. **Question drafting (LLM via LiteLLM):** grounded in supplied chunks, structured output, validated by a second pass.
6. **Explanation writer:** templates in Bangla and English; the LLM may polish wording but facts come from reason codes.
Data stays in the backend; the AI service remains stateless, and population priors are updated offline.

## 14. Open decisions
- Who operates the AI service and where it runs (same VM or separate).
- Which LLM provider is allowed for drafting and explanations.
- Whether parents see the AI's reasons per task or only per subject (default: per subject).
