import React, { useState } from "react";
import { Language, translations } from "@thinkbuddy/shared";
import { MessageSquareShare, Send, Check } from "lucide-react";

interface StudentChangeRequestViewProps {
  lang: Language;
}

export const StudentChangeRequestView: React.FC<StudentChangeRequestViewProps> = ({ lang }) => {
  const [requestType, setRequestType] = useState<"syllabus" | "holiday" | "exam_date">("holiday");
  const [reason, setReason] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) return;
    setSubmitted(true);
    setReason("");
    setTimeout(() => setSubmitted(false), 4000);
  };

  return (
    <div className="card" style={{ padding: "var(--space-6)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-4)" }}>
        <MessageSquareShare size={22} style={{ color: "var(--color-primary)" }} />
        <div>
          <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
            {lang === "bn" ? "অভিভাবকের কাছে রুটিন বা ছুটির অনুরোধ" : "Request Study Adjustment from Parent"}
          </h2>
          <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
            {lang === "bn"
              ? "অসুস্থতা, ছুটির দিন বা বিশেষ প্রয়োজনে পড়ার সময় পরিবর্তনের জন্য অভিভাবককে অবহিত করো"
              : "Notify parent for routine adjustments, sick leaves or exam date changes"}
          </span>
        </div>
      </div>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <div>
          <label style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-text-secondary)", display: "block", marginBottom: 6 }}>
            {lang === "bn" ? "অনুরোধের ধরন:" : "Request Category:"}
          </label>
          <select
            value={requestType}
            onChange={(e) => setRequestType(e.target.value as "syllabus" | "holiday" | "exam_date")}
            style={{
              padding: "10px 14px",
              borderRadius: "var(--radius-md)",
              border: "1.5px solid var(--color-border)",
              backgroundColor: "var(--color-surface)",
              color: "var(--color-text-main)",
              fontFamily: "inherit",
              fontSize: "var(--text-sm)",
              width: "100%",
            }}
          >
            <option value="holiday">{lang === "bn" ? "ছুটি বা বিশেষ দিনের ছাড়" : "Holiday / Day-off request"}</option>
            <option value="syllabus">{lang === "bn" ? "সিলেবাস বা পড়ার বিষয় পরিবর্তন" : "Syllabus or topic adjustment"}</option>
            <option value="exam_date">{lang === "bn" ? "স্কুল পরীক্ষার তারিখ হালনাগাদ" : "School Exam Date Update"}</option>
          </select>
        </div>

        <div>
          <label style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-text-secondary)", display: "block", marginBottom: 6 }}>
            {lang === "bn" ? "কারণ ও বিস্তারিত:" : "Reason & Details:"}
          </label>
          <textarea
            rows={4}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={
              lang === "bn"
                ? "যেমন: আগামী রবিবার স্কুলে বার্ষিক ক্রীড়া প্রতিযোগিতা থাকায় সন্ধ্যায় পড়তে পারব না..."
                : "e.g., Annual school sports this Sunday, requesting schedule shift..."
            }
            style={{
              width: "100%",
              padding: "var(--space-3)",
              borderRadius: "var(--radius-md)",
              border: "1.5px solid var(--color-border)",
              backgroundColor: "var(--color-surface)",
              color: "var(--color-text-main)",
              fontFamily: "inherit",
              fontSize: "var(--text-sm)",
              resize: "vertical",
            }}
          />
        </div>

        <button
          type="submit"
          disabled={!reason.trim()}
          className="btn-primary touch-target"
          style={{ alignSelf: "flex-end", display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-sm)", opacity: reason.trim() ? 1 : 0.6 }}
        >
          <Send size={15} />
          <span>{lang === "bn" ? "অভিভাবকের কাছে পাঠান" : "Send Request to Parent"}</span>
        </button>

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
            ✓ {lang === "bn" ? "অনুরোধটি সফলভাবে অভিভাবক পোর্টালে পাঠানো হয়েছে!" : "Request sent to Parent Dashboard successfully!"}
          </div>
        )}
      </form>
    </div>
  );
};

