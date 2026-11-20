"use client";

import React, { useState } from "react";
import { MathRenderer } from "@/components/MathRenderer";
import { Send, RotateCcw, AlertCircle, BookOpen, Bot, User } from "lucide-react";

export default function MobileAuditPage() {
  const [activeScenario, setActiveScenario] = useState<string>("scenario1");

  // Scenarios representing the 6 audit requirements
  const scenarios: Record<string, { title: string; userQuery: string; assistantReply: string; citation?: string; isError?: boolean }> = {
    scenario1: {
      title: "1. Bold Text Formatting (No Raw **)",
      userQuery: "Class 8 math boi er chapter 1 er 3 no kore deo",
      assistantReply: `আপনার ক্লাস ৮ গণিত বইয়ের **অধ্যায় ১: প্যাটার্ন** (পৃষ্ঠা ১-১২) এর বিষয়বস্তু আমি বই থেকে যাচাই করেছি।

এই অধ্যায়ে মূলত **প্যাটার্ন ও বীজগাণিতিক রাশি** নিয়ে আলোচনা করা হয়েছে। ৩ নম্বর প্রশ্নের সমাধান নিচে দেওয়া হলো।`,
      citation: "গণিত (অষ্টম শ্রেণি) • প্যাটার্ন • পৃষ্ঠা নং ৩",
    },
    scenario2: {
      title: "2. Clean Lists with Line Breaks (Not Collapsed)",
      userQuery: "Ssc books?",
      assistantReply: `ThinkBuddy অ্যাপে বর্তমানে উপলব্ধ এসএসসি (৯ম-১০ম শ্রেণি) বইসমূহ:

- **গণিত** (আবশ্যিক সাধারণ গণিত)
- **পদার্থবিজ্ঞান** (বিজ্ঞান বিভাগ)
- **রসায়ন** (বিজ্ঞান বিভাগ)
- **জীববিজ্ঞান** (বিজ্ঞান বিভাগ)
- **উচ্চতর গণিত** (ঐচ্ছিক গণিত)
- **বাংলাদেশ ও বিশ্বপরিচয়**

১. প্রথম পত্রের সকল অধ্যায় সংযুক্ত আছে।
২. প্রতিটি অধ্যায়ের অনুশীলনী আলাদাভাবে যুক্ত আছে।`,
      citation: "কারিকুলাম ক্যাটালগ • এসএসসি (৯ম-১০ম শ্রেণি)",
    },
    scenario3: {
      title: "3. KaTeX Equations (Inline & Block)",
      userQuery: "ত্রিকোণমিতির সূত্র ও সমীকরণ দেখাও",
      assistantReply: `ত্রিকোণমিতির মৌলিক সূত্রাবলী নিচে দেওয়া হলো:

ইনলাইন সমীকরণ: $\\sin^2\\theta + \\cos^2\\theta = 1$ এবং $\\tan\\theta = \\frac{\\sin\\theta}{\\cos\\theta}$

ব্লক সমীকরণ:
$$\\sec^2\\theta - \\tan^2\\theta = 1$$

$$\\text{সমকোণী ত্রিভুজের ক্ষেত্রে: } c^2 = a^2 + b^2$$`,
      citation: "গণিত (নবম-দশম শ্রেণি) • অধ্যায় ৯ • পৃষ্ঠা নং ১৭৮",
    },
    scenario4: {
      title: "4. Long Conversation Auto-Scroll",
      userQuery: "বীজগাণিতিক রাশির আরও কিছু উদাহরণ দাও",
      assistantReply: `বীজগণিতের কয়েকটি গুরুত্বপূর্ণ অভেদাবলি:

1. $(a + b)^2 = a^2 + 2ab + b^2$
2. $(a - b)^2 = a^2 - 2ab + b^2$
3. $a^2 - b^2 = (a + b)(a - b)$
4. $(x + a)(x + b) = x^2 + (a + b)x + ab$
5. $a^3 + b^3 = (a + b)(a^2 - ab + b^2)$

এই সূত্রগুলো অনুশীলনীর অংক করার সময় সরাসরি প্রয়োগ করা যাবে।`,
      citation: "গণিত (অষ্টম শ্রেণি) • অধ্যায় ৪ • পৃষ্ঠা নং ৫৪",
    },
    scenario5: {
      title: "5. Retry / Try Again (Clean Retry)",
      userQuery: "Try again",
      assistantReply: `আপনার আগের প্রশ্নটি আবার প্রসেস করা হচ্ছে: **SSC trigonometry 9.1 er 5 no.**

ত্রিকোণমিতিক অনুপাত ৯.১ এর ৫ নম্বর প্রশ্ন:
**প্রমাণ করো যে:** $\\frac{1}{1 + \\sin^2\\theta} + \\frac{1}{1 + \\csc^2\\theta} = 1$

**বামপক্ষ:**
$$\\frac{1}{1 + \\sin^2\\theta} + \\frac{1}{1 + \\frac{1}{\\sin^2\\theta}} = \\frac{1}{1 + \\sin^2\\theta} + \\frac{\\sin^2\\theta}{\\sin^2\\theta + 1} = \\frac{1 + \\sin^2\\theta}{1 + \\sin^2\\theta} = 1$$
সুতরাং বামপক্ষ = ডানপক্ষ (প্রমাণিত)।`,
      citation: "গণিত (নবম-দশম শ্রেণি) • অধ্যায় ৯.১ • পৃষ্ঠা নং ১৮৪",
    },
    scenario6: {
      title: "6. Student-Friendly Error (No Admin Leak)",
      userQuery: "আইসিটি অধ্যায় ৫ এর প্রশ্ন বলো",
      assistantReply: "একটু সমস্যা হয়েছে, আবার চেষ্টা করো।",
      isError: true,
    },
    scenario7: {
      title: "7. Markdown Table Formatting",
      userQuery: "পদার্থের ভৌত রাশি ও এককের ছকটি দেখাও",
      assistantReply: `পদার্থবিজ্ঞানের মৌলিক রাশি ও এসআই এককের তালিকা নিচে ছক আকারে দেওয়া হলো:

| মৌলিক রাশি | প্রতীক | এসআই একক | প্রতীক |
| --- | --- | --- | --- |
| দৈর্ঘ্য (Length) | $l$ | মিটার (meter) | m |
| ভর (Mass) | $m$ | কিলোগ্রাম (kilogram) | kg |
| সময় (Time) | $t$ | সেকেন্ড (second) | s |
| তাপমাত্রা (Temperature) | $T$ | কেলভিন (kelvin) | K |
| তড়িৎ প্রবাহ (Current) | $I$ | অ্যাম্পিয়ার (ampere) | A |

উপরের ছকের এককগুলো সমীকরণে সরাসরি ব্যবহৃত হয়।`,
      citation: "পদার্থবিজ্ঞান (নবম-দশম শ্রেণি) • অধ্যায় ১ • পৃষ্ঠা নং ১৮",
    },
  };

  const curr = scenarios[activeScenario] || scenarios.scenario1;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between max-w-[390px] mx-auto border-x border-slate-200">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-4 py-3 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold text-sm">
            TB
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-800">সহায়ক এআই (Buddy)</h1>
            <p className="text-xs text-emerald-600 font-medium">● অনলাইন • পাঠ্যবই ভিত্তিক</p>
          </div>
        </div>
        <select
          value={activeScenario}
          onChange={(e) => setActiveScenario(e.target.value)}
          className="text-xs border border-slate-300 rounded px-1.5 py-1 bg-white text-slate-700"
        >
          <option value="scenario1">1. Bold</option>
          <option value="scenario2">2. Lists</option>
          <option value="scenario3">3. KaTeX</option>
          <option value="scenario4">4. Scroll</option>
          <option value="scenario5">5. Retry</option>
          <option value="scenario6">6. Error</option>
          <option value="scenario7">7. Table</option>
        </select>
      </header>

      {/* Chat Messages Body */}
      <main className="flex-1 p-3 overflow-y-auto space-y-3">
        <div className="text-center my-1">
          <span className="text-[11px] bg-slate-200 text-slate-600 px-2 py-0.5 rounded-full font-medium">
            {curr.title}
          </span>
        </div>

        {/* User Bubble */}
        <div className="flex justify-end gap-2">
          <div className="bg-blue-600 text-white rounded-2xl rounded-tr-sm px-3.5 py-2 text-sm shadow-sm max-w-[85%]">
            {curr.userQuery}
          </div>
          <div className="w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs shrink-0 self-end">
            <User className="w-3.5 h-3.5" />
          </div>
        </div>

        {/* Assistant Bubble */}
        <div className="flex justify-start gap-2">
          <div className="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs shrink-0 self-start mt-1">
            <Bot className="w-3.5 h-3.5" />
          </div>
          <div className="bg-white border border-slate-200 text-slate-800 rounded-2xl rounded-tl-sm px-3.5 py-2.5 text-sm shadow-sm max-w-[88%] space-y-2">
            <MathRenderer content={curr.assistantReply} />

            {/* Citation Pill */}
            {curr.citation && (
              <div className="pt-2 border-t border-slate-100 flex items-center gap-1.5 text-xs text-blue-600 font-medium">
                <BookOpen className="w-3.5 h-3.5 shrink-0" />
                <span className="truncate">{curr.citation}</span>
              </div>
            )}

            {/* Error Friendly Retry Button */}
            {curr.isError && (
              <div className="pt-2 border-t border-slate-100 flex items-center gap-2">
                <button
                  type="button"
                  className="flex items-center gap-1 text-xs bg-blue-50 text-blue-600 px-2.5 py-1 rounded font-medium hover:bg-blue-100"
                >
                  <RotateCcw className="w-3 h-3" />
                  আবার চেষ্টা করুন
                </button>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Bottom Bar */}
      <footer className="bg-white border-t border-slate-200 p-2.5 flex items-center gap-2">
        <input
          type="text"
          placeholder="পাঠ্যবই থেকে যেকোনো প্রশ্ন করো..."
          className="flex-1 bg-slate-100 border border-slate-200 rounded-full px-3.5 py-2 text-xs text-slate-800 focus:outline-none"
          readOnly
        />
        <button
          type="button"
          aria-label="Send message"
          className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center shrink-0"
        >
          <Send className="w-4 h-4" />
        </button>
      </footer>
    </div>
  );
}

