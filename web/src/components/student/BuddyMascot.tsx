"use client";

import React from "react";

export type MascotState =
  | "idle"
  | "listening"
  | "transcribing"
  | "thinking"
  | "speaking"
  | "celebrating"
  | "confused";

interface BuddyMascotProps {
  state: MascotState;
  audioLevel?: number; // 0..1
  statusText?: string | null;
  onClick?: () => void;
  riveSrc?: string;
  size?: number;
}

export const BuddyMascot: React.FC<BuddyMascotProps> = ({
  state,
  audioLevel = 0,
  statusText,
  onClick,
  size = 54,
}) => {
  const clampedLevel = Math.max(0, Math.min(1, audioLevel));
  const beakOpen = state === "speaking" ? 4 + clampedLevel * 9 : state === "celebrating" ? 6 : 1.5;
  const haloScale = state === "listening" ? 1 + clampedLevel * 0.35 : 1;
  const tiltDeg = state === "confused" ? -10 : state === "listening" ? 4 : 0;

  return (
    <div
      style={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        gap: 10,
      }}
    >
      <style>{`
        @keyframes buddy-float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-3px); }
        }
        @keyframes buddy-bounce {
          0%, 100% { transform: translateY(0px) scale(1); }
          40% { transform: translateY(-7px) scale(1.06); }
          70% { transform: translateY(-2px) scale(0.98); }
        }
        @keyframes buddy-blink {
          0%, 92%, 100% { transform: scaleY(1); }
          96% { transform: scaleY(0.1); }
        }
        @media (prefers-reduced-motion: reduce) {
          .buddy-anim-float, .buddy-anim-bounce, .buddy-anim-blink {
            animation: none !important;
          }
        }
      `}</style>

      <button
        type="button"
        onClick={onClick}
        aria-label={`Buddy mascot (${state})`}
        title="Buddy"
        style={{
          position: "relative",
          width: size,
          height: size,
          borderRadius: "50%",
          border: "none",
          background: "transparent",
          padding: 0,
          cursor: onClick ? "pointer" : "default",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {state === "listening" && (
          <span
            style={{
              position: "absolute",
              inset: -4,
              borderRadius: "50%",
              backgroundColor: "rgba(16, 185, 129, 0.22)",
              transform: `scale(${haloScale})`,
              transition: "transform 80ms ease-out",
              pointerEvents: "none",
            }}
          />
        )}

        <svg
          width={size}
          height={size}
          viewBox="0 0 80 80"
          className={
            state === "celebrating"
              ? "buddy-anim-bounce"
              : state === "idle"
              ? "buddy-anim-float"
              : undefined
          }
          style={{
            transform: `rotate(${tiltDeg}deg)`,
            transition: "transform 180ms ease",
          }}
        >
          {/* Body */}
          <ellipse cx="40" cy="44" rx="26" ry="28" fill="#10B981" />
          <ellipse cx="40" cy="50" rx="17" ry="18" fill="#D1FAE5" />

          {/* Ear tufts */}
          <polygon points="18,22 26,12 31,24" fill="#059669" />
          <polygon points="62,22 54,12 49,24" fill="#059669" />

          {/* Eyes */}
          <g className="buddy-anim-blink" style={{ transformOrigin: "40px 33px" }}>
            <circle cx="30" cy="33" r="8.5" fill="#FFFFFF" />
            <circle cx="50" cy="33" r="8.5" fill="#FFFFFF" />
            <circle
              cx={state === "thinking" ? 32 : 30.5}
              cy={state === "thinking" ? 31.5 : 33}
              r="4.2"
              fill="#111827"
            />
            <circle
              cx={state === "thinking" ? 52 : 50.5}
              cy={state === "thinking" ? 31.5 : 33}
              r="4.2"
              fill="#111827"
            />
            <circle cx="31.8" cy="31.5" r="1.4" fill="#FFFFFF" />
            <circle cx="51.8" cy="31.5" r="1.4" fill="#FFFFFF" />
          </g>

          {/* Beak / Lip-sync mouth */}
          <polygon points="35,40 45,40 40,46" fill="#F59E0B" />
          <ellipse cx="40" cy="45" rx="4.2" ry={beakOpen / 2} fill="#B45309" />

          {/* Thinking magnifying glass */}
          {state === "thinking" && (
            <g transform="translate(52, 48)">
              <circle cx="8" cy="8" r="6" fill="#E0F2FE" stroke="#0284C7" strokeWidth="2.5" />
              <line x1="12.5" y1="12.5" x2="17" y2="17" stroke="#0284C7" strokeWidth="2.5" strokeLinecap="round" />
            </g>
          )}

          {/* Celebrating sparkles */}
          {state === "celebrating" && (
            <g fill="#FBBF24">
              <circle cx="12" cy="18" r="3" />
              <circle cx="68" cy="18" r="3" />
              <circle cx="40" cy="7" r="2.5" />
            </g>
          )}
        </svg>
      </button>

      {statusText && (
        <div
          style={{
            backgroundColor: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-md)",
            padding: "4px 10px",
            fontSize: "var(--text-xs)",
            color: "var(--color-text-secondary)",
            boxShadow: "0 2px 6px rgba(0,0,0,0.06)",
            maxWidth: 220,
          }}
        >
          {statusText}
        </div>
      )}
    </div>
  );
};
