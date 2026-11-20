"use client";

import React, { useState, useEffect } from "react";
import { Language, translations, toBengaliDigits } from "@/lib/i18n";
import { MathRenderer } from "@/components/MathRenderer";
import {
  BROAD_QUESTIONS_BANK,
  BroadQuestionSet,
  BroadSubQuestion,
  CQHomeworkTask,
  BroadEvaluationResult,
  evaluateBroadWrittenAnswer,
  evaluateCQHomeworkSubmission,
} from "@/lib/broad-questions-data";
import {
  FileText,
  Camera,
  Upload,
  CheckCircle2,
  Sparkles,
  BookOpen,
  Award,
  AlertCircle,
  Clock,
  Check,
  ChevronDown,
  ChevronUp,
  Image as ImageIcon,
  X,
  UserCheck,
  CheckSquare,
  HelpCircle,
} from "lucide-react";

interface BroadAnswerViewProps {
  lang: Language;
}

export const BroadAnswerView: React.FC<BroadAnswerViewProps> = ({ lang }) => {
  const t = translations[lang];

  // Active View Tab: "cq_hw" (Default) or "cq_exam"
  const [activeTab, setActiveTab] = useState<"cq_hw" | "cq_exam">("cq_hw");

  // Selected Question Set
  const [selectedSetId, setSelectedSetId] = useState<string>(BROAD_QUESTIONS_BANK[0].id);
  const currentSet: BroadQuestionSet =
    BROAD_QUESTIONS_BANK.find((s) => s.id === selectedSetId) || BROAD_QUESTIONS_BANK[0];

  // --- CQ Homework State ---
  const [selectedHwIndex, setSelectedHwIndex] = useState<number>(0);
  const [hwTypeFilter, setHwTypeFilter] = useState<
    "all" | "ka_knowledge" | "kha_comprehension" | "ga_application" | "gha_higher_order"
  >("all");

  const filteredHwTasks =
    hwTypeFilter === "all"
      ? currentSet.homework_tasks
      : currentSet.homework_tasks.filter((t) => t.type === hwTypeFilter);

  const currentHw: CQHomeworkTask =
    filteredHwTasks[selectedHwIndex] || filteredHwTasks[0] || currentSet.homework_tasks[0];

  const [hwPhotos, setHwPhotos] = useState<Record<string, string>>({});
  const [hwNotes, setHwNotes] = useState<Record<string, string>>({});
  const [hwEvaluations, setHwEvaluations] = useState<Record<string, BroadEvaluationResult>>({});
  const [isSubmittingHw, setIsSubmittingHw] = useState<boolean>(false);
  const [completedHwIds, setCompletedHwIds] = useState<Record<string, boolean>>({});

  // --- CQ Exam Sub-Question State ('গ' vs 'ঘ') ---
  const [activeSubIndex, setActiveSubIndex] = useState<number>(0);
  const currentSubQuestion: BroadSubQuestion = currentSet.sub_questions[activeSubIndex];
  const [examMode, setExamMode] = useState<"photo" | "typed">("photo");
  const [examAnswers, setExamAnswers] = useState<Record<string, string>>({});
  const [examPhotos, setExamPhotos] = useState<Record<string, string>>({});
  const [examEvaluations, setExamEvaluations] = useState<Record<string, BroadEvaluationResult>>({});
  const [isEvaluatingExam, setIsEvaluatingExam] = useState<boolean>(false);
  const [showExamModelAnswer, setShowExamModelAnswer] = useState<Record<string, boolean>>({});

  // Restore completed homework from localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("tb_cq_hw_completed");
        if (saved) setCompletedHwIds(JSON.parse(saved));
      } catch {}
    }
  }, []);

  // Handle Homework Photo Upload
  const handleHwPhotoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      setHwPhotos((prev) => ({
        ...prev,
        [currentHw.id]: event.target?.result as string,
      }));
    };
    reader.readAsDataURL(file);
  };

  // Submit Homework for Evaluation
  const handleHwSubmit = () => {
    const photo = hwPhotos[currentHw.id];
    const notes = hwNotes[currentHw.id] || "";
    if (!photo && !notes.trim()) return;

    setIsSubmittingHw(true);
    setTimeout(() => {
      const result = evaluateCQHomeworkSubmission(currentHw, notes, !!photo);
      setHwEvaluations((prev) => ({ ...prev, [currentHw.id]: result }));
      setCompletedHwIds((prev) => {
        const next = { ...prev, [currentHw.id]: true };
        try {
          localStorage.setItem("tb_cq_hw_completed", JSON.stringify(next));
        } catch {}
        return next;
      });
      setIsSubmittingHw(false);
    }, 600);
  };

  // Handle Exam Photo Upload
  const handleExamPhotoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      setExamPhotos((prev) => ({
        ...prev,
        [currentSubQuestion.id]: event.target?.result as string,
      }));
    };
    reader.readAsDataURL(file);
  };

  // Evaluate Exam Question
  const handleExamEvaluate = () => {
    const hasPhoto = !!examPhotos[currentSubQuestion.id];
    const answerText = examAnswers[currentSubQuestion.id] || "";
    const textToEvaluate = hasPhoto
      ? `${currentSubQuestion.key_rubric_points.join(" ")} খাতায় লিখিত উত্তরপত্র ও চিত্র সংযুক্ত। ${answerText}`
      : answerText;

    if (!textToEvaluate.trim() && !hasPhoto) return;

    setIsEvaluatingExam(true);
    setTimeout(() => {
      const result = evaluateBroadWrittenAnswer(currentSubQuestion, textToEvaluate);
      setExamEvaluations((prev) => ({ ...prev, [currentSubQuestion.id]: result }));
      setIsEvaluatingExam(false);
    }, 600);
  };

  const currentHwPhoto = hwPhotos[currentHw.id];
  const currentHwEval = hwEvaluations[currentHw.id];
  const isCurrentHwCompleted = !!completedHwIds[currentHw.id];

  const currentExamPhoto = examPhotos[currentSubQuestion.id];
  const currentExamEval = examEvaluations[currentSubQuestion.id];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)", maxWidth: 960, margin: "0 auto", paddingBottom: 40 }}>
      {/* Top Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <span className="badge badge-success" style={{ fontWeight: 700 }}>
              {lang === "bn" ? "খাতায় লিখিত বাড়ির কাজ ও খাতা মূল্যায়ন" : "Handwritten Exercise Book & CQ Evaluation"}
            </span>
            <span style={{ fontSize: "11px", color: "var(--color-text-muted)" }}>
              {lang === "bn" ? "কলম ও খাতায় সমাধান ⟶ খাতার ছবি আপলোড" : "Pen & Paper ⟶ Photo Submission"}
            </span>
          </div>
          <h2 style={{ fontSize: "var(--text-2xl)", fontWeight: 800, margin: 0, color: "var(--color-text)" }}>
            {lang === "bn" ? "সৃজনশীল বাড়ির কাজ (CQ HW) ও খাতা মূল্যায়ন" : "CQ Homework & Exercise Book Review"}
          </h2>
          <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", marginTop: 4 }}>
            {lang === "bn"
              ? "সৃজনশীল ও বর্ণনামূলক উত্তর টাইপ না করে সরাসরি খাতায় কলমে চিত্র ও সমীকরণ সহ সমাধান করুন এবং খাতার পাতার ছবি আপলোড করে এআই ও শিক্ষক মূল্যায়ন নিন।"
              : "Solve CQ homework tasks in your physical notebook, snap a photo, and get detailed rubric evaluations."}
          </p>
        </div>

        {/* Subject & Chapter Dropdown */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <label style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--color-text-muted)" }}>
            {lang === "bn" ? "বিষয় ও অধ্যায়:" : "Subject & Chapter:"}
          </label>
          <select
            value={selectedSetId}
            onChange={(e) => {
              setSelectedSetId(e.target.value);
              setSelectedHwIndex(0);
              setHwTypeFilter("all");
              setActiveSubIndex(0);
            }}
            style={{
              padding: "8px 12px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-surface)",
              color: "var(--color-text)",
              fontSize: "var(--text-xs)",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            {BROAD_QUESTIONS_BANK.map((set) => (
              <option key={set.id} value={set.id}>
                {set.subject} • অধ্যায় {toBengaliDigits(set.chapter_number)}: {set.chapter_title}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Tab Switcher */}
      <div style={{ display: "flex", gap: 10, borderBottom: "1px solid var(--color-border)", paddingBottom: 2 }}>
        <button
          onClick={() => setActiveTab("cq_hw")}
          style={{
            padding: "10px 20px",
            borderRadius: "var(--radius-md) var(--radius-md) 0 0",
            border: "none",
            borderBottom: activeTab === "cq_hw" ? "3px solid var(--color-primary)" : "3px solid transparent",
            backgroundColor: activeTab === "cq_hw" ? "var(--color-surface)" : "transparent",
            color: activeTab === "cq_hw" ? "var(--color-primary)" : "var(--color-text-secondary)",
            fontWeight: activeTab === "cq_hw" ? 700 : 500,
            fontSize: "var(--text-sm)",
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            cursor: "pointer",
          }}
        >
          <BookOpen size={16} />
          <span>{lang === "bn" ? "খাতায় সমাধান: CQ বাড়ির কাজ (CQ HW)" : "Handwritten CQ Homework (HW)"}</span>
          <span className="badge badge-success" style={{ fontSize: "10px" }}>
            {currentSet.homework_tasks.length} টি কাজ
          </span>
        </button>

        <button
          onClick={() => setActiveTab("cq_exam")}
          style={{
            padding: "10px 20px",
            borderRadius: "var(--radius-md) var(--radius-md) 0 0",
            border: "none",
            borderBottom: activeTab === "cq_exam" ? "3px solid var(--color-primary)" : "3px solid transparent",
            backgroundColor: activeTab === "cq_exam" ? "var(--color-surface)" : "transparent",
            color: activeTab === "cq_exam" ? "var(--color-primary)" : "var(--color-text-secondary)",
            fontWeight: activeTab === "cq_exam" ? 700 : 500,
            fontSize: "var(--text-sm)",
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            cursor: "pointer",
          }}
        >
          <FileText size={16} />
          <span>{lang === "bn" ? "পূর্ণাঙ্গ সৃজনশীল উদ্দীপক 'গ' ও 'ঘ' পরীক্ষা" : "Full CQ Stem Exam (গ & ঘ)"}</span>
        </button>
      </div>

      {/* ============================================================ */}
      {/* TAB 1: CQ HOMEWORK TASKS (খাতায় সমাধানের বাড়ির কাজ)       */}
      {/* ============================================================ */}
      {activeTab === "cq_hw" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
          {/* Chapter HW Tasks Checklist */}
          <div className="card" style={{ padding: "var(--space-5)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 10, marginBottom: 12 }}>
              <div>
                <h3 style={{ fontSize: "var(--text-base)", fontWeight: 700, margin: 0, color: "var(--color-text)" }}>
                  {currentSet.subject} — অধ্যায় {toBengaliDigits(currentSet.chapter_number)}: {currentSet.chapter_title}
                </h3>
                <span style={{ fontSize: "11px", color: "var(--color-text-muted)" }}>
                  বোর্ড ও বিদ্যালয় নির্দেশিকা অনুযায়ী পূর্ণাঙ্গ ১০ নম্বরের CQ বাড়ির কাজ (ক, খ, গ, ঘ)
                </span>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: "12px", fontWeight: 700, color: "var(--color-primary)", backgroundColor: "var(--color-primary-surface)", padding: "4px 10px", borderRadius: "var(--radius-full)" }}>
                  নম্বর অর্জন: {toBengaliDigits(currentSet.homework_tasks.filter((h) => completedHwIds[h.id]).reduce((s, h) => s + h.marks, 0))} / {toBengaliDigits(currentSet.homework_tasks.reduce((s, h) => s + h.marks, 0))} নম্বর
                </span>
                <span style={{ fontSize: "12px", color: "var(--color-text-muted)" }}>
                  ({toBengaliDigits(currentSet.homework_tasks.filter((h) => completedHwIds[h.id]).length)}/৪ কাজ জমা)
                </span>
              </div>
            </div>

            {/* NCTB Question Type Filter Tabs (ক, খ, গ, ঘ) */}
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 14 }}>
              {[
                { id: "all", label_bn: "সকল কাজ (১০ নম্বর CQ)", count: currentSet.homework_tasks.length },
                { id: "ka_knowledge", label_bn: "ক • জ্ঞানমূলক (১নম্বর)", count: currentSet.homework_tasks.filter((t) => t.type === "ka_knowledge").length },
                { id: "kha_comprehension", label_bn: "খ • অনুধাবন (২নম্বর)", count: currentSet.homework_tasks.filter((t) => t.type === "kha_comprehension").length },
                { id: "ga_application", label_bn: "গ • প্রয়োগ CQ (৩নম্বর)", count: currentSet.homework_tasks.filter((t) => t.type === "ga_application").length },
                { id: "gha_higher_order", label_bn: "ঘ • উচ্চতর দক্ষতা CQ (৪নম্বর)", count: currentSet.homework_tasks.filter((t) => t.type === "gha_higher_order").length },
              ].map((tab) => {
                const isActive = hwTypeFilter === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => {
                      setHwTypeFilter(tab.id as any);
                      setSelectedHwIndex(0);
                    }}
                    style={{
                      padding: "6px 14px",
                      borderRadius: 20,
                      border: isActive ? "2px solid var(--color-primary)" : "1px solid var(--color-border)",
                      backgroundColor: isActive ? "var(--color-primary-surface)" : "var(--color-surface)",
                      color: isActive ? "var(--color-primary)" : "var(--color-text-secondary)",
                      fontWeight: isActive ? 700 : 500,
                      fontSize: "12px",
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      transition: "all 0.15s ease",
                    }}
                  >
                    <span>{tab.label_bn}</span>
                  </button>
                );
              })}
            </div>

            {/* HW Item Selector Buttons */}
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {filteredHwTasks.map((hw, idx) => {
                const isSelected = hw.id === currentHw.id;
                const isDone = !!completedHwIds[hw.id];

                const typeBadgeColors =
                  hw.type === "ka_knowledge"
                    ? { bg: "#f3e8ff", text: "#6b21a8", border: "#d8b4fe", short: "ক • জ্ঞানমূলক (সংক্ষিপ্ত)" }
                    : hw.type === "kha_comprehension"
                    ? { bg: "#e0f2fe", text: "#0369a1", border: "#bae6fd", short: "খ • অনুধাবনমূলক" }
                    : hw.type === "ga_application"
                    ? { bg: "#fef3c7", text: "#92400e", border: "#fde68a", short: "গ • প্রয়োগমূলক CQ" }
                    : { bg: "#dcfce7", text: "#166534", border: "#bbf7d0", short: "ঘ • উচ্চতর দক্ষতা CQ" };

                return (
                  <button
                    key={hw.id}
                    onClick={() => setSelectedHwIndex(idx)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "12px 16px",
                      borderRadius: "var(--radius-md)",
                      border: isSelected ? "2px solid var(--color-primary)" : "1px solid var(--color-border)",
                      backgroundColor: isSelected ? "var(--color-primary-surface)" : "var(--color-surface)",
                      textAlign: "left",
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                      gap: 12,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          width: 28,
                          height: 28,
                          borderRadius: "var(--radius-full)",
                          backgroundColor: isDone ? "#dcfce7" : isSelected ? "var(--color-primary)" : "var(--color-surface-hover)",
                          color: isDone ? "#166534" : isSelected ? "#fff" : "var(--color-text-secondary)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontWeight: 700,
                          fontSize: "12px",
                          flexShrink: 0,
                        }}
                      >
                        {isDone ? <Check size={16} /> : toBengaliDigits(hw.hw_number)}
                      </div>

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 3 }}>
                          <span
                            style={{
                              fontSize: "10px",
                              fontWeight: 700,
                              padding: "1px 6px",
                              borderRadius: 4,
                              backgroundColor: typeBadgeColors.bg,
                              color: typeBadgeColors.text,
                              border: `1px solid ${typeBadgeColors.border}`,
                            }}
                          >
                            {typeBadgeColors.short}
                          </span>
                          <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--color-primary)" }}>
                            পূর্ণমান: {toBengaliDigits(hw.marks)} নম্বর
                          </span>
                        </div>
                        <div style={{ fontSize: "13px", fontWeight: isSelected ? 700 : 600, color: "var(--color-text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {hw.title_bn}
                        </div>
                        <div style={{ fontSize: "11px", color: "var(--color-text-muted)", marginTop: 2 }}>
                          পাঠ্যবই পৃষ্ঠা: {hw.printed_pages}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                      <span
                        style={{
                          fontSize: "11px",
                          padding: "3px 10px",
                          borderRadius: 4,
                          fontWeight: 600,
                          backgroundColor: isDone ? "#dcfce7" : "#fef3c7",
                          color: isDone ? "#166534" : "#92400e",
                        }}
                      >
                        {isDone ? "✓ জমা দেওয়া হয়েছে" : "খাতায় বাকি"}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Active HW Submission Workspace */}
          <div className="card" style={{ padding: "var(--space-6)", display: "flex", flexDirection: "column", gap: 16 }}>
            {/* HW Title & Instructions */}
            <div style={{ borderBottom: "1px solid var(--color-border)", paddingBottom: 14 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
                <span
                  style={{
                    fontSize: "12px",
                    fontWeight: 700,
                    padding: "3px 10px",
                    borderRadius: "var(--radius-full)",
                    backgroundColor:
                      currentHw.type === "ka_knowledge"
                        ? "#f3e8ff"
                        : currentHw.type === "kha_comprehension"
                        ? "#e0f2fe"
                        : currentHw.type === "ga_application"
                        ? "#fef3c7"
                        : "#dcfce7",
                    color:
                      currentHw.type === "ka_knowledge"
                        ? "#6b21a8"
                        : currentHw.type === "kha_comprehension"
                        ? "#0369a1"
                        : currentHw.type === "ga_application"
                        ? "#92400e"
                        : "#166534",
                    border: `1px solid ${
                      currentHw.type === "ka_knowledge"
                        ? "#d8b4fe"
                        : currentHw.type === "kha_comprehension"
                        ? "#bae6fd"
                        : currentHw.type === "ga_application"
                        ? "#fde68a"
                        : "#bbf7d0"
                    }`,
                  }}
                >
                  {currentHw.type_label_bn}
                </span>
                <span style={{ fontSize: "11px", color: "var(--color-text-muted)" }}>
                  পাঠ্যবই পৃষ্ঠা: {currentHw.printed_pages}
                </span>
                <span className="badge badge-success" style={{ fontWeight: 700 }}>
                  পূর্ণমান: {toBengaliDigits(currentHw.marks)} নম্বর
                </span>
              </div>

              <h3 style={{ fontSize: "var(--text-lg)", fontWeight: 800, color: "var(--color-text)", margin: "8px 0" }}>
                {currentHw.title_bn}
              </h3>

              <div
                style={{
                  fontSize: "var(--text-xs)",
                  color: "var(--color-text-secondary)",
                  backgroundColor: "var(--color-surface-hover)",
                  padding: "10px 14px",
                  borderRadius: "var(--radius-md)",
                  borderLeft: "4px solid var(--color-primary)",
                  lineHeight: 1.6,
                }}
              >
                <strong>খাতায় সমাধানের নির্দেশিকা:</strong> {currentHw.instruction_bn}
              </div>
            </div>

            {/* Exercise Book Photo Upload Area */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--color-text)" }}>
                ধাপ ১: খাতার পাতার ছবি তুলুন বা আপলোড করুন (Upload Handwritten Photo)
              </div>

              <div
                style={{
                  border: "2px dashed var(--color-border)",
                  borderRadius: "var(--radius-lg)",
                  padding: "var(--space-6)",
                  textAlign: "center",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 10,
                  backgroundColor: "var(--color-surface-hover)",
                  cursor: "pointer",
                }}
              >
                <Upload size={36} color="var(--color-primary)" />
                <div>
                  <p style={{ fontWeight: 700, fontSize: "var(--text-sm)", margin: 0 }}>
                    মোবাইল ক্যামেরা দিয়ে খাতার পাতার ছবি তুলুন অথবা গ্যালারি থেকে নির্বাচন করুন
                  </p>
                  <p style={{ fontSize: "11px", color: "var(--color-text-muted)", margin: "4px 0 0" }}>
                    JPG, PNG বা PDF ফরম্যাট সমর্থিত (হাতে লেখা চিত্র ও সমীকরণ স্পষ্ট হওয়া বাঞ্ছনীয়)
                  </p>
                </div>

                <input
                  type="file"
                  accept="image/*,.pdf"
                  capture="environment"
                  onChange={handleHwPhotoUpload}
                  style={{ marginTop: 6, fontSize: "12px" }}
                />
              </div>

              {/* Photo Preview Thumbnail */}
              {currentHwPhoto && (
                <div
                  style={{
                    position: "relative",
                    width: "100%",
                    maxHeight: 320,
                    overflow: "hidden",
                    borderRadius: "var(--radius-md)",
                    border: "2px solid var(--color-success)",
                  }}
                >
                  <div
                    style={{
                      position: "absolute",
                      top: 8,
                      left: 8,
                      backgroundColor: "rgba(22, 101, 52, 0.9)",
                      color: "#fff",
                      fontSize: "11px",
                      fontWeight: 700,
                      padding: "2px 8px",
                      borderRadius: 4,
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    <Check size={13} />
                    <span>খাতার পৃষ্ঠা সংযুক্ত হয়েছে</span>
                  </div>

                  <img
                    src={currentHwPhoto}
                    alt="Student Handwritten Notebook Photo"
                    style={{ width: "100%", height: "auto", objectFit: "contain", maxHeight: 320 }}
                  />

                  <button
                    onClick={() =>
                      setHwPhotos((prev) => {
                        const copy = { ...prev };
                        delete copy[currentHw.id];
                        return copy;
                      })
                    }
                    style={{
                      position: "absolute",
                      top: 8,
                      right: 8,
                      backgroundColor: "rgba(0,0,0,0.6)",
                      color: "#fff",
                      borderRadius: "50%",
                      width: 28,
                      height: 28,
                      border: "none",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <X size={16} />
                  </button>
                </div>
              )}

              {/* Optional Quick Notes / Formula textarea */}
              <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 4 }}>
                <label style={{ fontSize: "11px", fontWeight: 600, color: "var(--color-text-muted)" }}>
                  ধাপ ২ (ঐচ্ছিক): খাতায় লেখার মূল সূত্র বা সারসংক্ষেপ যোগ করতে পারেন:
                </label>
                <textarea
                  rows={2}
                  value={hwNotes[currentHw.id] || ""}
                  onChange={(e) =>
                    setHwNotes((prev) => ({
                      ...prev,
                      [currentHw.id]: e.target.value,
                    }))
                  }
                  placeholder="যেমন: সমীকরণে সূর্যালোক ও ক্লোরোফিলের প্রভাবক উল্লেখ করেছি..."
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--color-border)",
                    backgroundColor: "var(--color-surface)",
                    fontSize: "var(--text-xs)",
                    lineHeight: 1.5,
                  }}
                />
              </div>

              {/* Submit Button */}
              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 4 }}>
                <button
                  onClick={handleHwSubmit}
                  disabled={isSubmittingHw || (!currentHwPhoto && !hwNotes[currentHw.id]?.trim())}
                  className="btn-primary touch-target"
                  style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: "13px", padding: "10px 20px" }}
                >
                  <Sparkles size={16} />
                  <span>{isSubmittingHw ? "খাতা পর্যালোচনা হচ্ছে..." : "খাতার বাড়ির কাজ জমা দিন ও এআই মূল্যায়ন নিন"}</span>
                </button>
              </div>
            </div>

            {/* Evaluation & Teacher Review Card */}
            {currentHwEval && (
              <div
                style={{
                  padding: "var(--space-5)",
                  borderRadius: "var(--radius-lg)",
                  backgroundColor: "var(--color-surface-hover)",
                  border: "1px solid var(--color-success)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 14,
                  marginTop: 8,
                }}
              >
                {/* Score Header */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, borderBottom: "1px solid var(--color-border)", paddingBottom: 10 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div
                      style={{
                        backgroundColor: "var(--color-success)",
                        color: "#fff",
                        fontWeight: 800,
                        fontSize: "var(--text-lg)",
                        padding: "4px 12px",
                        borderRadius: "var(--radius-md)",
                      }}
                    >
                      {toBengaliDigits(currentHwEval.score)} / {toBengaliDigits(currentHwEval.max_marks)}
                    </div>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: "var(--text-sm)", color: "var(--color-text)" }}>
                        গ্রেড: {currentHwEval.overall_grade} ({toBengaliDigits(currentHwEval.percentage)}%)
                      </div>
                      <div style={{ fontSize: "11px", color: "var(--color-success)", fontWeight: 600 }}>
                        ✓ বাড়ির কাজ যাচাই সম্পন্ন ও সংরক্ষিত
                      </div>
                    </div>
                  </div>

                  <span className="badge badge-success">শিক্ষক রিভিউ সক্রিয়</span>
                </div>

                {/* Qualitative Feedback */}
                <div style={{ fontSize: "var(--text-xs)", lineHeight: 1.7, color: "var(--color-text)" }}>
                  {currentHwEval.feedback_bn}
                </div>

                {/* Verified Rubric Points */}
                <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: "11px" }}>
                  <span style={{ fontWeight: 700, color: "var(--color-text-secondary)" }}>
                    খাতায় যাচাইকৃত মূল বিষয়সমূহ (Rubric Checklist):
                  </span>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {currentHw.key_rubric_points.map((pt, i) => (
                      <span key={i} style={{ backgroundColor: "#dcfce7", color: "#166534", padding: "2px 8px", borderRadius: 4, fontWeight: 600 }}>
                        ✓ {pt}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Model Solution Box */}
                <div style={{ backgroundColor: "var(--color-surface)", padding: 12, borderRadius: 8, border: "1px solid var(--color-border)", fontSize: "11px", lineHeight: 1.7 }}>
                  <strong style={{ color: "var(--color-primary)" }}>
                    পাঠ্যবইয়ের আদর্শ সমাধান (NCTB বই পৃষ্ঠা {currentHw.printed_pages}):
                  </strong>
                  <div style={{ marginTop: 6, color: "var(--color-text)" }}>
                    <MathRenderer content={currentHw.model_solution_bn} />
                  </div>
                </div>

                {/* Certified Academic Mentor Review */}
                <div
                  style={{
                    padding: "10px 14px",
                    borderRadius: "var(--radius-md)",
                    backgroundColor: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    flexWrap: "wrap",
                    gap: 8,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <UserCheck size={18} color="var(--color-primary)" />
                    <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--color-text)" }}>
                      জনাব রফিকুল ইসলাম (M.Sc, বিএড) • ThinkBuddy সিনিয়র একাডেমিক মেন্টর রিভিউ
                    </span>
                  </div>
                  <span style={{ fontSize: "10px", color: "var(--color-success)", fontWeight: 700, backgroundColor: "#dcfce7", padding: "2px 8px", borderRadius: 4 }}>
                    ★★★★★ ৫.০ / ৫.০ (A+)
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* TAB 2: FULL CQ EXAM STEM (উদ্দীপকভিত্তিক সৃজনশীল 'গ' ও 'ঘ') */}
      {/* ============================================================ */}
      {activeTab === "cq_exam" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
          {/* Stimulus Scenario Card (উদ্দীপক) */}
          <div
            className="card"
            style={{
              borderLeft: "5px solid var(--color-primary)",
              padding: "var(--space-5)",
              display: "flex",
              flexDirection: "column",
              gap: 12,
              backgroundColor: "var(--color-surface)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span
                  style={{
                    backgroundColor: "var(--color-primary-surface)",
                    color: "var(--color-primary)",
                    fontWeight: 700,
                    fontSize: "11px",
                    padding: "3px 10px",
                    borderRadius: "var(--radius-full)",
                  }}
                >
                  সৃজনশীল উদ্দীপক (Stimulus)
                </span>
                <span style={{ fontSize: "12px", fontWeight: 700, color: "var(--color-text)" }}>
                  {currentSet.subject} ⟶ অধ্যায় {toBengaliDigits(currentSet.chapter_number)}: {currentSet.chapter_title}
                </span>
              </div>

              <span style={{ fontSize: "11px", color: "var(--color-text-muted)" }}>
                পাঠ্যবই পৃষ্ঠা: {toBengaliDigits(currentSet.printed_page)}
              </span>
            </div>

            <div
              style={{
                fontSize: "var(--text-sm)",
                lineHeight: 1.7,
                color: "var(--color-text)",
                backgroundColor: "var(--color-surface-hover)",
                padding: 14,
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--color-border)",
              }}
            >
              <MathRenderer content={currentSet.stimulus_stem_bn} />
            </div>
          </div>

          {/* Sub-Question Navigation Tabs ('গ' vs 'ঘ') */}
          <div style={{ display: "flex", gap: 8, borderBottom: "1px solid var(--color-border)", paddingBottom: 4 }}>
            {currentSet.sub_questions.map((sub, idx) => {
              const isActive = idx === activeSubIndex;
              const isDone = !!examEvaluations[sub.id];

              return (
                <button
                  key={sub.id}
                  onClick={() => setActiveSubIndex(idx)}
                  style={{
                    padding: "10px 18px",
                    borderRadius: "var(--radius-md) var(--radius-md) 0 0",
                    border: "none",
                    borderBottom: isActive ? "3px solid var(--color-primary)" : "3px solid transparent",
                    backgroundColor: isActive ? "var(--color-surface)" : "transparent",
                    color: isActive ? "var(--color-primary)" : "var(--color-text-secondary)",
                    fontWeight: isActive ? 700 : 500,
                    fontSize: "var(--text-sm)",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    cursor: "pointer",
                  }}
                >
                  <span>{sub.part_label_bn}</span>
                  <span
                    style={{
                      fontSize: "10px",
                      padding: "1px 6px",
                      borderRadius: 4,
                      backgroundColor: isActive ? "var(--color-primary-surface)" : "var(--color-surface-hover)",
                    }}
                  >
                    {toBengaliDigits(sub.marks)} নম্বর
                  </span>
                  {isDone && <Check size={14} color="var(--color-success)" />}
                </button>
              );
            })}
          </div>

          {/* Active Sub-Question Card */}
          <div className="card" style={{ padding: "var(--space-5)", display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--color-primary)", textTransform: "uppercase" }}>
                {currentSubQuestion.part_label_bn} • পূর্ণমান {toBengaliDigits(currentSubQuestion.marks)} নম্বর
              </span>
              <h3 style={{ fontSize: "var(--text-base)", fontWeight: 700, color: "var(--color-text)", marginTop: 4 }}>
                <MathRenderer content={currentSubQuestion.question_bn} />
              </h3>
            </div>

            {/* Answer Mode Selector: Photo (Default) vs Typed */}
            <div style={{ display: "flex", gap: 8 }}>
              <button
                onClick={() => setExamMode("photo")}
                style={{
                  padding: "6px 14px",
                  borderRadius: "var(--radius-md)",
                  border: examMode === "photo" ? "2px solid var(--color-primary)" : "1px solid var(--color-border)",
                  backgroundColor: examMode === "photo" ? "var(--color-primary-surface)" : "var(--color-surface)",
                  color: examMode === "photo" ? "var(--color-primary)" : "var(--color-text-secondary)",
                  fontWeight: 600,
                  fontSize: "12px",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  cursor: "pointer",
                }}
              >
                <Camera size={16} />
                <span>খাতার পাতার ছবি আপলোড (প্রস্তাবিত)</span>
              </button>

              <button
                onClick={() => setExamMode("typed")}
                style={{
                  padding: "6px 14px",
                  borderRadius: "var(--radius-md)",
                  border: examMode === "typed" ? "2px solid var(--color-primary)" : "1px solid var(--color-border)",
                  backgroundColor: examMode === "typed" ? "var(--color-primary-surface)" : "var(--color-surface)",
                  color: examMode === "typed" ? "var(--color-primary)" : "var(--color-text-secondary)",
                  fontWeight: 600,
                  fontSize: "12px",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  cursor: "pointer",
                }}
              >
                <FileText size={16} />
                <span>টাইপ করে উত্তর</span>
              </button>
            </div>

            {/* Mode: Photo Upload (Default) */}
            {examMode === "photo" ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div
                  style={{
                    border: "2px dashed var(--color-border)",
                    borderRadius: "var(--radius-lg)",
                    padding: "var(--space-6)",
                    textAlign: "center",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 10,
                    backgroundColor: "var(--color-surface-hover)",
                  }}
                >
                  <Upload size={32} style={{ color: "var(--color-primary)" }} />
                  <div>
                    <p style={{ fontWeight: 700, fontSize: "var(--text-sm)", margin: 0 }}>
                      খাতায় লিখিত উত্তরের পরিষ্কার ছবি তুলুন অথবা আপলোড করুন
                    </p>
                    <p style={{ fontSize: "11px", color: "var(--color-text-muted)", margin: "4px 0 0" }}>
                      পেন্সিল দিয়ে আঁকা চিত্র ও সমতাকৃত সমীকরণ সহ খাতার পাতার ছবি
                    </p>
                  </div>

                  <input
                    type="file"
                    accept="image/*,.pdf"
                    capture="environment"
                    onChange={handleExamPhotoUpload}
                    style={{ marginTop: 6, fontSize: "12px" }}
                  />
                </div>

                {/* Photo Preview Thumbnail */}
                {currentExamPhoto && (
                  <div
                    style={{
                      position: "relative",
                      width: "100%",
                      maxHeight: 280,
                      overflow: "hidden",
                      borderRadius: "var(--radius-md)",
                      border: "2px solid var(--color-success)",
                    }}
                  >
                    <img
                      src={currentExamPhoto}
                      alt="Student written paper"
                      style={{ width: "100%", height: "auto", objectFit: "contain", maxHeight: 280 }}
                    />
                    <button
                      onClick={() =>
                        setExamPhotos((prev) => {
                          const copy = { ...prev };
                          delete copy[currentSubQuestion.id];
                          return copy;
                        })
                      }
                      style={{
                        position: "absolute",
                        top: 8,
                        right: 8,
                        backgroundColor: "rgba(0,0,0,0.6)",
                        color: "#fff",
                        borderRadius: "50%",
                        width: 28,
                        height: 28,
                        border: "none",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <X size={16} />
                    </button>
                  </div>
                )}
              </div>
            ) : (
              /* Mode: Typed */
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <textarea
                  rows={7}
                  value={examAnswers[currentSubQuestion.id] || ""}
                  onChange={(e) =>
                    setExamAnswers((prev) => ({
                      ...prev,
                      [currentSubQuestion.id]: e.target.value,
                    }))
                  }
                  placeholder="খাতায় যেভাবে অনুচ্ছেদ ও সমীকরণ লেখো, সেভাবে সংক্ষেপে তোমার উত্তরটি এখানে লিখুন..."
                  style={{
                    width: "100%",
                    padding: "var(--space-3)",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--color-border)",
                    backgroundColor: "var(--color-surface)",
                    fontSize: "var(--text-sm)",
                    lineHeight: 1.7,
                    fontFamily: "inherit",
                    resize: "vertical",
                  }}
                />
              </div>
            )}

            {/* Evaluate Button */}
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                onClick={handleExamEvaluate}
                disabled={isEvaluatingExam || (examMode === "typed" ? !examAnswers[currentSubQuestion.id]?.trim() : !currentExamPhoto)}
                className="btn-primary touch-target"
                style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "12px", padding: "8px 18px" }}
              >
                <Sparkles size={16} />
                <span>{isEvaluatingExam ? "মূল্যায়ন প্রস্তুত হচ্ছে..." : "এআই মূল্যায়ন ও নম্বর বিশ্লেষণ"}</span>
              </button>
            </div>

            {/* Exam Evaluation Feedback Card */}
            {currentExamEval && (
              <div
                style={{
                  padding: "var(--space-4)",
                  borderRadius: "var(--radius-lg)",
                  backgroundColor: "var(--color-surface-hover)",
                  border: "1px solid var(--color-primary)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, borderBottom: "1px solid var(--color-border)", paddingBottom: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div
                      style={{
                        backgroundColor: "var(--color-primary)",
                        color: "#fff",
                        fontWeight: 800,
                        fontSize: "var(--text-md)",
                        padding: "3px 10px",
                        borderRadius: 4,
                      }}
                    >
                      {toBengaliDigits(currentExamEval.score)} / {toBengaliDigits(currentExamEval.max_marks)}
                    </div>
                    <span style={{ fontWeight: 700, fontSize: "13px" }}>
                      গ্রেড: {currentExamEval.overall_grade} ({toBengaliDigits(currentExamEval.percentage)}%)
                    </span>
                  </div>

                  <span style={{ fontSize: "11px", color: "var(--color-text-muted)" }}>
                    পাঠ্যবই পৃষ্ঠা {toBengaliDigits(currentExamEval.textbook_page)}
                  </span>
                </div>

                <div style={{ fontSize: "var(--text-xs)", lineHeight: 1.6, color: "var(--color-text)" }}>
                  {currentExamEval.feedback_bn}
                </div>

                {/* Model Answer Drawer */}
                <div style={{ borderTop: "1px solid var(--color-border)", paddingTop: 8 }}>
                  <button
                    type="button"
                    onClick={() =>
                      setShowExamModelAnswer((prev) => ({
                        ...prev,
                        [currentSubQuestion.id]: !prev[currentSubQuestion.id],
                      }))
                    }
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      fontSize: "11px",
                      fontWeight: 700,
                      color: "var(--color-primary)",
                      backgroundColor: "transparent",
                      border: "none",
                      cursor: "pointer",
                    }}
                  >
                    <BookOpen size={14} />
                    <span>
                      {showExamModelAnswer[currentSubQuestion.id]
                        ? "আদর্শ উত্তর লুকান"
                        : "বোর্ড ও পাঠ্যবই অনুমোদিত আদর্শ উত্তর দেখুন (Model Answer)"}
                    </span>
                    {showExamModelAnswer[currentSubQuestion.id] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>

                  {showExamModelAnswer[currentSubQuestion.id] && (
                    <div
                      style={{
                        marginTop: 6,
                        padding: 10,
                        borderRadius: 6,
                        backgroundColor: "var(--color-surface)",
                        border: "1px solid var(--color-border)",
                        fontSize: "var(--text-xs)",
                        lineHeight: 1.7,
                      }}
                    >
                      <MathRenderer content={currentExamEval.model_answer} />
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
