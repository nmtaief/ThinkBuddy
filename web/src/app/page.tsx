"use client";

import React, { useState, useEffect } from "react";
import { Navbar } from "@/components/layout/Navbar";
import { Sidebar } from "@/components/layout/Sidebar";
import { BottomNav } from "@/components/layout/BottomNav";
import { TodayView } from "@/components/student/TodayView";
import { PracticeQuizRunner } from "@/components/student/PracticeQuizRunner";
import { AIChatView } from "@/components/student/AIChatView";
import { ProgressView } from "@/components/student/ProgressView";
import RevisionQueueView from "@/components/student/RevisionQueueView";
import PlanTimelineView from "@/components/student/PlanTimelineView";
import { StudentChangeRequestView } from "@/components/student/StudentChangeRequestView";
import { ParentDashboardView } from "@/components/parent/ParentDashboardView";
import { StudySetupEditorView } from "@/components/parent/StudySetupEditorView";
import { ParentSuggestionsView } from "@/components/parent/ParentSuggestionsView";
import { ParentOnboardingView } from "@/components/parent/ParentOnboardingView";
import { NotificationPreferencesView } from "@/components/parent/NotificationPreferencesView";
import { BroadAnswerView } from "@/components/student/BroadAnswerView";
import { StudentOnboardingWizard } from "@/components/student/StudentOnboardingWizard";
import { FirebaseSignInModal } from "@/components/auth/FirebaseSignInModal";
import { AuthView } from "@/components/auth/AuthView";
import { Language, translations } from "@/lib/i18n";
import { apiClient } from "@/lib/api-client";
import { enrichStudyTaskWithCurriculumData } from "@/lib/curriculum-study-engine";
import { SessionUser, ClientConfig, TodayPayload, ChildSummary } from "@/lib/types";

export default function Home() {
  const [lang, setLang] = useState<Language>("bn");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [user, setUser] = useState<SessionUser | null>(null);
  const [isFirebaseModalOpen, setFirebaseModalOpen] = useState(false);
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
        try {
          const loginRes = await apiClient.login("student", "তাহমিদ আলিম");
          setUser(loginRes.user);
          setCurrentTab("today");
        } catch {
          setUser({
            id: "stu_101",
            role: "student",
            name: "তাহমিদ আলিম",
            student_id: "stu_101",
          });
          setCurrentTab("today");
        }
      }

      const tabParam = new URLSearchParams(window.location.search).get("tab");
      if (tabParam) {
        setCurrentTab(tabParam);
      }
    }
    init();
  }, []);


  // Load tab data
  useEffect(() => {
    if (!user) return;
    async function loadData() {
      if (user?.role === "student") {
        let td: TodayPayload | null = null;
        try {
          td = await apiClient.getToday(user.student_id || "stu_101");
        } catch {}

        // Check if student has activated a custom day-by-day plan in localStorage
        try {
          const rawSched = typeof window !== "undefined" ? localStorage.getItem("tb_active_schedule") : null;
          if (rawSched) {
            const sched = JSON.parse(rawSched);
            const dayMap = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
            const todayId = dayMap[new Date().getDay()];
            const todayPlan = sched.find((d: any) => d.day_id === todayId) || sched[0];
            if (todayPlan) {
              const customTasks: any[] = [];
              if (todayPlan.is_weekend && todayPlan.special_revision_block_minutes) {
                customTasks.push(
                  enrichStudyTaskWithCurriculumData({
                    id: "task_mega_rev",
                    subject: "মেগা স্পেসড রিভিশন",
                    title: "সাপ্তাহিক লাইটনার বক্স রিভিশন ও প্র্যাকটিস টেস্ট",
                    task_type: "revision",
                    estimated_minutes: todayPlan.special_revision_block_minutes,
                    status: "pending",
                    guidelines: "সারা সপ্তাহের সব অধ্যায়ের রিভিশন ও কুইজ সম্পন্ন করো।",
                  })
                );
              }
              (todayPlan.items || []).forEach((it: any, idx: number) => {
                customTasks.push(
                  enrichStudyTaskWithCurriculumData({
                    id: `task_${it.subject_slug}_${idx}`,
                    subject: it.subject_name_bn,
                    title: `${it.subject_name_bn} - নতুন পড়া ও স্পেসড রিভিশন`,
                    task_type: "study",
                    estimated_minutes: it.total_minutes,
                    status: "pending",
                    guidelines: `📖 নতুন পড়া: ${it.study_minutes} মি (৭৫%) • 🔄 স্পেসড রিভিশন: ${it.revision_minutes} মি (২৫%)`,
                  })
                );
              });
              const savedStreak = typeof window !== "undefined" ? localStorage.getItem("tb_streak_days") : null;
              const currentStreak = savedStreak !== null ? parseInt(savedStreak, 10) || 0 : 0;
              td = {
                student_id: user.student_id || "stu_101",
                date: new Date().toISOString().split("T")[0],
                day_type: todayPlan.is_weekend ? "holiday" : "school_day",
                streak_days: currentStreak,
                tasks_completed_count: 0,
                tasks_total_count: customTasks.length,
                remaining_minutes: customTasks.reduce((acc, t) => acc + (t.estimated_minutes || 0), 0),
                exam_countdown: td?.exam_countdown || {
                  exam_name: "টার্গেট পরীক্ষা",
                  days_left: 60,
                  exam_date: "2026-11-20",
                },
                tasks: customTasks,
              };
            }
          }
        } catch {}

        if (td) setTodayData(td);
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

    // Restore user preferences
  useEffect(() => {
    try {
      const savedTheme = localStorage.getItem("tb_theme") as "light" | "dark" | null;
      const prefersDark = typeof window !== "undefined" && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
      const initialTheme = savedTheme || (prefersDark ? "dark" : "light");
      setTheme(initialTheme);
      document.documentElement.setAttribute("data-theme", initialTheme);
      if (initialTheme === "dark") {
        document.documentElement.classList.add("dark");
      } else {
        document.documentElement.classList.remove("dark");
      }

      const savedLang = localStorage.getItem("tb_lang") as Language | null;
      if (savedLang) {
        setLang(savedLang);
        document.documentElement.lang = savedLang;
      }
    } catch {}
  }, []);

  const toggleLang = () => {
    setLang((prev) => {
      const next = prev === "bn" ? "en" : "bn";
      if (typeof document !== "undefined") {
        document.documentElement.lang = next;
      }
      try {
        localStorage.setItem("tb_lang", next);
      } catch {}
      return next;
    });
  };

  const toggleTheme = () => {
    setTheme((prev) => {
      const next = prev === "light" ? "dark" : "light";
      if (typeof document !== "undefined") {
        document.documentElement.setAttribute("data-theme", next);
        if (next === "dark") {
          document.documentElement.classList.add("dark");
        } else {
          document.documentElement.classList.remove("dark");
        }
      }
      try {
        localStorage.setItem("tb_theme", next);
      } catch {}
      return next;
    });
  };

  const handleLogin = async (role: "student" | "parent", displayName: string) => {
    const res = await apiClient.login(role, displayName);
    setUser(res.user);
    if (role === "parent") {
      const kids = await apiClient.getChildren();
      setChildrenList(kids);
      if (kids.length > 0) {
        setActiveChildId(kids[0].student_id);
      }
      setCurrentTab("dashboard");
    } else {
      const td = await apiClient.getToday(res.user.student_id || "stu_101");
      setTodayData(td);
      setCurrentTab("today");
    }
  };

  const handleLogout = async () => {
    await apiClient.logout();
    setUser(null);
  };

  const handleToggleTask = async (taskId: string, newStatus: "completed" | "pending") => {
    await apiClient.updateTaskStatus(taskId, newStatus);
  };

  // If unauthenticated, show secure login portal (Parent / Student login)
  if (!user) {
    return (
      <>
        <AuthView
          lang={lang}
          theme={theme}
          onToggleLang={toggleLang}
          onToggleTheme={toggleTheme}
          onLogin={handleLogin}
          onGoogleSuccess={(newUser) => {
            setUser(newUser);
            if (newUser.role === "parent") {
              setCurrentTab("dashboard");
            } else {
              setCurrentTab("today");
            }
          }}
          onOpenFirebaseModal={() => setFirebaseModalOpen(true)}
        />
        <FirebaseSignInModal
          isOpen={isFirebaseModalOpen}
          onClose={() => setFirebaseModalOpen(false)}
          onSuccess={(newUser) => {
            setUser(newUser);
            if (newUser.role === "parent") {
              setCurrentTab("dashboard");
            } else {
              setCurrentTab("today");
            }
          }}
          lang={lang}
        />
      </>
    );
  }

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
              {currentTab === "onboarding" && (
                <StudentOnboardingWizard
                  lang={lang}
                  onComplete={() => {
                    if (typeof window !== "undefined") {
                      window.history.replaceState({}, '', window.location.pathname);
                    }
                    setCurrentTab("today");
                    // Refresh today data from localStorage active schedule
                    try {
                      const rawSched = typeof window !== "undefined" ? localStorage.getItem("tb_active_schedule") : null;
                      if (rawSched && user) {
                        const sched = JSON.parse(rawSched);
                        const dayMap = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
                        const todayId = dayMap[new Date().getDay()];
                        const todayPlan = sched.find((d: any) => d.day_id === todayId) || sched[0];
                        if (todayPlan) {
                          const customTasks: any[] = [];
                          if (todayPlan.is_weekend && todayPlan.special_revision_block_minutes) {
                            customTasks.push(
                              enrichStudyTaskWithCurriculumData({
                                id: "task_mega_rev",
                                subject: "মেগা স্পেসড রিভিশন",
                                title: "সাপ্তাহিক লাইটনার বক্স রিভিশন ও প্র্যাকটিস টেস্ট",
                                task_type: "revision",
                                estimated_minutes: todayPlan.special_revision_block_minutes,
                                status: "pending",
                                guidelines: "সারা সপ্তাহের সব অধ্যায়ের রিভিশন ও কুইজ সম্পন্ন করো।",
                              })
                            );
                          }
                          (todayPlan.items || []).forEach((it: any, idx: number) => {
                            customTasks.push(
                              enrichStudyTaskWithCurriculumData({
                                id: `task_${it.subject_slug}_${idx}`,
                                subject: it.subject_name_bn,
                                title: `${it.subject_name_bn} - নতুন পড়া ও স্পেসড রিভিশন`,
                                task_type: "study",
                                estimated_minutes: it.total_minutes,
                                status: "pending",
                                guidelines: `📖 নতুন পড়া: ${it.study_minutes} মি (৭৫%) • 🔄 স্পেসড রিভিশন: ${it.revision_minutes} মি (২৫%)`,
                              })
                            );
                          });
                          const savedStreak = typeof window !== "undefined" ? localStorage.getItem("tb_streak_days") : null;
                          const currentStreak = savedStreak !== null ? parseInt(savedStreak, 10) || 0 : 0;
                          setTodayData({
                            student_id: user.student_id || "stu_101",
                            date: new Date().toISOString().split("T")[0],
                            day_type: todayPlan.is_weekend ? "holiday" : "school_day",
                            streak_days: currentStreak,
                            tasks_completed_count: 0,
                            tasks_total_count: customTasks.length,
                            remaining_minutes: customTasks.reduce((acc: number, t: any) => acc + (t.estimated_minutes || 0), 0),
                            exam_countdown: {
                              exam_name: "টার্গেট পরীক্ষা",
                              days_left: 60,
                              exam_date: "2026-11-20",
                            },
                            tasks: customTasks,
                          });
                        }
                      }
                    } catch {}
                  }}
                />
              )}
              {currentTab === "today" && todayData && (
                <TodayView
                  todayData={todayData}
                  lang={lang}
                            studentName={user.name}
                  onToggleTask={handleToggleTask}
                />
              )}
              {currentTab === "plan" && (
                <PlanTimelineView
                  todayData={todayData}
                  lang={lang}
                  onNavigateTab={setCurrentTab}
                />
              )}
              {currentTab === "quiz" && <PracticeQuizRunner lang={lang} config={config} />}
              {currentTab === "broad-answer" && <BroadAnswerView lang={lang} />}
              {currentTab === "chat" && <AIChatView lang={lang} />}
              {currentTab === "progress" && <ProgressView lang={lang} />}
              {currentTab === "revision" && (
                <RevisionQueueView
                  lang={lang}
                  onNavigateToToday={() => setCurrentTab("today")}
                />
              )}
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
              {currentTab === "dashboard" && (
                childrenList.length > 0 ? (
                  <ParentDashboardView
                    childrenList={childrenList}
                    activeChildId={activeChildId}
                    onSelectChild={setActiveChildId}
                    lang={lang}
                  />
                ) : (
                  <div className="card" style={{ textAlign: "center", padding: "var(--space-8)" }}>
                    <p style={{ color: "var(--color-text-muted)", marginBottom: "var(--space-4)" }}>
                      {lang === "bn" ? "কোনো শিক্ষার্থীর প্রোফাইল যুক্ত করা নেই।" : "No student linked to this parent account yet."}
                    </p>
                    <button
                      onClick={() => setCurrentTab("children")}
                      className="btn-primary touch-target"
                    >
                      {lang === "bn" ? "শিক্ষার্থী যুক্ত করুন" : "Link Student Profile"}
                    </button>
                  </div>
                )
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

      <FirebaseSignInModal
        isOpen={isFirebaseModalOpen}
        onClose={() => setFirebaseModalOpen(false)}
        onSuccess={(newUser) => {
          setUser(newUser);
          if (newUser.role === "parent") {
            setCurrentTab("dashboard");
          } else {
            setCurrentTab("today");
          }
        }}
        lang={lang}
      />
    </div>
  );
}
