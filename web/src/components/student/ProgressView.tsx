"use client";

import React, { useState } from "react";
import { Language, translations, toBengaliDigits } from "@/lib/i18n";
import {
  CheckCircle2,
  RotateCcw,
  AlertTriangle,
  Flame,
  Award,
  BookOpen,
  ArrowRight,
  Sparkles,
  TrendingUp,
  Brain,
  Clock,
} from "lucide-react";
import RevisionSessionView from "./RevisionSessionView";
import { getActiveRevisionQueue } from "@/lib/revision-queue-engine";

interface ProgressViewProps {
  lang: Language;
}

interface ChapterMastery {
  subject: string;
  chapter: string;
  score: number;
  confidence: number;
  state: "mastered" | "needs_practice" | "not_enough_data";
  box: number;
}

export const ProgressView: React.FC<ProgressViewProps> = ({ lang }) => {
  const t = translations[lang];
  const [inRevisionSession, setInRevisionSession] = useState(false);
  const [streakDays, setStreakDays] = useState(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("tb_streak_days");
      return saved !== null ? parseInt(saved, 10) || 0 : 0;
    }
    return 0;
  });
  const [studyMinutesToday, setStudyMinutesToday] = useState(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("tb_study_minutes_today");
      return saved !== null ? parseInt(saved, 10) || 0 : 0;
    }
    return 0;
  });
  const [tasksCompleted, setTasksCompleted] = useState(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("tb_completed_tasks_count");
      return saved !== null ? parseInt(saved, 10) || 0 : 0;
    }
    return 0;
  });
  const [totalTasks, setTotalTasks] = useState(3);

  // Active mastery items derived dynamically from authentic revision queue & curriculum dataset
  const [masteryItems, setMasteryItems] = useState<ChapterMastery[]>(() => {
    const queue = getActiveRevisionQueue();
    return queue.map((item) => ({
      subject: item.subject,
      chapter: item.chapter_title,
      score: item.box >= 4 ? 85 + item.box * 2 : item.box === 3 ? 72 : item.box === 2 ? 60 : 45,
      confidence: item.box >= 4 ? 0.9 : item.box === 3 ? 0.75 : 0.6,
      state: item.box >= 4 ? "mastered" : item.box <= 2 ? "needs_practice" : "not_enough_data",
      box: item.box,
    }));
  });

  if (inRevisionSession) {
    return (
      <RevisionSessionView
        lang={lang}
        onBackToProgress={() => setInRevisionSession(false)}
      />
    );
  }

  const weakTopics = masteryItems.filter((i) => i.state === "needs_practice");
  const masteredTopics = masteryItems.filter((i) => i.state === "mastered");
  const overallMastery = Math.round(
    masteryItems.reduce((acc, m) => acc + m.score, 0) / Math.max(1, masteryItems.length)
  );

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <h2 className="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-white tracking-tight">
            {lang === "bn" ? "শেখার অগ্রগতি ও ধারাবাহিকতা" : "Learning Progress & Streaks"}
          </h2>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 mt-1">
            {lang === "bn"
              ? "তোমার অধ্যয়ন ধারাবাহিকতা, দুর্বল অধ্যায়সমূহ ও স্পেসড রিপিটেশন রিভিশন"
              : "Track your study streaks, subject mastery, and spaced repetition revision"}
          </p>
        </div>

        {/* Spaced Revision Quick Action */}
        <button
          onClick={() => setInRevisionSession(true)}
          className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-700 hover:to-blue-700 text-white text-xs font-bold rounded-xl shadow-md hover:shadow-lg transition-all self-start sm:self-auto cursor-pointer"
        >
          <RotateCcw className="w-4 h-4" />
          {lang === "bn" ? "আজকের রিভিশন সেশন শুরু করো (৪টি প্রশ্ন)" : "Start Daily Revision (4 Items)"}
        </button>
      </div>

      {/* Hero Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Streak card */}
        <div className="bg-amber-50 dark:bg-amber-950/60 border border-amber-200 dark:border-amber-800 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-amber-900 dark:text-amber-200 uppercase tracking-wide">
              {lang === "bn" ? "অধ্যয়ন ধারাবাহিকতা" : "Study Streak"}
            </span>
            <Flame className="w-5 h-5 text-amber-500 fill-amber-500 animate-pulse" />
          </div>
          <div className="text-2xl sm:text-3xl font-extrabold text-amber-700 dark:text-amber-300 mt-2">
            {lang === "bn" ? toBengaliDigits(streakDays) : streakDays} {lang === "bn" ? "দিন" : "Days"}
          </div>
          <p className="text-xs text-amber-800 dark:text-amber-200/90 mt-1.5 font-medium">
            {lang === "bn" ? "দারুণ ধারাবাহিকতা! প্রতিদিন পড়লে স্মৃতিশক্তি বাড়ে।" : "Keep it up! Daily study strengthens long-term memory."}
          </p>
        </div>

        {/* Study Time Today */}
        <div className="bg-white dark:bg-slate-800/90 border border-slate-200 dark:border-slate-700 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-600 dark:text-slate-300 uppercase tracking-wide">
              {lang === "bn" ? "আজকের পড়ার সময়" : "Study Time Today"}
            </span>
            <Clock className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white mt-2">
            {lang === "bn" ? toBengaliDigits(studyMinutesToday) : studyMinutesToday} {lang === "bn" ? "মিনিট" : "min"}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1.5 font-medium">
            {lang === "bn" ? "দৈনিক লক্ষ্য: ৬০ মিনিট" : "Daily goal: 60 min"}
          </p>
        </div>

        {/* Tasks completed */}
        <div className="bg-white dark:bg-slate-800/90 border border-slate-200 dark:border-slate-700 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-600 dark:text-slate-300 uppercase tracking-wide">
              {lang === "bn" ? "আজকের কাজ সম্পন্ন" : "Tasks Done"}
            </span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white mt-2">
            {lang === "bn" ? toBengaliDigits(tasksCompleted) : tasksCompleted} / {lang === "bn" ? toBengaliDigits(totalTasks) : totalTasks}
          </div>
          <p className="text-xs text-emerald-700 dark:text-emerald-400 mt-1.5 font-bold">
            {lang === "bn" ? "৭৫% কাজ শেষ হয়েছে" : "75% completed"}
          </p>
        </div>

        {/* Overall Mastery */}
        <div className="bg-white dark:bg-slate-800/90 border border-slate-200 dark:border-slate-700 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-600 dark:text-slate-300 uppercase tracking-wide">
              {lang === "bn" ? "সামগ্রিক দক্ষতা" : "Overall Mastery"}
            </span>
            <Brain className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="text-2xl sm:text-3xl font-extrabold text-indigo-600 dark:text-indigo-400 mt-2">
            {lang === "bn" ? toBengaliDigits(overallMastery) : overallMastery}%
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1.5 font-medium">
            {masteredTopics.length} {lang === "bn" ? "টি অধ্যায় আয়ত্তে" : "chapters mastered"}
          </p>
        </div>
      </div>

      {/* Weak Points Alert Banner */}
      {weakTopics.length > 0 && (
        <div className="p-5 rounded-2xl bg-rose-50/90 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 shadow-sm space-y-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <h3 className="text-xs font-extrabold text-rose-900 dark:text-rose-200 uppercase tracking-wider">
              {lang === "bn" ? "বিশেষ নজর প্রয়োজন (Needs Practice Topics)" : "Needs Practice Topics"}
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {weakTopics.map((topic, idx) => (
              <div
                key={idx}
                className="p-4 bg-white dark:bg-slate-800 rounded-xl border border-rose-200 dark:border-rose-900/60 flex items-center justify-between shadow-sm"
              >
                <div>
                  <span className="text-xs font-bold text-rose-600 dark:text-rose-400">
                    {topic.subject}
                  </span>
                  <div className="text-xs sm:text-sm font-bold text-slate-900 dark:text-white mt-0.5">
                    {topic.chapter}
                  </div>
                  <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                    {lang === "bn" ? "বর্তমান স্কোর: " : "Current score: "}
                    <strong className="text-slate-700 dark:text-slate-200">
                      {lang === "bn" ? toBengaliDigits(topic.score) : topic.score}%
                    </strong> • Box {topic.box}
                  </div>
                </div>

                <button
                  onClick={() => setInRevisionSession(true)}
                  className="px-3 py-1.5 text-xs font-bold text-rose-700 dark:text-rose-200 bg-rose-100 dark:bg-rose-900/60 hover:bg-rose-200 dark:hover:bg-rose-800 rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm"
                >
                  {lang === "bn" ? "অনুশীলন" : "Practice"}
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Full Chapter Mastery List */}
      <div className="bg-white dark:bg-slate-800/90 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-sm space-y-4">
        <h3 className="text-sm sm:text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-indigo-500" />
          {lang === "bn" ? "অধ্যায়ভিত্তিক বিস্তারিত দক্ষতা" : "Chapter-by-Chapter Mastery Breakdown"}
        </h3>

        <div className="space-y-3">
          {masteryItems.map((item, idx) => {
            let badgeClass = "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800";
            let label = t.growthMindset.mastered;

            if (item.state === "needs_practice") {
              badgeClass = "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border border-rose-300 dark:border-rose-800";
              label = t.growthMindset.needsPractice;
            } else if (item.state === "not_enough_data") {
              badgeClass = "bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-600";
              label = t.growthMindset.notEnoughData;
            }

            return (
              <div
                key={idx}
                className="p-4 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/70 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:border-slate-300 dark:hover:border-slate-600 transition-all shadow-sm"
              >
                <div>
                  <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400">
                    {item.subject}
                  </span>
                  <h4 className="text-xs sm:text-sm font-bold text-slate-900 dark:text-white mt-0.5">
                    {item.chapter}
                  </h4>
                  <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400 mt-1.5">
                    <span>
                      {lang === "bn" ? "লাইটনার বাক্স: " : "Leitner Box: "}
                      <strong className="text-slate-800 dark:text-slate-200">
                        {lang === "bn" ? toBengaliDigits(item.box) : item.box} / ৫
                      </strong>
                    </span>
                    {item.confidence >= 0.35 && (
                      <span>
                        {lang === "bn" ? "দক্ষতা: " : "Mastery: "}
                        <strong className="text-slate-800 dark:text-slate-200">
                          {lang === "bn" ? toBengaliDigits(item.score) : item.score}%
                        </strong>
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 self-start sm:self-auto">
                  <span className={`px-3 py-1 rounded-full text-xs font-bold ${badgeClass}`}>
                    {label}
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
