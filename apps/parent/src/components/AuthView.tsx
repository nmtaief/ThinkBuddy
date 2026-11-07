import React, { useState } from "react";
import { Language, translations, signInWithGoogle, UserProfile } from "@thinkbuddy/shared";
import { ShieldCheck, Globe, Moon, Sun, AlertCircle, Loader2, ExternalLink } from "lucide-react";

interface AuthViewProps {
  lang: Language;
  onToggleLang: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onLoginSuccess: (user: UserProfile) => void;
}

export const AuthView: React.FC<AuthViewProps> = ({
  lang,
  onToggleLang,
  theme,
  onToggleTheme,
  onLoginSuccess,
}) => {
  const t = translations[lang];
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const studentUrl = import.meta.env.VITE_STUDENT_APP_URL || "http://localhost:3000";

  const handleGoogleSignIn = async () => {
    setErrorMsg(null);
    setLoading(true);

    try {
      const user = await signInWithGoogle("parent");
      onLoginSuccess(user);
    } catch (err: unknown) {
      const errCode = (err as { code?: string })?.code;
      if (errCode === "auth/popup-blocked") {
        setErrorMsg(t.auth.errorPopupBlocked);
      } else if (errCode === "auth/network-request-failed") {
        setErrorMsg(t.auth.errorNetwork);
      } else if (errCode === "auth/popup-closed-by-user") {
        setErrorMsg(t.auth.errorCancelled);
      } else {
        setErrorMsg(t.auth.errorGeneric);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: "var(--space-6)",
      }}
    >
      {/* Top Bar with Quiet link to Student app, lang, theme */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: "var(--radius-md)",
              backgroundColor: "var(--color-primary)",
              color: "#FFFFFF",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <ShieldCheck size={20} />
          </div>
          <span style={{ fontSize: "var(--text-lg)", fontWeight: 800 }}>ThinkBuddy</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
          <a
            href={studentUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="touch-target"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              fontSize: "var(--text-xs)",
              fontWeight: 600,
              color: "var(--color-text-muted)",
              textDecoration: "none",
              padding: "6px 10px",
              borderRadius: "var(--radius-md)",
              border: "1px dashed var(--color-border)",
            }}
          >
            <span>{t.app.switchToStudent}</span>
            <ExternalLink size={12} />
          </a>

          <button
            onClick={onToggleLang}
            className="btn-secondary touch-target"
            style={{ minHeight: 38, padding: "0 10px", fontSize: "var(--text-xs)", display: "flex", alignItems: "center", gap: 6 }}
          >
            <Globe size={15} />
            <span>{lang === "bn" ? "English" : "বাংলা"}</span>
          </button>

          <button
            onClick={onToggleTheme}
            className="btn-secondary touch-target"
            style={{ minHeight: 38, padding: "0 10px" }}
          >
            {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
          </button>
        </div>
      </div>

      {/* Main Login Card */}
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", margin: "auto 0" }}>
        <div
          className="card"
          style={{
            width: "100%",
            maxWidth: 440,
            padding: "var(--space-8)",
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-5)",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-2)" }}>
            <div
              style={{
                width: 56,
                height: 56,
                borderRadius: "var(--radius-xl)",
                backgroundColor: "var(--color-success-surface)",
                color: "var(--color-success)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <ShieldCheck size={32} />
            </div>
            <h1 style={{ fontSize: "var(--text-2xl)", fontWeight: 800, marginTop: "var(--space-2)", color: "var(--color-text-main)" }}>
              {t.auth.parentLoginTitle}
            </h1>
            <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.6 }}>
              {t.auth.parentLoginDesc}
            </p>
          </div>

          {errorMsg && (
            <div
              style={{
                padding: "var(--space-3) var(--space-4)",
                borderRadius: "var(--radius-md)",
                backgroundColor: "var(--color-error-surface)",
                color: "var(--color-error)",
                border: "1px solid var(--color-error)",
                fontSize: "var(--text-xs)",
                display: "flex",
                alignItems: "center",
                gap: 8,
                textAlign: "left",
              }}
            >
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{errorMsg}</span>
            </div>
          )}

          <button
            onClick={handleGoogleSignIn}
            disabled={loading}
            className="btn-primary touch-target"
            style={{
              width: "100%",
              minHeight: 48,
              fontSize: "var(--text-base)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "var(--space-3)",
              backgroundColor: "#2563EB",
            }}
          >
            {loading ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                <span>{t.app.loggingIn}</span>
              </>
            ) : (
              <>
                <svg width="20" height="20" viewBox="0 0 24 24">
                  <path
                    fill="#FFFFFF"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#FFFFFF"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FFFFFF"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                  />
                  <path
                    fill="#FFFFFF"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                  />
                </svg>
                <span>{t.auth.googleSignIn}</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Footer */}
      <footer style={{ textAlign: "center", fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
        {t.app.footerNote}
      </footer>
    </div>
  );
};

