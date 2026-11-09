"use client";

import React, { useState } from "react";
import { Language, translations } from "@/lib/i18n";
import { SessionUser } from "@/lib/types";
import {
  BookOpen, Globe, Moon, Sun, LogOut, Menu, X,
  GraduationCap, ExternalLink, Settings, Shield,
} from "lucide-react";

interface NavbarProps {
  user: SessionUser | null;
  lang: Language;
  onToggleLang: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onLogout: () => void;
  /** URL of the parent portal site */
  parentSiteUrl?: string;
}

export const Navbar: React.FC<NavbarProps> = ({
  user,
  lang,
  onToggleLang,
  theme,
  onToggleTheme,
  onLogout,
  parentSiteUrl = "https://thinkbuddy-parents.pages.dev",
}) => {
  const t = translations[lang];
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <>
      {/* ── Top Header Bar ── */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 var(--space-4)",
          height: 56,
          backgroundColor: "var(--color-surface)",
          borderBottom: "1px solid var(--color-border)",
          position: "sticky",
          top: 0,
          zIndex: 50,
          boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
        }}
      >
        {/* Brand */}
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <div
            style={{
              width: 34, height: 34,
              borderRadius: "var(--radius-md)",
              backgroundColor: "var(--color-primary)",
              display: "flex", alignItems: "center", justifyContent: "center",
              color: "#fff",
              flexShrink: 0,
            }}
          >
            <BookOpen size={18} />
          </div>
          <span style={{ fontWeight: 800, fontSize: "var(--text-lg)", letterSpacing: "-0.02em" }}>
            ThinkBuddy
          </span>
        </div>

        {/* Right controls */}
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {/* Language — desktop only */}
          <button
            id="btn-toggle-lang"
            data-testid="btn-toggle-lang"
            onClick={onToggleLang}
            className="btn-secondary touch-target navbar-desktop-only"
            style={{ fontSize: "var(--text-xs)", gap: 4, padding: "0 10px" }}
            aria-label={t.app.switchLanguage}
          >
            <Globe size={14} />
            <span>{lang === "bn" ? "English" : "বাংলা"}</span>
          </button>

          {/* Dark mode — desktop only */}
          <button
            id="btn-toggle-theme"
            data-testid="btn-toggle-theme"
            onClick={onToggleTheme}
            className="btn-secondary touch-target navbar-desktop-only"
            style={{ width: 40, height: 40, padding: 0 }}
            aria-label={theme === "light" ? t.app.themeDark : t.app.themeLight}
          >
            {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
          </button>

          {/* Admin link — desktop */}
          <a
            href="/admin"
            className="btn-secondary touch-target navbar-desktop-only"
            style={{ fontSize: "var(--text-xs)", gap: 4, padding: "0 10px", textDecoration: "none", display: "inline-flex", alignItems: "center" }}
            title="AI Tutor & RAG Admin Panel"
          >
            <Shield size={14} />
            <span>Admin</span>
          </a>

          {/* User avatar — desktop only */}
          {user && (
            <span
              className="navbar-desktop-only"
              style={{
                fontSize: "var(--text-xs)", fontWeight: 600,
                color: "var(--color-text-secondary)", maxWidth: 120,
                whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                marginLeft: 4,
              }}
            >
              {user.name}
            </span>
          )}

          {/* Logout — desktop only */}
          {user && (
            <button
              id="btn-logout"
              data-testid="btn-logout"
              onClick={onLogout}
              className="btn-secondary touch-target navbar-desktop-only"
              style={{ width: 40, height: 40, padding: 0 }}
              aria-label={t.nav.logout}
              title={t.nav.logout}
            >
              <LogOut size={16} />
            </button>
          )}

          {/* Hamburger / Profile — mobile only */}
          <button
            onClick={() => setDrawerOpen(true)}
            className="touch-target navbar-mobile-only"
            style={{
              width: 40, height: 40, padding: 0,
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-surface-hover)",
            }}
            aria-label="মেনু খুলুন"
          >
            <Menu size={20} />
          </button>
        </div>
      </header>

      {/* ── Mobile Slide-in Drawer ── */}
      {drawerOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="মূল মেনু"
          style={{
            position: "fixed", inset: 0, zIndex: 200,
            display: "flex", justifyContent: "flex-end",
          }}
        >
          {/* Backdrop */}
          <div
            style={{
              position: "absolute", inset: 0,
              backgroundColor: "rgba(15,23,42,0.5)",
              backdropFilter: "blur(3px)",
            }}
            onClick={() => setDrawerOpen(false)}
          />

          {/* Panel */}
          <div
            style={{
              position: "relative",
              width: "min(320px, 85vw)",
              height: "100%",
              backgroundColor: "var(--color-surface)",
              display: "flex", flexDirection: "column",
              boxShadow: "-4px 0 20px rgba(0,0,0,0.15)",
              overflowY: "auto",
            }}
          >
            {/* Drawer header */}
            <div
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "var(--space-4) var(--space-5)",
                borderBottom: "1px solid var(--color-border)",
                position: "sticky", top: 0, backgroundColor: "var(--color-surface)", zIndex: 1,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div
                  style={{
                    width: 30, height: 30,
                    borderRadius: "var(--radius-md)",
                    backgroundColor: "var(--color-primary)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    color: "#fff",
                  }}
                >
                  <BookOpen size={15} />
                </div>
                <span style={{ fontWeight: 800, fontSize: "var(--text-sm)" }}>ThinkBuddy</span>
              </div>
              <button
                onClick={() => setDrawerOpen(false)}
                className="btn-secondary touch-target"
                style={{ width: 36, height: 36, padding: 0 }}
                aria-label="মেনু বন্ধ করুন"
              >
                <X size={18} />
              </button>
            </div>

            {/* Drawer body */}
            <div style={{ flex: 1, padding: "var(--space-4) var(--space-5)", display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>

              {/* User profile card */}
              {user && (
                <div
                  style={{
                    padding: "var(--space-3) var(--space-4)",
                    backgroundColor: "var(--color-surface-hover)",
                    borderRadius: "var(--radius-lg)",
                    border: "1px solid var(--color-border)",
                  }}
                >
                  <div style={{ fontSize: "var(--text-sm)", fontWeight: 700, color: "var(--color-text-primary)" }}>
                    {user.name}
                  </div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: 2 }}>
                    {t.roles[user.role]}
                  </div>
                </div>
              )}

              {/* Class & Exam settings placeholder */}
              {user?.role === "student" && (
                <div
                  style={{
                    padding: "var(--space-3) var(--space-4)",
                    backgroundColor: "var(--color-surface-subtle, var(--color-surface-hover))",
                    borderRadius: "var(--radius-lg)",
                    border: "1px solid var(--color-border)",
                    display: "flex", flexDirection: "column", gap: "var(--space-2)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-primary)" }}>
                    <GraduationCap size={15} />
                    <span>{lang === "bn" ? "শ্রেণি ও পরীক্ষা" : "Class & Exam"}</span>
                  </div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)" }}>
                    {lang === "bn" ? "শ্রেণি নির্বাচন, পাঠ্যক্রম ও পরীক্ষার তারিখ পরিবর্তন করুন।" : "Change your class, syllabus and exam date."}
                  </div>
                  <button
                    className="btn-secondary touch-target"
                    style={{ width: "100%", fontSize: "var(--text-xs)", gap: 6, padding: "8px 12px" }}
                    onClick={() => setDrawerOpen(false)}
                  >
                    <Settings size={13} />
                    <span>{lang === "bn" ? "পরীক্ষার সেটিং" : "Exam Settings"}</span>
                  </button>
                </div>
              )}

              {/* Language switch */}
              <a
                href="/admin"
                className="btn-secondary touch-target"
                style={{
                  width: "100%", fontSize: "var(--text-xs)", gap: 8, padding: "10px 14px",
                  textDecoration: "none", display: "flex", alignItems: "center",
                  backgroundColor: "var(--color-surface-hover)",
                  borderRadius: "var(--radius-md)", border: "1px solid var(--color-border)",
                  color: "var(--color-text-primary)", fontWeight: 600,
                }}
              >
                <Shield size={16} />
                <span>AI Tutor & RAG Admin Panel</span>
              </a>

              {/* Language switch */}
              <div
                style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "var(--space-2) var(--space-3)",
                  backgroundColor: "var(--color-surface-hover)",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--color-border)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-xs)", fontWeight: 600 }}>
                  <Globe size={14} style={{ color: "var(--color-text-muted)" }} />
                  <span>{lang === "bn" ? "ভাষা" : "Language"}</span>
                </div>
                <button
                  onClick={onToggleLang}
                  className="btn-secondary touch-target"
                  style={{ padding: "4px 12px", minHeight: 34, fontSize: "var(--text-xs)", fontWeight: 700 }}
                >
                  {lang === "bn" ? "English" : "বাংলা"}
                </button>
              </div>

              {/* Theme switch */}
              <div
                style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "var(--space-2) var(--space-3)",
                  backgroundColor: "var(--color-surface-hover)",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--color-border)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-xs)", fontWeight: 600 }}>
                  {theme === "light" ? <Moon size={14} style={{ color: "var(--color-text-muted)" }} /> : <Sun size={14} style={{ color: "var(--color-warning, #f59e0b)" }} />}
                  <span>{theme === "light" ? (lang === "bn" ? "ডার্ক মোড" : "Dark Mode") : (lang === "bn" ? "লাইট মোড" : "Light Mode")}</span>
                </div>
                <button
                  onClick={onToggleTheme}
                  className="btn-secondary touch-target"
                  style={{ padding: "4px 12px", minHeight: 34, fontSize: "var(--text-xs)", fontWeight: 700 }}
                >
                  {theme === "light" ? (lang === "bn" ? "চালু করুন" : "Enable") : (lang === "bn" ? "বন্ধ করুন" : "Disable")}
                </button>
              </div>

              {/* Parent portal — hidden link, low-prominence */}
              {user?.role === "student" && (
                <div
                  style={{
                    padding: "var(--space-3) var(--space-4)",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid rgba(16,185,129,0.2)",
                    backgroundColor: "rgba(16,185,129,0.04)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                    <Shield size={13} style={{ color: "var(--color-success, #10b981)" }} />
                    <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--color-success, #10b981)" }}>
                      {lang === "bn" ? "অভিভাবক সাইট" : "Parent Site"}
                    </span>
                  </div>
                  <a
                    href={parentSiteUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      display: "inline-flex", alignItems: "center", gap: 4,
                      fontSize: "11px", color: "var(--color-success, #10b981)",
                      textDecoration: "underline", textDecorationStyle: "dotted",
                    }}
                  >
                    <span>{lang === "bn" ? "অভিভাবক হিসেবে লগইন করুন" : "Sign in as parent"}</span>
                    <ExternalLink size={11} />
                  </a>
                </div>
              )}
            </div>

            {/* Drawer footer — Logout */}
            {user && (
              <div style={{ padding: "var(--space-4) var(--space-5)", borderTop: "1px solid var(--color-border)" }}>
                <button
                  onClick={() => { setDrawerOpen(false); onLogout(); }}
                  className="touch-target"
                  style={{
                    width: "100%", display: "flex", alignItems: "center", justifyContent: "center",
                    gap: 8, padding: "10px 16px",
                    borderRadius: "var(--radius-md)",
                    backgroundColor: "rgba(239,68,68,0.08)",
                    color: "var(--color-danger, #ef4444)",
                    border: "1px solid rgba(239,68,68,0.2)",
                    fontSize: "var(--text-xs)", fontWeight: 700,
                  }}
                >
                  <LogOut size={15} />
                  <span>{t.nav.logout}</span>
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      <style>{`
        @media (max-width: 640px) {
          .navbar-desktop-only { display: none !important; }
        }
        @media (min-width: 641px) {
          .navbar-mobile-only { display: none !important; }
        }
      `}</style>
    </>
  );
};
