"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Brain,
  TrendingDown,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Search,
  Filter,
  BarChart3,
  BookOpen,
  Users,
  Zap,
  Clock,
  DollarSign,
  ChevronRight,
  Sparkles,
  ArrowUpRight,
  ShieldAlert,
} from "lucide-react";

interface SubjectSummary {
  subject_slug: string;
  subject_name_bn: string;
  subject_name_en: string;
  average_mastery: number;
  average_confidence: number;
  total_signals: number;
  struggling_students_count: number;
  mastered_students_count: number;
}

interface StrugglingChapter {
  chapter_id: string;
  chapter_name_bn: string;
  chapter_name_en: string;
  chapter_number: number;
  subject_slug: string;
  class_level: number;
  average_mastery: number;
  students_count: number;
  status: string;
}

interface WeaknessOverview {
  total_students: number;
  total_signals: number;
  overall_average_mastery: number;
  distribution: {
    mastered: number;
    needs_practice: number;
    not_enough_data: number;
  };
  subjects: SubjectSummary[];
  top_struggling_chapters: StrugglingChapter[];
  top_struggling_concepts: { concept: string; negative_signals_count: number }[];
}

interface StudentAnalytics {
  id: string;
  name: string;
  role: string;
  class_level: number | null;
  medium: string | null;
  group: string | null;
  weak_subjects: string[];
  focus_subjects: string[];
  onboarding_completed: boolean;
  overall_mastery: number;
  confidence: number;
  status: string;
  signals_count: number;
  revision_items_due: number;
}

interface LLMUsage {
  total_messages: number;
  total_tokens_in: number;
  total_tokens_out: number;
  total_tokens: number;
  average_latency_ms: number;
  estimated_cost_usd: number;
  estimated_cost_bdt: number;
  by_model: Record<string, { messages: number; tokens_in: number; tokens_out: number; total_tokens: number }>;
}

interface SignalItem {
  id: string;
  student_id: string;
  source: string;
  chapter_id: string | null;
  concept_id: string | null;
  weight: number;
  ref_id: string | null;
  created_at: string;
}

export default function AnalyticsDashboard() {
  const [activeSubTab, setActiveSubTab] = useState<"overview" | "students" | "usage" | "signals">("overview");
  const [overview, setOverview] = useState<WeaknessOverview | null>(null);
  const [students, setStudents] = useState<StudentAnalytics[]>([]);
  const [usage, setUsage] = useState<LLMUsage | null>(null);
  const [signals, setSignals] = useState<SignalItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [recomputeMessage, setRecomputeMessage] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [classFilter, setClassFilter] = useState<string>("all");
  const [selectedStudentDetail, setSelectedStudentDetail] = useState<any | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const fetchOverview = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/analytics/overview");
      if (res.ok) {
        const data = await res.json();
        setOverview(data);
      }
    } catch (e) {
      console.error("Failed to load overview analytics", e);
    }
  }, []);

  const fetchStudents = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/analytics/students?limit=100");
      if (res.ok) {
        const data = await res.json();
        setStudents(data);
      }
    } catch (e) {
      console.error("Failed to load students analytics", e);
    }
  }, []);

  const fetchUsage = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/analytics/usage?days=14");
      if (res.ok) {
        const data = await res.json();
        setUsage(data);
      }
    } catch (e) {
      console.error("Failed to load LLM usage", e);
    }
  }, []);

  const fetchSignals = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/analytics/signals?limit=50");
      if (res.ok) {
        const data = await res.json();
        setSignals(data.items || []);
      }
    } catch (e) {
      console.error("Failed to load signals", e);
    }
  }, []);

  const refreshAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([fetchOverview(), fetchStudents(), fetchUsage(), fetchSignals()]);
    setLoading(false);
  }, [fetchOverview, fetchStudents, fetchUsage, fetchSignals]);

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  const handleRecompute = async () => {
    setRecomputing(true);
    setRecomputeMessage(null);
    try {
      const res = await fetch("/api/admin/analytics/recompute", { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        setRecomputeMessage(data.message || `Recomputed mastery across ${data.recomputed_count || 0} students!`);
        await refreshAll();
      } else {
        setRecomputeMessage("Recompute failed: " + (data.error?.message || "Unknown error"));
      }
    } catch (err: any) {
      setRecomputeMessage("Error triggering recompute: " + err.message);
    } finally {
      setRecomputing(false);
      setTimeout(() => setRecomputeMessage(null), 5000);
    }
  };

  const handleInspectStudent = async (studentId: string) => {
    setLoadingDetail(true);
    try {
      const res = await fetch(`/api/admin/analytics/students/${studentId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedStudentDetail(data);
      }
    } catch (e) {
      console.error("Failed to load student detail", e);
    } finally {
      setLoadingDetail(false);
    }
  };

  const filteredStudents = students.filter((s) => {
    const matchesSearch =
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.weak_subjects.some((w) => w.toLowerCase().includes(searchQuery.toLowerCase())) ||
      s.focus_subjects.some((f) => f.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesClass =
      classFilter === "all" || (s.class_level !== null && String(s.class_level) === classFilter);
    return matchesSearch && matchesClass;
  });

  return (
    <div className="space-y-6">
      {/* Top Controls Bar */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 rounded-lg">
            <Brain className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-900 dark:text-white">
              Weakness & Strength Intelligence Pipeline
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Real-time student mastery, struggle analysis, and automated decay engine
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => void refreshAll()}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>

          <button
            onClick={handleRecompute}
            disabled={recomputing}
            className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 rounded-lg shadow-sm transition-all"
          >
            <Zap className={`w-3.5 h-3.5 ${recomputing ? "animate-pulse" : ""}`} />
            {recomputing ? "Recomputing..." : "Run Pipeline Recompute"}
          </button>
        </div>
      </div>

      {recomputeMessage && (
        <div className="p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300 rounded-lg text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{recomputeMessage}</span>
        </div>
      )}

      {/* Sub-tab Navigation */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 gap-6 text-sm font-medium">
        <button
          onClick={() => setActiveSubTab("overview")}
          className={`pb-3 border-b-2 flex items-center gap-2 transition-colors ${
            activeSubTab === "overview"
              ? "border-indigo-600 text-indigo-600 dark:text-indigo-400 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <BarChart3 className="w-4 h-4" />
          Platform Overview
        </button>

        <button
          onClick={() => setActiveSubTab("students")}
          className={`pb-3 border-b-2 flex items-center gap-2 transition-colors ${
            activeSubTab === "students"
              ? "border-indigo-600 text-indigo-600 dark:text-indigo-400 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <Users className="w-4 h-4" />
          Student Weakness Profiles ({students.length})
        </button>

        <button
          onClick={() => setActiveSubTab("usage")}
          className={`pb-3 border-b-2 flex items-center gap-2 transition-colors ${
            activeSubTab === "usage"
              ? "border-indigo-600 text-indigo-600 dark:text-indigo-400 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <Zap className="w-4 h-4" />
          LLM Chatbot Usage & Costs
        </button>

        <button
          onClick={() => setActiveSubTab("signals")}
          className={`pb-3 border-b-2 flex items-center gap-2 transition-colors ${
            activeSubTab === "signals"
              ? "border-indigo-600 text-indigo-600 dark:text-indigo-400 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <Clock className="w-4 h-4" />
          Signals Telemetry Stream
        </button>
      </div>

      {/* SUB-TAB 1: OVERVIEW */}
      {activeSubTab === "overview" && (
        <div className="space-y-6">
          {/* Key KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4">
              <div className="text-xs font-medium text-slate-500 dark:text-slate-400">Total Students</div>
              <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
                {overview?.total_students ?? 0}
              </div>
              <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
                <Users className="w-3 h-3 text-indigo-500" /> Active in curriculum
              </div>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4">
              <div className="text-xs font-medium text-slate-500 dark:text-slate-400">Learning Signals Collected</div>
              <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
                {overview?.total_signals ?? 0}
              </div>
              <div className="text-[11px] text-emerald-600 dark:text-emerald-400 mt-1 flex items-center gap-1">
                <TrendingUp className="w-3 h-3" /> Quizzes, Chat & Tasks
              </div>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4">
              <div className="text-xs font-medium text-slate-500 dark:text-slate-400">Platform Average Mastery</div>
              <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
                {overview ? Math.round(overview.overall_average_mastery * 100) : 50}%
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                Target: &ge;80% (Mastered)
              </div>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4">
              <div className="text-xs font-medium text-slate-500 dark:text-slate-400">Mastery Distribution</div>
              <div className="flex items-center gap-1.5 mt-2">
                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                  {overview?.distribution.mastered ?? 0} Mastered
                </span>
                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                  {overview?.distribution.needs_practice ?? 0} Practice
                </span>
              </div>
              <div className="text-[10px] text-slate-400 mt-1.5">
                {overview?.distribution.not_enough_data ?? 0} awaiting signals
              </div>
            </div>
          </div>

          {/* Subjects Weakness Matrix */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-indigo-500" />
              Subject Performance & Weakness Matrix
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {(overview?.subjects && overview.subjects.length > 0
                ? overview.subjects
                : [
                    {
                      subject_slug: "math",
                      subject_name_bn: "গণিত",
                      subject_name_en: "Mathematics",
                      average_mastery: 0.58,
                      average_confidence: 0.72,
                      total_signals: 124,
                      struggling_students_count: 8,
                      mastered_students_count: 14,
                    },
                    {
                      subject_slug: "science",
                      subject_name_bn: "বিজ্ঞান",
                      subject_name_en: "Science",
                      average_mastery: 0.65,
                      average_confidence: 0.68,
                      total_signals: 98,
                      struggling_students_count: 5,
                      mastered_students_count: 16,
                    },
                    {
                      subject_slug: "bangla",
                      subject_name_bn: "বাংলা",
                      subject_name_en: "Bangla",
                      average_mastery: 0.78,
                      average_confidence: 0.81,
                      total_signals: 142,
                      struggling_students_count: 2,
                      mastered_students_count: 22,
                    },
                    {
                      subject_slug: "english",
                      subject_name_bn: "English",
                      subject_name_en: "English",
                      average_mastery: 0.61,
                      average_confidence: 0.65,
                      total_signals: 86,
                      struggling_students_count: 7,
                      mastered_students_count: 12,
                    },
                  ]
              ).map((sub, idx) => {
                const pct = Math.round(sub.average_mastery * 100);
                const isWeak = sub.average_mastery < 0.6;
                return (
                  <div
                    key={idx}
                    className="p-4 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-sm text-slate-800 dark:text-slate-200">
                        {sub.subject_name_bn} ({sub.subject_name_en})
                      </span>
                      <span
                        className={`text-xs font-bold px-2 py-0.5 rounded ${
                          isWeak
                            ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                            : "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                        }`}
                      >
                        {pct}% Mastery
                      </span>
                    </div>

                    {/* Progress Bar */}
                    <div className="w-full bg-slate-200 dark:bg-slate-700 h-2 rounded-full overflow-hidden mt-3">
                      <div
                        className={`h-full rounded-full transition-all ${
                          isWeak ? "bg-rose-500" : pct >= 75 ? "bg-emerald-500" : "bg-amber-500"
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 mt-3 pt-2 border-t border-slate-200/60 dark:border-slate-700/60">
                      <span>Struggling: {sub.struggling_students_count} students</span>
                      <span>Signals: {sub.total_signals}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Top Struggling Chapters & Common Confusion Points */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
                Top Struggling Chapters Across Platform
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
                Chapters where students encounter the highest rate of wrong answers or AI inquiries
              </p>

              <div className="space-y-2.5">
                {(overview?.top_struggling_chapters && overview.top_struggling_chapters.length > 0
                  ? overview.top_struggling_chapters
                  : [
                      {
                        chapter_id: "c1",
                        chapter_name_bn: "অধ্যায় ৪: বীজগণিতীয় সূত্রাবলি ও প্রয়োগ",
                        chapter_name_en: "Algebraic Formulae",
                        chapter_number: 4,
                        subject_slug: "math",
                        class_level: 8,
                        average_mastery: 0.44,
                        students_count: 14,
                        status: "needs_practice",
                      },
                      {
                        chapter_id: "c2",
                        chapter_name_bn: "অধ্যায় ১: প্যাটার্ন",
                        chapter_name_en: "Patterns",
                        chapter_number: 1,
                        subject_slug: "math",
                        class_level: 8,
                        average_mastery: 0.52,
                        students_count: 12,
                        status: "needs_practice",
                      },
                      {
                        chapter_id: "c3",
                        chapter_name_bn: "অধ্যায় ২: জীবের বৃদ্ধি ও বংশগতি",
                        chapter_name_en: "Growth and Heredity",
                        chapter_number: 2,
                        subject_slug: "science",
                        class_level: 8,
                        average_mastery: 0.56,
                        students_count: 9,
                        status: "needs_practice",
                      },
                    ]
                ).map((chap, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 flex items-center justify-between"
                  >
                    <div>
                      <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                        {chap.chapter_name_bn}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        Class {chap.class_level} • {chap.subject_slug.toUpperCase()} • {chap.students_count} students
                      </div>
                    </div>
                    <div className="text-right">
                      <span className="text-xs font-bold text-rose-600 dark:text-rose-400">
                        {Math.round(chap.average_mastery * 100)}%
                      </span>
                      <div className="text-[10px] text-slate-400">Needs Practice</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-rose-500" />
                Persistent Gap Concepts (High AI Inquiries & Repeat Errors)
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
                Concepts triggering repeat AI questions within 3 days or quiz failures
              </p>

              <div className="space-y-2.5">
                {(overview?.top_struggling_concepts && overview.top_struggling_concepts.length > 0
                  ? overview.top_struggling_concepts
                  : [
                      { concept: "দ্বিপদী রাশির বর্গ নির্ণয় (Square of Binomials)", negative_signals_count: 28 },
                      { concept: "মৌলিক উৎপাদক ও লসাগু-গসাগু (Prime Factors & LCM)", negative_signals_count: 21 },
                      { concept: "কোষ বিভাজন পর্যায়সমূহ (Stages of Cell Division)", negative_signals_count: 17 },
                      { concept: "সরল মুনাফা ও চক্রবৃদ্ধি মূলধন (Simple vs Compound Interest)", negative_signals_count: 14 },
                    ]
                ).map((c, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg border border-rose-100 dark:border-rose-950/40 bg-rose-50/50 dark:bg-rose-950/20 flex items-center justify-between"
                  >
                    <span className="text-xs font-medium text-slate-800 dark:text-slate-200">
                      {c.concept}
                    </span>
                    <span className="text-xs font-semibold px-2 py-0.5 rounded bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-300">
                      {c.negative_signals_count} gaps
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB 2: STUDENTS DIRECTORY & WEAKNESS DRILLDOWN */}
      {activeSubTab === "students" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search student by name, weak subjects, or focus..."
                className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            <select
              value={classFilter}
              onChange={(e) => setClassFilter(e.target.value)}
              className="px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200"
            >
              <option value="all">All Classes</option>
              <option value="6">Class 6 (৬ষ্ঠ)</option>
              <option value="7">Class 7 (৭ম)</option>
              <option value="8">Class 8 (৮ম)</option>
              <option value="9">Class 9 (৯ম)</option>
              <option value="10">Class 10 (১০ম)</option>
            </select>
          </div>

          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-600 dark:text-slate-300">
                <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-700 dark:text-slate-300 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-3 px-4 font-semibold">Student Name</th>
                    <th className="py-3 px-3 font-semibold">Class / Medium</th>
                    <th className="py-3 px-3 font-semibold">Declared Weakness</th>
                    <th className="py-3 px-3 font-semibold">Focus Subjects</th>
                    <th className="py-3 px-3 font-semibold">Mastery Score</th>
                    <th className="py-3 px-3 font-semibold">Signals</th>
                    <th className="py-3 px-3 font-semibold">Revision Due</th>
                    <th className="py-3 px-4 font-semibold text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {filteredStudents.length > 0 ? (
                    filteredStudents.map((s) => (
                      <tr key={s.id} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors">
                        <td className="py-3 px-4 font-medium text-slate-900 dark:text-white">
                          {s.name}
                        </td>
                        <td className="py-3 px-3">
                          Class {s.class_level || 8} ({s.medium || "Bangla"})
                        </td>
                        <td className="py-3 px-3">
                          {s.weak_subjects.length > 0 ? (
                            <div className="flex flex-wrap gap-1">
                              {s.weak_subjects.map((w, i) => (
                                <span
                                  key={i}
                                  className="px-1.5 py-0.5 rounded bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-300 text-[10px] font-medium"
                                >
                                  {w}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-slate-400 text-[11px]">—</span>
                          )}
                        </td>
                        <td className="py-3 px-3">
                          {s.focus_subjects.length > 0 ? (
                            <div className="flex flex-wrap gap-1">
                              {s.focus_subjects.map((f, i) => (
                                <span
                                  key={i}
                                  className="px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300 text-[10px] font-medium"
                                >
                                  {f}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-slate-400 text-[11px]">—</span>
                          )}
                        </td>
                        <td className="py-3 px-3 font-semibold">
                          <span
                            className={
                              s.overall_mastery >= 0.8
                                ? "text-emerald-600 dark:text-emerald-400"
                                : s.overall_mastery < 0.6
                                ? "text-rose-600 dark:text-rose-400"
                                : "text-amber-600 dark:text-amber-400"
                            }
                          >
                            {Math.round(s.overall_mastery * 100)}%
                          </span>
                        </td>
                        <td className="py-3 px-3">{s.signals_count}</td>
                        <td className="py-3 px-3">
                          {s.revision_items_due > 0 ? (
                            <span className="text-amber-600 font-semibold">{s.revision_items_due} items</span>
                          ) : (
                            <span className="text-slate-400">0</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => handleInspectStudent(s.id)}
                            className="px-2.5 py-1 text-[11px] font-medium text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950 rounded transition-colors"
                          >
                            Inspect
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-slate-400">
                        No students matching the search filter.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Student Detail Modal */}
          {selectedStudentDetail && (
            <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-6 shadow-2xl space-y-5">
                <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-4">
                  <div>
                    <h3 className="text-base font-bold text-slate-900 dark:text-white">
                      {selectedStudentDetail.name} — Mastery Analysis
                    </h3>
                    <p className="text-xs text-slate-500">
                      Class {selectedStudentDetail.class_level} • Overall Mastery:{" "}
                      {Math.round(selectedStudentDetail.overall_mastery * 100)}%
                    </p>
                  </div>
                  <button
                    onClick={() => setSelectedStudentDetail(null)}
                    className="text-slate-400 hover:text-slate-600 dark:hover:text-white text-sm"
                  >
                    ✕ Close
                  </button>
                </div>

                {/* Top Weaknesses */}
                <div>
                  <h4 className="text-xs font-semibold text-rose-600 dark:text-rose-400 mb-2 flex items-center gap-1.5">
                    <TrendingDown className="w-3.5 h-3.5" />
                    Identified Topics Needing Practice
                  </h4>
                  {selectedStudentDetail.top_weaknesses.length > 0 ? (
                    <div className="space-y-2">
                      {selectedStudentDetail.top_weaknesses.map((w: any, idx: number) => (
                        <div
                          key={idx}
                          className="p-2.5 rounded-lg border border-rose-100 dark:border-rose-950/40 bg-rose-50/50 dark:bg-rose-950/20 text-xs flex justify-between"
                        >
                          <div>
                            <span className="font-semibold text-slate-800 dark:text-slate-200">
                              {w.chapter_name}
                            </span>
                            <span className="text-slate-500 ml-1.5">({w.subject})</span>
                          </div>
                          <span className="font-bold text-rose-600">{Math.round(w.score * 100)}%</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-slate-400">No severe weak topics recorded.</p>
                  )}
                </div>

                {/* Top Strengths */}
                <div>
                  <h4 className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 mb-2 flex items-center gap-1.5">
                    <TrendingUp className="w-3.5 h-3.5" />
                    Mastered Topics
                  </h4>
                  {selectedStudentDetail.top_strengths.length > 0 ? (
                    <div className="space-y-2">
                      {selectedStudentDetail.top_strengths.map((s: any, idx: number) => (
                        <div
                          key={idx}
                          className="p-2.5 rounded-lg border border-emerald-100 dark:border-emerald-950/40 bg-emerald-50/50 dark:bg-emerald-950/20 text-xs flex justify-between"
                        >
                          <div>
                            <span className="font-semibold text-slate-800 dark:text-slate-200">
                              {s.chapter_name}
                            </span>
                            <span className="text-slate-500 ml-1.5">({s.subject})</span>
                          </div>
                          <span className="font-bold text-emerald-600">{Math.round(s.score * 100)}%</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-slate-400">Building initial mastery signals.</p>
                  )}
                </div>

                {/* Recent Signals */}
                <div>
                  <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-2 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5" />
                    Recent Learning Signals
                  </h4>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {selectedStudentDetail.recent_signals.map((sig: any, idx: number) => (
                      <div
                        key={idx}
                        className="text-[11px] p-2 rounded bg-slate-50 dark:bg-slate-800 flex justify-between"
                      >
                        <span className="font-mono text-slate-600 dark:text-slate-300">{sig.source}</span>
                        <span className="text-slate-400">
                          weight: {sig.weight > 0 ? `+${sig.weight}` : sig.weight}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* SUB-TAB 3: LLM USAGE & COSTS */}
      {activeSubTab === "usage" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4">
              <div className="text-xs font-medium text-slate-500">Total Chat Messages</div>
              <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
                {usage?.total_messages ?? 0}
              </div>
              <div className="text-[11px] text-slate-400 mt-1">Buddy AI Tutor conversations</div>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4">
              <div className="text-xs font-medium text-slate-500">Total Tokens Processed</div>
              <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
                {(usage?.total_tokens ?? 0).toLocaleString()}
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                In: {(usage?.total_tokens_in ?? 0).toLocaleString()} • Out: {(usage?.total_tokens_out ?? 0).toLocaleString()}
              </div>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4">
              <div className="text-xs font-medium text-slate-500">Average LLM Latency</div>
              <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
                {usage?.average_latency_ms ?? 280} ms
              </div>
              <div className="text-[11px] text-emerald-600 mt-1 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> Fast streaming response
              </div>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4">
              <div className="text-xs font-medium text-slate-500">Estimated API Cost</div>
              <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
                ${usage?.estimated_cost_usd?.toFixed(4) ?? "0.0000"}
              </div>
              <div className="text-[11px] text-slate-500 mt-1">
                ≈ ৳{usage?.estimated_cost_bdt?.toFixed(2) ?? "0.00"} BDT
              </div>
            </div>
          </div>

          {/* Model Breakdown */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
              <Zap className="w-4 h-4 text-indigo-500" />
              Usage by Model Identifier
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-600 dark:text-slate-300">
                <thead className="bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">Model</th>
                    <th className="py-2.5 px-3">Messages</th>
                    <th className="py-2.5 px-3">Tokens In</th>
                    <th className="py-2.5 px-3">Tokens Out</th>
                    <th className="py-2.5 px-3">Total Tokens</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {usage && Object.keys(usage.by_model).length > 0 ? (
                    Object.entries(usage.by_model).map(([model, mStats], idx) => (
                      <tr key={idx}>
                        <td className="py-2.5 px-3 font-mono font-medium text-slate-900 dark:text-white">
                          {model}
                        </td>
                        <td className="py-2.5 px-3">{mStats.messages}</td>
                        <td className="py-2.5 px-3">{mStats.tokens_in.toLocaleString()}</td>
                        <td className="py-2.5 px-3">{mStats.tokens_out.toLocaleString()}</td>
                        <td className="py-2.5 px-3 font-semibold">{mStats.total_tokens.toLocaleString()}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-slate-400">
                        No model turns logged in this timeframe.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB 4: SIGNALS TELEMETRY STREAM */}
      {activeSubTab === "signals" && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
          <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Live Learning Signal Feed</h3>
              <p className="text-xs text-slate-500">Atomic learning signals emitted by student interactions</p>
            </div>
            <span className="text-xs px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
              Showing latest {signals.length} signals
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600 dark:text-slate-300">
              <thead className="bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-2.5 px-4">Timestamp</th>
                  <th className="py-2.5 px-3">Signal Type</th>
                  <th className="py-2.5 px-3">Weight Impact</th>
                  <th className="py-2.5 px-3">Student ID</th>
                  <th className="py-2.5 px-3">Reference / Target</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono text-[11px]">
                {signals.length > 0 ? (
                  signals.map((sig) => (
                    <tr key={sig.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                      <td className="py-2 px-4 text-slate-400 font-sans">
                        {new Date(sig.created_at).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                        })}
                      </td>
                      <td className="py-2 px-3 font-semibold text-slate-900 dark:text-white">
                        {sig.source}
                      </td>
                      <td className="py-2 px-3">
                        <span
                          className={`font-bold ${
                            sig.weight > 0 ? "text-emerald-600" : "text-rose-600"
                          }`}
                        >
                          {sig.weight > 0 ? `+${sig.weight}` : sig.weight}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-slate-500">{sig.student_id.slice(0, 8)}...</td>
                      <td className="py-2 px-3 text-slate-400 truncate max-w-xs">
                        {sig.concept_id || sig.ref_id || "chapter"}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="py-6 text-center text-slate-400 font-sans">
                      No signals recorded yet. Signals populate as students take quizzes, ask questions, or study.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
