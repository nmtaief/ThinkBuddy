"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { AdminAITutorView } from "@/components/admin/AdminAITutorView";

export default function AdminPage() {
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
