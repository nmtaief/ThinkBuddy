# 06 – Adaptive Engine (planner, mastery, revision)

Principle: **deterministic rules decide what to study and when; the LLM only writes explanations, rubrics feedback, and (grounded) question drafts.** This keeps behavior testable and cheap.

## 1. Planner (v2)
Inputs: resolved settings (from 3-tier hierarchy), day calendar, active subject setups, completed tasks, and `now` (Asia/Dhaka). Pure library: never reads database or system clock.

Algorithm outline:
1. **Calendar & Day Types**:
   - `school_day`: standard weekday budget (`school_day_minutes`).
   - `holiday`: weekly off days (default Friday and Saturday) and national holidays (`holiday_minutes`).
   - `blackout`: zero study tasks (national blackout, parent-blocked observances, custom blackout ranges).
   - `exam_day`: zero study tasks scheduled for subject exams.
2. **Today's Budget (Requirement D.11)**:
   - Budget is the remaining time in `study_window` (`study_window_start` to `study_window_end`) after `now`, minus `completed_minutes_today` and remaining recurring unavailable blocks (coaching/tuition), clamped to the day's base budget.
3. **Priority Multipliers (Requirement D.12)**:
   - Subject priorities (`normal`: 1.0, `main`: 1.3, `difficult`: 1.6) multiply chapter workload in the pace formula, granting main/difficult subjects proportionally more study time.
4. **Subject Rotation Rule (Requirement D.13)**:
   - No subject has study blocks on more than the configured maximum consecutive days (default 2) when 3 or more subjects are active with remaining syllabus.
   - Revision and quiz items are exempt.
   - Subjects are staggered to ensure rest days; if mathematically infeasible, the rule is relaxed with a `ROTATION_RULE_RELAXED` warning.
5. **Reserve Windows**:
   - Final revision window (default last 15% of days, minimum 3 days) dedicated to comprehensive review and mock quizzes.
   - Weekly buffer day (every 7th day) reserved for catch-up and revision.
6. **Task Partitioning**:
   - Long chapters partitioned contiguously across study slices (clamped to max block minutes, default 90m).
   - Each study day produces: study reading (with printed page bounds), spaced revision slot, homework practice, and quiz check.
7. **Regeneration Rules**:
   - Change in settings, syllabus, exam, or policy publish $\rightarrow$ serialize with advisory lock, regenerate **future** days only, preserve completed tasks, bump `plan_version`.

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
