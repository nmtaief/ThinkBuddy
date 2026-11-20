"use client";

import React, { useState } from "react";
import { QuizAttempt, QuizReviewItem, ClientConfig } from "@/lib/types";
import { Language, translations, toBengaliDigits } from "@/lib/i18n";
import { apiClient } from "@/lib/api-client";
import { MathRenderer } from "@/components/MathRenderer";
import { getCQQuestions, evaluateCQAnswer, CQQuestionItem, CQEvaluationResult } from "@/lib/cq-topic-mapping";
import { AlertCircle, CheckCircle, XCircle, ArrowRight, Smartphone, BookOpen, Sparkles, Check, HelpCircle } from "lucide-react";

interface PracticeQuizRunnerProps {
  lang: Language;
  config?: ClientConfig;
}

export const PracticeQuizRunner: React.FC<PracticeQuizRunnerProps> = ({ lang, config }) => {
  const t = translations[lang];

  const [activeTab, setActiveTab] = useState<"practice" | "cq_exam" | "assessed_notice">("practice");
  const [attempt, setAttempt] = useState<QuizAttempt | null>(null);
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ isCorrect: boolean } | null>(null);
  const [review, setReview] = useState<QuizReviewItem[] | null>(null);
  const [loading, setLoading] = useState(false);

  // CQ Exam Module State
  const [cqSubjectFilter, setCqSubjectFilter] = useState<string>("all");
  const [cqTypeFilter, setCqTypeFilter] = useState<string>("all");
  const [cqAnswers, setCqAnswers] = useState<Record<string, string>>({});
  const [cqEvaluations, setCqEvaluations] = useState<Record<string, CQEvaluationResult>>({});
  const [evaluatingCqId, setEvaluatingCqId] = useState<string | null>(null);

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

  const handleEvaluateCq = (question: CQQuestionItem) => {
    const studentAnswer = cqAnswers[question.id] || "";
    if (!studentAnswer.trim()) return;
    setEvaluatingCqId(question.id);
    setTimeout(() => {
      const res = evaluateCQAnswer(question, studentAnswer);
      setCqEvaluations((prev) => ({ ...prev, [question.id]: res }));
      setEvaluatingCqId(null);
    }, 400);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      {/* Quiz Mode Selector Header */}
      <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap" }}>
        <button
          onClick={() => setActiveTab("practice")}
          className={activeTab === "practice" ? "btn-primary touch-target" : "btn-secondary touch-target"}
        >
          {t.student.practiceQuizTitle}
        </button>
        <button
          onClick={() => setActiveTab("cq_exam")}
          className={activeTab === "cq_exam" ? "btn-primary touch-target" : "btn-secondary touch-target"}
          style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
        >
          <BookOpen size={16} />
          <span>{lang === "bn" ? "সৃজনশীল ক ও খ পরীক্ষা (AI Evaluated)" : "CQ Knowledge (ক) & Comprehension (খ)"}</span>
        </button>
        <button
          onClick={() => setActiveTab("assessed_notice")}
          className={activeTab === "assessed_notice" ? "btn-primary touch-target" : "btn-secondary touch-target"}
        >
          {t.student.assessedQuizBlockedTitle}
        </button>
      </div>

      {/* CQ Exam Flow with Topic Tagging & Short Answer Evaluation */}
      {activeTab === "cq_exam" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          {/* Header & Topic Filter Controls */}
          <div className="card" style={{ padding: "var(--space-5)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <span className="badge badge-success">
                    {lang === "bn" ? "সৃজনশীল টপিক ম্যাপিং ইঞ্জিন" : "NCTB CQ Topic Mapping"}
                  </span>
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                    ক (১ নম্বর) ও খ (২ নম্বর)
                  </span>
                </div>
                <h3 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
                  {lang === "bn" ? "জ্ঞান ও অনুধাবনমূলক সংক্ষিপ্ত উত্তর পরীক্ষা" : "Knowledge & Comprehension Short Answer Exam"}
                </h3>
                <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", marginTop: 4 }}>
                  {lang === "bn"
                    ? "প্রতিটি প্রশ্নের সাথে পাঠ্যবইয়ের অধ্যায় ও সুনির্দিষ্ট সাব-টপিক ট্যাগ সংযুক্ত। আপনার উত্তর লিখুন এবং এআই রুব্রিকের মাধ্যমে তাৎক্ষণিক নম্বর যাচাই করুন।"
                    : "Topic-tagged questions with direct NCTB syllabus mapping and criteria-based AI short-answer grading."}
                </p>
              </div>

              {/* Filters */}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                <select
                  value={cqSubjectFilter}
                  onChange={(e) => setCqSubjectFilter(e.target.value)}
                  style={{
                    padding: "6px 12px",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--color-border)",
                    backgroundColor: "var(--color-surface)",
                    fontSize: "var(--text-xs)",
                    fontWeight: 600,
                  }}
                >
                  <option value="all">{lang === "bn" ? "সকল বিষয় (All Subjects)" : "All Subjects"}</option>
                  <option value="সাধারণ বিজ্ঞান">সাধারণ বিজ্ঞান (Science)</option>
                  <option value="সাধারণ গণিত">সাধারণ গণিত (Math)</option>
                  <option value="তথ্য ও যোগাযোগ প্রযুক্তি">তথ্য ও যোগাযোগ প্রযুক্তি (ICT)</option>
                  <option value="বাংলা">বাংলা (Bangla)</option>
                  <option value="বাংলাদেশ ও বিশ্বপরিচয়">বাংলাদেশ ও বিশ্বপরিচয় (BGS)</option>
                </select>

                <select
                  value={cqTypeFilter}
                  onChange={(e) => setCqTypeFilter(e.target.value)}
                  style={{
                    padding: "6px 12px",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--color-border)",
                    backgroundColor: "var(--color-surface)",
                    fontSize: "var(--text-xs)",
                    fontWeight: 600,
                  }}
                >
                  <option value="all">{lang === "bn" ? "সব ধরনের প্রশ্ন" : "All Types"}</option>
                  <option value="ka_knowledge">{lang === "bn" ? "জ্ঞানমূলক (ক) • ১ নম্বর" : "Knowledge (ক) • 1m"}</option>
                  <option value="kha_comprehension">{lang === "bn" ? "অনুধাবনমূলক (খ) • ২ নম্বর" : "Comprehension (খ) • 2m"}</option>
                </select>
              </div>
            </div>
          </div>

          {/* Questions List */}
          {(() => {
            const questions = getCQQuestions({
              subject: cqSubjectFilter !== "all" ? cqSubjectFilter : undefined,
              type: cqTypeFilter !== "all" ? (cqTypeFilter as any) : undefined,
            });

            if (questions.length === 0) {
              return (
                <div className="card" style={{ textAlign: "center", padding: "var(--space-8)" }}>
                  <p style={{ color: "var(--color-text-muted)" }}>
                    {lang === "bn" ? "নির্বাচিত ফিল্টারে কোনো প্রশ্ন পাওয়া যায়নি।" : "No questions found for the selected filter."}
                  </p>
                </div>
              );
            }

            return questions.map((q, idx) => {
              const evalRes = cqEvaluations[q.id];
              const isEvaluating = evaluatingCqId === q.id;
              const ans = cqAnswers[q.id] || "";

              return (
                <div key={q.id} className="card" style={{ display: "flex", flexDirection: "column", gap: 12, padding: "var(--space-5)" }}>
                  {/* Inline Topic Tagging Header */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      <span
                        className="badge"
                        style={{
                          backgroundColor: q.type === "ka_knowledge" ? "#e0e7ff" : "#dbeafe",
                          color: q.type === "ka_knowledge" ? "#3730a3" : "#1e40af",
                          fontWeight: 700,
                          fontSize: "11px",
                        }}
                      >
                        {q.type_label_bn} • {lang === "bn" ? toBengaliDigits(q.marks) : q.marks} {lang === "bn" ? "নম্বর" : "mark"}
                      </span>
                      <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--color-primary)" }}>
                        {q.subject} ⟶ অধ্যায় {toBengaliDigits(q.chapter_number)}
                      </span>
                      <span style={{ fontSize: "11px", color: "var(--color-text-secondary)", backgroundColor: "var(--color-surface-hover)", padding: "2px 8px", borderRadius: 4 }}>
                        টপিক: {q.subtopic_tag}
                      </span>
                    </div>

                    <span style={{ fontSize: "11px", color: "var(--color-text-muted)" }}>
                      পাঠ্যবই পৃষ্ঠা: {lang === "bn" ? toBengaliDigits(q.printed_page) : q.printed_page}
                    </span>
                  </div>

                  {/* Question Text */}
                  <div style={{ fontSize: "var(--text-md)", fontWeight: 700, color: "var(--color-text)" }}>
                    {idx + 1}. {q.question_bn}
                  </div>

                  {/* Student Answer Textarea */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <textarea
                      value={ans}
                      onChange={(e) => setCqAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                      placeholder={lang === "bn" ? "খাতায় উত্তর যেভাবে লেখো, সেভাবে সংক্ষেপে তোমার উত্তরটি এখানে টাইপ করো..." : "Write your concise short answer here..."}
                      rows={3}
                      style={{
                        width: "100%",
                        padding: "10px 14px",
                        borderRadius: "var(--radius-md)",
                        border: "1px solid var(--color-border)",
                        backgroundColor: "var(--color-surface)",
                        fontSize: "var(--text-sm)",
                        lineHeight: 1.5,
                        resize: "vertical",
                      }}
                    />
                  </div>

                  {/* Evaluation Button */}
                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
                    <button
                      onClick={() => handleEvaluateCq(q)}
                      disabled={!ans.trim() || isEvaluating}
                      className="btn-primary touch-target"
                      style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "12px", padding: "8px 16px" }}
                    >
                      <Sparkles size={16} />
                      <span>{isEvaluating ? "মূল্যায়ন হচ্ছে..." : "এআই মূল্যায়ন ও নম্বর যাচাই"}</span>
                    </button>
                  </div>

                  {/* Immediate AI Feedback & Criteria Breakdown */}
                  {evalRes && (
                    <div
                      style={{
                        padding: "var(--space-4)",
                        borderRadius: "var(--radius-md)",
                        backgroundColor: evalRes.is_full_marks ? "var(--color-success-surface)" : "var(--color-surface-hover)",
                        border: `1px solid ${evalRes.is_full_marks ? "var(--color-success)" : "var(--color-border)"}`,
                        display: "flex",
                        flexDirection: "column",
                        gap: 10,
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          {evalRes.is_full_marks ? <CheckCircle size={20} color="var(--color-success)" /> : <AlertCircle size={20} color="#d97706" />}
                          <span style={{ fontWeight: 700, fontSize: "var(--text-sm)" }}>
                            প্রাপ্ত নম্বর: {toBengaliDigits(evalRes.score)} / {toBengaliDigits(evalRes.max_marks)}
                          </span>
                        </div>
                        <span style={{ fontSize: "11px", fontWeight: 600, color: evalRes.is_full_marks ? "var(--color-success)" : "#d97706" }}>
                          {evalRes.is_full_marks ? "✓ পূর্ণ নম্বর অর্জিত" : "আংশিক মূল্যায়ন"}
                        </span>
                      </div>

                      <p style={{ fontSize: "var(--text-xs)", margin: 0, lineHeight: 1.6, color: "var(--color-text)" }}>
                        {evalRes.feedback_bn}
                      </p>

                      {/* Rubric Points */}
                      <div style={{ fontSize: "11px", display: "flex", flexDirection: "column", gap: 4 }}>
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                          <span style={{ fontWeight: 600, color: "var(--color-text-secondary)" }}>শনাক্তকৃত কী-ওয়ার্ড:</span>
                          {evalRes.matched_keywords.length > 0 ? (
                            evalRes.matched_keywords.map((k, i) => (
                              <span key={i} style={{ backgroundColor: "#dcfce7", color: "#166534", padding: "1px 6px", borderRadius: 4, fontWeight: 600 }}>
                                ✓ {k}
                              </span>
                            ))
                          ) : (
                            <span style={{ color: "var(--color-text-muted)" }}>কোনোটি মেলেনি</span>
                          )}
                        </div>

                        {evalRes.missing_keywords.length > 0 && (
                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                            <span style={{ fontWeight: 600, color: "#b45309" }}>অনুপস্থিত বা আবশ্যক পয়েন্ট:</span>
                            {evalRes.missing_keywords.map((k, i) => (
                              <span key={i} style={{ backgroundColor: "#fef3c7", color: "#92400e", padding: "1px 6px", borderRadius: 4 }}>
                                ⚠️ {k}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Model Answer Drawer */}
                      <div style={{ backgroundColor: "var(--color-surface)", padding: 10, borderRadius: 6, border: "1px solid var(--color-border)", fontSize: "11px", lineHeight: 1.6 }}>
                        <strong style={{ color: "var(--color-primary)" }}>পাঠ্যবই আদর্শ উত্তর (পৃষ্ঠা {toBengaliDigits(evalRes.textbook_page)}):</strong>
                        <div style={{ marginTop: 4, color: "var(--color-text)" }}>{evalRes.model_answer}</div>
                      </div>
                    </div>
                  )}
                </div>
              );
            });
          })()}
        </div>
      )}

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
