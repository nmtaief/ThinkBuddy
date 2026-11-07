import React, { useState } from "react";
import {
  Language,
  translations,
  StudentExamSettings,
  toBengaliDigits,
  calculateDaysRemaining,
} from "@thinkbuddy/shared";
import { Calendar, GraduationCap, BookOpen, Sparkles, X, Check } from "lucide-react";

interface ExamSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: StudentExamSettings;
  onSave: (newSettings: StudentExamSettings) => void;
  lang: Language;
}

const CLASS_OPTIONS = [
  { grade: 6, labelBn: "৬ষ্ঠ শ্রেণি", labelEn: "Class 6" },
  { grade: 7, labelBn: "৭ম শ্রেণি", labelEn: "Class 7" },
  { grade: 8, labelBn: "৮ম শ্রেণি", labelEn: "Class 8" },
  { grade: 9, labelBn: "৯ম শ্রেণি", labelEn: "Class 9" },
  { grade: 10, labelBn: "১০ম শ্রেণি (এসএসসি)", labelEn: "Class 10 (SSC)" },
];

const SYLLABUS_OPTIONS = [
  { id: "nctb_bn", labelBn: "নতুন শিক্ষাক্রম ২০২৪-২৬ (বাংলা মাধ্যম)", labelEn: "New Curriculum 2024-26 (Bangla Medium)" },
  { id: "nctb_en", labelBn: "জাতীয় শিক্ষাক্রম (ইংলিশ ভার্সন)", labelEn: "National Curriculum (English Version)" },
  { id: "madrasah", labelBn: "মাদ্রাসা শিক্ষাক্রম (দাখিল)", labelEn: "Madrasah Board (Dakhil)" },
];

const EXAM_PRESETS = [
  { labelBn: "অর্ধবার্ষিক মূল্যায়ন পরীক্ষা", labelEn: "Mid-term Assessment Exam" },
  { labelBn: "বার্ষিক মূল্যায়ন পরীক্ষা", labelEn: "Annual Assessment Exam" },
  { labelBn: "প্রাক-নির্বাচনী / টেস্ট পরীক্ষা", labelEn: "Pre-test / Test Exam" },
  { labelBn: "এসএসসি প্রস্তুতি পরীক্ষা", labelEn: "SSC Board Preparation" },
];

export const ExamSettingsModal: React.FC<ExamSettingsModalProps> = ({
  isOpen,
  onClose,
  settings,
  onSave,
  lang,
}) => {
  const t = translations[lang];

  const [selectedGrade, setSelectedGrade] = useState<number>(settings.class_grade);
  const [selectedSyllabus, setSelectedSyllabus] = useState<string>(settings.syllabus);
  const [examTitle, setExamTitle] = useState<string>(settings.exam_title);
  const [examDate, setExamDate] = useState<string>(settings.exam_date);

  if (!isOpen) return null;

  const currentDaysLeft = calculateDaysRemaining(examDate);

  const handleSave = () => {
    const classObj = CLASS_OPTIONS.find((c) => c.grade === selectedGrade) || CLASS_OPTIONS[2];
    const newSettings: StudentExamSettings = {
      class_grade: selectedGrade,
      classNameBn: classObj.labelBn,
      syllabus: selectedSyllabus,
      exam_title: examTitle.trim() || (lang === "bn" ? "অর্ধবার্ষিক মূল্যায়ন পরীক্ষা" : "Mid-term Exam"),
      exam_date: examDate,
    };
    onSave(newSettings);
    onClose();
  };

  const todayStr = new Date().toISOString().split("T")[0];

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(15, 23, 42, 0.6)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
        padding: "var(--space-3)",
      }}
    >
      <div
        className="card"
        style={{
          width: "100%",
          maxWidth: 540,
          maxHeight: "92vh",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-4)",
          padding: "var(--space-5)",
          borderRadius: "var(--radius-xl)",
          backgroundColor: "var(--color-surface)",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: "var(--radius-md)",
                backgroundColor: "var(--color-primary-surface)",
                color: "var(--color-primary)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <GraduationCap size={22} />
            </div>
            <div>
              <h2 style={{ fontSize: "var(--text-base)", fontWeight: 800, margin: 0, color: "var(--color-text-main)" }}>
                {t.examSettings.title}
              </h2>
              <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", margin: 0 }}>
                {t.examSettings.subtitle}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="btn-secondary touch-target"
            style={{ padding: 6, minHeight: 36, minWidth: 36 }}
            aria-label="Close dialog"
          >
            <X size={18} />
          </button>
        </div>

        {/* 1. Class Selection */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          <label style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-text-main)" }}>
            {t.examSettings.classLabel}
          </label>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(90px, 1fr))", gap: "var(--space-2)" }}>
            {CLASS_OPTIONS.map((c) => {
              const isSelected = selectedGrade === c.grade;
              return (
                <button
                  key={c.grade}
                  type="button"
                  onClick={() => setSelectedGrade(c.grade)}
                  className="touch-target"
                  style={{
                    padding: "8px 10px",
                    borderRadius: "var(--radius-md)",
                    border: `1.5px solid ${isSelected ? "var(--color-primary)" : "var(--color-border)"}`,
                    backgroundColor: isSelected ? "var(--color-primary-surface)" : "var(--color-surface-hover)",
                    color: isSelected ? "var(--color-primary)" : "var(--color-text-main)",
                    fontWeight: isSelected ? 800 : 500,
                    fontSize: "var(--text-xs)",
                    cursor: "pointer",
                    textAlign: "center",
                    transition: "all 0.15s ease",
                  }}
                >
                  {lang === "bn" ? c.labelBn : c.labelEn}
                </button>
              );
            })}
          </div>
        </div>

        {/* 2. Syllabus / Curriculum */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          <label style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-text-main)" }}>
            {t.examSettings.syllabusLabel}
          </label>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            {SYLLABUS_OPTIONS.map((s) => {
              const label = lang === "bn" ? s.labelBn : s.labelEn;
              const isSelected = selectedSyllabus === label || selectedSyllabus.includes(s.labelBn.split(" ")[0]);
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setSelectedSyllabus(label)}
                  className="touch-target"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "10px 14px",
                    borderRadius: "var(--radius-md)",
                    border: `1.5px solid ${isSelected ? "var(--color-primary)" : "var(--color-border)"}`,
                    backgroundColor: isSelected ? "var(--color-primary-surface)" : "var(--color-surface)",
                    color: isSelected ? "var(--color-primary)" : "var(--color-text-main)",
                    fontWeight: isSelected ? 700 : 500,
                    fontSize: "var(--text-xs)",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all 0.15s ease",
                  }}
                >
                  <span>{label}</span>
                  {isSelected && <Check size={16} />}
                </button>
              );
            })}
          </div>
        </div>

        {/* 3. Upcoming Exam Name */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          <label style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-text-main)" }}>
            {t.examSettings.examTitleLabel}
          </label>
          {/* Quick Presets */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {EXAM_PRESETS.map((p, idx) => {
              const label = lang === "bn" ? p.labelBn : p.labelEn;
              const isSelected = examTitle === label;
              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setExamTitle(label)}
                  style={{
                    padding: "4px 10px",
                    borderRadius: "var(--radius-full)",
                    border: `1px solid ${isSelected ? "var(--color-primary)" : "var(--color-border)"}`,
                    backgroundColor: isSelected ? "var(--color-primary-surface)" : "var(--color-surface-hover)",
                    color: isSelected ? "var(--color-primary)" : "var(--color-text-secondary)",
                    fontSize: "11px",
                    fontWeight: isSelected ? 700 : 500,
                    cursor: "pointer",
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>
          <input
            type="text"
            value={examTitle}
            onChange={(e) => setExamTitle(e.target.value)}
            style={{
              padding: "10px 14px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border)",
              fontSize: "var(--text-sm)",
              backgroundColor: "var(--color-surface)",
              color: "var(--color-text-main)",
            }}
            placeholder={lang === "bn" ? "পরীক্ষার নাম লিখুন" : "Enter exam name"}
          />
        </div>

        {/* 4. Exam Date & Live Countdown Preview */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          <label style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-text-main)" }}>
            {t.examSettings.examDateLabel}
          </label>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flexWrap: "wrap" }}>
            <input
              type="date"
              value={examDate}
              min={todayStr}
              onChange={(e) => setExamDate(e.target.value)}
              style={{
                padding: "10px 14px",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--color-border)",
                fontSize: "var(--text-sm)",
                backgroundColor: "var(--color-surface)",
                color: "var(--color-text-main)",
                minWidth: 160,
                flex: 1,
              }}
            />

            {/* Countdown Badge Preview */}
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "8px 14px",
                borderRadius: "var(--radius-md)",
                backgroundColor: currentDaysLeft > 0 ? "var(--color-primary-surface)" : "var(--color-warning-surface)",
                color: currentDaysLeft > 0 ? "var(--color-primary)" : "var(--color-warning)",
                fontSize: "var(--text-xs)",
                fontWeight: 700,
              }}
            >
              <Calendar size={15} />
              <span>
                {currentDaysLeft > 0
                  ? lang === "bn"
                    ? `${toBengaliDigits(currentDaysLeft)} ${t.examSettings.daysLeftText}`
                    : `${currentDaysLeft} ${t.examSettings.daysLeftText}`
                  : currentDaysLeft === 0
                  ? t.examSettings.todayExam
                  : t.examSettings.examPassed}
              </span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-3)", marginTop: "var(--space-2)" }}>
          <button
            type="button"
            onClick={onClose}
            className="btn-secondary touch-target"
            style={{ fontSize: "var(--text-xs)", padding: "8px 16px" }}
          >
            {t.examSettings.cancelBtn}
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="btn-primary touch-target"
            style={{ fontSize: "var(--text-xs)", padding: "8px 20px" }}
          >
            {t.examSettings.saveBtn}
          </button>
        </div>
      </div>
    </div>
  );
};

