"use client";

import React, { useEffect, useRef, useState } from "react";
import { Language, translations } from "@/lib/i18n";
import { Loader2 } from "lucide-react";
import { SessionUser } from "@/lib/types";

interface GoogleSignInProps {
  role: "student" | "parent";
  lang: Language;
  onSuccess: (user: SessionUser) => void;
  onError?: (error: string) => void;
}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
            auto_select?: boolean;
          }) => void;
          renderButton: (
            parent: HTMLElement,
            options: {
              theme?: "outline" | "filled_blue" | "filled_black";
              size?: "large" | "medium" | "small";
              text?: "signin_with" | "signup_with" | "continue_with" | "signin";
              shape?: "rectangular" | "pill" | "circle" | "square";
              logo_alignment?: "left" | "center";
              width?: number;
              locale?: string;
            }
          ) => void;
          prompt: () => void;
        };
      };
    };
  }
}

export const GoogleSignIn: React.FC<GoogleSignInProps> = ({
  role,
  lang,
  onSuccess,
  onError,
}) => {
  const t = translations[lang];
  const [isLoading, setIsLoading] = useState(false);
  const [scriptLoaded, setScriptLoaded] = useState(false);
  const buttonRef = useRef<HTMLDivElement>(null);

  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";

  const handleCredentialResponse = async (credential: string) => {
    setIsLoading(true);
    try {
      const res = await fetch("/api/auth/google", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id_token: credential,
          role,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || "Google authentication failed");
      }

      const data = await res.json();
      if (data.authenticated && data.user) {
        onSuccess(data.user);
      } else {
        throw new Error("Invalid session response");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Authentication error";
      if (onError) onError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // If no client ID configured yet, don't load script
    if (!clientId) return;

    if (window.google?.accounts?.id) {
      setScriptLoaded(true);
      return;
    }

    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => setScriptLoaded(true);
    document.head.appendChild(script);

    return () => {
      // Cleanup script reference
    };
  }, [clientId]);

  useEffect(() => {
    if (!scriptLoaded || !clientId || !buttonRef.current || !window.google?.accounts?.id) return;

    try {
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: (response) => {
          if (response.credential) {
            handleCredentialResponse(response.credential);
          }
        },
      });

      window.google.accounts.id.renderButton(buttonRef.current, {
        theme: "outline",
        size: "large",
        text: "continue_with",
        shape: "pill",
        width: 320,
        locale: lang === "bn" ? "bn" : "en",
      });
    } catch (err) {
      console.warn("Failed to initialize Google Sign-In button:", err);
    }
  }, [scriptLoaded, clientId, lang, role]);

  // Fallback demo / mock sign-in when client ID is not yet set in environment
  const handleDevGoogleLogin = async () => {
    setIsLoading(true);
    try {
      const mockToken = `fake:google:${role}@thinkbuddy.org`;
      await handleCredentialResponse(mockToken);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Google sign-in error";
      if (onError) onError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: "100%" }}>
      {clientId && scriptLoaded ? (
        <div ref={buttonRef} style={{ minHeight: 44, display: "flex", justifyContent: "center" }} />
      ) : (
        <button
          type="button"
          onClick={handleDevGoogleLogin}
          disabled={isLoading}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "var(--space-3)",
            width: "100%",
            maxWidth: 340,
            padding: "10px 16px",
            borderRadius: "var(--radius-full)",
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
            color: "var(--color-text-primary)",
            fontSize: "var(--text-sm)",
            fontWeight: 500,
            cursor: isLoading ? "not-allowed" : "pointer",
            boxShadow: "var(--shadow-sm)",
            transition: "all 0.15s ease",
          }}
        >
          {isLoading ? (
            <Loader2 size={18} className="animate-spin" />
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              />
            </svg>
          )}
          <span>
            {lang === "bn"
              ? isLoading
                ? "যাচাই করা হচ্ছে..."
                : "গুগল দিয়ে প্রবেশ করো (Google Sign-In)"
              : isLoading
              ? "Authenticating..."
              : "Continue with Google"}
          </span>
        </button>
      )}
    </div>
  );
};
