"use client";

import React, { useState } from "react";
import { Language, translations } from "@/lib/i18n";
import { X, Phone, ShieldCheck, LogIn, Loader2 } from "lucide-react";
import { SessionUser } from "@/lib/types";

interface FirebaseSignInModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (user: SessionUser) => void;
  lang: Language;
}

export const FirebaseSignInModal: React.FC<FirebaseSignInModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  lang,
}) => {
  const t = translations[lang];

  const [role, setRole] = useState<"student" | "parent">("student");
  const [phoneNumber, setPhoneNumber] = useState("+8801712345678");
  const [otpCode, setOtpCode] = useState("");
  const [step, setStep] = useState<"phone" | "otp">("phone");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      // In production with Firebase SDK initialized, this triggers window.recaptchaVerifier
      // and signInWithPhoneNumber(auth, phoneNumber, window.recaptchaVerifier)
      await new Promise((res) => setTimeout(res, 600));
      setStep("otp");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to send verification code");
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      // Exchange mock or real Firebase ID token with ThinkBuddy server BFF
      const mockIdToken = "firebase_id_token_" + Buffer.from(phoneNumber + ":" + otpCode).toString("base64");
      const res = await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role,
          name: role === "parent" ? "অভিভাবক" : "শিক্ষার্থী",
          auth_provider: "firebase",
          id_token: mockIdToken,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || "Token exchange failed");
      }

      const data = await res.json();
      onSuccess(data.user);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setError(null);
    setIsLoading(true);

    try {
      // In production with Firebase SDK, signInWithPopup(auth, googleProvider)
      const mockGoogleToken = "firebase_google_id_token_" + Date.now();
      const res = await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role,
          name: role === "parent" ? "অভিভাবক (Google)" : "শিক্ষার্থী (Google)",
          auth_provider: "firebase",
          id_token: mockGoogleToken,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || "Google sign-in exchange failed");
      }

      const data = await res.json();
      onSuccess(data.user);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Google sign-in failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="firebase-modal-title"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        backgroundColor: "rgba(0, 0, 0, 0.6)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "var(--space-4)",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="card"
        style={{
          width: "100%",
          maxWidth: 440,
          backgroundColor: "var(--color-surface)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-xl)",
          padding: "var(--space-6)",
          position: "relative",
        }}
      >
        <button
          onClick={onClose}
          aria-label="Close"
          style={{
            position: "absolute",
            top: 16,
            right: 16,
            background: "none",
            border: "none",
            color: "var(--color-text-muted)",
            cursor: "pointer",
          }}
        >
          <X size={20} />
        </button>

        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", marginBottom: "var(--space-4)" }}>
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: "var(--radius-md)",
              backgroundColor: "rgba(22, 101, 52, 0.1)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--color-primary)",
            }}
          >
            <ShieldCheck size={24} />
          </div>
          <div>
            <h2 id="firebase-modal-title" style={{ fontSize: "var(--text-lg)", fontWeight: 700 }}>
              {lang === "bn" ? "নিরাপদ সাইন ইন" : "Secure Sign In"}
            </h2>
            <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              {lang === "bn"
                ? "ফোন নম্বর বা গুগল অ্যাকাউন্টের মাধ্যমে প্রবেশ করুন"
                : "Sign in with phone number OTP or Google"}
            </p>
          </div>
        </div>

        {/* Role Selection */}
        <div style={{ marginBottom: "var(--space-4)" }}>
          <label style={{ fontSize: "var(--text-xs)", fontWeight: 600, display: "block", marginBottom: 6 }}>
            {lang === "bn" ? "ব্যবহারকারীর ভূমিকা নির্বাচন করুন" : "Select User Role"}
          </label>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-2)" }}>
            <button
              type="button"
              className={role === "student" ? "btn-primary" : "btn-outline"}
              style={{ padding: "var(--space-2)", fontSize: "var(--text-sm)" }}
              onClick={() => setRole("student")}
            >
              {t.roles.student}
            </button>
            <button
              type="button"
              className={role === "parent" ? "btn-primary" : "btn-outline"}
              style={{ padding: "var(--space-2)", fontSize: "var(--text-sm)" }}
              onClick={() => setRole("parent")}
            >
              {t.roles.parent}
            </button>
          </div>
        </div>

        {error && (
          <div
            style={{
              padding: "var(--space-2) var(--space-3)",
              backgroundColor: "rgba(239, 68, 68, 0.1)",
              color: "var(--color-error)",
              borderRadius: "var(--radius-md)",
              fontSize: "var(--text-xs)",
              marginBottom: "var(--space-4)",
            }}
          >
            {error}
          </div>
        )}

        {step === "phone" ? (
          <form onSubmit={handleSendOtp} style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <div>
              <label style={{ fontSize: "var(--text-xs)", fontWeight: 600, display: "block", marginBottom: 4 }}>
                {lang === "bn" ? "মোবাইল নম্বর" : "Mobile Phone Number"}
              </label>
              <div style={{ position: "relative" }}>
                <Phone
                  size={16}
                  style={{
                    position: "absolute",
                    left: 10,
                    top: "50%",
                    transform: "translateY(-50%)",
                    color: "var(--color-text-muted)",
                  }}
                />
                <input
                  type="tel"
                  required
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  placeholder="+8801XXXXXXXXX"
                  style={{
                    width: "100%",
                    padding: "var(--space-2) var(--space-3) var(--space-2) 34px",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--color-border)",
                    backgroundColor: "var(--color-background)",
                    fontSize: "var(--text-sm)",
                  }}
                />
              </div>
            </div>

            {/* Invisible / Visible reCAPTCHA container required for Firebase Phone Auth */}
            <div id="recaptcha-container" style={{ margin: "4px 0" }} />

            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary"
              style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
            >
              {isLoading ? <Loader2 size={16} className="animate-spin" /> : <LogIn size={16} />}
              {lang === "bn" ? "ওটিপি (OTP) কোড পাঠান" : "Send Verification Code"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleVerifyOtp} style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <div>
              <label style={{ fontSize: "var(--text-xs)", fontWeight: 600, display: "block", marginBottom: 4 }}>
                {lang === "bn" ? "৬-সংখ্যার ওটিপি কোড দিন" : "Enter 6-digit OTP Code"}
              </label>
              <input
                type="text"
                required
                maxLength={6}
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value)}
                placeholder="123456"
                autoFocus
                style={{
                  width: "100%",
                  padding: "var(--space-2) var(--space-3)",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-background)",
                  fontSize: "var(--text-lg)",
                  textAlign: "center",
                  letterSpacing: 4,
                }}
              />
            </div>

            <div style={{ display: "flex", gap: "var(--space-2)" }}>
              <button
                type="button"
                className="btn-outline"
                style={{ flex: 1 }}
                onClick={() => setStep("phone")}
              >
                {lang === "bn" ? "নম্বর পরিবর্তন" : "Change Number"}
              </button>
              <button
                type="submit"
                disabled={isLoading}
                className="btn-primary"
                style={{ flex: 2, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
              >
                {isLoading ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
                {lang === "bn" ? "যাচাই ও প্রবেশ" : "Verify & Sign In"}
              </button>
            </div>
          </form>
        )}

        <div style={{ position: "relative", margin: "var(--space-4) 0", textAlign: "center" }}>
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center" }}>
            <div style={{ width: "100%", borderTop: "1px solid var(--color-border)" }} />
          </div>
          <span
            style={{
              position: "relative",
              padding: "0 var(--space-2)",
              backgroundColor: "var(--color-surface)",
              fontSize: "var(--text-xs)",
              color: "var(--color-text-muted)",
            }}
          >
            {lang === "bn" ? "অথবা" : "or"}
          </span>
        </div>

        {/* Google Sign In */}
        <button
          type="button"
          onClick={handleGoogleSignIn}
          disabled={isLoading}
          className="btn-outline"
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "var(--space-2)",
            fontSize: "var(--text-sm)",
          }}
        >
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
          {lang === "bn" ? "Google অ্যাকাউন্ট দিয়ে প্রবেশ করুন" : "Sign in with Google"}
        </button>
      </div>
    </div>
  );
};
