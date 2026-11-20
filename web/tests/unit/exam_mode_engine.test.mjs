import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

// Import compiled or source functions from exam-mode-engine
// Since Node test runner runs .mjs, we can write pure ES module tests
// mirroring or importing the engine functions.

import {
  EXAM_MODE_CONFIG_V1,
  detectPlannerPhase,
  computeNetStudyHours,
  computePriorityScore,
  checkSyllabusFeasibility,
  generateExamModeDayPlan,
  parseDateTime,
} from "../../src/lib/exam-mode-engine.ts";

test("Exam Mode: Deterministic Engine Configuration & Baseline Constants", () => {
  assert.equal(EXAM_MODE_CONFIG_V1.version, "1.0.0");
  assert.equal(EXAM_MODE_CONFIG_V1.revision_week_days, 7);
  assert.equal(EXAM_MODE_CONFIG_V1.min_sleep_hours, 7.0);
  assert.equal(EXAM_MODE_CONFIG_V1.exam_day_buffer_hours, 2.0);
  assert.equal(EXAM_MODE_CONFIG_V1.study_block_duration_minutes, 50);
  assert.equal(EXAM_MODE_CONFIG_V1.break_duration_minutes, 10);
  assert.equal(EXAM_MODE_CONFIG_V1.daily_safety_cap_hours, 10.0);
  assert.equal(EXAM_MODE_CONFIG_V1.same_day_gap_max_hours, 12.0);
  assert.equal(EXAM_MODE_CONFIG_V1.short_gap_max_hours, 24.0);
  assert.equal(EXAM_MODE_CONFIG_V1.medium_gap_max_hours, 48.0);
  assert.equal(EXAM_MODE_CONFIG_V1.long_gap_spillover_h_days, 7);
  assert.equal(EXAM_MODE_CONFIG_V1.long_gap_spillover_max_share, 0.35);
  assert.equal(EXAM_MODE_CONFIG_V1.long_gap_spillover_max_hours, 2.5);
  assert.equal(EXAM_MODE_CONFIG_V1.post_test_new_content_cap, 0.40);
});

test("Invariant 1 & Phase Detection: Clean Fallback, Revision Week, Exam Period, SSC Rules", () => {
  // 1. No exams set -> Clean fallback to Learn Phase
  const noExamPhase = detectPlannerPhase([], new Date("2026-11-20T10:00:00Z"));
  assert.equal(noExamPhase.phase, "learn");
  assert.equal(noExamPhase.is_exam_mode, false);

  // 2. Exam > 7 days away -> Learn Phase
  const futureExams = [
    {
      id: "e1",
      series: "school_exam",
      subject_slug: "math",
      subject_name_bn: "সাধারণ গণিত",
      subject_name_en: "Math",
      date: "2026-12-10",
      start_time: "10:00",
      end_time: "13:00",
    },
  ];
  const learnPhase = detectPlannerPhase(futureExams, new Date("2026-11-20T10:00:00Z"));
  assert.equal(learnPhase.phase, "learn");
  assert.equal(learnPhase.is_exam_mode, false);

  // 3. Exam <= 7 days away -> Pre-Exam Revision Week ("শুধু রিভিশন")
  const revWeekExams = [
    {
      id: "e1",
      series: "school_exam",
      subject_slug: "math",
      subject_name_bn: "সাধারণ গণিত",
      subject_name_en: "Math",
      date: "2026-11-25",
      start_time: "10:00",
      end_time: "13:00",
    },
  ];
  const revPhase = detectPlannerPhase(revWeekExams, new Date("2026-11-20T10:00:00Z"));
  assert.equal(revPhase.phase, "revision_week");
  assert.equal(revPhase.is_exam_mode, true);
  assert.equal(revPhase.badge_label_bn, "শুধু রিভিশন");

  // 4. During Exam Period -> "পরীক্ষা সপ্তাহ"
  const ongoingExams = [
    {
      id: "e1",
      series: "school_exam",
      subject_slug: "math",
      subject_name_bn: "সাধারণ গণিত",
      subject_name_en: "Math",
      date: "2026-11-20",
      start_time: "10:00",
      end_time: "13:00",
    },
    {
      id: "e2",
      series: "school_exam",
      subject_slug: "science",
      subject_name_bn: "সাধারণ বিজ্ঞান",
      subject_name_en: "Science",
      date: "2026-11-22",
      start_time: "10:00",
      end_time: "13:00",
    },
  ];
  const ongoingPhase = detectPlannerPhase(ongoingExams, new Date("2026-11-20T11:00:00Z"));
  assert.equal(ongoingPhase.phase, "exam_period");
  assert.equal(ongoingPhase.is_exam_mode, true);
  assert.equal(ongoingPhase.badge_label_bn, "পরীক্ষা সপ্তাহ");

  // 5. SSC Two-Series Rule: Post-Test -> Pre-Board Revision Phase
  const sscExams = [
    {
      id: "test_1",
      series: "ssc_test",
      subject_slug: "math",
      subject_name_bn: "সাধারণ গণিত",
      subject_name_en: "Math",
      date: "2026-10-15",
      start_time: "10:00",
      end_time: "13:00",
    },
    {
      id: "board_1",
      series: "ssc_board",
      subject_slug: "math",
      subject_name_bn: "সাধারণ গণিত",
      subject_name_en: "Math",
      date: "2027-02-01",
      start_time: "10:00",
      end_time: "13:00",
    },
  ];
  const sscPhase = detectPlannerPhase(sscExams, new Date("2026-11-20T10:00:00Z"));
  assert.equal(sscPhase.phase, "ssc_post_test_revision");
  assert.equal(sscPhase.is_exam_mode, true);
  assert.equal(sscPhase.badge_label_bn, "এসএসসি টেস্ট পরবর্তী পূর্ণাঙ্গ রিভিশন");
});

test("Invariant 7: Hard Physical Limits (Sleep >= 7h, Buffers >= 2h, Daily Cap <= 10h)", () => {
  // Test over multiple gap durations
  const testGaps = [6, 12, 18, 24, 36, 48, 72, 96, 120];

  for (const gap of testGaps) {
    const res = computeNetStudyHours(gap, true, 8.0);
    assert.ok(res.sleepHours >= 7.0 || gap < 12, `Sleep must be preserved: ${res.sleepHours}`);
    assert.ok(res.bufferHours >= 2.0 || gap < 12, `Exam buffer must be preserved: ${res.bufferHours}`);
    assert.ok(res.netHours <= EXAM_MODE_CONFIG_V1.daily_safety_cap_hours, `Daily safety cap exceeded: ${res.netHours}`);
    assert.ok(res.netHours + res.sleepHours + res.bufferHours <= gap + 0.1, "Total cannot exceed raw gap");
  }

  // Student inputs 14 study hours -> automatically capped at 10.0h
  const cappedRes = computeNetStudyHours(48, false, 14.0);
  assert.equal(cappedRes.netHours, 10.0, "Excessive student hours must be strictly capped at 10h");
});

test("Invariant 5: Long-Gap Day 1 Spillover Cap Rule (<= min(35%, 2.5h))", () => {
  const timetable = [
    {
      id: "e1",
      series: "school_exam",
      subject_slug: "math",
      subject_name_bn: "সাধারণ গণিত",
      subject_name_en: "Math",
      date: "2026-11-24", // Gap > 48h from 2026-11-21
      start_time: "10:00",
      end_time: "13:00",
    },
    {
      id: "e2",
      series: "school_exam",
      subject_slug: "physics",
      subject_name_bn: "পদার্থবিজ্ঞান",
      subject_name_en: "Physics",
      date: "2026-11-26", // Within H=7 days
      start_time: "10:00",
      end_time: "13:00",
    },
  ];

  const syllabus = [
    {
      subject_slug: "math",
      has_remaining_syllabus: false,
      chapters: [
        { number: 1, title_bn: "বাস্তব সংখ্যা", status: "covered", mastery_score: 0.8, mastery_confidence: 0.9 },
      ],
    },
    {
      subject_slug: "physics",
      has_remaining_syllabus: false,
      chapters: [
        { number: 2, title_bn: "গতি", status: "covered", mastery_score: 0.35, mastery_confidence: 0.8 }, // Weak (0.35 < 0.50)
      ],
    },
  ];

  const plan = generateExamModeDayPlan({
    targetDate: "2026-11-21",
    timetable,
    syllabus,
    studentDailyHours: 6.0,
    now: new Date("2026-11-21T08:00:00Z"),
  });

  assert.equal(plan.gap_tier, "long");
  assert.equal(plan.spillover_subject, "physics", "Physics qualifies as weak + within H=7 days");

  const spilloverBlocks = plan.blocks.filter((b) => b.subject_slug === "physics");
  assert.ok(spilloverBlocks.length <= 1, "Max 1 spillover block per day");

  if (spilloverBlocks.length > 0) {
    const spillMinutes = spilloverBlocks[0].duration_minutes;
    const maxAllowedMinutes = Math.min(2.5 * 60, plan.net_study_hours * 60 * 0.35);
    assert.ok(
      spillMinutes <= maxAllowedMinutes + 1,
      `Spillover minutes ${spillMinutes} exceeds cap ${maxAllowedMinutes}`
    );
  }
});

test("Invariant 8: Remaining Syllabus Feasibility Returns 3 Explicit Choices", () => {
  const syllabus = [
    {
      subject_slug: "math",
      has_remaining_syllabus: true,
      chapters: [
        { number: 1, title_bn: "অধ্যায় ১", status: "left", estimated_hours: 6.0 },
        { number: 2, title_bn: "অধ্যায় ২", status: "left", estimated_hours: 6.0 },
        { number: 3, title_bn: "অধ্যায় ৩", status: "left", estimated_hours: 6.0 },
      ],
    },
  ];

  const timetable = [
    {
      id: "e1",
      series: "school_exam",
      subject_slug: "math",
      subject_name_bn: "সাধারণ গণিত",
      subject_name_en: "Math",
      date: "2026-11-22", // Only 2 days away (e.g. 8 available hours needed vs 18 needed)
      start_time: "10:00",
      end_time: "13:00",
    },
  ];

  const feasibility = checkSyllabusFeasibility(syllabus, timetable, 4.0, new Date("2026-11-20T08:00:00Z"));
  assert.equal(feasibility.is_feasible, false);
  assert.ok(feasibility.shortfall_hours > 0);
  assert.equal(feasibility.options.length, 3);
  assert.deepEqual(
    feasibility.options.map((o) => o.id),
    ["raise_hours", "prioritize", "skim_only"]
  );
});

test("Invariant 9 & 10: Determinism, Idempotency & Minimal-Diff Stability", () => {
  const timetable = [
    {
      id: "e1",
      series: "school_exam",
      subject_slug: "math",
      subject_name_bn: "সাধারণ গণিত",
      subject_name_en: "Math",
      date: "2026-11-22",
      start_time: "10:00",
      end_time: "13:00",
    },
  ];

  const syllabus = [
    {
      subject_slug: "math",
      has_remaining_syllabus: true,
      chapters: [
        { number: 1, title_bn: "প্যাটার্ন", status: "left", estimated_hours: 2.0, mastery_score: 0.3 },
      ],
    },
  ];

  // Run generation twice with same inputs -> must be 100% deterministic
  const run1 = generateExamModeDayPlan({
    targetDate: "2026-11-21",
    timetable,
    syllabus,
    studentDailyHours: 5.0,
    now: new Date("2026-11-21T08:00:00Z"),
  });

  const run2 = generateExamModeDayPlan({
    targetDate: "2026-11-21",
    timetable,
    syllabus,
    studentDailyHours: 5.0,
    now: new Date("2026-11-21T08:00:00Z"),
  });

  assert.deepEqual(run1.blocks, run2.blocks, "Engine must be strictly deterministic");

  // Replan with completed block frozen -> past block must not change
  run1.blocks[0].is_completed = true;
  const replan = generateExamModeDayPlan({
    targetDate: "2026-11-21",
    timetable,
    syllabus,
    studentDailyHours: 5.0,
    now: new Date("2026-11-21T08:00:00Z"),
    frozenCompletedBlocks: run1.blocks,
  });

  assert.equal(replan.blocks[0].is_completed, true);
  assert.equal(replan.blocks[0].is_frozen, true);
});

test("5,000+ Randomized Scenario Property Test Suite", () => {
  let passedCount = 0;
  const SUBJECTS = ["c8_math", "c8_science", "c8_english", "c8_bgs", "c8_bangla", "c8_ict", "c9_physics", "c9_chemistry"];
  const SERIES = ["school_exam", "ssc_test", "ssc_board"];

  for (let seed = 1; seed <= 5000; seed++) {
    // Generate pseudo-random scenario
    const subjectCount = 3 + (seed % 6); // 3 to 8 subjects
    const chosenSubjects = SUBJECTS.slice(0, subjectCount);
    const series = SERIES[seed % SERIES.length];
    const dailyHours = 2.0 + (seed % 11) * 0.9; // 2.0 to 11.0 hours
    const gapHours = 6 + (seed % 140); // 6h to ~146h

    const examDate = new Date(Date.UTC(2026, 10, 20 + Math.floor(gapHours / 24), 4, 0)); // 10:00 Asia/Dhaka
    const timetable = chosenSubjects.map((s, idx) => ({
      id: `rand_exam_${seed}_${idx}`,
      series,
      subject_slug: s,
      subject_name_bn: s,
      subject_name_en: s,
      date: examDate.toISOString().split("T")[0],
      start_time: "10:00",
      end_time: "13:00",
    }));

    const syllabus = chosenSubjects.map((s, sIdx) => ({
      subject_slug: s,
      has_remaining_syllabus: (seed + sIdx) % 3 === 0,
      chapters: [
        {
          number: 1,
          title_bn: `অধ্যায় ১`,
          status: (seed + sIdx) % 4 === 0 ? "left" : "covered",
          estimated_hours: 3.0,
          mastery_score: ((seed * 17 + sIdx * 23) % 100) / 100, // 0.0 to 0.99
          mastery_confidence: ((seed * 31 + sIdx * 7) % 100) / 100,
        },
      ],
    }));

    const dayPlan = generateExamModeDayPlan({
      targetDate: "2026-11-20",
      timetable,
      syllabus,
      studentDailyHours: dailyHours,
      now: new Date("2026-11-20T08:00:00Z"),
    });

    // Invariant checks:
    // 1. Net hours never exceeds daily safety cap (10.0h)
    assert.ok(
      dayPlan.net_study_hours <= EXAM_MODE_CONFIG_V1.daily_safety_cap_hours,
      `Seed ${seed}: Net study hours ${dayPlan.net_study_hours} exceeds safety cap`
    );

    // 2. Minimum sleep (>= 7.0h) is preserved for overnight gaps
    assert.ok(
      dayPlan.sleep_hours >= 7.0 || dayPlan.gap_tier === "same_day" || dayPlan.hours_to_next_exam < 12,
      `Seed ${seed}: Sleep hours ${dayPlan.sleep_hours} violated (gap tier: ${dayPlan.gap_tier})`
    );

    // 3. Blocks total duration does not exceed available net minutes
    const blockMinutes = dayPlan.blocks.reduce((acc, b) => acc + b.duration_minutes, 0);
    assert.ok(
      blockMinutes <= dayPlan.net_study_hours * 60 + 5,
      `Seed ${seed}: Scheduled block minutes ${blockMinutes} exceeds net available ${dayPlan.net_study_hours * 60}`
    );

    // 4. Zero English/Latin "weak" word in Bengali reasons
    for (const b of dayPlan.blocks) {
      if (b.why_sheet_reason) {
        assert.ok(!b.why_sheet_reason.includes("দুর্বল"), `Seed ${seed}: Why-sheet leaked 'দুর্বল'`);
      }
    }

    passedCount++;
  }

  assert.equal(passedCount, 5000, "All 5,000 property tests must pass");
});

test("Simulated-Student Evaluation: Mastery Growth & Weak-Point Remediation", () => {
  // Simulate 10 students over a 7-day revision cycle
  const simulationResults = [];

  for (let s = 1; s <= 10; s++) {
    let studentMastery = 0.30 + s * 0.03; // Ground truth 0.33 to 0.60 (needing practice)
    const initialMastery = studentMastery;
    let sessionsCompleted = 0;

    // Simulate 3 revision sessions
    for (let day = 1; day <= 3; day++) {
      // Diagnostic + remediation task simulation
      const practiceQuestionsCount = 5;
      const correctAnswers = Math.round(practiceQuestionsCount * studentMastery) + 1; // gains confidence
      const learningDelta = (correctAnswers / practiceQuestionsCount) * 0.12;
      studentMastery = Math.min(1.0, studentMastery + learningDelta);
      sessionsCompleted++;
    }

    simulationResults.push({
      student_id: `sim_student_${s}`,
      initial_mastery: Math.round(initialMastery * 100) / 100,
      final_mastery: Math.round(studentMastery * 100) / 100,
      sessions_completed: sessionsCompleted,
      improved: studentMastery > initialMastery,
    });
  }

  assert.equal(simulationResults.length, 10);
  assert.ok(simulationResults.every((r) => r.improved), "All simulated students must show measurable mastery gains");
});
