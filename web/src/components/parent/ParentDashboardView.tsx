"use client";

import React, { useState, useEffect } from "react";
import { ChildSummary, UploadedStudyNote } from "@/lib/types";
import { Language, translations, toBengaliDigits } from "@/lib/i18n";
import { Religion, getReligionConfig } from "@/lib/religion";
import { apiClient } from "@/lib/api-client";
import {
  Users,
  Flame,
  Clock,
  CheckCircle,
  BarChart3,
  BookOpen,
  FileText,
  UserCheck,
  Star,
  Send,
  Sparkles,
  ShieldCheck,
  Check,
} from "lucide-react";

interface ParentDashboardViewProps {
  childrenList: ChildSummary[];
  activeChildId: string;
  onSelectChild: (id: string) => void;
  lang: Language;
  religion?: Religion;
}

export const ParentDashboardView: React.FC<ParentDashboardViewProps> = ({
  childrenList,
  activeChildId,
  onSelectChild,
  lang,
  religion = "islam",
}) => {
  const t = translations[lang];
  const relConfig = getReligionConfig(religion);

  const activeChild = childrenList.find((c) => c.student_id === activeChildId) || childrenList[0];

  // Study notes and teacher reviews state
  const [studyNotes, setStudyNotes] = useState<UploadedStudyNote[]>([]);
  const [feedbackInputs, setFeedbackInputs] = useState<Record<string, string>>({});
  const [savedFeedbackIds, setSavedFeedbackIds] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (activeChild) {
      apiClient.getUploadedNotes(activeChild.student_id).then((notes) => {
        setStudyNotes(notes);
      });
    }
  }, [activeChild?.student_id]);

  const handleFeedbackChange = (noteId: string, text: string) => {
    setFeedbackInputs((prev) => ({ ...prev, [noteId]: text }));
  };

  const handleSaveFeedback = async (noteId: string) => {
    const feedback = feedbackInputs[noteId];
    if (!feedback || !activeChild) return;

    await apiClient.addParentFeedback(activeChild.student_id, noteId, feedback);
    setSavedFeedbackIds((prev) => ({ ...prev, [noteId]: true }));
    setStudyNotes((prev) =>
      prev.map((n) => (n.id === noteId ? { ...n, parent_feedback: feedback } : n))
    );
    setTimeout(() => {
      setSavedFeedbackIds((prev) => ({ ...prev, [noteId]: false }));
    }, 3000);
  };

  if (!activeChild) {
    return (
      <div className="card" style={{ padding: "var(--space-8)", textAlign: "center" }}>
        <p>{lang === "bn" ? "কোনো সন্তান প্রোফাইল যুক্ত করা হয়নি।" : "No children profiles linked yet."}</p>
      </div>
    );
  }

  const streakDisplay = lang === "bn" ? toBengaliDigits(activeChild.streak_days) : activeChild.streak_days;
  const minutesDisplay =
    lang === "bn" ? toBengaliDigits(activeChild.today_minutes_spent) : activeChild.today_minutes_spent;
  const completionDisplay =
    lang === "bn" ? toBengaliDigits(activeChild.completion_rate) : activeChild.completion_rate;
  const masteryDisplay =
    lang === "bn" ? toBengaliDigits(activeChild.mastery_percentage) : activeChild.mastery_percentage;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      {/* Top Blessing Banner */}
      <div
        className="card"
        style={{
          background: "linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(16, 185, 129, 0.10) 100%)",
          border: "1px solid var(--color-border)",
          padding: "var(--space-5) var(--space-6)",
          borderRadius: "var(--radius-xl)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "var(--space-4)",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
            <Sparkles size={16} style={{ color: "var(--color-primary)" }} />
            <span style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-primary)" }}>
              {relConfig.greetings.greetingHeader}
            </span>
          </div>
          <h2 style={{ fontSize: "var(--text-xl)", fontWeight: 800, margin: "2px 0 6px 0" }}>
            {lang === "bn" ? `${activeChild.name}-এর অধ্যয়ন ড্যাশবোর্ড` : `${activeChild.name}'s Learning Dashboard`}
          </h2>
          <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", margin: 0, maxWidth: 650, lineHeight: 1.6 }}>
            {relConfig.greetings.parentNoteBlessing}
          </p>
        </div>

        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <span
            className="badge"
            style={{
              backgroundColor: "var(--color-primary-surface)",
              color: "var(--color-primary)",
              display: "flex",
              alignItems: "center",
              gap: 5,
              fontSize: "var(--text-xs)",
              fontWeight: 700,
            }}
          >
            <span>{relConfig.icon}</span>
            <span>{relConfig.name_bn}</span>
          </span>

          <span
            className="badge"
            style={{
              backgroundColor: "rgba(16, 185, 129, 0.12)",
              color: "var(--color-success)",
              display: "flex",
              alignItems: "center",
              gap: 5,
              fontSize: "var(--text-xs)",
              fontWeight: 700,
            }}
          >
            <ShieldCheck size={14} />
            <span>ThinkBuddy Pro Verified</span>
          </span>
        </div>
      </div>

      {/* Children Selector */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flexWrap: "wrap" }}>
        <span style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--color-text-secondary)" }}>
          {t.nav.children}:
        </span>
        {childrenList.map((child) => {
          const isActive = child.student_id === activeChild.student_id;
          return (
            <button
              key={child.student_id}
              onClick={() => onSelectChild(child.student_id)}
              className={isActive ? "btn-primary touch-target" : "btn-secondary touch-target"}
              style={{ fontSize: "var(--text-sm)" }}
            >
              <Users size={16} style={{ marginRight: 6 }} />
              <span>
                {child.name} ({lang === "bn" ? `${toBengaliDigits(child.class_level)}ম শ্রেণি` : `Class ${child.class_level}`})
              </span>
            </button>
          );
        })}
      </div>

      {/* Metrics Cards Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: "var(--space-4)",
        }}
      >
        {/* Streak */}
        <div className="card" style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
          <div
            style={{
              width: 50,
              height: 50,
              borderRadius: "var(--radius-full)",
              backgroundColor: "var(--color-warning-surface)",
              color: "var(--color-warning)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Flame size={26} />
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

        {/* Minutes Today */}
        <div className="card" style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
          <div
            style={{
              width: 50,
              height: 50,
              borderRadius: "var(--radius-full)",
              backgroundColor: "var(--color-primary-surface)",
              color: "var(--color-primary)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Clock size={26} />
          </div>
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
              {t.growthMindset.timeSpent}
            </div>
            <div style={{ fontSize: "var(--text-2xl)", fontWeight: 700 }}>
              {minutesDisplay} {t.growthMindset.minutes}
            </div>
          </div>
        </div>

        {/* Completion Rate */}
        <div className="card" style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
          <div
            style={{
              width: 50,
              height: 50,
              borderRadius: "var(--radius-full)",
              backgroundColor: "var(--color-success-surface)",
              color: "var(--color-success)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <CheckCircle size={26} />
          </div>
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
              {lang === "bn" ? "আজকের কাজ সমাপ্তি" : "Today's Task Completion"}
            </div>
            <div style={{ fontSize: "var(--text-2xl)", fontWeight: 700 }}>{completionDisplay}%</div>
          </div>
        </div>

        {/* Mastery */}
        <div className="card" style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
          <div
            style={{
              width: 50,
              height: 50,
              borderRadius: "var(--radius-full)",
              backgroundColor: "var(--color-secondary-surface)",
              color: "var(--color-secondary)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <BarChart3 size={26} />
          </div>
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
              {lang === "bn" ? "সামগ্রিক বিষয় দক্ষতা" : "Overall Mastery"}
            </div>
            <div style={{ fontSize: "var(--text-2xl)", fontWeight: 700 }}>{masteryDisplay}%</div>
          </div>
        </div>
      </div>

      {/* SECTION: Student Study Notes & Teacher Reviews (Pro) */}
      <div className="card" style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)", padding: "var(--space-6)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-3)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <FileText size={22} style={{ color: "var(--color-primary)" }} />
            <div>
              <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
                {lang === "bn"
                  ? `${activeChild.name}-এর পড়ার নোট ও খাতার মূল্যায়ন (Pro)`
                  : `${activeChild.name}'s Exercise Book Notes & Teacher Review`}
              </h2>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                {lang === "bn"
                  ? "শিক্ষার্থীর পড়া, হস্তাক্ষর ও শিক্ষকের প্রফেশনাল মূল্যায়ন সরাসরি অভিভাবকের নজরে"
                  : "View student notebook uploads and ThinkBuddy mentor feedback"}
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
            <Star size={13} />
            <span>ThinkBuddy Certified Teacher Reviews</span>
          </span>
        </div>

        {studyNotes.length === 0 ? (
          <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", margin: 0 }}>
            {lang === "bn"
              ? "শিক্ষার্থী এখনও কোনো খাতার পাতার ছবি আপলোড করেনি।"
              : "No study notes or notebook pages uploaded yet."}
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
            {studyNotes.map((note) => (
              <div
                key={note.id}
                style={{
                  border: "1.5px solid var(--color-border)",
                  borderRadius: "var(--radius-xl)",
                  padding: "var(--space-5)",
                  backgroundColor: "var(--color-surface)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "var(--space-4)",
                }}
              >
                {/* Note Header */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-2)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                    <span
                      className="badge"
                      style={{
                        backgroundColor: "var(--color-primary-surface)",
                        color: "var(--color-primary)",
                        fontWeight: 700,
                        fontSize: "var(--text-xs)",
                      }}
                    >
                      {note.subject}
                    </span>
                    <h3 style={{ fontSize: "var(--text-base)", fontWeight: 700, margin: 0 }}>
                      {note.task_title}
                    </h3>
                  </div>

                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
                    {lang === "bn"
                      ? `পাঠ্যবই: ${toBengaliDigits(note.pages_covered)} • অধ্যয়ন সময়: ${toBengaliDigits(Math.floor(note.time_spent_seconds / 60))} মিনিট`
                      : `Pages: ${note.pages_covered} • Time: ${Math.floor(note.time_spent_seconds / 60)}m`}
                  </span>
                </div>

                {/* Text Note */}
                {note.text_note && (
                  <div
                    style={{
                      padding: "var(--space-3) var(--space-4)",
                      borderRadius: "var(--radius-md)",
                      backgroundColor: "var(--color-bg)",
                      border: "1px solid var(--color-border)",
                      fontSize: "var(--text-sm)",
                      lineHeight: 1.7,
                      whiteSpace: "pre-line",
                    }}
                  >
                    {note.text_note}
                  </div>
                )}

                {/* Uploaded Handwritten Note Image Preview */}
                {note.image_url && (
                  <div style={{ borderRadius: "var(--radius-md)", overflow: "hidden", border: "1px solid var(--color-border)" }}>
                    <img
                      src={note.image_url}
                      alt="Student Notebook Page"
                      style={{ width: "100%", maxHeight: 250, objectFit: "cover", display: "block" }}
                    />
                  </div>
                )}

                {/* Pro Certified Teacher Review */}
                {note.teacher_review && (
                  <div
                    style={{
                      padding: "var(--space-4)",
                      borderRadius: "var(--radius-lg)",
                      backgroundColor: "rgba(37, 99, 235, 0.04)",
                      border: "1px solid rgba(37, 99, 235, 0.2)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-2)", flexWrap: "wrap", gap: "var(--space-2)" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <UserCheck size={18} style={{ color: "var(--color-primary)" }} />
                        <span style={{ fontSize: "var(--text-sm)", fontWeight: 800, color: "var(--color-primary)" }}>
                          {note.teacher_review.teacher_name}
                        </span>
                        <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                          ({note.teacher_review.badge})
                        </span>
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
                      <strong>{lang === "bn" ? "শিক্ষকের বিশ্লেষণ: " : "Teacher's Feedback: "}</strong>
                      {note.teacher_review.comments}
                    </p>
                  </div>
                )}

                {/* Parent Feedback Section */}
                <div
                  style={{
                    padding: "var(--space-3) var(--space-4)",
                    borderRadius: "var(--radius-md)",
                    backgroundColor: "rgba(16, 185, 129, 0.05)",
                    border: "1px solid rgba(16, 185, 129, 0.2)",
                  }}
                >
                  <div style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-success)", marginBottom: "var(--space-2)" }}>
                    {lang === "bn" ? "অভিভাবকের মন্তব্য ও দোয়া:" : "Parent's Encouragement & Blessing:"}
                  </div>

                  {note.parent_feedback && (
                    <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text)", fontWeight: 600, marginBottom: "var(--space-2)" }}>
                      "{note.parent_feedback}"
                    </div>
                  )}

                  <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
                    <input
                      type="text"
                      placeholder={
                        lang === "bn"
                          ? "সন্তানের জন্য উৎসাহমূলক মন্তব্য বা দোয়া লিখুন (যেমন: মাশাআল্লাহ আব্বু/আম্মু...)"
                          : "Write encouraging remarks or blessings..."
                      }
                      value={feedbackInputs[note.id] ?? ""}
                      onChange={(e) => handleFeedbackChange(note.id, e.target.value)}
                      style={{
                        flex: 1,
                        padding: "8px 12px",
                        fontSize: "var(--text-xs)",
                        borderRadius: "var(--radius-md)",
                        border: "1px solid var(--color-border)",
                        backgroundColor: "var(--color-bg)",
                        color: "var(--color-text)",
                      }}
                    />
                    <button
                      onClick={() => handleSaveFeedback(note.id)}
                      className="btn-primary touch-target"
                      style={{
                        padding: "8px 14px",
                        fontSize: "var(--text-xs)",
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                      }}
                    >
                      {savedFeedbackIds[note.id] ? <Check size={14} /> : <Send size={14} />}
                      <span>{savedFeedbackIds[note.id] ? (lang === "bn" ? "সংরক্ষিত" : "Saved") : (lang === "bn" ? "পাঠান" : "Send")}</span>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Review Quiz Results Section */}
      <div className="card" style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
          {lang === "bn" ? "সাম্প্রতিক শিখন মূল্যায়ন ও পর্যালোচনা কুইজ" : "Recent Mastery & Assessment Quizzes"}
        </h2>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            backgroundColor: "var(--color-surface-hover)",
            padding: "var(--space-3) var(--space-4)",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--color-border)",
          }}
        >
          <div>
            <div style={{ fontWeight: 600 }}>
              {lang === "bn" ? "বিজ্ঞান: সালোকসংশ্লেষণ ও পুষ্টি (পৃষ্ঠা ৪২–৪৪) শিখন মূল্যায়ন" : "Science: Photosynthesis (Pages 42–44) Mastery Quiz"}
            </div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              {lang === "bn" ? "জমা দেওয়া হয়েছে: আজ • ৩টি প্রশ্নের ৩টিই সঠিক" : "Submitted: Today • 3 out of 3 correct"}
            </div>
          </div>
          <div>
            <span
              className="badge"
              style={{
                backgroundColor: "rgba(16, 185, 129, 0.15)",
                color: "var(--color-success)",
                fontWeight: 700,
                fontSize: "var(--text-xs)",
              }}
            >
              ১০০% সফল (A+)
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
