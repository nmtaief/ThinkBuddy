import React, { useState } from "react";
import { Language, translations, toBengaliDigits } from "@thinkbuddy/shared";
import { MathRenderer } from "./MathRenderer";
import { HelpCircle, CheckCircle, XCircle, ArrowRight, Smartphone, BookOpen, RotateCcw } from "lucide-react";

interface PracticeQuizRunnerProps {
  lang: Language;
}

interface QuestionItem {
  id: string;
  position: number;
  question_bn: string;
  question_en: string;
  options: { key: string; text_bn: string; text_en: string }[];
  correctKey: string;
  explanation_bn: string;
  explanation_en: string;
  textbook_page: number;
}

const DEMO_QUESTIONS: QuestionItem[] = [
  {
    id: "q_1",
    position: 1,
    question_bn: "সালোকসংশ্লেষণ প্রক্রিয়ায় উপজাত হিসেবে কোনটি নির্গত হয়?",
    question_en: "Which of the following is released as a byproduct during photosynthesis?",
    options: [
      { key: "A", text_bn: "নাইট্রোজেন গ্যাস", text_en: "Nitrogen gas" },
      { key: "B", text_bn: "অক্সিজেন গ্যাস (O₂)", text_en: "Oxygen gas (O₂)" },
      { key: "C", text_bn: "কার্বন ডাই-অক্সাইড", text_en: "Carbon dioxide" },
      { key: "D", text_bn: "মিথেন", text_en: "Methane" },
    ],
    correctKey: "B",
    explanation_bn: "পাঠ্যবই পৃষ্ঠা ৪৩: আলোক পর্যায়ে পানির ফটোলাইসিসের মাধ্যমে অক্সিজেন উৎপন্ন হয়ে বায়ুমণ্ডলে মুক্ত হয়।",
    explanation_en: "Textbook page 43: Photolysis of water releases oxygen gas into the atmosphere.",
    textbook_page: 43,
  },
  {
    id: "q_2",
    position: 2,
    question_bn: "উদ্ভিদের কোন অঙ্গাণুতে সালোকসংশ্লেষণ ঘটে?",
    question_en: "In which cellular organelle does photosynthesis take place?",
    options: [
      { key: "A", text_bn: "মাইটোকন্ড্রিয়া", text_en: "Mitochondria" },
      { key: "B", text_bn: "রাইবোসোম", text_en: "Ribosome" },
      { key: "C", text_bn: "ক্লোরোপ্লাস্ট", text_en: "Chloroplast" },
      { key: "D", text_bn: "গলজি বস্তু", text_en: "Golgi apparatus" },
    ],
    correctKey: "C",
    explanation_bn: "পাঠ্যবই পৃষ্ঠা ৪২: উদ্ভিদের পাতার মেসোফিল টিস্যুর কোষে অবস্থিত ক্লোরোপ্লাস্টে প্রক্রিয়াটি সংঘটিত হয়।",
    explanation_en: "Textbook page 42: It takes place within the chloroplasts of mesophyll cells in leaves.",
    textbook_page: 42,
  },
  {
    id: "q_3",
    position: 3,
    question_bn: "বর্গের সূত্র অনুসারে $(a + b)^2$ এর সঠিক সম্প্রসারিত রূপ কোনটি?",
    question_en: "According to algebraic identity, what is the expansion of $(a + b)^2$?",
    options: [
      { key: "A", text_bn: "$a^2 + b^2$", text_en: "$a^2 + b^2$" },
      { key: "B", text_bn: "$a^2 + 2ab + b^2$", text_en: "$a^2 + 2ab + b^2$" },
      { key: "C", text_bn: "$a^2 - 2ab + b^2$", text_en: "$a^2 - 2ab + b^2$" },
      { key: "D", text_bn: "$a^2 + ab + b^2$", text_en: "$a^2 + ab + b^2$" },
    ],
    correctKey: "B",
    explanation_bn: "পাঠ্যবই পৃষ্ঠা ৭২: দুই পদের বর্গের মৌলিক সূত্র $(a + b)^2 = a^2 + 2ab + b^2$।",
    explanation_en: "Textbook page 72: Basic square expansion is $(a + b)^2 = a^2 + 2ab + b^2$.",
    textbook_page: 72,
  },
];

export const PracticeQuizRunner: React.FC<PracticeQuizRunnerProps> = ({ lang }) => {
  const t = translations[lang];

  const [activeTab, setActiveTab] = useState<"practice" | "assessed_notice">("practice");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [isAnswered, setIsAnswered] = useState(false);
  const [score, setScore] = useState(0);
  const [isFinished, setIsFinished] = useState(false);

  const currentQ = DEMO_QUESTIONS[currentIndex];

  const handleSelectOption = (key: string) => {
    if (isAnswered) return;
    setSelectedKey(key);
  };

  const handleCheckAnswer = () => {
    if (!selectedKey || isAnswered) return;
    setIsAnswered(true);
    if (selectedKey === currentQ.correctKey) {
      setScore((s) => s + 1);
    }
  };

  const handleNext = () => {
    if (currentIndex + 1 < DEMO_QUESTIONS.length) {
      setCurrentIndex((i) => i + 1);
      setSelectedKey(null);
      setIsAnswered(false);
    } else {
      setIsFinished(true);
    }
  };

  const handleRestart = () => {
    setCurrentIndex(0);
    setSelectedKey(null);
    setIsAnswered(false);
    setScore(0);
    setIsFinished(false);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      {/* Quiz Mode Selector Header */}
      <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
        <button
          onClick={() => setActiveTab("practice")}
          className={activeTab === "practice" ? "btn-primary touch-target" : "btn-secondary touch-target"}
          style={{ fontSize: "var(--text-xs)", flex: "1 1 140px" }}
        >
          {t.quiz.title}
        </button>
        <button
          onClick={() => setActiveTab("assessed_notice")}
          className={activeTab === "assessed_notice" ? "btn-primary touch-target" : "btn-secondary touch-target"}
          style={{ fontSize: "var(--text-xs)", flex: "1 1 140px" }}
        >
          {lang === "bn" ? "মূল্যায়ন কুইজ (অ্যাপ)" : "Assessed Quiz (App Only)"}
        </button>
      </div>

      {/* Assessed Quiz Notice Card */}
      {activeTab === "assessed_notice" && (
        <div
          className="card"
          style={{
            borderLeft: "6px solid var(--color-primary)",
            padding: "var(--space-6)",
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-4)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: "var(--radius-full)",
                backgroundColor: "var(--color-primary-surface)",
                color: "var(--color-primary)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Smartphone size={24} />
            </div>
            <div>
              <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
                {lang === "bn" ? "মূল্যায়ন কুইজ শুধুমাত্র ThinkBuddy অ্যান্ড্রয়েড অ্যাপে সংরক্ষিত" : "Assessed Quizzes are Mobile App Only"}
              </h2>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                {lang === "bn" ? "প্লে ইন্টিগ্রিটি ও সিকিউর ফ্লাগ সুরক্ষিত মূল্যায়ন" : "Play Integrity & FLAG_SECURE Protected"}
              </span>
            </div>
          </div>

          <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.7 }}>
            {lang === "bn"
              ? "নিরাপদ ও নকলমুক্ত পরীক্ষা নিশ্চিত করতে সরকারি সিলেবাসের মূল্যায়ন কুইজ শুধুমাত্র ThinkBuddy অ্যান্ড্রয়েড অ্যাপে সমর্থিত। তবে পাঠ্যবই আয়ত্ত করতে ওয়েবে অনুশীলনী কুইজ যেকোনো সময় বিনামূল্যে চালু রাখা যাবে।"
              : "To prevent unauthorized assistance and uphold strict assessment integrity, assessed quizzes are permitted only inside the ThinkBuddy native Android application. Practice quizzes remain fully accessible on web."}
          </p>
        </div>
      )}

      {/* Practice Quiz Card */}
      {activeTab === "practice" && (
        <div className="card" style={{ padding: "var(--space-6)" }}>
          {!isFinished ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
              {/* Question Header & Citation */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-2)" }}>
                <span
                  style={{
                    backgroundColor: "var(--color-primary-surface)",
                    color: "var(--color-primary)",
                    padding: "4px 12px",
                    borderRadius: "var(--radius-full)",
                    fontSize: "var(--text-xs)",
                    fontWeight: 700,
                  }}
                >
                  {lang === "bn"
                    ? `প্রশ্ন ${toBengaliDigits(currentIndex + 1)} / ${toBengaliDigits(DEMO_QUESTIONS.length)}`
                    : `Question ${currentIndex + 1} of ${DEMO_QUESTIONS.length}`}
                </span>

                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                  <BookOpen size={14} />
                  <span>
                    {lang === "bn" ? `মুদ্রিত পৃষ্ঠা: ${toBengaliDigits(currentQ.textbook_page)}` : `Page: ${currentQ.textbook_page}`}
                  </span>
                </div>
              </div>

              {/* Question Text */}
              <h3 style={{ fontSize: "var(--text-lg)", fontWeight: 700, color: "var(--color-text-main)" }}>
                <MathRenderer content={lang === "bn" ? currentQ.question_bn : currentQ.question_en} />
              </h3>

              {/* Options */}
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                {currentQ.options.map((opt) => {
                  const isSelected = selectedKey === opt.key;
                  let bg = "var(--color-surface)";
                  let border = "1px solid var(--color-border)";

                  if (isAnswered) {
                    if (opt.key === currentQ.correctKey) {
                      bg = "var(--color-success-surface)";
                      border = "1.5px solid var(--color-success)";
                    } else if (isSelected && opt.key !== currentQ.correctKey) {
                      bg = "var(--color-error-surface)";
                      border = "1.5px solid var(--color-error)";
                    }
                  } else if (isSelected) {
                    bg = "var(--color-primary-surface)";
                    border = "1.5px solid var(--color-primary)";
                  }

                  return (
                    <button
                      key={opt.key}
                      onClick={() => handleSelectOption(opt.key)}
                      className="touch-target"
                      style={{
                        padding: "12px 16px",
                        borderRadius: "var(--radius-lg)",
                        backgroundColor: bg,
                        border,
                        textAlign: "left",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        cursor: isAnswered ? "default" : "pointer",
                        transition: "all 0.12s ease",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                        <span
                          style={{
                            width: 28,
                            height: 28,
                            borderRadius: "var(--radius-full)",
                            backgroundColor: isSelected ? "var(--color-primary)" : "var(--color-surface-hover)",
                            color: isSelected ? "#FFFFFF" : "var(--color-text-secondary)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "var(--text-xs)",
                            fontWeight: 700,
                          }}
                        >
                          {opt.key}
                        </span>
                        <span style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>
                          <MathRenderer content={lang === "bn" ? opt.text_bn : opt.text_en} />
                        </span>
                      </div>

                      {isAnswered && opt.key === currentQ.correctKey && (
                        <CheckCircle size={20} style={{ color: "var(--color-success)" }} />
                      )}
                      {isAnswered && isSelected && opt.key !== currentQ.correctKey && (
                        <XCircle size={20} style={{ color: "var(--color-error)" }} />
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Explanation on Answer */}
              {isAnswered && (
                <div
                  style={{
                    backgroundColor: "var(--color-surface-hover)",
                    borderRadius: "var(--radius-md)",
                    padding: "var(--space-4)",
                    fontSize: "var(--text-xs)",
                    lineHeight: 1.6,
                    border: "1px solid var(--color-border)",
                  }}
                >
                  <strong style={{ color: "var(--color-primary)" }}>{t.quiz.explanation}: </strong>
                  <span>{lang === "bn" ? currentQ.explanation_bn : currentQ.explanation_en}</span>
                </div>
              )}

              {/* Action Buttons */}
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-3)", marginTop: "var(--space-2)" }}>
                {!isAnswered ? (
                  <button
                    onClick={handleCheckAnswer}
                    disabled={!selectedKey}
                    className="btn-primary touch-target"
                    style={{
                      opacity: selectedKey ? 1 : 0.6,
                      cursor: selectedKey ? "pointer" : "not-allowed",
                      fontSize: "var(--text-sm)",
                    }}
                  >
                    {t.quiz.checkAnswer}
                  </button>
                ) : (
                  <button
                    onClick={handleNext}
                    className="btn-primary touch-target"
                    style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-sm)" }}
                  >
                    <span>{currentIndex + 1 < DEMO_QUESTIONS.length ? t.quiz.nextQuestion : t.quiz.finish}</span>
                    <ArrowRight size={16} />
                  </button>
                )}
              </div>
            </div>
          ) : (
            /* Finished Results Screen */
            <div style={{ textAlign: "center", padding: "var(--space-6)", display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-4)" }}>
              <div
                style={{
                  width: 64,
                  height: 64,
                  borderRadius: "var(--radius-full)",
                  backgroundColor: "var(--color-success-surface)",
                  color: "var(--color-success)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <CheckCircle size={36} />
              </div>

              <h2 style={{ fontSize: "var(--text-2xl)", fontWeight: 800 }}>
                {lang === "bn" ? "অনুশীলন সফলভাবে সমাপ্ত!" : "Practice Completed!"}
              </h2>

              <p style={{ fontSize: "var(--text-base)", color: "var(--color-text-secondary)" }}>
                {t.session.yourScore}:{" "}
                <strong style={{ color: "var(--color-primary)" }}>
                  {lang === "bn" ? toBengaliDigits(score) : score} / {lang === "bn" ? toBengaliDigits(DEMO_QUESTIONS.length) : DEMO_QUESTIONS.length}
                </strong>
              </p>

              <button
                onClick={handleRestart}
                className="btn-primary touch-target"
                style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-sm)", marginTop: "var(--space-2)" }}
              >
                <RotateCcw size={16} />
                <span>{t.quiz.tryAgain}</span>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

