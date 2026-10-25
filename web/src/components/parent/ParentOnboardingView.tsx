"use client";

import React, { useState } from "react";
import { Language, translations } from "@/lib/i18n";
import { UserPlus, QrCode, CheckCircle2, Copy } from "lucide-react";

interface ParentOnboardingViewProps {
  lang: Language;
}

export const ParentOnboardingView: React.FC<ParentOnboardingViewProps> = ({ lang }) => {
  const t = translations[lang];

  const [familyName, setFamilyName] = useState("রহমান পরিবার");
  const [childName, setChildName] = useState("তাহমিদ আলিম");
  const [classLevel, setClassLevel] = useState(7);
  const [medium, setMedium] = useState<"bangla" | "english">("bangla");
  const [group, setGroup] = useState<"general" | "science" | "humanities" | "business">("general");

  const [generatedLinkCode, setGeneratedLinkCode] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const code = `TB-${Math.floor(1000 + Math.random() * 9000)}-C${classLevel}`;
    setGeneratedLinkCode(code);
  };

  const copyToClipboard = () => {
    if (!generatedLinkCode) return;
    navigator.clipboard.writeText(generatedLinkCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)", maxWidth: 680 }}>
      <div>
        <h2 style={{ fontSize: "var(--text-xl)", fontWeight: 700 }}>{t.parent.onboardingTitle}</h2>
        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>
          আপনার পরিবার তৈরি করুন এবং সন্তানের ডিভাইস সংযোগ করতে লিংক কোড তৈরি করুন
        </p>
      </div>

      <form onSubmit={handleSubmit} className="card" style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <div>
          <label style={{ fontSize: "var(--text-sm)", fontWeight: 600, display: "block", marginBottom: 6 }}>
            {t.parent.familyName}
          </label>
          <input
            type="text"
            required
            value={familyName}
            onChange={(e) => setFamilyName(e.target.value)}
            style={{
              width: "100%",
              padding: "var(--space-2) var(--space-3)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-surface)",
            }}
          />
        </div>

        <div>
          <label style={{ fontSize: "var(--text-sm)", fontWeight: 600, display: "block", marginBottom: 6 }}>
            {t.parent.childName}
          </label>
          <input
            type="text"
            required
            value={childName}
            onChange={(e) => setChildName(e.target.value)}
            style={{
              width: "100%",
              padding: "var(--space-2) var(--space-3)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-surface)",
            }}
          />
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
          <div>
            <label style={{ fontSize: "var(--text-sm)", fontWeight: 600, display: "block", marginBottom: 6 }}>
              {t.parent.classLevel}
            </label>
            <select
              value={classLevel}
              onChange={(e) => setClassLevel(Number(e.target.value))}
              style={{
                width: "100%",
                padding: "var(--space-2) var(--space-3)",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--color-border)",
                backgroundColor: "var(--color-surface)",
              }}
            >
              {[6, 7, 8, 9, 10, 11, 12].map((lvl) => (
                <option key={lvl} value={lvl}>
                  {lang === "bn" ? `${lvl}ম শ্রেণি` : `Class ${lvl}`}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ fontSize: "var(--text-sm)", fontWeight: 600, display: "block", marginBottom: 6 }}>
              {t.parent.medium}
            </label>
            <select
              value={medium}
              onChange={(e) => setMedium(e.target.value as "bangla" | "english")}
              style={{
                width: "100%",
                padding: "var(--space-2) var(--space-3)",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--color-border)",
                backgroundColor: "var(--color-surface)",
              }}
            >
              <option value="bangla">বাংলা মাধ্যম (Bangla)</option>
              <option value="english">ইংরেজি ভার্সন (English)</option>
            </select>
          </div>
        </div>

        {classLevel >= 9 && (
          <div>
            <label style={{ fontSize: "var(--text-sm)", fontWeight: 600, display: "block", marginBottom: 6 }}>
              {t.parent.group}
            </label>
            <select
              value={group}
              onChange={(e) => setGroup(e.target.value as any)}
              style={{
                width: "100%",
                padding: "var(--space-2) var(--space-3)",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--color-border)",
                backgroundColor: "var(--color-surface)",
              }}
            >
              <option value="science">বিজ্ঞান (Science)</option>
              <option value="humanities">মানবিক (Humanities)</option>
              <option value="business">ব্যবসায় শিক্ষা (Business Studies)</option>
            </select>
          </div>
        )}

        <button type="submit" className="btn-primary touch-target" style={{ marginTop: "var(--space-2)" }}>
          <UserPlus size={18} style={{ marginRight: 6 }} />
          <span>সন্তান প্রোফাইল তৈরি ও লিংক কোড পান</span>
        </button>
      </form>

      {/* Generated Link Code & QR Representation */}
      {generatedLinkCode && (
        <div
          className="card"
          style={{
            backgroundColor: "var(--color-primary-surface)",
            border: "2px dashed var(--color-primary)",
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-4)",
            alignItems: "center",
            textAlign: "center",
            padding: "var(--space-6)",
          }}
        >
          <div style={{ fontWeight: 700, fontSize: "var(--text-lg)", color: "var(--color-primary)" }}>
            {t.parent.linkCode}
          </div>
          <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", maxWidth: 440 }}>
            {t.parent.linkCodeDesc}
          </p>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-3)",
              backgroundColor: "var(--color-surface)",
              padding: "var(--space-3) var(--space-6)",
              borderRadius: "var(--radius-lg)",
              boxShadow: "var(--shadow-sm)",
            }}
          >
            <span
              style={{
                fontSize: "var(--text-2xl)",
                fontFamily: "var(--font-mono)",
                fontWeight: 700,
                letterSpacing: 3,
                color: "var(--color-primary)",
              }}
            >
              {generatedLinkCode}
            </span>
            <button
              type="button"
              onClick={copyToClipboard}
              className="btn-secondary touch-target"
              style={{ width: 44, height: 44, padding: 0 }}
              title="Copy Code"
            >
              {copied ? <CheckCircle2 size={18} color="var(--color-success)" /> : <Copy size={18} />}
            </button>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
            <QrCode size={18} />
            <span>{t.parent.qrCodeTitle} (ThinkBuddy QR)</span>
          </div>
        </div>
      )}
    </div>
  );
};
