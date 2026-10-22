# 06 – Adaptive Engine (planner, mastery, revision)

Principle: **deterministic rules decide what to study and when; the LLM only writes explanations, rubrics feedback, and (grounded) question drafts.** This keeps behavior testable and cheap.

## 1. Planner
Inputs: exam date(s), included chapters with order and weights, daily minutes, available days, current mastery.

Algorithm outline:
1. Count usable study days between now and the exam (honor available days).
2. Reserve a **final revision window** (default last 15% of days, minimum 3 days) and a buffer day each week.
3. Estimate chapter effort = pages × difficulty factor × (1 + (1 − mastery)). Unknown mastery uses 0.5.
4. Allocate chapters in the parent's order into days, respecting daily minutes. Split long chapters across days.
5. Per day, add: study task, a daily revision slot (from §3), homework, and a short quiz.
6. Output plan + warnings (e.g., "exam too close for full coverage – compressed plan").
Regeneration rules: change in syllabus/exam/order → regenerate **future** days only; keep completed tasks; bump `plan_version`.

## 2. Signals → mastery
Signals (`learning_signals`) and starting weights (tune with data):
| Signal | Effect |
|---|---|
| Quiz correct (assessed) | + strong |
| Quiz wrong (assessed) | − strong |
| Practice correct/wrong | ± light |
| Slow correct answer | small − (fragile knowledge) |
| AI question on a topic | − small; repeats within 3 days: − medium |
| Teacher flags difficult (later) | − strong, decays slower |
| Task skipped repeatedly | − small on that chapter |
Mastery per (student, chapter, concept) is a bounded score with an exponential recency decay. Store `confidence` (how many signals); low confidence shows as "not enough data" to parents, not as "weak".

## 3. Revision (spaced repetition)
- Leitner-style boxes 1–5 with intervals (default 1, 3, 7, 14, 30 days).
- Correct → promote; wrong → back to box 1. Items come from missed questions, weak concepts, and recently studied concepts.
- Daily revision slot: 5–10 minutes, ordered by (overdue × weakness).

## 4. Daily composition (default)
| Component | Share of study time |
|---|---|
| New study (current chapter) | ~55% |
| Revision | ~20% |
| Weak-point practice | ~15% |
| Homework + quiz check | ~10% |
If mastery data says a student is struggling, the share shifts toward revision and weak points.

## 5. 3-day review cycle
Scheduled job every 3 days per student:
1. Gather last 3 days of signals.
2. Build a review quiz (assessed): weighted sample from recent chapters, wrong answers, and repeated-AI-question topics.
3. Add 1–2 broad questions on the weakest recent topic.
4. Recompute mastery, then rewrite upcoming revision and quiz tasks (`source = adaptive`).
5. Notify student; update parent summary.

## 6. Question generation (LLM, grounded)
- Generate only from retrievable chunks; store `source_chunk_ids`.
- Second-pass validation: another LLM call (or rules) checks answerability from the chunk, single correct option, no ambiguity, language quality.
- Status path: `draft → validated → approved`. In beta, unreviewed AI questions are used for **practice only**; assessed quizzes prefer `curated`/`approved` questions.
- Always create variants (`variant_group_id`) to support secure quiz randomization.

## 7. Broad answer feedback
AI scores against a rubric (provisional, labelled). With a teacher (premium, later) the teacher's comment overrides and the score updates mastery with higher weight.

## 8. Evaluation (build early)
- Planner: property tests (never schedule beyond exam date; never exceed daily minutes).
- Mastery: simulated student histories with expected trends.
- Revision: intervals respect boxes.
- RAG: Bangla + English retrieval set with expected printed pages; track hit-rate@k and citation accuracy.
- Question generation: sample audit of 100 questions per release.
