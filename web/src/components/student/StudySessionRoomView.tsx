"use client";

import React, { useState, useEffect, useRef } from "react";
import { StudyTask, PageStudyBreakdown, HomeworkTask, UploadedStudyNote } from "@/lib/types";
import { Language, translations, toBengaliDigits } from "@/lib/i18n";
import { apiClient } from "@/lib/api-client";
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
  Upload,
  Camera,
  Layers,
  ListTodo,
  CheckSquare,
  ShieldCheck,
  Star,
  UserCheck,
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

  // Chapter Chunking & Pages Data (Science 42-44 or task defaults)
  const chapterPart = task.chapter_part || 2;
  const chapterTotalParts = task.chapter_total_parts || 3;

  const defaultPagesBreakdown: PageStudyBreakdown[] = task.pages_breakdown || [
    {
      page: 42,
      title: "সালোকসংশ্লেষণের মৌলিক ধারণা ও কাঁচামাল",
      summary_bn:
        "সালোকসংশ্লেষণ হলো সবুজ উদ্ভিদের শর্করা তৈরির জৈব-রাসায়নিক প্রক্রিয়া। প্রধান কাঁচামাল: কার্বন ডাই-অক্সাইড (CO₂) ও পানি (H₂O); শক্তি যোগায় সূর্যালোক এবং ক্লোরোফিল সৌরশক্তি শোষণ করে।",
      key_points: [
        "উদ্ভিদের পাতায় মেসোফিল কোষে অবস্থিত ক্লোরোপ্লাস্টে প্রক্রিয়াটি সম্পন্ন হয়।",
        "বায়ুমণ্ডল থেকে পত্ররন্ধ্রের মাধ্যমে CO₂ গৃহীত হয় এবং মূলরোম দিয়ে মাটি থেকে পানি শোষিত হয়।",
        "সবুজ পাতার ক্লোরোফিল কণা সৌরশক্তি শোষণ করে রাসায়নিক শক্তিতে রূপান্তরিত করে।",
      ],
    },
    {
      page: 43,
      title: "সালোকসংশ্লেষণের বিক্রিয়া ও পর্যায়সমূহ",
      summary_bn:
        "পূর্ণাঙ্গ সমীকরণ: 6CO₂ + 12H₂O ⟶ C₆H₁₂O₆ + 6H₂O + 6O₂ (সূর্যালোক ও ক্লোরোফিলের উপস্থিতিতে)। প্রক্রিয়াটি আলোক এবং অন্ধকার (কার্বন বিজারণ) পর্যায়ে সম্পন্ন হয়।",
      key_points: [
        "আলোক পর্যায়ে পানির ফটোলাইসিস ঘটে এবং উচ্চ শক্তি সম্পন্ন ATP ও NADPH তৈরি হয়।",
        "অন্ধকার পর্যায়ে কেলভিন চক্রের মাধ্যমে CO₂ বিজারিত হয়ে গ্লুকোজ উৎপন্ন হয়।",
        "উপজাত হিসেবে বায়ুমণ্ডলে জীবনধারণের জন্য অক্সিজেন (O₂) নির্গত হয়।",
      ],
    },
    {
      page: 44,
      title: "সালোকসংশ্লেষণের পরিবেশগত তাৎপর্য ও গ্যাসীয় ভারসাম্য",
      summary_bn:
        "সালোকসংশ্লেষণ সমগ্র জীবজগতের খাদ্যের একমাত্র প্রাথমিক উৎস এবং বায়ুমণ্ডলে অক্সিজেন ও কার্বন ডাই-অক্সাইডের অনুপাত ভারসাম্যপূর্ণ রাখে।",
      key_points: [
        "সমগ্র প্রাণী ও মানবকুলের শ্বাসকার্যের জন্য অক্সিজেন নিশ্চিত করে।",
        "গ্রিনহাউস গ্যাস কার্বন ডাই-অক্সাইড শোষণ করে পরিবেশ ও জলবায়ু রক্ষা করে।",
        "জীবাশ্ম জ্বালানি (কয়লা, তেল, গ্যাস) মূলত উদ্ভিদের সঞ্চিত প্রাচীন সৌরশক্তি।",
      ],
    },
  ];

  // Track page study progress & split times
  const [pagesProgress, setPagesProgress] = useState<PageStudyState[]>(
    defaultPagesBreakdown.map((p) => ({
      page: p.page,
      completed: false,
    }))
  );

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

  // Homework Tasks state
  const defaultHomework: HomeworkTask[] = task.homework_tasks || [
    {
      id: "hw_1",
      title_bn: "সালোকসংশ্লেষণ প্রক্রিয়ার পূর্ণাঙ্গ রাসায়নিক সমীকরণটি খাতায় না দেখে লিখো ও সমতাকরণ করো।",
      completed: false,
    },
    {
      id: "hw_2",
      title_bn: "একটি ক্লোরোপ্লাস্টের চিত্র এঁকে গ্রানা ও স্ট্রোমা চিহ্নিত করো।",
      completed: false,
    },
    {
      id: "hw_3",
      title_bn: "বায়ুমণ্ডলে অক্সিজেন ও কার্বন ডাই-অক্সাইডের ভারসাম্য রক্ষায় সালোকসংশ্লেষণের ভূমিকা ৩টি বাক্যে খাতায় ব্যাখ্যা করো।",
      completed: false,
    },
  ];

  const [homeworkList, setHomeworkList] = useState<HomeworkTask[]>(defaultHomework);
  const handleToggleHomework = (hwId: string) => {
    setHomeworkList((prev) =>
      prev.map((hw) => (hw.id === hwId ? { ...hw, completed: !hw.completed } : hw))
    );
  };

  // Note taking & Upload state
  const [noteContent, setNoteContent] = useState(
    "১. সালোকসংশ্লেষণের পূর্ণাঙ্গ সমীকরণ: 6CO₂ + 12H₂O ⟶ C₆H₁₂O₆ + 6H₂O + 6O₂ (সূর্যালোক ও ক্লোরোফিল)।\n২. পাতায় ক্লোরোপ্লাস্টের গ্রানায় আলোক পর্যায় এবং স্ট্রোমায় অন্ধকার পর্যায় (কেলভিন চক্র) ঘটে।"
  );
  const [isSavedNote, setIsSavedNote] = useState(false);
  const [uploadedImagePreview, setUploadedImagePreview] = useState<string | null>(
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='600' height='260' viewBox='0 0 600 260'><rect width='100%25' height='100%25' fill='%23f1f5f9'/><rect x='15' y='15' width='570' height='230' rx='10' fill='%23ffffff' stroke='%2394a3b8' stroke-dasharray='4'/><text x='35' y='50' font-family='sans-serif' font-size='14' font-weight='bold' fill='%230f172a'>হাতে লেখা বিজ্ঞান খাতা • পৃষ্ঠা ৪২-৪৪ (তাহমিদ আলিম)</text><circle cx='80' cy='130' r='35' fill='%23bbf7d0' stroke='%2315803d'/><text x='62' y='135' font-family='sans-serif' font-size='11' fill='%2314532d'>ক্লোরোপ্লাস্ট</text><text x='150' y='120' font-family='sans-serif' font-size='13' fill='%230284c7'>6CO₂ + 12H₂O ⟶ C₆H₁₂O₆ + 6H₂O + 6O₂</text><text x='150' y='145' font-family='sans-serif' font-size='12' fill='%23475569'>✓ গ্রানা ও স্ট্রোমা লেবেলিং সম্পন্ন • কেলভিন চক্রের ধাপসমূহ বর্ণিত</text><text x='35' y='210' font-family='sans-serif' font-size='11' fill='%2364748b'>জমা দেয়ার সময়: আজকের তারিখ • ThinkBuddy Verified Notebook</text></svg>"
  );
  const [uploadSuccessMsg, setUploadSuccessMsg] = useState(false);

  const handleImageFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setUploadedImagePreview(reader.result as string);
        setIsSavedNote(false);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSaveAndSubmitNote = async () => {
    setIsSavedNote(true);
    setUploadSuccessMsg(true);

    const newNote: UploadedStudyNote = {
      id: `note_${Date.now()}`,
      task_id: task.id,
      task_title: task.title,
      subject: task.subject,
      student_id: "stu_101",
      student_name: studentName,
      pages_covered: `${task.printed_page_start || 42}–${task.printed_page_end || 44}`,
      time_spent_seconds: secondsElapsed,
      text_note: noteContent,
      image_url: uploadedImagePreview || undefined,
      created_at: new Date().toISOString(),
      is_pro: true,
      teacher_review: {
        teacher_name: "জনাব রফিকুল ইসলাম (M.Sc, বিএড)",
        badge: "সিনিয়র বিজ্ঞান শিক্ষক • ThinkBuddy Academic Mentor",
        comments:
          "চমৎকার প্রস্তুতি ও সুন্দর হাতের লেখা! সালোকসংশ্লেষণের সমীকরণ ও কাঁচামাল নিখুঁত। অভিভাবক ও শিক্ষক ড্যাশবোর্ডে সংরক্ষিত হয়েছে।",
        rating: 5,
        reviewed_at: new Date().toISOString(),
      },
    };

    await apiClient.uploadStudyNote(newNote);
    setTimeout(() => setUploadSuccessMsg(false), 4000);
  };

  // Post-Study Mastery Check Quiz
  const [quizStarted, setQuizStarted] = useState(false);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, number>>({});
  const [quizSubmitted, setQuizSubmitted] = useState(false);
  const [quizScore, setQuizScore] = useState(0);

  const scienceQuestions = [
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
      explanation_bn:
        "পাঠ্যবই পৃষ্ঠা ৪২ অনুযায়ী: উদ্ভিদ মূল দিয়ে পানি (H₂O) শোষণ করে এবং পত্ররন্ধ্র দিয়ে CO₂ গ্রহণ করে।",
      explanation_en:
        "From textbook page 42: Plants absorb water via root hairs and CO₂ through stomata.",
    },
    {
      id: "q2",
      question_bn: "সালোকসংশ্লেষণের আলোক পর্যায়ে পানির বিভাজন ঘটে কী উৎপন্ন হয়?",
      question_en: "What is produced in the light-dependent phase through photolysis of water?",
      options_bn: [
        "শুধুমাত্র কার্বন ডাই-অক্সাইড",
        "অক্সিজেন (O₂), ATP এবং NADPH₂",
        "ল্যাকটিক অ্যাসিড",
        "ইউরিয়া",
      ],
      options_en: [
        "Only Carbon Dioxide",
        "Oxygen (O₂), ATP and NADPH₂",
        "Lactic acid",
        "Urea",
      ],
      correctIndex: 1,
      explanation_bn:
        "পাঠ্যবই পৃষ্ঠা ৪৩ অনুযায়ী: আলোক পর্যায়ে সূর্যালোকের সাহায্যে পানি ভেঙে O₂, ATP এবং NADPH₂ তৈরি হয়।",
      explanation_en:
        "From textbook page 43: Photolysis of water releases O₂ and generates assimilatory power ATP & NADPH₂.",
    },
    {
      id: "q3",
      question_bn: "বায়ুমণ্ডলে অক্সিজেন ও কার্বন ডাই-অক্সাইডের ভারসাম্য বজায় রাখতে সালোকসংশ্লেষণ কীভাবে ভূমিকা রাখে?",
      question_en: "How does photosynthesis maintain O₂ and CO₂ atmospheric balance?",
      options_bn: [
        "CO₂ নির্গত করে এবং O₂ শোষণ করে",
        "গ্রিনহাউস গ্যাস CO₂ শোষণ করে এবং প্রাণীদের জন্য O₂ মুক্ত করে",
        "নাইট্রোজেন গ্যাস উৎপাদন করে",
        "কোনো ভূমিকা রাখে না",
      ],
      options_en: [
        "Emitting CO₂ and consuming O₂",
        "Absorbing CO₂ greenhouse gas and releasing O₂ for aerobic life",
        "Producing nitrogen gas",
        "Has no role",
      ],
      correctIndex: 1,
      explanation_bn:
        "পাঠ্যবই পৃষ্ঠা ৪৪ অনুযায়ী: সালোকসংশ্লেষণ জীবজগতের শ্বাসকার্যের অক্সিজেন সরবরাহ করে এবং ক্ষতিকর CO₂ শোষণ করে পরিবেশ নির্মল রাখে।",
      explanation_en:
        "From textbook page 44: It balances the carbon cycle by sequestering CO₂ and replenishing O₂.",
    },
  ];

  const handleSelectAnswer = (qId: string, optIndex: number) => {
    if (quizSubmitted) return;
    setSelectedAnswers((prev) => ({ ...prev, [qId]: optIndex }));
  };

  const handleSubmitQuiz = () => {
    let score = 0;
    scienceQuestions.forEach((q) => {
      if (selectedAnswers[q.id] === q.correctIndex) {
        score += 1;
      }
    });
    setQuizScore(score);
    setQuizSubmitted(true);
  };

  const handleFinishSession = () => {
    onComplete(task.id, secondsElapsed, noteContent, quizSubmitted ? quizScore : 3);
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

      {/* Dynamic Religious Blessing Banner */}
      <div
        className="card"
        style={{
          background: "linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(16, 185, 129, 0.10) 100%)",
          border: "1px solid var(--color-border)",
          padding: "var(--space-5) var(--space-6)",
          borderRadius: "var(--radius-xl)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-1)" }}>
          <Sparkles size={18} style={{ color: "var(--color-primary)" }} />
          <span style={{ fontSize: "var(--text-sm)", fontWeight: 700, color: "var(--color-primary)" }}>
          </span>
        </div>
        <h2 style={{ fontSize: "var(--text-xl)", fontWeight: 800, margin: "var(--space-1) 0" }}>
        </h2>
        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", margin: 0, lineHeight: 1.6 }}>
        </p>
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
                {lang === "bn" ? "পৃষ্ঠা ৪২–৪৪ এর উপর বাড়ির কাজ (Homework / HW)" : "Homework Tasks on Pages 42–44"}
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

      {/* SECTION 3: Student Study Note & Exercise Book Photo Upload */}
      <div className="card" style={{ padding: "var(--space-6)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)", flexWrap: "wrap", gap: "var(--space-2)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <FileText size={20} style={{ color: "var(--color-primary)" }} />
            <div>
              <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
                {lang === "bn" ? "পড়ার খাতার নোট ও ছবি আপলোড" : "Exercise Book & Study Notes Upload"}
              </h2>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                {lang === "bn"
                  ? "অভিভাবক সরাসরি দেখতে পারবেন এবং ThinkBuddy Pro শিক্ষকরা মূল্যায়ন করবেন"
                  : "Viewable by parents and reviewed by ThinkBuddy Pro certified teachers"}
              </span>
            </div>
          </div>

          <span
            className="badge"
            style={{
              backgroundColor: "rgba(37, 99, 235, 0.12)",
              color: "var(--color-primary)",
              fontWeight: 700,
              fontSize: "var(--text-xs)",
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <Star size={12} />
            <span>Pro: Teacher Review Active</span>
          </span>
        </div>

        {/* Dynamic Religious Note Prompt */}
        <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", marginBottom: "var(--space-3)" }}>
        </p>

        {/* Text Note Area */}
        <textarea
          value={noteContent}
          onChange={(e) => {
            setNoteContent(e.target.value);
            setIsSavedNote(false);
          }}
          placeholder={
            lang === "bn"
              ? "সালোকসংশ্লেষণের মূল সূত্র, সমীকরণ বা কঠিন পয়েন্টগুলো এখানে লিখে রাখো..."
              : "Type your equations, formulas and takeaways..."
          }
          rows={4}
          style={{
            width: "100%",
            padding: "var(--space-3)",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-bg)",
            color: "var(--color-text)",
            fontFamily: "inherit",
            fontSize: "var(--text-sm)",
            lineHeight: 1.6,
            resize: "vertical",
            marginBottom: "var(--space-4)",
          }}
        />

        {/* Photo Upload Area */}
        <div
          style={{
            border: "1.5px dashed var(--color-border)",
            borderRadius: "var(--radius-lg)",
            padding: "var(--space-4)",
            backgroundColor: "var(--color-surface-hover)",
            marginBottom: "var(--space-4)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <Camera size={18} style={{ color: "var(--color-primary)" }} />
              <span style={{ fontSize: "var(--text-sm)", fontWeight: 700 }}>
                {lang === "bn" ? "হাতে লেখা খাতার পাতার ছবি (Handwritten Notebook Photo)" : "Handwritten Exercise Book Photo"}
              </span>
            </div>

            <label
              className="btn-secondary touch-target"
              style={{
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 14px",
                fontSize: "var(--text-xs)",
              }}
            >
              <Upload size={14} />
              <span>{lang === "bn" ? "নতুন ছবি আপলোড করুন" : "Upload Notebook Photo"}</span>
              <input type="file" accept="image/*" onChange={handleImageFileChange} style={{ display: "none" }} />
            </label>
          </div>

          {/* Uploaded Note Preview */}
          {uploadedImagePreview && (
            <div style={{ marginTop: "var(--space-2)" }}>
              <img
                src={uploadedImagePreview}
                alt="Student Handwritten Notebook"
                style={{
                  width: "100%",
                  maxHeight: 220,
                  objectFit: "cover",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--color-border)",
                }}
              />
            </div>
          )}
        </div>

        {/* Action: Save & Submit for Parent & Teacher Review */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-3)" }}>
          <button
            onClick={handleSaveAndSubmitNote}
            className="btn-primary touch-target"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-2)",
              fontSize: "var(--text-sm)",
              padding: "10px 20px",
              borderRadius: "var(--radius-md)",
              fontWeight: 700,
            }}
          >
            {isSavedNote ? <Check size={16} /> : <Upload size={16} />}
            <span>
              {isSavedNote
                ? (lang === "bn" ? "খাতা ও নোট সফলভাবে জমা হয়েছে ✓" : "Note & Notebook Submitted ✓")
                : (lang === "bn" ? "অভিভাবক ও শিক্ষক পর্যালোচনার জন্য জমা দিন" : "Submit for Parent & Teacher Review")}
            </span>
          </button>

          {uploadSuccessMsg && (
            <span style={{ fontSize: "var(--text-xs)", color: "var(--color-success)", fontWeight: 700 }}>
            </span>
          )}
        </div>

        {/* ThinkBuddy Pro Live Teacher Review Preview */}
        <div
          style={{
            marginTop: "var(--space-5)",
            padding: "var(--space-4)",
            borderRadius: "var(--radius-lg)",
            backgroundColor: "rgba(37, 99, 235, 0.04)",
            border: "1px solid rgba(37, 99, 235, 0.2)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-2)", flexWrap: "wrap", gap: "var(--space-2)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <UserCheck size={18} style={{ color: "var(--color-primary)" }} />
              <div>
                <span style={{ fontSize: "var(--text-sm)", fontWeight: 800, color: "var(--color-primary)" }}>
                  জনাব রফিকুল ইসলাম (M.Sc, বিএড)
                </span>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginLeft: 6 }}>
                  (সিনিয়র বিজ্ঞান শিক্ষক • ThinkBuddy Academic Mentor)
                </span>
              </div>
            </div>

            <span
              className="badge"
              style={{
                backgroundColor: "var(--color-success)",
                color: "#ffffff",
                fontSize: "var(--text-xs)",
                fontWeight: 700,
                padding: "2px 8px",
              }}
            >
              ⭐⭐⭐⭐⭐ ৫.০ / ৫.০ (A+)
            </span>
          </div>

          <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", lineHeight: 1.6, margin: 0 }}>
            <strong>{lang === "bn" ? "শিক্ষকের মন্তব্য ও দিকনির্দেশনা: " : "Teacher's Evaluation: "}</strong>
            &ldquo;খাতায় সালোকসংশ্লেষণের পূর্ণাঙ্গ সমীকরণ এবং মেসোফিল টিস্যুর কাজ অত্যন্ত স্পষ্টভাবে লিখেছ। ক্লোরোপ্লাস্টের চিত্রে গ্রানা ও স্ট্রোমা লেবেলিং নিখুঁত। আলোক ও অন্ধকার পর্যায়ের ধাপগুলো এভাবে খাতায় লিখে চর্চা করলে পরীক্ষায় সর্বোচ্চ নম্বর পাবে। চালিয়ে যাও!&rdquo;
          </p>
        </div>
      </div>

      {/* SECTION 4: Post-Study Mastery Check Quiz (শিখন মূল্যায়ন) */}
      <div className="card" style={{ padding: "var(--space-6)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)", flexWrap: "wrap", gap: "var(--space-2)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <HelpCircle size={20} style={{ color: "var(--color-primary)" }} />
            <div>
              <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
                {lang === "bn" ? "শিখন মূল্যায়ন কুইজ (Mastery Check)" : "Post-Study Mastery Check Quiz"}
              </h2>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                {lang === "bn" ? "পৃষ্ঠা ৪২–৪৪ এর ধারণার ওপর ৩টি দ্রুত বহুনির্বাচনি প্রশ্ন" : "3 quick MCQs on pages 42–44"}
              </span>
            </div>
          </div>

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
              {lang === "bn" ? "৩টি প্রশ্ন • প্রতিটি প্রশ্নের মান ১" : "3 Questions • 1 mark each"}
            </span>
          )}
        </div>

        {quizStarted && (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
            {scienceQuestions.map((q, qIndex) => {
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
                      {lang === "bn" ? q.question_bn : q.question_en}
                    </h3>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                    {(lang === "bn" ? q.options_bn : q.options_en).map((optText, optIdx) => {
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
                      {lang === "bn" ? q.explanation_bn : q.explanation_en}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Quiz Submit Button & Feedback */}
            {!quizSubmitted ? (
              <button
                onClick={handleSubmitQuiz}
                disabled={Object.keys(selectedAnswers).length < scienceQuestions.length}
                className="btn-primary touch-target"
                style={{
                  padding: "12px 24px",
                  fontSize: "var(--text-sm)",
                  fontWeight: 700,
                  alignSelf: "flex-start",
                  opacity: Object.keys(selectedAnswers).length < scienceQuestions.length ? 0.6 : 1,
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
                    </h3>
                    <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
                      {lang === "bn" ? "তোমার অর্জিত স্কোর: " : "Your Score: "}
                      <strong style={{ color: "var(--color-success)", fontSize: "var(--text-base)" }}>
                        {lang === "bn"
                          ? `${toBengaliDigits(quizScore)} / ${toBengaliDigits(scienceQuestions.length)}`
                          : `${quizScore} / ${scienceQuestions.length}`}
                      </strong>
                    </div>
                  </div>
                </div>

                <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text)", margin: 0, lineHeight: 1.6 }}>
                  {quizScore === scienceQuestions.length
                    ? (lang === "bn" ? "অসাধারণ দক্ষতা! সবগুলো প্রশ্নের সঠিক উত্তর দিয়েছো।" : "Outstanding! You got every question right.")
                    : quizScore >= 2
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
          </div>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
            {lang === "bn"
              ? `মোট অধ্যয়নকৃত সময়: ${formatTimer(secondsElapsed)} • পৃষ্ঠা ৪২–৪৪ সম্পন্ন`
              : `Total Time Spent: ${formatTimer(secondsElapsed)} • Pages 42–44 Completed`}
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
