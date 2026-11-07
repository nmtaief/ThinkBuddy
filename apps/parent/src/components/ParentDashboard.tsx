import React, { useState } from "react";
import {
  UserProfile,
  Language,
  translations,
  toBengaliDigits,
  linkChildWithInviteCode,
  RoutineSlot,
  INITIAL_ROUTINE_SLOTS,
} from "@thinkbuddy/shared";
import {
  ShieldCheck,
  Flame,
  Clock,
  CheckCircle2,
  TrendingUp,
  AlertTriangle,
  BookOpen,
  Calendar,
  UserPlus,
  Bell,
  Star,
  Check,
  X,
  ExternalLink,
} from "lucide-react";
import { MathRenderer } from "./MathRenderer";

interface ParentDashboardProps {
  user: UserProfile;
  lang: Language;
}

export const ParentDashboard: React.FC<ParentDashboardProps> = ({ user, lang }) => {
  const t = translations[lang];

  // Linked children state
  const [children, setChildren] = useState([
    {
      student_id: "stu_101",
      name: "তাহমিদ আলিম",
      grade: lang === "bn" ? "৭ম শ্রেণি" : "Class 7",
      school: "ঢাকা রেসিডেনসিয়াল মডেল কলেজ",
      streak_days: 7,
      completion_rate: 65,
      study_minutes_today: 50,
      overall_mastery: 82,
    },
  ]);

  const [activeChildIndex, setActiveChildIndex] = useState(0);
  const activeChild = children[activeChildIndex];

  // Link child modal state
  const [isLinkModalOpen, setIsLinkModalOpen] = useState(false);
  const [inviteCodeInput, setInviteCodeInput] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const [linkSuccessMsg, setLinkSuccessMsg] = useState<string | null>(null);
  const [isLinking, setIsLinking] = useState(false);

  // Notifications feed
  const [notifications] = useState([
    {
      id: "n_1",
      title_bn: "আজকের বিজ্ঞান খাতা জমা হয়েছে",
      title_en: "Science study notebook submitted",
      time_bn: "১০ মিনিট আগে",
      time_en: "10 mins ago",
      desc_bn: "তাহমিদ আলিম পাঠ্যবই পৃষ্ঠা ৪২-৪৪ এর সালোকসংশ্লেষণ নোট জমা দিয়েছে। শিক্ষক মূল্যায়ন সম্পন্ন।",
      desc_en: "Tahmid Alim submitted notebook notes for pages 42-44. Teacher review complete.",
      read: false,
    },
    {
      id: "n_2",
      title_bn: "আসন্ন অর্ধবার্ষিক পরীক্ষা সতর্কতা",
      title_en: "Upcoming Mid-Term Exam Notice",
      time_bn: "২ ঘণ্টা আগে",
      time_en: "2 hours ago",
      desc_bn: "আর মাত্র ১৪ দিন বাকি। গণিত বীজগণিতীয় সূত্রাবলী রিভিশন করা জরুরি।",
      desc_en: "14 days remaining. Revision of algebraic formulas recommended.",
      read: true,
    },
    {
      id: "n_3",
      title_bn: "দিনের পড়ার ধারাবাহিকতা রক্ষা (৭ দিন)",
      title_en: "Consistent 7-day study streak",
      time_bn: "গতকাল",
      time_en: "Yesterday",
      desc_bn: "তাহমিদ টানা ৭ দিন তার নির্ধারিত পড়ার রুটিন বজায় রেখেছে। মাশাআল্লাহ!",
      desc_en: "Tahmid maintained his daily study routine for 7 consecutive days.",
      read: true,
    },
  ]);

  const handleLinkChild = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteCodeInput.trim()) return;

    setLinkError(null);
    setLinkSuccessMsg(null);
    setIsLinking(true);

    try {
      const res = await linkChildWithInviteCode(user.uid, inviteCodeInput);
      if (res.success) {
        setLinkSuccessMsg(t.parent.linkSuccess);
        const newKid = {
          student_id: `stu_${Date.now()}`,
          name: res.studentName || "তাহমিদ আলিম",
          grade: lang === "bn" ? "৭ম শ্রেণি" : "Class 7",
          school: "মিরপুর ক্যান্টনমেন্ট পাবলিক স্কুল",
          streak_days: 7,
          completion_rate: 65,
          study_minutes_today: 50,
          overall_mastery: 82,
        };
        setChildren((prev) => [...prev, newKid]);
        setInviteCodeInput("");
        setTimeout(() => {
          setIsLinkModalOpen(false);
          setLinkSuccessMsg(null);
        }, 1800);
      } else {
        setLinkError(t.parent.linkNotFound);
      }
    } catch {
      setLinkError(t.parent.linkNotFound);
    } finally {
      setIsLinking(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      {/* 1. Header & Child Selector */}
      <div
        className="card"
        style={{
          background: "linear-gradient(135deg, rgba(16, 185, 129, 0.06) 0%, rgba(37, 99, 235, 0.06) 100%)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "var(--space-4)",
          padding: "var(--space-5) var(--space-6)",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <ShieldCheck size={18} style={{ color: "var(--color-success)" }} />
            <span style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-success)" }}>
              {t.parent.dashboardTitle}
            </span>
          </div>
          <h1 style={{ fontSize: "var(--text-xl)", fontWeight: 800, marginTop: 4, color: "var(--color-text-main)" }}>
            {activeChild.name} — {lang === "bn" ? "এর অধ্যয়ন ড্যাশবোর্ড" : "'s Study Dashboard"}
          </h1>
          <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
            {activeChild.school} • {activeChild.grade}
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap" }}>
          {/* Child Switcher buttons */}
          {children.map((k, idx) => (
            <button
              key={k.student_id}
              onClick={() => setActiveChildIndex(idx)}
              className={activeChildIndex === idx ? "btn-primary touch-target" : "btn-secondary touch-target"}
              style={{ fontSize: "var(--text-xs)", height: 38, padding: "0 14px" }}
            >
              {k.name} ({k.grade})
            </button>
          ))}

          {/* Add Child Link Trigger */}
          <button
            onClick={() => setIsLinkModalOpen(true)}
            className="btn-secondary touch-target"
            style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-xs)", height: 38 }}
          >
            <UserPlus size={15} />
            <span>{t.parent.linkChildTitle}</span>
          </button>
        </div>
      </div>

      {/* 2. Key Progress Metrics Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "var(--space-4)",
        }}
      >
        {/* Streak */}
        <div className="card" style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", borderLeft: "4px solid var(--color-warning)" }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: "var(--radius-full)",
              backgroundColor: "var(--color-warning-surface)",
              color: "var(--color-warning)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Flame size={24} />
          </div>
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
              {t.parent.streak}
            </div>
            <div style={{ fontSize: "var(--text-xl)", fontWeight: 800 }}>
              {lang === "bn" ? toBengaliDigits(activeChild.streak_days) : activeChild.streak_days} {t.today.streakDays}
            </div>
          </div>
        </div>

        {/* Study Time */}
        <div className="card" style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", borderLeft: "4px solid var(--color-primary)" }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: "var(--radius-full)",
              backgroundColor: "var(--color-primary-surface)",
              color: "var(--color-primary)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Clock size={24} />
          </div>
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
              {t.parent.studyTime}
            </div>
            <div style={{ fontSize: "var(--text-xl)", fontWeight: 800 }}>
              {lang === "bn" ? toBengaliDigits(activeChild.study_minutes_today) : activeChild.study_minutes_today} {t.today.minutes}
            </div>
          </div>
        </div>

        {/* Task Completion */}
        <div className="card" style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", borderLeft: "4px solid var(--color-success)" }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: "var(--radius-full)",
              backgroundColor: "var(--color-success-surface)",
              color: "var(--color-success)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <CheckCircle2 size={24} />
          </div>
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
              {t.parent.taskCompletion}
            </div>
            <div style={{ fontSize: "var(--text-xl)", fontWeight: 800 }}>
              {lang === "bn" ? toBengaliDigits(activeChild.completion_rate) : activeChild.completion_rate}%
            </div>
          </div>
        </div>

        {/* Overall Mastery */}
        <div className="card" style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", borderLeft: "4px solid #8B5CF6" }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: "var(--radius-full)",
              backgroundColor: "rgba(139, 92, 246, 0.12)",
              color: "#8B5CF6",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <TrendingUp size={24} />
          </div>
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
              {t.parent.overallMastery}
            </div>
            <div style={{ fontSize: "var(--text-xl)", fontWeight: 800 }}>
              {lang === "bn" ? toBengaliDigits(activeChild.overall_mastery) : activeChild.overall_mastery}%
            </div>
          </div>
        </div>
      </div>

      {/* 3. Daily Study Report & Handwritten Notebook Review */}
      <div className="card" style={{ padding: "var(--space-6)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)", flexWrap: "wrap", gap: "var(--space-2)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <BookOpen size={20} style={{ color: "var(--color-primary)" }} />
            <h2 style={{ fontSize: "var(--text-base)", fontWeight: 700, margin: 0 }}>
              {t.parent.teacherReviewTitle}
            </h2>
          </div>
          <span style={{ fontSize: "var(--text-xs)", color: "var(--color-success)", fontWeight: 700 }}>
            ★ ThinkBuddy Certified Teacher Reviews
          </span>
        </div>

        {/* Notebook & Evaluation Container */}
        <div
          style={{
            padding: "var(--space-4)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-lg)",
            backgroundColor: "var(--color-surface-hover)",
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-3)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-2)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <span style={{ padding: "2px 8px", backgroundColor: "var(--color-primary-surface)", color: "var(--color-primary)", borderRadius: "var(--radius-full)", fontSize: "var(--text-xs)", fontWeight: 700 }}>
                সাধারণ বিজ্ঞান
              </span>
              <strong style={{ fontSize: "var(--text-sm)" }}>সালোকসংশ্লেষণ ও উদ্ভিদের পুষ্টি</strong>
            </div>
            <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              পাঠ্যবই: পৃষ্ঠা ৪২-৪৪ • অধ্যয়ন সময়: ২৩ মিনিট
            </span>
          </div>

          {/* Student's submitted work */}
          <div
            style={{
              padding: "var(--space-3)",
              backgroundColor: "var(--color-surface)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border)",
              fontSize: "var(--text-xs)",
              lineHeight: 1.7,
            }}
          >
            <strong>১. সালোকসংশ্লেষণের সামগ্রিক রাসায়নিক সমীকরণ:</strong>
            <div style={{ marginTop: 4 }}>
              <MathRenderer content="$$6CO_2 + 12H_2O \\longrightarrow C_6H_{12}O_6 + 6H_2O + 6O_2 \\quad (\\text{সূর্যালোক ও ক্লোরোফিলের উপস্থিতিতে})$$" />
            </div>
            <p style={{ marginTop: 4, color: "var(--color-text-secondary)" }}>
              ২. ক্লোরোপ্লাস্টের প্রধান দুটি অংশ হলো গ্রানা এবং স্ট্রোমা। আলোক পর্যায় সম্পন্ন হয় গ্রানায় এবং অন্ধকার পর্যায় (কার্বন বিজারণ) সম্পন্ন হয় স্ট্রোমায়।
            </p>
          </div>

          {/* Teacher's Feedback */}
          <div
            style={{
              padding: "var(--space-3) var(--space-4)",
              backgroundColor: "var(--color-success-surface)",
              borderRadius: "var(--radius-md)",
              border: "1px solid rgba(16, 185, 129, 0.25)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <Star size={14} style={{ color: "#F59E0B", fill: "#F59E0B" }} />
              <strong style={{ fontSize: "var(--text-xs)", color: "var(--color-text-main)" }}>
                জনাব রফিকুল ইসলাম (M.Sc, বিএড) — সিনিয়র বিজ্ঞান শিক্ষক
              </strong>
            </div>
            <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", margin: 0 }}>
              "চমৎকার প্রস্তুতি ও সুন্দর হাতের লেখা! সালোকসংশ্লেষণের সমীকরণ ও কাঁচামাল নিখুঁত। ক্লোরোপ্লাস্টের চিহ্নিত চিত্র পরিষ্কার হয়েছে।"
            </p>
          </div>
        </div>
      </div>

      {/* 4. Routine Overview */}
      <div className="card" style={{ padding: "var(--space-6)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <Calendar size={20} style={{ color: "var(--color-primary)" }} />
            <h2 style={{ fontSize: "var(--text-base)", fontWeight: 700, margin: 0 }}>
              {t.parent.routineOverviewTitle}
            </h2>
          </div>
          <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
            {t.today.allSevenDays}
          </span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "var(--space-3)" }}>
          {INITIAL_ROUTINE_SLOTS.map((slot) => (
            <div
              key={slot.id}
              style={{
                padding: "var(--space-3) var(--space-4)",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--color-border)",
                backgroundColor: "var(--color-surface-hover)",
              }}
            >
              <div style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-primary)" }}>
                {lang === "bn" ? slot.timeSlot : slot.timeSlotEn}
              </div>
              <div style={{ fontWeight: 700, fontSize: "var(--text-sm)", marginTop: 2 }}>
                {lang === "bn" ? slot.subject : slot.subjectEn}
              </div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: 2 }}>
                {lang === "bn" ? slot.chapterTitle : slot.chapterTitleEn}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 5. Weak Chapters & AI Suggestions */}
      <div className="card" style={{ padding: "var(--space-6)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}>
          <AlertTriangle size={20} style={{ color: "var(--color-warning)" }} />
          <div>
            <h2 style={{ fontSize: "var(--text-base)", fontWeight: 700, margin: 0 }}>
              {t.parent.weakChaptersTitle}
            </h2>
            <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              {t.parent.weakChaptersDesc}
            </span>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", marginTop: "var(--space-3)" }}>
          {/* Chapter 1 */}
          <div
            style={{
              padding: "var(--space-4)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-surface)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "var(--space-2)",
            }}
          >
            <div>
              <span style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-warning)" }}>
                গণিত (Mathematics)
              </span>
              <h3 style={{ fontSize: "var(--text-sm)", fontWeight: 700, margin: 0, marginTop: 2 }}>
                অধ্যায় ৫: বীজগণিতীয় সূত্রাবলী ও প্রয়োগ (অনুশীলনী ৫.১)
              </h3>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
              <span
                style={{
                  padding: "4px 10px",
                  borderRadius: "var(--radius-full)",
                  backgroundColor: "var(--color-warning-surface)",
                  color: "var(--color-warning)",
                  fontSize: "var(--text-xs)",
                  fontWeight: 700,
                }}
              >
                {t.status.needsPractice}
              </span>
              <span style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-text-secondary)" }}>
                দক্ষতা: {lang === "bn" ? toBengaliDigits(58) : 58}%
              </span>
            </div>
          </div>

          {/* Chapter 2 */}
          <div
            style={{
              padding: "var(--space-4)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-surface)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "var(--space-2)",
            }}
          >
            <div>
              <span style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-text-muted)" }}>
                বাংলাদেশ ও বিশ্বপরিচয়
              </span>
              <h3 style={{ fontSize: "var(--text-sm)", fontWeight: 700, margin: 0, marginTop: 2 }}>
                অধ্যায় ৪: বাংলাদেশের অর্থনীতি ও প্রাকৃতিক সম্পদ
              </h3>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
              <span
                style={{
                  padding: "4px 10px",
                  borderRadius: "var(--radius-full)",
                  backgroundColor: "var(--color-surface-hover)",
                  color: "var(--color-text-muted)",
                  fontSize: "var(--text-xs)",
                  fontWeight: 700,
                }}
              >
                {t.status.insufficientData}
              </span>
              <span style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-text-secondary)" }}>
                দক্ষতা: {lang === "bn" ? toBengaliDigits(35) : 35}%
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 6. Notifications Feed */}
      <div className="card" style={{ padding: "var(--space-6)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-4)" }}>
          <Bell size={20} style={{ color: "var(--color-primary)" }} />
          <h2 style={{ fontSize: "var(--text-base)", fontWeight: 700, margin: 0 }}>
            {lang === "bn" ? "সাম্প্রতিক বিজ্ঞপ্তি ও সতর্কতা" : "Recent Notifications"}
          </h2>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          {notifications.map((n) => (
            <div
              key={n.id}
              style={{
                padding: "var(--space-3) var(--space-4)",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--color-border)",
                backgroundColor: n.read ? "var(--color-surface)" : "var(--color-primary-surface)",
                display: "flex",
                flexDirection: "column",
                gap: 2,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong style={{ fontSize: "var(--text-xs)", color: "var(--color-text-main)" }}>
                  {lang === "bn" ? n.title_bn : n.title_en}
                </strong>
                <span style={{ fontSize: "10px", color: "var(--color-text-muted)" }}>
                  {lang === "bn" ? n.time_bn : n.time_en}
                </span>
              </div>
              <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", margin: 0 }}>
                {lang === "bn" ? n.desc_bn : n.desc_en}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Modal: Link New Child */}
      {isLinkModalOpen && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(15, 23, 42, 0.5)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
            padding: "var(--space-4)",
          }}
        >
          <div
            className="card"
            style={{
              width: "100%",
              maxWidth: 440,
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-4)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                <UserPlus size={20} style={{ color: "var(--color-primary)" }} />
                <h3 style={{ fontSize: "var(--text-base)", fontWeight: 700, margin: 0 }}>
                  {t.parent.linkChildTitle}
                </h3>
              </div>
              <button
                onClick={() => setIsLinkModalOpen(false)}
                className="btn-secondary touch-target"
                style={{ padding: 6 }}
              >
                <X size={16} />
              </button>
            </div>

            <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", lineHeight: 1.6 }}>
              {t.parent.studentInviteCodeDesc}
            </p>

            <form onSubmit={handleLinkChild} style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
              <div>
                <label style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-text-secondary)", display: "block", marginBottom: 6 }}>
                  {t.parent.inviteCodeLabel}
                </label>
                <input
                  type="text"
                  value={inviteCodeInput}
                  onChange={(e) => setInviteCodeInput(e.target.value.toUpperCase())}
                  placeholder={t.parent.inviteCodePlaceholder}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: "var(--radius-md)",
                    border: "1.5px solid var(--color-border)",
                    backgroundColor: "var(--color-surface)",
                    color: "var(--color-text-main)",
                    fontFamily: "monospace",
                    fontSize: "var(--text-base)",
                    fontWeight: 700,
                    textTransform: "uppercase",
                  }}
                />
              </div>

              {linkError && (
                <div style={{ fontSize: "var(--text-xs)", color: "var(--color-error)", fontWeight: 600 }}>
                  ✕ {linkError}
                </div>
              )}

              {linkSuccessMsg && (
                <div style={{ fontSize: "var(--text-xs)", color: "var(--color-success)", fontWeight: 700 }}>
                  ✓ {linkSuccessMsg}
                </div>
              )}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)", marginTop: "var(--space-2)" }}>
                <button
                  type="button"
                  onClick={() => setIsLinkModalOpen(false)}
                  className="btn-secondary touch-target"
                  style={{ fontSize: "var(--text-xs)" }}
                >
                  {t.today.cancel}
                </button>
                <button
                  type="submit"
                  disabled={!inviteCodeInput.trim() || isLinking}
                  className="btn-primary touch-target"
                  style={{ fontSize: "var(--text-xs)" }}
                >
                  {isLinking ? t.parent.linking : t.parent.linkBtn}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

