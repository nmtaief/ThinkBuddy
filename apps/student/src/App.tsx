import React, { useState, useEffect } from "react";
import {
  UserProfile,
  Language,
  RoutineSlot,
  getPersistedUser,
  signOutUser,
  getStoredRoutineSlots,
  saveStoredRoutineSlots,
  StudentExamSettings,
  getStoredExamSettings,
  saveStoredExamSettings,
} from "@thinkbuddy/shared";
import { Navbar } from "./components/Navbar";
import { Sidebar } from "./components/Sidebar";
import { BottomNav } from "./components/BottomNav";
import { TodayMergedView } from "./components/TodayMergedView";
import { AuthView } from "./components/AuthView";
import { ExamSettingsModal } from "./components/ExamSettingsModal";
import { ProfileDrawer } from "./components/ProfileDrawer";

const PracticeQuizRunner = React.lazy(() =>
  import("./components/PracticeQuizRunner").then((m) => ({ default: m.PracticeQuizRunner }))
);
const AIChatView = React.lazy(() =>
  import("./components/AIChatView").then((m) => ({ default: m.AIChatView }))
);
const ProgressView = React.lazy(() =>
  import("./components/ProgressView").then((m) => ({ default: m.ProgressView }))
);
const BroadAnswerView = React.lazy(() =>
  import("./components/BroadAnswerView").then((m) => ({ default: m.BroadAnswerView }))
);
const StudentChangeRequestView = React.lazy(() =>
  import("./components/StudentChangeRequestView").then((m) => ({ default: m.StudentChangeRequestView }))
);

export const App: React.FC = () => {
  const [lang, setLang] = useState<Language>(() => {
    try {
      const saved = localStorage.getItem("tb_lang");
      return (saved as Language) || "bn";
    } catch {
      return "bn";
    }
  });

  const [theme, setTheme] = useState<"light" | "dark">(() => {
    try {
      const saved = localStorage.getItem("tb_theme");
      return (saved as "light" | "dark") || "light";
    } catch {
      return "light";
    }
  });

  const [user, setUser] = useState<UserProfile | null>(() => getPersistedUser("student"));
  const [currentTab, setCurrentTab] = useState<string>("today");
  const [routineSlots, setRoutineSlots] = useState<RoutineSlot[]>(() => getStoredRoutineSlots());
  const [examSettings, setExamSettings] = useState<StudentExamSettings>(() => getStoredExamSettings());

  // Modal / Drawer states
  const [isExamModalOpen, setIsExamModalOpen] = useState(false);
  const [isProfileDrawerOpen, setIsProfileDrawerOpen] = useState(false);

  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
    try {
      localStorage.setItem("tb_theme", theme);
    } catch {}
  }, [theme]);

  // Apply lang to document
  useEffect(() => {
    document.documentElement.lang = lang;
    try {
      localStorage.setItem("tb_lang", lang);
    } catch {}
  }, [lang]);

  const toggleLang = () => {
    setLang((prev) => (prev === "bn" ? "en" : "bn"));
  };

  const toggleTheme = () => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  };

  const handleLogout = async () => {
    await signOutUser("student");
    setUser(null);
  };

  const handleSaveExamSettings = (newSettings: StudentExamSettings) => {
    setExamSettings(newSettings);
    saveStoredExamSettings(newSettings);
    if (user) {
      const updatedUser: UserProfile = {
        ...user,
        class_grade: newSettings.class_grade,
        syllabus: newSettings.syllabus,
        exam_title: newSettings.exam_title,
        exam_date: newSettings.exam_date,
      };
      setUser(updatedUser);
    }
  };

  if (!user) {
    return (
      <AuthView
        lang={lang}
        onToggleLang={toggleLang}
        theme={theme}
        onToggleTheme={toggleTheme}
        onLoginSuccess={(loggedUser) => setUser(loggedUser)}
      />
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
        onOpenProfile={() => setIsProfileDrawerOpen(true)}
      />

      <div
        style={{
          display: "flex",
          flex: 1,
          maxWidth: 1400,
          width: "100%",
          margin: "0 auto",
          paddingBottom: 76, // Buffer for mobile bottom nav
        }}
      >
        <Sidebar currentTab={currentTab} onSelectTab={setCurrentTab} lang={lang} />

        <main className="student-main-content">
          <React.Suspense fallback={<div style={{ padding: "var(--space-4)", color: "var(--color-text-muted)" }}>Loading...</div>}>
            {currentTab === "today" && (
              <TodayMergedView
                user={user}
                lang={lang}
                routineSlots={routineSlots}
                onUpdateRoutineSlots={(updated) => {
                  setRoutineSlots(updated);
                  saveStoredRoutineSlots(updated);
                }}
                examSettings={examSettings}
                onOpenExamSettings={() => setIsExamModalOpen(true)}
              />
            )}

            {currentTab === "quiz" && <PracticeQuizRunner lang={lang} />}
            {currentTab === "revision" && <ProgressView lang={lang} />}
            {currentTab === "chat" && <AIChatView lang={lang} />}
            {currentTab === "broad-answer" && <BroadAnswerView lang={lang} />}
            {currentTab === "progress" && <ProgressView lang={lang} />}
            {currentTab === "change-request" && <StudentChangeRequestView lang={lang} />}
          </React.Suspense>
        </main>
      </div>

      <BottomNav currentTab={currentTab} onSelectTab={setCurrentTab} lang={lang} />

      {/* Profile & Menu Drawer (includes hidden Parent Portal link) */}
      <ProfileDrawer
        isOpen={isProfileDrawerOpen}
        onClose={() => setIsProfileDrawerOpen(false)}
        user={user}
        examSettings={examSettings}
        onOpenExamSettings={() => setIsExamModalOpen(true)}
        lang={lang}
        onToggleLang={toggleLang}
        theme={theme}
        onToggleTheme={toggleTheme}
        onLogout={handleLogout}
      />

      {/* Class, Syllabus & Exam Goal Settings Modal */}
      <ExamSettingsModal
        isOpen={isExamModalOpen}
        onClose={() => setIsExamModalOpen(false)}
        settings={examSettings}
        onSave={handleSaveExamSettings}
        lang={lang}
      />

      <style>{`
        .student-main-content {
          flex: 1;
          padding: var(--space-6);
          max-width: 1040px;
          width: 100%;
        }
        @media (max-width: 640px) {
          .student-main-content {
            padding: var(--space-3) var(--space-3) 80px var(--space-3) !important;
          }
        }
      `}</style>
    </div>
  );
};
