import React from "react";
import { UserProfile, Language, translations } from "@thinkbuddy/shared";
import { X, User, Globe, Moon, Sun, LogOut, ExternalLink, BookOpen, ShieldCheck } from "lucide-react";

interface ParentProfileDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  user: UserProfile;
  lang: Language;
  onToggleLang: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onLogout: () => void;
}

export const ParentProfileDrawer: React.FC<ParentProfileDrawerProps> = ({
  isOpen,
  onClose,
  user,
  lang,
  onToggleLang,
  theme,
  onToggleTheme,
  onLogout,
}) => {
  const t = translations[lang];
  const studentUrl = import.meta.env.VITE_STUDENT_APP_URL || "http://localhost:3000";

  if (!isOpen) return null;

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
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 360,
          height: "100%",
          backgroundColor: "var(--color-surface)",
          display: "flex",
          flexDirection: "column",
          boxShadow: "-8px 0 24px rgba(0, 0, 0, 0.15)",
          overflowY: "auto",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
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
            <ShieldCheck size={18} style={{ color: "var(--color-success)" }} />
            <span style={{ fontSize: "var(--text-sm)", fontWeight: 800, color: "var(--color-text-main)" }}>
              {lang === "bn" ? "অভিভাবক অ্যাকাউন্ট" : "Parent Account"}
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

        {/* Content */}
        <div style={{ padding: "var(--space-5)", display: "flex", flexDirection: "column", gap: "var(--space-5)", flex: 1 }}>
          {/* Parent User Info */}
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
                  border: "2px solid rgba(16, 185, 129, 0.3)",
                }}
              />
            ) : (
              <div
                style={{
                  width: 50,
                  height: 50,
                  borderRadius: "var(--radius-full)",
                  backgroundColor: "var(--color-success-surface)",
                  color: "var(--color-success)",
                  fontWeight: 800,
                  fontSize: "var(--text-lg)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  border: "2px solid rgba(16, 185, 129, 0.3)",
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

          {/* Hidden Link to Student App */}
          <div
            style={{
              padding: "var(--space-4)",
              borderRadius: "var(--radius-lg)",
              backgroundColor: "rgba(37, 99, 235, 0.05)",
              border: "1.5px solid rgba(37, 99, 235, 0.25)",
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-3)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <BookOpen size={18} style={{ color: "var(--color-primary)" }} />
              <span style={{ fontSize: "var(--text-xs)", fontWeight: 800, color: "var(--color-primary)" }}>
                {lang === "bn" ? "শিক্ষার্থী অ্যাপ (Student App)" : "Student App"}
              </span>
            </div>
            <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", margin: 0, lineHeight: 1.5 }}>
              {lang === "bn"
                ? "শিক্ষার্থীদের জন্য প্রতিদিনের পড়া, রুটিন, স্টপওয়াচ ও কুইজ অনুশীলনের পৃথক শিক্ষার্থী অ্যাপ।"
                : "Dedicated student app for daily study routines, stopwatch sessions, and practice quizzes."}
            </p>
            <a
              href={studentUrl}
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
                backgroundColor: "var(--color-primary)",
                color: "#FFFFFF",
                fontSize: "var(--text-xs)",
                fontWeight: 700,
                textDecoration: "none",
              }}
            >
              <span>{lang === "bn" ? "শিক্ষার্থী অ্যাপে যান" : "Go to Student App"}</span>
              <ExternalLink size={14} />
            </a>
          </div>

          {/* Quick Controls: Language & Theme Switches */}
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
        </div>

        {/* Footer: Logout */}
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

