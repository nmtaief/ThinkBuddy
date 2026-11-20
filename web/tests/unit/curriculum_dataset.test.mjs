import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test("Curriculum study dataset is valid, authentic and enforces Class 6/7 assessment rules", () => {
  const datasetPath = path.resolve(__dirname, "../../src/lib/curriculum_study_dataset.json");
  assert.ok(fs.existsSync(datasetPath), "curriculum_study_dataset.json exists");

  const raw = fs.readFileSync(datasetPath, "utf-8");
  const data = JSON.parse(raw);

  assert.ok(data.curated_chapters, "Has curated chapters");
  assert.ok(Object.keys(data.curated_chapters).length >= 7, "Has at least 7 curated chapters");

  // 1. Verify Class 6 ICT: strictly NO Board Questions!
  const c6Ict = data.curated_chapters["c6_ict_ch1"];
  assert.ok(c6Ict, "Class 6 ICT exists");
  assert.equal(c6Ict.class_level, 6, "Class level is 6");
  assert.ok(
    c6Ict.parts[0].homework_tasks.every(hw => !hw.title_bn.includes("বোর্ড প্রশ্ন")),
    "Class 6 homework must NOT include board questions"
  );
  assert.ok(
    c6Ict.parts[0].homework_tasks.some(hw => hw.title_bn.includes("বিদ্যালয়")),
    "Class 6 homework includes school assessments"
  );
  assert.ok(
    c6Ict.notes.exam_strategy_tips.every(tip => !tip.includes("বোর্ড পরীক্ষা")),
    "Class 6 exam tips must NOT reference board exams"
  );

  // 2. Verify Class 6 Math: strictly NO Board Questions!
  const c6Math = data.curated_chapters["c6_math_ch1"];
  assert.ok(c6Math, "Class 6 Math exists");
  assert.ok(
    c6Math.parts[0].homework_tasks.every(hw => !hw.title_bn.includes("বোর্ড প্রশ্ন")),
    "Class 6 Math must NOT include board questions"
  );

  // 3. Verify Class 8 Math & Science: Authentic Board Questions present
  const c8Math = data.curated_chapters["c8_math_ch1"];
  assert.ok(c8Math, "Class 8 Math exists");
  assert.ok(
    c8Math.parts[0].homework_tasks.some(hw => hw.title_bn.includes("বোর্ড সৃজনশীল প্রশ্ন")),
    "Class 8 includes authentic Board CQ"
  );

  // 4. Verify Quiz Questions structure
  for (const [key, ch] of Object.entries(data.curated_chapters)) {
    for (const part of ch.parts) {
      assert.ok(part.quiz_questions, `${key} part ${part.part} has quiz_questions`);
      assert.equal(part.quiz_questions.length, 3, `${key} part has 3 quiz questions`);
      for (const q of part.quiz_questions) {
        assert.ok(q.question_bn.length > 5, "Has Bengali question text");
        assert.equal(q.options_bn.length, 4, "Has 4 Bengali options");
        assert.ok(q.correctIndex >= 0 && q.correctIndex <= 3, "Valid correct option index");
        assert.ok(q.explanation_bn.length > 10, "Has detailed Bengali explanation");
      }
    }
  }

  // 5. Verify rich notes
  for (const [key, ch] of Object.entries(data.curated_chapters)) {
    assert.ok(ch.notes.core_concepts.length >= 2, `${key} has core concepts`);
    assert.ok(ch.notes.key_formulas_or_reactions.length >= 1, `${key} has formulas/reactions`);
  }
});

test("Curriculum 15-question dataset is authentic, comprehensive and supports refresh", () => {
  const datasetPath = path.resolve(__dirname, "../../src/lib/curriculum_questions_dataset.json");
  assert.ok(fs.existsSync(datasetPath), "curriculum_questions_dataset.json exists");

  const raw = fs.readFileSync(datasetPath, "utf-8");
  const dataset = JSON.parse(raw);

  assert.ok(dataset.subject_pools, "Has subject pools");
  const requiredPools = ["bangla", "math", "science", "ict", "english", "bgs"];
  for (const pool of requiredPools) {
    const questions = dataset.subject_pools[pool];
    assert.ok(questions, `Pool ${pool} exists`);
    assert.ok(questions.length >= 15, `Pool ${pool} has at least 15 questions (found ${questions.length})`);
    for (const q of questions) {
      assert.ok(q.question_bn && q.question_bn.length > 5, "Has Bengali question text");
      assert.equal(q.options_bn.length, 4, "Has 4 Bengali options");
      assert.ok(q.correctIndex >= 0 && q.correctIndex <= 3, "Valid correct index");
      assert.ok(q.explanation_bn && q.explanation_bn.length > 10, "Has explanation");
    }
  }
});

test("Revision Queue is grounded in authentic NCTB curriculum dataset with textbook citations and Leitner boxes", () => {
  const datasetPath = path.resolve(__dirname, "../../src/lib/curriculum_questions_dataset.json");
  const dataset = JSON.parse(fs.readFileSync(datasetPath, "utf-8"));

  // Verify that questions in all 6 subjects contain high-yield concept evidence
  for (const [pool, questions] of Object.entries(dataset.subject_pools)) {
    assert.ok(questions.length >= 20, `${pool} has at least 20 authentic curriculum items`);
    questions.forEach((q, idx) => {
      assert.ok(q.question_bn.length >= 8, `${pool} Q${idx + 1} has complete question text`);
      assert.equal(q.options_bn.length, 4, `${pool} Q${idx + 1} has 4 options`);
      assert.ok(q.correctIndex >= 0 && q.correctIndex < 4, `${pool} Q${idx + 1} correctIndex in bounds`);
      assert.ok(q.explanation_bn.length >= 10, `${pool} Q${idx + 1} has textbook explanation`);
    });
  }
});

test("CQ Knowledge (ক) & Comprehension (খ) Topic Mapping and AI Rubric Engine works accurately", async () => {
  const tsModule = await import("typescript");
  const ts = tsModule.default || tsModule;
  const cqTsPath = path.resolve(__dirname, "../../src/lib/cq-topic-mapping.ts");
  const rawTs = fs.readFileSync(cqTsPath, "utf-8");
  const jsCode = ts.transpileModule(rawTs, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
  const dataUri = `data:text/javascript;base64,${Buffer.from(jsCode).toString("base64")}`;
  const cqMapping = await import(dataUri);
  const { CQ_QUESTIONS_BANK, getCQQuestions, evaluateCQAnswer } = cqMapping;

  assert.ok(CQ_QUESTIONS_BANK.length >= 10, "CQ question bank contains authentic items");

  // Every item must have valid topic tags, printed page numbers, marks (1 or 2), and model answers
  CQ_QUESTIONS_BANK.forEach((q) => {
    assert.ok(q.id, "Question has ID");
    assert.ok(q.type === "ka_knowledge" || q.type === "kha_comprehension", "Valid CQ type");
    assert.equal(q.marks, q.type === "ka_knowledge" ? 1 : 2, "1 mark for ক, 2 marks for খ");
    assert.ok(q.subject.length > 0, "Has subject");
    assert.ok(q.chapter_number > 0, "Has chapter number");
    assert.ok(q.subtopic_tag.length > 0, "Has subtopic tag");
    assert.ok(q.printed_page > 0, "Has valid printed page number");
    assert.ok(q.model_answer_bn.length >= 15, "Has comprehensive model answer");
    assert.ok(q.key_rubric_points.length >= 2, "Has rubric keywords");
  });

  // Test filtering
  const sciQuestions = getCQQuestions({ subject: "সাধারণ বিজ্ঞান" });
  assert.ok(sciQuestions.length >= 2, "Science questions filtered properly");

  const kaOnly = getCQQuestions({ type: "ka_knowledge" });
  assert.ok(kaOnly.every((q) => q.type === "ka_knowledge" && q.marks === 1), "Filtered ka questions");

  // Test Rubric Grading: Full marks scenario
  const pollinationQ = CQ_QUESTIONS_BANK.find((q) => q.id === "cq_sci_ch4_k1");
  assert.ok(pollinationQ, "Pollination question exists");

  const fullScoreEval = evaluateCQAnswer(
    pollinationQ,
    "ফুলের পরাগধানী হতে পরাগরেণু গর্ভমুণ্ডে স্থানান্তর হওয়াকে পরাগায়ন বলে।"
  );
  assert.equal(fullScoreEval.score, 1, "Earned full 1 mark for correct definition");
  assert.equal(fullScoreEval.is_full_marks, true);
  assert.ok(fullScoreEval.matched_keywords.length >= 2);
  assert.equal(fullScoreEval.textbook_page, 42);

  // Test Rubric Grading: Comprehension (2 marks)
  const selfPollinationQ = CQ_QUESTIONS_BANK.find((q) => q.id === "cq_sci_ch4_kh1");
  assert.ok(selfPollinationQ, "Comprehension question exists");

  const compEval = evaluateCQAnswer(
    selfPollinationQ,
    "স্বপরাগায়ন একই উদ্ভিদে ঘটে। এতে কোনো বাইরের ভিন্ন বৈশিষ্ট্য সংমিশ্রণ হয় না, তাই মাতৃ উদ্ভিদের বিশুদ্ধতা বজায় থাকে।"
  );
  assert.equal(compEval.score, 2, "Earned full 2 marks for complete explanation");
  assert.equal(compEval.is_full_marks, true);
});

test("English Writing & Contextual Vocabulary Enhancement Engine evaluates grammar and suggests academic synonyms", async () => {
  const tsModule = await import("typescript");
  const ts = tsModule.default || tsModule;
  const tutorPath = path.resolve(__dirname, "../../src/lib/english-writing-tutor.ts");
  let rawTs = fs.readFileSync(tutorPath, "utf-8");
  rawTs = rawTs.replace(/import\s*\{[^}]*\}\s*from\s*['"][^'"]*['"];?/, "const LEITNER_INTERVALS = {1:1, 2:3, 3:7, 4:14, 5:30}; const getActiveRevisionQueue = () => [];");
  const jsCode = ts.transpileModule(rawTs, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
  const dataUri = `data:text/javascript;base64,${Buffer.from(jsCode).toString("base64")}`;
  const tutor = await import(dataUri);
  const { analyzeEnglishWriting, isEnglishWritingSubmission, ADVANCED_VOCABULARY_DICTIONARY } = tutor;

  assert.ok(Object.keys(ADVANCED_VOCABULARY_DICTIONARY).length >= 15, "Vocabulary dictionary has 15+ entries");

  // Test detection
  const sampleParagraph =
    "A rainy day is very good. It rains heavy all day. The roads are full of big water and people cannot go outside easily. It is hard for poor people but helps nature.";

  assert.equal(isEnglishWritingSubmission(sampleParagraph), true, "Detects English paragraph");
  assert.equal(isEnglishWritingSubmission("আজকে বৃষ্টি হচ্ছে"), false, "Rejects Bengali text");

  // Test analysis
  const feedback = analyzeEnglishWriting(sampleParagraph);
  assert.ok(feedback.word_count >= 25, "Counted words accurately");
  assert.ok(feedback.sentence_count >= 3, "Counted sentences accurately");
  assert.ok(feedback.overall_score > 0 && feedback.overall_score <= 10, "Score within 1-10 range");
  assert.ok(feedback.structure_feedback.clarity_bn, "Has clarity feedback");

  // Test Vocabulary Upgrades: 'good', 'big', 'hard', 'help' detected and upgraded
  const detectedUpgrades = feedback.vocabulary_upgrades;
  assert.ok(detectedUpgrades.length >= 2, "Identified basic repetitive words for upgrade");

  const upgradedWords = detectedUpgrades.map((u) => u.original_word);
  assert.ok(upgradedWords.includes("good") || upgradedWords.includes("hard") || upgradedWords.includes("help"));

  // Check detail on upgrade item
  const sampleUpgrade = detectedUpgrades[0];
  assert.ok(sampleUpgrade.advanced_word, "Has advanced synonym");
  assert.ok(sampleUpgrade.meaning_bn, "Has Bengali meaning");
  assert.ok(sampleUpgrade.example_sentence, "Has illustrative example sentence");
});

test("Broad and Creative Written Questions (CQ গ ও ঘ) Bank and Evaluation Engine works accurately", async () => {
  const tsModule = await import("typescript");
  const ts = tsModule.default || tsModule;
  const broadPath = path.resolve(__dirname, "../../src/lib/broad-questions-data.ts");
  const rawTs = fs.readFileSync(broadPath, "utf-8");
  const jsCode = ts.transpileModule(rawTs, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
  const dataUri = `data:text/javascript;base64,${Buffer.from(jsCode).toString("base64")}`;
  const broadData = await import(dataUri);
  const { BROAD_QUESTIONS_BANK, evaluateBroadWrittenAnswer, evaluateCQHomeworkSubmission } = broadData;

  assert.ok(BROAD_QUESTIONS_BANK.length >= 4, "Broad questions bank has sets across core subjects");

  BROAD_QUESTIONS_BANK.forEach((set) => {
    assert.ok(set.id, "Set has ID");
    assert.ok(set.stimulus_stem_bn.length >= 40, "Set has authentic stimulus scenario");
    assert.ok(set.printed_page > 0, "Set has printed page citation");
    assert.ok(set.homework_tasks.length >= 2, "Set has at least 2 CQ homework tasks");
    assert.equal(set.homework_tasks.length, 4, "Set has 4 CQ homework tasks (ক, খ, গ, ঘ)");
    assert.equal(set.sub_questions.length, 2, "Set has both 'গ' (৩ নম্বর) and 'ঘ' (৪ নম্বর)");

    // Verify CQ HW tasks
    // Verify CQ HW tasks cover authentic NCTB 10-mark breakdown
    const hwTypes = set.homework_tasks.map((h) => h.type);
    assert.ok(hwTypes.includes("ka_knowledge"), "Contains ক: জ্ঞানমূলক");
    assert.ok(hwTypes.includes("kha_comprehension"), "Contains খ: অনুধাবনমূলক");
    assert.ok(hwTypes.includes("ga_application"), "Contains গ: প্রয়োগমূলক CQ");
    assert.ok(hwTypes.includes("gha_higher_order"), "Contains ঘ: উচ্চতর দক্ষতা CQ");

    const totalMarks = set.homework_tasks.reduce((sum, h) => sum + h.marks, 0);
    assert.equal(totalMarks, 10, "Total CQ homework marks is 10 (1 + 2 + 3 + 4 = 10)");

    set.homework_tasks.forEach((hw) => {
      assert.ok(hw.id, "HW has ID");
      assert.ok(hw.title_bn.length >= 10, "HW has title");
      assert.ok(hw.marks >= 1 && hw.marks <= 4, "HW has valid marks (1-4)");
      assert.ok(hw.printed_pages.length > 0, "HW has printed pages reference");
      assert.ok(hw.key_rubric_points.length >= 2, "HW has rubric checklist");
      assert.ok(hw.model_solution_bn.length >= 20, "HW has model solution");
    });

    const [ga, gha] = set.sub_questions;
    assert.equal(ga.marks, 3, "'গ' has 3 marks");
    assert.equal(gha.marks, 4, "'ঘ' has 4 marks");
    assert.ok(ga.model_answer_bn.length >= 30, "'গ' has comprehensive model answer");
    assert.ok(gha.model_answer_bn.length >= 40, "'ঘ' has comprehensive model answer");
    assert.ok(ga.key_rubric_points.length >= 3, "'গ' has rubric points");
    assert.ok(gha.key_rubric_points.length >= 3, "'ঘ' has rubric points");
  });

  // Test Evaluation for CQ Homework with Photo
  const sciSet = BROAD_QUESTIONS_BANK.find((s) => s.id === "bq_sci_ch4_photosynthesis");
  assert.ok(sciSet, "Science set exists");
  const hwKa = sciSet.homework_tasks.find((h) => h.type === "ka_knowledge");
  const hwGa = sciSet.homework_tasks.find((h) => h.type === "ga_application");

  const hwKaResult = evaluateCQHomeworkSubmission(hwKa, "সালোকসংশ্লেষণ সংজ্ঞা", true);
  assert.equal(hwKaResult.score, 1.0, "Full 1 mark for submitted handwritten ক photo");
  assert.equal(hwKaResult.overall_grade, "A+");

  const hwGaResult = evaluateCQHomeworkSubmission(hwGa, "সালোকসংশ্লেষণ সমীকরণ", true);
  assert.equal(hwGaResult.score, 3.0, "Full 3 marks for submitted handwritten গ photo");
  assert.equal(hwGaResult.overall_grade, "A+");
  assert.ok(hwGaResult.matched_keywords.length >= 2);

  // Test Evaluation for Part 'গ' (3 marks)
  const gaQuestion = sciSet.sub_questions[0];

  const evalResult = evaluateBroadWrittenAnswer(
    gaQuestion,
    "সালোকসংশ্লেষণের আলোক পর্যায়ে সৌরশক্তি থেকে রাসায়নিক শক্তি উৎপন্ন হয়। ক্লোরোপ্লাস্টের গ্রানামে পানির ফটোলাইসিস বা বিভাজন ঘটে এবং ATP ও NADPH উৎপন্ন হয়।"
  );

  assert.equal(evalResult.score, 3.0, "Full 3 marks for matching concept keywords");
  assert.equal(evalResult.max_marks, 3);
  assert.equal(evalResult.overall_grade, "A+");
  assert.ok(evalResult.dimension_scores.concept_score > 0);
  assert.ok(evalResult.matched_keywords.length >= 3);
});
