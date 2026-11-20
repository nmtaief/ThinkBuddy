# ThinkBuddy Data Guide
### Building data so the AI can answer creative (সৃজনশীল) and analytical questions

Audience: the data team. Read this first, then ask the engineer for the exact file schemas (section 8).
Status: draft v1. Items marked **(verify)** must be confirmed with a subject teacher or NCTB before you rely on them.

---

## 1. The one idea to understand

ThinkBuddy's AI does **not memorize** our data. In beta nothing is trained or fine-tuned. For every student question the system:
1. **Finds** the most relevant textbook passages (retrieval).
2. **Reasons** over them with a language model, following our guidance and rules.
3. **Shows** the answer with the book, chapter and **printed page number**.

So good data means two things:
- **The textbook text is clean and findable** (otherwise the AI can't find the right passage).
- **We give the AI good examples of how to think and write** (otherwise answers are correct but shallow, or not in the style students need for exams).

If a fact is missing from our data, the AI should say "not found in your textbook". It must not guess. Do not write data that encourages guessing.

## 2. What "creative" and "analytical" mean here

| Type | What the student is asked to do | What a good answer shows |
|---|---|---|
| **Knowledge** (জ্ঞানমূলক) | Recall a fact, term or definition | Exact, short, correct |
| **Comprehension** (অনুধাবনমূলক) | Explain in own words, say why | Reason, not copying |
| **Application** (প্রয়োগ) | Use an idea in a new situation | Links the rule to the situation |
| **Higher-order** (উচ্চতর দক্ষতা) | Analyse, compare, judge, justify, propose | Weighs evidence, reaches a conclusion |
| **Analytical (extra types)** | Compare and contrast, cause and effect, interpret a table or graph, multi-step problem solving, spot the error, evaluate a claim | Clear steps, correct reasoning, uses data from the question |

The usual NCTB creative question (সৃজনশীল প্রশ্ন) is a **stimulus** (উদ্দীপক) followed by four parts of increasing difficulty, commonly worth 1, 2, 3 and 4 marks **(verify the exact structure and marks for each class and subject with a teacher)**.

If by "analytical" you also meant *learning analytics* (finding a student's weak topics), that works only if every item is tagged with concept IDs (dataset B) and difficulty. Tag everything.

## 3. Datasets to build

Letters are used in file names and in conversations with the engineer.

| ID | Dataset | Purpose | Who writes it |
|---|---|---|---|
| **A** | Clean textbook text | What the AI retrieves and cites | Knowledge Factory (OCR) plus human check |
| **B** | Concept layer | Lets the AI explain and link ideas; powers weak-topic detection | Team plus teacher |
| **C** | Bangla and English glossary | Correct, consistent terms | Team plus teacher |
| **D** | Guided answers (Class 6 to 8 first) | Shows how to answer: steps, what to write, what to avoid | Team plus teacher |
| **E** | Creative questions (সৃজনশীল) | Practice, rubrics, and answer-style examples | Teacher-reviewed |
| **F** | Analytical questions | Same, for higher-order thinking | Teacher-reviewed |
| **G** | MCQ and short questions with variants | Quizzes | Team plus teacher |
| **H** | Retrieval test set | Measures whether the AI finds the right page | Teacher |
| **I** | "Do not answer" examples | Off-syllabus, unsafe, cheating attempts | Team |

### A. Clean textbook text
- Split by **book, chapter, section, page**. Keep the **printed page number** (the number shown on the page) separate from the PDF page index. Students and the AI cite the printed number only.
- Keep headings, definitions, formulas (write maths in LaTeX), worked examples, exercises, tables, and image captions as separate, labeled pieces.
- Record OCR quality. Mark broken or doubtful passages, and **do not hide errors**: flag them for a human fix.
- Use proper Unicode (NFC). Keep Bangla digits as printed in the book.

### B. Concept layer (one row per concept)
Fields: concept ID, name in Bangla and English, class, subject, chapter, definition (with page), prerequisite concepts, related concepts, formulas, one or two **common misconceptions**, pages where it is taught, and difficulty (easy, medium, hard).
Aim: about 30 to 60 concepts per book for the pilot.

### C. Glossary
Bangla term, English term, short meaning, page of first use. Use the textbook's own wording. Where books disagree, flag it.

### D. Guided answers (the existing Class 6 to 8 work)
For each exercise or typical question:
1. **Question** and its source page.
2. **Steps** to reach the answer, in plain language for that class.
3. **What to write** (a model answer in the style students are marked on).
4. **What not to write** (common wrong or off-target answers, over-long answers).
5. **Hint ladder:** three hints from a gentle nudge to almost the answer, so the AI can help without handing over the answer straight away.
6. **Marks guidance:** what earns the marks.
7. Concept IDs, difficulty, and review status.

### E. Creative questions (সৃজনশীল)
Each item has:
- A **new, original stimulus** (a short passage, situation, data, or picture description) set in a context Bangladeshi students know.
- Four parts (knowledge, comprehension, application, higher-order), each with: question, model answer, marking rubric (what earns each mark), the textbook pages the answer relies on, and concept IDs.
- A short note on common student mistakes.

### F. Analytical questions
Fields: type (compare, cause and effect, data interpretation, multi-step, error-spotting, evaluate), question, any data or table, **step-by-step reference answer**, rubric, pages, concept IDs, difficulty.

### G. Quiz questions
MCQ and short answers with 2 to 3 **variants** of each question (same skill, different wording or numbers), correct answer, accepted alternative answers (including Bangla and English digit forms), a one-line explanation, and the source page.

### H. Retrieval test set (needed before the AI can be tested on real books)
About 50 questions per pilot book, written as students really type them: Bangla, English, mixed, misspelled, informal. For each: expected book, chapter and **printed page**, and a short note of what the passage says. Include:
- 5 to 10 questions that are **not in the textbook** (expected answer: "not found").
- A few follow-up questions ("and what about the second one?").
- A mix of easy, hard and ambiguous questions.
A teacher, not an AI, should confirm every expected page.

### I. "Do not answer" examples (about 30)
Off-topic requests, attempts to get answers during a quiz, requests to do homework wholesale, unsafe or inappropriate topics. For each, write the kind of reply we want: kind, short, redirecting to study.

## 4. Quality bar (applies to every item)

Every row must carry: class, subject, medium (Bangla version or English version), chapter, **printed page**, language, difficulty, concept IDs, type, **status** (`draft`, `team_checked`, `teacher_approved`), author, reviewer, date.

Rules:
1. **Check against the textbook page.** If you can't point to a page, the item isn't ready.
2. **Two people:** the author, and a different reviewer. Creative and analytical items also need a **teacher's approval**.
3. **AI-written content** is always `draft` and marked as AI-generated until a human has checked it. Never mark AI output approved yourself.
4. **Language:** correct Bangla for the class level, NCTB terminology, short sentences, no copied wording from guides or other publishers, no mixed scripts by accident.
5. **Tone:** encouraging and neutral. Never call a child weak or slow. No religion, politics or personal stories about real people in examples, and keep festival or cultural examples inclusive.
6. **No student data.** No real names, photos or school details in any file.

## 5. Sources and copyright (important)

- **NCTB textbooks:** the rules for digitizing and indexing them are still an **open question** for NCTB and a lawyer. Until it is settled, keep text and PDFs **private**: not in public repositories, not in public chat tools you don't control, and not shared outside the team.
- **Free guides and notebooks** (commercial guide books and notes) are other people's copyrighted work. Use them only to **understand the answer style**. **Do not copy or lightly reword their text into our data.** Write the answers yourself from the textbook, in your own words, then have a teacher check them. Keep a short source log: where each idea came from.
- **Past board questions:** use as a style reference only. Write original questions. Ask before reusing real exam text.
- When using AI tools (Antigravity, Gemini, Claude), check their data and privacy settings before pasting book text, and never paste anything personal.

## 6. Working with AI tools (draft, then verify)

The AI is a fast first-drafter, not the authority. The order is always: **AI drafts, you check against the page, a reviewer checks you, a teacher approves.**

Use these prompt patterns (adapt the wording):

> **Guided answer draft.** "Using only the textbook passage below (pages ___), write a guided answer for this question for a Class ___ student: steps, a model answer in the style a teacher would mark, what not to write, and a three-step hint ladder. Use simple Bangla. If the passage does not contain enough to answer, say so. Do not invent facts or page numbers. Return the fields: steps, model_answer, avoid, hints, marks_guidance."

> **Creative question draft.** "Write a new, original stimulus and four questions (knowledge, comprehension, application, higher-order) for Class ___ , chapter ___ . Use only ideas in the passage below. Give a model answer and marking rubric for each part, and the page each answer relies on. Do not copy any existing board or guide-book question."

> **Analytical question draft.** "Create one [compare / cause-and-effect / data-interpretation / multi-step] question from the passage below, with a step-by-step reference answer and a marking rubric. Say which passage sentences support each step."

> **Reviewer prompt.** "Check this item against the passage. List any claim not supported by the passage, any wrong or unclear step, any wording that could mislead a student, and any Bangla errors. Do not rewrite it."

Always read the output yourself. A confident-looking wrong answer is worse than no answer.

## 7. Suggested sizes for the first pilot

One class and two subjects (for example one language and one science or maths) to start. These are targets to adjust, not rules.

| Dataset | Pilot size |
|---|---|
| A. Clean text | 2 full books, validated |
| B. Concepts | 30 to 60 per book |
| C. Glossary | all key terms in the 2 books |
| D. Guided answers | 60 |
| E. Creative questions | 30 |
| F. Analytical questions | 30 |
| G. Quiz questions | 100, with variants |
| H. Retrieval test set | 50 per book |
| I. "Do not answer" | 30 |

## 8. File format and delivery

- UTF-8 text files, one item per line (JSONL) or CSV, named like `data/class7/science/guided_answers.jsonl`.
- Use IDs that never change (for example `c7-sci-ch2-q014`).
- **Match the schemas used by the system exactly.** Ask the engineer for the final field list and a validation script. The textbook format is in `docs/ingest_format.md`, and quiz questions follow the sample in `fixtures/questions_sample.jsonl`. Datasets B to F and I are new, so agree their fields with the engineer before writing hundreds of rows.
- Do not put raw books or PDFs, or any personal data, into the code repository. Share data through private storage the engineer sets up.

## 9. How we will know it works

| Test | Measures |
|---|---|
| Retrieval test set (H) | Does the AI find the right chapter and printed page? |
| Groundedness check | Is every claim in an answer supported by the cited passage? |
| Rubric scoring by teachers (E, F) | Are answers correct, complete, and in the marking style? |
| "Not found" and "do not answer" sets | Does it refuse and redirect properly? |

When an answer is wrong, we first ask **"was the data missing, unclear or wrong?"** and fix the data, before blaming the model.

## 10. Definition of done for a batch

- [ ] Every item has all required fields and a printed page.
- [ ] No item copies text from guide books or other publishers.
- [ ] A reviewer has checked every item, and a teacher has approved creative and analytical items.
- [ ] Files pass the engineer's validation script.
- [ ] A short note lists sources used, problems found, and items left unfinished.
- [ ] Nothing private or personal is included.

## 11. Open questions (owner in brackets)

1. May NCTB textbooks be digitized and indexed for this product, and under what conditions? (lawyer, NCTB)
2. Which curriculum version applies to each class (including the English version books), and what is the official creative-question format for each? (teacher)
3. Who is the reviewing teacher for each subject? (project owner)
4. Which two subjects and which class do we pilot first? (project owner)
5. Final schemas and the validation script for datasets B to F and I. (engineer)
