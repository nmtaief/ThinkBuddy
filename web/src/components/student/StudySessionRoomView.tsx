"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import { StudyTask, PageStudyBreakdown, HomeworkTask } from "@/lib/types";
import { Language, translations, toBengaliDigits } from "@/lib/i18n";
import {
  enrichStudyTaskWithCurriculumData,
  getStudyBreakdownForTask,
  StudySessionQuizQuestion,
} from "@/lib/curriculum-study-engine";
import {
  Clock,
  Play,
  Pause,
  RotateCcw,
  CheckCircle2,
  Circle,
  BookOpen,
  ArrowLeft,
  FileText,
  HelpCircle,
  Award,
  Sparkles,
  Save,
  Check,
  Flame,
  Layers,
  ListTodo,
  CheckSquare,
  ShieldCheck,
  Star,
  Bot,
  RefreshCw,
  GraduationCap,
} from "lucide-react";

interface StudySessionRoomViewProps {
  task: StudyTask;
  lang: Language;
  studentName?: string;
  onBack: () => void;
  onComplete: (taskId: string, timeSpentSeconds: number, note: string, quizScore: number) => void;
}

interface PageStudyState {
  page: number;
  completed: boolean;
  timeTakenSeconds?: number;
}

export const StudySessionRoomView: React.FC<StudySessionRoomViewProps> = ({
  task,
  lang,
  studentName = "তাহমিদ আলিম",
  onBack,
  onComplete,
}) => {
  const t = translations[lang];

  // Stopwatch state
  const [secondsElapsed, setSecondsElapsed] = useState(0);
  const [isRunning, setIsRunning] = useState(true);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (isRunning) {
      timerRef.current = setInterval(() => {
        setSecondsElapsed((prev) => prev + 1);
      }, 1000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isRunning]);

  const toggleStopwatch = () => setIsRunning((prev) => !prev);
  const resetStopwatch = () => {
    setIsRunning(false);
    setSecondsElapsed(0);
  };

  const formatTimer = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    const formatted = `${String(mins).padStart(2, "0")} : ${String(secs).padStart(2, "0")}`;
    return lang === "bn" ? toBengaliDigits(formatted) : formatted;
  };

  // Dynamically resolve authentic NCTB curriculum pages & board homework tasks
  const enrichedTask = useMemo(() => {
    return enrichStudyTaskWithCurriculumData(task);
  }, [task]);

  const curriculumData = useMemo(() => {
    let derivedChapter = 1;
    const numMatch = task.title.match(/অধ্যায়\s*(\d+)|Chapter\s*(\d+)|Unit\s*(\d+)|(\d+)/i);
    if (numMatch) {
      derivedChapter = parseInt(numMatch[1] || numMatch[2] || numMatch[3] || numMatch[4], 10) || 1;
    }
    return getStudyBreakdownForTask({
      subjectSlug: task.subject,
      subjectName: task.subject,
      chapterNumber: derivedChapter,
      chapterTitle: task.title,
      part: task.chapter_part || 1,
      totalParts: task.chapter_total_parts || 3,
    });
  }, [task]);

  const chapterPart = enrichedTask.chapter_part || 1;
  const chapterTotalParts = enrichedTask.chapter_total_parts || 3;
  const defaultPagesBreakdown: PageStudyBreakdown[] = enrichedTask.pages_breakdown || [];
  const defaultHomework: HomeworkTask[] = enrichedTask.homework_tasks || [];

  const startPage = defaultPagesBreakdown[0]?.page || enrichedTask.printed_page_start || 1;
  const endPage = defaultPagesBreakdown[defaultPagesBreakdown.length - 1]?.page || enrichedTask.printed_page_end || startPage;

  // Track page study progress & split times
  const [pagesProgress, setPagesProgress] = useState<PageStudyState[]>(() =>
    defaultPagesBreakdown.map((p) => ({
      page: p.page,
      completed: false,
    }))
  );

  useEffect(() => {
    setPagesProgress(
      defaultPagesBreakdown.map((p) => ({
        page: p.page,
        completed: false,
      }))
    );
  }, [task]);

  const handleTogglePage = (pageNumber: number) => {
    setPagesProgress((prev) =>
      prev.map((item) => {
        if (item.page === pageNumber) {
          const willComplete = !item.completed;
          return {
            ...item,
            completed: willComplete,
            timeTakenSeconds: willComplete ? secondsElapsed : item.timeTakenSeconds,
          };
        }
        return item;
      })
    );
  };

  const [homeworkList, setHomeworkList] = useState<HomeworkTask[]>(() => defaultHomework);

  useEffect(() => {
    setHomeworkList(defaultHomework);
  }, [task]);

  const handleToggleHomework = (hwId: string) => {
    setHomeworkList((prev) =>
      prev.map((hw) => (hw.id === hwId ? { ...hw, completed: !hw.completed } : hw))
    );
  };

  // Class level detection: Class 6/7 are strictly School Assessments (No Board exams in Bangladesh)
  const classMatch = (task.subject || "").match(/^c(\d+)_/i) || (task.title || "").match(/শ্রেণি\s*(\d+)|Class\s*(\d+)/i);
  const classLevelNum = classMatch ? parseInt(classMatch[1] || classMatch[2], 10) : 8;
  const isSchoolExamOnly = classLevelNum <= 7;

  // Post-Study Mastery Check Quiz (Dynamic & AI-driven)
  const [quizStarted, setQuizStarted] = useState(false);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, number>>({});
  const [quizSubmitted, setQuizSubmitted] = useState(false);
  const [quizScore, setQuizScore] = useState(0);
  const [isAiGeneratingQuiz, setIsAiGeneratingQuiz] = useState(false);

  const initialQuestions: StudySessionQuizQuestion[] = useMemo(() => {
    return curriculumData.quiz_questions && curriculumData.quiz_questions.length > 0
      ? curriculumData.quiz_questions
      : [];
  }, [curriculumData]);

  const [quizQuestions, setQuizQuestions] = useState<StudySessionQuizQuestion[]>(initialQuestions);

  useEffect(() => {
    if (curriculumData.quiz_questions && curriculumData.quiz_questions.length > 0) {
      setQuizQuestions(curriculumData.quiz_questions);
      setSelectedAnswers({});
      setQuizSubmitted(false);
      setQuizScore(0);
    }
  }, [curriculumData]);

  const handleGenerateAiQuiz = async () => {
    setIsAiGeneratingQuiz(true);
    try {
      const freshSeed = Date.now();
      const res = await fetch("/api/curriculum/quiz", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          subject: task.subject,
          chapterTitle: task.title,
          classLevel: classLevelNum,
          startPage,
          endPage,
          count: 15,
          seed: freshSeed,
        }),
      });
      const data = await res.json();
      if (data.success && data.data?.questions) {
        setQuizQuestions(data.data.questions);
        setSelectedAnswers({});
        setQuizSubmitted(false);
        setQuizScore(0);
        setQuizStarted(true);
      }
    } catch (err) {
      console.error("AI quiz generation error:", err);
    } finally {
      setIsAiGeneratingQuiz(false);
    }
  };

  const handleSelectAnswer = (qId: string, optIndex: number) => {
    if (quizSubmitted) return;
    setSelectedAnswers((prev) => ({ ...prev, [qId]: optIndex }));
  };

  const handleSubmitQuiz = () => {
    let score = 0;
    quizQuestions.forEach((q) => {
      if (selectedAnswers[q.id] === q.correctIndex) {
        score += 1;
      }
    });
    setQuizScore(score);
    setQuizSubmitted(true);
  };

  const handleFinishSession = () => {
    onComplete(task.id, secondsElapsed, "", quizSubmitted ? quizScore : 3);
  };

  const completedPagesCount = pagesProgress.filter((p) => p.completed).length;
  const completedHwCount = homeworkList.filter((h) => h.completed).length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      {/* Top Header Navigation */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-3)" }}>
        <button
          onClick={onBack}
          className="btn-secondary touch-target"
          style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--text-sm)" }}
        >
          <ArrowLeft size={16} />
          <span>{lang === "bn" ? "আজকের রুটিনে ফিরে যান" : "Back to Today"}</span>
        </button>

        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
          <span
            className="badge"
            style={{
              backgroundColor: "var(--color-primary-surface)",
              color: "var(--color-primary)",
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 12px",
              borderRadius: "var(--radius-full)",
              fontSize: "var(--text-xs)",
              fontWeight: 700,
            }}
          >
          </span>

          <span
            className="badge"
            style={{
              backgroundColor: "rgba(16, 185, 129, 0.12)",
              color: "var(--color-success)",
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 12px",
              borderRadius: "var(--radius-full)",
              fontSize: "var(--text-xs)",
              fontWeight: 700,
            }}
          >
            <ShieldCheck size={14} />
            <span>ThinkBuddy Pro Verified</span>
          </span>
        </div>
      </div>



      {/* Chapter 3-Part Chunking & Textbook Citation Card */}
      <div
        className="card"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "var(--space-4)",
          backgroundColor: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          padding: "var(--space-5)",
          borderRadius: "var(--radius-lg)",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap" }}>
            <span
              className="badge"
              style={{
                backgroundColor: "var(--color-primary-surface)",
                color: "var(--color-primary)",
                fontWeight: 700,
                fontSize: "var(--text-xs)",
              }}
            >
              {task.subject}
            </span>

            {/* Pedagogical Chunking Badge (3 Parts standard, max 4) */}
            <span
              className="badge"
              style={{
                backgroundColor: "rgba(245, 158, 11, 0.12)",
                color: "var(--color-warning)",
                fontWeight: 700,
                fontSize: "var(--text-xs)",
                display: "flex",
                alignItems: "center",
                gap: 5,
              }}
            >
              <Layers size={13} />
              <span>
                {lang === "bn"
                  ? `অধ্যায় বিভাজন: অংশ ${toBengaliDigits(chapterPart)} / ${toBengaliDigits(chapterTotalParts)}`
                  : `Chapter Chunk: Part ${chapterPart} of ${chapterTotalParts}`}
              </span>
            </span>

            <span
              style={{
                fontSize: "var(--text-xs)",
                color: "var(--color-text-muted)",
              }}
            >
              {lang === "bn"
                ? "(অধ্যায় ৩ ভাগে বিন্যস্ত, অতিরিক্ত বোঝা পরিহার্য)"
                : "(3 balanced parts per chapter, avoiding cognitive overload)"}
            </span>
          </div>

          <h1 style={{ fontSize: "var(--text-2xl)", fontWeight: 800, margin: 0 }}>
            {task.title}
          </h1>

          {/* Rule 8: Printed Textbook Page Citation */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "var(--space-2)",
              fontSize: "var(--text-sm)",
              color: "var(--color-text-secondary)",
            }}
          >
            <BookOpen size={16} />
            <span style={{ fontWeight: 600 }}>
              {task.book_title || "সাধারণ বিজ্ঞান (NCTB)"} — {t.student.printedPage}:{" "}
              <strong style={{ color: "var(--color-primary)" }}>
                {lang === "bn"
                  ? `${toBengaliDigits(task.printed_page_start || 42)} – ${toBengaliDigits(task.printed_page_end || 44)}`
                  : `${task.printed_page_start || 42} – ${task.printed_page_end || 44}`}
              </strong>
            </span>
          </div>
        </div>

        {/* Live Digital Stopwatch */}
        <div
          style={{
            backgroundColor: "var(--color-bg)",
            border: "2px solid var(--color-border)",
            borderRadius: "var(--radius-xl)",
            padding: "var(--space-4) var(--space-6)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "var(--space-2)",
            minWidth: 200,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
            <Clock size={14} />
            <span>{lang === "bn" ? "অধ্যয়ন স্টপওয়াচ" : "Study Stopwatch"}</span>
          </div>

          <div
            style={{
              fontSize: "var(--text-3xl)",
              fontFamily: "monospace",
              fontWeight: 800,
              color: isRunning ? "var(--color-primary)" : "var(--color-text-secondary)",
              letterSpacing: 2,
            }}
          >
            {formatTimer(secondsElapsed)}
          </div>

          <div style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-1)" }}>
            <button
              onClick={toggleStopwatch}
              className="btn-primary touch-target"
              style={{
                padding: "6px 14px",
                fontSize: "var(--text-xs)",
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              {isRunning ? <Pause size={13} /> : <Play size={13} />}
              <span>{isRunning ? (lang === "bn" ? "বিরতি" : "Pause") : (lang === "bn" ? "চালু" : "Resume")}</span>
            </button>

            <button
              onClick={resetStopwatch}
              className="btn-secondary touch-target"
              style={{
                padding: "6px 10px",
                fontSize: "var(--text-xs)",
              }}
              title={lang === "bn" ? "রিসেট করুন" : "Reset Timer"}
            >
              <RotateCcw size={13} />
            </button>
          </div>
        </div>
      </div>

      {/* SECTION 1: Page-by-Page Progress with Immediate Summary on Each Page */}
      <div className="card" style={{ padding: "var(--space-6)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)", flexWrap: "wrap", gap: "var(--space-2)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <BookOpen size={20} style={{ color: "var(--color-primary)" }} />
            <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
              {lang === "bn" ? "পৃষ্ঠাভিত্তিক অধ্যয়ন ও সারসংক্ষেপ" : "Page-by-Page Study & Immediate Summaries"}
            </h2>
          </div>

          <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
            {lang === "bn"
              ? `সম্পন্ন: ${toBengaliDigits(completedPagesCount)} / ${toBengaliDigits(defaultPagesBreakdown.length)} পৃষ্ঠা`
              : `Completed: ${completedPagesCount} / ${defaultPagesBreakdown.length} Pages`}
          </span>
        </div>

        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", marginBottom: "var(--space-4)" }}>
          {lang === "bn"
            ? "পাঠ্যবইয়ের পৃষ্ঠাগুলো ক্রমানুসারে পড়ুন। প্রতিটি পৃষ্ঠা পড়া শেষ হলে টিক দিন; সাথে সাথে ঐ পৃষ্ঠার মূল সারসংক্ষেপ ও গুরুত্বপূর্ণ পয়েন্ট উন্মুক্ত হবে।"
            : "Read the textbook pages sequentially. Tick off each page upon reading to instantly unlock its key takeaways and summaries."}
        </p>

        {/* Page List */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          {defaultPagesBreakdown.map((pageItem) => {
            const pageState = pagesProgress.find((p) => p.page === pageItem.page);
            const isCompleted = !!pageState?.completed;

            return (
              <div
                key={pageItem.page}
                style={{
                  border: isCompleted ? "1.5px solid var(--color-success)" : "1px solid var(--color-border)",
                  borderRadius: "var(--radius-lg)",
                  padding: "var(--space-4)",
                  backgroundColor: isCompleted ? "rgba(16, 185, 129, 0.03)" : "var(--color-surface)",
                  transition: "all 0.2s ease",
                }}
              >
                {/* Page Reading Header & Action */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-3)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                    <button
                      onClick={() => handleTogglePage(pageItem.page)}
                      className="touch-target"
                      style={{
                        padding: 0,
                        color: isCompleted ? "var(--color-success)" : "var(--color-text-muted)",
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                      }}
                      aria-label="Toggle Page Reading"
                    >
                      {isCompleted ? <CheckCircle2 size={26} /> : <Circle size={26} />}
                    </button>

                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                        <span
                          className="badge"
                          style={{
                            backgroundColor: "var(--color-primary-surface)",
                            color: "var(--color-primary)",
                            fontSize: "var(--text-xs)",
                            fontWeight: 700,
                          }}
                        >
                          {lang === "bn" ? `পৃষ্ঠা ${toBengaliDigits(pageItem.page)}` : `Page ${pageItem.page}`}
                        </span>
                        <h3 style={{ fontSize: "var(--text-base)", fontWeight: 700, margin: 0 }}>
                          {pageItem.title}
                        </h3>
                      </div>
                    </div>
                  </div>

                  {/* Split time badge */}
                  <div>
                    {isCompleted ? (
                      <span
                        className="badge"
                        style={{
                          backgroundColor: "rgba(16, 185, 129, 0.12)",
                          color: "var(--color-success)",
                          fontSize: "var(--text-xs)",
                          fontWeight: 700,
                          padding: "4px 10px",
                        }}
                      >
                        ✓ {lang === "bn" ? "সময়:" : "Time:"}{" "}
                        {formatTimer(pageState?.timeTakenSeconds || secondsElapsed)}
                      </span>
                    ) : (
                      <button
                        onClick={() => handleTogglePage(pageItem.page)}
                        className="btn-secondary touch-target"
                        style={{ padding: "4px 12px", fontSize: "var(--text-xs)", fontWeight: 600 }}
                      >
                        {lang === "bn" ? `পৃষ্ঠা ${toBengaliDigits(pageItem.page)} পড়া শেষ` : `Mark Read`}
                      </button>
                    )}
                  </div>
                </div>

                {/* Immediate Page Summary (Revealed upon completing page reading) */}
                {isCompleted && (
                  <div
                    style={{
                      marginTop: "var(--space-4)",
                      paddingTop: "var(--space-4)",
                      borderTop: "1px dashed var(--color-border)",
                      animation: "fadeIn 0.3s ease-in-out",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: "var(--space-2)" }}>
                      <FileText size={15} style={{ color: "var(--color-primary)" }} />
                      <span style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-primary)" }}>
                        {lang === "bn"
                          ? `পৃষ্ঠা ${toBengaliDigits(pageItem.page)} এর মূল সারসংক্ষেপ ও টেকঅ্যাওয়ে:`
                          : `Page ${pageItem.page} Key Takeaways & Summary:`}
                      </span>
                    </div>

                    <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text)", fontWeight: 500, lineHeight: 1.6, margin: "0 0 var(--space-2) 0" }}>
                      {pageItem.summary_bn}
                    </p>

                    <ul style={{ margin: 0, paddingLeft: "var(--space-5)", fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", lineHeight: 1.7 }}>
                      {pageItem.key_points.map((pt, idx) => (
                        <li key={idx}>{pt}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* SECTION 2: Homework (বাড়ির কাজ / HW) Placed Directly Below Page Summaries */}
      <div className="card" style={{ padding: "var(--space-6)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)", flexWrap: "wrap", gap: "var(--space-2)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <ListTodo size={20} style={{ color: "var(--color-warning)" }} />
            <div>
              <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
                {lang === "bn"
                  ? `পৃষ্ঠা ${toBengaliDigits(startPage)}–${toBengaliDigits(endPage)} এর উপর বাড়ির কাজ (Homework / HW)`
                  : `Homework Tasks on Pages ${startPage}–${endPage}`}
              </h2>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                {lang === "bn" ? "পড়ার পর খাতায় নিজে সমাধান করে টিক দিন" : "Solve in exercise book and check off"}
              </span>
            </div>
          </div>

          <span
            className="badge"
            style={{
              backgroundColor: "rgba(245, 158, 11, 0.12)",
              color: "var(--color-warning)",
              fontSize: "var(--text-xs)",
              fontWeight: 700,
            }}
          >
            {lang === "bn"
              ? `HW সম্পন্ন: ${toBengaliDigits(completedHwCount)} / ${toBengaliDigits(homeworkList.length)}`
              : `Done: ${completedHwCount} / ${homeworkList.length}`}
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          {homeworkList.map((hw, idx) => (
            <div
              key={hw.id}
              onClick={() => handleToggleHomework(hw.id)}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "var(--space-3)",
                padding: "var(--space-3) var(--space-4)",
                borderRadius: "var(--radius-md)",
                backgroundColor: hw.completed ? "rgba(16, 185, 129, 0.05)" : "var(--color-surface)",
                border: hw.completed ? "1px solid var(--color-success)" : "1px solid var(--color-border)",
                cursor: "pointer",
                userSelect: "none",
              }}
            >
              <div style={{ paddingTop: 2, color: hw.completed ? "var(--color-success)" : "var(--color-text-muted)" }}>
                {hw.completed ? <CheckSquare size={20} /> : <Circle size={20} />}
              </div>
              <div style={{ flex: 1 }}>
                <span
                  style={{
                    fontSize: "var(--text-sm)",
                    fontWeight: 600,
                    textDecoration: hw.completed ? "line-through" : "none",
                    color: hw.completed ? "var(--color-text-muted)" : "var(--color-text)",
                  }}
                >
                  <strong style={{ color: "var(--color-primary)" }}>
                    {lang === "bn" ? `বাড়ির কাজ ${toBengaliDigits(idx + 1)}: ` : `HW ${idx + 1}: `}
                  </strong>
                  {hw.title_bn}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* SECTION 2.5: High-Yield Notes & Strategy */}
      <div className="card" style={{ padding: "var(--space-6)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-4)" }}>
          <Sparkles size={20} style={{ color: "var(--color-primary)" }} />
          <div>
            <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
              {isSchoolExamOnly
                ? (lang === "bn" ? "অধ্যায়ের গুরুত্বপূর্ণ নোট ও বিদ্যালয় মূল্যায়ন প্রস্তুতি" : "Chapter Key Notes & School Assessment Strategy")
                : (lang === "bn" ? "অধ্যায়ের গুরুত্বপূর্ণ নোট ও বোর্ড পরীক্ষার প্রস্তুতি" : "Chapter Key Notes & Board Exam Strategy")}
            </h2>
            <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              {isSchoolExamOnly
                ? (lang === "bn" ? "শ্রেণি ৬ ও ৭ এর বিদ্যালয়ভিত্তিক বার্ষিক ও ধারাবাহিক মূল্যায়ন প্রস্তুতি" : "School continuous and annual exam preparation for class 6 & 7")
                : (lang === "bn" ? "পরীক্ষার আগে দ্রুত রিভিশনের জন্য মূল তত্ত্ব, সূত্র ও টিপস" : "Core takeaways, key formulas, and high-yield board exam tips")}
            </span>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "var(--space-4)" }}>
          <div style={{ padding: "var(--space-4)", borderRadius: "var(--radius-md)", backgroundColor: "rgba(37, 99, 235, 0.04)", border: "1px solid rgba(37, 99, 235, 0.15)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: "var(--space-2)", color: "var(--color-primary)", fontWeight: 700, fontSize: "var(--text-sm)" }}>
              <BookOpen size={16} />
              <span>{lang === "bn" ? "মূল তত্ত্ব ও ফর্মুলা সামারি" : "Core Concepts & Formula Summary"}</span>
            </div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: "var(--text-xs)", lineHeight: 1.7, color: "var(--color-text-secondary)" }}>
              <li><strong>পাঠ্যবইয়ের পরিধি:</strong> {enrichedTask.chapter_title} (পৃষ্ঠা {toBengaliDigits(startPage)}–{toBengaliDigits(endPage)})</li>
              {curriculumData.notes?.core_concepts?.slice(0, 3).map((concept, idx) => (
                <li key={idx}><strong>মূল পয়েন্ট {toBengaliDigits(idx + 1)}:</strong> {concept}</li>
              ))}
              {curriculumData.notes?.key_formulas_or_reactions?.slice(0, 2).map((formula, idx) => (
                <li key={`f-${idx}`} style={{ color: "var(--color-primary)", fontWeight: 600 }}>{formula}</li>
              ))}
              <li><strong>স্ব-মূল্যায়ন:</strong> উপরের {toBengaliDigits(homeworkList.length)}টি বাড়ির কাজ খাতায় সমাধান করে টিক দাও।</li>
            </ul>
          </div>

          <div style={{ padding: "var(--space-4)", borderRadius: "var(--radius-md)", backgroundColor: "rgba(16, 185, 129, 0.04)", border: "1px solid rgba(16, 185, 129, 0.15)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: "var(--space-2)", color: "var(--color-success)", fontWeight: 700, fontSize: "var(--text-sm)" }}>
              <Award size={16} />
              <span>
                {isSchoolExamOnly
                  ? (lang === "bn" ? "বিদ্যালয় ধারাবাহিক ও সামষ্টিক মূল্যায়ন টিপস" : "School Assessment Scoring Tips")
                  : (lang === "bn" ? "বোর্ড পরীক্ষার সৃজনশীল (CQ) টিপস" : "Board Exam CQ Scoring Tips")}
              </span>
            </div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: "var(--text-xs)", lineHeight: 1.7, color: "var(--color-text-secondary)" }}>
              {(curriculumData.notes?.exam_strategy_tips || curriculumData.notes?.board_exam_tips || []).map((tip, idx) => (
                <li key={idx}>{tip}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* SECTION 3: Post-Study Mastery Check Quiz (Dynamic & AI Handled) */}
      <div className="card" style={{ padding: "var(--space-6)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)", flexWrap: "wrap", gap: "var(--space-3)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <HelpCircle size={20} style={{ color: "var(--color-primary)" }} />
            <div>
              <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
                {lang === "bn" ? "শিখন মূল্যায়ন কুইজ (Mastery Check)" : "Post-Study Mastery Check Quiz"}
              </h2>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                {lang === "bn"
                  ? `পৃষ্ঠা ${toBengaliDigits(startPage)}–${toBengaliDigits(endPage)} এর ধারণার ওপর ${toBengaliDigits(quizQuestions.length)}টি দ্রুত বহুনির্বাচনি প্রশ্ন`
                  : `${quizQuestions.length} quick MCQs on pages ${startPage}–${endPage}`}
              </span>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap" }}>
            {/* AI Regeneration Button */}
            <button
              onClick={handleGenerateAiQuiz}
              disabled={isAiGeneratingQuiz}
              className="btn-secondary touch-target"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                fontSize: "var(--text-xs)",
                padding: "6px 12px",
                borderRadius: "var(--radius-full)",
                border: "1px solid var(--color-primary)",
                color: "var(--color-primary)",
                backgroundColor: "rgba(37, 99, 235, 0.05)",
              }}
              title={lang === "bn" ? "এআই দিয়ে এই অধ্যায়ের জন্য নতুন ১৫টি প্রশ্ন তৈরি করুন" : "Generate 15 fresh MCQs using AI for this chapter"}
            >
              {isAiGeneratingQuiz ? (
                <RefreshCw size={13} className="spin-slow" />
              ) : (
                <Bot size={14} />
              )}
              <span>
                {isAiGeneratingQuiz
                  ? (lang === "bn" ? "এআই প্রশ্ন তৈরি করছে..." : "Generating AI Quiz...")
                  : (lang === "bn" ? "এআই কুইজ রিফ্রেশ" : "AI Quiz Refresh")}
              </span>
            </button>

            {!quizStarted ? (
              <button
                onClick={() => setQuizStarted(true)}
                className="btn-primary touch-target"
                style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-xs)", padding: "8px 16px" }}
              >
                <Play size={14} />
                <span>{lang === "bn" ? "কুইজ শুরু করুন" : "Start Mastery Quiz"}</span>
              </button>
            ) : (
              <span style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-primary)" }}>
                {lang === "bn" ? `${toBengaliDigits(quizQuestions.length)}টি প্রশ্ন • মান ১ করে` : `${quizQuestions.length} Questions • 1 mark each`}
              </span>
            )}
          </div>
        </div>

        {quizStarted && (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
            {quizQuestions.map((q, qIndex) => {
              const selectedOpt = selectedAnswers[q.id];

              return (
                <div
                  key={q.id}
                  style={{
                    backgroundColor: "var(--color-bg)",
                    border: "1px solid var(--color-border)",
                    borderRadius: "var(--radius-lg)",
                    padding: "var(--space-4)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}>
                    <span
                      style={{
                        backgroundColor: "var(--color-primary-surface)",
                        color: "var(--color-primary)",
                        fontWeight: 800,
                        fontSize: "var(--text-xs)",
                        padding: "2px 8px",
                        borderRadius: "var(--radius-full)",
                      }}
                    >
                      {lang === "bn" ? `প্রশ্ন ${toBengaliDigits(qIndex + 1)}` : `Q${qIndex + 1}`}
                    </span>
                    <h3 style={{ fontSize: "var(--text-base)", fontWeight: 700, margin: 0 }}>
                      {lang === "bn" ? q.question_bn : (q.question_en || q.question_bn)}
                    </h3>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                    {(lang === "bn" ? q.options_bn : (q.options_en || q.options_bn)).map((optText, optIdx) => {
                      const isSelected = selectedOpt === optIdx;
                      const isCorrect = q.correctIndex === optIdx;

                      let borderColor = "var(--color-border)";
                      let bgColor = "var(--color-surface)";

                      if (quizSubmitted) {
                        if (isCorrect) {
                          borderColor = "var(--color-success)";
                          bgColor = "rgba(16, 185, 129, 0.1)";
                        } else if (isSelected && !isCorrect) {
                          borderColor = "var(--color-error)";
                          bgColor = "rgba(239, 68, 68, 0.1)";
                        }
                      } else if (isSelected) {
                        borderColor = "var(--color-primary)";
                        bgColor = "var(--color-primary-surface)";
                      }

                      return (
                        <button
                          key={optIdx}
                          type="button"
                          onClick={() => handleSelectAnswer(q.id, optIdx)}
                          className="touch-target"
                          style={{
                            textAlign: "left",
                            padding: "var(--space-3) var(--space-4)",
                            borderRadius: "var(--radius-md)",
                            border: `1.5px solid ${borderColor}`,
                            backgroundColor: bgColor,
                            cursor: quizSubmitted ? "default" : "pointer",
                            fontSize: "var(--text-sm)",
                            fontWeight: isSelected ? 700 : 500,
                            color: "var(--color-text)",
                            display: "flex",
                            alignItems: "center",
                            gap: "var(--space-3)",
                          }}
                        >
                          <span
                            style={{
                              width: 22,
                              height: 22,
                              borderRadius: "50%",
                              border: `1.5px solid ${isSelected ? "var(--color-primary)" : "var(--color-border)"}`,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontSize: "var(--text-xs)",
                              fontWeight: 700,
                              backgroundColor: isSelected ? "var(--color-primary)" : "transparent",
                              color: isSelected ? "#ffffff" : "var(--color-text-muted)",
                            }}
                          >
                            {lang === "bn" ? toBengaliDigits(optIdx + 1) : optIdx + 1}
                          </span>
                          <span>{optText}</span>
                        </button>
                      );
                    })}
                  </div>

                  {/* Explanation after submit */}
                  {quizSubmitted && (
                    <div
                      style={{
                        marginTop: "var(--space-3)",
                        padding: "var(--space-3)",
                        borderRadius: "var(--radius-md)",
                        backgroundColor: "var(--color-surface-hover)",
                        fontSize: "var(--text-xs)",
                        color: "var(--color-text-secondary)",
                      }}
                    >
                      <strong>{lang === "bn" ? "ব্যাখ্যা: " : "Explanation: "}</strong>
                      {lang === "bn" ? q.explanation_bn : (q.explanation_en || q.explanation_bn)}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Quiz Submit Button & Feedback */}
            {!quizSubmitted ? (
              <button
                onClick={handleSubmitQuiz}
                disabled={Object.keys(selectedAnswers).length < quizQuestions.length}
                className="btn-primary touch-target"
                style={{
                  padding: "12px 24px",
                  fontSize: "var(--text-sm)",
                  fontWeight: 700,
                  alignSelf: "flex-start",
                  opacity: Object.keys(selectedAnswers).length < quizQuestions.length ? 0.6 : 1,
                }}
              >
                {lang === "bn" ? "ফলাফল ও ব্যাখ্যা দেখুন" : "Submit Answers & View Score"}
              </button>
            ) : (
              <div
                style={{
                  backgroundColor: "rgba(16, 185, 129, 0.08)",
                  border: "1.5px solid var(--color-success)",
                  borderRadius: "var(--radius-xl)",
                  padding: "var(--space-5)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "var(--space-3)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                  <Award size={32} style={{ color: "var(--color-success)" }} />
                  <div>
                    <h3 style={{ fontSize: "var(--text-lg)", fontWeight: 800, margin: 0 }}>
                      {lang === "bn" ? "শিখন মূল্যায়ন সম্পন্ন!" : "Mastery Assessment Completed!"}
                    </h3>
                    <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
                      {lang === "bn" ? "তোমার অর্জিত স্কোর: " : "Your Score: "}
                      <strong style={{ color: "var(--color-success)", fontSize: "var(--text-base)" }}>
                        {lang === "bn"
                          ? `${toBengaliDigits(quizScore)} / ${toBengaliDigits(quizQuestions.length)}`
                          : `${quizScore} / ${quizQuestions.length}`}
                      </strong>
                    </div>
                  </div>
                </div>

                <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text)", margin: 0, lineHeight: 1.6 }}>
                  {quizScore === quizQuestions.length
                    ? (lang === "bn" ? "অসাধারণ দক্ষতা! সবগুলো প্রশ্নের সঠিক উত্তর দিয়েছো।" : "Outstanding! You got every question right.")
                    : quizScore >= Math.round(quizQuestions.length * 0.7)
                    ? (lang === "bn" ? "চমৎকার প্রচেষ্টা! নিয়মিত চর্চায় তোমার দক্ষতা আরও বৃদ্ধি পাবে।" : "Great effort! Continuous practice will strengthen your mastery.")
                    : (lang === "bn" ? "ভালো চেষ্টা করেছো! পাঠ্যবইয়ের অধ্যায়টি পুনরায় পড়ে আবার চেষ্টা করো।" : "Good try! Review the chapter in your textbook and try again.")}
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Final Action Bar */}
      <div
        className="card"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "var(--space-4)",
          padding: "var(--space-5)",
          backgroundColor: "var(--color-surface)",
        }}
      >
        <div>
          <div style={{ fontSize: "var(--text-sm)", fontWeight: 700 }}>
            {lang === "bn" ? "আজকের অধ্যয়ন অগ্রগতি" : "Today's Study Progress"}
          </div>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
            {lang === "bn"
              ? `মোট অধ্যয়নকৃত সময়: ${formatTimer(secondsElapsed)} • পৃষ্ঠা ${toBengaliDigits(startPage)}–${toBengaliDigits(endPage)} সম্পন্ন`
              : `Total Time Spent: ${formatTimer(secondsElapsed)} • Pages ${startPage}–${endPage} Completed`}
          </div>
        </div>

        <button
          onClick={handleFinishSession}
          className="btn-primary touch-target"
          style={{
            padding: "12px 28px",
            fontSize: "var(--text-sm)",
            fontWeight: 800,
            borderRadius: "var(--radius-lg)",
            backgroundColor: "var(--color-success)",
            borderColor: "var(--color-success)",
          }}
        >
          {lang === "bn" ? "আজকের সেশন সম্পন্ন করুন (Finish)" : "Complete Today's Session"}
        </button>
      </div>
    </div>
  );
};
