import React, { useState, useEffect } from "react";
import { TodayPayload, StudyTask } from "@/lib/types";
import { Language, translations, toBengaliDigits } from "@/lib/i18n";
import { MathRenderer } from "@/components/MathRenderer";
import {
  CheckCircle2,
  Circle,
  Flame,
  Calendar,
  Clock,
  BookOpen,
  Play,
  Sparkles,
  RotateCcw,
  AlertTriangle,
  Tag,
  HelpCircle,
  ShieldCheck,
  Check,
} from "lucide-react";
import { StudySessionRoomView } from "@/components/student/StudySessionRoomView";
import { enqueueCompletedStudySession } from "@/lib/revision-queue-engine";
import {
  detectPlannerPhase,
  generateExamModeDayPlan,
  ExamTimetableEntry,
  SubjectSyllabusInput,
  DayGapPlan,
  ScheduledStudyBlock,
  toBengaliNumber,
} from "@/lib/exam-mode-engine";

interface TodayViewProps {
  todayData: TodayPayload;
  lang: Language;
  studentName?: string;
  onToggleTask: (taskId: string, newStatus: "completed" | "pending") => void;
}

export const TodayView: React.FC<TodayViewProps> = ({
  todayData,
  lang,
  studentName = "তাহমিদ আলিম",
  onToggleTask,
}) => {
  const t = translations[lang];

  // Completed task ids
  const [completedTaskIds, setCompletedTaskIds] = useState<Set<string>>(() => {
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem("tb_completed_task_ids");
        if (stored) return new Set(JSON.parse(stored));
      } catch {}
    }
    return new Set();
  });

  const [selectedStudyTask, setSelectedStudyTask] = useState<StudyTask | null>(null);

  const [streakDays, setStreakDays] = useState<number>(() => {
    if (typeof window !== "undefined") {
      const s = localStorage.getItem("tb_streak_days");
      if (s !== null) return parseInt(s, 10) || 0;
    }
    return todayData.streak_days || 0;
  });

  // Timetable and Syllabus state
  const [timetable, setTimetable] = useState<ExamTimetableEntry[]>(() => {
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem("tb_exam_timetable");
        if (stored) return JSON.parse(stored);
      } catch {}
    }
    return [
      {
        id: "tt_default_01",
        series: "school_exam",
        subject_slug: "math",
        subject_name_bn: "সাধারণ গণিত",
        subject_name_en: "General Math",
        date: new Date(Date.now() + 5 * 86400000).toISOString().split("T")[0],
        start_time: "10:00",
        end_time: "13:00",
        marks_weight: 100,
      },
    ];
  });

  const [syllabusList, setSyllabusList] = useState<SubjectSyllabusInput[]>(() => {
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem("tb_exam_syllabus");
        if (stored) return JSON.parse(stored);
      } catch {}
    }
    return [
      {
        subject_slug: "math",
        has_remaining_syllabus: true,
        chapters: [
          {
            number: 2,
            title_bn: "মুনাফা ও চক্রবৃদ্ধি মূলধন",
            status: "partly",
            estimated_hours: 4.0,
            mastery_score: 0.35,
            why_sheet_reason: "কেন: গতবার ৫টির মধ্যে ২টি সঠিক; আরও অনুশীলন দরকার।",
          },
          {
            number: 3,
            title_bn: "বীজগণিতীয় সূত্রাবলি ও প্রয়োগ",
            status: "left",
            estimated_hours: 5.0,
            mastery_score: 0.4,
          },
        ],
      },
    ];
  });

  const [userChoice, setUserChoice] = useState<"raise_hours" | "prioritize" | "skim_only" | undefined>();
  const [examPlan, setExamPlan] = useState<DayGapPlan | null>(null);

  // Sync timetable and syllabus changes
  const reloadExamPlan = () => {
    const todayStr = new Date().toISOString().split("T")[0];
    let activeTt = timetable;
    let activeSyl = syllabusList;

    if (typeof window !== "undefined") {
      try {
        const storedTt = localStorage.getItem("tb_exam_timetable");
        if (storedTt) activeTt = JSON.parse(storedTt);
        const storedSyl = localStorage.getItem("tb_exam_syllabus");
        if (storedSyl) activeSyl = JSON.parse(storedSyl);
      } catch {}
    }

    setTimetable(activeTt);
    setSyllabusList(activeSyl);

    const generated = generateExamModeDayPlan({
      targetDate: todayStr,
      timetable: activeTt,
      syllabus: activeSyl,
      studentDailyHours: 6.0,
      userChoice,
      now: new Date(),
    });

    setExamPlan(generated);
  };

  useEffect(() => {
    reloadExamPlan();

    const handleUpdate = () => reloadExamPlan();
    window.addEventListener("tb_exam_plan_updated", handleUpdate);
    window.addEventListener("storage", handleUpdate);
    return () => {
      window.removeEventListener("tb_exam_plan_updated", handleUpdate);
      window.removeEventListener("storage", handleUpdate);
    };
  }, [userChoice]);

  // Phase detection
  const currentPhase = detectPlannerPhase(timetable, new Date());
  const isExamMode = currentPhase.is_exam_mode;

  // Single Replan Handler (Freezes completed blocks)
  const handleReplan = () => {
    if (!examPlan) return;
    const todayStr = new Date().toISOString().split("T")[0];
    const replanned = generateExamModeDayPlan({
      targetDate: todayStr,
      timetable,
      syllabus: syllabusList,
      studentDailyHours: 6.0,
      userChoice,
      frozenCompletedBlocks: examPlan.blocks,
      now: new Date(),
    });
    setExamPlan(replanned);
  };

  const handleToggleBlock = (blockId: string) => {
    setCompletedTaskIds((prev) => {
      const next = new Set(prev);
      if (next.has(blockId)) next.delete(blockId);
      else next.add(blockId);

      if (typeof window !== "undefined") {
        try {
          localStorage.setItem("tb_completed_task_ids", JSON.stringify(Array.from(next)));
        } catch {}
      }
      return next;
    });
    onToggleTask(blockId, completedTaskIds.has(blockId) ? "pending" : "completed");
  };

  const handleToggle = (task: StudyTask) => {
    const nextStatus: StudyTask["status"] = task.status === "completed" ? "pending" : "completed";
    handleToggleBlock(task.id);
  };

  const handleStudySessionComplete = (
    taskId: string,
    timeSpentSeconds: number,
    note: string,
    quizScore: number
  ) => {
    setCompletedTaskIds((prev) => {
      const next = new Set(prev);
      next.add(taskId);
      if (typeof window !== "undefined") {
        try {
          localStorage.setItem("tb_completed_task_ids", JSON.stringify(Array.from(next)));
        } catch {}
      }
      return next;
    });

    onToggleTask(taskId, "completed");
    setSelectedStudyTask(null);
  };

  if (selectedStudyTask) {
    return (
      <StudySessionRoomView
        task={selectedStudyTask}
        lang={lang}
        studentName={studentName}
        onBack={() => setSelectedStudyTask(null)}
        onComplete={handleStudySessionComplete}
      />
    );
  }

  // Determine badge label
  let inlineBadgeLabel = currentPhase.badge_label_bn;
  if (examPlan?.hours_to_next_exam !== undefined && examPlan.hours_to_next_exam <= 24 && examPlan.next_exam) {
    inlineBadgeLabel = `পরীক্ষার আগের দিন: ${examPlan.next_exam.subject_name_bn}`;
  }

  const completedBlocksCount = (examPlan?.blocks || []).filter((b) => completedTaskIds.has(b.id)).length;
  const totalBlocksCount = examPlan?.blocks.length || todayData.tasks.length || 1;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      {/* 1. Daily Overview Header with Exam Mode Badge */}
      <div
        className="card"
        style={{
          background: isExamMode
            ? "linear-gradient(135deg, rgba(99, 102, 241, 0.10) 0%, rgba(244, 63, 94, 0.08) 100%)"
            : "linear-gradient(135deg, rgba(37, 99, 235, 0.06) 0%, rgba(16, 185, 129, 0.08) 100%)",
          border: isExamMode ? "1px solid rgba(99, 102, 241, 0.3)" : "1px solid var(--color-border)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "var(--space-3)",
          padding: "var(--space-4) var(--space-6)",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Sparkles size={16} style={{ color: isExamMode ? "#6366f1" : "var(--color-primary)" }} />
            <span
              style={{
                fontSize: "var(--text-xs)",
                fontWeight: 800,
                color: isExamMode ? "#4f46e5" : "var(--color-primary)",
                padding: "2px 8px",
                borderRadius: "12px",
                backgroundColor: isExamMode ? "#e0e7ff" : "var(--color-primary-surface)",
              }}
            >
              {inlineBadgeLabel}
            </span>
          </div>
          <div style={{ fontSize: "var(--text-lg)", fontWeight: 800, marginTop: 4 }}>
            {lang === "bn" ? "আজকের পড়াশোনার পরিকল্পনা ও অগ্রগতি" : "Today's Study Plan & Progress"}
          </div>
        </div>

        {/* Replan Trigger Button */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            onClick={handleReplan}
            className="btn-secondary touch-target"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: "12px",
              fontWeight: 700,
              padding: "6px 14px",
              borderRadius: "10px",
              cursor: "pointer",
            }}
            title="সম্পন্ন কাজ অপরিবর্তিত রেখে নতুন করে শিডিউল তৈরি করুন"
          >
            <RotateCcw size={14} />
            <span>{lang === "bn" ? "পরিকল্পনা আবার বানাও" : "Replan"}</span>
          </button>
        </div>
      </div>

      {/* 2. Top Banner: Suspended Streak Pressure & Next-Exam Countdown */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "var(--space-4)",
        }}
      >
        {/* Streak card (Empathetic / Suspended during Exam Week) */}
        <div
          className="card"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-4)",
            borderLeft: isExamMode ? "4px solid #6366f1" : "4px solid var(--color-warning)",
          }}
        >
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: "var(--radius-full)",
              backgroundColor: isExamMode ? "#e0e7ff" : "var(--color-warning-surface)",
              color: isExamMode ? "#4f46e5" : "var(--color-warning)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <ShieldCheck size={28} />
          </div>
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
              {isExamMode ? "পরীক্ষার মানসিক স্বস্তি (No Streak Guilt)" : t.growthMindset.streakBadge}
            </div>
            <div style={{ fontSize: "var(--text-base)", fontWeight: 800, marginTop: 2 }}>
              {isExamMode
                ? "পরীক্ষা সপ্তাহে স্ট্রিকের চাপ নেই • প্রশান্ত মনে রিভিশন করো"
                : `${toBengaliDigits(streakDays)} দিন সক্রিয়`}
            </div>
          </div>
        </div>

        {/* Next-Exam Countdown & Explicit Gap Summary Line */}
        {examPlan && (
          <div
            className="card"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-4)",
              borderLeft: "4px solid var(--color-day-exam)",
            }}
          >
            <div
              style={{
                width: 52,
                height: 52,
                borderRadius: "var(--radius-full)",
                backgroundColor: "var(--color-primary-surface)",
                color: "var(--color-day-exam)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Calendar size={28} />
            </div>
            <div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
                {examPlan.next_exam ? examPlan.next_exam.subject_name_bn : "টার্গেট পরীক্ষা"}
              </div>
              <div style={{ fontSize: "var(--text-lg)", fontWeight: 800, color: "var(--color-text)" }}>
                {examPlan.gap_summary_line_bn}
              </div>
              <div style={{ fontSize: "11px", color: "var(--color-text-muted)", marginTop: 2 }}>
                ঘুম: {toBengaliNumber(examPlan.sleep_hours)} ঘণ্টা • বাফার: {toBengaliNumber(examPlan.buffer_hours)} ঘণ্টা • ৫০মি পড়া + ১০মি বিরতি
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 3. Feasibility Warning Alert & 3 Explicit Choices */}
      {examPlan?.feasibility_warning && (
        <div
          className="card"
          style={{
            borderLeft: "4px solid #f59e0b",
            backgroundColor: "rgba(245, 158, 11, 0.08)",
            padding: "var(--space-4)",
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-3)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <AlertTriangle size={18} style={{ color: "#d97706" }} />
            <span style={{ fontSize: "var(--text-sm)", fontWeight: 800, color: "#b45309" }}>
              {examPlan.feasibility_warning.message_bn}
            </span>
          </div>

          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)" }}>
            পরীক্ষার আগে সম্পূর্ণ সিলেবাস শেষ করার জন্য নিচের যেকোনো একটি কৌশল নির্বাচন করুন:
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 8 }}>
            {examPlan.feasibility_warning.options.map((opt) => (
              <button
                key={opt.id}
                onClick={() => setUserChoice(opt.id)}
                className="touch-target"
                style={{
                  padding: "10px 14px",
                  borderRadius: "8px",
                  border: userChoice === opt.id ? "2px solid #b45309" : "1px solid var(--color-border)",
                  backgroundColor: userChoice === opt.id ? "#fef3c7" : "var(--color-surface)",
                  textAlign: "left",
                  cursor: "pointer",
                }}
              >
                <div style={{ fontSize: "12px", fontWeight: 800, color: "#92400e" }}>{opt.title_bn}</div>
                <div style={{ fontSize: "11px", color: "var(--color-text-muted)", marginTop: 2 }}>
                  {opt.description_bn}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 4. Blocks List Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ fontSize: "var(--text-xl)", fontWeight: 700 }}>
            {isExamMode ? "আজকের গ্যাপ মাইক্রো-প্ল্যান ব্লকসমূহ" : t.student.todayHeader}
          </h2>
          <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>
            সম্পন্ন: {toBengaliDigits(completedBlocksCount)}/{toBengaliDigits(examPlan?.blocks.length || 0)}টি সেশন •
            নিট পড়ার সময়: {toBengaliNumber(examPlan?.net_study_hours || 6)} ঘণ্টা
          </p>
        </div>
      </div>

      {/* 5. Scheduled Study Blocks with Type Chips & Why-Sheet Explanations */}
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        {examPlan && examPlan.blocks.length > 0 ? (
          examPlan.blocks.map((block) => {
            const isCompleted = completedTaskIds.has(block.id);

            // Chip styling
            let chipBg = "#e0e7ff";
            let chipColor = "#4338ca";
            if (block.task_type === "remaining_syllabus") {
              chipBg = "#ffe4e6";
              chipColor = "#be123c"; // Crimson for "বাকি সিলেবাস"
            } else if (block.task_type === "needs_practice") {
              chipBg = "#fef3c7";
              chipColor = "#b45309"; // Amber for "আরও অনুশীলন"
            } else if (block.task_type === "formula_pass") {
              chipBg = "#ecfdf5";
              chipColor = "#047857"; // Emerald for "ফর্মুলা"
            } else if (block.task_type === "light_review") {
              chipBg = "#f3e8ff";
              chipColor = "#6b21a8"; // Purple for "হালকা রিভিশন"
            }

            return (
              <div
                key={block.id}
                className="card"
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "var(--space-3)",
                  opacity: isCompleted ? 0.85 : 1,
                  backgroundColor: isCompleted ? "var(--color-surface-hover)" : "var(--color-surface)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div style={{ display: "flex", alignItems: "flex-start", gap: "var(--space-3)" }}>
                    <button
                      onClick={() => handleToggleBlock(block.id)}
                      className="touch-target"
                      style={{ padding: 0, color: isCompleted ? "var(--color-success)" : "var(--color-text-muted)" }}
                      aria-label="সম্পন্ন হিসেবে চিহ্নিত করুন"
                    >
                      {isCompleted ? <CheckCircle2 size={24} /> : <Circle size={24} />}
                    </button>

                    <div>
                      {/* Meta Line: Subject, Time, and Type Chip */}
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                        <span
                          style={{
                            backgroundColor: "var(--color-primary-surface)",
                            color: "var(--color-primary)",
                            fontSize: "11px",
                            fontWeight: 700,
                            padding: "2px 8px",
                            borderRadius: "6px",
                          }}
                        >
                          {block.subject_name_bn}
                        </span>

                        {/* Block Type Chip */}
                        <span
                          style={{
                            backgroundColor: chipBg,
                            color: chipColor,
                            fontSize: "11px",
                            fontWeight: 800,
                            padding: "2px 8px",
                            borderRadius: "6px",
                          }}
                        >
                          {block.type_chip_bn}
                        </span>

                        <span
                          style={{
                            fontSize: "11px",
                            color: "var(--color-text-muted)",
                            display: "flex",
                            alignItems: "center",
                            gap: 4,
                            fontFamily: "monospace",
                          }}
                        >
                          <Clock size={12} />
                          {block.start_time} - {block.end_time} ({toBengaliDigits(block.duration_minutes)} মি)
                        </span>
                      </div>

                      <h3
                        style={{
                          fontSize: "var(--text-base)",
                          fontWeight: 700,
                          marginTop: "var(--space-1)",
                          textDecoration: isCompleted ? "line-through" : "none",
                        }}
                      >
                        {block.chapter_title_bn}
                      </h3>
                    </div>
                  </div>
                </div>

                {/* Why-Sheet Pedagogic Reason (Rule 6: Explainability) */}
                {block.why_sheet_reason && (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "var(--space-2)",
                      fontSize: "12px",
                      color: "var(--color-text-secondary)",
                      backgroundColor: "var(--color-surface-hover)",
                      padding: "var(--space-2) var(--space-3)",
                      borderRadius: "var(--radius-sm)",
                      borderLeft: "3px solid #6366f1",
                    }}
                  >
                    <HelpCircle size={14} style={{ color: "#6366f1", flexShrink: 0 }} />
                    <span>{block.why_sheet_reason}</span>
                  </div>
                )}

                {/* Math Exercise Reference if applicable */}
                {block.math_exercise_label && (
                  <div style={{ fontSize: "12px", color: "var(--color-primary)", fontWeight: 600 }}>
                    📖 পাঠ্যবইয়ের অনুশীলন: {block.math_exercise_label} (নমুনা ৩-৫টি বহুনির্বাচনি ও সৃজনশীল প্রশ্ন)
                  </div>
                )}

                {/* Action Bar */}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    paddingTop: "var(--space-2)",
                    borderTop: "1px solid var(--color-border)",
                    flexWrap: "wrap",
                    gap: "var(--space-2)",
                  }}
                >
                  <button
                    type="button"
                    onClick={() => {
                      const studyTaskAdapter: StudyTask = {
                        id: block.id,
                        subject: block.subject_name_bn,
                        title: `${block.subject_name_bn}: ${block.chapter_title_bn}`,
                        task_type: block.task_type === "remaining_syllabus" ? "study" : "revision",
                        estimated_minutes: block.duration_minutes,
                        status: isCompleted ? "completed" : "pending",
                        guidelines: block.why_sheet_reason,
                        chapter_title: block.chapter_title_bn,
                        book_title: `${block.subject_name_bn} (NCTB)`,
                        printed_page_start: 1,
                        printed_page_end: 15,
                      };
                      setSelectedStudyTask(studyTaskAdapter);
                    }}
                    className="btn-primary touch-target"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "var(--space-2)",
                      fontSize: "var(--text-xs)",
                      padding: "8px 16px",
                      borderRadius: "var(--radius-md)",
                      fontWeight: 700,
                    }}
                  >
                    <Play size={14} />
                    <span>
                      {isCompleted ? "সেশন পর্যালোচনা" : "পড়া ও অনুশীলন শুরু করুন"}
                    </span>
                  </button>

                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                    {isCompleted ? "আলহামদুলিল্লাহ, এই ব্লক সম্পন্ন হয়েছে!" : "৫০ মিনিট মনোযোগ + ১০ মিনিট বিরতি"}
                  </span>
                </div>
              </div>
            );
          })
        ) : (
          <div className="card" style={{ textAlign: "center", padding: "var(--space-8)" }}>
            <p style={{ color: "var(--color-text-muted)" }}>{t.student.noTasksToday}</p>
          </div>
        )}
      </div>
    </div>
  );
};
