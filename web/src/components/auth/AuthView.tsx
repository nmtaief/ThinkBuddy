"use client";

import React, { useState } from "react";
import { Language, translations } from "@/lib/i18n";
import { BookOpen, User, Users, Shield, ArrowRight, Smartphone, Sparkles, Moon, Sun, Globe } from "lucide-react";

interface AuthViewProps {
  lang: Language;
  theme: "light" | "dark";
  onToggleLang: () => void;
  onToggleTheme: () => void;
  onLogin: (role: "student" | "parent", displayName: string) => Promise<void>;
  onOpenFirebaseModal: () => void;
}

export const AuthView: React.FC<AuthViewProps> = ({
  lang,
  theme,
  onToggleLang,
  onToggleTheme,
  onLogin,
  onOpenFirebaseModal,
}) => {
  const t = translations[lang];
  const [selectedRole, setSelectedRole] = useState<"student" | "parent">("student");
  const [phone, setPhone] = useState("");
  const [studentName, setStudentName] = useState(lang === "bn" ? "তাহমিদ আলিম" : "Tahmid Alim");
  const [parentName, setParentName] = useState(lang === "bn" ? "রফিকুল ইসলাম" : "Rafiqul Islam");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const displayName = selectedRole === "student" ? studentName : parentName;
      await onLogin(selectedRole, displayName);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        backgroundColor: "var(--color-bg)",
        color: "var(--color-text)",
      }}
    >
      {/* Top Header */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "var(--space-4) var(--space-6)",
          borderBottom: "1px solid var(--color-border)",
          backgroundColor: "var(--color-surface)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: "var(--radius-lg)",
              backgroundColor: "var(--color-primary)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#ffffff",
              boxShadow: "0 4px 12px rgba(37, 99, 235, 0.2)",
            }}
          >
            <BookOpen size={22} />
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: "var(--text-xl)", letterSpacing: "-0.02em" }}>
              {t.app.title}
            </div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              {t.app.subtitle}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <button
            onClick={onToggleLang}
            className="btn-secondary touch-target"
            style={{ display: "flex", gap: "var(--space-1)", fontSize: "var(--text-sm)" }}
            aria-label={t.app.switchLanguage}
          >
            <Globe size={16} />
            <span>{lang === "bn" ? "English" : "বাংলা"}</span>
          </button>

          <button
            onClick={onToggleTheme}
            className="btn-secondary touch-target"
            style={{ width: 44, height: 44, padding: 0 }}
            aria-label={theme === "light" ? t.app.themeDark : t.app.themeLight}
          >
            {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
          </button>
        </div>
      </header>

      {/* Main Login Body */}
      <main
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "var(--space-6)",
        }}
      >
        <div
          className="card"
          style={{
            width: "100%",
            maxWidth: 480,
            padding: "var(--space-8)",
            boxShadow: "var(--shadow-lg)",
            borderRadius: "var(--radius-xl)",
            backgroundColor: "var(--color-surface)",
          }}
        >
          {/* Badge */}
          <div style={{ textAlign: "center", marginBottom: "var(--space-6)" }}>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "4px 12px",
                borderRadius: "var(--radius-full)",
                backgroundColor: "var(--color-primary-surface)",
                color: "var(--color-primary)",
                fontSize: "var(--text-xs)",
                fontWeight: 600,
                marginBottom: "var(--space-2)",
              }}
            >
              <Shield size={14} />
              {lang === "bn" ? "নিরাপদ সাইন ইন পোর্টাল" : "Secure Sign-in Portal"}
            </span>
            <h1 style={{ fontSize: "var(--text-2xl)", fontWeight: 800, marginTop: "var(--space-2)" }}>
              {lang === "bn" ? "আপনার অ্যাকাউন্টে প্রবেশ করুন" : "Sign in to your account"}
            </h1>
            <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)", marginTop: "var(--space-1)" }}>
              {lang === "bn"
                ? "শিক্ষার্থী বা অভিভাবক হিসেবে আপনার নির্ধারিত পোর্টালে লগইন করুন"
                : "Choose your role to access your dedicated student or parent portal"}
            </p>
          </div>

          {/* Role Tabs */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "var(--space-2)",
              backgroundColor: "var(--color-bg)",
              padding: "var(--space-1)",
              borderRadius: "var(--radius-lg)",
              marginBottom: "var(--space-6)",
            }}
          >
            <button
              type="button"
              id="role-tab-student"
              onClick={() => {
                setSelectedRole("student");
                onLogin("student", studentName);
              }}
              className="touch-target"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "var(--space-2)",
                padding: "var(--space-3)",
                borderRadius: "var(--radius-md)",
                border: "none",
                fontWeight: 600,
                fontSize: "var(--text-sm)",
                cursor: "pointer",
                backgroundColor: selectedRole === "student" ? "var(--color-surface)" : "transparent",
                color: selectedRole === "student" ? "var(--color-primary)" : "var(--color-text-secondary)",
                boxShadow: selectedRole === "student" ? "0 2px 8px rgba(0,0,0,0.06)" : "none",
                transition: "all 0.2s ease",
              }}
            >
              <User size={18} />
              <span>{lang === "bn" ? "শিক্ষার্থী (Student)" : "Student"}</span>
            </button>

            <button
              type="button"
              id="role-tab-parent"
              onClick={() => {
                setSelectedRole("parent");
                onLogin("parent", parentName);
              }}
              className="touch-target"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "var(--space-2)",
                padding: "var(--space-3)",
                borderRadius: "var(--radius-md)",
                border: "none",
                fontWeight: 600,
                fontSize: "var(--text-sm)",
                cursor: "pointer",
                backgroundColor: selectedRole === "parent" ? "var(--color-surface)" : "transparent",
                color: selectedRole === "parent" ? "var(--color-primary)" : "var(--color-text-secondary)",
                boxShadow: selectedRole === "parent" ? "0 2px 8px rgba(0,0,0,0.06)" : "none",
                transition: "all 0.2s ease",
              }}
            >
              <Users size={18} />
              <span>{lang === "bn" ? "অভিভাবক (Parent)" : "Parent"}</span>
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            <div>
              <label
                htmlFor="user-name-input"
                style={{
                  display: "block",
                  fontSize: "var(--text-xs)",
                  fontWeight: 600,
                  color: "var(--color-text-secondary)",
                  marginBottom: "var(--space-1)",
                }}
              >
                {selectedRole === "student"
                  ? lang === "bn"
                    ? "শিক্ষার্থীর নাম"
                    : "Student Name"
                  : lang === "bn"
                  ? "অভিভাবকের নাম"
                  : "Parent Name"}
              </label>
              <input
                id="user-name-input"
                type="text"
                required
                value={selectedRole === "student" ? studentName : parentName}
                onChange={(e) =>
                  selectedRole === "student" ? setStudentName(e.target.value) : setParentName(e.target.value)
                }
                style={{
                  width: "100%",
                  padding: "var(--space-3)",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-bg)",
                  color: "var(--color-text)",
                  fontSize: "var(--text-sm)",
                }}
              />
            </div>

            <div>
              <label
                htmlFor="user-phone-input"
                style={{
                  display: "block",
                  fontSize: "var(--text-xs)",
                  fontWeight: 600,
                  color: "var(--color-text-secondary)",
                  marginBottom: "var(--space-1)",
                }}
              >
                {lang === "bn" ? "মোবাইল নম্বর (ঐচ্ছিক)" : "Mobile Number (Optional)"}
              </label>
              <div style={{ position: "relative" }}>
                <input
                  id="user-phone-input"
                  type="tel"
                  placeholder="+88017XXXXXXXX"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "var(--space-3)",
                    paddingLeft: "36px",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--color-border)",
                    backgroundColor: "var(--color-bg)",
                    color: "var(--color-text)",
                    fontSize: "var(--text-sm)",
                  }}
                />
                <Smartphone
                  size={16}
                  style={{
                    position: "absolute",
                    left: 12,
                    top: "50%",
                    transform: "translateY(-50%)",
                    color: "var(--color-text-muted)",
                  }}
                />
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              id="btn-login-submit"
              disabled={isLoading}
              className="btn-primary touch-target"
              style={{
                width: "100%",
                padding: "var(--space-3)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "var(--space-2)",
                fontSize: "var(--text-base)",
                fontWeight: 600,
                marginTop: "var(--space-2)",
              }}
            >
              <span>
                {selectedRole === "student"
                  ? lang === "bn"
                    ? "শিক্ষার্থী পোর্টালে প্রবেশ করুন"
                    : "Enter Student Portal"
                  : lang === "bn"
                  ? "অভিভাবক ড্যাশবোর্ডে প্রবেশ করুন"
                  : "Enter Parent Dashboard"}
              </span>
              <ArrowRight size={18} />
            </button>

            {/* Or divider */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-3)",
                margin: "var(--space-2) 0",
              }}
            >
              <div style={{ flex: 1, height: 1, backgroundColor: "var(--color-border)" }} />
              <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                {lang === "bn" ? "অথবা" : "or"}
              </span>
              <div style={{ flex: 1, height: 1, backgroundColor: "var(--color-border)" }} />
            </div>

            {/* Firebase Auth Modal trigger */}
            <button
              type="button"
              id="btn-firebase-signin"
              onClick={onOpenFirebaseModal}
              className="btn-outline touch-target"
              style={{
                width: "100%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "var(--space-2)",
                fontSize: "var(--text-sm)",
              }}
            >
              <Sparkles size={16} style={{ color: "var(--color-primary)" }} />
              <span>
                {lang === "bn"
                  ? "Firebase ওটিপি / গুগল সাইন-ইন"
                  : "Firebase Phone OTP / Google Sign-In"}
              </span>
            </button>
          </form>

          {/* Security Note */}
          <div
            style={{
              marginTop: "var(--space-6)",
              padding: "var(--space-3)",
              backgroundColor: "var(--color-bg)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border)",
              fontSize: "var(--text-xs)",
              color: "var(--color-text-secondary)",
              lineHeight: 1.5,
            }}
          >
            <strong>{lang === "bn" ? "নিরাপত্তা নীতি:" : "Security Policy:"}</strong>{" "}
            {selectedRole === "student"
              ? lang === "bn"
                ? "শিক্ষার্থী পোর্টালে অভিভাবক সেটিংসের কোনো এক্সেস নেই। অভিভাবক মোড সুরক্ষিত প্রমাণীকরণের অধীনে পৃথকভাবে নিয়ন্ত্রিত।"
                : "Student portal does not contain parent settings. Parent mode requires separate authenticated login."
              : lang === "bn"
              ? "অভিভাবক পোর্টালে সময়সীমা, অধ্যয়ন পরিকল্পনা এবং সন্তানের অগ্রগতি তদারকি করা যায়।"
              : "Parent portal allows configuring study limits, syllabus plans, and viewing child progress."}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer
        style={{
          textAlign: "center",
          padding: "var(--space-4)",
          fontSize: "var(--text-xs)",
          color: "var(--color-text-muted)",
          borderTop: "1px solid var(--color-border)",
        }}
      >
        ThinkBuddy Arc &copy; 2026. {lang === "bn" ? "সর্বস্বত্ব সংরক্ষিত।" : "All rights reserved."}
      </footer>
    </div>
  );
};
