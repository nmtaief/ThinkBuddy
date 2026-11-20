"use client";

import React, { useState } from "react";
import {
  RotateCcw,
  CheckCircle2,
  XCircle,
  ArrowRight,
  Sparkles,
  Award,
  ChevronLeft,
  BookOpen,
} from "lucide-react";
import {
  AuthenticRevisionItem,
  getActiveRevisionQueue,
  recordRevisionReviewOutcome,
} from "@/lib/revision-queue-engine";
import { toBengaliDigits } from "@/lib/i18n";

interface RevisionSessionViewProps {
  onBackToProgress: () => void;
  lang?: "bn" | "en";
  initialItems?: AuthenticRevisionItem[];
}

export default function RevisionSessionView({
  onBackToProgress,
  lang = "bn",
  initialItems,
}: RevisionSessionViewProps) {
  const [items] = useState<AuthenticRevisionItem[]>(() => {
    if (initialItems && initialItems.length > 0) return initialItems;
    const all = getActiveRevisionQueue();
    const due = all.filter((i) => i.is_due);
    return due.length > 0 ? due : all.slice(0, 5);
  });

  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState<number | null>(null);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [score, setScore] = useState(0);
  const [boxTransitions, setBoxTransitions] = useState<
    { id: string; oldBox: number; newBox: number; nextDueDate: string; isCorrect: boolean }[]
  >([]);
  const [isCompleted, setIsCompleted] = useState(false);

  const currentItem = items[currentIndex];

  const handleSelectOption = (idx: number) => {
    if (isSubmitted) return;
    setSelectedOption(idx);
  };

  const handleSubmitAnswer = () => {
    if (selectedOption === null || isSubmitted || !currentItem) return;
    const isCorrect = selectedOption === currentItem.question.correctIndex;
    setIsSubmitted(true);

    if (isCorrect) {
      setScore((prev) => prev + 1);
    }

    // Persist real Leitner transition
    const { transition } = recordRevisionReviewOutcome(currentItem.id, isCorrect);
    setBoxTransitions((prev) => [...prev, transition]);
  };

  const handleNext = () => {
    if (currentIndex + 1 < items.length) {
      setCurrentIndex((prev) => prev + 1);
      setSelectedOption(null);
      setIsSubmitted(false);
    } else {
      setIsCompleted(true);
    }
  };

  if (!currentItem || items.length === 0) {
    return (
      <div className="max-w-xl mx-auto py-12 px-4 text-center space-y-5">
        <div className="w-16 h-16 bg-emerald-100 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400 rounded-full flex items-center justify-center mx-auto shadow-md">
          <CheckCircle2 className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">
          {lang === "bn" ? "আজকের কোনো রিভিশন বাকি নেই!" : "No Revision Items Due Today!"}
        </h2>
        <p className="text-sm text-slate-500">
          {lang === "bn"
            ? "সবগুলো লাইটনার বক্সের নির্ধারিত রিভিশন সম্পন্ন হয়েছে। নতুন অধ্যায় পড়ে রিভিশন কিউ বৃদ্ধি করো।"
            : "All scheduled Leitner box revisions are up to date. Keep studying new chapters to grow your queue."}
        </p>
        <button
          onClick={onBackToProgress}
          className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-xl shadow-md transition-all cursor-pointer"
        >
          {lang === "bn" ? "রিভিশন কিউতে ফিরুন" : "Back to Revision Queue"}
        </button>
      </div>
    );
  }

  if (isCompleted) {
    return (
      <div className="max-w-xl mx-auto py-10 px-4 text-center space-y-6">
        <div className="w-16 h-16 bg-emerald-100 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400 rounded-full flex items-center justify-center mx-auto shadow-md">
          <Award className="w-8 h-8" />
        </div>

        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">
            {lang === "bn" ? "রিভিশন সেশন সম্পন্ন!" : "Revision Session Completed!"}
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            {lang === "bn"
              ? `তুমি ${toBengaliDigits(items.length)}টি প্রশ্নের মধ্যে ${toBengaliDigits(score)}টি সঠিক উত্তর দিয়েছ।`
              : `You scored ${score} out of ${items.length} revision questions.`}
          </p>
        </div>

        {/* Leitner Box Movement Summary */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 text-left space-y-3 shadow-sm">
          <h4 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide flex items-center justify-between">
            <span>{lang === "bn" ? "লাইটনার বাক্স স্থানান্তর (Leitner Movement)" : "Leitner Repetition Movement"}</span>
            <span className="text-[11px] text-slate-500 font-normal">
              {lang === "bn" ? "সঠিক ⟶ বক্স বৃদ্ধি • ভুল ⟶ বক্স ১ এ রিসেট" : "Correct ⟶ Next Box • Wrong ⟶ Reset to Box 1"}
            </span>
          </h4>
          <div className="space-y-2">
            {boxTransitions.map((t, idx) => {
              const it = items[idx];
              return (
                <div
                  key={idx}
                  className="flex items-center justify-between text-xs p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800"
                >
                  <div className="flex items-center gap-2">
                    {t.isCorrect ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                    ) : (
                      <XCircle className="w-4 h-4 text-rose-500 flex-shrink-0" />
                    )}
                    <div>
                      <div className="font-bold text-slate-800 dark:text-slate-200">
                        {it?.subject}
                      </div>
                      <div className="text-[11px] text-slate-500 dark:text-slate-400">
                        {it?.chapter_title} (পৃষ্ঠা {lang === "bn" ? toBengaliDigits(it?.question.textbook_page || 1) : it?.question.textbook_page})
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 font-mono text-[11px]">
                      Box {t.oldBox}
                    </span>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                    <span
                      className={`px-2 py-0.5 rounded font-mono text-[11px] font-bold ${
                        t.isCorrect
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                          : "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                      }`}
                    >
                      Box {t.newBox}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <button
          onClick={onBackToProgress}
          className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-xl shadow-md transition-all cursor-pointer"
        >
          {lang === "bn" ? "রিভিশন কিউতে ফিরুন" : "Back to Revision Queue"}
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header bar */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBackToProgress}
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer"
        >
          <ChevronLeft className="w-4 h-4" />
          {lang === "bn" ? "ফিরে যান" : "Back"}
        </button>

        <div className="flex items-center gap-2">
          <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
            {lang === "bn" ? "প্রশ্ন " : "Question "} {lang === "bn" ? toBengaliDigits(currentIndex + 1) : currentIndex + 1} / {lang === "bn" ? toBengaliDigits(items.length) : items.length}
          </span>
          <span className="text-xs font-semibold px-2 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 flex items-center gap-1">
            <RotateCcw className="w-3 h-3" /> Box {currentItem.box} ({lang === "bn" ? `${toBengaliDigits(currentItem.interval_days)} দিন ব্যবধান` : `${currentItem.interval_days}d interval`})
          </span>
        </div>
      </div>

      {/* Progress tracker bar */}
      <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
        <div
          className="h-full bg-indigo-600 rounded-full transition-all duration-300"
          style={{ width: `${((currentIndex + 1) / items.length) * 100}%` }}
        />
      </div>

      {/* Question Card */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-5">
        <div>
          <div className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 mb-1 flex items-center gap-1.5">
            <BookOpen className="w-3.5 h-3.5" />
            {currentItem.subject} • {currentItem.chapter_title}
          </div>
          <div className="text-[11px] text-slate-500 dark:text-slate-400 mb-2">
            📖 {currentItem.book_title} (পৃষ্ঠা {lang === "bn" ? toBengaliDigits(currentItem.printed_page_start) : currentItem.printed_page_start}–{lang === "bn" ? toBengaliDigits(currentItem.printed_page_end) : currentItem.printed_page_end})
          </div>
          <h3 className="text-base font-bold text-slate-900 dark:text-white leading-relaxed">
            {currentItem.question.question_bn}
          </h3>
        </div>

        {/* Options */}
        <div className="space-y-2.5">
          {currentItem.question.options_bn.map((opt, idx) => {
            let stateClass = "border-slate-200 dark:border-slate-800 hover:border-indigo-400";
            if (selectedOption === idx) {
              stateClass = "border-indigo-600 bg-indigo-50/50 dark:bg-indigo-950/20";
            }
            if (isSubmitted) {
              if (idx === currentItem.question.correctIndex) {
                stateClass = "border-emerald-500 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-200 font-semibold";
              } else if (selectedOption === idx) {
                stateClass = "border-rose-500 bg-rose-50 dark:bg-rose-950/40 text-rose-900 dark:text-rose-200 font-semibold";
              }
            }

            return (
              <button
                key={idx}
                type="button"
                onClick={() => handleSelectOption(idx)}
                disabled={isSubmitted}
                className={`w-full text-left p-3.5 rounded-xl border text-xs sm:text-sm transition-all flex items-center justify-between cursor-pointer ${stateClass}`}
              >
                <span>{opt}</span>
                {isSubmitted && idx === currentItem.question.correctIndex && (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                )}
                {isSubmitted && selectedOption === idx && idx !== currentItem.question.correctIndex && (
                  <XCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                )}
              </button>
            );
          })}
        </div>

        {/* Explanation & Textbook Evidence Citation */}
        {isSubmitted && (
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-800 space-y-2 text-xs">
            <div className="font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
              {lang === "bn" ? "পাঠ্যবইয়ের প্রমাণ ও ব্যাখ্যা" : "Textbook Evidence & Explanation"}
            </div>
            <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
              {currentItem.question.explanation_bn}
            </p>
            <div className="text-[11px] text-indigo-600 dark:text-indigo-400 font-bold flex items-center gap-1">
              📖 এনসিটিবি পাঠ্যবই পৃষ্ঠা নং {lang === "bn" ? toBengaliDigits(currentItem.question.textbook_page) : currentItem.question.textbook_page}
            </div>
          </div>
        )}

        {/* Action Button */}
        <div className="pt-2 flex justify-end">
          {!isSubmitted ? (
            <button
              onClick={handleSubmitAnswer}
              disabled={selectedOption === null}
              className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white text-xs font-semibold rounded-xl shadow-sm transition-all cursor-pointer"
            >
              {lang === "bn" ? "উত্তর যাচাই করো" : "Submit Answer"}
            </button>
          ) : (
            <button
              onClick={handleNext}
              className="flex items-center gap-1.5 px-5 py-2.5 bg-slate-900 hover:bg-slate-800 dark:bg-white dark:hover:bg-slate-100 text-white dark:text-slate-900 text-xs font-semibold rounded-xl shadow-sm transition-all cursor-pointer"
            >
              {currentIndex + 1 < items.length ? (
                <>
                  {lang === "bn" ? "পরবর্তী প্রশ্ন" : "Next Question"}
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              ) : (
                <>
                  {lang === "bn" ? "ফলাফল ও লাইটনার পরিবর্তন দেখুন" : "View Results & Box Movements"}
                  <Award className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
