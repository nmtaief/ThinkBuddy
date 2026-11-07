import React from "react";
import { Language, translations, toBengaliDigits } from "@thinkbuddy/shared";
import { TrendingUp, Award, RotateCcw, CheckCircle, AlertTriangle, HelpCircle } from "lucide-react";

interface ProgressViewProps {
  lang: Language;
}

export const ProgressView: React.FC<ProgressViewProps> = ({ lang }) => {
  const t = translations[lang];

  const chaptersProgress = [
    {
      subject: "সাধারণ বিজ্ঞান",
      subjectEn: "General Science",
      chapter: "অধ্যায় ৪: উদ্ভিদের পুষ্টি ও সালোকসংশ্লেষণ",
      chapterEn: "Chapter 4: Plant Nutrition & Photosynthesis",
      mastery: 85,
      status: "mastered" as const,
      leitnerBox: 3,
    },
    {
      subject: "গণিত",
      subjectEn: "Mathematics",
      chapter: "অধ্যায় ৫: বীজগণিতীয় সূত্রাবলী ও প্রয়োগ",
      chapterEn: "Chapter 5: Algebraic Identities",
      mastery: 58,
      status: "needs_practice" as const,
      leitnerBox: 1,
    },
    {
      subject: "English For Today",
      subjectEn: "English For Today",
      chapter: "Unit 3: Health and Hygiene",
      chapterEn: "Unit 3: Health and Hygiene",
      mastery: 72,
      status: "mastered" as const,
      leitnerBox: 2,
    },
    {
      subject: "বাংলাদেশ ও বিশ্বপরিচয়",
      subjectEn: "Bangladesh & Global Studies",
      chapter: "অধ্যায় ৪: অর্থনীতি ও প্রাকৃতিক সম্পদ",
      chapterEn: "Chapter 4: Economy & Natural Resources",
      mastery: 35,
      status: "insufficient_data" as const,
      leitnerBox: 1,
    },
  ];

  const getStatusBadge = (status: "mastered" | "needs_practice" | "insufficient_data") => {
    switch (status) {
      case "mastered":
        return {
          label: t.status.mastered,
          bg: "var(--color-success-surface)",
          color: "var(--color-success)",
          icon: CheckCircle,
        };
      case "needs_practice":
        return {
          label: t.status.needsPractice,
          bg: "var(--color-warning-surface)",
          color: "var(--color-warning)",
          icon: AlertTriangle,
        };
      case "insufficient_data":
        return {
          label: t.status.insufficientData,
          bg: "var(--color-surface-hover)",
          color: "var(--color-text-muted)",
          icon: HelpCircle,
        };
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      {/* Overview Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: "var(--space-4)",
        }}
      >
        <div className="card" style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
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
            <TrendingUp size={24} />
          </div>
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
              {lang === "bn" ? "সামগ্রিক দক্ষতা" : "Overall Mastery"}
            </div>
            <div style={{ fontSize: "var(--text-2xl)", fontWeight: 800 }}>
              {lang === "bn" ? toBengaliDigits(75) : 75}%
            </div>
          </div>
        </div>

        <div className="card" style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: "var(--radius-full)",
              backgroundColor: "var(--color-success-surface)",
              color: "var(--color-success)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <RotateCcw size={24} />
          </div>
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
              {lang === "bn" ? "লেইটনার রিভিশন বক্স" : "Leitner Spaced Revision"}
            </div>
            <div style={{ fontSize: "var(--text-base)", fontWeight: 700 }}>
              {lang === "bn" ? "৩টি বিষয় পর্যালোচনা বাকি" : "3 topics due for revision"}
            </div>
          </div>
        </div>
      </div>

      {/* Chapter Breakdown */}
      <div className="card" style={{ padding: "var(--space-6)" }}>
        <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700, marginBottom: "var(--space-4)" }}>
          {lang === "bn" ? "অধ্যায়ভিত্তিক শিখন অগ্রগতি ও অবস্থা" : "Chapter Mastery Breakdown"}
        </h2>

        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          {chaptersProgress.map((item, idx) => {
            const badge = getStatusBadge(item.status);
            const Icon = badge.icon;
            return (
              <div
                key={idx}
                style={{
                  padding: "var(--space-4)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-lg)",
                  backgroundColor: "var(--color-surface)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "var(--space-3)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "var(--space-2)" }}>
                  <div>
                    <span style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-primary)" }}>
                      {lang === "bn" ? item.subject : item.subjectEn}
                    </span>
                    <h3 style={{ fontSize: "var(--text-base)", fontWeight: 700, margin: 0, marginTop: 2 }}>
                      {lang === "bn" ? item.chapter : item.chapterEn}
                    </h3>
                  </div>

                  {/* Status Badge with required wording */}
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 5,
                      padding: "4px 10px",
                      borderRadius: "var(--radius-full)",
                      fontSize: "var(--text-xs)",
                      fontWeight: 700,
                      backgroundColor: badge.bg,
                      color: badge.color,
                    }}
                  >
                    <Icon size={13} />
                    <span>{badge.label}</span>
                  </span>
                </div>

                {/* Mastery Progress Bar */}
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                  <div
                    style={{
                      flex: 1,
                      height: 8,
                      borderRadius: "var(--radius-full)",
                      backgroundColor: "var(--color-surface-hover)",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${item.mastery}%`,
                        height: "100%",
                        backgroundColor: badge.color,
                        borderRadius: "var(--radius-full)",
                        transition: "width 0.4s ease",
                      }}
                    />
                  </div>
                  <span style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-text-secondary)", minWidth: 35 }}>
                    {lang === "bn" ? toBengaliDigits(item.mastery) : item.mastery}%
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

