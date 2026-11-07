import React, { useState } from "react";
import { Language, translations } from "@thinkbuddy/shared";
import { FileEdit, Check, Camera, Send, Sparkles } from "lucide-react";
import { MathRenderer } from "./MathRenderer";

interface BroadAnswerViewProps {
  lang: Language;
}

export const BroadAnswerView: React.FC<BroadAnswerViewProps> = ({ lang }) => {
  const [answerText, setAnswerText] = useState(
    "উদ্ভিদের পাতায় মেসোফিল কোষে অবস্থিত ক্লোরোপ্লাস্টে সূর্যালোকের উপস্থিতিতে সালোকসংশ্লেষণ সম্পন্ন হয়। প্রধান কাঁচামাল CO₂ পত্ররন্ধ্রের মাধ্যমে গৃহীত হয় এবং মূলরোম দিয়ে শোষিত পানি জাইলেম বাহিকার মাধ্যমে পাতায় পৌঁছায়।"
  );
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
    setTimeout(() => setSubmitted(false), 4000);
  };

  return (
    <div className="card" style={{ padding: "var(--space-6)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-4)" }}>
        <FileEdit size={22} style={{ color: "var(--color-primary)" }} />
        <div>
          <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
            {lang === "bn" ? "রচনামূলক ও বর্ণনামূলক উত্তর অনুশীলন" : "Descriptive Answer Practice"}
          </h2>
          <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
            {lang === "bn" ? "বড় প্রশ্নের উত্তর টাইপ করে বা খাতার ছবি তুলে যাচাই করো" : "Submit long-form answers for AI and mentor feedback"}
          </span>
        </div>
      </div>

      <div
        style={{
          padding: "var(--space-4)",
          backgroundColor: "var(--color-surface-hover)",
          borderRadius: "var(--radius-md)",
          border: "1px solid var(--color-border)",
          marginBottom: "var(--space-4)",
        }}
      >
        <div style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-primary)" }}>
          {lang === "bn" ? "অনুশীলনের প্রশ্ন (বিজ্ঞান • ৭ম শ্রেণি):" : "Question (Science Class 7):"}
        </div>
        <p style={{ fontSize: "var(--text-sm)", fontWeight: 600, marginTop: 4 }}>
          {lang === "bn"
            ? "সালোকসংশ্লেষণ প্রক্রিয়ার কাঁচামালসমূহ কীভাবে সংগৃহীত হয় এবং উদ্ভিদদেহে কীভাবে পরিবাহিত হয়? ব্যাখ্যা করো।"
            : "Explain how the raw materials for photosynthesis are absorbed and transported within plants."}
        </p>
      </div>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <textarea
          rows={6}
          value={answerText}
          onChange={(e) => setAnswerText(e.target.value)}
          placeholder={lang === "bn" ? "এখানে তোমার উত্তরটি লেখো..." : "Type your answer here..."}
          style={{
            width: "100%",
            padding: "var(--space-4)",
            borderRadius: "var(--radius-lg)",
            border: "1.5px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
            color: "var(--color-text-main)",
            fontFamily: "inherit",
            fontSize: "var(--text-sm)",
            lineHeight: 1.7,
            resize: "vertical",
          }}
        />

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-3)" }}>
          <button
            type="button"
            className="btn-secondary touch-target"
            style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-xs)" }}
          >
            <Camera size={15} />
            <span>{lang === "bn" ? "খাতার ছবি আপলোড করুন" : "Upload Hand-written Photo"}</span>
          </button>

          <button
            type="submit"
            className="btn-primary touch-target"
            style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-sm)" }}
          >
            <Send size={15} />
            <span>{lang === "bn" ? "উত্তর জমা দিন" : "Submit Answer"}</span>
          </button>
        </div>

        {submitted && (
          <div
            style={{
              padding: "var(--space-3) var(--space-4)",
              borderRadius: "var(--radius-md)",
              backgroundColor: "var(--color-success-surface)",
              color: "var(--color-success)",
              border: "1px solid var(--color-success)",
              fontSize: "var(--text-xs)",
              fontWeight: 700,
            }}
          >
            ✓ {lang === "bn" ? "উত্তর সফলভাবে জমা হয়েছে! এআই শিক্ষক পর্যালোচনা করছেন।" : "Answer submitted successfully for review!"}
          </div>
        )}
      </form>
    </div>
  );
};

