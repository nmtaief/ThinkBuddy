# ThinkBuddy – Architecture & Antigravity Prompt Pack

This pack tells Antigravity (and you) **what to build, in what order, and what "done" means**.
Nothing here is code. It is architecture, contracts, and prompts.

## How to use with Antigravity
1. Create a monorepo. Copy this whole folder into it as `/thinkbuddy-docs` (keep the structure).
2. Copy `AGENT_RULES.md` into the repo's agent rules location (Antigravity workspace rules / `GEMINI.md`) so every agent session reads it.
3. Run prompts **in order** (`prompts/P00` → `P10`). Each prompt tells the agent which docs to read first.
4. After each prompt: run the acceptance checks listed in that prompt before starting the next one.
5. Do not paste several prompts at once. One prompt = one reviewable pull request.

## Folder map
| File | Purpose |
|---|---|
| `AGENT_RULES.md` | Standing rules for every agent session |
| `docs/01_ARCHITECTURE.md` | Components, stack decisions, request flows |
| `docs/02_PRODUCT_FLOWS.md` | Roles, permissions, and the full student/parent learning loop |
| `docs/03_DATA_MODEL.md` | Tables and relationships |
| `docs/04_API_CONTRACT.md` | API conventions, endpoints, SSE events, multi-platform rules |
| `docs/05_SECURE_QUIZ.md` | Anti-cheat design (what is and is not achievable) |
| `docs/06_ADAPTIVE_ENGINE.md` | Planner, mastery, spaced revision, weak-point logic |
| `prompts/P00…P10` | Build prompts, in order |

## Build order (milestones)
| # | Prompt | Result |
|---|---|---|
| P00 | Repo + infra scaffold | Docker Compose boots Postgres, Redis, gateway, core API |
| P01 | Auth, roles, family linking | Parent + Student login, linking, devices |
| P02 | Curriculum + content ingestion | Books/chapters/chunks from Knowledge Factory output |
| P03 | Planner | Syllabus, exam date, chapter order → weekly plan |
| P04 | Question bank + secure quiz engine | Server-controlled quizzes |
| P05 | RAG chat with streaming | Cited answers over SSE |
| P06 | Progress, mastery, adaptive revision | Daily revision/HW/quiz generation |
| P07 | Parent dashboard APIs + notifications | Progress, controls, push |
| P08 | Android app (Kotlin/Compose) | Student + Parent app, phone and tablet layouts |
| P09 | Teacher review + premium (flagged off in beta) | Ready but disabled |
| P10 | Hardening, observability, deploy | Staging deploy, load/security checks |

## Decisions I made for you (change if you disagree)
These are defaults so Antigravity never has to guess. Each can be flipped without redesign.

1. **One language on the server: Python/FastAPI.** The RAG, embeddings, and LLM tooling are all Python-first. Using NestJS for the core backend would add a second language for little gain.
2. **Modular monolith for the core backend**, plus a thin gateway and a separate RAG module. Split into more services only when load demands it.
3. **pgvector for MVP**, behind a `VectorStore` interface so Qdrant (which your Knowledge Factory doc mentions) can replace it later.
4. **Multilingual embeddings are mandatory.** `bge-small-en-v1.5` and `all-MiniLM-L6-v2` are English-only and will retrieve Bangla text badly. Use `BAAI/bge-m3` or `multilingual-e5` (self-hosted) or a hosted multilingual embedding API. Verify on a Bangla retrieval test set before committing.
5. **LLM via LiteLLM to a hosted frontier model first.** Small self-hosted models (Llama 3 8B, Mistral 7B) are weak in Bangla. Self-host only after you have measured quality.
6. **Auth: Firebase Auth (phone OTP + Google), behind an `AuthProvider` interface.** Phone OTP is the norm in Bangladesh. The backend verifies the provider token and keeps its own user table.
7. **Students are minors (Class 6–8).** Parent-first onboarding: the parent creates the family, adds the child, and controls the link. This also protects you on consent.
8. **Teacher role exists in schema and RBAC but is feature-flagged off in beta.**
9. **Parents see progress, scores, weak points, and time spent. They do not see raw chat transcripts by default.** (Configurable later.)

## Open questions (defaults are used until you answer)
- Can a student propose a syllabus/exam change, or only a parent edit it? *Default: parent edits; student can request.*
- Quiz on web: allowed for assessed quizzes? *Default: practice-only on web; assessed quizzes are mobile-app only (see `05_SECURE_QUIZ.md`).*
- Which classes/subjects are in beta? *Default: Class 6–8, matching the data team's work.*
- **NCTB Content Licensing (Open Question for NCTB and Legal Counsel):** What formal permissions, licensing agreements, or MOUs are required from NCTB / Ministry of Education for digitizing curriculum textbooks and indexing competencies for AI-assisted tutoring? Open question for legal counsel and NCTB; no legal conclusions reached (see `docs/ingest_format.md §3`).
