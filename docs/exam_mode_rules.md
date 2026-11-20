# ThinkBuddy Exam-Week Mode: Deterministic Rules & Mathematical Rationale

**Document Version:** 1.0.0  
**Status:** Canonical Rules Engine Specification  
**Authority:** Server-side deterministic scheduling; student empathy guidelines.

---

## 1. Core Principles & Non-Negotiable Invariants

1. **Deterministic Rules Engine:** All phase transitions, hour-level gap calculations, subject splits, block sequencing, and caps are computed deterministically. The LLM produces only empathetic, encouraging Bengali explanation copy—it never chooses times or subjects.
2. **Student-Centric Empathetic UX:** All student-facing copy strictly uses **"আরও অনুশীলন দরকার"** (needs more practice). The word **"দুর্বল"** (weak) is forbidden in user-facing UI. Streak shaming and guilt messaging are suspended during exam weeks.
3. **Physical & Mental Well-being Guarantees:** Sleep windows (minimum 7.0 hours), exam-day meal/travel/rest buffers (2.0 hours), and daily study caps (10.0 hours max) are strictly preserved as non-negotiable hard invariants.
4. **Zero New Pages/Navigation:** All functionality integrates seamlessly into the existing Exam-Day option, Syllabus option, and the merged "আজকের পড়া" (`TodayView.tsx` / `PlanTimelineView.tsx`) interface.

---

## 2. Centralized Versioned Configuration (`EXAM_MODE_CONFIG_V1`)

Every parameter and coefficient below is centralized in `EXAM_MODE_CONFIG_V1` and documented with its pedagogic rationale.

| Parameter | Value | Status | Rationale |
|---|---|---|---|
| `REVISION_WEEK_DAYS` | `7` days | `default awaiting teacher review` | Cognitive consolidation period. Within 7 days of an exam series, starting new chapters induces cognitive overload. Only revision, past questions, and weak-point remediation are permitted. |
| `MIN_SLEEP_HOURS` | `7.0` hours | `default awaiting teacher review` | Sleep deprivation directly impairs executive function, recall, and mathematical computation during high-stakes exams. Non-negotiable ceiling deduction. |
| `EXAM_DAY_BUFFER_HOURS` | `2.0` hours | `default awaiting teacher review` | Accounts for post-exam physical travel, meals, decompressing, and mental transition before resuming study at 15:00. |
| `STUDY_BLOCK_DURATION` | `50` mins | `default awaiting teacher review` | Standard ultradian focus cycle for secondary students. Followed immediately by a 10 min break. |
| `BREAK_DURATION` | `10` mins | `default awaiting teacher review` | Cognitive rest interval between 50-minute study blocks to prevent fatigue. |
| `DAILY_SAFETY_CAP_HOURS` | `10.0` hours | `default awaiting teacher review` | Hard physiological safety ceiling. If a student attempts to schedule >10 hours, the engine automatically clamps it to 10.0h and issues an encouraging pacing notice. |
| `SAME_DAY_GAP_MAX_HOURS`| `12.0` hours | `default awaiting teacher review` | When two exams take place on the same day or within 12 hours, net study is strictly limited to micro-review for exam 2. |
| `SHORT_GAP_MAX_HOURS` | `24.0` hours | `default awaiting teacher review` | Gaps $\le 24$ hours (or $< 9.0$ hours net study) are 100% exclusive to the immediate next exam's subject. |
| `MEDIUM_GAP_MAX_HOURS` | `48.0` hours | `default awaiting teacher review` | 24–48 hour gaps. Immediate next exam dominates; the final day is 100% exclusive to that subject. |
| `LONG_GAP_SPILLOVER_H` | `7` days | `default awaiting teacher review` | In gaps $> 48$ hours, a later subject $Y$ qualifies for Day 1 advance study only if its exam falls within $H=7$ days. |
| `SPILLOVER_MAX_SHARE` | `35%` | `default awaiting teacher review` | Day 1 study for later subject $Y$ may not consume more than 35% of that day's net study hours. |
| `SPILLOVER_MAX_HOURS` | `2.5` hours | `default awaiting teacher review` | Absolute hour ceiling for later subject $Y$ on Day 1, ensuring the immediate subject remains dominant. |
| `EXTENDED_GAP_THRESHOLD`| `96.0` hours | `default awaiting teacher review` | Gaps $> 4$ days allow the capped spillover block on both Day 1 and Day 2. |
| `POST_TEST_NEW_CAP` | `40%` | `default awaiting teacher review` | Post-SSC Test exam, any unfinished syllabus may occupy at most 40% of daily study hours so that 60% remains dedicated to model questions and revision. |
| `COEF_WEAKNESS` ($a$) | `0.35` | `default awaiting teacher review` | Multiplier for chapter weakness in intra-day priority formula. |
| `COEF_REMAINING` ($b$) | `0.40` | `default awaiting teacher review` | Multiplier for unread remaining syllabus in intra-day priority formula. |
| `WEAKNESS_THRESHOLD` | `0.50` | `default awaiting teacher review` | A concept or chapter score $< 0.50$ qualifies as needing practice ("আরও অনুশীলন দরকার"). |
| `CONFIDENCE_DIAGNOSTIC` | `0.40` | `default awaiting teacher review` | Confidence $< 0.40$ triggers a mandatory 10–15 min diagnostic quiz block to establish baseline before the exam. |

---

## 3. Mathematical Models & Decision Trees

### 3.1 Phase Detection Logic
Let $E_{\text{first}}$ = epoch timestamp of the first exam in the series:
$$\text{Phase}(t) = \begin{cases}
\text{Learn Phase}, & t < E_{\text{first}} - 7\text{ days} \\
\text{Revision Week}, & E_{\text{first}} - 7\text{ days} \le t < E_{\text{first}} \\
\text{Exam Period}, & E_{\text{first}} \le t \le E_{\text{last}} \\
\text{SSC Post-Test Revision}, & t > \text{Test}_{\text{end}} \land t < \text{Board}_{\text{first}} - 7\text{ days}
\end{cases}$$

### 3.2 Net Study Hours Equation
$$\text{Net Study Hours} = \min\left(\text{SafetyCap}, \max\left(0, \text{RawGap} - \text{Sleep} - \text{Buffer}\right)\right)$$
Where:
- $\text{Sleep} = \max(7.0, \text{MinSleep}) \times \min(1.0, \text{DaysInGap})$
- $\text{Buffer} = 2.0\text{h (on exam day)} \text{ or } 1.5\text{h (on non-exam day)}$

### 3.3 Priority Allocation Formula
$$\text{Priority} = \text{MarksWeight} \times (1 + a \cdot \text{Weakness}) \times (1 + b \cdot \text{RemainingSyllabus}) \times \text{Urgency}(\Delta t)$$
Where:
$$\text{Urgency}(\Delta t) = \begin{cases}
2.5, & \Delta t \le 24\text{ hours} \\
1.8, & 24 < \Delta t \le 48\text{ hours} \\
1.3, & 48 < \Delta t \le 96\text{ hours} \\
1.0, & \Delta t > 96\text{ hours}
\end{cases}$$

### 3.4 Long-Gap Spillover Eligibility Rule
A later subject $Y$ receives a study block on Day 1 if and only if:
1. $\text{DaysToExam}(Y) \le H\text{ (7 days)}$
2. $\text{Weakness}(Y) \ge 0.50$
3. $\text{MarksWeight}(Y) \ge \text{MedianMarksWeight}$

If eligible:
$$\text{AllocatedMinutes}(Y) = \min\left(2.5 \times 60, \text{NetDailyMinutes} \times 0.35\right)$$

---

## 4. Remaining Syllabus Feasibility Decision Tree
When a student declares `"বাকি আছে"` syllabus:
1. Compare $\text{HoursNeeded} = \sum \text{EstimatedChapterHours}$ against $\text{HoursAvailable}$.
2. If $\text{HoursNeeded} > \text{HoursAvailable}$, present 3 explicit options in the UI:
   - **Option 1 (Raise Hours):** Increase daily hours up to the 10.0h safety cap.
   - **Option 2 (Prioritize):** Allocate time to high-weight and high-weakness chapters first.
   - **Option 3 (Skim Only):** Designate secondary chapters for rapid formula/summary passes.
3. The engine never silently drops chapters and never overbooks days without user direction.

---

## 5. Weak-Point Remediation Closed-Loop
For each upcoming exam:
1. Rank concepts by $\text{Weakness} \times \text{MarksWeight} \times \text{Fixability}$.
2. Schedule a 20–30 min block:
   - Active recall of key definitions.
   - 3–5 targeted practice questions (or exact exercises for Math).
   - Mini-check verification.
3. Attach authentic Why-Sheet reasons (e.g. `"কেন: গতবার ৫টির মধ্যে ১টি সঠিক"`).
4. Update Leitner queue with interval promotion upon resolution.
