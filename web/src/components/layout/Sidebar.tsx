"use client";

import React from "react";
import { Language, translations } from "@/lib/i18n";
import { UserRole } from "@/lib/types";
import {
  Calendar,
  Clock,
  RotateCcw,
  HelpCircle,
  MessageSquare,
  BarChart2,
  Settings,
  Users,
  Sliders,
  Sparkles,
  GitPullRequest,
  CheckCircle,
} from "lucide-react";

interface SidebarProps {
  role: UserRole;
  currentTab: string;
  onSelectTab: (tab: string) => void;
  lang: Language;
}

export const Sidebar: React.FC<SidebarProps> = ({ role, currentTab, onSelectTab, lang }) => {
  const t = translations[lang];

  const studentLinks = [
    { id: "today", label: t.nav.today, icon: Calendar },
    { id: "plan", label: t.nav.plan, icon: Clock },
    { id: "revision", label: t.nav.revision, icon: RotateCcw },
    { id: "quiz", label: t.nav.quiz, icon: HelpCircle },
    { id: "chat", label: t.nav.chat, icon: MessageSquare },
    { id: "progress", label: t.nav.progress, icon: BarChart2 },
    { id: "change-request", label: t.nav.changeRequest, icon: GitPullRequest },
  ];

  const parentLinks = [
    { id: "children", label: t.nav.children, icon: Users },
    { id: "dashboard", label: t.nav.dashboard, icon: BarChart2 },
    { id: "study-setup", label: t.nav.studySetup, icon: Sliders },
    { id: "suggestions", label: t.nav.suggestions, icon: Sparkles },
    { id: "auto-adjustments", label: t.nav.autoAdjustments, icon: CheckCircle },
    { id: "change-requests", label: t.nav.changeRequest, icon: GitPullRequest },
  ];

  const links = role === "parent" ? parentLinks : studentLinks;

  return (
    <aside
      className="sidebar-container"
      style={{
        width: 260,
        backgroundColor: "var(--color-surface)",
        borderRight: "1px solid var(--color-border)",
        display: "flex",
        flexDirection: "column",
        padding: "var(--space-4) var(--space-2)",
        flexShrink: 0,
      }}
    >
      <nav style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        {links.map((link) => {
          const Icon = link.icon;
          const isActive = currentTab === link.id;
          return (
            <button
              key={link.id}
              data-testid={`nav-${link.id}`}
              onClick={() => onSelectTab(link.id)}
              className="touch-target"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-3)",
                padding: "var(--space-3) var(--space-4)",
                borderRadius: "var(--radius-md)",
                backgroundColor: isActive ? "var(--color-primary-surface)" : "transparent",
                color: isActive ? "var(--color-primary)" : "var(--color-text-secondary)",
                fontWeight: isActive ? 600 : 500,
                fontSize: "var(--text-sm)",
                textAlign: "left",
                width: "100%",
                justifyContent: "flex-start",
                transition: "all 0.15s ease",
              }}
            >
              <Icon size={20} />
              <span>{link.label}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
};
