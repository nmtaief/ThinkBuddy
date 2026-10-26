"use client";

import React from "react";
import { Language, translations } from "@/lib/i18n";
import { SessionUser } from "@/lib/types";
import { Religion, RELIGION_CONFIGS } from "@/lib/religion";
import { BookOpen, Globe, Moon, Sun, LogOut } from "lucide-react";

interface NavbarProps {
  user: SessionUser | null;
  lang: Language;
  onToggleLang: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onLogout: () => void;
  religion?: Religion;
  onChangeReligion?: (rel: Religion) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  user,
  lang,
  onToggleLang,
  theme,
  onToggleTheme,
  onLogout,
  religion = "islam",
  onChangeReligion,
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
        {/* Dynamic Faith / Tradition Selector */}
        {onChangeReligion && (
          <select
            value={religion}
            onChange={(e) => onChangeReligion(e.target.value as Religion)}
            className="touch-target"
            style={{
              padding: "6px 10px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-surface)",
              color: "var(--color-text)",
              fontSize: "var(--text-xs)",
              fontWeight: 600,
              cursor: "pointer",
            }}
            aria-label="Select Faith Tradition"
            title={lang === "bn" ? "ধর্মীয় ও সামাজিক দৃষ্টিভঙ্গি নির্বাচন" : "Select Faith Tradition"}
          >
            {Object.values(RELIGION_CONFIGS).map((rel) => (
              <option key={rel.id} value={rel.id}>
                {rel.icon} {lang === "bn" ? rel.name_bn : rel.name_en}
              </option>
            ))}
          </select>
        )}

        {/* Language switch */}
        <button
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
