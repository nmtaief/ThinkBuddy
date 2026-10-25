"use client";

import React, { useState } from "react";
import { ChildSummary } from "@/lib/types";
import { Language, translations, toBengaliDigits } from "@/lib/i18n";
import { Users, Flame, Clock, CheckCircle, BarChart3, Calendar } from "lucide-react";

interface ParentDashboardViewProps {
  childrenList: ChildSummary[];
  activeChildId: string;
  onSelectChild: (id: string) => void;
  lang: Language;
}

export const ParentDashboardView: React.FC<ParentDashboardViewProps> = ({
  childrenList,
  activeChildId,
  onSelectChild,
  lang,
}) => {
  const t = translations[lang];

  const activeChild = childrenList.find((c) => c.student_id === activeChildId) || childrenList[0];

  if (!activeChild) {
    return (
      <div className="card" style={{ padding: "var(--space-8)", textAlign: "center" }}>
        <p>কোনো সন্তান প্রোফাইল যুক্ত করা হয়নি।</p>
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
              আজকের কাজ সমাপ্তি
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
              সামগ্রিক বিষয় দক্ষতা
            </div>
            <div style={{ fontSize: "var(--text-2xl)", fontWeight: 700 }}>{masteryDisplay}%</div>
          </div>
        </div>
      </div>

      {/* Review Quiz Results Section */}
      <div className="card" style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700 }}>সাম্প্রতিক পর্যালোচনা কুইজ ফলাফল</h2>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            backgroundColor: "var(--color-surface-hover)",
            padding: "var(--space-3) var(--space-4)",
            borderRadius: "var(--radius-md)",
          }}
        >
          <div>
            <div style={{ fontWeight: 600 }}>বিজ্ঞান ও গণিত ৩-দিনের সাইকেল কুইজ</div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              জমা দেওয়া হয়েছে: গতকাল রাত ৮:১৫
            </div>
          </div>
          <div>
            <span className="badge badge-success">৮০% সফল</span>
          </div>
        </div>
      </div>
    </div>
  );
};
