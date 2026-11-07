import React from "react";
import { Language, translations } from "@thinkbuddy/shared";
import { CalendarDays, HelpCircle, RotateCcw, Sparkles, TrendingUp } from "lucide-react";

interface BottomNavProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  lang: Language;
}

export const BottomNav: React.FC<BottomNavProps> = ({ currentTab, onSelectTab, lang }) => {
  const t = translations[lang];

  const tabs = [
    { id: "today", label: t.nav.today, icon: CalendarDays },
    { id: "revision", label: t.nav.revision, icon: RotateCcw },
    { id: "quiz", label: t.nav.quiz, icon: HelpCircle },
    { id: "chat", label: t.nav.chat, icon: Sparkles },
    { id: "progress", label: t.nav.progress, icon: TrendingUp },
  ];

  return (
    <nav
      className="mobile-bottom-nav"
      aria-label="Mobile Navigation"
      style={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        height: 60,
        paddingBottom: "env(safe-area-inset-bottom, 0px)",
        backgroundColor: "var(--color-surface)",
        borderTop: "1px solid var(--color-border)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-around",
        zIndex: 50,
        boxShadow: "0 -2px 10px rgba(0, 0, 0, 0.05)",
      }}
    >
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = currentTab === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => onSelectTab(tab.id)}
            className="touch-target"
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 2,
              background: "none",
              border: "none",
              cursor: "pointer",
              color: isActive ? "var(--color-primary)" : "var(--color-text-muted)",
              padding: "4px 0",
              transition: "color 0.15s ease",
            }}
          >
            <Icon size={19} strokeWidth={isActive ? 2.5 : 2} />
            <span
              style={{
                fontSize: "11px",
                fontWeight: isActive ? 800 : 500,
                lineHeight: 1.2,
                whiteSpace: "nowrap",
              }}
            >
              {tab.label}
            </span>
          </button>
        );
      })}

      <style>{`
        @media (min-width: 769px) {
          .mobile-bottom-nav {
            display: none !important;
          }
        }
      `}</style>
    </nav>
  );
};
