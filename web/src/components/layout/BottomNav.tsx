"use client";

import React from "react";
import { Language, translations } from "@/lib/i18n";
import { UserRole } from "@/lib/types";
import { Calendar, RotateCcw, HelpCircle, MessageSquare, BarChart2, Users, Sliders } from "lucide-react";

interface BottomNavProps {
  role: UserRole;
  currentTab: string;
  onSelectTab: (tab: string) => void;
  lang: Language;
}

export const BottomNav: React.FC<BottomNavProps> = ({ role, currentTab, onSelectTab, lang }) => {
  const t = translations[lang];

  const studentLinks = [
    { id: "today", label: t.nav.today, icon: Calendar },
    { id: "revision", label: t.nav.revision, icon: RotateCcw },
    { id: "quiz", label: t.nav.quiz, icon: HelpCircle },
    { id: "chat", label: t.nav.chat, icon: MessageSquare },
    { id: "progress", label: t.nav.progress, icon: BarChart2 },
  ];

  const parentLinks = [
    { id: "children", label: t.nav.children, icon: Users },
    { id: "dashboard", label: t.nav.dashboard, icon: BarChart2 },
    { id: "study-setup", label: t.nav.studySetup, icon: Sliders },
  ];

  const links = role === "parent" ? parentLinks : studentLinks;

  return (
    <nav
      className="bottom-nav-mobile"
      style={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        backgroundColor: "var(--color-surface)",
        borderTop: "1px solid var(--color-border)",
        display: "flex",
        justifyContent: "space-around",
        alignItems: "flex-start",
        paddingTop: 8,
        height: 64,
        zIndex: 9999,
        boxShadow: "0 -2px 10px rgba(0, 0, 0, 0.05)",
      }}
    >
      {links.map((link) => {
        const Icon = link.icon;
        const isActive = currentTab === link.id;
        return (
          <button
            key={link.id}
            data-testid={`bottom-nav-${link.id}`}
            onClick={() => onSelectTab(link.id)}
            className="touch-target"
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 2,
              padding: "4px 8px",
              color: isActive ? "var(--color-primary)" : "var(--color-text-muted)",
              fontSize: "var(--text-xs)",
              fontWeight: isActive ? 600 : 400,
              flex: 1,
            }}
          >
            <Icon size={20} />
            <span>{link.label}</span>
          </button>
        );
      })}
    </nav>
  );
};
