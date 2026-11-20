"use client";

import React, { useState, useEffect } from "react";
import {
  RotateCcw,
  CheckCircle2,
  Clock,
  BookOpen,
  ArrowRight,
  Sparkles,
  Layers,
  Filter,
  Flame,
  Calendar,
} from "lucide-react";
import {
  AuthenticRevisionItem,
  getActiveRevisionQueue,
} from "@/lib/revision-queue-engine";
import RevisionSessionView from "./RevisionSessionView";
import { toBengaliDigits, Language } from "@/lib/i18n";

interface RevisionQueueViewProps {
  lang?: Language;
  onNavigateToToday?: () => void;
}

export default function RevisionQueueView({
  lang = "bn",
  onNavigateToToday,
}: RevisionQueueViewProps) {
  const [queue, setQueue] = useState<AuthenticRevisionItem[]>([]);
  const [inSession, setInSession] = useState(false);
  const [sessionItems, setSessionItems] = useState<AuthenticRevisionItem[]>([]);
  const [selectedFilter, setSelectedFilter] = useState<"all" | "due" | 1 | 2 | 3 | 4 | 5>("all");

  const loadQueue = () => {
    const q = getActiveRevisionQueue();
    setQueue(q);
  };

  useEffect(() => {
    loadQueue();
  }, []);

  const dueItems = queue.filter((i) => i.is_due);

  // Box statistics
  const boxCounts = {
    1: queue.filter((i) => i.box === 1).length,
    2: queue.filter((i) => i.box === 2).length,
    3: queue.filter((i) => i.box === 3).length,
    4: queue.filter((i) => i.box === 4).length,
    5: queue.filter((i) => i.box === 5).length,
  };

  const handleStartSession = (customItems?: AuthenticRevisionItem[]) => {
    const itemsToReview = customItems || (dueItems.length > 0 ? dueItems : queue.slice(0, 5));
    setSessionItems(itemsToReview);
    setInSession(true);
  };

  const handleBackFromSession = () => {
    setInSession(false);
    loadQueue();
  };

  if (inSession) {
    return (
      <RevisionSessionView
        lang={lang}
        initialItems={sessionItems}
        onBackToProgress={handleBackFromSession}
      />
    );
  }

  // Filter items
  const filteredItems = queue.filter((item) => {
    if (selectedFilter === "all") return true;
    if (selectedFilter === "due") return item.is_due;
    return item.box === selectedFilter;
  });

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-8">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
              {lang === "bn" ? "স্পেসড রিপিটেশন অ্যালগরিদম" : "Spaced Repetition Algorithm"}
            </span>
            <span className="text-xs text-slate-500">
              {lang === "bn" ? "প্রমাণভিত্তিক পাঠ্যবই ডেটাসেট" : "Authentic Curriculum Dataset"}
            </span>
          </div>
          <h2 className="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
            <RotateCcw className="w-6 h-6 text-indigo-600" />
            {lang === "bn" ? "রিভিশন কিউ ও লাইটনার বক্স" : "Revision Queue & Leitner Boxes"}
          </h2>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 mt-1">
            {lang === "bn"
              ? "পড়া ভুলে যাওয়া রোধ করতে লাইটনার ৫-বক্স পদ্ধতিতে নির্ধারিত ব্যবধানে অধ্যায়গুলো রিভিশন দাও।"
              : "Retain 90%+ concepts by reviewing curriculum topics on scientifically spaced intervals."}
          </p>
        </div>

        {/* Start Due Session Button */}
        <button
          onClick={() => handleStartSession()}
          className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-700 hover:to-blue-700 text-white text-xs sm:text-sm font-bold rounded-xl shadow-md hover:shadow-lg transition-all self-start sm:self-auto cursor-pointer"
        >
          <RotateCcw className="w-4 h-4 animate-spin-reverse" />
          <span>
            {lang === "bn"
              ? `আজকের রিভিশন শুরু করো (${toBengaliDigits(dueItems.length)}টি বাকি)`
              : `Start Today's Revision (${dueItems.length} Due)`}
          </span>
        </button>
      </div>

      {/* Leitner 5-Box Pipeline Visualization */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
            <Layers className="w-4 h-4 text-indigo-500" />
            {lang === "bn" ? "লাইটনার ৫-বক্স মেমোরি পাইপলাইন" : "Leitner 5-Box Memory Pipeline"}
          </h3>
          <span className="text-xs text-slate-500 font-medium">
            {lang === "bn" ? `মোট অধ্যায় কিউ: ${toBengaliDigits(queue.length)}টি` : `Total Queued: ${queue.length} topics`}
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {/* Box 1 */}
          <div
            onClick={() => setSelectedFilter(selectedFilter === 1 ? "all" : 1)}
            className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
              selectedFilter === 1
                ? "border-rose-500 bg-rose-50 dark:bg-rose-950/40 ring-2 ring-rose-400"
                : "border-rose-200 dark:border-rose-900/60 bg-rose-50/60 dark:bg-rose-950/20 hover:border-rose-300"
            }`}
          >
            <div className="flex items-center justify-between text-xs font-bold text-rose-700 dark:text-rose-300">
              <span>Box 1</span>
              <span>{lang === "bn" ? "১ দিন" : "1 Day"}</span>
            </div>
            <div className="text-2xl font-extrabold text-rose-900 dark:text-rose-100 mt-2">
              {lang === "bn" ? toBengaliDigits(boxCounts[1]) : boxCounts[1]}
            </div>
            <p className="text-[11px] text-rose-600 dark:text-rose-300 mt-1">
              {lang === "bn" ? "প্রতিদিনের রিভিশন" : "Daily Review"}
            </p>
          </div>

          {/* Box 2 */}
          <div
            onClick={() => setSelectedFilter(selectedFilter === 2 ? "all" : 2)}
            className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
              selectedFilter === 2
                ? "border-amber-500 bg-amber-50 dark:bg-amber-950/40 ring-2 ring-amber-400"
                : "border-amber-200 dark:border-amber-900/60 bg-amber-50/60 dark:bg-amber-950/20 hover:border-amber-300"
            }`}
          >
            <div className="flex items-center justify-between text-xs font-bold text-amber-700 dark:text-amber-300">
              <span>Box 2</span>
              <span>{lang === "bn" ? "৩ দিন" : "3 Days"}</span>
            </div>
            <div className="text-2xl font-extrabold text-amber-900 dark:text-amber-100 mt-2">
              {lang === "bn" ? toBengaliDigits(boxCounts[2]) : boxCounts[2]}
            </div>
            <p className="text-[11px] text-amber-600 dark:text-amber-300 mt-1">
              {lang === "bn" ? "প্রাথমিক ধারণ" : "Initial Retention"}
            </p>
          </div>

          {/* Box 3 */}
          <div
            onClick={() => setSelectedFilter(selectedFilter === 3 ? "all" : 3)}
            className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
              selectedFilter === 3
                ? "border-blue-500 bg-blue-50 dark:bg-blue-950/40 ring-2 ring-blue-400"
                : "border-blue-200 dark:border-blue-900/60 bg-blue-50/60 dark:bg-blue-950/20 hover:border-blue-300"
            }`}
          >
            <div className="flex items-center justify-between text-xs font-bold text-blue-700 dark:text-blue-300">
              <span>Box 3</span>
              <span>{lang === "bn" ? "৭ দিন" : "7 Days"}</span>
            </div>
            <div className="text-2xl font-extrabold text-blue-900 dark:text-blue-100 mt-2">
              {lang === "bn" ? toBengaliDigits(boxCounts[3]) : boxCounts[3]}
            </div>
            <p className="text-[11px] text-blue-600 dark:text-blue-300 mt-1">
              {lang === "bn" ? "মাঝারি ধারণ" : "Intermediate"}
            </p>
          </div>

          {/* Box 4 */}
          <div
            onClick={() => setSelectedFilter(selectedFilter === 4 ? "all" : 4)}
            className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
              selectedFilter === 4
                ? "border-purple-500 bg-purple-50 dark:bg-purple-950/40 ring-2 ring-purple-400"
                : "border-purple-200 dark:border-purple-900/60 bg-purple-50/60 dark:bg-purple-950/20 hover:border-purple-300"
            }`}
          >
            <div className="flex items-center justify-between text-xs font-bold text-purple-700 dark:text-purple-300">
              <span>Box 4</span>
              <span>{lang === "bn" ? "১৪ দিন" : "14 Days"}</span>
            </div>
            <div className="text-2xl font-extrabold text-purple-900 dark:text-purple-100 mt-2">
              {lang === "bn" ? toBengaliDigits(boxCounts[4]) : boxCounts[4]}
            </div>
            <p className="text-[11px] text-purple-600 dark:text-purple-300 mt-1">
              {lang === "bn" ? "মজবুত স্মৃতি" : "Strong Memory"}
            </p>
          </div>

          {/* Box 5 */}
          <div
            onClick={() => setSelectedFilter(selectedFilter === 5 ? "all" : 5)}
            className={`col-span-2 sm:col-span-1 p-3.5 rounded-xl border transition-all cursor-pointer ${
              selectedFilter === 5
                ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-950/40 ring-2 ring-emerald-400"
                : "border-emerald-200 dark:border-emerald-900/60 bg-emerald-50/60 dark:bg-emerald-950/20 hover:border-emerald-300"
            }`}
          >
            <div className="flex items-center justify-between text-xs font-bold text-emerald-700 dark:text-emerald-300">
              <span>Box 5</span>
              <span>{lang === "bn" ? "৩০ দিন" : "30 Days"}</span>
            </div>
            <div className="text-2xl font-extrabold text-emerald-900 dark:text-emerald-100 mt-2">
              {lang === "bn" ? toBengaliDigits(boxCounts[5]) : boxCounts[5]}
            </div>
            <p className="text-[11px] text-emerald-600 dark:text-emerald-300 mt-1">
              {lang === "bn" ? "সম্পূর্ণ আয়ত্তে" : "Fully Mastered"}
            </p>
          </div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
        <button
          onClick={() => setSelectedFilter("all")}
          className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer whitespace-nowrap ${
            selectedFilter === "all"
              ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900"
              : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"
          }`}
        >
          {lang === "bn" ? `সকল অধ্যায় (${toBengaliDigits(queue.length)})` : `All Topics (${queue.length})`}
        </button>

        <button
          onClick={() => setSelectedFilter("due")}
          className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer whitespace-nowrap flex items-center gap-1.5 ${
            selectedFilter === "due"
              ? "bg-rose-600 text-white shadow-sm"
              : "bg-rose-100 text-rose-700 hover:bg-rose-200 dark:bg-rose-950/50 dark:text-rose-300"
          }`}
        >
          <Clock className="w-3.5 h-3.5" />
          {lang === "bn" ? `আজকের বাকি (${toBengaliDigits(dueItems.length)})` : `Due Today (${dueItems.length})`}
        </button>

        {[1, 2, 3, 4, 5].map((b) => (
          <button
            key={b}
            onClick={() => setSelectedFilter(b as any)}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer whitespace-nowrap ${
              selectedFilter === b
                ? "bg-indigo-600 text-white shadow-sm"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"
            }`}
          >
            Box {b} ({lang === "bn" ? toBengaliDigits(boxCounts[b as keyof typeof boxCounts]) : boxCounts[b as keyof typeof boxCounts]})
          </button>
        ))}
      </div>

      {/* Revision Items List with Proper Evidence */}
      <div className="space-y-3.5">
        {filteredItems.map((item) => {
          let boxBadge = "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border-rose-200";
          if (item.box === 2) boxBadge = "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border-amber-200";
          else if (item.box === 3) boxBadge = "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 border-blue-200";
          else if (item.box === 4) boxBadge = "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300 border-purple-200";
          else if (item.box === 5) boxBadge = "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border-emerald-200";

          return (
            <div
              key={item.id}
              className="p-4 sm:p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm hover:border-indigo-300 dark:hover:border-indigo-800 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4"
            >
              <div className="space-y-1.5 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 px-2.5 py-0.5 rounded-full">
                    {item.subject}
                  </span>
                  <span className={`text-[11px] font-bold px-2 py-0.5 rounded border ${boxBadge}`}>
                    Box {item.box} • {lang === "bn" ? `${toBengaliDigits(item.interval_days)} দিন ব্যবধান` : `${item.interval_days}d interval`}
                  </span>
                  {item.is_due ? (
                    <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-rose-50 text-rose-600 dark:bg-rose-950/60 dark:text-rose-400 border border-rose-200">
                      {lang === "bn" ? "আজ রিভিশন বাকি" : "Due Today"}
                    </span>
                  ) : (
                    <span className="text-[11px] text-slate-500 flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {lang === "bn" ? `পরবর্তী রিভিশন: ${item.due_date}` : `Next due: ${item.due_date}`}
                    </span>
                  )}
                </div>

                <h4 className="text-sm sm:text-base font-bold text-slate-900 dark:text-white">
                  {item.chapter_title}
                </h4>

                {/* Evidence & Printed Page Citation */}
                <div className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-3 flex-wrap">
                  <span className="flex items-center gap-1 font-medium text-slate-700 dark:text-slate-300">
                    <BookOpen className="w-3.5 h-3.5 text-indigo-500" />
                    {item.book_title}
                  </span>
                  <span className="text-indigo-600 dark:text-indigo-400 font-semibold">
                    📖 এনসিটিবি পাঠ্যবই পৃষ্ঠা নং {lang === "bn" ? toBengaliDigits(item.printed_page_start) : item.printed_page_start}–{lang === "bn" ? toBengaliDigits(item.printed_page_end) : item.printed_page_end}
                  </span>
                </div>
              </div>

              {/* Action */}
              <div className="flex items-center gap-2 self-start sm:self-auto">
                <button
                  type="button"
                  onClick={() => handleStartSession([item])}
                  className={`px-4 py-2 text-xs font-bold rounded-xl transition-all flex items-center gap-1.5 cursor-pointer shadow-sm ${
                    item.is_due
                      ? "bg-indigo-600 hover:bg-indigo-700 text-white"
                      : "bg-slate-100 hover:bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-200"
                  }`}
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>{item.is_due ? (lang === "bn" ? "রিভিশন দিন" : "Review Now") : (lang === "bn" ? "পুনরায় দেখুন" : "Practice")}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
