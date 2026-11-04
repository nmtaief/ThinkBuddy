"use client";

import React from "react";
import { Language, translations } from "@/lib/i18n";
import { SessionUser } from "@/lib/types";
import { BookOpen, Globe, Moon, Sun, LogOut } from "lucide-react";

interface NavbarProps {
  user: SessionUser | null;
  lang: Language;
  onToggleLang: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  user,
  lang,
  onToggleLang,
  theme,
  onToggleTheme,
  onLogout,
}) => {
  const t = translations[lang];

  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "var(--space-3) var(--space-6)",
        backgroundColor: "var(--color-surface)",
        borderBottom: "1px solid var(--color-border)",
        position: "sticky",
        top: 0,
        zIndex: 50,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: "var(--radius-md)",
            backgroundColor: "var(--color-primary)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--color-text-inverse)",
          }}
        >
          <BookOpen size={20} />
        </div>
        <div>
          <span style={{ fontWeight: 700, fontSize: "var(--text-lg)", letterSpacing: "-0.02em" }}>
            {t.app.title}
          </span>
          <span
            style={{
              marginLeft: "var(--space-2)",
              fontSize: "var(--text-xs)",
              backgroundColor: "var(--color-primary-surface)",
              color: "var(--color-primary)",
              padding: "2px 8px",
              borderRadius: "var(--radius-full)",
              fontWeight: 600,
            }}
          >
            {user ? t.roles[user.role] : "Beta"}
          </span>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap" }}>
        {/* Language switch */}
        <button
          id="btn-toggle-lang"
          data-testid="btn-toggle-lang"
          onClick={onToggleLang}
          className="btn-secondary touch-target"
          style={{ display: "flex", gap: "var(--space-1)", fontSize: "var(--text-sm)" }}
          aria-label={t.app.switchLanguage}
          title={t.app.switchLanguage}
        >
          <Globe size={16} />
          <span>{lang === "bn" ? "English" : "বাংলা"}</span>
        </button>

        {/* Theme switch */}
        <button
          id="btn-toggle-theme"
          data-testid="btn-toggle-theme"
          onClick={onToggleTheme}
          className="btn-secondary touch-target"
          style={{ width: 44, height: 44, padding: 0 }}
          aria-label={theme === "light" ? t.app.themeDark : t.app.themeLight}
          title={theme === "light" ? t.app.themeDark : t.app.themeLight}
        >
          {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
        </button>

        {/* User profile & Logout */}
        {user && (
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginLeft: "var(--space-2)" }}>
            <span style={{ fontSize: "var(--text-sm)", fontWeight: 500, color: "var(--color-text-secondary)" }}>
              {user.name}
            </span>
            <button
              id="btn-logout"
              data-testid="btn-logout"
              onClick={onLogout}
              className="btn-secondary touch-target"
              style={{ width: 44, height: 44, padding: 0, color: "var(--color-danger)" }}
              aria-label={t.nav.logout}
              title={t.nav.logout}
            >
              <LogOut size={18} />
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
