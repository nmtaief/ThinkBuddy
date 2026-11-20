"use client";

import React, { useState, useEffect } from "react";
import {
  Calendar,
  Clock,
  Sparkles,
  BookOpen,
  TrendingUp,
  RotateCcw,
  Flag,
  ChevronRight,
  Sliders,
  Plus,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
} from "lucide-react";
import { Language, toBengaliDigits } from "@/lib/i18n";
import { TodayPayload } from "@/lib/types";
import { DayPlan, DayScheduleItem } from "@/lib/allocation-engine";
import {
  ExamTimetableEntry,
  ExamSeriesType,
  SubjectSyllabusInput,
  detectPlannerPhase,
  EXAM_MODE_CONFIG_V1,
} from "@/lib/exam-mode-engine";

interface PlanTimelineViewProps {
  todayData: TodayPayload | null;
  lang?: Language;
  onNavigateTab: (tab: string) => void;
}

function makeItem(
  slug: string,
  name_bn: string,
  name_en: string,
  total_minutes: number,
  study_minutes: number,
  revision_minutes: number,
  is_weak = false
): DayScheduleItem {
  return {
    subject_slug: slug,
    subject_name_bn: name_bn,
    subject_name_en: name_en,
    is_weak,
    is_focus: is_weak,
    total_minutes,
    study_minutes,
    revision_minutes,
  };
}

const DEFAULT_7_DAY_SCHEDULE: DayPlan[] = [
  {
    day_id: "sat",
    day_name_bn: "শনিবার",
    day_name_en: "Saturday",
    is_weekend: true,
    is_school_day: false,
    school_status_label_bn: "স্কুল বন্ধ (ছুটির দিন)",
    special_revision_block_minutes: 120,
    daily_total_minutes: 225,
    daily_study_minutes: 79,
    daily_revision_minutes: 26,
    items: [
      makeItem("math", "সাধারণ গণিত", "Mathematics", 60, 45, 15, true),
      makeItem("english", "English", "English", 45, 34, 11),
    ],
  },
  {
    day_id: "sun",
    day_name_bn: "রবিবার",
    day_name_en: "Sunday",
    is_weekend: false,
    is_school_day: true,
    school_status_label_bn: "স্কুল দিন",
    special_revision_block_minutes: 0,
    daily_total_minutes: 150,
    daily_study_minutes: 112,
    daily_revision_minutes: 38,
    items: [
      makeItem("math", "সাধারণ গণিত", "Mathematics", 60, 45, 15, true),
      makeItem("science", "সাধারণ বিজ্ঞান", "Science", 45, 34, 11),
      makeItem("ict", "তথ্য ও যোগাযোগ প্রযুক্তি", "ICT", 45, 33, 12),
    ],
  },
  {
    day_id: "mon",
    day_name_bn: "সোমবার",
    day_name_en: "Monday",
    is_weekend: false,
    is_school_day: true,
    school_status_label_bn: "স্কুল দিন",
    special_revision_block_minutes: 0,
    daily_total_minutes: 150,
    daily_study_minutes: 112,
    daily_revision_minutes: 38,
    items: [
      makeItem("math", "সাধারণ গণিত", "Mathematics", 60, 45, 15, true),
      makeItem("bangla", "বাংলা", "Bangla", 45, 34, 11),
      makeItem("bgs", "বাংলাদেশ ও বিশ্বপরিচয়", "BGS", 45, 33, 12),
    ],
  },
  {
    day_id: "tue",
    day_name_bn: "মঙ্গলবার",
    day_name_en: "Tuesday",
    is_weekend: false,
    is_school_day: true,
    school_status_label_bn: "স্কুল দিন",
    special_revision_block_minutes: 0,
    daily_total_minutes: 150,
    daily_study_minutes: 112,
    daily_revision_minutes: 38,
    items: [
      makeItem("science", "সাধারণ বিজ্ঞান", "Science", 60, 45, 15),
      makeItem("english", "English", "English", 45, 34, 11),
      makeItem("bgs", "বাংলাদেশ ও বিশ্বপরিচয়", "BGS", 45, 33, 12),
    ],
  },
  {
    day_id: "wed",
    day_name_bn: "বুধবার",
    day_name_en: "Wednesday",
    is_weekend: false,
    is_school_day: true,
    school_status_label_bn: "স্কুল দিন",
    special_revision_block_minutes: 0,
    daily_total_minutes: 150,
    daily_study_minutes: 112,
    daily_revision_minutes: 38,
    items: [
      makeItem("math", "সাধারণ গণিত", "Mathematics", 60, 45, 15, true),
      makeItem("science", "সাধারণ বিজ্ঞান", "Science", 45, 34, 11),
      makeItem("ict", "তথ্য ও যোগাযোগ প্রযুক্তি", "ICT", 45, 33, 12),
    ],
  },
  {
    day_id: "thu",
    day_name_bn: "বৃহস্পতিবার",
    day_name_en: "Thursday",
    is_weekend: false,
    is_school_day: true,
    school_status_label_bn: "স্কুল দিন",
    special_revision_block_minutes: 0,
    daily_total_minutes: 150,
    daily_study_minutes: 112,
    daily_revision_minutes: 38,
    items: [
      makeItem("math", "সাধারণ গণিত", "Mathematics", 60, 45, 15, true),
      makeItem("bangla", "বাংলা", "Bangla", 45, 34, 11),
      makeItem("english", "English", "English", 45, 33, 12),
    ],
  },
  {
    day_id: "fri",
    day_name_bn: "শুক্রবার",
    day_name_en: "Friday",
    is_weekend: true,
    is_school_day: false,
    school_status_label_bn: "স্কুল বন্ধ (ছুটির দিন)",
    special_revision_block_minutes: 120,
    daily_total_minutes: 225,
    daily_study_minutes: 79,
    daily_revision_minutes: 26,
    items: [
      makeItem("science", "সাধারণ বিজ্ঞান", "Science", 60, 45, 15),
      makeItem("bgs", "বাংলাদেশ ও বিশ্বপরিচয়", "BGS", 45, 34, 11),
    ],
  },
];

const DEFAULT_TIMETABLE: ExamTimetableEntry[] = [
  {
    id: "tt_math_01",
    series: "school_exam",
    subject_slug: "math",
    subject_name_bn: "সাধারণ গণিত",
    subject_name_en: "General Math",
    paper: "১ম ও ২য় পত্র",
    date: new Date(Date.now() + 5 * 86400000).toISOString().split("T")[0],
    start_time: "10:00",
    end_time: "13:00",
    marks_weight: 100,
  },
  {
    id: "tt_sci_02",
    series: "school_exam",
    subject_slug: "science",
    subject_name_bn: "সাধারণ বিজ্ঞান",
    subject_name_en: "General Science",
    date: new Date(Date.now() + 8 * 86400000).toISOString().split("T")[0],
    start_time: "10:00",
    end_time: "13:00",
    marks_weight: 100,
  },
];

const DEFAULT_SYLLABUS: SubjectSyllabusInput[] = [
  {
    subject_slug: "math",
    has_remaining_syllabus: true,
    chapters: [
      { number: 1, title_bn: "প্যাটার্ন", status: "covered", estimated_hours: 4.0, mastery_score: 0.8 },
      { number: 2, title_bn: "মুনাফা ও চক্রবৃদ্ধি মূলধন", status: "partly", estimated_hours: 5.0, mastery_score: 0.35, why_sheet_reason: "কেন: গতবার ৫টির মধ্যে ২টি সঠিক; আরও অনুশীলন দরকার।" },
      { number: 3, title_bn: "বীজগণিতীয় সূত্রাবলি ও প্রয়োগ", status: "left", estimated_hours: 5.0, mastery_score: 0.4 },
      { number: 9, title_bn: "পিথাগোরাসের উপপাদ্য", status: "covered", estimated_hours: 4.0, mastery_score: 0.85 },
    ],
  },
  {
    subject_slug: "science",
    has_remaining_syllabus: false,
    chapters: [
      { number: 4, title_bn: "উদ্ভিদে বংশবৃদ্ধি ও পরাগায়ন", status: "covered", estimated_hours: 4.0, mastery_score: 0.45 },
      { number: 7, title_bn: "মহাকর্ষ ও অভিকর্ষ", status: "covered", estimated_hours: 4.0, mastery_score: 0.8 },
    ],
  },
];

export default function PlanTimelineView({
  todayData,
  lang = "bn",
  onNavigateTab,
}: PlanTimelineViewProps) {
  const [schedule, setSchedule] = useState<DayPlan[]>(DEFAULT_7_DAY_SCHEDULE);
  const [activeDayIndex, setActiveDayIndex] = useState<number>(() => {
    const day = new Date().getDay();
    const map = [1, 2, 3, 4, 5, 6, 0];
    return map[day];
  });
  const [viewMode, setViewMode] = useState<"timetable" | "subjects" | "exam_day" | "syllabus">("timetable");

  // Exam Timetable & Syllabus State
  const [timetable, setTimetable] = useState<ExamTimetableEntry[]>(() => {
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem("tb_exam_timetable");
        if (stored) return JSON.parse(stored);
      } catch {}
    }
    return DEFAULT_TIMETABLE;
  });

  const [syllabusList, setSyllabusList] = useState<SubjectSyllabusInput[]>(() => {
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem("tb_exam_syllabus");
        if (stored) return JSON.parse(stored);
      } catch {}
    }
    return DEFAULT_SYLLABUS;
  });

  // Hours & Safety Settings
  const [examWeekHours, setExamWeekHours] = useState<number>(6.0);
  const [dailySafetyCapWarning, setDailySafetyCapWarning] = useState<string | null>(null);

  // New exam entry form fields
  const [newSeries, setNewSeries] = useState<ExamSeriesType>("school_exam");
  const [newSubjectBn, setNewSubjectBn] = useState("ইংরেজি (English)");
  const [newSubjectSlug, setNewSubjectSlug] = useState("english");
  const [newExamDate, setNewExamDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 10);
    return d.toISOString().split("T")[0];
  });
  const [newStartTime, setNewStartTime] = useState("10:00");
  const [newEndTime, setNewEndTime] = useState("13:00");

  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem("tb_active_schedule");
        if (stored) {
          const parsed = JSON.parse(stored);
          if (Array.isArray(parsed) && parsed.length === 7) {
            setSchedule(parsed);
          }
        }
      } catch {}
    }
  }, []);

  // Save timetable & sync with TodayView
  const saveTimetable = (updated: ExamTimetableEntry[]) => {
    setTimetable(updated);
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("tb_exam_timetable", JSON.stringify(updated));
        window.dispatchEvent(new Event("tb_exam_plan_updated"));
      } catch {}
    }
  };

  // Save syllabus & sync with TodayView
  const saveSyllabus = (updated: SubjectSyllabusInput[]) => {
    setSyllabusList(updated);
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("tb_exam_syllabus", JSON.stringify(updated));
        window.dispatchEvent(new Event("tb_exam_plan_updated"));
      } catch {}
    }
  };

  const handleAddExam = () => {
    if (!newSubjectBn.trim() || !newExamDate) return;
    const newEntry: ExamTimetableEntry = {
      id: `tt_${Date.now()}`,
      series: newSeries,
      subject_slug: newSubjectSlug,
      subject_name_bn: newSubjectBn,
      subject_name_en: newSubjectSlug,
      date: newExamDate,
      start_time: newStartTime,
      end_time: newEndTime,
      marks_weight: 100,
    };
    saveTimetable([...timetable, newEntry]);
  };

  const handleDeleteExam = (id: string) => {
    const filtered = timetable.filter((t) => t.id !== id);
    saveTimetable(filtered);
  };

  const handleToggleSyllabusRemaining = (subjectSlug: string) => {
    const updated = syllabusList.map((s) =>
      s.subject_slug === subjectSlug ? { ...s, has_remaining_syllabus: !s.has_remaining_syllabus } : s
    );
    saveSyllabus(updated);
  };

  const handleUpdateChapterStatus = (
    subjectSlug: string,
    chapterNumber: number,
    newStatus: "covered" | "partly" | "left"
  ) => {
    const updated = syllabusList.map((s) => {
      if (s.subject_slug !== subjectSlug) return s;
      const updatedChapters = s.chapters.map((ch) =>
        ch.number === chapterNumber ? { ...ch, status: newStatus } : ch
      );
      return { ...s, chapters: updatedChapters };
    });
    saveSyllabus(updated);
  };

  const handleHoursChange = (val: number) => {
    if (val > EXAM_MODE_CONFIG_V1.daily_safety_cap_hours) {
      setExamWeekHours(EXAM_MODE_CONFIG_V1.daily_safety_cap_hours);
      setDailySafetyCapWarning(
        `পড়ার সময় সর্বোচ্চ দৈনিক নিরাপদ সীমা ${toBengaliDigits(EXAM_MODE_CONFIG_V1.daily_safety_cap_hours)} ঘণ্টায় সীমাবদ্ধ করা হয়েছে (পর্যাপ্ত ঘুম ও স্বাস্থ্য সুরক্ষার জন্য)।`
      );
    } else {
      setExamWeekHours(val);
      setDailySafetyCapWarning(null);
    }
  };

  // Phase detection
  const currentPhase = detectPlannerPhase(timetable, new Date());
  const examInfo = todayData?.exam_countdown || {
    exam_name: timetable[0]?.subject_name_bn || "টার্গেট পরীক্ষা",
    days_left: currentPhase.days_to_first_exam || 14,
    total_chapters: 55,
  };

  const daysLeft = currentPhase.days_to_first_exam ?? examInfo.days_left ?? 14;
  const currentDayPlan = schedule[activeDayIndex] || schedule[0];

  const dayLabels = [
    { id: "sat", name_bn: "শনিবার", name_en: "Saturday", is_weekend: true },
    { id: "sun", name_bn: "রবিবার", name_en: "Sunday", is_weekend: false },
    { id: "mon", name_bn: "সোমবার", name_en: "Monday", is_weekend: false },
    { id: "tue", name_bn: "মঙ্গলবার", name_en: "Tuesday", is_weekend: false },
    { id: "wed", name_bn: "বুধবার", name_en: "Wednesday", is_weekend: false },
    { id: "thu", name_bn: "বৃহস্পতিবার", name_en: "Thursday", is_weekend: false },
    { id: "fri", name_bn: "শুক্রবার", name_en: "Friday", is_weekend: true },
  ];

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-10">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
              {currentPhase.badge_label_bn}
            </span>
            <span className="text-xs text-slate-500">
              {lang === "bn" ? "পরীক্ষা সপ্তাহ ও পূর্ণাঙ্গ পরিকল্পনা" : "Exam Week & Study Schedule"}
            </span>
          </div>
          <h2 className="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
            <Clock className="w-6 h-6 text-indigo-600" />
            {lang === "bn" ? "সময়রেখা ও পরীক্ষার রুটিন" : "Timeline & Exam Routine"}
          </h2>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 mt-1">
            {currentPhase.explanation_bn}
          </p>
        </div>

        {/* Quick Actions */}
        <div className="flex items-center gap-2 self-start sm:self-auto flex-wrap">
          <button
            onClick={() => onNavigateTab("today")}
            className="flex items-center gap-1.5 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-md transition-all cursor-pointer"
          >
            <Calendar className="w-4 h-4" />
            <span>{lang === "bn" ? "আজকের পড়ার কাজ" : "Go to Today's Tasks"}</span>
          </button>
        </div>
      </div>

      {/* Safety Cap Notification if student enters excessive hours */}
      {dailySafetyCapWarning && (
        <div className="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 flex items-center gap-2 text-xs font-bold text-amber-900 dark:text-amber-200 shadow-sm">
          <ShieldAlert className="w-4 h-4 text-amber-600 flex-shrink-0" />
          <span>{dailySafetyCapWarning}</span>
        </div>
      )}

      {/* Hero Exam Milestone & Roadmap */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Countdown card */}
        <div className="bg-gradient-to-br from-indigo-500 to-indigo-700 text-white rounded-2xl p-5 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-indigo-100 text-xs font-semibold">
            <span className="uppercase tracking-wider">
              {lang === "bn" ? "টার্গেট পরীক্ষা" : "Upcoming Exam"}
            </span>
            <Flag className="w-4 h-4 text-indigo-200" />
          </div>
          <div className="text-xl font-black">{examInfo.exam_name}</div>
          <div className="flex items-baseline gap-2 pt-1">
            <span className="text-3xl sm:text-4xl font-extrabold tracking-tight">
              {lang === "bn" ? toBengaliDigits(daysLeft) : daysLeft}
            </span>
            <span className="text-sm text-indigo-100 font-semibold">
              {lang === "bn" ? "দিন বাকি" : "Days Left"}
            </span>
          </div>
          <div className="w-full bg-white/20 h-1.5 rounded-full overflow-hidden mt-2">
            <div
              className="bg-white h-full rounded-full"
              style={{ width: `${Math.min(100, Math.max(10, (1 - daysLeft / 60) * 100))}%` }}
            />
          </div>
        </div>

        {/* Study Strategy card */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-xs font-bold text-slate-500 uppercase tracking-wider">
            <span>{lang === "bn" ? "পড়াশোনার কৌশল ও নিরাপত্তা" : "Pacing & Safety"}</span>
            <Sparkles className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            <span>
              {currentPhase.is_exam_mode
                ? lang === "bn"
                  ? "নিবেদিত গ্যাপ মাইক্রো-প্ল্যান সক্রিয়"
                  : "Gap Micro-Plan Active"
                : lang === "bn"
                ? "সুষম গতি (Balanced)"
                : "Balanced Pace"}
            </span>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
            {lang === "bn"
              ? "নিরাপদ নীতিমালা: সর্বনিম্ন ৭ ঘণ্টা ঘুম, ২ ঘণ্টার পরীক্ষা প্রস্তুতি বাফার এবং ৫০ মিনিট পড়া + ১০ মিনিট বিরতির নিয়ম সুরক্ষিত।"
              : "Safety rules: Minimum 7h sleep, 2h exam buffers, and 50m study + 10m break cycles guaranteed."}
          </p>
        </div>

        {/* Milestone Phasing card */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-xs font-bold text-slate-500 uppercase tracking-wider">
            <span>{lang === "bn" ? "পরিকল্পনার ধাপসমূহ" : "Milestone Phases"}</span>
            <TrendingUp className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="space-y-1.5 text-xs text-slate-700 dark:text-slate-300">
            <div className="flex items-center justify-between">
              <span className="font-semibold">{lang === "bn" ? "১. মূল সিলেবাস অধ্যয়ন" : "1. Core Syllabus"}</span>
              <span className="text-emerald-600 font-bold">সম্পন্ন</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="font-semibold">{lang === "bn" ? "২. শুধু রিভিশন (শেষ ৭ দিন)" : "2. Revision Week"}</span>
              <span className="text-indigo-600 font-bold">
                {currentPhase.phase === "revision_week" ? "চলমান" : "পরবর্তী"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="font-semibold">{lang === "bn" ? "৩. পরীক্ষার গ্যাপ মাইক্রো-প্ল্যান" : "3. Gap Micro-Plans"}</span>
              <span className="text-rose-600 font-bold">
                {currentPhase.phase === "exam_period" ? "সক্রিয়" : "পরীক্ষার সময়"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Mode Explorer Card with 4 Interactive Tabs */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 sm:p-6 shadow-sm space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 dark:border-slate-800 pb-4">
          <div>
            <h3 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Calendar className="w-5 h-5 text-indigo-600" />
              {lang === "bn" ? "সময়সূচি ও সিলেবাস নিয়ন্ত্রণ" : "Exam Timetable & Syllabus Controls"}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              {lang === "bn"
                ? "পরীক্ষার তারিখ, সময়সূচি এবং বাকি সিলেবাস পরিবর্তন করলে স্বয়ংক্রিয়ভাবে রুটিন হালনাগাদ হবে"
                : "Edit exam dates, start/end times and syllabus status to automatically adapt your routine"}
            </p>
          </div>

          {/* 4 Existing Mode Toggles (Zero New Pages / Zero External Links) */}
          <div className="flex items-center gap-1 p-1 bg-slate-100 dark:bg-slate-800 rounded-xl self-start sm:self-auto flex-wrap">
            <button
              onClick={() => setViewMode("timetable")}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                viewMode === "timetable"
                  ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm"
                  : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
              }`}
            >
              {lang === "bn" ? "দিনভিত্তিক শিডিউল" : "Day-by-Day"}
            </button>
            <button
              onClick={() => setViewMode("subjects")}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                viewMode === "subjects"
                  ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm"
                  : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
              }`}
            >
              {lang === "bn" ? "বিষয়ভিত্তিক বরাদ্দ" : "Subject Breakdown"}
            </button>
            <button
              onClick={() => setViewMode("exam_day")}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                viewMode === "exam_day"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-indigo-600 hover:text-indigo-800 dark:text-indigo-400"
              }`}
            >
              {lang === "bn" ? "পরীক্ষার রুটিন (Timetable)" : "Exam Timetable"}
            </button>
            <button
              onClick={() => setViewMode("syllabus")}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                viewMode === "syllabus"
                  ? "bg-amber-600 text-white shadow-sm"
                  : "text-amber-600 hover:text-amber-800 dark:text-amber-400"
              }`}
            >
              {lang === "bn" ? "সিলেবাস ও বাকি পড়া" : "Syllabus Status"}
            </button>
          </div>
        </div>

        {/* 1. Day-by-Day View */}
        {viewMode === "timetable" && (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-7 gap-2">
              {dayLabels.map((d, idx) => {
                const isSelected = activeDayIndex === idx;
                const p = schedule[idx];
                const totalM = p ? p.daily_total_minutes : 180;

                return (
                  <button
                    key={d.id}
                    onClick={() => setActiveDayIndex(idx)}
                    className={`p-3 rounded-xl border text-center transition-all cursor-pointer flex flex-col items-center justify-center gap-1 ${
                      isSelected
                        ? "border-indigo-600 bg-indigo-50 dark:bg-indigo-950/40 ring-2 ring-indigo-500"
                        : "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-slate-300 dark:hover:border-slate-700"
                    }`}
                  >
                    <span
                      className={`text-xs font-bold ${
                        isSelected
                          ? "text-indigo-700 dark:text-indigo-300"
                          : "text-slate-800 dark:text-slate-200"
                      }`}
                    >
                      {lang === "bn" ? d.name_bn : d.name_en}
                    </span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                        d.is_weekend
                          ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                          : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400"
                      }`}
                    >
                      {d.is_weekend
                        ? lang === "bn"
                          ? "ছুটি (২ঘণ্টা রিভিশন)"
                          : "Holiday"
                        : lang === "bn"
                        ? "স্কুল দিন"
                        : "School"}
                    </span>
                    <span className="text-[11px] font-bold text-slate-500 dark:text-slate-400 mt-0.5">
                      {lang === "bn" ? toBengaliDigits(totalM) : totalM} {lang === "bn" ? "মি" : "m"}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Selected Day Details Card */}
            {currentDayPlan && (
              <div className="rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 p-5 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-200 dark:border-slate-700 pb-3">
                  <div className="flex items-center gap-2">
                    <h4 className="text-base font-extrabold text-slate-900 dark:text-white">
                      {lang === "bn"
                        ? dayLabels[activeDayIndex]?.name_bn
                        : dayLabels[activeDayIndex]?.name_en}
                    </h4>
                    <span
                      className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                        currentDayPlan.is_weekend
                          ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                          : "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300"
                      }`}
                    >
                      {currentDayPlan.is_weekend
                        ? lang === "bn"
                          ? "স্কুল বন্ধ (ছুটির দিন)"
                          : "Holiday / Weekend"
                        : lang === "bn"
                        ? "স্কুলের দিন"
                        : "School Day"}
                    </span>
                  </div>

                  <div className="text-xs text-slate-600 dark:text-slate-300 font-medium">
                    {lang === "bn" ? "মোট পড়ার বাজেট: " : "Daily Budget: "}
                    <strong className="text-indigo-600 dark:text-indigo-400 font-bold">
                      {Math.floor(currentDayPlan.daily_total_minutes / 60)} ঘণ্টা{" "}
                      {currentDayPlan.daily_total_minutes % 60} মিনিট
                    </strong>{" "}
                    • {lang === "bn" ? "৭৫% নতুন পড়া + ২৫% রিভিশন" : "75% Study + 25% Revision"}
                  </div>
                </div>

                {/* Subject Study Blocks */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {currentDayPlan.items.map((item, idx) => (
                    <div
                      key={idx}
                      className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2 shadow-sm"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-extrabold text-slate-900 dark:text-white">
                          {item.subject_name_bn}
                        </span>
                        <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400">
                          {lang === "bn" ? toBengaliDigits(item.total_minutes) : item.total_minutes}{" "}
                          {lang === "bn" ? "মি" : "min"}
                        </span>
                      </div>

                      <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden flex">
                        <div
                          className="bg-indigo-600 h-full"
                          style={{
                            width: `${Math.round((item.study_minutes / item.total_minutes) * 100)}%`,
                          }}
                          title={`নতুন পড়া: ${item.study_minutes} মি`}
                        />
                        <div
                          className="bg-emerald-500 h-full"
                          style={{
                            width: `${Math.round((item.revision_minutes / item.total_minutes) * 100)}%`,
                          }}
                          title={`স্পেসড রিভিশন: ${item.revision_minutes} মি`}
                        />
                      </div>

                      <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 pt-0.5">
                        <span className="flex items-center gap-1">
                          <BookOpen className="w-3 h-3 text-indigo-500" />
                          {lang === "bn"
                            ? `পড়া: ${toBengaliDigits(item.study_minutes)} মি (৭৫%)`
                            : `Study: ${item.study_minutes}m`}
                        </span>
                        <span className="flex items-center gap-1">
                          <RotateCcw className="w-3 h-3 text-emerald-500" />
                          {lang === "bn"
                            ? `রিভিশন: ${toBengaliDigits(item.revision_minutes)} মি (২৫%)`
                            : `Rev: ${item.revision_minutes}m`}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* 2. Subject Breakdown View */}
        {viewMode === "subjects" && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-bold uppercase tracking-wider border-b border-slate-200 dark:border-slate-700">
                <tr>
                  <th className="py-3 px-4">{lang === "bn" ? "বিষয়" : "Subject"}</th>
                  <th className="py-3 px-4">{lang === "bn" ? "সিলেবাসে অধ্যায়" : "Syllabus Status"}</th>
                  <th className="py-3 px-4">{lang === "bn" ? "সপ্তাহে পড়ার দিন" : "Days/Week"}</th>
                  <th className="py-3 px-4">{lang === "bn" ? "সেশনের সময়" : "Daily Session"}</th>
                  <th className="py-3 px-4">{lang === "bn" ? "স্পেসড রিভিশন সাইকেল" : "Leitner Interval"}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-slate-700 dark:text-slate-300">
                {[
                  { name: "সাধারণ গণিত", unread: 15, done: 2, days: 5, time: 60, isWeak: true },
                  { name: "সাধারণ বিজ্ঞান", unread: 12, done: 2, days: 4, time: 45, isWeak: false },
                  { name: "English", unread: 10, done: 2, days: 4, time: 45, isWeak: false },
                  { name: "বাংলা (১ম ও ২য় পত্র)", unread: 10, done: 2, days: 3, time: 30, isWeak: false },
                  { name: "তথ্য ও যোগাযোগ প্রযুক্তি", unread: 3, done: 2, days: 3, time: 30, isWeak: false },
                  { name: "বাংলাদেশ ও বিশ্বপরিচয়", unread: 13, done: 2, days: 4, time: 40, isWeak: false },
                ].map((s, idx) => (
                  <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                    <td className="py-3.5 px-4 font-bold text-slate-900 dark:text-white flex items-center gap-2">
                      <span>{s.name}</span>
                      {s.isWeak && (
                        <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                          {lang === "bn" ? "আরও অনুশীলন দরকার (+৪০% সময়)" : "Practice Focus"}
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="text-indigo-600 font-bold">{toBengaliDigits(s.unread)}টি বাকি</span> •{" "}
                      <span className="text-emerald-600 font-bold">{toBengaliDigits(s.done)}টি শেষ</span>
                    </td>
                    <td className="py-3.5 px-4 font-medium">
                      {lang === "bn" ? `সপ্তাহে ${toBengaliDigits(s.days)} দিন` : `${s.days} days/week`}
                    </td>
                    <td className="py-3.5 px-4 font-bold text-slate-900 dark:text-white">
                      {lang === "bn" ? toBengaliDigits(s.time) : s.time} {lang === "bn" ? "মিনিট" : "min"}
                    </td>
                    <td className="py-3.5 px-4 text-slate-500 font-mono">
                      {s.isWeak ? "১-২-৫-১০ দিন" : "১-৩-৭-১৪ দিন"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* 3. Existing Option: Exam-Day Timetable Quick-Add */}
        {viewMode === "exam_day" && (
          <div className="space-y-5">
            <div className="p-4 rounded-xl bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h4 className="text-sm font-bold text-indigo-950 dark:text-indigo-200">
                  {lang === "bn" ? "পরীক্ষা সিরিজ নির্বাচন ও সময়সূচি যুক্তকরণ" : "Exam Series & Timetable Entry"}
                </h4>
                <p className="text-xs text-indigo-800 dark:text-indigo-300 mt-0.5">
                  {lang === "bn"
                    ? "শিক্ষার্থী নিজেই নিজের পরীক্ষার তারিখ ও সময় এন্ট্রি করবে (১০:০০ - ১৩:০০ ডিফল্ট)।"
                    : "Enter your real exam timetable with editable default 10:00 - 13:00 slots."}
                </p>
              </div>

              {/* Series Selector */}
              <div className="flex items-center gap-2">
                {(["school_exam", "ssc_test", "ssc_board"] as ExamSeriesType[]).map((st) => (
                  <button
                    key={st}
                    onClick={() => setNewSeries(st)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                      newSeries === st
                        ? "bg-indigo-600 text-white shadow-sm"
                        : "bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
                    }`}
                  >
                    {st === "school_exam"
                      ? "স্কুল পরীক্ষা"
                      : st === "ssc_test"
                      ? "SSC টেস্ট পরীক্ষা"
                      : "SSC বোর্ড পরীক্ষা"}
                  </button>
                ))}
              </div>
            </div>

            {/* Quick Add Form */}
            <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
              <div className="space-y-1 sm:col-span-2">
                <label className="text-[11px] font-bold text-slate-600 dark:text-slate-400">বিষয় ও পত্র</label>
                <input
                  type="text"
                  value={newSubjectBn}
                  onChange={(e) => {
                    setNewSubjectBn(e.target.value);
                    setNewSubjectSlug(e.target.value.toLowerCase().replace(/\s+/g, "_"));
                  }}
                  className="w-full text-xs font-semibold px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900"
                  placeholder="যেমন: পদার্থবিজ্ঞান ১ম পত্র"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-bold text-slate-600 dark:text-slate-400">পরীক্ষার তারিখ</label>
                <input
                  type="date"
                  value={newExamDate}
                  onChange={(e) => setNewExamDate(e.target.value)}
                  className="w-full text-xs font-semibold px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-bold text-slate-600 dark:text-slate-400">শুরু ও শেষ সময়</label>
                <div className="flex items-center gap-1">
                  <input
                    type="time"
                    value={newStartTime}
                    onChange={(e) => setNewStartTime(e.target.value)}
                    className="w-1/2 text-xs font-semibold px-2 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900"
                  />
                  <input
                    type="time"
                    value={newEndTime}
                    onChange={(e) => setNewEndTime(e.target.value)}
                    className="w-1/2 text-xs font-semibold px-2 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900"
                  />
                </div>
              </div>

              <div className="flex items-end">
                <button
                  onClick={handleAddExam}
                  className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg flex items-center justify-center gap-1 cursor-pointer transition-all"
                >
                  <Plus className="w-4 h-4" />
                  <span>{lang === "bn" ? "পরীক্ষা যুক্ত করুন" : "Add Exam"}</span>
                </button>
              </div>
            </div>

            {/* Timetable Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-bold uppercase tracking-wider border-b border-slate-200 dark:border-slate-700">
                  <tr>
                    <th className="py-3 px-4">সিরিজ</th>
                    <th className="py-3 px-4">বিষয় ও পত্র</th>
                    <th className="py-3 px-4">তারিখ</th>
                    <th className="py-3 px-4">সময়সূচি</th>
                    <th className="py-3 px-4 text-right">অ্যাকশন</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {timetable.map((t) => (
                    <tr key={t.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded font-bold text-[10px] bg-slate-200 dark:bg-slate-700">
                          {t.series === "school_exam"
                            ? "স্কুল পরীক্ষা"
                            : t.series === "ssc_test"
                            ? "SSC টেস্ট"
                            : "SSC বোর্ড"}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                        {t.subject_name_bn} {t.paper ? `(${t.paper})` : ""}
                      </td>
                      <td className="py-3 px-4 font-medium">{t.date}</td>
                      <td className="py-3 px-4 font-mono font-bold text-indigo-600 dark:text-indigo-400">
                        {t.start_time} - {t.end_time}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => handleDeleteExam(t.id)}
                          className="p-1.5 text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-lg transition-all cursor-pointer"
                          title="পরীক্ষা মুছুন"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Hours Override & Safety Cap Settings */}
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 space-y-3">
              <h4 className="text-xs font-bold text-slate-800 dark:text-slate-200">
                {lang === "bn" ? "পরীক্ষা সপ্তাহের পড়ার ঘণ্টা ও নিরাপত্তা সীমা" : "Hours & Safety Ceiling"}
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="space-y-1">
                  <label className="text-[11px] text-slate-500 font-semibold">পরীক্ষা সপ্তাহের দৈনিক পড়ার ঘণ্টা</label>
                  <input
                    type="number"
                    step="0.5"
                    min="2"
                    max="14"
                    value={examWeekHours}
                    onChange={(e) => handleHoursChange(parseFloat(e.target.value) || 6.0)}
                    className="w-full text-xs font-bold px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] text-slate-500 font-semibold">সংরক্ষিত ঘুম (ডিফল্ট সর্বনিম্ন ৭ ঘণ্টা)</label>
                  <input
                    type="text"
                    disabled
                    value="৭.০ ঘণ্টা (সুরক্ষিত)"
                    className="w-full text-xs font-bold px-3 py-2 rounded-lg border border-slate-200 bg-slate-100 dark:bg-slate-800 text-slate-500 cursor-not-allowed"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] text-slate-500 font-semibold">পরীক্ষার দিনের খাবার/যাতায়াত বাফার</label>
                  <input
                    type="text"
                    disabled
                    value="২.০ ঘণ্টা (সুরক্ষিত)"
                    className="w-full text-xs font-bold px-3 py-2 rounded-lg border border-slate-200 bg-slate-100 dark:bg-slate-800 text-slate-500 cursor-not-allowed"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 4. Existing Option: Syllabus Status & "বাকি আছে" Toggles */}
        {viewMode === "syllabus" && (
          <div className="space-y-5">
            <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 flex items-center justify-between gap-3">
              <div>
                <h4 className="text-sm font-bold text-amber-950 dark:text-amber-200">
                  {lang === "bn" ? "অধ্যায়ভিত্তিক পাঠ অগ্রগতি ও বাকি সিলেবাস চিহ্নিতকরণ" : "Syllabus Progress & Leftover Chapters"}
                </h4>
                <p className="text-xs text-amber-800 dark:text-amber-300 mt-0.5">
                  {lang === "bn"
                    ? "কোনো অধ্যায় বাকি থাকলে তা 'বাকি আছে' নির্বাচন করুন। পরীক্ষার পূর্বে এই অধ্যায়গুলো সর্বোচ্চ অগ্রাধিকার পাবে।"
                    : "Flag unread chapters as 'Left'. The planner prioritizes them before standard revision."}
                </p>
              </div>
            </div>

            {syllabusList.map((sub) => (
              <div
                key={sub.subject_slug}
                className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-3 shadow-sm"
              >
                <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2.5">
                  <span className="text-sm font-extrabold text-slate-900 dark:text-white">
                    {sub.subject_slug === "math" ? "সাধারণ গণিত" : "সাধারণ বিজ্ঞান"}
                  </span>

                  {/* Quick Toggle: Some Syllabus Left */}
                  <button
                    onClick={() => handleToggleSyllabusRemaining(sub.subject_slug)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                      sub.has_remaining_syllabus
                        ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border border-rose-300"
                        : "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300"
                    }`}
                  >
                    <span>
                      {sub.has_remaining_syllabus
                        ? lang === "bn"
                          ? "⚠ বাকি সিলেবাস আছে (সক্রিয়)"
                          : "Has Remaining Syllabus"
                        : lang === "bn"
                        ? "✓ সব সিলেবাস শেষ"
                        : "All Covered"}
                    </span>
                  </button>
                </div>

                {/* Chapter Toggles */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {sub.chapters.map((ch) => (
                    <div
                      key={ch.number}
                      className="p-3 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 flex items-center justify-between gap-2"
                    >
                      <div>
                        <div className="text-xs font-bold text-slate-900 dark:text-white">
                          অধ্যায় {toBengaliDigits(ch.number)}: {ch.title_bn}
                        </div>
                        <div className="text-[10px] text-slate-500 mt-0.5">
                          প্রয়োজনীয় সময়: ~{toBengaliDigits(ch.estimated_hours || 4)} ঘণ্টা
                        </div>
                      </div>

                      {/* 3 Status Buttons: Covered / Partly / Left ("বাকি আছে") */}
                      <div className="flex items-center gap-1">
                        {(["covered", "partly", "left"] as const).map((st) => (
                          <button
                            key={st}
                            onClick={() => handleUpdateChapterStatus(sub.subject_slug, ch.number, st)}
                            className={`px-2 py-1 rounded text-[10px] font-bold transition-all cursor-pointer ${
                              ch.status === st
                                ? st === "covered"
                                  ? "bg-emerald-600 text-white"
                                  : st === "partly"
                                  ? "bg-amber-600 text-white"
                                  : "bg-rose-600 text-white"
                                : "bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
                            }`}
                          >
                            {st === "covered"
                              ? "সম্পন্ন"
                              : st === "partly"
                              ? "আংশিক"
                              : "বাকি আছে"}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
