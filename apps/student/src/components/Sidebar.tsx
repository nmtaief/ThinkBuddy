import React from "react";
import { Language, translations } from "@thinkbuddy/shared";
import {
  CalendarDays,
  HelpCircle,
  RotateCcw,
  Sparkles,
  FileEdit,
  TrendingUp,
  MessageSquareShare,
} from "lucide-react";

interface SidebarProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  lang: Language;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, onSelectTab, lang }) => {
  const t = translations[lang];

  const navItems = [
    { id: "today", label: t.nav.today, icon: CalendarDays },
    { id: "quiz", label: t.nav.quiz, icon: HelpCircle },
    { id: "revision", label: t.nav.revision, icon: RotateCcw },
    { id: "chat", label: t.nav.chat, icon: Sparkles },
    { id: "broad-answer", label: t.nav.broadAnswer, icon: FileEdit },
    { id: "progress", label: t.nav.progress, icon: TrendingUp },
    { id: "change-request", label: t.nav.changeRequest, icon: MessageSquareShare },
  ];

  return (
    <aside
      className="desktop-sidebar"
      style={{
        width: 250,
        backgroundColor: "var(--color-surface)",
        borderRight: "1px solid var(--color-border)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: "var(--space-4) var(--space-3)",
        flexShrink: 0,
      }}
    >
      <nav style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className="touch-target"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-3)",
                padding: "10px 14px",
                borderRadius: "var(--radius-lg)",
                backgroundColor: isActive ? "var(--color-primary-surface)" : "transparent",
                color: isActive ? "var(--color-primary)" : "var(--color-text-secondary)",
                fontWeight: isActive ? 700 : 500,
                fontSize: "var(--text-sm)",
                border: "none",
                textAlign: "left",
                cursor: "pointer",
                transition: "all 0.12s ease",
                position: "relative",
              }}
            >
              <Icon size={18} />
              <span>{item.label}</span>
              {isActive && (
                <div
                  style={{
                    position: "absolute",
                    right: 0,
                    top: "20%",
                    bottom: "20%",
                    width: 3,
                    borderRadius: "2px 0 0 2px",
                    backgroundColor: "var(--color-primary)",
                  }}
                />
              )}
            </button>
          );
        })}
      </nav>

      <div
        style={{
          padding: "var(--space-3)",
          backgroundColor: "var(--color-surface-subtle)",
          borderRadius: "var(--radius-md)",
          fontSize: "var(--text-xs)",
          color: "var(--color-text-muted)",
          textAlign: "center",
          border: "1px solid var(--color-border-subtle)",
        }}
      >
        {t.app.footerNote}
      </div>

      <style>{`
        @media (max-width: 768px) {
          .desktop-sidebar {
            display: none !important;
          }
        }
      `}</style>
    </aside>
  );
};

