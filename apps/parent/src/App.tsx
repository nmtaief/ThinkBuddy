import React, { useState, useEffect } from "react";
import {
  UserProfile,
  Language,
  getPersistedUser,
  signOutUser,
} from "@thinkbuddy/shared";
import { Navbar } from "./components/Navbar";
import { AuthView } from "./components/AuthView";
import { ParentDashboard } from "./components/ParentDashboard";
import { ParentProfileDrawer } from "./components/ParentProfileDrawer";

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

  const [user, setUser] = useState<UserProfile | null>(() => getPersistedUser("parent"));
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
    await signOutUser("parent");
    setUser(null);
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

      <main className="parent-main-content">
        <ParentDashboard user={user} lang={lang} />
      </main>

      {/* Parent Profile Drawer (with hidden link to Student App) */}
      <ParentProfileDrawer
        isOpen={isProfileDrawerOpen}
        onClose={() => setIsProfileDrawerOpen(false)}
        user={user}
        lang={lang}
        onToggleLang={toggleLang}
        theme={theme}
        onToggleTheme={toggleTheme}
        onLogout={handleLogout}
      />

      <footer
        style={{
          textAlign: "center",
          padding: "var(--space-5)",
          fontSize: "var(--text-xs)",
          color: "var(--color-text-muted)",
          borderTop: "1px solid var(--color-border)",
          backgroundColor: "var(--color-surface)",
        }}
      >
        ThinkBuddy অভিভাবক পোর্টাল • জাতীয় শিক্ষাক্রম ও পাঠ্যপুস্তক বোর্ড (NCTB) শিক্ষাক্রম ভিত্তিক
      </footer>

      <style>{`
        .parent-main-content {
          flex: 1;
          max-width: 1200px;
          width: 100%;
          margin: 0 auto;
          padding: var(--space-6);
        }
        @media (max-width: 640px) {
          .parent-main-content {
            padding: var(--space-3) !important;
          }
        }
      `}</style>
    </div>
  );
};
