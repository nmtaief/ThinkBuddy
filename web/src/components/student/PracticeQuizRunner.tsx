"use client";

import React, { useState } from "react";
import { QuizAttempt, QuizReviewItem, ClientConfig } from "@/lib/types";
import { Language, translations, toBengaliDigits } from "@/lib/i18n";
import { apiClient } from "@/lib/api-client";
import { MathRenderer } from "@/components/MathRenderer";
import { AlertCircle, CheckCircle, XCircle, ArrowRight, Smartphone, BookOpen } from "lucide-react";

interface PracticeQuizRunnerProps {
  lang: Language;
  config?: ClientConfig;
}

export const PracticeQuizRunner: React.FC<PracticeQuizRunnerProps> = ({ lang, config }) => {
  const t = translations[lang];

  const [activeTab, setActiveTab] = useState<"practice" | "assessed_notice">("practice");
  const [attempt, setAttempt] = useState<QuizAttempt | null>(null);
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ isCorrect: boolean } | null>(null);
  const [review, setReview] = useState<QuizReviewItem[] | null>(null);
  const [loading, setLoading] = useState(false);

  const startQuiz = async () => {
    setLoading(true);
    try {
      const att = await apiClient.startPracticeQuiz("quiz_practice_demo");
      setAttempt(att);
      setFeedback(null);
      setSelectedOption(null);
      setReview(null);
    } finally {
      setLoading(false);
    }
  };

  const handleAnswer = async () => {
    if (!attempt || !selectedOption) return;
    setLoading(true);
    try {
      const res = await apiClient.answerQuizItem(
        attempt.attempt_id,
        attempt.current_item.position,
        attempt.current_item.item_nonce,
        selectedOption
      );

      setFeedback({ isCorrect: !!res.is_correct });

      if (!res.has_more) {
        // Finalize attempt
        await apiClient.submitQuizAttempt(attempt.attempt_id);
        const reviewItems = await apiClient.getQuizReview(attempt.attempt_id);
        setReview(reviewItems);
        setAttempt(null);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      {/* Quiz Mode Selector Header */}
      <div style={{ display: "flex", gap: "var(--space-3)" }}>
        <button
          onClick={() => setActiveTab("practice")}
          className={activeTab === "practice" ? "btn-primary touch-target" : "btn-secondary touch-target"}
        >
          {t.student.practiceQuizTitle}
        </button>
        <button
          onClick={() => setActiveTab("assessed_notice")}
          className={activeTab === "assessed_notice" ? "btn-primary touch-target" : "btn-secondary touch-target"}
        >
          {t.student.assessedQuizBlockedTitle}
        </button>
      </div>

      {/* Assessed Quiz Blocking Card */}
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
              <h3 style={{ fontSize: "var(--text-lg)", fontWeight: 700 }}>
                {(lang === "bn" ? config?.assessed_quiz_banner?.title_bn : config?.assessed_quiz_banner?.title_en) ||
                  t.student.assessedQuizBlockedTitle}
              </h3>
              <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
                {(lang === "bn" ? config?.assessed_quiz_banner?.body_bn : config?.assessed_quiz_banner?.body_en) ||
                  "ThinkBuddy অ্যান্ড্রয়েড অ্যাপ শীঘ্রই আসছে। অ্যাপ প্রকাশ না হওয়া পর্যন্ত মূল্যায়ন কুইজ সাময়িকভাবে স্থগিত।"}
              </p>
            </div>
          </div>

          <div
            style={{
              backgroundColor: "var(--color-surface-hover)",
              padding: "var(--space-4)",
              borderRadius: "var(--radius-md)",
              fontSize: "var(--text-sm)",
              lineHeight: 1.6,
            }}
          >
            🛡️ <strong>সিকিউর কুইজ স্ট্যান্ডার্ড (05_SECURE_QUIZ.md):</strong> ব্রাউজারে স্ক্রিনশট ও ক্লিপবোর্ড
            সুরক্ষা নির্ভরযোগ্যভাবে নিশ্চিত করা সম্ভব নয় বলে ওয়েব ভার্সনে শুধুমাত্র প্র্যাকটিস কুইজ অনুমোদিত।
            মূল্যায়ন কুইজ শুরু করতে আপনার অ্যান্ড্রয়েড ডিভাইসে ThinkBuddy অ্যাপ ব্যবহার করুন।
          </div>

          <div>
            <a
              href="https://play.google.com/store/apps/details?id=arc.thinkbuddy.student"
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary touch-target"
              style={{ display: "inline-flex", gap: "var(--space-2)" }}
            >
              <Smartphone size={18} />
              <span>{t.student.downloadApp}</span>
            </a>
          </div>
        </div>
      )}

      {/* Practice Quiz Flow */}
      {activeTab === "practice" && (
        <div>
          {!attempt && !review && (
            <div className="card" style={{ textAlign: "center", padding: "var(--space-8)" }}>
              <h3 style={{ fontSize: "var(--text-xl)", fontWeight: 700, marginBottom: "var(--space-2)" }}>
                {t.student.practiceQuizTitle}
              </h3>
              <p
                style={{
                  color: "var(--color-text-secondary)",
                  marginBottom: "var(--space-5)",
                  maxWidth: 540,
                  margin: "0 auto var(--space-5)",
                }}
              >
                {t.student.practiceQuizNotice}
              </p>
              <button onClick={startQuiz} disabled={loading} className="btn-primary touch-target">
                {loading ? "শুরু হচ্ছে..." : "অনুশীলন শুরু করুন"}
              </button>
            </div>
          )}

          {/* Active Question Item */}
          {attempt && (
            <div className="card" style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="badge badge-success">
                  প্রশ্ন {lang === "bn" ? toBengaliDigits(attempt.current_item.position) : attempt.current_item.position}
                </span>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                  অনুশীলনী মোড
                </span>
              </div>

              <div style={{ fontSize: "var(--text-lg)", fontWeight: 600 }}>
                <MathRenderer content={attempt.current_item.question_text} />
              </div>

              {/* Options */}
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                {attempt.current_item.options.map((opt) => {
                  const isSelected = selectedOption === opt.id;
                  return (
                    <button
                      key={opt.id}
                      onClick={() => setSelectedOption(opt.id)}
                      className="touch-target"
                      style={{
                        padding: "var(--space-3) var(--space-4)",
                        borderRadius: "var(--radius-md)",
                        border: isSelected ? "2px solid var(--color-primary)" : "1px solid var(--color-border)",
                        backgroundColor: isSelected ? "var(--color-primary-surface)" : "var(--color-surface)",
                        textAlign: "left",
                        justifyContent: "flex-start",
                        fontWeight: isSelected ? 600 : 400,
                      }}
                    >
                      <MathRenderer content={opt.text} />
                    </button>
                  );
                })}
              </div>

              {/* Immediate Feedback in Practice Mode */}
              {feedback && (
                <div
                  style={{
                    padding: "var(--space-3)",
                    borderRadius: "var(--radius-md)",
                    backgroundColor: feedback.isCorrect
                      ? "var(--color-success-surface)"
                      : "var(--color-danger-surface)",
                    color: feedback.isCorrect ? "var(--color-success)" : "var(--color-danger)",
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-2)",
                  }}
                >
                  {feedback.isCorrect ? <CheckCircle size={20} /> : <XCircle size={20} />}
                  <span>{feedback.isCorrect ? "সঠিক উত্তর!" : "পুনরায় চেষ্টা করুন।"}</span>
                </div>
              )}

              {/* Submit / Next Button */}
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <button
                  onClick={handleAnswer}
                  disabled={!selectedOption || loading}
                  className="btn-primary touch-target"
                  style={{ display: "inline-flex", gap: "var(--space-2)" }}
                >
                  <span>{loading ? "যাচাই হচ্ছে..." : "উত্তর জমা দিন"}</span>
                  <ArrowRight size={18} />
                </button>
              </div>
            </div>
          )}

          {/* Review Summary */}
          {review && (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
              <div
                className="card"
                style={{
                  backgroundColor: "var(--color-success-surface)",
                  border: "1px solid var(--color-success)",
                  textAlign: "center",
                  padding: "var(--space-6)",
                }}
              >
                <CheckCircle size={40} style={{ color: "var(--color-success)", margin: "0 auto" }} />
                <h3 style={{ fontSize: "var(--text-xl)", fontWeight: 700, marginTop: "var(--space-2)" }}>
                  অনুশীলনী কুইজ সমাপ্ত!
                </h3>
                <p style={{ color: "var(--color-text-secondary)" }}>
                  নিচে আপনার প্রতিটি প্রশ্নের উত্তর ও ব্যাখ্যা পর্যালোচনা করুন।
                </p>
              </div>

              {review.map((item) => (
                <div key={item.position} className="card" style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span className="badge badge-success">
                      প্রশ্ন {lang === "bn" ? toBengaliDigits(item.position) : item.position}
                    </span>
                    <span className={item.is_correct ? "badge badge-success" : "badge badge-danger"}>
                      {item.is_correct ? "সঠিক" : "ভুল"}
                    </span>
                  </div>

                  <div style={{ fontWeight: 600 }}>
                    <MathRenderer content={item.question_text} />
                  </div>

                  {item.explanation && (
                    <div
                      style={{
                        backgroundColor: "var(--color-surface-hover)",
                        padding: "var(--space-3)",
                        borderRadius: "var(--radius-md)",
                        fontSize: "var(--text-sm)",
                        color: "var(--color-text-secondary)",
                      }}
                    >
                      💡 <strong>ব্যাখ্যা:</strong> <MathRenderer content={item.explanation} />
                    </div>
                  )}
                </div>
              ))}

              <button onClick={() => setReview(null)} className="btn-secondary touch-target">
                নতুন কুইজ নিন
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
