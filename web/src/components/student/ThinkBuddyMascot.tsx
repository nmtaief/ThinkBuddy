"use client";

import React, { useEffect, useState } from "react";

/** Easy-to-change placeholder name shown under the mascot. */
export const MASCOT_NAME = "বাডি (Buddy)";

export type MascotState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "happy"
  | "confused";

export interface ThinkBuddyMascotProps {
  state: MascotState;
  /** Normalized 0..1 mouth openness driven by AnalyserNode or fallback loop */
  mouthLevel?: number;
  /** Normalized 0..1 mic volume for the listening pulse ring */
  micLevel?: number;
  /** Optional size in px (default 140) */
  size?: number;
  /** Show Bangla status caption & AI-voice disclaimer under the mascot */
  showCaption?: boolean;
  className?: string;
}

const STATE_CAPTIONS: Record<MascotState, { bn: string; bubble?: string }> = {
  idle: { bn: "প্রস্তুত আছি", bubble: "কী জানতে চাও?" },
  listening: { bn: "শুনছি..." },
  thinking: { bn: "ভাবছি..." },
  speaking: { bn: "বলছি..." },
  happy: { bn: "দারুণ!" },
  confused: { bn: "আবার বলো?" },
};

const REDUCED_MOTION_ICONS: Record<MascotState, string> = {
  idle: "😊",
  listening: "🎙️",
  thinking: "💡",
  speaking: "🔊",
  happy: "🎉",
  confused: "🤔",
};

/**
 * Isolated ThinkBuddyMascot component.
 * To swap in custom SVG, Lottie, or sprite art later, replace only the
 * `<svg>...</svg>` block inside `ThinkBuddyMascot` without touching voice logic.
 */
export function ThinkBuddyMascot({
  state,
  mouthLevel = 0,
  micLevel = 0,
  size = 140,
  showCaption = true,
  className = "",
}: ThinkBuddyMascotProps) {
  const [reducedMotion, setReducedMotion] = useState(false);
  const [tabHidden, setTabHidden] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const onMq = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener("change", onMq);

    const onVis = () => setTabHidden(document.visibilityState === "hidden");
    document.addEventListener("visibilitychange", onVis);

    return () => {
      mq.removeEventListener("change", onMq);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);

  const clampedMouth = Math.max(0, Math.min(1, mouthLevel));
  const clampedMic = Math.max(0, Math.min(1, micLevel));
  const caption = STATE_CAPTIONS[state];
  const pauseAnim = reducedMotion || tabHidden;

  // Mouth vertical radius (2px closed -> 11px wide open)
  const mouthRy = state === "speaking" ? 2 + clampedMouth * 9 : state === "happy" ? 6 : 2.5;
  const ringScale = state === "listening" && !pauseAnim ? 1 + clampedMic * 0.25 : 1;

  const headTransform =
    state === "listening"
      ? "rotate(-4deg)"
      : state === "confused"
        ? "rotate(10deg)"
        : state === "happy"
          ? "translateY(-4px)"
          : "none";

  return (
    <div
      className={`flex flex-col items-center select-none ${className}`}
      aria-label={`${MASCOT_NAME} - ${caption.bn}`}
    >
      {/* Idle Bangla greeting bubble */}
      {state === "idle" && caption.bubble && (
        <div className="mb-1.5 rounded-full bg-emerald-50 border border-emerald-200 px-3 py-0.5 text-xs font-medium text-emerald-800 shadow-sm">
          {caption.bubble}
        </div>
      )}

      {/* Mascot Artwork Container (200-300ms smooth CSS transitions) */}
      <div
        className="relative flex items-center justify-center transition-transform duration-300 ease-out"
        style={{
          width: size,
          height: size,
          transform: reducedMotion ? "none" : headTransform,
        }}
      >
        {/* Listening mic pulse ring */}
        {state === "listening" && (
          <div
            className="absolute inset-0 rounded-full bg-emerald-400/25 transition-transform duration-150"
            style={{ transform: `scale(${ringScale})` }}
          />
        )}

        {reducedMotion ? (
          /* Reduced-motion static state icon */
          <div
            className="flex items-center justify-center rounded-full bg-emerald-100 border-2 border-emerald-500 text-4xl shadow-inner"
            style={{ width: size * 0.8, height: size * 0.8 }}
            role="img"
            aria-label={caption.bn}
          >
            {REDUCED_MOTION_ICONS[state]}
          </div>
        ) : (
          /* === SWAPPABLE INLINE SVG ARTWORK === */
          <svg
            viewBox="0 0 120 120"
            width={size}
            height={size}
            className={pauseAnim ? "" : state === "idle" ? "animate-[pulse_3.5s_ease-in-out_infinite]" : ""}
          >
            {/* Thinking lightbulb accessory */}
            <g
              className="transition-opacity duration-300"
              style={{ opacity: state === "thinking" ? 1 : 0.35 }}
            >
              <circle
                cx="60"
                cy="14"
                r="7"
                fill={state === "thinking" ? "#FACC15" : "#E5E7EB"}
                stroke="#0F766E"
                strokeWidth="2"
              />
              <line x1="60" y1="21" x2="60" y2="26" stroke="#0F766E" strokeWidth="2.5" />
            </g>

            {/* Round head in ThinkBuddy brand emerald/teal */}
            <circle cx="60" cy="66" r="40" fill="#10B981" stroke="#065F46" strokeWidth="3" />
            {/* Inner face */}
            <ellipse cx="60" cy="70" rx="31" ry="26" fill="#ECFDF5" />

            {/* Eyebrows */}
            <path
              d={state === "confused" ? "M38 52 Q44 48 50 53" : "M38 52 Q44 49 50 52"}
              fill="none"
              stroke="#065F46"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
            <path
              d={state === "confused" ? "M70 50 Q76 45 82 49" : "M70 52 Q76 49 82 52"}
              fill="none"
              stroke="#065F46"
              strokeWidth="2.5"
              strokeLinecap="round"
            />

            {/* Eyes */}
            <circle
              cx="45"
              cy={state === "thinking" ? 58 : 62}
              r={state === "listening" ? 6.5 : 5.5}
              fill="#064E3B"
            />
            <circle
              cx="75"
              cy={state === "thinking" ? 58 : 62}
              r={state === "listening" ? 6.5 : 5.5}
              fill="#064E3B"
            />
            {/* Eye sparkles */}
            <circle cx="43.5" cy={state === "thinking" ? 56 : 60} r="1.8" fill="#FFFFFF" />
            <circle cx="73.5" cy={state === "thinking" ? 56 : 60} r="1.8" fill="#FFFFFF" />

            {/* Mouth */}
            {state === "happy" ? (
              <path
                d="M48 78 Q60 90 72 78"
                fill="#065F46"
                stroke="#065F46"
                strokeWidth="2.5"
                strokeLinecap="round"
              />
            ) : (
              <ellipse
                cx="60"
                cy="80"
                rx={state === "speaking" ? 8 + clampedMouth * 4 : 7}
                ry={mouthRy}
                fill="#065F46"
              />
            )}
          </svg>
        )}
      </div>

      {/* Name, Bangla Status Caption, and AI-voice label */}
      {showCaption && (
        <div className="mt-1 flex flex-col items-center text-center">
          <span className="text-xs font-semibold text-slate-800">{MASCOT_NAME}</span>
          <span className="text-xs font-medium text-emerald-700">{caption.bn}</span>
          <span className="mt-0.5 text-[10px] text-slate-400">এআই-জেনারেটেড কণ্ঠ</span>
        </div>
      )}
    </div>
  );
}

/**
 * Static, zero-animation mini avatar for normal chat answers.
 */
export function StaticMascotAvatar({ size = 28 }: { size?: number }) {
  return (
    <svg
      viewBox="0 0 120 120"
      width={size}
      height={size}
      className="shrink-0 rounded-full"
      aria-hidden="true"
    >
      <circle cx="60" cy="60" r="54" fill="#10B981" stroke="#065F46" strokeWidth="4" />
      <ellipse cx="60" cy="64" rx="40" ry="34" fill="#ECFDF5" />
      <circle cx="44" cy="56" r="6" fill="#064E3B" />
      <circle cx="76" cy="56" r="6" fill="#064E3B" />
      <path d="M48 76 Q60 85 72 76" fill="none" stroke="#065F46" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}
