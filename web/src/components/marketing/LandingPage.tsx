"use client";

import React, { useState } from "react";
import {
  BookOpen,
  Brain,
  Sparkles,
  RotateCcw,
  Calendar,
  CheckCircle2,
  Users,
  Shield,
  ArrowRight,
  ChevronRight,
  Flame,
  Globe,
  Sun,
  Moon,
  Smartphone,
  Star,
  Zap,
} from "lucide-react";
import { GoogleSignIn } from "@/components/auth/GoogleSignIn";
import { SessionUser } from "@/lib/types";

interface LandingPageProps {
  lang: "bn" | "en";
  theme: "light" | "dark";
  onToggleLang: () => void;
  onToggleTheme: () => void;
  onLogin: (role: "student" | "parent", displayName: string) => Promise<void>;
  onGoogleSuccess?: (user: SessionUser) => void;
  onOpenFirebaseModal: () => void;
}

export default function LandingPage({
  lang,
  theme,
  onToggleLang,
  onToggleTheme,
  onLogin,
  onGoogleSuccess,
  onOpenFirebaseModal,
}: LandingPageProps) {
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [modalRole, setModalRole] = useState<"student" | "parent">("student");
  const [selectedDemoClass, setSelectedDemoClass] = useState<number>(8);

  const isBn = lang === "bn";

  const handleQuickDemoLogin = async (role: "student" | "parent") => {
    const name = role === "student" ? (isBn ? "তাহমিদ আলিম" : "Tahmid Alim") : (isBn ? "রফিকুল ইসলাম" : "Rafiqul Islam");
    await onLogin(role, name);
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col font-sans transition-colors">
      {/* Top Navigation */}
      <header className="sticky top-0 z-40 w-full backdrop-blur-md bg-white/80 dark:bg-slate-900/80 border-b border-slate-200/80 dark:border-slate-800">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-md shadow-indigo-500/20">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <span className="font-extrabold text-lg tracking-tight bg-gradient-to-r from-indigo-600 to-blue-600 bg-clip-text text-transparent">
                ThinkBuddy
              </span>
              <span className="hidden sm:inline-block ml-2 text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                NCTB AI
              </span>
            </div>
          </div>

          {/* Right Navigation Actions */}
          <div className="flex items-center gap-2 sm:gap-3">
            <button
              onClick={onToggleLang}
              className="px-2.5 py-1.5 text-xs font-medium rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors flex items-center gap-1.5"
              aria-label="Toggle language"
            >
              <Globe className="w-3.5 h-3.5" />
              <span>{isBn ? "English" : "বাংলা"}</span>
            </button>

            <button
              onClick={onToggleTheme}
              className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
              aria-label="Toggle theme"
            >
              {theme === "light" ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
            </button>

            <button
              onClick={() => setShowAuthModal(true)}
              className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm transition-all"
            >
              {isBn ? "প্রবেশ করো" : "Sign In"}
            </button>
          </div>
        </div>
      </header>

      {/* Main Hero Section */}
      <section className="relative overflow-hidden pt-12 pb-20 px-4 sm:px-6">
        <div className="max-w-5xl mx-auto text-center space-y-6">
          {/* Trust Badge */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-100 dark:border-indigo-900 text-indigo-700 dark:text-indigo-300 text-xs font-semibold shadow-sm">
            <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
            <span>
              {isBn
                ? "🇧🇩 জাতীয় শিক্ষাক্রম (NCTB) ৬ষ্ঠ থেকে ১০ম শ্রেণির জন্য ডেডিকেটেড এআই গৃহশিক্ষক"
                : "Dedicated AI Tutor for NCTB Curriculum (Class 6 to 10)"}
            </span>
          </div>

          {/* Headline */}
          <h1 className="text-3xl sm:text-5xl font-black tracking-tight text-slate-900 dark:text-white max-w-3xl mx-auto leading-tight sm:leading-tight">
            {isBn ? (
              <>
                পড়াশোনায় আর কোনো দ্বিধা নয়, সাথে আছে{" "}
                <span className="bg-gradient-to-r from-indigo-600 via-blue-600 to-indigo-500 bg-clip-text text-transparent">
                  ThinkBuddy
                </span>
              </>
            ) : (
              <>
                Master Your Textbooks with Your Personal{" "}
                <span className="bg-gradient-to-r from-indigo-600 via-blue-600 to-indigo-500 bg-clip-text text-transparent">
                  AI Companion
                </span>
              </>
            )}
          </h1>

          {/* Subheading */}
          <p className="text-sm sm:text-base text-slate-600 dark:text-slate-300 max-w-2xl mx-auto leading-relaxed">
            {isBn
              ? "পাঠ্যবইয়ের প্রতিটি অধ্যায় ও সূত্রের উদ্ধৃতিসহ নির্ভুল উত্তর, স্বয়ংক্রিয় দুর্বলতা চিহ্নিতকরণ এবং পরীক্ষার দিন অনুযায়ী ব্যালান্সড স্পেসড রিভিশন রুটিন।"
              : "Authoritative textbook solutions with verified printed page citations, automated weakness detection, and Leitner spaced repetition study schedules."}
          </p>

          {/* Hero CTAs */}
          <div className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-3.5 max-w-md mx-auto">
            {/* Google Sign In Direct Box */}
            <div className="w-full sm:w-auto">
              <GoogleSignIn
                role="student"
                lang={lang}
                onSuccess={(user) => {
                  if (onGoogleSuccess) onGoogleSuccess(user);
                }}
                onError={(err) => console.error(err)}
              />
            </div>

            <button
              onClick={() => handleQuickDemoLogin("student")}
              className="w-full sm:w-auto px-5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 text-xs font-semibold hover:bg-slate-50 dark:hover:bg-slate-700 transition-all flex items-center justify-center gap-1.5 shadow-sm"
            >
              <span>{isBn ? "ছাত্র ডেমো অ্যাকাউন্ট" : "Try Student Demo"}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Interactive Chat / Solution Mock Preview Card */}
          <div className="pt-8 max-w-2xl mx-auto">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xl text-left space-y-4">
              {/* Question bubble */}
              <div className="flex justify-end">
                <div className="bg-indigo-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-xs font-medium max-w-xs sm:max-w-md shadow-sm">
                  {isBn
                    ? "Class 8 math boi er chapter 1 er 3 no kore deo"
                    : "Solve question 3 from chapter 1 of Class 8 Math book"}
                </div>
              </div>

              {/* Buddy response bubble */}
              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-lg bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300 flex items-center justify-center flex-shrink-0 text-xs font-bold">
                  🤖
                </div>
                <div className="bg-slate-50 dark:bg-slate-800/80 border border-slate-100 dark:border-slate-800 rounded-2xl rounded-tl-sm p-4 text-xs space-y-2.5 max-w-md">
                  <div className="font-semibold text-slate-800 dark:text-slate-200">
                    {isBn ? "পদ্ধতি: সংজ্ঞা ও মান যাচাই" : "Method: Definition & Step-by-Step Verification"}
                  </div>
                  <div className="text-slate-600 dark:text-slate-300 font-mono text-[11px] space-y-1">
                    <div>১. ১ + ৩ + ৫ = ৯</div>
                    <div>২. ৯ = ৩² (পূর্ণবর্গ), ৯ বিজোড় সংখ্যা, কিন্তু ৯ যৌগিক</div>
                    <div>৩. সঠিক: i ও ii (ক)</div>
                  </div>
                  <div className="pt-1.5 border-t border-slate-200/60 dark:border-slate-700/60 flex items-center justify-between text-[10px] text-indigo-600 dark:text-indigo-400 font-medium">
                    <span>📖 গণিত (৮ম শ্রেণি) • অনুশীলনী ১ (প্রশ্ন ৩) • পৃষ্ঠা নং ৯</span>
                    <span className="bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 px-1.5 py-0.5 rounded font-bold">
                      যাচাইকৃত সমাধান
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 6 Core Features Grid */}
      <section className="py-16 bg-white dark:bg-slate-900/60 border-y border-slate-200/80 dark:border-slate-800/80 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto space-y-10">
          <div className="text-center space-y-2">
            <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white">
              {isBn ? "শিক্ষার্থীদের সফলতার জন্য পূর্ণাঙ্গ প্ল্যাটফর্ম" : "Everything You Need for Academic Excellence"}
            </h2>
            <p className="text-xs sm:text-sm text-slate-500 max-w-lg mx-auto">
              {isBn
                ? "বাডি এআই সহায়ক থেকে শুরু করে স্পেসড রিভিশন—সবকিছু এনসিটিবি কারিকুলাম অনুযায়ী সাজানো"
                : "Engineered specifically for Bangladeshi schools, aligning with national textbook curricula"}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Feature 1 */}
            <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/20 hover:border-indigo-400 transition-all space-y-3">
              <div className="w-10 h-10 rounded-xl bg-blue-100 text-blue-600 dark:bg-blue-950 dark:text-blue-400 flex items-center justify-center">
                <Brain className="w-5 h-5" />
              </div>
              <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                {isBn ? "AI পাঠ্যবই সহায়ক (Buddy)" : "Buddy AI Textbook Tutor"}
              </h3>
              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                {isBn
                  ? "যে কোনো প্রশ্নের নির্ভুল সমাধান এবং পাঠ্যবইয়ের মূল পৃষ্ঠা ও অধ্যায় উদ্ধৃতি। কোনো ভুল তথ্য দেয় না।"
                  : "Authoritative explanations with printed page and chapter citations. Guaranteed zero hallucinations."}
              </p>
            </div>

            {/* Feature 2 */}
            <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/20 hover:border-indigo-400 transition-all space-y-3">
              <div className="w-10 h-10 rounded-xl bg-rose-100 text-rose-600 dark:bg-rose-950 dark:text-rose-400 flex items-center justify-center">
                <Zap className="w-5 h-5" />
              </div>
              <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                {isBn ? "স্বয়ংক্রিয় দুর্বলতা চিহ্নিতকরণ" : "Automated Weakness Detection"}
              </h3>
              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                {isBn
                  ? "কুইজ, অনুশীলন ও এআই প্রশ্নে যেসব জায়গায় ঘাটতি দেখা যায়, তা চিহ্নিত করে বিশেষ রিভিশন বরাদ্দ করে।"
                  : "Continuous telemetry pinpoints struggles across chapters and schedules focused booster sessions."}
              </p>
            </div>

            {/* Feature 3 */}
            <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/20 hover:border-indigo-400 transition-all space-y-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-100 text-indigo-600 dark:bg-indigo-950 dark:text-indigo-400 flex items-center justify-center">
                <RotateCcw className="w-5 h-5" />
              </div>
              <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                {isBn ? "স্পেসড রিপিটেশন রিভিশন" : "Leitner Spaced Repetition"}
              </h3>
              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                {isBn
                  ? "ভুলে যাওয়া রোধ করতে বৈজ্ঞানিক ৫-বক্স পদ্ধতিতে ১, ৩, ৭ ও ১৪ দিনের বিরতিতে প্রশ্ন পুনরাবৃত্তি।"
                  : "Scientifically proven 5-box memory scheduling that prevents the forgetting curve before exams."}
              </p>
            </div>

            {/* Feature 4 */}
            <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/20 hover:border-indigo-400 transition-all space-y-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400 flex items-center justify-center">
                <Calendar className="w-5 h-5" />
              </div>
              <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                {isBn ? "ব্যক্তিগত পরীক্ষার রুটিন" : "Personalized Exam Planner"}
              </h3>
              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                {isBn
                  ? "পরীক্ষার বাকি দিন ও দৈনিক পড়ার সময় অনুযায়ী কঠিন ও দুর্বল বিষয়ে অতিরিক্ত সময় বণ্টন।"
                  : "Mathematically balanced daily minutes ensuring full syllabus coverage and revision buffers."}
              </p>
            </div>

            {/* Feature 5 */}
            <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/20 hover:border-indigo-400 transition-all space-y-3">
              <div className="w-10 h-10 rounded-xl bg-amber-100 text-amber-600 dark:bg-amber-950 dark:text-amber-400 flex items-center justify-center">
                <Flame className="w-5 h-5" />
              </div>
              <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                {isBn ? "ধারাবাহিকতা ও স্ট্রিক" : "Habit Formation & Streaks"}
              </h3>
              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                {isBn
                  ? "প্রতিদিন পড়ার অভ্যাস গড়ে তুলতে স্ট্রিক ট্র্যাকিং এবং পয়েন্ট ও ব্যাজ অর্জনের আনন্দ।"
                  : "Daily streaks and milestone celebrations keep students motivated to study consistently."}
              </p>
            </div>

            {/* Feature 6 */}
            <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/20 hover:border-indigo-400 transition-all space-y-3">
              <div className="w-10 h-10 rounded-xl bg-purple-100 text-purple-600 dark:bg-purple-950 dark:text-purple-400 flex items-center justify-center">
                <Users className="w-5 h-5" />
              </div>
              <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                {isBn ? "অভিভাবক ড্যাশবোর্ড" : "Parent Visibility Dashboard"}
              </h3>
              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                {isBn
                  ? "অভিভাবকরা সন্তানের পড়ালেখার সময়, দুর্বলতার অগ্রগতি এবং পরীক্ষার প্রস্তুতি সরাসরি দেখতে পারেন।"
                  : "Transparent, real-time insights for parents without intrusive surveillance."}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Curriculum Coverage Selector Section */}
      <section className="py-16 px-4 sm:px-6">
        <div className="max-w-4xl mx-auto text-center space-y-8">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
              {isBn ? "সম্পূর্ণ এনসিটিবি পাঠ্যক্রম কাভারেজ" : "Full NCTB Subject Coverage"}
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              {isBn ? "শ্রেণি বেছে নিয়ে পাঠ্যবইসমূহ দেখুন" : "Select a class to view supported subjects"}
            </p>
          </div>

          <div className="flex justify-center gap-2">
            {[6, 7, 8, 9, 10].map((c) => (
              <button
                key={c}
                onClick={() => setSelectedDemoClass(c)}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
                  selectedDemoClass === c
                    ? "bg-indigo-600 text-white shadow-md shadow-indigo-500/20"
                    : "bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100"
                }`}
              >
                {isBn ? `${c}ম শ্রেণি` : `Class ${c}`}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 text-left">
            {[
              { name: isBn ? "গণিত" : "Mathematics", icon: "📐", chapters: 11 },
              { name: isBn ? "বিজ্ঞান" : "Science", icon: "🔬", chapters: 14 },
              { name: isBn ? "বাংলা" : "Bangla", icon: "📖", chapters: 16 },
              { name: isBn ? "English" : "English", icon: "🌍", chapters: 12 },
              { name: isBn ? "বাংলাদেশ ও বিশ্বপরিচয়" : "BGS", icon: "🇧🇩", chapters: 10 },
              { name: isBn ? "তথ্য ও যোগাযোগ প্রযুক্তি" : "ICT", icon: "💻", chapters: 5 },
              { name: isBn ? "ইসলাম ও নৈতিক শিক্ষা" : "Religion", icon: "🕌", chapters: 5 },
              { name: isBn ? "হিন্দুধর্ম ও নৈতিক শিক্ষা" : "Hindu Studies", icon: "🕉️", chapters: 5 },
            ].map((sub, idx) => (
              <div
                key={idx}
                className="p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl flex items-center gap-3 shadow-sm"
              >
                <span className="text-xl">{sub.icon}</span>
                <div>
                  <div className="text-xs font-semibold text-slate-900 dark:text-white">
                    {sub.name}
                  </div>
                  <div className="text-[10px] text-slate-400">
                    {sub.chapters} {isBn ? "টি অধ্যায়" : "chapters"}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Bottom CTA Banner */}
      <section className="py-14 bg-gradient-to-r from-indigo-600 to-blue-700 text-white px-4 sm:px-6 text-center space-y-4">
        <h2 className="text-2xl sm:text-3xl font-extrabold max-w-xl mx-auto leading-tight">
          {isBn ? "আজই শুরু করো তোমার স্মার্ট পড়াশোনা" : "Start Your Smart Study Journey Today"}
        </h2>
        <p className="text-xs sm:text-sm text-indigo-100 max-w-md mx-auto">
          {isBn
            ? "কোনো ক্রেডিট কার্ডের প্রয়োজন নেই। গুগল দিয়ে এক ক্লিকে সাইন ইন করে শুরু করো।"
            : "No credit card required. Sign in with Google in one click and build your personalized plan."}
        </p>

        <div className="pt-2 flex justify-center">
          <GoogleSignIn
            role="student"
            lang={lang}
            onSuccess={(user) => {
              if (onGoogleSuccess) onGoogleSuccess(user);
            }}
          />
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 bg-slate-900 text-slate-400 text-xs px-4 sm:px-6 border-t border-slate-800">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-center sm:text-left">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-indigo-400" />
            <span className="font-bold text-white">ThinkBuddy Arc</span>
            <span>• {isBn ? "জাতীয় শিক্ষাক্রম ও পাঠ্যপুস্তক বোর্ড (NCTB) সহায়ক" : "NCTB Curriculum Companion"}</span>
          </div>
          <div>
            &copy; 2026 ThinkBuddy. {isBn ? "সর্বস্বত্ব সংরক্ষিত।" : "All rights reserved."}
          </div>
        </div>
      </footer>

      {/* Auth Modal for Quick Selection */}
      {showAuthModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-sm w-full p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900 dark:text-white">
                {isBn ? "লগইন করুন" : "Sign In to ThinkBuddy"}
              </h3>
              <button
                onClick={() => setShowAuthModal(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            {/* Role Toggle */}
            <div className="grid grid-cols-2 gap-1.5 p-1 bg-slate-100 dark:bg-slate-800 rounded-xl text-xs font-semibold">
              <button
                onClick={() => setModalRole("student")}
                className={`py-2 rounded-lg transition-all ${
                  modalRole === "student"
                    ? "bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-400 shadow-sm"
                    : "text-slate-600 dark:text-slate-400"
                }`}
              >
                {isBn ? "শিক্ষার্থী (Student)" : "Student"}
              </button>
              <button
                onClick={() => setModalRole("parent")}
                className={`py-2 rounded-lg transition-all ${
                  modalRole === "parent"
                    ? "bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-400 shadow-sm"
                    : "text-slate-600 dark:text-slate-400"
                }`}
              >
                {isBn ? "অভিভাবক (Parent)" : "Parent"}
              </button>
            </div>

            {/* Google Sign In */}
            <div className="flex justify-center pt-2">
              <GoogleSignIn
                role={modalRole}
                lang={lang}
                onSuccess={(u) => {
                  setShowAuthModal(false);
                  if (onGoogleSuccess) onGoogleSuccess(u);
                }}
              />
            </div>

            <div className="relative text-center my-3">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-slate-200 dark:border-slate-800" />
              </div>
              <span className="relative bg-white dark:bg-slate-900 px-3 text-[11px] text-slate-400">
                {isBn ? "অথবা" : "or"}
              </span>
            </div>

            {/* Quick Demo Access */}
            <button
              onClick={() => {
                setShowAuthModal(false);
                handleQuickDemoLogin(modalRole);
              }}
              className="w-full py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-200 transition-colors"
            >
              {isBn
                ? `${modalRole === "student" ? "তাহমিদ আলিম (শিক্ষার্থী)" : "রফিকুল ইসলাম (অভিভাবক)"} হিসেবে ডেমো প্রবেশ`
                : `Quick Demo as ${modalRole === "student" ? "Student" : "Parent"}`}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
