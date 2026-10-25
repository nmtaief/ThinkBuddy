"use client";

import React, { useState } from "react";
import { Language, translations, toBengaliDigits } from "@/lib/i18n";
import { apiClient } from "@/lib/api-client";
import { GitPullRequest, CheckCircle2 } from "lucide-react";

interface StudentChangeRequestViewProps {
  studentId: string;
  lang: Language;
}

export const StudentChangeRequestView: React.FC<StudentChangeRequestViewProps> = ({
  studentId,
  lang,
}) => {
  const t = translations[lang];

  const [minutes, setMinutes] = useState(45);
  const [reason, setReason] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) return;
    setLoading(true);
    try {
      await apiClient.submitChangeRequest(studentId, minutes, reason);
      setSubmitted(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card" style={{ maxWidth: 600, display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: "var(--radius-md)",
            backgroundColor: "var(--color-primary-surface)",
            color: "var(--color-primary)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <GitPullRequest size={22} />
        </div>
        <div>
          <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700 }}>পড়ার সময় পরিবর্তনের অনুরোধ</h2>
          <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
            অভিভাবকের অনুমোদনের জন্য আপনার প্রস্তাবিত রুটিন পরিবর্তন পাঠান
          </p>
        </div>
      </div>

      {submitted ? (
        <div
          style={{
            backgroundColor: "var(--color-success-surface)",
            color: "var(--color-success)",
            padding: "var(--space-4)",
            borderRadius: "var(--radius-md)",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
          }}
        >
          <CheckCircle2 size={20} />
          <span>অনুরোধটি সফলভাবে অভিভাবকের কাছে পাঠানো হয়েছে।</span>
        </div>
      ) : (
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          <div>
            <label style={{ fontSize: "var(--text-sm)", fontWeight: 600, display: "block", marginBottom: 6 }}>
              প্রস্তাবিত দৈনিক পড়ার সময় (মিনিট): {lang === "bn" ? toBengaliDigits(minutes) : minutes}
            </label>
            <input
              type="range"
              min={15}
              max={180}
              step={15}
              value={minutes}
              onChange={(e) => setMinutes(Number(e.target.value))}
              style={{ width: "100%", height: 36 }}
            />
          </div>

          <div>
            <label style={{ fontSize: "var(--text-sm)", fontWeight: 600, display: "block", marginBottom: 6 }}>
              পরিবর্তনের কারণ
            </label>
            <textarea
              required
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="উদাহরণ: আগামী সপ্তাহে স্কুলের ক্রীড়া প্রতিযোগিতা অনুশীলনের জন্য..."
              style={{
                width: "100%",
                padding: "var(--space-3)",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--color-border)",
                backgroundColor: "var(--color-surface)",
                fontSize: "var(--text-sm)",
              }}
            />
          </div>

          <button type="submit" disabled={loading} className="btn-primary touch-target">
            {loading ? "জমা হচ্ছে..." : "অনুরোধ পাঠান"}
          </button>
        </form>
      )}
    </div>
  );
};
