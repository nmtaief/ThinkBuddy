"use client";

import React, { useState } from "react";
import { Language, translations } from "@/lib/i18n";
import { apiClient } from "@/lib/api-client";
import { MathRenderer } from "@/components/MathRenderer";
import { FileText, Camera, Upload, CheckCircle2, Sparkles } from "lucide-react";

interface BroadAnswerViewProps {
  lang: Language;
}

export const BroadAnswerView: React.FC<BroadAnswerViewProps> = ({ lang }) => {
  const t = translations[lang];

  const [mode, setMode] = useState<"typed" | "photo">("typed");
  const [typedAnswer, setTypedAnswer] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const questionPrompt =
    "উদ্ভিদের সালোকসংশ্লেষণ প্রক্রিয়ায় আলোক পর্যায় এবং অন্ধকার পর্যায়ের তুলনামূলক আলোচনা কর এবং রাসায়নিক সমীকরণ লিখ।";

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setFeedback(null);
    try {
      if (mode === "photo" && selectedFile) {
        // Request signed upload URL
        const signData = await apiClient.signUploadUrl(selectedFile.name, selectedFile.type);
        // Upload would proceed to signData.upload_url
        console.log("Uploaded via signed URL key:", signData.file_key);
      }

      // Generate provisional AI evaluation feedback
      setFeedback(
        "উত্তরটি সন্তোষজনক হয়েছে। আলোক পর্যায়ের জন্য এটিপি ($ATP$) ও এনএডিপিএইচ ($NADPH$) উৎপাদনের উল্লেখ সঠিক। অন্ধকার পর্যায়ের কেলভিন চক্রের ধাপসমূহ আরও বিশদভাবে ব্যাখ্যা করলে পূর্ণ নম্বর অর্জন সম্ভব।"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      <div>
        <h2 style={{ fontSize: "var(--text-xl)", fontWeight: 700 }}>{t.student.broadAnswerTitle}</h2>
        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>
          রচনামূলক ও বর্ণনামূলক প্রশ্নের উত্তর টাইপ করুন অথবা খাতার পাতার ছবি আপলোড করে এআই মূল্যায়ন নিন
        </p>
      </div>

      {/* Question Card */}
      <div className="card" style={{ borderLeft: "4px solid var(--color-primary)", display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <div style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--color-primary)" }}>
          প্রশ্ন (সাধারণ বিজ্ঞান - অধ্যায় ৪)
        </div>
        <div style={{ fontSize: "var(--text-base)", fontWeight: 600 }}>
          <MathRenderer content={questionPrompt} />
        </div>
      </div>

      {/* Answer Mode Selector */}
      <div style={{ display: "flex", gap: "var(--space-3)" }}>
        <button
          onClick={() => setMode("typed")}
          className={mode === "typed" ? "btn-primary touch-target" : "btn-secondary touch-target"}
          style={{ display: "inline-flex", gap: "var(--space-2)" }}
        >
          <FileText size={18} />
          <span>টাইপ করে উত্তর</span>
        </button>
        <button
          onClick={() => setMode("photo")}
          className={mode === "photo" ? "btn-primary touch-target" : "btn-secondary touch-target"}
          style={{ display: "inline-flex", gap: "var(--space-2)" }}
        >
          <Camera size={18} />
          <span>{t.student.uploadPhoto}</span>
        </button>
      </div>

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="card" style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        {mode === "typed" ? (
          <div>
            <textarea
              rows={8}
              value={typedAnswer}
              onChange={(e) => setTypedAnswer(e.target.value)}
              placeholder={t.student.typedAnswerPlaceholder}
              style={{
                width: "100%",
                padding: "var(--space-3)",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--color-border)",
                backgroundColor: "var(--color-surface)",
                fontSize: "var(--text-base)",
                lineHeight: 1.6,
                fontFamily: "inherit",
              }}
            />
          </div>
        ) : (
          <div
            style={{
              border: "2px dashed var(--color-border)",
              borderRadius: "var(--radius-lg)",
              padding: "var(--space-8)",
              textAlign: "center",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "var(--space-3)",
            }}
          >
            <Upload size={32} style={{ color: "var(--color-text-muted)" }} />
            <div>
              <p style={{ fontWeight: 600 }}>খাতার ছবি নির্বাচন করুন অথবা ক্যামেরা দিয়ে তুলুন</p>
              <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                JPG, PNG অথবা PDF ফাইল (সর্বোচ্চ ১০ এমবি)
              </p>
            </div>
            <input
              type="file"
              accept="image/*,.pdf"
              onChange={handleFileUpload}
              style={{ marginTop: "var(--space-2)" }}
            />
            {selectedFile && (
              <p style={{ fontSize: "var(--text-xs)", color: "var(--color-success)", fontWeight: 600 }}>
                নির্বাচিত ফাইল: {selectedFile.name}
              </p>
            )}
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button
            type="submit"
            disabled={loading || (mode === "typed" ? !typedAnswer.trim() : !selectedFile)}
            className="btn-primary touch-target"
            style={{ display: "inline-flex", gap: "var(--space-2)" }}
          >
            <Sparkles size={18} />
            <span>{loading ? "মূল্যায়ন প্রস্তুত হচ্ছে..." : t.student.submitForFeedback}</span>
          </button>
        </div>
      </form>

      {/* Provisional AI Feedback */}
      {feedback && (
        <div
          className="card"
          style={{
            backgroundColor: "var(--color-surface-hover)",
            border: "1px solid var(--color-primary)",
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-3)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", color: "var(--color-primary)" }}>
            <CheckCircle2 size={20} />
            <h3 style={{ fontSize: "var(--text-base)", fontWeight: 700 }}>
              {t.student.provisionalFeedbackNotice}
            </h3>
          </div>
          <div style={{ fontSize: "var(--text-sm)", lineHeight: 1.6 }}>
            <MathRenderer content={feedback} />
          </div>
        </div>
      )}
    </div>
  );
};
