"use client";

import React, { useState, useEffect } from "react";
import { AISuggestion, AutoAdjustment, StudentChangeRequest } from "@/lib/types";
import { Language, translations } from "@/lib/i18n";
import { apiClient } from "@/lib/api-client";
import { Sparkles, CheckCircle2, XCircle, RotateCcw, GitPullRequest } from "lucide-react";

interface ParentSuggestionsViewProps {
  studentId: string;
  lang: Language;
}

export const ParentSuggestionsView: React.FC<ParentSuggestionsViewProps> = ({ studentId, lang }) => {
  const t = translations[lang];

  const [suggestions, setSuggestions] = useState<AISuggestion[]>([]);
  const [adjustments, setAdjustments] = useState<AutoAdjustment[]>([]);
  const [changeRequests, setChangeRequests] = useState<StudentChangeRequest[]>([]);
  const [notice, setNotice] = useState<string | null>(null);

  const loadData = async () => {
    const [sugs, adjs, reqs] = await Promise.all([
      apiClient.getAISuggestions(studentId),
      apiClient.getAutoAdjustments(studentId),
      apiClient.getChangeRequests(studentId),
    ]);
    setSuggestions(sugs);
    setAdjustments(adjs);
    setChangeRequests(reqs);
  };

  useEffect(() => {
    loadData();
  }, [studentId]);

  const handleApproveSuggestion = async (id: string) => {
    await apiClient.approveAISuggestion(id);
    setSuggestions((prev) => prev.filter((s) => s.id !== id));
    setNotice("এআই পরামর্শ অনুমোদিত হয়েছে এবং ভবিষ্যৎ রুটিন আপডেট করা হয়েছে।");
  };

  const handleDeclineSuggestion = async (id: string) => {
    await apiClient.declineAISuggestion(id);
    setSuggestions((prev) => prev.filter((s) => s.id !== id));
    setNotice("এআই পরামর্শ বাতিল করা হয়েছে।");
  };

  const handleUndoAdjustment = async (id: string) => {
    await apiClient.undoAutoAdjustment(id);
    setAdjustments((prev) => prev.filter((a) => a.id !== id));
    setNotice(t.parent.undoSuccess);
  };

  const handleApproveRequest = async (id: string) => {
    await apiClient.approveChangeRequest(id);
    setChangeRequests((prev) => prev.filter((r) => r.id !== id));
    setNotice("শিক্ষার্থীর অনুরোধ অনুমোদিত হয়েছে।");
  };

  const handleDeclineRequest = async (id: string) => {
    await apiClient.declineChangeRequest(id);
    setChangeRequests((prev) => prev.filter((r) => r.id !== id));
    setNotice("শিক্ষার্থীর অনুরোধ প্রত্যাখ্যাত হয়েছে।");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      {notice && (
        <div
          style={{
            backgroundColor: "var(--color-success-surface)",
            color: "var(--color-success)",
            padding: "var(--space-3) var(--space-4)",
            borderRadius: "var(--radius-md)",
            fontSize: "var(--text-sm)",
          }}
        >
          {notice}
        </div>
      )}

      {/* AI Suggestions Section */}
      <div className="card" style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
          <Sparkles size={22} style={{ color: "var(--color-primary)" }} />
          <h3 style={{ fontSize: "var(--text-lg)", fontWeight: 700 }}>{t.nav.suggestions}</h3>
        </div>

        {suggestions.length === 0 ? (
          <p style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>
            বর্তমানে কোনো বিচারাধীন এআই পরামর্শ নেই।
          </p>
        ) : (
          suggestions.map((sug) => (
            <div
              key={sug.id}
              style={{
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-md)",
                padding: "var(--space-4)",
                display: "flex",
                flexDirection: "column",
                gap: "var(--space-2)",
              }}
            >
              <div style={{ fontWeight: 600 }}>{sug.title}</div>
              <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
                {sug.reason}
              </p>
              <div style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-2)" }}>
                <button
                  onClick={() => handleApproveSuggestion(sug.id)}
                  className="btn-primary touch-target"
                  style={{ fontSize: "var(--text-xs)", padding: "var(--space-2) var(--space-3)" }}
                >
                  <CheckCircle2 size={14} style={{ marginRight: 4 }} />
                  {t.parent.approve}
                </button>
                <button
                  onClick={() => handleDeclineSuggestion(sug.id)}
                  className="btn-secondary touch-target"
                  style={{ fontSize: "var(--text-xs)", padding: "var(--space-2) var(--space-3)" }}
                >
                  <XCircle size={14} style={{ marginRight: 4 }} />
                  {t.parent.decline}
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Auto Adjustments with One-Tap Undo */}
      <div className="card" style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
          <CheckCircle2 size={22} style={{ color: "var(--color-secondary)" }} />
          <h3 style={{ fontSize: "var(--text-lg)", fontWeight: 700 }}>{t.nav.autoAdjustments}</h3>
        </div>

        {adjustments.length === 0 ? (
          <p style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>
            কোনো স্বয়ংক্রিয় সমন্বয় ইতিহাস পাওয়া যায়নি।
          </p>
        ) : (
          adjustments.map((adj) => (
            <div
              key={adj.id}
              style={{
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-md)",
                padding: "var(--space-4)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <div style={{ fontWeight: 600 }}>{adj.title}</div>
                <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
                  {adj.reason}
                </p>
              </div>
              {adj.can_undo && (
                <button
                  onClick={() => handleUndoAdjustment(adj.id)}
                  className="btn-secondary touch-target"
                  style={{ color: "var(--color-warning)", fontSize: "var(--text-xs)" }}
                >
                  <RotateCcw size={14} style={{ marginRight: 4 }} />
                  {t.parent.undo}
                </button>
              )}
            </div>
          ))
        )}
      </div>

      {/* Student Change Requests Section */}
      <div className="card" style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
          <GitPullRequest size={22} style={{ color: "var(--color-primary)" }} />
          <h3 style={{ fontSize: "var(--text-lg)", fontWeight: 700 }}>শিক্ষার্থীর পরিবর্তনের অনুরোধ</h3>
        </div>

        {changeRequests.length === 0 ? (
          <p style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>
            বর্তমানে কোনো শিক্ষার্থী অনুরোধ বিচারাধীন নেই।
          </p>
        ) : (
          changeRequests.map((req) => (
            <div
              key={req.id}
              style={{
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-md)",
                padding: "var(--space-4)",
                display: "flex",
                flexDirection: "column",
                gap: "var(--space-2)",
              }}
            >
              <div style={{ fontWeight: 600 }}>
                প্রস্তাবিত দৈনিক সময়: {req.requested_school_day_minutes} মিনিট
              </div>
              <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
                {req.reason}
              </p>
              <div style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-2)" }}>
                <button
                  onClick={() => handleApproveRequest(req.id)}
                  className="btn-primary touch-target"
                  style={{ fontSize: "var(--text-xs)" }}
                >
                  {t.parent.approve}
                </button>
                <button
                  onClick={() => handleDeclineRequest(req.id)}
                  className="btn-secondary touch-target"
                  style={{ fontSize: "var(--text-xs)" }}
                >
                  {t.parent.decline}
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
