import React, { useState, useEffect, useRef } from "react";
import {
  RoutineSlot,
  Language,
  translations,
  toBengaliDigits,
  DEFAULT_PAGE_BREAKDOWNS,
  DEFAULT_HOMEWORK,
  saveSessionState,
  loadSessionState,
  PageStudyBreakdown,
  HomeworkTask,
} from "@thinkbuddy/shared";
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
  Award,
  Sparkles,
  Check,
  Camera,
  Layers,
  ShieldCheck,
  CheckSquare,
} from "lucide-react";
import { MathRenderer } from "./MathRenderer";

interface StudySessionRoomViewProps {
  slot: RoutineSlot;
  lang: Language;
  studentName: string;
  studentUid: string;
  onBack: () => void;
  onComplete: (slotId: string) => void;
}

export const StudySessionRoomView: React.FC<StudySessionRoomViewProps> = ({
  slot,
  lang,
  studentName,
  studentUid,
  onBack,
  onComplete,
}) => {
  const t = translations[lang];

  // 1. Persistent Stopwatch across refresh
  const stopwatchKey = `tb_stopwatch_${slot.id}`;
  const [secondsElapsed, setSecondsElapsed] = useState<number>(() => {
    try {
      const saved = localStorage.getItem(stopwatchKey);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.isRunning && parsed.lastTimestamp) {
          const diff = Math.floor((Date.now() - parsed.lastTimestamp) / 1000);
          return Math.max(0, (parsed.secondsElapsed || 0) + diff);
        }
        return parsed.secondsElapsed || 0;
      }
    } catch {}
    return 0;
  });

  const [isRunning, setIsRunning] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem(stopwatchKey);
      if (saved) {
        const parsed = JSON.parse(saved);
        return Boolean(parsed.isRunning);
      }
    } catch {}
    return true; // Start running by default
  });

  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Sync stopwatch to localStorage
  useEffect(() => {
    const payload = {
      secondsElapsed,
      isRunning,
      lastTimestamp: Date.now(),
    };
    try {
      localStorage.setItem(stopwatchKey, JSON.stringify(payload));
    } catch {}
  }, [secondsElapsed, isRunning, stopwatchKey]);

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
    try {
      localStorage.setItem(
        stopwatchKey,
        JSON.stringify({ secondsElapsed: 0, isRunning: false, lastTimestamp: Date.now() })
      );
    } catch {}
  };

  const formatTimer = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    const formatted = `${String(mins).padStart(2, "0")} : ${String(secs).padStart(2, "0")}`;
    return lang === "bn" ? toBengaliDigits(formatted) : formatted;
  };

  // 2. Pages Breakdown & Dynamic Page Progress Ticks
  const pagesKey = slot.subject.includes("গণিত") ? "math_ch5" : "science_ch4";
  const pagesBreakdown: PageStudyBreakdown[] = DEFAULT_PAGE_BREAKDOWNS[pagesKey] || DEFAULT_PAGE_BREAKDOWNS.science_ch4;

  const [pagesProgress, setPagesProgress] = useState<Record<number, boolean>>(() => {
    const saved = loadSessionState(slot.id);
    if (saved?.pagesProgress) return saved.pagesProgress;
    const initial: Record<number, boolean> = {};
    pagesBreakdown.forEach((p) => {
      initial[p.page] = false;
    });
    return initial;
  });

  const handleTogglePage = (pageNum: number) => {
    const nextVal = !pagesProgress[pageNum];
    const updated = { ...pagesProgress, [pageNum]: nextVal };
    setPagesProgress(updated);

    // Persist to session state
    saveSessionState({
      taskId: slot.id,
      secondsElapsed,
      isRunning,
      lastUpdatedTimestamp: Date.now(),
      pagesProgress: updated,
      homeworkProgress,
      noteContent,
    });
  };

  const completedPagesCount = pagesBreakdown.filter((p) => pagesProgress[p.page]).length;

  // 3. Homework Tasks state
  const homeworkKey = slot.subject.includes("গণিত") ? "math_ch5" : "science_ch4";
  const initialHwList = DEFAULT_HOMEWORK[homeworkKey] || DEFAULT_HOMEWORK.science_ch4;

  const [homeworkProgress, setHomeworkProgress] = useState<Record<string, boolean>>(() => {
    const saved = loadSessionState(slot.id);
    if (saved?.homeworkProgress) return saved.homeworkProgress;
    const initial: Record<string, boolean> = {};
    initialHwList.forEach((hw) => {
      initial[hw.id] = false;
    });
    return initial;
  });

  const handleToggleHomework = (hwId: string) => {
    const nextVal = !homeworkProgress[hwId];
    const updated = { ...homeworkProgress, [hwId]: nextVal };
    setHomeworkProgress(updated);
    saveSessionState({
      taskId: slot.id,
      secondsElapsed,
      isRunning,
      lastUpdatedTimestamp: Date.now(),
      pagesProgress,
      homeworkProgress: updated,
      noteContent,
    });
  };

  // 4. Handwritten Note Simulation
  const [noteContent, setNoteContent] = useState(
    "১. সালোকসংশ্লেষণের পূর্ণাঙ্গ সমীকরণ: 6CO₂ + 12H₂O ⟶ C₆H₁₂O₆ + 6H₂O + 6O₂ (সূর্যালোক ও ক্লোরোফিল)।\n২. পাতায় ক্লোরোপ্লাস্টের গ্রানায় আলোক পর্যায় এবং স্ট্রোমায় অন্ধকার পর্যায় (কেলভিন চক্র) ঘটে।"
  );
  const [noteSavedNotice, setNoteSavedNotice] = useState(false);

  const handleSaveNote = () => {
    setNoteSavedNotice(true);
    saveSessionState({
      taskId: slot.id,
      secondsElapsed,
      isRunning,
      lastUpdatedTimestamp: Date.now(),
      pagesProgress,
      homeworkProgress,
      noteContent,
    });
    setTimeout(() => setNoteSavedNotice(false), 3500);
  };

  // 5. Post-Study Mastery Check Quiz
  const [quizStarted, setQuizStarted] = useState(false);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, number>>({});
  const [quizSubmitted, setQuizSubmitted] = useState(false);
  const [quizScore, setQuizScore] = useState(0);

  const questions = [
    {
      id: "q1",
      question_bn: "সালোকসংশ্লেষণ প্রক্রিয়ার প্রধান কাঁচামাল কোন দুটি?",
      question_en: "Which two are the primary raw materials of photosynthesis?",
      options_bn: [
        "অক্সিজেন ও নাইট্রোজেন",
        "কার্বন ডাই-অক্সাইড ও পানি (CO₂ এবং H₂O)",
        "গ্লুকোজ ও ক্লোরোফিল",
        "অ্যালকোহল ও মিথেন",
      ],
      options_en: [
        "Oxygen & Nitrogen",
        "Carbon Dioxide & Water (CO₂ and H₂O)",
        "Glucose & Chlorophyll",
        "Alcohol & Methane",
      ],
      correctIndex: 1,
      explanation_bn: "পাঠ্যবই পৃষ্ঠা ৪২: উদ্ভিদ মূল দিয়ে পানি এবং পত্ররন্ধ্র দিয়ে CO₂ গ্রহণ করে।",
      explanation_en: "Textbook page 42: Plants absorb water via roots and CO₂ through stomata.",
    },
    {
      id: "q2",
      question_bn: "সালোকসংশ্লেষণের আলোক পর্যায়ে পানির বিভাজনে কী উৎপন্ন হয়?",
      question_en: "What is produced during the photolysis of water in the light phase?",
      options_bn: [
        "শুধুমাত্র কার্বন ডাই-অক্সাইড",
        "অক্সিজেন (O₂), ATP এবং NADPH",
        "ল্যাকটিক অ্যাসিড",
        "মিথেন গ্যাস",
      ],
      options_en: [
        "Only Carbon Dioxide",
        "Oxygen (O₂), ATP and NADPH",
        "Lactic acid",
        "Methane gas",
      ],
      correctIndex: 1,
      explanation_bn: "পাঠ্যবই পৃষ্ঠা ৪৩: আলোক পর্যায়ে সৌরশক্তি ব্যবহার করে পানি ভেঙে O₂, ATP এবং NADPH উৎপন্ন হয়।",
      explanation_en: "Textbook page 43: Solar energy splits water into O₂, ATP, and NADPH.",
    },
    {
      id: "q3",
      question_bn: "বায়ুমণ্ডলে অক্সিজেন ও কার্বন ডাই-অক্সাইডের ভারসাম্য রক্ষায় সালোকসংশ্লেষণের ভূমিকা কী?",
      question_en: "What role does photosynthesis play in balancing O₂ and CO₂?",
      options_bn: [
        "CO₂ বৃদ্ধি করে",
        "গ্রিনহাউস গ্যাস CO₂ শোষণ করে এবং প্রাণীদের শ্বাসকার্যের জন্য O₂ মুক্ত করে",
        "নাইট্রোজেন উৎপন্ন করে",
        "কোনো ভূমিকা নেই",
      ],
      options_en: [
        "Increases CO₂",
        "Absorbs CO₂ greenhouse gas and releases O₂ for aerobic respiration",
        "Produces nitrogen",
        "Has no role",
      ],
      correctIndex: 1,
      explanation_bn: "পাঠ্যবই পৃষ্ঠা ৪৪: উদ্ভিদ CO₂ শোষণ করে খাদ্য তৈরি করে এবং পরিবেশের জন্য অপরিহার্য O₂ উন্মুক্ত করে।",
      explanation_en: "Textbook page 44: It sequesters CO₂ and replenishes O₂ in the atmosphere.",
    },
  ];

  const handleSelectQuizAnswer = (qId: string, index: number) => {
    if (quizSubmitted) return;
    setSelectedAnswers((prev) => ({ ...prev, [qId]: index }));
  };

  const handleSubmitQuiz = () => {
    let score = 0;
    questions.forEach((q) => {
      if (selectedAnswers[q.id] === q.correctIndex) {
        score += 1;
      }
    });
    setQuizScore(score);
    setQuizSubmitted(true);
  };

  const handleFinishStudy = () => {
    onComplete(slot.id);
  };

  const chapterPart = slot.chapterPart || 2;
  const chapterTotalParts = slot.chapterTotalParts || 3;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      {/* Top Header Navigation (Fixed: Removed empty pill!) */}
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
          <span>{t.session.backToRoutine}</span>
        </button>

        {/* Clean, Verified Pro Badge (Fixed: NO empty pill beside it!) */}
        <div style={{ display: "flex", alignItems: "center" }}>
          <span
            style={{
              backgroundColor: "var(--color-success-surface)",
              color: "var(--color-success)",
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 14px",
              borderRadius: "var(--radius-full)",
              fontSize: "var(--text-xs)",
              fontWeight: 700,
              border: "1px solid rgba(16, 185, 129, 0.2)",
            }}
          >
            <ShieldCheck size={15} />
            <span>{t.session.proVerified}</span>
          </span>
        </div>
      </div>

      {/* Chapter Information & Stopwatch Header Card */}
      <div
        className="card"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "var(--space-5)",
          padding: "var(--space-6)",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", flex: 1, minWidth: 280 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap" }}>
            <span
              style={{
                backgroundColor: "var(--color-primary-surface)",
                color: "var(--color-primary)",
                fontWeight: 700,
                fontSize: "var(--text-xs)",
                padding: "2px 8px",
                borderRadius: "var(--radius-full)",
              }}
            >
              {lang === "bn" ? slot.subject : slot.subjectEn}
            </span>

            {/* Repaired Chapter Chunking Badge (No stray cursor or glitch!) */}
            <span
              style={{
                backgroundColor: "var(--color-warning-surface)",
                color: "var(--color-warning)",
                fontWeight: 700,
                fontSize: "var(--text-xs)",
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                padding: "2px 10px",
                borderRadius: "var(--radius-full)",
                border: "1px solid rgba(245, 158, 11, 0.25)",
              }}
            >
              <Layers size={13} />
              <span>
                {lang === "bn"
                  ? `${t.session.chunkingBadge}: ${t.session.partOf} ${toBengaliDigits(chapterPart)} / ${toBengaliDigits(chapterTotalParts)}`
                  : `${t.session.chunkingBadge}: Part ${chapterPart} of ${chapterTotalParts}`}
              </span>
            </span>

            <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              ({t.session.chunkExplanation})
            </span>
          </div>

          <h1 style={{ fontSize: "var(--text-2xl)", fontWeight: 800, margin: 0, color: "var(--color-text-main)" }}>
            {lang === "bn" ? slot.chapterTitle : slot.chapterTitleEn}
          </h1>

          {/* Printed Textbook Page Citation */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "var(--space-2)",
              fontSize: "var(--text-sm)",
              color: "var(--color-text-secondary)",
            }}
          >
            <BookOpen size={16} style={{ color: "var(--color-primary)" }} />
            <span>
              {slot.bookTitle} — {t.today.printedPages}:{" "}
              <strong style={{ color: "var(--color-primary)" }}>
                {lang === "bn" ? slot.printedPages : slot.printedPagesEn}
              </strong>
            </span>
          </div>
        </div>

        {/* Repaired Persistent Stopwatch Container */}
        <div
          className="stopwatch-container"
          style={{
            backgroundColor: "var(--color-surface-hover)",
            border: "1.5px solid var(--color-border)",
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
            <span>{t.session.stopwatch}</span>
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
                borderRadius: "var(--radius-md)",
              }}
            >
              {isRunning ? <Pause size={13} /> : <Play size={13} />}
              <span>{isRunning ? t.session.pause : t.session.resume}</span>
            </button>

            <button
              onClick={resetStopwatch}
              className="btn-secondary touch-target"
              style={{
                padding: "6px 10px",
                fontSize: "var(--text-xs)",
                borderRadius: "var(--radius-md)",
              }}
              title={t.session.reset}
              aria-label={t.session.reset}
            >
              <RotateCcw size={13} />
            </button>
          </div>
        </div>
      </div>

      {/* SECTION 1: Page-by-Page Progress with Dynamic Ticking */}
      <div className="card" style={{ padding: "var(--space-6)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)", flexWrap: "wrap", gap: "var(--space-2)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <BookOpen size={20} style={{ color: "var(--color-primary)" }} />
            <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
              {t.session.pagesStudyTitle}
            </h2>
          </div>

          {/* Dynamic Progress Indicator (Fixed: updates instantly on click!) */}
          <span
            style={{
              fontSize: "var(--text-xs)",
              color: completedPagesCount === pagesBreakdown.length ? "var(--color-success)" : "var(--color-text-muted)",
              fontWeight: 700,
              backgroundColor: "var(--color-surface-hover)",
              padding: "4px 10px",
              borderRadius: "var(--radius-full)",
            }}
          >
            {lang === "bn"
              ? `${t.session.completedPages}: ${toBengaliDigits(completedPagesCount)} / ${toBengaliDigits(pagesBreakdown.length)} ${t.session.pagesUnit}`
              : `${t.session.completedPages}: ${completedPagesCount} / ${pagesBreakdown.length} ${t.session.pagesUnit}`}
          </span>
        </div>

        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", marginBottom: "var(--space-4)" }}>
          {t.session.pagesInstruction}
        </p>

        {/* Page List */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          {pagesBreakdown.map((pageItem) => {
            const isCompleted = Boolean(pagesProgress[pageItem.page]);

            return (
              <div
                key={pageItem.page}
                style={{
                  border: `1.5px solid ${isCompleted ? "var(--color-success)" : "var(--color-border)"}`,
                  borderRadius: "var(--radius-lg)",
                  padding: "var(--space-4)",
                  backgroundColor: isCompleted ? "var(--color-surface)" : "var(--color-surface-hover)",
                  transition: "all 0.15s ease",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "var(--space-2)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                    <button
                      onClick={() => handleTogglePage(pageItem.page)}
                      className="touch-target"
                      style={{
                        padding: 0,
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        color: isCompleted ? "var(--color-success)" : "var(--color-text-muted)",
                      }}
                      aria-label={isCompleted ? "Unmark page" : "Mark page complete"}
                    >
                      {isCompleted ? <CheckCircle2 size={24} /> : <Circle size={24} />}
                    </button>
                    <div>
                      <span
                        style={{
                          fontSize: "var(--text-xs)",
                          fontWeight: 700,
                          color: "var(--color-primary)",
                          textTransform: "uppercase",
                        }}
                      >
                        {lang === "bn" ? `পৃষ্ঠা ${toBengaliDigits(pageItem.page)}` : `Page ${pageItem.page}`}
                      </span>
                      <h3 style={{ fontSize: "var(--text-base)", fontWeight: 700, margin: 0 }}>
                        {pageItem.title}
                      </h3>
                    </div>
                  </div>

                  <span style={{ fontSize: "var(--text-xs)", color: isCompleted ? "var(--color-success)" : "var(--color-text-muted)", fontWeight: 600 }}>
                    {isCompleted ? "✓ পড়া শেষ" : "পড়ুন ও টিক দিন"}
                  </span>
                </div>

                {/* Summary & Keypoints revealed when ticked */}
                {isCompleted && (
                  <div
                    style={{
                      marginTop: "var(--space-3)",
                      paddingTop: "var(--space-3)",
                      borderTop: "1px dashed var(--color-border)",
                      display: "flex",
                      flexDirection: "column",
                      gap: "var(--space-2)",
                    }}
                  >
                    <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-main)", fontWeight: 500 }}>
                      <MathRenderer content={pageItem.summary_bn} />
                    </p>
                    <div style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-text-secondary)", marginTop: 2 }}>
                      {t.session.keyPoints}
                    </div>
                    <ul style={{ paddingLeft: "var(--space-4)", fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", display: "flex", flexDirection: "column", gap: 3 }}>
                      {pageItem.key_points.map((pt, i) => (
                        <li key={i}>{pt}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* SECTION 2: Homework & Physical Notebook Check */}
      <div className="card" style={{ padding: "var(--space-6)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}>
          <CheckSquare size={20} style={{ color: "var(--color-primary)" }} />
          <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
            {t.session.homeworkTitle}
          </h2>
        </div>
        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", marginBottom: "var(--space-4)" }}>
          {t.session.homeworkInstruction}
        </p>

        {/* Homework Items */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", marginBottom: "var(--space-5)" }}>
          {initialHwList.map((hw) => {
            const isDone = Boolean(homeworkProgress[hw.id]);
            return (
              <div
                key={hw.id}
                onClick={() => handleToggleHomework(hw.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-3)",
                  padding: "var(--space-3) var(--space-4)",
                  backgroundColor: isDone ? "var(--color-success-surface)" : "var(--color-surface-hover)",
                  border: `1px solid ${isDone ? "var(--color-success)" : "var(--color-border)"}`,
                  borderRadius: "var(--radius-md)",
                  cursor: "pointer",
                }}
              >
                <button
                  className="touch-target"
                  style={{
                    background: "none",
                    border: "none",
                    padding: 0,
                    cursor: "pointer",
                    color: isDone ? "var(--color-success)" : "var(--color-text-muted)",
                  }}
                  aria-label="Toggle homework item"
                >
                  {isDone ? <CheckCircle2 size={20} /> : <Circle size={20} />}
                </button>
                <span
                  style={{
                    fontSize: "var(--text-sm)",
                    fontWeight: 500,
                    textDecoration: isDone ? "line-through" : "none",
                    color: isDone ? "var(--color-text-muted)" : "var(--color-text-main)",
                  }}
                >
                  {lang === "bn" ? hw.title_bn : hw.title_en || hw.title_bn}
                </span>
              </div>
            );
          })}
        </div>

        {/* Written Notes / Upload Simulation */}
        <div
          style={{
            padding: "var(--space-4)",
            border: "1px dashed var(--color-border)",
            borderRadius: "var(--radius-lg)",
            backgroundColor: "var(--color-surface-subtle)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-2)" }}>
            <span style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-text-secondary)" }}>
              {t.session.notebookPreview}
            </span>
            <button
              onClick={handleSaveNote}
              className="btn-primary touch-target"
              style={{ fontSize: "var(--text-xs)", padding: "6px 14px" }}
            >
              {t.session.saveNotebook}
            </button>
          </div>

          <textarea
            value={noteContent}
            onChange={(e) => setNoteContent(e.target.value)}
            rows={3}
            style={{
              width: "100%",
              padding: "var(--space-3)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border)",
              fontFamily: "inherit",
              fontSize: "var(--text-sm)",
              backgroundColor: "var(--color-surface)",
              color: "var(--color-text-main)",
              resize: "vertical",
            }}
          />

          {noteSavedNotice && (
            <div style={{ marginTop: "var(--space-2)", fontSize: "var(--text-xs)", color: "var(--color-success)", fontWeight: 700 }}>
              ✓ {t.session.notebookSavedSuccess}
            </div>
          )}
        </div>
      </div>

      {/* SECTION 3: Mastery Check Quiz */}
      <div className="card" style={{ padding: "var(--space-6)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <Award size={20} style={{ color: "var(--color-primary)" }} />
            <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
              {t.session.masteryQuizTitle}
            </h2>
          </div>
          {!quizStarted && (
            <button
              onClick={() => setQuizStarted(true)}
              className="btn-primary touch-target"
              style={{ fontSize: "var(--text-xs)", padding: "6px 16px" }}
            >
              {t.session.startQuiz}
            </button>
          )}
        </div>

        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", marginBottom: "var(--space-4)" }}>
          {t.session.quizInstruction}
        </p>

        {quizStarted && (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
            {questions.map((q, idx) => (
              <div
                key={q.id}
                style={{
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-md)",
                  padding: "var(--space-4)",
                  backgroundColor: "var(--color-surface)",
                }}
              >
                <div style={{ fontWeight: 700, fontSize: "var(--text-sm)", marginBottom: "var(--space-3)" }}>
                  {idx + 1}. {lang === "bn" ? q.question_bn : q.question_en}
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "var(--space-2)" }}>
                  {(lang === "bn" ? q.options_bn : q.options_en).map((opt, optIdx) => {
                    const isSelected = selectedAnswers[q.id] === optIdx;
                    let bg = "var(--color-surface-hover)";
                    let borderColor = "var(--color-border)";

                    if (quizSubmitted) {
                      if (optIdx === q.correctIndex) {
                        bg = "var(--color-success-surface)";
                        borderColor = "var(--color-success)";
                      } else if (isSelected && optIdx !== q.correctIndex) {
                        bg = "var(--color-error-surface)";
                        borderColor = "var(--color-error)";
                      }
                    } else if (isSelected) {
                      bg = "var(--color-primary-surface)";
                      borderColor = "var(--color-primary)";
                    }

                    return (
                      <button
                        key={optIdx}
                        onClick={() => handleSelectQuizAnswer(q.id, optIdx)}
                        className="touch-target"
                        style={{
                          textAlign: "left",
                          padding: "10px 14px",
                          borderRadius: "var(--radius-md)",
                          backgroundColor: bg,
                          border: `1px solid ${borderColor}`,
                          cursor: quizSubmitted ? "default" : "pointer",
                          fontSize: "var(--text-xs)",
                          fontWeight: isSelected ? 700 : 500,
                          color: "var(--color-text-main)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                        }}
                      >
                        <span>{opt}</span>
                        {quizSubmitted && optIdx === q.correctIndex && (
                          <Check size={16} style={{ color: "var(--color-success)" }} />
                        )}
                      </button>
                    );
                  })}
                </div>

                {quizSubmitted && (
                  <div
                    style={{
                      marginTop: "var(--space-3)",
                      padding: "var(--space-2) var(--space-3)",
                      borderRadius: "var(--radius-sm)",
                      backgroundColor: "var(--color-surface-hover)",
                      fontSize: "var(--text-xs)",
                      color: "var(--color-text-secondary)",
                    }}
                  >
                    💡 {lang === "bn" ? q.explanation_bn : q.explanation_en}
                  </div>
                )}
              </div>
            ))}

            {!quizSubmitted ? (
              <button
                onClick={handleSubmitQuiz}
                className="btn-primary touch-target"
                style={{ alignSelf: "flex-end", padding: "10px 24px", fontSize: "var(--text-sm)" }}
              >
                {t.session.submitQuiz}
              </button>
            ) : (
              <div
                style={{
                  padding: "var(--space-4)",
                  borderRadius: "var(--radius-md)",
                  backgroundColor: "var(--color-success-surface)",
                  border: "1px solid var(--color-success)",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div style={{ fontWeight: 800, color: "var(--color-success)", fontSize: "var(--text-base)" }}>
                  {t.session.yourScore}: {lang === "bn" ? toBengaliDigits(quizScore) : quizScore} / {lang === "bn" ? toBengaliDigits(questions.length) : questions.length}
                </div>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-success)", fontWeight: 700 }}>
                  ✓ {t.session.perfectScoreMsg}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Completion Action Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "var(--space-4) 0",
        }}
      >
        <button
          onClick={onBack}
          className="btn-secondary touch-target"
          style={{ fontSize: "var(--text-sm)" }}
        >
          {t.session.backToRoutine}
        </button>

        <button
          onClick={handleFinishStudy}
          className="btn-primary touch-target"
          style={{
            fontSize: "var(--text-sm)",
            padding: "10px 24px",
            backgroundColor: "var(--color-success)",
            borderColor: "var(--color-success)",
          }}
        >
          {t.session.finishSessionBtn}
        </button>
      </div>

      <style>{`
        @media (max-width: 640px) {
          .stopwatch-container {
            width: 100% !important;
            min-width: unset !important;
          }
        }
      `}</style>
    </div>
  );
};

