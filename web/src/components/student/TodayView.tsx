import React, { useState } from "react";
import { TodayPayload, StudyTask } from "@/lib/types";
import { Language, translations, toBengaliDigits } from "@/lib/i18n";
import { MathRenderer } from "@/components/MathRenderer";
import { CheckCircle2, Circle, Flame, Calendar, Clock, BookOpen, Play, Sparkles } from "lucide-react";
import { StudySessionRoomView } from "@/components/student/StudySessionRoomView";


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
  const [tasks, setTasks] = useState<StudyTask[]>(todayData.tasks);
  const [selectedStudyTask, setSelectedStudyTask] = useState<StudyTask | null>(null);

  const handleToggle = (task: StudyTask) => {
    const nextStatus = task.status === "completed" ? "pending" : "completed";
    setTasks((prev) =>
      prev.map((t) => (t.id === task.id ? { ...t, status: nextStatus } : t))
    );
    onToggleTask(task.id, nextStatus);
  };

  const handleStudySessionComplete = (
    taskId: string,
    timeSpentSeconds: number,
    note: string,
    quizScore: number
  ) => {
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, status: "completed" } : t))
    );
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

  const streakDisplay = lang === "bn" ? toBengaliDigits(todayData.streak_days) : todayData.streak_days;
  const remainingMinutesDisplay =
    lang === "bn" ? toBengaliDigits(todayData.remaining_minutes) : todayData.remaining_minutes;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      {/* Daily Overview Header */}
      <div
        className="card"
        style={{
          background: "linear-gradient(135deg, rgba(37, 99, 235, 0.06) 0%, rgba(16, 185, 129, 0.08) 100%)",
          border: "1px solid var(--color-border)",
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
            <Sparkles size={16} style={{ color: "var(--color-primary)" }} />
            <span style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-primary)" }}>
              {lang === "bn" ? "দৈনিক ড্যাশবোর্ড" : "Daily Dashboard"}
            </span>
          </div>
          <div style={{ fontSize: "var(--text-lg)", fontWeight: 800, marginTop: 2 }}>
            {lang === "bn" ? "আজকের পড়াশোনার পরিকল্পনা ও অগ্রগতি" : "Today's Study Plan & Progress"}
          </div>
        </div>

        <div
          style={{
            backgroundColor: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-lg)",
            padding: "var(--space-2) var(--space-4)",
            textAlign: "center",
          }}
        >
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
            {lang === "bn" ? "সাপ্তাহিক রুটিন" : "Weekly Schedule"}
          </div>
          <div style={{ fontSize: "var(--text-sm)", fontWeight: 700, color: "var(--color-success)" }}>
            {lang === "bn" ? "৭ দিনই সক্রিয় (কোনো অফ-ডে নেই)" : "Active All 7 Days"}
          </div>
        </div>
      </div>

      {/* Top Banner: Streak and Exam Countdown */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "var(--space-4)",
        }}
      >
        {/* Streak card */}
        <div
          className="card"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-4)",
            borderLeft: "4px solid var(--color-warning)",
          }}
        >
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: "var(--radius-full)",
              backgroundColor: "var(--color-warning-surface)",
              color: "var(--color-warning)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Flame size={28} />
          </div>
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
              {t.growthMindset.streakBadge}
            </div>
            <div style={{ fontSize: "var(--text-2xl)", fontWeight: 700 }}>
              {streakDisplay} {t.growthMindset.streakDays}
            </div>
          </div>
        </div>

        {/* Exam Countdown card */}
        {todayData.exam_countdown && (
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
                {t.student.examCountdown}: {todayData.exam_countdown.exam_name}
              </div>
              <div style={{ fontSize: "var(--text-2xl)", fontWeight: 700 }}>
                {lang === "bn"
                  ? toBengaliDigits(todayData.exam_countdown.days_left)
                  : todayData.exam_countdown.days_left}{" "}
                {t.student.daysLeft}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Today's Tasks Header & Summary */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ fontSize: "var(--text-xl)", fontWeight: 700 }}>{t.student.todayHeader}</h2>
          <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>
            {t.growthMindset.timeSpent}: {remainingMinutesDisplay} {t.growthMindset.minutes}
          </p>
        </div>
      </div>

      {/* Task List */}
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        {tasks.length === 0 ? (
          <div className="card" style={{ textAlign: "center", padding: "var(--space-8)" }}>
            <p style={{ color: "var(--color-text-muted)" }}>{t.student.noTasksToday}</p>
          </div>
        ) : (
          tasks.map((task) => {
            const isCompleted = task.status === "completed";
            const minDisplay =
              lang === "bn" ? toBengaliDigits(task.estimated_minutes) : task.estimated_minutes;

            return (
              <div
                key={task.id}
                className={`card ${isCompleted ? "badge-success" : ""}`}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "var(--space-3)",
                  opacity: isCompleted ? 0.85 : 1,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div style={{ display: "flex", alignItems: "flex-start", gap: "var(--space-3)" }}>
                    <button
                      onClick={() => handleToggle(task)}
                      className="touch-target"
                      style={{ padding: 0, color: isCompleted ? "var(--color-success)" : "var(--color-text-muted)" }}
                      aria-label={isCompleted ? t.student.markIncomplete : t.student.markComplete}
                    >
                      {isCompleted ? <CheckCircle2 size={24} /> : <Circle size={24} />}
                    </button>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                        <span
                          className="badge"
                          style={{
                            backgroundColor: "var(--color-primary-surface)",
                            color: "var(--color-primary)",
                            fontSize: "var(--text-xs)",
                          }}
                        >
                          {task.subject}
                        </span>
                        <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "flex", alignItems: "center", gap: 4 }}>
                          <Clock size={12} />
                          {minDisplay} {t.growthMindset.minutesAbbr}
                        </span>
                      </div>
                      <h3
                        style={{
                          fontSize: "var(--text-base)",
                          fontWeight: 600,
                          marginTop: "var(--space-1)",
                          textDecoration: isCompleted ? "line-through" : "none",
                        }}
                      >
                        {task.title}
                      </h3>
                    </div>
                  </div>
                </div>

                {/* Printed textbook citations (Rule 8: Printed Page != PDF index) */}
                {task.printed_page_start && (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "var(--space-2)",
                      fontSize: "var(--text-xs)",
                      color: "var(--color-text-secondary)",
                      backgroundColor: "var(--color-surface-hover)",
                      padding: "var(--space-2) var(--space-3)",
                      borderRadius: "var(--radius-sm)",
                    }}
                  >
                    <BookOpen size={14} />
                    <span>
                      {task.book_title} — {t.student.printedPage}:{" "}
                      {lang === "bn"
                        ? `${toBengaliDigits(task.printed_page_start)} - ${toBengaliDigits(task.printed_page_end || task.printed_page_start)}`
                        : `${task.printed_page_start} - ${task.printed_page_end || task.printed_page_start}`}
                    </span>
                  </div>
                )}

                {/* Guidelines */}
                {task.guidelines && (
                  <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
                    <MathRenderer content={task.guidelines} />
                  </div>
                )}

                {/* Launch Study Session Room Button */}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginTop: "var(--space-2)",
                    paddingTop: "var(--space-3)",
                    borderTop: "1px solid var(--color-border)",
                    flexWrap: "wrap",
                    gap: "var(--space-2)",
                  }}
                >
                  <button
                    type="button"
                    onClick={() => setSelectedStudyTask(task)}
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
                      {lang === "bn"
                        ? isCompleted
                          ? "পুনরায় স্টাডি সেশন দেখুন"
                          : "পড়া শুরু করুন"
                        : isCompleted
                        ? "Review Study Session"
                        : "Start Study Session"}
                    </span>
                  </button>

                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                    {isCompleted
                      ? (lang === "bn" ? "আলহামদুলিল্লাহ, পড়া সম্পন্ন হয়েছে!" : "Alhamdulillah, Completed!")
                      : (lang === "bn" ? "স্টপওয়াচ, লক্ষ্য ট্র্যাকিং ও কুইজ অন্তর্ভুক্ত" : "Includes stopwatch, split-targets & quiz")}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
