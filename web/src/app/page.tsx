"use client";

import React, { useState, useEffect } from "react";
import { Navbar } from "@/components/layout/Navbar";
import { Sidebar } from "@/components/layout/Sidebar";
import { BottomNav } from "@/components/layout/BottomNav";
import { TodayView } from "@/components/student/TodayView";
import { PracticeQuizRunner } from "@/components/student/PracticeQuizRunner";
import { AIChatView } from "@/components/student/AIChatView";
import { ProgressView } from "@/components/student/ProgressView";
import { StudentChangeRequestView } from "@/components/student/StudentChangeRequestView";
import { ParentDashboardView } from "@/components/parent/ParentDashboardView";
import { StudySetupEditorView } from "@/components/parent/StudySetupEditorView";
import { ParentSuggestionsView } from "@/components/parent/ParentSuggestionsView";
import { ParentOnboardingView } from "@/components/parent/ParentOnboardingView";
import { NotificationPreferencesView } from "@/components/parent/NotificationPreferencesView";
import { BroadAnswerView } from "@/components/student/BroadAnswerView";
import { Language, translations } from "@/lib/i18n";
import { apiClient } from "@/lib/api-client";
import { SessionUser, ClientConfig, TodayPayload, ChildSummary } from "@/lib/types";

export default function Home() {
  const [lang, setLang] = useState<Language>("bn");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [user, setUser] = useState<SessionUser | null>(null);
  const [config, setConfig] = useState<ClientConfig>({
    min_supported_version: "1.0.0",
    quiz_security_mode: "assessed_app_only",
    features: {
      rag_chat_enabled: true,
      parent_dashboard_enabled: true,
      notifications_enabled: true,
      progress_mastery_enabled: true,
    },
    limits: {
      daily_minutes_min: 15,
      daily_minutes_max: 360,
      max_block_minutes: 90,
    },
    observance_catalog: [
      {
        id: "obs_eid",
        name_bn: "পবিত্র ঈদুল ফিতর",
        name_en: "Eid-ul-Fitr",
        start_date: "2026-03-20",
        end_date: "2026-03-23",
      },
    ],
  });
  const [currentTab, setCurrentTab] = useState<string>("today");

  // Mock domain data
  const [todayData, setTodayData] = useState<TodayPayload | null>(null);
  const [childrenList, setChildrenList] = useState<ChildSummary[]>([]);
  const [activeChildId, setActiveChildId] = useState<string>("stu_101");

  // Load config & auth on startup
  useEffect(() => {
    async function init() {
      const cfg = await apiClient.getConfig();
      setConfig(cfg);

      const authStatus = await apiClient.getAuthStatus();
      if (authStatus.authenticated && authStatus.user) {
        setUser(authStatus.user);
        if (authStatus.user.role === "parent") {
          setCurrentTab("dashboard");
        } else {
          setCurrentTab("today");
        }
      } else {
        // Default local dev student session
        const loginRes = await apiClient.login("student", "তাহমিদ আলিম");
        setUser(loginRes.user);
        setCurrentTab("today");
      }
    }
    init();
  }, []);

  // Load tab data
  useEffect(() => {
    if (!user) return;
    async function loadData() {
      if (user?.role === "student") {
        const td = await apiClient.getToday(user.student_id || "stu_101");
        setTodayData(td);
      } else if (user?.role === "parent") {
        const kids = await apiClient.getChildren();
        setChildrenList(kids);
        if (kids.length > 0 && !activeChildId) {
          setActiveChildId(kids[0].student_id);
        }
      }
    }
    loadData();
  }, [user, activeChildId]);

  const toggleLang = () => {
    setLang((prev) => (prev === "bn" ? "en" : "bn"));
  };

  const toggleTheme = () => {
    setTheme((prev) => {
      const next = prev === "light" ? "dark" : "light";
      document.documentElement.setAttribute("data-theme", next);
      return next;
    });
  };

  const handleSwitchRole = async (newRole: "student" | "parent") => {
    const res = await apiClient.login(
      newRole,
      newRole === "student" ? "তাহমিদ আলিম (শিক্ষার্থী)" : "রফিকুল ইসলাম (অভিভাবক)"
    );
    setUser(res.user);
    if (newRole === "parent") {
      const kids = await apiClient.getChildren();
      setChildrenList(kids);
      if (kids.length > 0) {
        setActiveChildId(kids[0].student_id);
      }
    }
    setCurrentTab(newRole === "student" ? "today" : "dashboard");
  };

  const handleLogout = async () => {
    await apiClient.logout();
    setUser(null);
  };

  const handleToggleTask = async (taskId: string, newStatus: "completed" | "pending") => {
    await apiClient.updateTaskStatus(taskId, newStatus);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <Navbar
        user={user}
        lang={lang}
        onToggleLang={toggleLang}
        theme={theme}
        onToggleTheme={toggleTheme}
        onLogout={handleLogout}
      />

      {/* Dev role switcher banner */}
      <nav
        aria-label="Role selector"
        style={{
          backgroundColor: "var(--color-surface)",
          borderBottom: "1px solid var(--color-border)",
          padding: "var(--space-2) var(--space-6)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontSize: "var(--text-xs)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <span style={{ fontWeight: 600, color: "var(--color-text-muted)" }}>রোল নির্বাচন:</span>
          <button
            onClick={() => handleSwitchRole("student")}
            className={user?.role === "student" ? "btn-primary touch-target" : "btn-secondary touch-target"}
            style={{ fontSize: "var(--text-xs)", height: 32, padding: "0 12px" }}
          >
            শিক্ষার্থী (Student)
          </button>
          <button
            onClick={() => handleSwitchRole("parent")}
            className={user?.role === "parent" ? "btn-primary touch-target" : "btn-secondary touch-target"}
            style={{ fontSize: "var(--text-xs)", height: 32, padding: "0 12px" }}
          >
            অভিভাবক (Parent)
          </button>
        </div>
        <span style={{ color: "var(--color-text-muted)" }}>ThinkBuddy Web Client v1.0</span>
      </nav>

      <div className="app-container">
        {user && (
          <Sidebar
            role={user.role}
            currentTab={currentTab}
            onSelectTab={setCurrentTab}
            lang={lang}
          />
        )}

        <main className="content-area">
          <h1 style={{ position: "absolute", width: 1, height: 1, padding: 0, margin: -1, overflow: "hidden", clip: "rect(0, 0, 0, 0)", border: 0 }}>
            ThinkBuddy Smart Learning Platform
          </h1>
          {/* STUDENT VIEWS */}
          {user?.role === "student" && (
            <>
              {currentTab === "today" && todayData && (
                <TodayView
                  todayData={todayData}
                  lang={lang}
                  onToggleTask={handleToggleTask}
                />
              )}
              {currentTab === "plan" && todayData && (
                <TodayView
                  todayData={todayData}
                  lang={lang}
                  onToggleTask={handleToggleTask}
                />
              )}
              {currentTab === "quiz" && <PracticeQuizRunner lang={lang} config={config} />}
              {currentTab === "broad-answer" && <BroadAnswerView lang={lang} />}
              {currentTab === "chat" && <AIChatView lang={lang} />}
              {currentTab === "progress" && <ProgressView lang={lang} />}
              {currentTab === "revision" && <ProgressView lang={lang} />}
              {currentTab === "change-request" && (
                <StudentChangeRequestView
                  studentId={user.student_id || "stu_101"}
                  lang={lang}
                />
              )}
            </>
          )}

          {/* PARENT VIEWS */}
          {user?.role === "parent" && (
            <>
              {currentTab === "children" && <ParentOnboardingView lang={lang} />}
              {currentTab === "dashboard" && childrenList.length > 0 && (
                <ParentDashboardView
                  childrenList={childrenList}
                  activeChildId={activeChildId}
                  onSelectChild={setActiveChildId}
                  lang={lang}
                />
              )}
              {currentTab === "study-setup" && config && (
                <StudySetupEditorView
                  studentId={activeChildId}
                  config={config}
                  lang={lang}
                />
              )}
              {(currentTab === "suggestions" ||
                currentTab === "auto-adjustments" ||
                currentTab === "change-requests") && (
                <ParentSuggestionsView
                  studentId={activeChildId}
                  lang={lang}
                />
              )}
              {currentTab === "notifications" && (
                <NotificationPreferencesView lang={lang} />
              )}
            </>
          )}
        </main>
      </div>

      {user && (
        <BottomNav
          role={user.role}
          currentTab={currentTab}
          onSelectTab={setCurrentTab}
          lang={lang}
        />
      )}
    </div>
  );
}
