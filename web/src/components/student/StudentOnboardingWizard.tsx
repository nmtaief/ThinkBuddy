"use client";

import React, { useState, useEffect, useMemo } from "react";
import { Language, translations, toBengaliDigits } from "@/lib/i18n";
import { getSubjectsForClassAndGroup, SubjectItem, ChapterItem } from "@/lib/curriculum-data";
import { computeClientAllocation, RoutineStrategy, DayPlan, DayScheduleItem } from "@/lib/allocation-engine";
import { getCQQuestions, CQQuestionItem } from "@/lib/cq-topic-mapping";
import {
  BookOpen,
  Calendar,
  Clock,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  RotateCcw,
  ChevronRight,
  ChevronLeft,
  Flame,
  Award,
  ChevronDown,
  ChevronUp,
  Brain,
  Send,
  Zap,
} from "lucide-react";

interface SubjectAllocation {
  slug: string;
  name_bn: string;
  name_en: string;
  total_chapters: number;
  completed_chapters_count: number;
  new_chapters_count: number;
  weak_chapters_count: number;
  is_stem: boolean;
  is_weak: boolean;
  is_focus: boolean;
  priority: string;
  daily_study_minutes: number;
  daily_revision_minutes: number;
  daily_weakness_minutes: number;
  daily_total_minutes: number;
  total_estimated_hours_to_exam: number;
  recommended_sessions_per_week: number;
  revision_box_interval_days: number[];
  sessions_per_week?: number;
  session_duration_minutes?: number;
  days_schedule_label?: string;
  is_daily_subject?: boolean;
  chapter_breakdown?: {
    number: number;
    title_bn: string;
    status: string;
    is_weak?: boolean;
  }[];
}

interface AllocationSummary {
  days_remaining: number;
  daily_study_hours: number;
  daily_total_minutes: number;
  routine_strategy?: RoutineStrategy;
  breakdown_shares: {
    new_study?: number;
    spaced_revision?: number;
    weakness_practice?: number;
    quizzes?: number;
    study?: number;
    revision?: number;
    weakness?: number;
    quiz?: number;
    new_study_minutes?: number;
    spaced_revision_minutes?: number;
    weakness_practice_minutes?: number;
    quiz_minutes?: number;
  };
  subjects: SubjectAllocation[];
  total_allocated_minutes: number;
  final_revision_window_days: number;
  buffer_catchup_days: number;
  total_unread_chapters: number;
  total_completed_chapters: number;
  weekly_schedule?: DayPlan[];
}

interface AIReviewData {
  ai_review_status: string;
  ai_guidance_bn: string;
  ai_guidance_en: string;
  key_recommendations: string[];
  feasibility_score: number;
}

interface StudentOnboardingWizardProps {
  lang: Language;
  onComplete: () => void;
}

export const StudentOnboardingWizard: React.FC<StudentOnboardingWizardProps> = ({
  lang,
  onComplete,
}) => {
  const t = translations[lang];

  // Mode: "wizard" or "ai_prompt"
  const [plannerMode, setPlannerMode] = useState<"wizard" | "ai_prompt">("wizard");
  const [freeformPrompt, setFreeformPrompt] = useState<string>("");
  const [isGeneratingAI, setIsGeneratingAI] = useState<boolean>(false);

  // Wizard Steps: 1: Class, 2: Syllabus & Chapters, 3: Exam, 4: Hours, 5: Preview
  const [currentStep, setCurrentStep] = useState<number>(1);

  // Step 1: Class & Medium
  const [selectedClass, setSelectedClass] = useState<number>(8);
  const [selectedMedium, setSelectedMedium] = useState<string>("bn");
  const [selectedGroup, setSelectedGroup] = useState<string>("general");

  // Step 2: Subjects, Chapters, Weakness, Focus, Priorities
  // Initialize with authoritative NCTB curriculum data immediately (ZERO empty state)
  const initialSubjects = useMemo(() => {
    return getSubjectsForClassAndGroup(selectedClass, selectedClass >= 9 ? selectedGroup : "general");
  }, [selectedClass, selectedGroup]);

  const [catalogSubjects, setCatalogSubjects] = useState<SubjectItem[]>(() => {
    return getSubjectsForClassAndGroup(8, "general");
  });
  const [selectedSubjects, setSelectedSubjects] = useState<string[]>(() => {
    return getSubjectsForClassAndGroup(8, "general").map((s) => s.slug);
  });
  const [weakSubjects, setWeakSubjects] = useState<string[]>(["c8_math"]);
  const [focusSubjects, setFocusSubjects] = useState<string[]>(["c8_math"]);
  const [subjectPriorities, setSubjectPriorities] = useState<Record<string, string>>({});
  const [chapterStatuses, setChapterStatuses] = useState<Record<string, Record<number, string>>>({});
  const [expandedSubject, setExpandedSubject] = useState<string | null>(null);
  const [selectedCqChapter, setSelectedCqChapter] = useState<{
    subject: string;
    subjectSlug: string;
    chapterNumber: number;
    chapterTitle: string;
  } | null>(null);

  // Synchronize subjects whenever class or group changes
  useEffect(() => {
    const groupParam = selectedClass >= 9 ? selectedGroup : "general";
    const subjects = getSubjectsForClassAndGroup(selectedClass, groupParam);

    setCatalogSubjects(subjects);
    const allSlugs = subjects.map((s) => s.slug);
    setSelectedSubjects(allSlugs);

    // Default STEM subjects as main priority
    const initialPriorities: Record<string, string> = {};
    subjects.forEach((s) => {
      initialPriorities[s.slug] = s.is_stem ? "main" : "normal";
    });
    setSubjectPriorities(initialPriorities);

    // Default chapter statuses (first 2 completed, rest new)
    const initialStatuses: Record<string, Record<number, string>> = {};
    subjects.forEach((s) => {
      if (s.chapters) {
        const chMap: Record<number, string> = {};
        s.chapters.forEach((ch, idx) => {
          chMap[ch.number] = idx < 2 ? "completed" : "new";
        });
        initialStatuses[s.slug] = chMap;
      }
    });
    setChapterStatuses(initialStatuses);

    // Default Math / science as weak & focus
    const mathSub = subjects.find((s) => s.slug.includes("math") || s.slug.includes("physics"));
    if (mathSub) {
      setWeakSubjects([mathSub.slug]);
      setFocusSubjects([mathSub.slug]);
    } else if (subjects.length > 0) {
      setWeakSubjects([subjects[0].slug]);
      setFocusSubjects([subjects[0].slug]);
    }

    // Expand the first subject by default so chapters are immediately visible to the user!
    if (subjects.length > 0) {
      setExpandedSubject(subjects[0].slug);
    }

    // Background refresh from backend if online
    async function fetchFromBackend() {
      try {
        const res = await fetch(`/api/proxy/curriculum/subjects?class_level=${selectedClass}&group=${groupParam}`);
        if (res.ok) {
          const data: SubjectItem[] = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            setCatalogSubjects(data);
          }
        }
      } catch {}
    }
    fetchFromBackend();
  }, [selectedClass, selectedGroup]);

  // Step 3: Exam Setup
  const [examName, setExamName] = useState<string>("অর্ধবার্ষিক পরীক্ষা (Half-Yearly Exam)");
  const [examDate, setExamDate] = useState<string>(() => {
    const d = new Date();
    d.setDate(d.getDate() + 60);
    return d.toISOString().split("T")[0];
  });

  // Step 4: Study Budget & Routine Combination
  const [dailyHours, setDailyHours] = useState<number>(3.5);
  const [routineStrategy, setRoutineStrategy] = useState<RoutineStrategy>("core_weak_daily");
  const [studyWindowStart, setStudyWindowStart] = useState<string>("18:00");
  const [studyWindowEnd, setStudyWindowEnd] = useState<string>("22:00");

  // Step 5: Day-by-Day View & Subject Summary
  const [selectedDayId, setSelectedDayId] = useState<string>("sat");
  const [routineViewMode, setRoutineViewMode] = useState<"day_by_day" | "subject_summary">("day_by_day");
  const [isActivated, setIsActivated] = useState<boolean>(false);

  // Step 5: Live Calculated Dataset & AI Review
  const [allocation, setAllocation] = useState<AllocationSummary | null>(null);
  const [aiReview, setAIReview] = useState<AIReviewData | null>(null);
  const [isCalculating, setIsCalculating] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Handle Freeform AI Study Plan Generation
  const handleGenerateAIPlan = async () => {
    if (!freeformPrompt.trim()) return;
    setIsGeneratingAI(true);
    setErrorMsg(null);

    // 1. Try backend proxy first
    try {
      const res = await fetch("/api/proxy/planner/ai-review-and-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          freeform_text: freeformPrompt,
          class_level: selectedClass,
          medium: selectedMedium,
          group: selectedClass >= 9 ? selectedGroup : "general",
          daily_study_hours: Math.max(3.0, dailyHours),
          routine_strategy: routineStrategy,
          exam_name: examName,
          exam_date: examDate,
          selected_subjects: selectedSubjects,
          weak_subjects: weakSubjects,
          focus_subjects: focusSubjects,
          subject_priorities: subjectPriorities,
          chapter_statuses: chapterStatuses,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setAllocation(data.plan_dataset);
        setAIReview({
          ai_review_status: data.ai_review_status,
          ai_guidance_bn: data.ai_guidance_bn,
          ai_guidance_en: data.ai_guidance_en,
          key_recommendations: data.key_recommendations,
          feasibility_score: data.feasibility_score,
        });
        setPlannerMode("wizard");
        setCurrentStep(5);
        setIsGeneratingAI(false);
        return;
      }
    } catch {}

    // 2. Local resilient parser & allocator fallback
    try {
      const lower = freeformPrompt.toLowerCase();
      let c = selectedClass;
      if (lower.includes("6") || lower.includes("৬")) c = 6;
      else if (lower.includes("7") || lower.includes("৭")) c = 7;
      else if (lower.includes("8") || lower.includes("৮")) c = 8;
      else if (lower.includes("9") || lower.includes("৯")) c = 9;
      else if (lower.includes("10") || lower.includes("১০")) c = 10;
      setSelectedClass(c);

      let g = selectedGroup;
      if (c >= 9) {
        if (lower.includes("science") || lower.includes("বিজ্ঞান")) g = "science";
        else if (lower.includes("commerce") || lower.includes("বাণিজ্য") || lower.includes("ব্যবসা")) g = "business_studies";
        else if (lower.includes("arts") || lower.includes("humanities") || lower.includes("মানবিক")) g = "humanities";
        setSelectedGroup(g);
      }

      const activeSubs = getSubjectsForClassAndGroup(c, g);
      setCatalogSubjects(activeSubs);
      setSelectedSubjects(activeSubs.map((s) => s.slug));

      let h = dailyHours;
      const hMatch = lower.match(/(\d+(?:\.\d+)?|[১-৯]+)\s*(?:hour|hours|ঘণ্টা|ঘন্টা|hr)/);
      if (hMatch) {
        const bnMap: Record<string, string> = { "১": "1", "২": "2", "৩": "3", "৪": "4", "৫": "5", "৬": "6" };
        const clean = hMatch[1].replace(/[১-৬]/g, (m) => bnMap[m] || m);
        h = parseFloat(clean) || dailyHours;
        setDailyHours(h);
      }

      const localReview = computeClientAllocation({
        class_level: c,
        group: g,
        catalogSubjects: activeSubs,
        selected_subject_slugs: activeSubs.map((s) => s.slug),
        weak_subject_slugs: weakSubjects,
        focus_subject_slugs: focusSubjects,
        subject_priorities: subjectPriorities,
        chapter_statuses: chapterStatuses,
        daily_study_hours: Math.max(3.0, h),
        routine_strategy: routineStrategy,
        exam_name: examName,
        exam_date: examDate,
      });

      setAllocation(localReview.plan_dataset as any);
      setAIReview({
        ai_review_status: localReview.ai_review_status,
        ai_guidance_bn: localReview.ai_guidance_bn,
        ai_guidance_en: localReview.ai_guidance_en,
        key_recommendations: localReview.key_recommendations,
        feasibility_score: localReview.feasibility_score,
      });
      setPlannerMode("wizard");
      setCurrentStep(5);
    } catch (err: any) {
      setErrorMsg(err.message || "Error generating AI plan");
    } finally {
      setIsGeneratingAI(false);
    }
  };

  // Calculate balanced allocation dataset
  const calculateAllocation = async () => {
    setIsCalculating(true);
    setErrorMsg(null);
    try {
      const res = await fetch("/api/proxy/planner/ai-review-and-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          class_level: selectedClass,
          group: selectedClass >= 9 ? selectedGroup : "general",
          selected_subjects: selectedSubjects,
          weak_subjects: weakSubjects,
          focus_subjects: focusSubjects,
          subject_priorities: subjectPriorities,
          chapter_statuses: chapterStatuses,
          daily_study_hours: Math.max(3.0, dailyHours),
          routine_strategy: routineStrategy,
          exam_name: examName,
          exam_date: examDate,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setAllocation(data.plan_dataset);
        setAIReview({
          ai_review_status: data.ai_review_status,
          ai_guidance_bn: data.ai_guidance_bn,
          ai_guidance_en: data.ai_guidance_en,
          key_recommendations: data.key_recommendations,
          feasibility_score: data.feasibility_score,
        });
        setIsCalculating(false);
        return;
      }
    } catch {}

    // Resilient local calculation
    try {
      const localReview = computeClientAllocation({
        class_level: selectedClass,
        group: selectedClass >= 9 ? selectedGroup : "general",
        catalogSubjects,
        selected_subject_slugs: selectedSubjects,
        weak_subject_slugs: weakSubjects,
        focus_subject_slugs: focusSubjects,
        subject_priorities: subjectPriorities,
        chapter_statuses: chapterStatuses,
        daily_study_hours: Math.max(3.0, dailyHours),
        routine_strategy: routineStrategy,
        exam_name: examName,
        exam_date: examDate,
      });

      setAllocation(localReview.plan_dataset as any);
      setAIReview({
        ai_review_status: localReview.ai_review_status,
        ai_guidance_bn: localReview.ai_guidance_bn,
        ai_guidance_en: localReview.ai_guidance_en,
        key_recommendations: localReview.key_recommendations,
        feasibility_score: localReview.feasibility_score,
      });
    } catch (err: any) {
      setErrorMsg(err.message || "Error calculating schedule");
    } finally {
      setIsCalculating(false);
    }
  };

  useEffect(() => {
    if (currentStep === 5) {
      calculateAllocation();
    }
  }, [currentStep]);

  // Day-by-Day schedule helper (ensures Friday/Saturday = No School & 2 hr revision, 25% daily revision)
  const activeSchedule: DayPlan[] = useMemo(() => {
    if (allocation?.weekly_schedule && allocation.weekly_schedule.length > 0) {
      return allocation.weekly_schedule;
    }
    if (!allocation?.subjects) return [];

    const daysMeta: Array<{
      day_id: "sat" | "sun" | "mon" | "tue" | "wed" | "thu" | "fri";
      name_bn: string;
      name_en: string;
      is_weekend: boolean;
    }> = [
      { day_id: "sat", name_bn: "শনিবার", name_en: "Saturday", is_weekend: true },
      { day_id: "sun", name_bn: "রবিবার", name_en: "Sunday", is_weekend: false },
      { day_id: "mon", name_bn: "সোমবার", name_en: "Monday", is_weekend: false },
      { day_id: "tue", name_bn: "মঙ্গলবার", name_en: "Tuesday", is_weekend: false },
      { day_id: "wed", name_bn: "বুধবার", name_en: "Wednesday", is_weekend: false },
      { day_id: "thu", name_bn: "বৃহস্পতিবার", name_en: "Thursday", is_weekend: false },
      { day_id: "fri", name_bn: "শুক্রবার", name_en: "Friday", is_weekend: true },
    ];

    const coreSubs = allocation.subjects.filter((s) => s.is_weak || s.is_focus || s.is_stem);
    const secSubs = allocation.subjects.filter((s) => !s.is_weak && !s.is_focus && !s.is_stem);
    const effectiveCore = coreSubs.length > 0 ? coreSubs : allocation.subjects.slice(0, 2);
    const effectiveSecondary = secSubs.length > 0 ? secSubs : allocation.subjects.slice(2);
    const weekdayTargetMins = Math.max(180, Math.round((allocation.daily_study_hours || 3.5) * 60));

    return daysMeta.map((d, dIdx) => {
      const isWk = d.is_weekend;
      const specRev = isWk ? 120 : 0; // 2 hours (120 mins) revision on Friday & Saturday

      let daySubs: SubjectAllocation[] = [];
      if (isWk) {
        const c = effectiveCore[dIdx % effectiveCore.length];
        const s = effectiveSecondary.length > 0
          ? effectiveSecondary[dIdx % effectiveSecondary.length]
          : effectiveCore[(dIdx + 1) % effectiveCore.length];
        daySubs = [c, s].filter(Boolean);
      } else {
        const c1 = effectiveCore[dIdx % effectiveCore.length];
        const c2 = effectiveCore[(dIdx + 1) % effectiveCore.length];
        const s1 = effectiveSecondary.length > 0
          ? effectiveSecondary[dIdx % effectiveSecondary.length]
          : effectiveCore[(dIdx + 2) % effectiveCore.length];
        const seen = new Set<string>();
        [c1, s1, c2].forEach((sub) => {
          if (sub && !seen.has(sub.slug)) {
            seen.add(sub.slug);
            daySubs.push(sub);
          }
        });
        for (const sub of allocation.subjects) {
          if (daySubs.length >= 3) break;
          if (!seen.has(sub.slug)) {
            seen.add(sub.slug);
            daySubs.push(sub);
          }
        }
      }

      const availMins = isWk ? Math.max(90, weekdayTargetMins - specRev) : weekdayTargetMins;
      const baseMins = Math.max(30, Math.floor(availMins / Math.max(1, daySubs.length)));

      let dayStudyTotal = 0;
      let dayRevTotal = specRev;

      const dayItems: DayScheduleItem[] = daySubs.map((sub) => {
        let subTotal = baseMins + (sub.is_weak ? 15 : 0);
        subTotal = Math.max(30, subTotal);

        // Exactly 25% of time for revision, 75% for new study
        const revM = Math.max(8, Math.round(subTotal * 0.25));
        const studyM = Math.max(22, subTotal - revM);

        dayStudyTotal += studyM;
        dayRevTotal += revM;

        return {
          subject_slug: sub.slug,
          subject_name_bn: sub.name_bn,
          subject_name_en: sub.name_en,
          is_weak: sub.is_weak,
          is_focus: sub.is_focus,
          total_minutes: studyM + revM,
          study_minutes: studyM,
          revision_minutes: revM,
        };
      });

      return {
        day_id: d.day_id,
        day_name_bn: d.name_bn,
        day_name_en: d.name_en,
        is_weekend: isWk,
        is_school_day: !isWk,
        school_status_label_bn: isWk ? "স্কুল বন্ধ (ছুটির দিন)" : "স্কুল ডে",
        special_revision_block_minutes: specRev,
        daily_total_minutes: dayStudyTotal + dayRevTotal,
        daily_study_minutes: dayStudyTotal,
        daily_revision_minutes: dayRevTotal,
        items: dayItems,
      };
    });
  }, [allocation]);

  const toggleSubject = (slug: string) => {
    if (selectedSubjects.includes(slug)) {
      if (selectedSubjects.length > 1) {
        setSelectedSubjects(selectedSubjects.filter((s) => s !== slug));
        setWeakSubjects(weakSubjects.filter((s) => s !== slug));
        setFocusSubjects(focusSubjects.filter((s) => s !== slug));
      }
    } else {
      setSelectedSubjects([...selectedSubjects, slug]);
    }
  };

  const toggleWeak = (slug: string) => {
    if (weakSubjects.includes(slug)) {
      setWeakSubjects(weakSubjects.filter((s) => s !== slug));
    } else {
      setWeakSubjects([...weakSubjects, slug]);
    }
  };

  const toggleFocus = (slug: string) => {
    if (focusSubjects.includes(slug)) {
      setFocusSubjects(focusSubjects.filter((s) => s !== slug));
    } else {
      setFocusSubjects([...focusSubjects, slug]);
    }
  };

  const setPriority = (slug: string, priority: string) => {
    setSubjectPriorities({
      ...subjectPriorities,
      [slug]: priority,
    });
  };

  const setChapterStatus = (subjectSlug: string, chapterNumber: number, status: string) => {
    const currentSub = chapterStatuses[subjectSlug] || {};
    setChapterStatuses({
      ...chapterStatuses,
      [subjectSlug]: {
        ...currentSub,
        [chapterNumber]: status,
      },
    });
  };

  const setAllChaptersStatus = (subjectSlug: string, chapters: ChapterItem[], status: string) => {
    const updated: Record<number, string> = {};
    chapters.forEach((ch) => {
      updated[ch.number] = status;
    });
    setChapterStatuses({
      ...chapterStatuses,
      [subjectSlug]: updated,
    });
  };

  const handleFinishOnboarding = async () => {
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await fetch("/api/proxy/students/onboarding", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          class_level: selectedClass,
          medium: selectedMedium,
          group: selectedClass >= 9 ? selectedGroup : "general",
          selected_subject_slugs: selectedSubjects,
          weak_subject_slugs: weakSubjects,
          focus_subject_slugs: focusSubjects,
          subject_priorities: subjectPriorities,
          daily_study_hours: dailyHours,
          routine_strategy: routineStrategy,
          exam_name: examName,
          exam_date: examDate,
          study_window_start: studyWindowStart,
          study_window_end: studyWindowEnd,
          weekly_off_days: ["fri", "sat"],
        }),
      });
    } catch {}

    // Resilient local persistence
    try {
      if (allocation) {
        localStorage.setItem("tb_active_study_plan", JSON.stringify(allocation));
      }
      if (activeSchedule && activeSchedule.length > 0) {
        localStorage.setItem("tb_active_schedule", JSON.stringify(activeSchedule));
      }
      localStorage.setItem("tb_student_onboarding_done", "true");
      // Reset streak and today stats for the newly activated routine
      localStorage.setItem("tb_streak_days", "0");
      localStorage.setItem("tb_study_minutes_today", "0");
      localStorage.setItem("tb_completed_tasks_count", "0");
    } catch {}

    setIsSubmitting(false);
    setIsActivated(true);
  };

  return (
    <div className="w-full mx-auto p-2 sm:p-4 md:p-6 lg:p-8 space-y-6">
      {/* ACTIVATION SUCCESS SCREEN */}
      {isActivated ? (
        <div className="bg-white dark:bg-slate-900 border border-emerald-200 dark:border-emerald-800/60 rounded-3xl p-6 sm:p-10 shadow-xl text-center space-y-6 animate-in fade-in zoom-in-95 duration-200">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-emerald-100 dark:bg-emerald-950/80 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shadow-inner">
            <CheckCircle2 className="w-10 h-10 animate-bounce" />
          </div>

          <div className="space-y-2">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 text-xs font-bold">
              ✓ রুটিন সফলভাবে সক্রিয় হয়েছে (Plan Activated)
            </div>
            <h2 className="text-xl sm:text-2xl font-black text-slate-900 dark:text-white">
              🎉 অভিনন্দন! তোমার ব্যক্তিগত স্টাডি প্ল্যান সফলভাবে চালু হয়েছে!
            </h2>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 max-w-lg mx-auto">
              তোমার নির্বাচিত বিষয়সমূহ, দুর্বল বিষয়ের অতিরিক্ত মনোযোগ, প্রতিদিনের ২৫% স্পেসড রিভিশন এবং শুক্র-শনিবারের ২ ঘণ্টা মেগা রিভিশন ড্যাশবোর্ডে সেট করা হয়েছে।
            </p>
          </div>

          {/* Quick Summary Highlights */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 max-w-2xl mx-auto text-center">
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
              <div className="text-[10px] text-slate-500 font-semibold">শ্রেণি ও মাধ্যম</div>
              <div className="text-sm font-bold text-slate-900 dark:text-white">
                {selectedClass}ম শ্রেণি ({selectedMedium === "en" ? "English" : "বাংলা"})
              </div>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
              <div className="text-[10px] text-slate-500 font-semibold">দৈনিক পড়ার বাজেট</div>
              <div className="text-sm font-bold text-blue-600 dark:text-blue-400">
                {dailyHours} ঘণ্টা / দিন
              </div>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
              <div className="text-[10px] text-slate-500 font-semibold">প্রতিদিনের রিভিশন</div>
              <div className="text-sm font-bold text-emerald-600 dark:text-emerald-400">
                ২৫% স্পেসড রিভিশন
              </div>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
              <div className="text-[10px] text-slate-500 font-semibold">ছুটির দিন রিভিশন</div>
              <div className="text-sm font-bold text-amber-600 dark:text-amber-400">
                ২ ঘণ্টা (শুক্র ও শনি)
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-4">
            <button
              type="button"
              onClick={() => {
                if (typeof window !== "undefined") {
                  window.history.replaceState({}, '', window.location.pathname);
                }
                onComplete();
              }}
              className="w-full sm:w-auto px-8 py-3.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm shadow-lg hover:shadow-xl transition-all cursor-pointer flex items-center justify-center gap-2"
            >
              <span>আজকের পড়ার টেবিলে যাও (Go to Today&apos;s Dashboard)</span>
              <ChevronRight className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => setIsActivated(false)}
              className="w-full sm:w-auto px-5 py-3.5 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold text-xs transition-colors cursor-pointer"
            >
              রুটিন পুনরায় দেখুন (Review Routine)
            </button>
          </div>
        </div>
      ) : (
        <>
      {/* Wizard Header */}
      <div className="text-center space-y-3 pb-2">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300 text-xs font-bold shadow-sm">
          <Sparkles className="w-3.5 h-3.5" />
          {lang === "bn" ? "ব্যক্তিগত স্টাডি প্ল্যান সেটআপ" : "Personalized Study Setup"}
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
          {lang === "bn" ? "তোমার পড়াশোনার সময় ও রিভিশন শিডিউল তৈরি করো" : "Create Your Balanced Study & Revision Schedule"}
        </h1>
        <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 max-w-xl mx-auto leading-relaxed">
          {lang === "bn"
            ? "দুর্বল বিষয়গুলোকে বাড়তি সময়, নতুন পড়া ও রিভিশনের ভারসাম্য এবং পরীক্ষার আগের নিখুঁত স্পেসড রুটিন।"
            : "Balance new study chapters, spaced revision slots, and boosted practice for weak subjects."}
        </p>

        {/* Dual Mode Switcher: Step-by-Step vs AI Prompt */}
        <div className="flex justify-center pt-3">
          <div className="inline-flex p-1.5 rounded-xl bg-slate-200/80 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-xs font-semibold shadow-inner">
            <button
              type="button"
              onClick={() => setPlannerMode("wizard")}
              className={`px-4 py-2 rounded-lg transition-all cursor-pointer ${
                plannerMode === "wizard"
                  ? "bg-white dark:bg-slate-700 text-blue-700 dark:text-blue-300 font-bold shadow-sm"
                  : "text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              {lang === "bn" ? "ধাপভিত্তিক সিলেবাস নির্বাচন" : "Step-by-Step Setup"}
            </button>
            <button
              type="button"
              onClick={() => setPlannerMode("ai_prompt")}
              className={`px-4 py-2 rounded-lg transition-all flex items-center gap-1.5 cursor-pointer ${
                plannerMode === "ai_prompt"
                  ? "bg-white dark:bg-slate-700 text-indigo-700 dark:text-indigo-300 font-bold shadow-sm"
                  : "text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              <Brain className="w-4 h-4 text-indigo-500" />
              {lang === "bn" ? "এআই দিয়ে লিখুন (Write to AI)" : "Write to AI Generator"}
            </button>
          </div>
        </div>
      </div>

      {/* AI PROMPT MODE: DIRECT FREE-FORM GENERATOR */}
      {plannerMode === "ai_prompt" ? (
        <div className="bg-white dark:bg-slate-900 border border-indigo-200 dark:border-indigo-900/60 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300">
              <Brain className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                {lang === "bn" ? "নিজের ভাষায় তোমার লক্ষ্য ও দুর্বলতা লিখুন" : "Describe Your Study Goals in Natural Language"}
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {lang === "bn"
                  ? "বাডি এআই তোমার লেখা বিশ্লেষণ করে শ্রেণি, দুর্বল বিষয় ও পরীক্ষার তারিখ অনুযায়ী নিখুঁত প্ল্যান তৈরি করবে।"
                  : "Buddy AI will parse your goals, weak subjects, daily hours, and generate the schedule automatically."}
              </p>
            </div>
          </div>

          <textarea
            rows={4}
            value={freeformPrompt}
            onChange={(e) => setFreeformPrompt(e.target.value)}
            placeholder={
              lang === "bn"
                ? "যেমন: আমার ক্লাস ৮, আগামী ২০ জুলাই অর্ধবার্ষিক পরীক্ষা। গণিতে বীজগণিত আর জ্যামিতি কঠিন লাগে, ইংরেজিতে গ্রামার দুর্বল। প্রতিদিন ৩ ঘণ্টা পড়তে পারব..."
                : "e.g.: I am in Class 8, half-yearly exam on July 20. I struggle with Math algebra and English grammar. I can study 3 hours daily..."
            }
            className="w-full p-4 text-xs sm:text-sm rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />

          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
            <span className="text-[11px] text-slate-500 dark:text-slate-400">
              💡 {lang === "bn" ? "টিপ: পরীক্ষার তারিখ, বিষয় ও দৈনিক পড়ার সময় উল্লেখ করলে প্ল্যান আরও নিখুঁত হয়।" : "Tip: Mention exam date, weak subjects, and daily hours for best results."}
            </span>

            <button
              onClick={handleGenerateAIPlan}
              disabled={isGeneratingAI || !freeformPrompt.trim()}
              className="w-full sm:w-auto px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-bold rounded-xl shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              {isGeneratingAI ? (
                <>
                  <Zap className="w-4 h-4 animate-spin" />
                  {lang === "bn" ? "এআই প্ল্যান তৈরি হচ্ছে..." : "AI Generating Plan..."}
                </>
              ) : (
                <>
                  <Send className="w-3.5 h-3.5" />
                  {lang === "bn" ? "এআই দিয়ে প্ল্যান তৈরি করো" : "Generate Plan with AI"}
                </>
              )}
            </button>
          </div>
        </div>
      ) : (
        /* WIZARD MODE: 5 STEP STEPPER */
        <>
          {/* Stepper Progress Bar */}
          <div className="flex items-center justify-center gap-2 sm:gap-4 my-6 py-2">
            {[1, 2, 3, 4, 5].map((step) => (
              <React.Fragment key={step}>
                <div
                  className={`w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold transition-all shadow-sm ${
                    currentStep === step
                      ? "bg-blue-600 text-white ring-4 ring-blue-500/20"
                      : currentStep > step
                      ? "bg-emerald-600 text-white"
                      : "bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
                  }`}
                >
                  {currentStep > step ? "✓" : step}
                </div>
                {step < 5 && (
                  <div
                    className={`w-8 sm:w-14 h-1.5 rounded-full transition-all ${
                      currentStep > step ? "bg-emerald-500" : "bg-slate-200 dark:bg-slate-800"
                    }`}
                  />
                )}
              </React.Fragment>
            ))}
          </div>

          {/* STEP 1: CLASS & MEDIUM */}
          {currentStep === 1 && (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 sm:p-8 shadow-sm space-y-6">
              <div>
                <h3 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white">
                  {lang === "bn" ? "১. তোমার শ্রেণি ও মাধ্যম নির্বাচন করো" : "1. Select Class & Medium"}
                </h3>
                <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                  {lang === "bn" ? "শ্রেণি অনুযায়ী জাতীয় শিক্ষাক্রমের পাঠ্যবইসমূহ স্বয়ংক্রিয়ভাবে লোড হবে।" : "Textbooks will automatically load based on your class."}
                </p>
              </div>

              {/* Class Selector */}
              <div className="space-y-3">
                <label className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wide">
                  {lang === "bn" ? "কোন শ্রেণিতে পড়ো?" : "Select Your Class"}
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                  {[6, 7, 8, 9, 10].map((cls) => (
                    <button
                      key={cls}
                      type="button"
                      onClick={() => setSelectedClass(cls)}
                      className={`p-3.5 rounded-xl border-2 text-center text-sm font-bold transition-all cursor-pointer ${
                        selectedClass === cls
                          ? "border-blue-600 bg-blue-600 text-white shadow-md shadow-blue-500/25 ring-2 ring-blue-500/20"
                          : "border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-100 hover:bg-slate-200 dark:hover:bg-slate-700"
                      }`}
                    >
                      {lang === "bn" ? `${cls}ম শ্রেণি` : `Class ${cls}`}
                    </button>
                  ))}
                </div>
              </div>

              {/* Group Selector for Class 9 & 10 */}
              {selectedClass >= 9 && (
                <div className="space-y-3">
                  <label className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wide">
                    {lang === "bn" ? "বিভাগ (Group)" : "Academic Stream / Group"}
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {[
                      { id: "science", bn: "বিজ্ঞান", en: "Science" },
                      { id: "humanities", bn: "মানবিক", en: "Humanities" },
                      { id: "business_studies", bn: "ব্যবসায় শিক্ষা", en: "Business Studies" },
                    ].map((grp) => (
                      <button
                        key={grp.id}
                        type="button"
                        onClick={() => setSelectedGroup(grp.id)}
                        className={`p-3 rounded-xl border-2 text-center text-xs sm:text-sm font-bold transition-all cursor-pointer ${
                          selectedGroup === grp.id
                            ? "border-blue-600 bg-blue-600 text-white shadow-md shadow-blue-500/25 ring-2 ring-blue-500/20"
                            : "border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-100 hover:bg-slate-200 dark:hover:bg-slate-700"
                        }`}
                      >
                        {lang === "bn" ? grp.bn : grp.en}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Medium */}
              <div className="space-y-3">
                <label className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wide">
                  {lang === "bn" ? "পড়াশোনার মাধ্যম (Medium):" : "Medium of Instruction:"}
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setSelectedMedium("bn")}
                    className={`p-3.5 rounded-xl border-2 text-center text-xs sm:text-sm font-bold transition-all cursor-pointer ${
                      selectedMedium === "bn"
                        ? "border-blue-600 bg-blue-600 text-white shadow-md shadow-blue-500/25 ring-2 ring-blue-500/20"
                        : "border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-100 hover:bg-slate-200 dark:hover:bg-slate-700"
                    }`}
                  >
                    বাংলা মাধ্যম (Bangla Medium)
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedMedium("en")}
                    className={`p-3.5 rounded-xl border-2 text-center text-xs sm:text-sm font-bold transition-all cursor-pointer ${
                      selectedMedium === "en"
                        ? "border-blue-600 bg-blue-600 text-white shadow-md shadow-blue-500/25 ring-2 ring-blue-500/20"
                        : "border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-100 hover:bg-slate-200 dark:hover:bg-slate-700"
                    }`}
                  >
                    English Version
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: SYLLABUS & CHAPTER STATUS (NEW vs REVISION) */}
          {currentStep === 2 && (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  {lang === "bn" ? "২. বিষয় ও অধ্যায়ভিত্তিক সিলেবাস ট্র্যাকার" : "2. Subject Syllabus & Chapter Tracker"}
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  {lang === "bn"
                    ? "প্রতিটি বিষয়ের অধ্যায় খুলে চিহ্নিত করো কোনগুলো পড়া শেষ (যা রিভিশন সেশনে যাবে) এবং কোনগুলো বাকি আছে (যা নতুন পড়ার জন্য বরাদ্দ পাবে)।"
                    : "Expand subjects to mark chapters as Completed (for Spaced Revision) or Left to Study (for New Study slots)."}
                </p>
              </div>

              <div className="space-y-4">
                {catalogSubjects.map((sub) => {
                  const isSelected = selectedSubjects.includes(sub.slug);
                  const isWeak = weakSubjects.includes(sub.slug);
                  const isFocus = focusSubjects.includes(sub.slug);
                  const isExpanded = expandedSubject === sub.slug;
                  const chapters = sub.chapters || [];
                  const subStatus = chapterStatuses[sub.slug] || {};

                  // Counts
                  const includedChapters = chapters.filter((c) => subStatus[c.number] !== "excluded");
                  const includedCount = includedChapters.length;
                  const doneCount = chapters.filter((c) => subStatus[c.number] === "completed").length;
                  const newCount = chapters.filter((c) => (subStatus[c.number] === "new" || !subStatus[c.number])).length;
                  const excludedCount = chapters.length - includedCount;

                  return (
                    <div
                      key={sub.slug}
                      className={`rounded-xl border transition-all overflow-hidden ${
                        isSelected
                          ? "border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800/40 shadow-sm"
                          : "border-slate-200 dark:border-slate-800 opacity-60"
                      }`}
                    >
                      {/* Subject Header */}
                      <div className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50 dark:bg-slate-800/70">
                        <div className="flex items-center gap-3">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleSubject(sub.slug)}
                            className="w-4 h-4 rounded text-blue-600 focus:ring-blue-500 cursor-pointer"
                          />
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-sm text-slate-900 dark:text-white">
                                {sub.name_bn}
                              </span>
                              <span className="text-xs text-slate-500 dark:text-slate-400">({sub.name_en})</span>
                              {sub.is_stem && (
                                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                                  STEM
                                </span>
                              )}
                            </div>
                            <div className="text-xs text-slate-500 dark:text-slate-400 mt-1 flex flex-wrap items-center gap-2">
                              <span className="font-bold text-slate-800 dark:text-slate-200">সিলেবাসে অন্তর্ভুক্ত: {includedCount}/{sub.total_chapters}টি</span>
                              <span>•</span>
                              <span className="text-emerald-600 font-bold">{doneCount}টি পড়া শেষ</span>
                              <span>•</span>
                              <span className="text-blue-600 font-bold">{newCount}টি বাকি</span>
                              {excludedCount > 0 && (
                                <>
                                  <span>•</span>
                                  <span className="text-slate-400">{excludedCount}টি বাদ</span>
                                </>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Subject Actions */}
                        {isSelected && (
                          <div className="flex flex-wrap items-center gap-2">
                            <button
                              type="button"
                              onClick={() => toggleWeak(sub.slug)}
                              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                                isWeak
                                  ? "bg-rose-600 text-white shadow-sm ring-2 ring-rose-500/20"
                                  : "bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200 hover:bg-slate-300 dark:hover:bg-slate-600"
                              }`}
                            >
                              {isWeak ? "★ দুর্বল বিষয় (+৪০%)" : "দুর্বল?"}
                            </button>

                            <button
                              type="button"
                              onClick={() => toggleFocus(sub.slug)}
                              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                                isFocus
                                  ? "bg-blue-600 text-white shadow-sm ring-2 ring-blue-500/20"
                                  : "bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200 hover:bg-slate-300 dark:hover:bg-slate-600"
                              }`}
                            >
                              {isFocus ? "🎯 ফোকাস বিষয়" : "ফোকাস?"}
                            </button>

                            <button
                              type="button"
                              onClick={() => setExpandedSubject(isExpanded ? null : sub.slug)}
                              className="px-3 py-1.5 text-xs font-bold text-slate-800 dark:text-slate-100 bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg flex items-center gap-1.5 shadow-sm cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-600"
                            >
                              <span>অধ্যায়সমূহ ({chapters.length})</span>
                              {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                            </button>
                          </div>
                        )}
                      </div>

                      {/* Expandable Chapter List */}
                      {isSelected && isExpanded && (
                        <div className="p-4 border-t border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-900/50 space-y-3">
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs pb-2 border-b border-slate-200 dark:border-slate-700">
                            <span className="font-bold text-slate-700 dark:text-slate-300">
                              ১. সিলেবাসে যোগ/বাদ করো → ২. পড়া শেষ বা বাকি নির্ধারণ করো:
                            </span>
                            <div className="flex flex-wrap items-center gap-1.5">
                              <button
                                type="button"
                                onClick={() => setAllChaptersStatus(sub.slug, chapters, "new")}
                                className="px-2.5 py-1 rounded-lg bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300 hover:bg-blue-200 font-bold text-[11px] cursor-pointer"
                              >
                                সব সিলেবাসে নাও
                              </button>
                              <button
                                type="button"
                                onClick={() => setAllChaptersStatus(sub.slug, chapters, "completed")}
                                className="px-2.5 py-1 rounded-lg bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-200 font-bold text-[11px] cursor-pointer"
                              >
                                সব পড়া শেষ
                              </button>
                              <button
                                type="button"
                                onClick={() => setAllChaptersStatus(sub.slug, chapters, "excluded")}
                                className="px-2.5 py-1 rounded-lg bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-400 hover:bg-slate-300 font-bold text-[11px] cursor-pointer"
                              >
                                সব বাদ দাও
                              </button>
                            </div>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                            {chapters.map((ch) => {
                              const st = subStatus[ch.number] || "new";
                              const isIncluded = st !== "excluded";
                              return (
                                <div
                                  key={ch.number}
                                  className={`p-3 rounded-xl border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 text-xs shadow-sm ${
                                    isIncluded
                                      ? "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800"
                                      : "border-slate-200/60 dark:border-slate-800/60 bg-slate-100/60 dark:bg-slate-900/60 opacity-60 border-dashed"
                                  }`}
                                >
                                  {/* Left: Checkbox for In Syllabus + Title */}
                                  <div className="flex items-center gap-2.5 truncate pr-2">
                                    <input
                                      type="checkbox"
                                      checked={isIncluded}
                                      onChange={(e) => {
                                        const willInclude = e.target.checked;
                                        setChapterStatus(sub.slug, ch.number, willInclude ? "new" : "excluded");
                                      }}
                                      className="w-4 h-4 rounded text-blue-600 focus:ring-blue-500 cursor-pointer flex-shrink-0"
                                      title={isIncluded ? "সিলেবাস থেকে বাদ দিন" : "সিলেবাসে অন্তর্ভুক্ত করুন"}
                                    />
                                    <div className="truncate">
                                      <div className="flex items-center gap-1.5">
                                        <span className="font-bold text-slate-900 dark:text-white">
                                          অধ্যায় {ch.number}:
                                        </span>
                                        <span className="text-slate-800 dark:text-slate-200 truncate font-semibold">
                                          {ch.title_bn}
                                        </span>
                                      </div>
                                      <div className="text-[11px] text-slate-400">
                                        {ch.title_en} • আনুমানিক {ch.estimated_study_hours} ঘণ্টা
                                      </div>
                                    </div>
                                  </div>

                                  {/* Right: Status Actions */}
                                  <div className="flex items-center gap-1.5 flex-shrink-0 self-end sm:self-auto">
                                    {/* Topic-Mapped CQ Questions Button */}
                                    <button
                                      type="button"
                                      onClick={() =>
                                        setSelectedCqChapter({
                                          subject: sub.name_bn,
                                          subjectSlug: sub.slug,
                                          chapterNumber: ch.number,
                                          chapterTitle: ch.title_bn,
                                        })
                                      }
                                      className="px-2 py-1 rounded-lg text-[11px] font-bold text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/60 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 border border-indigo-200 dark:border-indigo-800 flex items-center gap-1 transition-all cursor-pointer"
                                      title="জ্ঞানমূলক (ক) ও অনুধাবন (খ) প্রশ্নসমূহ দেখুন"
                                    >
                                      <BookOpen className="w-3 h-3 text-indigo-600 dark:text-indigo-400" />
                                      <span>ক ও খ প্রশ্ন</span>
                                    </button>

                                    {isIncluded ? (
                                      <>
                                        <button
                                          type="button"
                                          onClick={() => setChapterStatus(sub.slug, ch.number, "completed")}
                                          className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all cursor-pointer ${
                                            st === "completed"
                                              ? "bg-emerald-600 text-white shadow-sm ring-2 ring-emerald-500/25"
                                              : "bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600"
                                          }`}
                                        >
                                          ✓ পড়া শেষ
                                        </button>
                                        <button
                                          type="button"
                                          onClick={() => setChapterStatus(sub.slug, ch.number, "new")}
                                          className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all cursor-pointer ${
                                            st === "new"
                                              ? "bg-blue-600 text-white shadow-sm ring-2 ring-blue-500/25"
                                              : "bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600"
                                          }`}
                                        >
                                          ⏳ বাকি
                                        </button>
                                      </>
                                    ) : (
                                      <span className="px-2.5 py-1 rounded-lg text-[10px] font-semibold text-slate-400 dark:text-slate-500 bg-slate-200/60 dark:bg-slate-800/60">
                                        ✕ পরীক্ষায় নেই (বাদ)
                                      </span>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* STEP 3: EXAM TARGET */}
          {currentStep === 3 && (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  {lang === "bn" ? "৩. লক্ষ্য পরীক্ষা ও পরীক্ষার তারিখ" : "3. Target Exam & Date"}
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  {lang === "bn"
                    ? "পরীক্ষার বাকি দিন হিসাব করে প্রতিদিনের পড়া ও স্পেসড রিভিশন সাইকেল নির্ধারিত হবে।"
                    : "The engine uses the days remaining to balance new syllabus completion with revision."}
                </p>
              </div>

              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                    {lang === "bn" ? "পরীক্ষার নাম:" : "Exam Name:"}
                  </label>
                  <select
                    value={examName}
                    onChange={(e) => setExamName(e.target.value)}
                    className="w-full p-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                  >
                    <option value="অর্ধবার্ষিক পরীক্ষা (Half-Yearly Exam)">অর্ধবার্ষিক পরীক্ষা (Half-Yearly Exam)</option>
                    <option value="বার্ষিক পরীক্ষা (Annual Exam)">বার্ষিক পরীক্ষা (Annual Exam)</option>
                    <option value="প্রাক-নির্বাচনী পরীক্ষা (Pre-Test Exam)">প্রাক-নির্বাচনী পরীক্ষা (Pre-Test Exam)</option>
                    <option value="এসএসসি / সমাপনী চূড়ান্ত পরীক্ষা (Final Exam)">এসএসসি / সমাপনী চূড়ান্ত পরীক্ষা (Final Exam)</option>
                    <option value="কাস্টম প্রস্তুতি লক্ষ্য (Custom Target)">কাস্টম প্রস্তুতি লক্ষ্য (Custom Target)</option>
                  </select>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                    {lang === "bn" ? "পরীক্ষা শুরু হওয়ার সম্ভাব্য তারিখ:" : "Target Exam Date:"}
                  </label>
                  <input
                    type="date"
                    value={examDate}
                    min={new Date().toISOString().split("T")[0]}
                    onChange={(e) => setExamDate(e.target.value)}
                    className="w-full p-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                  />
                </div>
              </div>
            </div>
          )}

          {/* STEP 4: DAILY HOURS & STUDY WINDOW */}
          {currentStep === 4 && (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  {lang === "bn" ? "৪. দৈনিক পড়াশোনার সময় ও পড়ার সময়সূচি" : "4. Daily Study Hours & Schedule"}
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  {lang === "bn"
                    ? "তোমার প্রতিদিনের পড়ার বাজেট এবং পড়ার রুটিনের ধরন বেছে নাও।"
                    : "Choose your comfortable daily study commitment and routine mode."}
                </p>
              </div>

              {/* Hours Slider */}
              <div className="space-y-3 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-700 dark:text-slate-300">
                    {lang === "bn" ? "দৈনিক পড়ার সময়:" : "Daily Study Budget:"}
                  </span>
                  <span className="text-base font-black text-blue-600 dark:text-blue-400">
                    {dailyHours} {lang === "bn" ? "ঘণ্টা" : "hours"} ({Math.round(dailyHours * 60)} {lang === "bn" ? "মিনিট" : "min"})
                  </span>
                </div>
                <input
                  type="range"
                  min="3.0"
                  max="8.0"
                  step="0.5"
                  value={dailyHours}
                  onChange={(e) => setDailyHours(Math.max(3.0, parseFloat(e.target.value)))}
                  className="w-full accent-blue-600 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-400 font-medium">
                  <span>৩ ঘণ্টা (সর্বনিম্ন)</span>
                  <span>৪.৫ ঘণ্টা (প্রস্তাবিত)</span>
                  <span>৮ ঘণ্টা</span>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">
                  {lang === "bn"
                    ? "💡 নিয়ম: প্রতিটি বিষয়ের গভীর মনোযোগের জন্য দৈনিক ন্যূনতম ৩ ঘণ্টা এবং বিষয়প্রতি কমপক্ষে ৩০ মিনিট বরাদ্দ রাখা হয়।"
                    : "💡 Policy: Minimum 3.0 hours daily and at least 30 minutes per subject session to ensure deep focus."}
                </p>
              </div>

              {/* 3 Routine Strategy Options */}
              <div className="space-y-3">
                <label className="text-xs font-bold text-slate-700 dark:text-slate-300 block">
                  {lang === "bn" ? "পড়ার রুটিনের ধরন বেছে নাও (৩টি বিকল্প):" : "Choose Study Routine Mode (3 Options):"}
                </label>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {/* Option 2: Core & Weak Daily + Alternating (Recommended) */}
                  <div
                    onClick={() => setRoutineStrategy("core_weak_daily")}
                    className={`p-4 rounded-xl border-2 cursor-pointer transition-all flex flex-col justify-between ${
                      routineStrategy === "core_weak_daily"
                        ? "border-blue-600 bg-blue-50/60 dark:bg-blue-950/40 shadow-sm ring-1 ring-blue-500/30"
                        : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-white dark:bg-slate-900"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                          {lang === "bn" ? "প্রস্তাবিত" : "Recommended"}
                        </span>
                        <Zap className={`w-4 h-4 ${routineStrategy === "core_weak_daily" ? "text-blue-600" : "text-slate-400"}`} />
                      </div>
                      <h4 className="text-xs font-bold text-slate-900 dark:text-white mb-1">
                        ২. প্রধান ও দুর্বল বিষয় প্রতিদিন + অন্য বিষয় অল্টারনেট
                      </h4>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                        গণিত, বিজ্ঞান ও দুর্বল বিষয়ে প্রতিদিন ৪৫-৬০+ মি। অন্য বিষয়গুলো শনি-সোম-বুধ ও রবি-মঙ্গল-বৃহস্পতি হিসেবে রোটেশন হবে (কমপক্ষে ৩৫-৪৫ মি)।
                      </p>
                    </div>
                    <div className="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 text-[10px] font-semibold text-blue-600 dark:text-blue-400">
                      ✓ সেরা ভারসাম্য ও ক্লান্তিহীন পড়া
                    </div>
                  </div>

                  {/* Option 3: Importance-Weighted Rotation */}
                  <div
                    onClick={() => setRoutineStrategy("importance_weighted_rotation")}
                    className={`p-4 rounded-xl border-2 cursor-pointer transition-all flex flex-col justify-between ${
                      routineStrategy === "importance_weighted_rotation"
                        ? "border-purple-600 bg-purple-50/60 dark:bg-purple-950/40 shadow-sm ring-1 ring-purple-500/30"
                        : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-white dark:bg-slate-900"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded-full bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
                          {lang === "bn" ? "গভীর ফোকাস" : "Deep Focus"}
                        </span>
                        <Brain className={`w-4 h-4 ${routineStrategy === "importance_weighted_rotation" ? "text-purple-600" : "text-slate-400"}`} />
                      </div>
                      <h4 className="text-xs font-bold text-slate-900 dark:text-white mb-1">
                        ৩. গুরুত্বপূর্ণ বিষয়ে বেশি সময়, অন্যদের কম
                      </h4>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                        প্রতিদিন ৩-৪টি বিষয়ে গভীর মনোযোগ (৫০-৭০ মি সেশন)। কঠিন বিষয় সপ্তাহে ৫ দিন, মাঝারি ৪ দিন এবং হালকা বিষয় সপ্তাহে ২ দিন।
                      </p>
                    </div>
                    <div className="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 text-[10px] font-semibold text-purple-600 dark:text-purple-400">
                      ✓ লম্বা ও গভীর স্টাডি ব্লকের জন্য আদর্শ
                    </div>
                  </div>

                  {/* Option 1: All Subjects Daily */}
                  <div
                    onClick={() => setRoutineStrategy("all_daily")}
                    className={`p-4 rounded-xl border-2 cursor-pointer transition-all flex flex-col justify-between ${
                      routineStrategy === "all_daily"
                        ? "border-emerald-600 bg-emerald-50/60 dark:bg-emerald-950/40 shadow-sm ring-1 ring-emerald-500/30"
                        : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-white dark:bg-slate-900"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">
                          {lang === "bn" ? "সব বিষয়" : "All Subjects"}
                        </span>
                        <BookOpen className={`w-4 h-4 ${routineStrategy === "all_daily" ? "text-emerald-600" : "text-slate-400"}`} />
                      </div>
                      <h4 className="text-xs font-bold text-slate-900 dark:text-white mb-1">
                        ১. প্রতিদিন সব বিষয়
                      </h4>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                        সবগুলো বিষয় প্রতিদিন নিয়ম করে স্পর্শ করা হবে। প্রতিটি বিষয়ের সেশন কমপক্ষে ৩০ মিনিট রাখা হবে।
                      </p>
                    </div>
                    <div className="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                      ✓ কোনো বিষয় বাদ না দিয়ে ধারাবাহিকতা
                    </div>
                  </div>
                </div>
              </div>

              {/* Study Window */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    {lang === "bn" ? "পড়ার শুরুর সময়:" : "Window Start:"}
                  </label>
                  <input
                    type="time"
                    value={studyWindowStart}
                    onChange={(e) => setStudyWindowStart(e.target.value)}
                    className="w-full p-2.5 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    {lang === "bn" ? "পড়ার শেষের সময়:" : "Window End:"}
                  </label>
                  <input
                    type="time"
                    value={studyWindowEnd}
                    onChange={(e) => setStudyWindowEnd(e.target.value)}
                    className="w-full p-2.5 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                  />
                </div>
              </div>
            </div>
          )}

          {/* STEP 5: LIVE CALCULATED DATASET PREVIEW & AI REVIEW */}
          {currentStep === 5 && (
            <div className="space-y-6">
              {/* AI Review Banner */}
              {aiReview && (
                <div className="p-5 rounded-2xl bg-indigo-50/80 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-900/60 shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Brain className="w-5 h-5 text-indigo-600" />
                      <h4 className="text-xs font-bold text-indigo-950 dark:text-indigo-200 uppercase tracking-wide">
                        {lang === "bn" ? "বাডি এআই দুর্বলতা ও রুটিন পর্যালোচনা" : "Buddy AI Weakness & Schedule Review"}
                      </h4>
                    </div>
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200">
                      Feasibility: {Math.round(aiReview.feasibility_score * 100)}% ({aiReview.ai_review_status.toUpperCase()})
                    </span>
                  </div>

                  <p className="text-xs text-indigo-900 dark:text-indigo-200 leading-relaxed font-medium">
                    {lang === "bn" ? aiReview.ai_guidance_bn : aiReview.ai_guidance_en}
                  </p>

                  {/* Recommendations */}
                  <div className="space-y-1.5 pt-1 border-t border-indigo-200/60 dark:border-indigo-900/40">
                    {aiReview.key_recommendations.map((rec, idx) => (
                      <div key={idx} className="text-[11px] text-indigo-800 dark:text-indigo-300 flex items-start gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0 mt-0.5" />
                        <span>{rec}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Allocation Summary Card */}
              {isCalculating ? (
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 text-center space-y-3">
                  <Clock className="w-8 h-8 text-blue-600 animate-spin mx-auto" />
                  <p className="text-xs text-slate-500">
                    {lang === "bn" ? "তোমার নতুন পড়া ও রিভিশন শিডিউল প্রস্তুত হচ্ছে..." : "Computing balanced study and revision dataset..."}
                  </p>
                </div>
              ) : allocation ? (
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
                  <div>
                    <h3 className="text-base font-bold text-slate-900 dark:text-white">
                      {lang === "bn" ? "৫. তোমার ব্যক্তিগত স্টাডি প্ল্যান পর্যালোচনা" : "5. Plan Review & Allocation Summary"}
                    </h3>
                    <p className="text-xs text-slate-500 mt-1">
                      {allocation.days_remaining} {lang === "bn" ? "দিন বাকি" : "days left"} •{" "}
                      {allocation.total_unread_chapters} {lang === "bn" ? "টি অধ্যায় নতুন পড়া" : "new chapters"} •{" "}
                      {allocation.total_completed_chapters} {lang === "bn" ? "টি অধ্যায় রিভিশন" : "revision chapters"}
                    </p>
                  </div>

                  {/* Breakdown Pills */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                    <div className="p-3 rounded-xl bg-blue-50 dark:bg-blue-950/30 border border-blue-100 dark:border-blue-900">
                      <div className="text-[10px] text-blue-600 dark:text-blue-400 font-semibold">নতুন পড়া (৭৫%)</div>
                      <div className="text-base font-black text-blue-700 dark:text-blue-300">
                        {allocation.breakdown_shares?.new_study_minutes ?? allocation.breakdown_shares?.new_study ?? allocation.breakdown_shares?.study ?? 0} মি
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-100 dark:border-emerald-900">
                      <div className="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold">দৈনিক রিভিশন (২৫%)</div>
                      <div className="text-base font-black text-emerald-700 dark:text-emerald-300">
                        {allocation.breakdown_shares?.spaced_revision_minutes ?? allocation.breakdown_shares?.spaced_revision ?? allocation.breakdown_shares?.revision ?? 0} মি
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900">
                      <div className="text-[10px] text-amber-700 dark:text-amber-300 font-semibold">শুক্র ও শনি রিভিশন</div>
                      <div className="text-base font-black text-amber-800 dark:text-amber-200">
                        ১২০ মি (২ ঘণ্টা)
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-100 dark:border-rose-900">
                      <div className="text-[10px] text-rose-600 dark:text-rose-400 font-semibold">দুর্বল বিষয়ে জোর</div>
                      <div className="text-base font-black text-rose-700 dark:text-rose-300">
                        {allocation.breakdown_shares?.weakness_practice_minutes ?? allocation.breakdown_shares?.weakness_practice ?? allocation.breakdown_shares?.weakness ?? 0} মি
                      </div>
                    </div>
                  </div>

                  {/* View Mode Switcher */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 border-t border-slate-200 dark:border-slate-800">
                    <div className="flex items-center gap-1.5 p-1 bg-slate-100 dark:bg-slate-800 rounded-xl">
                      <button
                        type="button"
                        onClick={() => setRoutineViewMode("day_by_day")}
                        className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                          routineViewMode === "day_by_day"
                            ? "bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm"
                            : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
                        }`}
                      >
                        📅 দিনভিত্তিক রুটিন (Day-by-Day View)
                      </button>
                      <button
                        type="button"
                        onClick={() => setRoutineViewMode("subject_summary")}
                        className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                          routineViewMode === "subject_summary"
                            ? "bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm"
                            : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
                        }`}
                      >
                        📊 বিষয়ভিত্তিক সারাংশ (Subject Breakdown)
                      </button>
                    </div>
                    <div className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
                      <span>প্রতিদিন ২৫% রিভিশন • শুক্র ও শনিবার স্কুল বন্ধ (২ ঘণ্টা মেগা রিভিশন)</span>
                    </div>
                  </div>

                  {/* VIEW 1: DAY-BY-DAY ROUTINE */}
                  {routineViewMode === "day_by_day" && (
                    <div className="space-y-4">
                      {/* Day Tabs - Full Width Distributed Grid */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 w-full pb-1">
                        {activeSchedule.map((day) => {
                          const isSelected = selectedDayId === day.day_id;
                          return (
                            <button
                              key={day.day_id}
                              type="button"
                              onClick={() => setSelectedDayId(day.day_id)}
                              className={`w-full py-2.5 px-2 rounded-xl text-xs font-bold transition-all flex flex-col items-center justify-center gap-1 cursor-pointer text-center ${
                                isSelected
                                  ? "bg-blue-600 text-white shadow-md ring-2 ring-blue-500/20"
                                  : day.is_weekend
                                  ? "bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-200 border border-amber-200 dark:border-amber-900/60 hover:bg-amber-100"
                                  : "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"
                              }`}
                            >
                              <span className="text-xs font-bold leading-tight">{day.day_name_bn}</span>
                              <span className={`text-[10px] font-normal leading-tight ${isSelected ? "text-blue-100" : "opacity-80"}`}>
                                {day.is_weekend ? "🏖️ ছুটি (২ঘণ্টা রিভিশন)" : `🏫 ${day.items.length}টি বিষয়`}
                              </span>
                            </button>
                          );
                        })}
                      </div>

                      {/* Active Day Detail Card */}
                      {(() => {
                        const day = activeSchedule.find((d) => d.day_id === selectedDayId) || activeSchedule[0];
                        if (!day) return null;

                        return (
                          <div className="p-5 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-4 shadow-sm">
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-200 dark:border-slate-700">
                              <div className="flex items-center gap-2">
                                <h4 className="text-sm font-bold text-slate-900 dark:text-white">
                                  {day.day_name_bn} ({day.day_name_en})
                                </h4>
                                <span
                                  className={`px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider ${
                                    day.is_weekend
                                      ? "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200"
                                      : "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
                                  }`}
                                >
                                  {day.school_status_label_bn}
                                </span>
                              </div>
                              <div className="flex items-center gap-2 text-xs font-semibold text-slate-600 dark:text-slate-300">
                                <span>মোট পড়ার সময়: {Math.floor(day.daily_total_minutes / 60)} ঘণ্টা {day.daily_total_minutes % 60} মি</span>
                                <span>•</span>
                                <span className="text-emerald-600 dark:text-emerald-400">২৫% রিভিশন নিশ্চিত</span>
                              </div>
                            </div>

                            {/* Friday & Saturday 2-Hour Mega Revision Banner */}
                            {day.is_weekend && (
                              <div className="p-3.5 rounded-xl bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-950/40 dark:to-orange-950/30 border border-amber-200 dark:border-amber-900/60 flex items-start gap-3">
                                <RotateCcw className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                                <div>
                                  <div className="text-xs font-bold text-amber-900 dark:text-amber-200 flex items-center gap-1.5">
                                    <span>🔄 সাপ্তাহিক মেগা রিভিশন ও প্র্যাকটিস ব্লক</span>
                                    <span className="px-2 py-0.5 rounded-md bg-amber-200/80 dark:bg-amber-800 text-amber-900 dark:text-amber-100 text-[10px] font-black">
                                      ১২০ মিনিট (২ ঘণ্টা)
                                    </span>
                                  </div>
                                  <p className="text-[11px] text-amber-800 dark:text-amber-300 mt-0.5 leading-relaxed">
                                    যেহেতু আজ স্কুল বন্ধ, তাই সারা সপ্তাহের পড়া ঝালিয়ে নিতে এবং লাইটনার বক্সের রিভিশন ও প্র্যাকটিস কুইজ দিতে ২ ঘণ্টা ডেডিকেটেড রিভিশন বরাদ্দ রাখা হয়েছে।
                                  </p>
                                </div>
                              </div>
                            )}

                            {/* Subjects Allocated for this Day */}
                            <div className="space-y-2.5">
                              <div className="text-xs font-bold text-slate-700 dark:text-slate-300 flex items-center justify-between">
                                <span>আজকের নির্ধারিত বিষয়সমূহ ({day.items.length}টি বিষয় • সব সেশন কমপক্ষে ৩০ মি):</span>
                                <span className="text-[11px] text-slate-400 font-normal">
                                  প্রতি বিষয়ে ৭৫% নতুন পড়া + ২৫% স্পেসড রিভিশন
                                </span>
                              </div>

                              <div className={`grid grid-cols-1 ${day.items.length === 2 ? "sm:grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-3"} gap-3`}>
                                {day.items.map((item) => (
                                  <div
                                    key={item.subject_slug}
                                    className="p-3.5 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 space-y-2.5 shadow-sm"
                                  >
                                    <div className="flex items-center justify-between">
                                      <span className="font-bold text-xs text-slate-900 dark:text-white flex items-center gap-1.5">
                                        {item.subject_name_bn}
                                        {item.is_weak && (
                                          <span className="px-1.5 py-0.5 rounded text-[9px] bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300 font-bold">
                                            দুর্বল (+৪০%)
                                          </span>
                                        )}
                                      </span>
                                      <span className="text-xs font-black text-blue-600 dark:text-blue-400">
                                        {item.total_minutes} মি
                                      </span>
                                    </div>

                                    {/* Split Bar */}
                                    <div className="w-full h-2 rounded-full bg-slate-100 dark:bg-slate-700 flex overflow-hidden">
                                      <div
                                        className="h-full bg-blue-500"
                                        style={{ width: `${Math.round((item.study_minutes / item.total_minutes) * 100)}%` }}
                                        title={`নতুন পড়া: ${item.study_minutes} মি`}
                                      />
                                      <div
                                        className="h-full bg-emerald-500"
                                        style={{ width: `${Math.round((item.revision_minutes / item.total_minutes) * 100)}%` }}
                                        title={`রিভিশন: ${item.revision_minutes} মি (২৫%)`}
                                      />
                                    </div>

                                    <div className="flex items-center justify-between text-[11px] font-medium text-slate-600 dark:text-slate-300 pt-0.5">
                                      <span className="text-blue-600 dark:text-blue-400">
                                        📖 পড়া: {item.study_minutes} মি (৭৫%)
                                      </span>
                                      <span className="text-emerald-600 dark:text-emerald-400">
                                        🔄 রিভিশন: {item.revision_minutes} মি (২৫%)
                                      </span>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        );
                      })()}

                      {/* Full Week At-a-Glance Table */}
                      <div className="space-y-2 pt-2">
                        <div className="text-xs font-bold text-slate-800 dark:text-slate-200">
                          পুরো সপ্তাহের রুটিন এক নজরে (Full Week Schedule):
                        </div>
                        <div className="overflow-x-auto">
                          <table className="w-full text-left text-xs text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
                            <thead className="bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                              <tr>
                                <th className="py-2.5 px-3">বার</th>
                                <th className="py-2.5 px-3">স্কুল স্ট্যাটাস</th>
                                <th className="py-2.5 px-3">নির্ধারিত বিষয়সমূহ (কমপক্ষে ৩০মি/সেশন)</th>
                                <th className="py-2.5 px-3">রিভিশন সময়</th>
                                <th className="py-2.5 px-3">মোট সময়</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-slate-800 bg-white dark:bg-slate-900">
                              {activeSchedule.map((d) => (
                                <tr
                                  key={d.day_id}
                                  onClick={() => setSelectedDayId(d.day_id)}
                                  className={`cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/60 ${
                                    selectedDayId === d.day_id ? "bg-blue-50/50 dark:bg-blue-950/30" : ""
                                  }`}
                                >
                                  <td className="py-2.5 px-3 font-bold text-slate-900 dark:text-white">
                                    {d.day_name_bn}
                                  </td>
                                  <td className="py-2.5 px-3">
                                    <span
                                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                        d.is_weekend
                                          ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200"
                                          : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                                      }`}
                                    >
                                      {d.school_status_label_bn}
                                    </span>
                                  </td>
                                  <td className="py-2.5 px-3">
                                    <div className="flex items-center gap-1.5 flex-wrap">
                                      {d.items.map((it) => (
                                        <span
                                          key={it.subject_slug}
                                          className="px-2 py-0.5 rounded-md bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 font-semibold text-[11px]"
                                        >
                                          {it.subject_name_bn} ({it.total_minutes}মি)
                                        </span>
                                      ))}
                                      {d.is_weekend && (
                                        <span className="px-2 py-0.5 rounded-md bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 font-bold text-[11px]">
                                          + ২ঘণ্টা মেগা রিভিশন
                                        </span>
                                      )}
                                    </div>
                                  </td>
                                  <td className="py-2.5 px-3 text-emerald-600 font-bold">
                                    {d.daily_revision_minutes} মি
                                  </td>
                                  <td className="py-2.5 px-3 font-black text-slate-900 dark:text-white">
                                    {Math.floor(d.daily_total_minutes / 60)}ঘ {d.daily_total_minutes % 60}মি
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* VIEW 2: SUBJECT BREAKDOWN TABLE */}
                  {routineViewMode === "subject_summary" && (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs text-slate-600 dark:text-slate-300">
                        <thead className="bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-b border-slate-200 dark:border-slate-700">
                          <tr>
                            <th className="py-2.5 px-3">বিষয়</th>
                            <th className="py-2.5 px-3">সিলেবাসে অধ্যায়</th>
                            <th className="py-2.5 px-3">পড়ার দিন ও শিডিউল</th>
                            <th className="py-2.5 px-3">সেশনের সময়</th>
                            <th className="py-2.5 px-3">দৈনিক গড় মোট</th>
                            <th className="py-2.5 px-3">স্পেসড রিভিশন সাইকেল</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                          {allocation.subjects.map((s) => {
                            const totalSyllabusCh = s.chapter_breakdown
                              ? s.chapter_breakdown.filter((c) => c.status !== "excluded").length
                              : s.total_chapters || 0;
                            const completedCh = s.completed_chapters_count ?? (s.chapter_breakdown ? s.chapter_breakdown.filter((c) => c.status === "completed").length : 0);
                            const newCh = Math.max(0, totalSyllabusCh - completedCh);

                            const durationMins = s.session_duration_minutes || Math.max(30, s.daily_total_minutes);
                            const daysLabel = s.days_schedule_label || (s.sessions_per_week ? `সপ্তাহে ${s.sessions_per_week} দিন` : "প্রতিদিন");

                            return (
                              <tr key={s.slug} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                                <td className="py-2.5 px-3 font-semibold text-slate-900 dark:text-white">
                                  <div className="flex items-center gap-1.5 flex-wrap">
                                    <span>{s.name_bn}</span>
                                    {s.is_weak && (
                                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 font-bold">
                                        দুর্বল
                                      </span>
                                    )}
                                    {s.is_focus && !s.is_weak && (
                                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-blue-100 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 font-bold">
                                        ফোকাস
                                      </span>
                                    )}
                                  </div>
                                </td>
                                <td className="py-2.5 px-3">
                                  <span className="text-blue-600 font-medium">{newCh}টি বাকি</span> •{" "}
                                  <span className="text-emerald-600 font-medium">{completedCh}টি শেষ</span>
                                </td>
                                <td className="py-2.5 px-3">
                                  <span className="font-medium text-slate-800 dark:text-slate-200">
                                    {daysLabel}
                                  </span>
                                </td>
                                <td className="py-2.5 px-3">
                                  <span className="font-bold text-blue-600 dark:text-blue-400">
                                    {durationMins} মি
                                  </span>
                                  <span className="text-[10px] text-slate-400 block font-normal">
                                    (ন্যূনতম ৩০ মি)
                                  </span>
                                </td>
                                <td className="py-2.5 px-3 font-bold text-slate-900 dark:text-white">
                                  {s.daily_total_minutes} মি
                                </td>
                                <td className="py-2.5 px-3 font-mono text-[11px] text-slate-500 dark:text-slate-400">
                                  {(s.revision_box_interval_days || [1, 3, 7, 14]).join("-")} দিন
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          )}

          {/* Wizard Footer Navigation */}
          <div className="flex items-center justify-between pt-2">
            {currentStep > 1 ? (
              <button
                type="button"
                onClick={() => setCurrentStep((prev) => prev - 1)}
                className="px-4 py-2 text-xs font-semibold rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-100 text-slate-700 dark:text-slate-300 flex items-center gap-1.5 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
                {lang === "bn" ? "আগের ধাপ" : "Back"}
              </button>
            ) : <div />}

            {currentStep < 5 ? (
              <button
                type="button"
                onClick={() => setCurrentStep((prev) => prev + 1)}
                className="px-5 py-2.5 text-xs font-semibold rounded-xl bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-1.5 shadow-md transition-all"
              >
                {lang === "bn" ? "পরবর্তী ধাপ" : "Next Step"}
                <ChevronRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleFinishOnboarding}
                disabled={isSubmitting}
                className="px-6 py-2.5 text-xs font-bold rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white flex items-center gap-1.5 shadow-md transition-all"
              >
                {isSubmitting ? (
                  <>
                    <Clock className="w-4 h-4 animate-spin" />
                    {lang === "bn" ? "সংরক্ষণ হচ্ছে..." : "Saving Setup..."}
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    {lang === "bn" ? "এই রুটিন চালু করো (Activate Plan)" : "Activate My Study Plan"}
                  </>
                )}
              </button>
            )}
          </div>
        </>
      )}
      </>
    )}

      {errorMsg && (
        <div className="p-3 rounded-xl bg-rose-50 text-rose-800 border border-rose-200 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Topic-Mapped CQ (ক ও খ) Questions Drawer / Modal */}
      {selectedCqChapter && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fadeIn">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-2xl w-full max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="p-4 sm:p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50 dark:bg-slate-800/50">
              <div>
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                    {selectedCqChapter.subject} • অধ্যায় {toBengaliDigits(selectedCqChapter.chapterNumber)}
                  </span>
                  <span className="text-xs text-slate-500 font-medium">
                    সৃজনশীল প্রশ্ন ব্যাংক
                  </span>
                </div>
                <h3 className="text-base sm:text-lg font-black text-slate-900 dark:text-white mt-1">
                  {selectedCqChapter.chapterTitle}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedCqChapter(null)}
                className="w-8 h-8 rounded-full bg-slate-200/60 dark:bg-slate-700/60 hover:bg-slate-300 dark:hover:bg-slate-600 text-slate-600 dark:text-slate-300 flex items-center justify-center font-bold text-sm cursor-pointer"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-4 sm:p-5 overflow-y-auto space-y-4">
              {(() => {
                const questions = getCQQuestions({
                  subject: selectedCqChapter.subject,
                  chapterNumber: selectedCqChapter.chapterNumber,
                });

                if (questions.length === 0) {
                  return (
                    <div className="text-center py-8 text-slate-500 text-xs">
                      এই অধ্যায়ের জন্য সৃজনশীল প্রশ্ন শীঘ্রই যুক্ত করা হবে।
                    </div>
                  );
                }

                return questions.map((q) => (
                  <div
                    key={q.id}
                    className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-850 space-y-2.5"
                  >
                    {/* Tagging */}
                    <div className="flex items-center justify-between gap-2 flex-wrap text-[11px]">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span
                          className={`px-2 py-0.5 rounded-full font-bold ${
                            q.type === "ka_knowledge"
                              ? "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300"
                              : "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300"
                          }`}
                        >
                          {q.type === "ka_knowledge" ? "জ্ঞানমূলক (ক) • ১ নম্বর" : "অনুধাবনমূলক (খ) • ২ নম্বর"}
                        </span>
                        <span className="text-slate-600 dark:text-slate-300 font-semibold">
                          টপিক: {q.subtopic_tag}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-400 font-medium">
                        পাঠ্যবই পৃষ্ঠা: {toBengaliDigits(q.printed_page)}
                      </span>
                    </div>

                    {/* Question text */}
                    <div className="text-sm font-bold text-slate-900 dark:text-white leading-relaxed">
                      {q.question_bn}
                    </div>

                    {/* Model Answer & Rubric */}
                    <div className="text-xs p-3 rounded-lg bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700/80 space-y-1.5">
                      <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                        আদর্শ উত্তর (Model Answer):
                      </div>
                      <div className="text-slate-700 dark:text-slate-300 leading-relaxed font-normal">
                        {q.model_answer_bn}
                      </div>
                      <div className="pt-1.5 border-t border-slate-100 dark:border-slate-700/50 flex items-center gap-2 flex-wrap text-[10px] text-slate-500">
                        <span className="font-bold">মূল কি-ওয়ার্ড/রুব্রিক:</span>
                        {q.key_rubric_points.map((pt, idx) => (
                          <span
                            key={idx}
                            className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300"
                          >
                            • {pt}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                ));
              })()}
            </div>

            {/* Modal Footer */}
            <div className="p-3 bg-slate-50 dark:bg-slate-800/50 border-t border-slate-200 dark:border-slate-800 flex justify-end">
              <button
                type="button"
                onClick={() => setSelectedCqChapter(null)}
                className="px-4 py-2 text-xs font-bold rounded-xl bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 text-slate-800 dark:text-slate-200 cursor-pointer"
              >
                বন্ধ করুন (Close)
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
