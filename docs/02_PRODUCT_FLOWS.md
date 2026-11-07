# 02 – Product Flows & Permissions

## 1. Roles
| Role | Beta | Description |
|---|---|---|
| Student | Yes | Studies, takes quizzes, asks the AI |
| Parent | Yes | Oversees progress, sets syllabus/exam/chapter order |
| Teacher | No (flagged) | Reviews broad answers, comments, flags difficult topics (premium) |
| Admin | Internal | Content, flags, support |

One person = one account = one role in beta. A family has one or more parents and one or more students.

## 2. Permission matrix
| Action | Student | Parent (linked) | Teacher (assigned, later) |
|---|---|---|---|
| See own plan/tasks | ✔ | ✔ (child's) | ✔ |
| Edit syllabus, exam date, chapter order | request only | ✔ | ✗ |
| Take quizzes / submit answers | ✔ | ✗ | ✗ |
| See quiz scores and weak points | ✔ | ✔ | ✔ |
| See quiz questions after submission | ✔ | ✔ | ✔ |
| Ask AI | ✔ | ✗ (beta) | ✗ |
| See raw chat transcript | own | ✗ by default | ✗ |
| Review broad answers | ✗ | ✗ | ✔ |
| Manage subscription | ✗ | ✔ | ✗ |

## 3. Onboarding & Configuration
1. **Parent signs up** (phone OTP or Google), creates the family.
2. Parent **adds a child**: name, class (6–12), medium (Bangla/English), group (Science, Humanities, Business Studies for 9–12), optional/4th subjects, school optional. System creates a student profile and a **link code** (or QR).
3. Student installs the app, signs in, and enters the code; the link becomes `active`.
4. Parent sets the **study setup & settings**:
   - Setup: subjects, syllabus (chapters included), exam name + date, preferred chapter order.
   - Settings: `school_day_minutes`, `holiday_minutes`, study window (e.g. 17:00–21:30), recurring unavailable blocks (coaching/tuition), blocked observances, custom blackout ranges (coarse reasons only: `family_event`, `travel`, `illness`, `school_event`, `other`), and subject priorities (`normal`, `main`, `difficult`).
   - Privacy rule: **Religion is never stored**; observance selections from the catalog are the sole input.
5. System resolves settings against admin class-band policies and generates the plan.

## 4. The learning loop

### 4.1 Plan creation and updates (Planner v2)
- **Inputs**: resolved 3-tier settings, syllabus (chapter list), exam date(s), chapter order, historical completed tasks, and `now` (student timezone, default `Asia/Dhaka`). Pure function: reads zero database or clock.
- **Day Types**:
  - `school_day`: standard weekday study budget.
  - `holiday`: weekly off days (default Friday and Saturday) and national holidays; study days with holiday budget, not skipped days.
  - `blackout`: zero study (national blackout holidays, parent-blocked observances, custom blackout ranges).
  - `exam_day`: zero study tasks scheduled for subject exams.
- **Dynamic Configuration Hierarchy**:
  1. System Defaults $\rightarrow$ 2. Admin Policy by Class Band (`6-8`, `9-10`, `11-12`) and Group $\rightarrow$ 3. Parent Settings per Student.
  - Parent values are clamped to Admin Hard Limits (`daily_minutes` 0–600, `max_block_minutes` 90 with break, `latest_end_time`) at planning time, emitting clamping notices to the parent.
  - Warning emitted when minutes exceed recommended levels.
- **Governance & Concurrency**:
  - Admin changes follow `draft` $\rightarrow$ `impact preview` $\rightarrow$ `publish`. Drafts never touch plans. Publishing queues throttled idempotent regeneration for future days only, with coalesced notifications.
  - Optimistic concurrency (`409 Conflict`) on every settings row via `version`.
  - Students can propose change requests (`POST /study-settings/change-requests`), but cannot apply them.
- **Timeline & Tasks**: Output timeline (exam date backwards) and daily schedule with task types `study`, `revision`, `homework`, `quiz`, `broad_question`.
- **Rotation Rule**: No subject has study blocks on > 2 consecutive days when $\ge 3$ active subjects have remaining content (revision/quizzes exempt). Staggers subjects; relaxes with warning if infeasible.
- Parent updates:
  1. Versions the settings and plan (`version` +1), keeping audit log entries.
  2. Regenerates **only future days**; completed work is untouched.
  3. Notifies the student.

### 4.2 Daily rhythm
Each day the student sees:
1. **Today's study** (new chapter material, short).
2. **Daily revision** (5–10 minutes from spaced-revision items).
3. **Homework** (a few questions on today's study).
4. **Daily quiz** (short, secure when flagged as assessed).
Missed tasks roll forward or get compressed; the planner decides, not the client.

### 4.3 Questions
- **Objective (MCQ/short)**: auto-graded by the server.
- **Broad/written**: student types or uploads a photo. AI gives *provisional* feedback against a rubric; in premium, a teacher reviews and comments (later). Provisional AI grades are labelled as such.

### 4.4 AI help (RAG)
Available any time **except during a secure quiz attempt**. Answers are cited to textbook pages. Every question to the AI is also a learning signal (topic confusion).

### 4.5 Every 3 days: review cycle
A scheduled job builds a **review quiz + review questions** from:
- topics studied in the last 3 days,
- wrong answers,
- AI questions the student asked repeatedly,
- teacher-flagged difficult topics (later).
Then the adaptive engine recomputes mastery and rewrites the next days' revision and quiz content (`06_ADAPTIVE_ENGINE.md`).

### 4.6 Parent view
- Today's completion, streak, time spent.
- Per-subject mastery, weak chapters, and trend.
- Upcoming exam countdown and plan timeline.
- Quiz results with question review (after submission).
- Controls: edit syllabus/exam/chapter order, daily minutes, notification settings.
- Weekly summary push/notification.

### 4.7 Teacher (premium, later, flagged)
Assigned teacher sees students' broad answers, comments, can mark topics "difficult", and these feed the adaptive engine at a high weight.

## 5. Free vs premium (initial proposal)
| Feature | Free | Premium |
|---|---|---|
| Plan, tasks, quizzes | ✔ | ✔ |
| AI chat | daily quota | higher quota |
| Teacher review of broad answers | ✗ | ✔ |
| Detailed parent reports | basic | full |
Entitlements are checked server-side from `entitlements`, never trusted from the client.

## 6. Edge cases the agent must handle
- Student with two parents: both can see; edits from either create a new plan version with an audit entry; last-write-wins with conflict notice.
- Parent unlinks a student: access ends immediately; data retained per policy.
- Exam date moved earlier than feasible: planner returns a warning with a compressed plan, never an error.
- Student offline: today's tasks viewable; quiz attempts **cannot** start offline.
- Device changed mid-quiz: attempt is flagged and may be invalidated per policy.
