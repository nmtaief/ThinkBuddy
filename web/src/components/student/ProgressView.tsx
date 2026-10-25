"use client";

import React from "react";
import { Language, translations, toBengaliDigits } from "@/lib/i18n";
import { CheckCircle2, RotateCcw, AlertTriangle, HelpCircle } from "lucide-react";

interface ProgressViewProps {
  lang: Language;
}

export const ProgressView: React.FC<ProgressViewProps> = ({ lang }) => {
  const t = translations[lang];

  const masteryItems = [
    {
      subject: "সাধারণ বিজ্ঞান",
      chapter: "অধ্যায় ৪: উদ্ভিদের খাদ্য উৎপাদন",
      score: 85,
      state: "mastered",
      box: 4,
    },
    {
      subject: "গণিত",
      chapter: "অধ্যায় ৫: বীজগণিতীয় সূত্রাবলি",
      score: 55,
      state: "needs_practice", // Approved wording
      box: 2,
    },
    {
      subject: "ইংরেজি",
      chapter: "Unit 4: Morality & Ethics",
      score: 0,
      state: "not_enough_data", // Approved wording
      box: 1,
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      <div>
        <h2 style={{ fontSize: "var(--text-xl)", fontWeight: 700 }}>{t.nav.progress}</h2>
        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>
          আপনার অধ্যয়ন ধারাবাহিকতা ও বিষয়ভিত্তিক দক্ষতা অগ্রগতি
        </p>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        {masteryItems.map((item, idx) => {
          let badgeClass = "badge-success";
          let label = t.growthMindset.mastered;

          if (item.state === "needs_practice") {
            badgeClass = "badge-needs-practice";
            label = t.growthMindset.needsPractice;
          } else if (item.state === "not_enough_data") {
            badgeClass = "badge-not-enough-data";
            label = t.growthMindset.notEnoughData;
          }

          return (
            <div
              key={idx}
              className="card"
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <span
                  style={{
                    fontSize: "var(--text-xs)",
                    fontWeight: 600,
                    color: "var(--color-primary)",
                  }}
                >
                  {item.subject}
                </span>
                <h4 style={{ fontSize: "var(--text-base)", fontWeight: 600 }}>{item.chapter}</h4>
                <div
                  style={{
                    fontSize: "var(--text-xs)",
                    color: "var(--color-text-muted)",
                    display: "flex",
                    gap: "var(--space-2)",
                    marginTop: 4,
                  }}
                >
                  <span>
                    লাইটনার বাক্স: {lang === "bn" ? toBengaliDigits(item.box) : item.box} / ৫
                  </span>
                </div>
              </div>

              <div>
                <span className={`badge ${badgeClass}`}>{label}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
