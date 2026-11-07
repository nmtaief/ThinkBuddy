import React, { useState } from "react";
import {
  UserProfile,
  Language,
  translations,
  StudentExamSettings,
  toBengaliDigits,
  calculateDaysRemaining,
} from "@thinkbuddy/shared";
import {
  X,
  User,
  GraduationCap,
  Calendar,
  Globe,
  Moon,
  Sun,
  LogOut,
  ExternalLink,
  Copy,
  Check,
  Settings,
  ChevronRight,
  ShieldCheck,
} from "lucide-react";

interface ProfileDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  user: UserProfile;
  examSettings: StudentExamSettings;
  onOpenExamSettings: () => void;
  lang: Language;
  onToggleLang: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onLogout: () => void;
}

export const ProfileDrawer: React.FC<ProfileDrawerProps> = ({
  isOpen,
  onClose,
  user,
  examSettings,
  onOpenExamSettings,
  lang,
  onToggleLang,
  theme,
  onToggleTheme,
  onLogout,
}) => {
  const t = translations[lang];
  const [copiedCode, setCopiedCode] = useState(false);
  const parentUrl = import.meta.env.VITE_PARENT_SITE_URL || "http://localhost:3001";

  if (!isOpen) return null;

  const daysLeft = calculateDaysRemaining(examSettings.exam_date);

  const handleCopyCode = () => {
    const code = user.inviteCode || "TB-8392";
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(code);
    }
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(15, 23, 42, 0.55)",
        backdropFilter: "blur(4px)",
        zIndex: 90,
        display: "flex",
        justifyContent: "flex-end",
        transition: "opacity 0.2s ease",
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 380,
          height: "100%",
          backgroundColor: "var(--color-surface)",
          display: "flex",
          flexDirection: "column",
          boxShadow: "-8px 0 24px rgba(0, 0, 0, 0.15)",
          overflowY: "auto",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drawer Header */}
        <div
          style={{
            padding: "var(--space-4) var(--space-5)",
            borderBottom: "1px solid var(--color-border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            position: "sticky",
            top: 0,
            backgroundColor: "var(--color-surface)",
            zIndex: 10,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <User size={18} style={{ color: "var(--color-primary)" }} />
            <span style={{ fontSize: "var(--text-sm)", fontWeight: 800, color: "var(--color-text-main)" }}>
              {t.menu.profileTitle}
            </span>
          </div>
          <button
            onClick={onClose}
            className="btn-secondary touch-target"
            style={{ padding: 6, minHeight: 34, minWidth: 34 }}
            aria-label="Close menu"
          >
            <X size={18} />
          </button>
        </div>

        {/* Drawer Body Content */}
        <div style={{ padding: "var(--space-5)", display: "flex", flexDirection: "column", gap: "var(--space-5)", flex: 1 }}>
          {/* 1. Student User Profile Card */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-3)",
              padding: "var(--space-4)",
              backgroundColor: "var(--color-surface-hover)",
              borderRadius: "var(--radius-lg)",
              border: "1px solid var(--color-border)",
            }}
          >
            {user.photoURL ? (
              <img
                src={user.photoURL}
                alt={user.name}
                style={{
                  width: 50,
                  height: 50,
                  borderRadius: "var(--radius-full)",
                  objectFit: "cover",
                  border: "2px solid var(--color-primary-border)",
                }}
              />
            ) : (
              <div
                style={{
                  width: 50,
                  height: 50,
                  borderRadius: "var(--radius-full)",
                  backgroundColor: "var(--color-primary-surface)",
                  color: "var(--color-primary)",
                  fontWeight: 800,
                  fontSize: "var(--text-lg)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  border: "2px solid var(--color-primary-border)",
                }}
              >
                {user.name.slice(0, 1)}
              </div>
            )}
            <div style={{ flex: 1, minWidth: 0 }}>
              <h3
                style={{
                  fontSize: "var(--text-sm)",
                  fontWeight: 800,
                  color: "var(--color-text-main)",
                  margin: 0,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {user.name}
              </h3>
              <p
                style={{
                  fontSize: "var(--text-xs)",
                  color: "var(--color-text-muted)",
                  margin: "2px 0 0 0",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {user.email}
              </p>
            </div>
          </div>

          {/* 2. Current Class & Exam Target Section */}
          <div
            style={{
              padding: "var(--space-4)",
              borderRadius: "var(--radius-lg)",
              backgroundColor: "var(--color-surface-subtle)",
              border: "1px solid var(--color-border)",
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-3)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-primary)" }}>
                <GraduationCap size={16} />
                <span>{lang === "bn" ? "শ্রেণি ও পাঠ্যক্রম" : "Class & Curriculum"}</span>
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
              <div style={{ fontSize: "var(--text-sm)", fontWeight: 800, color: "var(--color-text-main)" }}>
                {lang === "bn" ? examSettings.classNameBn : `Class ${examSettings.class_grade}`}
              </div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)" }}>
                {examSettings.syllabus}
              </div>
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px 12px",
                borderRadius: "var(--radius-md)",
                backgroundColor: "var(--color-surface)",
                border: "1px dashed var(--color-border)",
              }}
            >
              <div>
                <div style={{ fontSize: "11px", color: "var(--color-text-muted)", fontWeight: 600 }}>
                  {examSettings.exam_title}
                </div>
                <div style={{ fontSize: "var(--text-xs)", fontWeight: 800, color: "var(--color-primary)" }}>
                  {daysLeft > 0
                    ? lang === "bn"
                      ? `${toBengaliDigits(daysLeft)} দিন বাকি`
                      : `${daysLeft} days left`
                    : daysLeft === 0
                    ? lang === "bn" ? "আজই পরীক্ষা!" : "Today is exam!"
                    : lang === "bn" ? "পরীক্ষা সম্পন্ন" : "Exam ended"}
                </div>
              </div>
            </div>

            {/* Change Target Trigger */}
            <button
              onClick={() => {
                onClose();
                onOpenExamSettings();
              }}
              className="btn-secondary touch-target"
              style={{
                width: "100%",
                fontSize: "var(--text-xs)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 6,
                padding: "8px 12px",
                borderRadius: "var(--radius-md)",
              }}
            >
              <Settings size={14} />
              <span>{t.examSettings.title}</span>
            </button>
          </div>

          {/* 3. Hidden Menu Link: Parent Portal ("অভিভাবক সাইট") */}
          <div
            style={{
              padding: "var(--space-4)",
              borderRadius: "var(--radius-lg)",
              backgroundColor: "rgba(16, 185, 129, 0.05)",
              border: "1.5px solid rgba(16, 185, 129, 0.25)",
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-3)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <ShieldCheck size={18} style={{ color: "var(--color-success)" }} />
              <span style={{ fontSize: "var(--text-xs)", fontWeight: 800, color: "var(--color-success)" }}>
                {t.menu.parentPortalTitle}
              </span>
            </div>
            <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", margin: 0, lineHeight: 1.5 }}>
              {t.menu.parentPortalDesc}
            </p>
            <a
              href={parentUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="touch-target"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 6,
                padding: "10px 14px",
                borderRadius: "var(--radius-md)",
                backgroundColor: "var(--color-success)",
                color: "#FFFFFF",
                fontSize: "var(--text-xs)",
                fontWeight: 700,
                textDecoration: "none",
                transition: "background-color 0.15s ease",
              }}
            >
              <span>{t.menu.openParentPortal}</span>
              <ExternalLink size={14} />
            </a>
          </div>

          {/* 4. Quick Controls: Language & Theme Switches */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-2)",
              padding: "var(--space-3)",
              borderRadius: "var(--radius-lg)",
              backgroundColor: "var(--color-surface-hover)",
              border: "1px solid var(--color-border)",
            }}
          >
            {/* Language Switch */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "4px 8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-xs)", fontWeight: 600 }}>
                <Globe size={15} style={{ color: "var(--color-text-muted)" }} />
                <span>{t.menu.language}</span>
              </div>
              <button
                onClick={onToggleLang}
                className="btn-secondary touch-target"
                style={{ padding: "4px 12px", minHeight: 32, fontSize: "var(--text-xs)", fontWeight: 700 }}
              >
                {lang === "bn" ? "English" : "বাংলা"}
              </button>
            </div>

            {/* Theme Switch */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "4px 8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-xs)", fontWeight: 600 }}>
                {theme === "light" ? <Moon size={15} style={{ color: "var(--color-text-muted)" }} /> : <Sun size={15} style={{ color: "var(--color-warning)" }} />}
                <span>{theme === "light" ? t.menu.darkMode : t.menu.lightMode}</span>
              </div>
              <button
                onClick={onToggleTheme}
                className="btn-secondary touch-target"
                style={{ padding: "4px 12px", minHeight: 32, fontSize: "var(--text-xs)", fontWeight: 700 }}
              >
                {theme === "light" ? "ডার্ক মোড" : "লাইট মোড"}
              </button>
            </div>
          </div>

          {/* 5. Invite Code Section */}
          <div
            style={{
              padding: "var(--space-3) var(--space-4)",
              borderRadius: "var(--radius-md)",
              backgroundColor: "var(--color-surface)",
              border: "1px dashed var(--color-primary-border)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div>
              <div style={{ fontSize: "11px", color: "var(--color-primary)", fontWeight: 700 }}>
                {t.invite.studentCardTitle}
              </div>
              <div style={{ fontSize: "var(--text-xs)", fontFamily: "monospace", fontWeight: 800 }}>
                {user.inviteCode || "TB-8392"}
              </div>
            </div>
            <button
              onClick={handleCopyCode}
              className="btn-secondary touch-target"
              style={{ padding: "4px 10px", minHeight: 32, fontSize: "11px", display: "flex", alignItems: "center", gap: 4 }}
            >
              {copiedCode ? <Check size={13} style={{ color: "var(--color-success)" }} /> : <Copy size={13} />}
              <span>{copiedCode ? t.invite.copied : t.invite.copyCode}</span>
            </button>
          </div>
        </div>

        {/* Drawer Footer: Logout */}
        <div
          style={{
            padding: "var(--space-4) var(--space-5)",
            borderTop: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
          }}
        >
          <button
            onClick={() => {
              onClose();
              onLogout();
            }}
            className="touch-target"
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              padding: "10px 16px",
              borderRadius: "var(--radius-md)",
              backgroundColor: "var(--color-error-surface)",
              color: "var(--color-error)",
              border: "1px solid rgba(239, 68, 68, 0.2)",
              fontSize: "var(--text-xs)",
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            <LogOut size={16} />
            <span>{t.app.logout}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

