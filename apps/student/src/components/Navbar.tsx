import React from "react";
import { UserProfile, Language, translations } from "@thinkbuddy/shared";
import { BookOpen, Globe, Moon, Sun, Menu } from "lucide-react";

interface NavbarProps {
  user: UserProfile;
  lang: Language;
  onToggleLang: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onOpenProfile: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  user,
  lang,
  onToggleLang,
  theme,
  onToggleTheme,
  onOpenProfile,
}) => {
  const t = translations[lang];

  return (
    <header
      style={{
        backgroundColor: "var(--color-surface)",
        borderBottom: "1px solid var(--color-border)",
        padding: "0 var(--space-4)",
        height: 58,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        position: "sticky",
        top: 0,
        zIndex: 40,
        boxShadow: "var(--shadow-subtle)",
      }}
    >
      {/* Brand Logo only (Clean, no student badge up top!) */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <div
          style={{
            width: 34,
            height: 34,
            borderRadius: "var(--radius-md)",
            backgroundColor: "var(--color-primary)",
            color: "#FFFFFF",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <BookOpen size={18} />
        </div>
        <span
          style={{
            fontSize: "var(--text-lg)",
            fontWeight: 800,
            color: "var(--color-text-main)",
            letterSpacing: "-0.02em",
          }}
        >
          ThinkBuddy
        </span>
      </div>

      {/* Right Controls: Desktop shows quick tools + Profile; Mobile shows just Profile Trigger */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        {/* Desktop Quick Language Toggle */}
        <button
          onClick={onToggleLang}
          className="btn-secondary touch-target hide-on-mobile"
          style={{
            minHeight: 36,
            padding: "0 10px",
            fontSize: "var(--text-xs)",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
          aria-label={lang === "bn" ? "Switch to English" : "বাংলায় পরিবর্তন করুন"}
        >
          <Globe size={14} />
          <span>{lang === "bn" ? "English" : "বাংলা"}</span>
        </button>

        {/* Desktop Quick Dark Mode Toggle */}
        <button
          onClick={onToggleTheme}
          className="btn-secondary touch-target hide-on-mobile"
          style={{
            minHeight: 36,
            padding: "0 10px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
          aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
        >
          {theme === "light" ? <Moon size={15} /> : <Sun size={15} />}
        </button>

        {/* Profile / Menu Button (Opens Profile Drawer with hidden Parent Portal link) */}
        <button
          onClick={onOpenProfile}
          className="touch-target"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "4px 8px",
            borderRadius: "var(--radius-full)",
            backgroundColor: "var(--color-surface-hover)",
            border: "1px solid var(--color-border)",
            cursor: "pointer",
            transition: "all 0.15s ease",
          }}
          title={lang === "bn" ? "প্রোফাইল ও মেনু খুলুন" : "Open Profile & Menu"}
          aria-label={lang === "bn" ? "প্রোফাইল ও মেনু খুলুন" : "Open Profile & Menu"}
        >
          {user.photoURL ? (
            <img
              src={user.photoURL}
              alt={user.name}
              style={{
                width: 30,
                height: 30,
                borderRadius: "var(--radius-full)",
                objectFit: "cover",
              }}
            />
          ) : (
            <div
              style={{
                width: 30,
                height: 30,
                borderRadius: "var(--radius-full)",
                backgroundColor: "var(--color-primary-surface)",
                color: "var(--color-primary)",
                fontWeight: 800,
                fontSize: "var(--text-xs)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {user.name.slice(0, 1)}
            </div>
          )}

          <span
            className="student-name-desktop"
            style={{
              fontSize: "var(--text-xs)",
              fontWeight: 700,
              color: "var(--color-text-main)",
              maxWidth: 110,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {user.name}
          </span>

          <Menu size={16} style={{ color: "var(--color-text-muted)" }} />
        </button>
      </div>

      <style>{`
        @media (max-width: 640px) {
          .hide-on-mobile {
            display: none !important;
          }
          .student-name-desktop {
            display: none !important;
          }
        }
      `}</style>
    </header>
  );
};
