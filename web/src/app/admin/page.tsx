"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, ShieldAlert, Lock, KeyRound } from "lucide-react";
import { AdminAITutorView } from "@/components/admin/AdminAITutorView";
import { apiClient } from "@/lib/api-client";

export default function AdminPage() {
  const [isAdminAuthenticated, setIsAdminAuthenticated] = useState<boolean>(false);
  const [pinInput, setPinInput] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    async function checkAuth() {
      try {
        const auth = await apiClient.getAuthStatus();
        if (auth.authenticated && auth.user?.role === "admin") {
          setIsAdminAuthenticated(true);
        } else {
          // Check local session key
          const storedPin = sessionStorage.getItem("tb_admin_auth");
          if (storedPin === "verified") {
            setIsAdminAuthenticated(true);
          }
        }
      } catch {
        // Fallback
      } finally {
        setIsLoading(false);
      }
    }
    checkAuth();
  }, []);

  const handleVerifyPin = (e: React.FormEvent) => {
    e.preventDefault();
    // Default admin pin guard against unauthorized student navigation
    const targetPin = process.env.NEXT_PUBLIC_ADMIN_PIN || "202688";
    if (pinInput.trim() === targetPin) {
      sessionStorage.setItem("tb_admin_auth", "verified");
      setIsAdminAuthenticated(true);
      setError(null);
    } else {
      setError("অননুমোদিত প্রবেশাধিকার। সঠিক অ্যাডমিন পিন প্রদান করুন।");
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-400 text-sm">
        অনুমতি যাচাই করা হচ্ছে...
      </div>
    );
  }

  if (!isAdminAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl text-center space-y-6">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-amber-500/10 text-amber-500 border border-amber-500/20 flex items-center justify-center">
            <Lock className="w-8 h-8" />
          </div>
          <div className="space-y-2">
            <h2 className="text-xl font-bold text-white flex items-center justify-center gap-2">
              <ShieldAlert className="w-5 h-5 text-amber-500" />
              অ্যাডমিন পোর্টাল এক্সেস সংরক্ষিত
            </h2>
            <p className="text-xs text-slate-400">
              এই পৃষ্ঠাটি শুধুমাত্র অনুমোদিত সিস্টেম অ্যাডমিনিস্ট্রেটরদের জন্য সংরক্ষিত। অনুগ্রহ করে আপনার সিকিউরিটি পিন দিন।
            </p>
          </div>

          <form onSubmit={handleVerifyPin} className="space-y-4">
            <div className="relative">
              <KeyRound className="w-4 h-4 absolute left-3.5 top-3.5 text-slate-500" />
              <input
                type="password"
                value={pinInput}
                onChange={(e) => setPinInput(e.target.value)}
                placeholder="অ্যাডমিন এক্সেস পিন লিখুন"
                className="w-full pl-10 pr-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-sm text-white focus:outline-none focus:border-blue-500"
                autoFocus
              />
            </div>
            {error && <p className="text-xs text-rose-400 font-medium">{error}</p>}
            <button
              type="submit"
              className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-xl transition-colors cursor-pointer"
            >
              প্রবেশ করুন (Access Panel)
            </button>
          </form>

          <div className="pt-2">
            <Link
              href="/"
              className="inline-flex items-center gap-2 text-xs text-slate-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              শিক্ষার্থী ড্যাশবোর্ডে ফিরে যান
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 pb-16">
      {/* Top Navbar */}
      <header className="sticky top-0 z-40 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 px-4 sm:px-6 py-3.5">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-2 text-xs sm:text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to ThinkBuddy
          </Link>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-600" />
            <span className="text-xs font-semibold tracking-wide uppercase text-slate-500">
              Admin Portal
            </span>
          </div>
        </div>
      </header>

      <main className="pt-6">
        <AdminAITutorView />
      </main>
    </div>
  );
}
