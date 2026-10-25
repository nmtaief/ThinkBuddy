"use client";

import React, { useState } from "react";
import { Language, translations } from "@/lib/i18n";
import { apiClient } from "@/lib/api-client";
import { Bell, Moon, Clock, Save, CheckCircle2 } from "lucide-react";

interface NotificationPreferencesViewProps {
  lang: Language;
}

export const NotificationPreferencesView: React.FC<NotificationPreferencesViewProps> = ({ lang }) => {
  const t = translations[lang];

  const [quietHoursEnabled, setQuietHoursEnabled] = useState(true);
  const [quietStart, setQuietStart] = useState("21:00");
  const [quietEnd, setQuietEnd] = useState("07:00");
  const [dailyDigest, setDailyDigest] = useState(true);
  const [studyReminders, setStudyReminders] = useState(true);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await apiClient.saveNotificationPreferences({
        quiet_hours_enabled: quietHoursEnabled,
        quiet_hours_start: quietStart,
        quiet_hours_end: quietEnd,
        daily_digest: dailyDigest,
        study_reminders: studyReminders,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      <div>
        <h2 style={{ fontSize: "var(--text-xl)", fontWeight: 700 }}>
          {t.nav.notifications || "নোটিফিকেশন ও অ্যালার্ট সেটিংস"}
        </h2>
        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>
          পড়ার সময়সূচি, অ্যালার্ট ও নীরব সময়ের (Quiet Hours) পছন্দসমূহ পরিচালনা করুন
        </p>
      </div>

      {saved && (
        <div
          style={{
            backgroundColor: "var(--color-success-surface)",
            color: "var(--color-success)",
            padding: "var(--space-3) var(--space-4)",
            borderRadius: "var(--radius-md)",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
          }}
        >
          <CheckCircle2 size={18} />
          <span>নোটিফিকেশন পছন্দসমূহ সফলভাবে সংরক্ষিত হয়েছে।</span>
        </div>
      )}

      <form onSubmit={handleSave} className="card" style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
        {/* Quiet Hours */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", borderBottom: "1px solid var(--color-border)", paddingBottom: "var(--space-4)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <Moon size={20} style={{ color: "var(--color-primary)" }} />
              <div>
                <div style={{ fontWeight: 600 }}>নীরব সময় (Quiet Hours - Asia/Dhaka)</div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                  এই সময়ের পুশ নোটিফিকেশনগুলো স্থগিত রাখা হবে এবং পরদিন সকাল ৭:০০ টায় পাঠানো হবে।
                </div>
              </div>
            </div>
            <input
              type="checkbox"
              checked={quietHoursEnabled}
              onChange={(e) => setQuietHoursEnabled(e.target.checked)}
              style={{ width: 20, height: 20 }}
            />
          </div>

          {quietHoursEnabled && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)", marginTop: "var(--space-2)" }}>
              <div>
                <label style={{ fontSize: "var(--text-xs)", fontWeight: 600, display: "block", marginBottom: 4 }}>
                  শুরু (রাত)
                </label>
                <input
                  type="time"
                  value={quietStart}
                  onChange={(e) => setQuietStart(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "var(--space-2)",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--color-border)",
                    backgroundColor: "var(--color-surface)",
                  }}
                />
              </div>
              <div>
                <label style={{ fontSize: "var(--text-xs)", fontWeight: 600, display: "block", marginBottom: 4 }}>
                  শেষ (সকাল)
                </label>
                <input
                  type="time"
                  value={quietEnd}
                  onChange={(e) => setQuietEnd(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "var(--space-2)",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--color-border)",
                    backgroundColor: "var(--color-surface)",
                  }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Daily Digest */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--color-border)", paddingBottom: "var(--space-4)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <Clock size={20} style={{ color: "var(--color-secondary)" }} />
            <div>
              <div style={{ fontWeight: 600 }}>দৈনিক অধ্যয়ন সারাংশ ডাইজেস্ট</div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                প্রতিদিন রাত ৯:০০ টায় সন্তানের সমাপ্ত টাস্ক এবং অধ্যয়ন সময়ের সংক্ষিপ্ত বিবরণী।
              </div>
            </div>
          </div>
          <input
            type="checkbox"
            checked={dailyDigest}
            onChange={(e) => setDailyDigest(e.target.checked)}
            style={{ width: 20, height: 20 }}
          />
        </div>

        {/* Study Reminders */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <Bell size={20} style={{ color: "var(--color-warning)" }} />
            <div>
              <div style={{ fontWeight: 600 }}>পড়ার সময় শুরু ও বিরতি সতর্কতা</div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                নির্ধারিত পড়ার উইন্ডো শুরুর ১০ মিনিট পূর্বে পুশ রিমাইন্ডার প্রেরণ।
              </div>
            </div>
          </div>
          <input
            type="checkbox"
            checked={studyReminders}
            onChange={(e) => setStudyReminders(e.target.checked)}
            style={{ width: 20, height: 20 }}
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="btn-primary touch-target"
          style={{ display: "inline-flex", gap: "var(--space-2)", alignSelf: "flex-end" }}
        >
          <Save size={18} />
          <span>{loading ? "সংরক্ষণ হচ্ছে..." : "পছন্দসমূহ সংরক্ষণ করুন"}</span>
        </button>
      </form>
    </div>
  );
};
