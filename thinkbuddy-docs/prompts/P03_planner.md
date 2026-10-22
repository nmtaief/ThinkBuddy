# P03 – Study Setup & Planner

**Read first:** `AGENT_RULES.md`, `docs/02_PRODUCT_FLOWS.md` (§4.1, §4.2, §6), `docs/06_ADAPTIVE_ENGINE.md` (§1), `docs/03_DATA_MODEL.md` (§3), `docs/04_API_CONTRACT.md` (Planning).

## Task
Parent configures syllabus, exam date, and chapter order; the system produces a versioned weekly plan with clear guidelines.

## Deliverables
1. Endpoints: study setup upsert (parent), change request (student), plan fetch, `today` payload, task status update.
2. **Pure-Python planner library** (no DB or HTTP imports) implementing `docs/06_ADAPTIVE_ENGINE.md §1`: final revision window, weekly buffer, effort estimate, daily-minute limits, available days, warnings for infeasible exams.
3. Plan versioning: regenerate future days only; preserve completed tasks; audit log entry; notify student (stub notification).
4. Task `refs` include book, chapter, printed page ranges, and a one-line "what to do / how it's checked".
5. Rolling logic: missed tasks roll forward or compress per rule; never schedule past the exam date.
6. Celery job to regenerate affected plans after change; API returns immediately with `plan_version` pending state.

## Acceptance
- Property tests: no day exceeds daily minutes; no task after exam date; chapter order respected; completed tasks unchanged after regeneration.
- Infeasible exam date returns a compressed plan with a `warnings` array.
- Parent of another family cannot edit the setup.
