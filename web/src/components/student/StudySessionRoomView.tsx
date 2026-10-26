"use client";

import React, { useState, useEffect, useRef } from "react";
import { StudyTask } from "@/lib/types";
import { Language, translations, toBengaliDigits } from "@/lib/i18n";
import { MathRenderer } from "@/components/MathRenderer";
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
} from "lucide-react";

interface StudySessionRoomViewProps {
  task: StudyTask;
  lang: Language;
  onBack: () => void;
  onComplete: (taskId: string, timeSpentSeconds: number, note: string, quizScore: number) => void;
}

interface TargetItem {
  id: string;
  title_bn: string;
  title_en: string;
  completed: boolean;
  timeTakenSeconds?: number;
}

interface MiniQuizQuestion {
  id: string;
  question_bn: string;
  question_en: string;
  options_bn: string[];
  options_en: string[];
  correctIndex: number;
  explanation_bn: string;
  explanation_en: string;
}

export const StudySessionRoomView: React.FC<StudySessionRoomViewProps> = ({
  task,
  lang,
  onBack,
  onComplete,
}) => {
  const t = translations[lang];

  // Stopwatch state
  const [secondsElapsed, setSecondsElapsed] = useState(0);
  const [isRunning, setIsRunning] = useState(true);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Targets state
  const [targets, setTargets] = useState<TargetItem[]>([
    {
      id: "tgt_1",
      title_bn: "পাঠ্যবইয়ের মূল ধারণা ও সূত্রগুলো মনোযোগ দিয়ে পড়া",
      title_en: "Read and understand the core concept and formulas from textbook",
      completed: false,
    },
    {
      id: "tgt_2",
      title_bn: "উদাহরণ সমস্যাগুলো নিজে নিজে খাতায় সমাধান করা",
      title_en: "Work through and solve example problems independently in notebook",
      completed: false,
    },
    {
      id: "tgt_3",
      title_bn: "অনুশীলনীর গাণিতিক সমস্যার সমাধান ও জটিল অংশ চিহ্নিত করা",
      title_en: "Solve exercise problems and identify tricky steps",
      completed: false,
    },
  ]);

  // Notes state
  const [studentNote, setStudentNote] = useState("");
  const [noteSaved, setNoteSaved] = useState(false);

  // Quiz state
  const [quizStarted, setQuizStarted] = useState(false);
  const [quizAnswers, setQuizAnswers] = useState<Record<number, number>>({});
  const [quizSubmitted, setQuizSubmitted] = useState(false);
  const [quizScore, setQuizScore] = useState(0);

  // Sample assessment quiz questions bound to the topic
  const sampleQuiz: MiniQuizQuestion[] = [
    {
      id: "q1",
      question_bn: "সরল সমীকরণ $2x + 6 = 16$ হলে, $x$-এর মান কত?",
      question_en: "In the simple linear equation $2x + 6 = 16$, what is the value of $x$?",
      options_bn: ["৩ (3)", "৫ (5)", "৮ (8)", "১০ (10)"],
      options_en: ["3", "5", "8", "10"],
      correctIndex: 1,
      explanation_bn: "ব্যাখ্যা: $2x = 16 - 6 \\implies 2x = 10 \\implies x = 5$।",
      explanation_en: "Explanation: $2x = 16 - 6 \\implies 2x = 10 \\implies x = 5$.",
    },
    {
      id: "q2",
      question_bn: "সমীকরণের উভয় পক্ষে একই অশূন্য সংখ্যা দ্বারা গুণ বা ভাগ করলে কী ঘটে?",
      question_en: "What happens if both sides of an equation are multiplied or divided by the same non-zero number?",
      options_bn: [
        "সমীকরণের সমতা অপরিবর্তিত থাকে",
        "সমীকরণের মান দ্বিগুণ হয়ে যায়",
        "সমীকরণটি অর্থহীন হয়ে যায়",
        "চলকের মান ঋণাত্মক হয়ে যায়",
      ],
      options_en: [
        "The equality remains unchanged",
        "The equation value doubles",
        "The equation becomes undefined",
        "The variable becomes negative",
      ],
      correctIndex: 0,
      explanation_bn: "স্বতঃসিদ্ধ অনুযায়ী, উভয় পক্ষে একই সংখ্যা গুণ/ভাগ করলে সমতা বজায় থাকে।",
      explanation_en: "By axiom of equality, multiplying/dividing non-zero equals preserves equality.",
    },
    {
      id: "q3",
      question_bn: "যদি কোনো সংখ্যার দ্বিগুণের সাথে ৫ যোগ করলে ১৫ হয়, তবে সংখ্যাটি কত?",
      question_en: "If 5 is added to twice a number and the result is 15, what is the number?",
      options_bn: ["৪ (4)", "৫ (5)", "৬ (6)", "১০ (10)"],
      options_en: ["4", "5", "6", "10"],
      correctIndex: 1,
      explanation_bn: "ধরি সংখ্যাটি $x$। সুতরাং $2x + 5 = 15 \\implies 2x = 10 \\implies x = 5$।",
      explanation_en: "Let number be $x$. So $2x + 5 = 15 \\implies 2x = 10 \\implies x = 5$.",
    },
  ];

  // Stopwatch interval
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

  const formatTimer = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    const pad = (num: number) => String(num).padStart(2, "0");
    const formatted = `${pad(mins)}:${pad(secs)}`;
    return lang === "bn" ? toBengaliDigits(formatted) : formatted;
  };

  const handleToggleTarget = (targetId: string) => {
    setTargets((prev) =>
      prev.map((t) => {
        if (t.id === targetId) {
          const nextCompleted = !t.completed;
          return {
            ...t,
            completed: nextCompleted,
            timeTakenSeconds: nextCompleted ? secondsElapsed : undefined,
          };
        }
        return t;
      })
    );
  };

  const handleSaveNote = () => {
    setNoteSaved(true);
    setTimeout(() => setNoteSaved(false), 3000);
  };

  const handleAnswerSelect = (qIndex: number, optionIndex: number) => {
    if (quizSubmitted) return;
    setQuizAnswers((prev) => ({ ...prev, [qIndex]: optionIndex }));
  };

  const handleQuizSubmit = () => {
    let score = 0;
    sampleQuiz.forEach((q, idx) => {
      if (quizAnswers[idx] === q.correctIndex) {
        score += 1;
      }
    });
    setQuizScore(score);
    setQuizSubmitted(true);
  };

  const handleFinishSession = () => {
    setIsRunning(false);
    onComplete(task.id, secondsElapsed, studentNote, quizScore);
  };

  const allTargetsCompleted = targets.every((t) => t.completed);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-6)",
        maxWidth: 960,
        margin: "0 auto",
        width: "100%",
        paddingBottom: "var(--space-12)",
      }}
    >
      {/* Top Bar with Greetings */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "var(--space-3)",
        }}
      >
        <button
          onClick={onBack}
          className="btn-secondary touch-target"
          style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--text-sm)" }}
        >
          <ArrowLeft size={16} />
          <span>{lang === "bn" ? "আজকের রুটিনে ফিরে যান" : "Back to Today"}</span>
        </button>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
            backgroundColor: "var(--color-primary-surface)",
            color: "var(--color-primary)",
            padding: "4px 14px",
            borderRadius: "var(--radius-full)",
            fontSize: "var(--text-xs)",
            fontWeight: 700,
          }}
        >
          <Flame size={14} />
          <span>
            {lang === "bn"
              ? "৭ দিনের নিরবচ্ছিন্ন অধ্যয়ন • কোনো সাপ্তাহিক অফ-ডে নেই"
              : "7-Day Continuous Habit • No Weekly Off-Day"}
          </span>
        </div>
      </div>

      {/* Islamic & BD Warm Welcome Banner */}
      <div
        className="card"
        style={{
          background: "linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(16, 185, 129, 0.08) 100%)",
          border: "1px solid var(--color-primary-surface)",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-2)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <Sparkles size={18} style={{ color: "var(--color-primary)" }} />
          <span style={{ fontSize: "var(--text-sm)", fontWeight: 700, color: "var(--color-primary)" }}>
            {lang === "bn" ? "আসসালামু আলাইকুম ওয়া রাহমাতুল্লাহ" : "Assalamu Alaikum wa Rahmatullah"}
          </span>
        </div>
        <div style={{ fontSize: "var(--text-lg)", fontWeight: 800 }}>
          {lang === "bn" ? "বিসমিল্লাহির রাহমানির রাহিম" : "Bismillahir Rahmanir Rahim"}
        </div>
        <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", margin: 0 }}>
          {lang === "bn"
            ? "পরম করুণাময় আল্লাহর নামে শুরু করো। স্থির মন ও একাগ্রতা নিয়ে আজকের প্রতিটি লক্ষ্য অর্জন করো।"
            : "Begin in the name of Allah. Study with focus, clarity, and continuous dedication."}
        </p>
      </div>

      {/* Task Header & Citations */}
      <div className="card" style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap" }}>
          <span className="badge" style={{ backgroundColor: "var(--color-primary)", color: "#ffffff" }}>
            {task.subject}
          </span>
          <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
            {lang === "bn" ? "আনুমানিক সময়:" : "Est. Time:"}{" "}
            {lang === "bn" ? toBengaliDigits(task.estimated_minutes) : task.estimated_minutes}{" "}
            {t.growthMindset.minutesAbbr}
          </span>
        </div>

        <h1 style={{ fontSize: "var(--text-2xl)", fontWeight: 800, margin: 0 }}>
          {task.title}
        </h1>

        {/* Rule 8: Printed Textbook Page Number */}
        {task.printed_page_start && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-2)",
              fontSize: "var(--text-sm)",
              color: "var(--color-primary)",
              backgroundColor: "var(--color-primary-surface)",
              padding: "var(--space-2) var(--space-4)",
              borderRadius: "var(--radius-md)",
              fontWeight: 600,
            }}
          >
            <BookOpen size={16} />
            <span>
              {task.book_title} — {t.student.printedPage}:{" "}
              {lang === "bn"
                ? `${toBengaliDigits(task.printed_page_start)} - ${toBengaliDigits(task.printed_page_end || task.printed_page_start)}`
                : `${task.printed_page_start} - ${task.printed_page_end || task.printed_page_start}`}
            </span>
          </div>
        )}

        {task.guidelines && (
          <div
            style={{
              fontSize: "var(--text-sm)",
              color: "var(--color-text-secondary)",
              lineHeight: 1.6,
              paddingTop: "var(--space-2)",
            }}
          >
            <MathRenderer content={task.guidelines} />
          </div>
        )}
      </div>

      {/* Digital Stopwatch Section */}
      <div
        className="card"
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "var(--space-8)",
          textAlign: "center",
          backgroundColor: "var(--color-surface)",
          boxShadow: "var(--shadow-md)",
          border: "2px solid var(--color-primary-surface)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", color: "var(--color-text-muted)", fontSize: "var(--text-xs)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>
          <Clock size={16} />
          <span>{lang === "bn" ? "অধ্যয়ন স্টপওয়াচ (পড়ার সময়)" : "Live Study Stopwatch"}</span>
        </div>

        {/* Live Timer Display */}
        <div
          style={{
            fontSize: "clamp(3rem, 7vw, 4.5rem)",
            fontWeight: 800,
            fontFamily: "monospace",
            color: isRunning ? "var(--color-primary)" : "var(--color-text-muted)",
            letterSpacing: "0.04em",
            margin: "var(--space-3) 0",
            textShadow: isRunning ? "0 4px 18px rgba(37, 99, 235, 0.2)" : "none",
          }}
        >
          {formatTimer(secondsElapsed)}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
          <button
            onClick={() => setIsRunning(!isRunning)}
            className={isRunning ? "btn-secondary touch-target" : "btn-primary touch-target"}
            style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", padding: "var(--space-2) var(--space-6)" }}
          >
            {isRunning ? (
              <>
                <Pause size={18} />
                <span>{lang === "bn" ? "বিরতি দিন (Pause)" : "Pause"}</span>
              </>
            ) : (
              <>
                <Play size={18} />
                <span>{lang === "bn" ? "চালু রাখুন (Resume)" : "Resume"}</span>
              </>
            )}
          </button>

          <button
            onClick={() => {
              setIsRunning(false);
              setSecondsElapsed(0);
            }}
            className="btn-outline touch-target"
            style={{ width: 44, height: 44, padding: 0 }}
            title={lang === "bn" ? "পুনরায় শুরু করুন" : "Reset Timer"}
            aria-label={lang === "bn" ? "পুনরায় শুরু করুন" : "Reset Timer"}
          >
            <RotateCcw size={16} />
          </button>
        </div>

        <div style={{ marginTop: "var(--space-3)", fontSize: "var(--text-xs)", color: isRunning ? "var(--color-success)" : "var(--color-text-muted)", display: "flex", alignItems: "center", gap: 6, fontWeight: 600 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", backgroundColor: isRunning ? "var(--color-success)" : "var(--color-text-muted)", display: "inline-block" }} />
          <span>{isRunning ? (lang === "bn" ? "মনোযোগ দিয়ে পড়া চলমান..." : "Active study in progress...") : (lang === "bn" ? "সময় বিরতিতে রয়েছে" : "Timer paused")}</span>
        </div>
      </div>

      {/* Micro-Targets with Split Duration */}
      <div className="card" style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <div>
          <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
            {lang === "bn" ? "আজকের পড়ার সুনির্দিষ্ট লক্ষ্যসমূহ (Targets)" : "Session Specific Targets"}
          </h2>
          <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: 4 }}>
            {lang === "bn"
              ? "একটি লক্ষ্য সম্পন্ন হলে সেটিতে ক্লিক করো। কত সময় লাগল তা সাথে সাথে রেকর্ড হয়ে যাবে।"
              : "Click each target as you complete it to record your exact split time."}
          </p>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          {targets.map((tgt, index) => {
            const isDone = tgt.completed;
            return (
              <div
                key={tgt.id}
                onClick={() => handleToggleTarget(tgt.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "var(--space-4)",
                  borderRadius: "var(--radius-lg)",
                  border: isDone ? "1px solid var(--color-success)" : "1px solid var(--color-border)",
                  backgroundColor: isDone ? "var(--color-surface-hover)" : "var(--color-surface)",
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                  <button
                    type="button"
                    className="touch-target"
                    style={{ padding: 0, color: isDone ? "var(--color-success)" : "var(--color-text-muted)" }}
                    aria-label={tgt.title_bn}
                  >
                    {isDone ? <CheckCircle2 size={24} /> : <Circle size={24} />}
                  </button>
                  <div>
                    <span
                      style={{
                        fontSize: "var(--text-sm)",
                        fontWeight: 600,
                        textDecoration: isDone ? "line-through" : "none",
                        color: isDone ? "var(--color-text-secondary)" : "var(--color-text)",
                      }}
                    >
                      {lang === "bn" ? tgt.title_bn : tgt.title_en}
                    </span>
                  </div>
                </div>

                {/* Split Time Display */}
                {isDone && tgt.timeTakenSeconds !== undefined && (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                      fontSize: "var(--text-xs)",
                      fontWeight: 700,
                      color: "var(--color-success)",
                      backgroundColor: "rgba(16, 185, 129, 0.12)",
                      padding: "4px 10px",
                      borderRadius: "var(--radius-full)",
                    }}
                  >
                    <Clock size={12} />
                    <span>
                      {lang === "bn" ? "সময় লেগেছে:" : "Time taken:"}{" "}
                      {formatTimer(tgt.timeTakenSeconds)}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {allTargetsCompleted && (
          <div
            style={{
              padding: "var(--space-3)",
              backgroundColor: "rgba(16, 185, 129, 0.1)",
              borderRadius: "var(--radius-md)",
              color: "var(--color-success)",
              fontSize: "var(--text-xs)",
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: "var(--space-2)",
            }}
          >
            <Sparkles size={16} />
            <span>
              {lang === "bn"
                ? "মাশাআল্লাহ! আজকের সমস্ত পড়ার লক্ষ্য অর্জিত হয়েছে! এবার সারসংক্ষেপ নোট লিখে কুইজে অংশগ্রহণ করো।"
                : "MashaAllah! All study targets completed! Now summarize your notes and take the mastery quiz."}
            </span>
          </div>
        )}
      </div>

      {/* Summary & Note Pad */}
      <div className="card" style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <FileText size={20} style={{ color: "var(--color-primary)" }} />
          <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
            {lang === "bn" ? "সারসংক্ষেপ ও আমার নোট (Key Points & Notes)" : "Summary & Personal Notes"}
          </h2>
        </div>

        {/* Core Formula & Key Points Box */}
        <div
          style={{
            padding: "var(--space-4)",
            backgroundColor: "var(--color-bg)",
            borderRadius: "var(--radius-md)",
            border: "1px dashed var(--color-border)",
            fontSize: "var(--text-xs)",
            color: "var(--color-text-secondary)",
            lineHeight: 1.6,
          }}
        >
          <strong>{lang === "bn" ? "অধ্যায়ের মূল পয়েন্ট ও সূত্র:" : "Key Takeaways:"}</strong>
          <ul style={{ margin: "var(--space-2) 0 0 var(--space-4)", padding: 0 }}>
            <li>{lang === "bn" ? "সমীকরণের সংজ্ঞা: চলক, প্রক্রিয়া চিহ্ন ও সমান চিহ্ন সংবলিত গাণিতিক খোলা বাক্য।" : "Equation definition: Mathematical open sentence containing variables, operators and equal sign."}</li>
            <li>{lang === "bn" ? "পক্ষান্তর বিধি: সমান চিহ্নের একপাশ থেকে অন্যপাশে পদ স্থানান্তর করলে চিহ্নের পরিবর্তন ঘটে (+ থাকলে -, × থাকলে ÷)।" : "Transposition rule: Moving a term across equality changes its sign."}</li>
            <li>{lang === "bn" ? "শুদ্ধি পরীক্ষা: প্রাপ্ত মান মূল সমীকরণের উভয় পক্ষে বসিয়ে বামপক্ষ = ডানপক্ষ নিশ্চিত করা।" : "Verification: Substituting the value into LHS and verifying LHS = RHS."}</li>
          </ul>
        </div>

        {/* Student Note Area */}
        <div>
          <label
            htmlFor="student-note-pad"
            style={{
              display: "block",
              fontSize: "var(--text-xs)",
              fontWeight: 600,
              color: "var(--color-text-secondary)",
              marginBottom: "var(--space-1)",
            }}
          >
            {lang === "bn"
              ? "তোমার নিজের ভাষায় গুরুত্বপূর্ণ নোট / সূত্র লিখে রাখো:"
              : "Write down your key formulas or personal takeaways in your own words:"}
          </label>
          <textarea
            id="student-note-pad"
            rows={4}
            value={studentNote}
            onChange={(e) => setStudentNote(e.target.value)}
            placeholder={
              lang === "bn"
                ? "আজকের পড়া থেকে আমি যা শিখলাম... যেমন: পক্ষান্তরের সময় চিহ্নের পরিবর্তন মনে রাখতে হবে..."
                : "What I learned today... e.g. remember to change the sign during transposition..."
            }
            style={{
              width: "100%",
              padding: "var(--space-3)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-bg)",
              color: "var(--color-text)",
              fontSize: "var(--text-sm)",
              fontFamily: "inherit",
              resize: "vertical",
            }}
          />
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button
            onClick={handleSaveNote}
            className="btn-secondary touch-target"
            style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--text-sm)" }}
          >
            {noteSaved ? (
              <>
                <Check size={16} style={{ color: "var(--color-success)" }} />
                <span style={{ color: "var(--color-success)" }}>
                  {lang === "bn" ? "নোট সংরক্ষিত হয়েছে!" : "Note Saved!"}
                </span>
              </>
            ) : (
              <>
                <Save size={16} />
                <span>{lang === "bn" ? "নোট সংরক্ষণ করুন" : "Save Note"}</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Post-Study Assessment Quiz ("How good is he?") */}
      <div
        className="card"
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-4)",
          borderLeft: "4px solid var(--color-primary)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-2)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <Award size={22} style={{ color: "var(--color-primary)" }} />
            <div>
              <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
                {lang === "bn" ? "শিখন মূল্যায়ন কুইজ (Mastery Check)" : "Post-Study Mastery Quiz"}
              </h2>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                {lang === "bn"
                  ? "পড়া কতটা মনে আছে তা তাৎক্ষণিক যাচাই করতে ৩টি প্রশ্নের উত্তর দাও"
                  : "Answer 3 quick questions to determine how well you mastered the chapter"}
              </div>
            </div>
          </div>

          {!quizStarted && (
            <button
              onClick={() => setQuizStarted(true)}
              className="btn-primary touch-target"
              style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}
            >
              <HelpCircle size={18} />
              <span>{lang === "bn" ? "কুইজ শুরু করুন" : "Start Mini Quiz"}</span>
            </button>
          )}
        </div>

        {quizStarted && (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)", marginTop: "var(--space-2)" }}>
            {sampleQuiz.map((q, qIndex) => {
              const selectedOpt = quizAnswers[qIndex];
              return (
                <div
                  key={q.id}
                  style={{
                    padding: "var(--space-4)",
                    borderRadius: "var(--radius-lg)",
                    border: "1px solid var(--color-border)",
                    backgroundColor: "var(--color-bg)",
                  }}
                >
                  <div style={{ fontSize: "var(--text-sm)", fontWeight: 700, marginBottom: "var(--space-3)" }}>
                    <span style={{ color: "var(--color-primary)", marginRight: 6 }}>
                      {lang === "bn" ? `প্রশ্ন ${toBengaliDigits(qIndex + 1)}:` : `Q${qIndex + 1}:`}
                    </span>
                    <MathRenderer content={lang === "bn" ? q.question_bn : q.question_en} />
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "var(--space-2)" }}>
                    {(lang === "bn" ? q.options_bn : q.options_en).map((opt, optIndex) => {
                      const isSelected = selectedOpt === optIndex;
                      const isCorrect = q.correctIndex === optIndex;

                      let borderColor = "var(--color-border)";
                      let bgColor = "var(--color-surface)";
                      let textColor = "var(--color-text)";

                      if (quizSubmitted) {
                        if (isCorrect) {
                          borderColor = "var(--color-success)";
                          bgColor = "rgba(16, 185, 129, 0.12)";
                          textColor = "var(--color-success)";
                        } else if (isSelected && !isCorrect) {
                          borderColor = "var(--color-danger)";
                          bgColor = "rgba(239, 68, 68, 0.12)";
                          textColor = "var(--color-danger)";
                        }
                      } else if (isSelected) {
                        borderColor = "var(--color-primary)";
                        bgColor = "var(--color-primary-surface)";
                        textColor = "var(--color-primary)";
                      }

                      return (
                        <button
                          key={optIndex}
                          type="button"
                          onClick={() => handleAnswerSelect(qIndex, optIndex)}
                          className="touch-target"
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "var(--space-3)",
                            padding: "var(--space-3)",
                            borderRadius: "var(--radius-md)",
                            border: `1px solid ${borderColor}`,
                            backgroundColor: bgColor,
                            color: textColor,
                            fontSize: "var(--text-sm)",
                            fontWeight: isSelected ? 600 : 500,
                            textAlign: "left",
                            cursor: quizSubmitted ? "default" : "pointer",
                            transition: "all 0.15s ease",
                          }}
                        >
                          <span
                            style={{
                              width: 22,
                              height: 22,
                              borderRadius: "50%",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontSize: "var(--text-xs)",
                              fontWeight: 700,
                              backgroundColor: isSelected ? "var(--color-primary)" : "var(--color-border)",
                              color: isSelected ? "#ffffff" : "var(--color-text-secondary)",
                            }}
                          >
                            {lang === "bn" ? ["ক", "খ", "গ", "ঘ"][optIndex] : ["A", "B", "C", "D"][optIndex]}
                          </span>
                          <span>{opt}</span>
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
                        backgroundColor: "var(--color-surface)",
                        borderRadius: "var(--radius-md)",
                        borderLeft: "3px solid var(--color-primary)",
                        fontSize: "var(--text-xs)",
                        color: "var(--color-text-secondary)",
                      }}
                    >
                      <MathRenderer content={lang === "bn" ? q.explanation_bn : q.explanation_en} />
                    </div>
                  )}
                </div>
              );
            })}

            {!quizSubmitted ? (
              <button
                onClick={handleQuizSubmit}
                disabled={Object.keys(quizAnswers).length < sampleQuiz.length}
                className="btn-primary touch-target"
                style={{
                  alignSelf: "flex-end",
                  padding: "var(--space-3) var(--space-6)",
                  fontSize: "var(--text-sm)",
                }}
              >
                {lang === "bn" ? "ফলাফল ও ব্যাখ্যা দেখুন" : "Submit & View Score"}
              </button>
            ) : (
              /* Score Feedback Card */
              <div
                style={{
                  padding: "var(--space-6)",
                  borderRadius: "var(--radius-xl)",
                  textAlign: "center",
                  backgroundColor: "var(--color-surface)",
                  border: "2px solid var(--color-success)",
                  boxShadow: "var(--shadow-md)",
                }}
              >
                <div style={{ fontSize: "var(--text-sm)", fontWeight: 700, color: "var(--color-success)" }}>
                  {lang === "bn" ? "আলহামদুলিল্লাহ! শিখন মূল্যায়ন সম্পন্ন!" : "Alhamdulillah! Assessment Complete!"}
                </div>
                <div style={{ fontSize: "var(--text-3xl)", fontWeight: 800, margin: "var(--space-2) 0" }}>
                  {lang === "bn" ? "অর্জিত স্কোর:" : "Your Score:"}{" "}
                  <span style={{ color: "var(--color-primary)" }}>
                    {lang === "bn" ? toBengaliDigits(quizScore) : quizScore} / {lang === "bn" ? toBengaliDigits(sampleQuiz.length) : sampleQuiz.length}
                  </span>
                </div>
                <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", maxWidth: 500, margin: "0 auto" }}>
                  {quizScore === 3
                    ? lang === "bn"
                      ? "মাশাআল্লাহ! অসাধারণ পারদর্শিতা! তুমি আজকের অধ্যায়ের সমস্ত মৌলিক ধারণা সুন্দরভাবে আয়ত্ত করেছ।"
                      : "MashaAllah! Outstanding proficiency! You have completely mastered the core ideas."
                    : quizScore === 2
                    ? lang === "bn"
                      ? "মাশাআল্লাহ! বেশ ভালো প্রস্তুতি। আরেকটু রিভিশন দিলে ইনশাআল্লাহ শতভাগ আয়ত্তে চলে আসবে।"
                      : "MashaAllah! Very good grasp. A quick review of tricky steps will ensure 100% mastery."
                    : lang === "bn"
                    ? "ইনশাআল্লাহ অনুশীলন চালিয়ে যাও! উদাহরণগুলো আরেকবার খাতায় লিখে চেষ্টা করলে পুরো পরিষ্কার হবে।"
                    : "InshaAllah keep practicing! Re-working through the examples in your notebook will build mastery."}
                </p>

                <button
                  onClick={handleFinishSession}
                  className="btn-primary touch-target"
                  style={{
                    marginTop: "var(--space-4)",
                    padding: "var(--space-3) var(--space-8)",
                    fontSize: "var(--text-base)",
                    fontWeight: 700,
                  }}
                >
                  {lang === "bn" ? "আজকের সেশন সম্পন্ন করুন (Finish)" : "Complete Today's Session"}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
