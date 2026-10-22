# P07 – Parent Dashboard APIs & Notifications

**Read first:** `AGENT_RULES.md`, `docs/02_PRODUCT_FLOWS.md` (§2, §4.6), `docs/04_API_CONTRACT.md` (Progress & parent, notifications).

## Task
Give parents the data and controls they need, with privacy boundaries.

## Deliverables
1. `GET /parents/me/students` and per-student dashboard payload: today's completion, streak, time spent, exam countdown, mastery by subject/chapter, weak points, recent quiz results, flagged attempts.
2. Quiz review for parents (after submission only).
3. Controls: edit syllabus/exam/order/daily minutes (calls P03), approve/decline student change requests, mark a flagged attempt as "allowed".
4. **No raw chat transcripts** for parents; show only topic-level summaries ("asked about photosynthesis 3 times").
5. Notification module: FCM sender behind an interface; types: daily reminder, task missed, quiz ready, weekly parent summary, plan changed, integrity flag. Per-user settings and quiet hours.
6. Weekly parent summary job (Bangla + English text templates).

## Acceptance
- A parent never receives data for unlinked students (tests for every endpoint).
- Notification settings and quiet hours are respected.
- Summaries render correctly in Bangla.
