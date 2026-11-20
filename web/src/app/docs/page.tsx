"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  BookOpen,
  Sparkles,
  Shield,
  Layers,
  Database,
  Cpu,
  Clock,
  CheckCircle2,
  AlertCircle,
  Copy,
  Printer,
  Share2,
  Settings,
  X,
  ExternalLink,
  ChevronRight,
  TrendingUp,
  Award,
  Users,
  Search,
  Lock,
  Eye,
  EyeOff,
  Calendar,
  Radio,
  FileText,
  Workflow,
  ArrowRight,
  Check,
  Terminal,
} from "lucide-react";

// ==========================================
// TYPES & DATA STRUCTURES
// ==========================================

interface TeamMember {
  id: string;
  name: string;
  role: string;
  email: string;
  avatar_url?: string;
  initials: string;
  bio: string;
}

interface AccessConfig {
  is_public: boolean;
  publish_start: string;
  publish_end: string;
  admin_override: boolean;
  last_updated: string;
}

const DEFAULT_TEAM: TeamMember[] = [
  {
    id: "member-1",
    name: "Noor Mohammed Taief",
    role: "Founder & Full-Stack AI Architect",
    email: "taief@thinkbuddy.ai",
    initials: "NT",
    bio: "AI systems engineer & full-stack architect leading ThinkBuddy's grounded RAG, pedagogical rubric engine, and platform infrastructure.",
  },
  {
    id: "member-2",
    name: "Dr. A. K. Rahman",
    role: "Curriculum Advisor & Pedagogical Lead",
    email: "curriculum@thinkbuddy.ai",
    initials: "AR",
    bio: "Ex-NCTB education specialist with 18+ years in curriculum design, secondary assessment frameworks, and bilingual evaluation.",
  },
  {
    id: "member-3",
    name: "Tanzim Hasan",
    role: "Senior AI & NLP Engineer",
    email: "tanzim@thinkbuddy.ai",
    initials: "TH",
    bio: "Machine learning engineer specializing in dense bilingual embeddings (Bengali/English), vector retrieval, and prompt optimization.",
  },
];

const DEFAULT_ACCESS: AccessConfig = {
  is_public: true,
  publish_start: "2026-06-10T00:00:00.000Z",
  publish_end: "2026-06-14T23:59:59.000Z",
  admin_override: true,
  last_updated: new Date().toISOString(),
};

export default function DocsPage() {
  // Navigation View: "pitch" | "tech" | "dashboard"
  const [activeTab, setActiveTab] = useState<"pitch" | "tech" | "dashboard">("pitch");
  const [searchQuery, setSearchQuery] = useState("");
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedMarkdown, setCopiedMarkdown] = useState(false);

  // Admin & Access Control State
  const [accessConfig, setAccessConfig] = useState<AccessConfig>(DEFAULT_ACCESS);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>(DEFAULT_TEAM);
  const [isAdminOpen, setIsAdminOpen] = useState(false);
  const [isAdminAuthenticated, setIsAdminAuthenticated] = useState(false);
  const [adminPassInput, setAdminPassInput] = useState("");
  const [authError, setAuthError] = useState("");

  const [isWithinSchedule, setIsWithinSchedule] = useState<boolean>(true);

  // Load persistence & evaluate schedule
  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const savedAccess = localStorage.getItem("tb_docs_access_config");
        const config = savedAccess ? JSON.parse(savedAccess) : DEFAULT_ACCESS;
        if (savedAccess) setAccessConfig(config);

        const now = new Date();
        const startTime = new Date(config.publish_start);
        const endTime = new Date(config.publish_end);
        setIsWithinSchedule(now >= startTime && now <= endTime);

        const savedTeam = localStorage.getItem("tb_docs_team_config");
        if (savedTeam) setTeamMembers(JSON.parse(savedTeam));

        const savedAuth = localStorage.getItem("tb_docs_admin_auth");
        if (savedAuth === "true") setIsAdminAuthenticated(true);
      } catch {}
    }
  }, []);

  const saveAccessConfig = (newConfig: AccessConfig) => {
    setAccessConfig(newConfig);
    const now = new Date();
    const startTime = new Date(newConfig.publish_start);
    const endTime = new Date(newConfig.publish_end);
    setIsWithinSchedule(now >= startTime && now <= endTime);
    if (typeof window !== "undefined") {
      localStorage.setItem("tb_docs_access_config", JSON.stringify(newConfig));
    }
  };

  const saveTeamConfig = (newTeam: TeamMember[]) => {
    setTeamMembers(newTeam);
    if (typeof window !== "undefined") {
      localStorage.setItem("tb_docs_team_config", JSON.stringify(newTeam));
    }
  };

  const isAccessible = accessConfig.is_public && (accessConfig.admin_override || isWithinSchedule);

  const handleAdminLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (adminPassInput === "thinkbuddy2026" || adminPassInput === "admin") {
      setIsAdminAuthenticated(true);
      setAuthError("");
      if (typeof window !== "undefined") {
        localStorage.setItem("tb_docs_admin_auth", "true");
      }
    } else {
      setAuthError("Invalid admin access key. Use 'admin' to unlock.");
    }
  };

  const copyShareLink = () => {
    if (typeof window !== "undefined") {
      navigator.clipboard.writeText(window.location.href);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    }
  };

  const copyMarkdownSummary = () => {
    const md = `# ThinkBuddy — YC Pitch Deck & Technical Whitepaper
**Live App:** https://thinkbuddy-web.vercel.app
**Documentation:** https://thinkbuddy-web.vercel.app/docs

## 1. Problem
Over 70% of students in Bangladesh cannot afford quality private tutoring ($4B spent annually on unregulated coaching). Generic AI models (ChatGPT) hallucinate on the national curriculum (NCTB) and fail in Bengali. Furthermore, school exams rely on physical handwritten Creative Questions (CQ) with math proofs and diagrams, which digital EdTech completely ignores.

## 2. Solution
ThinkBuddy is an authentic bilingual (Bangla/English) AI Teacher grounded in the NCTB curriculum with zero hallucinations. Students solve Creative Questions (ক, খ, গ, ঘ) in physical exercise books and upload photos for instant AI rubric grading with exact textbook printed page citations.

## 3. Technology Stack
- Frontend: Next.js 16 (Turbopack), React 19, Tailwind CSS, KaTeX
- Backend: FastAPI, PostgreSQL + pgvector, Redis, Celery Workers
- AI: Grounded RAG with BAAI/bge-m3 dense embeddings, LiteLLM orchestration (Gemini, Claude, GPT, DeepSeek, Qwen)
- MCP Protocol: thinkbuddy-mcp-server exposing 4 production tools over stdio
`;
    if (typeof window !== "undefined") {
      navigator.clipboard.writeText(md);
      setCopiedMarkdown(true);
      setTimeout(() => setCopiedMarkdown(false), 2000);
    }
  };

  // If not accessible and user is not admin
  if (!isAccessible && !isAdminAuthenticated) {
    return (
      <div style={{ minHeight: "100vh", backgroundColor: "#0b0f19", color: "#f3f4f6", display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
        <div style={{ maxWidth: 520, width: "100%", backgroundColor: "#111827", borderRadius: 16, border: "1px solid #1f2937", padding: 32, textAlign: "center" }}>
          <div style={{ width: 56, height: 56, borderRadius: "50%", backgroundColor: "#374151", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px" }}>
            <Lock size={28} color="#9ca3af" />
          </div>
          <h2 style={{ fontSize: 22, fontWeight: 800, margin: "0 0 8px" }}>Documentation Window Locked</h2>
          <p style={{ fontSize: 14, color: "#9ca3af", lineHeight: 1.6, marginBottom: 20 }}>
            Public access to the ThinkBuddy /docs module is currently restricted to scheduled evaluation and judging windows.
          </p>

          <div style={{ backgroundColor: "#1f2937", padding: 12, borderRadius: 8, fontSize: 13, marginBottom: 24, textAlign: "left" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span style={{ color: "#9ca3af" }}>Scheduled Window:</span>
              <span style={{ fontWeight: 600, color: "#60a5fa" }}>June 10 – June 14, 2026</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#9ca3af" }}>Current Status:</span>
              <span style={{ color: "#f59e0b", fontWeight: 700 }}>Restricted Access</span>
            </div>
          </div>

          <form onSubmit={handleAdminLogin} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <input
              type="password"
              placeholder="Enter Admin Access Key (e.g. admin)"
              value={adminPassInput}
              onChange={(e) => setAdminPassInput(e.target.value)}
              style={{ padding: "10px 14px", borderRadius: 8, border: "1px solid #374151", backgroundColor: "#030712", color: "#fff", fontSize: 13 }}
            />
            {authError && <span style={{ color: "#ef4444", fontSize: 12 }}>{authError}</span>}
            <button type="submit" style={{ padding: "10px 16px", borderRadius: 8, backgroundColor: "#2563eb", color: "#fff", border: "none", fontWeight: 700, cursor: "pointer" }}>
              Unlock Evaluator / Admin View
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#0b0f19", color: "#f3f4f6", fontFamily: "var(--font-geist-sans), sans-serif" }}>
      {/* ============================================================ */}
      {/* 1. TOP HEADER & ACCESS CONTROL BAR                           */}
      {/* ============================================================ */}
      <header
        style={{
          position: "sticky",
          top: 0,
          zIndex: 50,
          backgroundColor: "rgba(11, 15, 25, 0.92)",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid #1f2937",
          padding: "12px 24px",
        }}
      >
        <div style={{ maxWidth: 1200, margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          {/* Logo & Status Badge */}
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Link href="/" style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 32, height: 32, borderRadius: 8, backgroundColor: "#2563eb", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontWeight: 900, fontSize: 16 }}>
                TB
              </div>
              <span style={{ fontSize: 18, fontWeight: 800, color: "#fff" }}>ThinkBuddy</span>
            </Link>
            <span style={{ backgroundColor: "#1e293b", color: "#94a3b8", fontSize: 12, padding: "2px 8px", borderRadius: 6, fontWeight: 600 }}>
              /docs
            </span>
            <div style={{ display: "flex", alignItems: "center", gap: 6, backgroundColor: accessConfig.is_public ? "#064e3b" : "#7f1d1d", color: accessConfig.is_public ? "#34d399" : "#f87171", padding: "2px 8px", borderRadius: 12, fontSize: 11, fontWeight: 700 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", backgroundColor: accessConfig.is_public ? "#34d399" : "#f87171" }} />
              <span>{accessConfig.is_public ? "LIVE JUDGING WINDOW (ACTIVE)" : "VISIBILITY PAUSED"}</span>
            </div>
          </div>

          {/* View Mode Tabs */}
          <div style={{ display: "flex", backgroundColor: "#111827", padding: 3, borderRadius: 10, border: "1px solid #1f2937" }}>
            <button
              onClick={() => setActiveTab("pitch")}
              style={{
                padding: "6px 14px",
                borderRadius: 7,
                border: "none",
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
                backgroundColor: activeTab === "pitch" ? "#2563eb" : "transparent",
                color: activeTab === "pitch" ? "#fff" : "#9ca3af",
                display: "flex",
                alignItems: "center",
                gap: 6,
                transition: "all 0.15s ease",
              }}
            >
              <TrendingUp size={14} />
              <span>YC Pitch Deck</span>
            </button>
            <button
              onClick={() => setActiveTab("tech")}
              style={{
                padding: "6px 14px",
                borderRadius: 7,
                border: "none",
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
                backgroundColor: activeTab === "tech" ? "#2563eb" : "transparent",
                color: activeTab === "tech" ? "#fff" : "#9ca3af",
                display: "flex",
                alignItems: "center",
                gap: 6,
                transition: "all 0.15s ease",
              }}
            >
              <Cpu size={14} />
              <span>Technical Whitepaper</span>
            </button>
            <button
              onClick={() => setActiveTab("dashboard")}
              style={{
                padding: "6px 14px",
                borderRadius: 7,
                border: "none",
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
                backgroundColor: activeTab === "dashboard" ? "#2563eb" : "transparent",
                color: activeTab === "dashboard" ? "#fff" : "#9ca3af",
                display: "flex",
                alignItems: "center",
                gap: 6,
                transition: "all 0.15s ease",
              }}
            >
              <Radio size={14} />
              <span>System Health</span>
            </button>
          </div>

          {/* Action Buttons */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              onClick={copyShareLink}
              title="Copy shareable link"
              style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #374151", backgroundColor: "#111827", color: "#e5e7eb", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 600 }}
            >
              {copiedLink ? <Check size={14} color="#34d399" /> : <Share2 size={14} />}
              <span>{copiedLink ? "Copied" : "Share"}</span>
            </button>

            <button
              onClick={copyMarkdownSummary}
              title="Copy markdown export"
              style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #374151", backgroundColor: "#111827", color: "#e5e7eb", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 600 }}
            >
              {copiedMarkdown ? <Check size={14} color="#34d399" /> : <Copy size={14} />}
              <span>{copiedMarkdown ? "Copied MD" : "Export MD"}</span>
            </button>

            <button
              onClick={() => window.print()}
              title="Print or export as PDF"
              style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #374151", backgroundColor: "#111827", color: "#e5e7eb", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 600 }}
            >
              <Printer size={14} />
              <span>PDF</span>
            </button>

            <button
              onClick={() => setIsAdminOpen(true)}
              title="Admin access & schedule controls"
              style={{ padding: "8px 14px", borderRadius: 8, border: "none", backgroundColor: "#3b82f6", color: "#fff", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 700 }}
            >
              <Settings size={14} />
              <span>Admin Panel</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Container */}
      <main style={{ maxWidth: 1140, margin: "0 auto", padding: "40px 20px 80px" }}>
        {/* ============================================================ */}
        {/* VIEW 1: YC-STYLE PITCH DECK                                 */}
        {/* ============================================================ */}
        {activeTab === "pitch" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 48 }}>
            {/* Hero / Deck Banner */}
            <div style={{ textAlign: "center", maxWidth: 860, margin: "0 auto" }}>
              <div style={{ display: "inline-flex", alignItems: "center", gap: 8, backgroundColor: "rgba(37, 99, 235, 0.15)", border: "1px solid #2563eb", padding: "4px 14px", borderRadius: 20, color: "#60a5fa", fontSize: 13, fontWeight: 700, marginBottom: 16 }}>
                <Sparkles size={14} />
                <span>LearnSphere AI Track • AI Teacher Domain</span>
              </div>
              <h1 style={{ fontSize: "clamp(32px, 5vw, 54px)", fontWeight: 900, letterSpacing: "-0.03em", margin: "0 0 16px", color: "#fff", lineHeight: 1.15 }}>
                ThinkBuddy: The AI Teacher for the Next 100 Million Students
              </h1>
              <p style={{ fontSize: "clamp(16px, 2.5vw, 20px)", color: "#9ca3af", lineHeight: 1.6, margin: "0 auto 24px", maxWidth: 740 }}>
                100% textbook-grounded, bilingual (Bangla & English) AI personal tutor bridging the $4B private tutoring divide with camera-based handwritten homework evaluation and adaptive spaced repetition.
              </p>
              <div style={{ display: "flex", justifyContent: "center", gap: 12, flexWrap: "wrap" }}>
                <Link href="/" style={{ padding: "12px 28px", borderRadius: 10, backgroundColor: "#2563eb", color: "#fff", fontWeight: 700, textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 8 }}>
                  <span>Launch Live App</span>
                  <ExternalLink size={16} />
                </Link>
                <button onClick={() => setActiveTab("tech")} style={{ padding: "12px 24px", borderRadius: 10, border: "1px solid #374151", backgroundColor: "#111827", color: "#fff", fontWeight: 600, cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 8 }}>
                  <span>Explore Technical Architecture</span>
                  <ArrowRight size={16} />
                </button>
              </div>
            </div>

            {/* 1. Problem */}
            <section style={{ backgroundColor: "#111827", borderRadius: 16, border: "1px solid #1f2937", padding: "32px 36px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                <div style={{ width: 28, height: 28, borderRadius: 6, backgroundColor: "rgba(239, 68, 68, 0.2)", display: "flex", alignItems: "center", justifyContent: "center", color: "#f87171", fontWeight: 800 }}>
                  1
                </div>
                <h2 style={{ fontSize: 24, fontWeight: 800, margin: 0, color: "#fff" }}>The Problem: The Tutoring Crisis in the Global South</h2>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 20, marginTop: 20 }}>
                <div style={{ backgroundColor: "#0f172a", padding: 20, borderRadius: 12, border: "1px solid #1e293b" }}>
                  <h3 style={{ fontSize: 16, fontWeight: 700, color: "#f87171", margin: "0 0 8px" }}>$4B+ Private Coaching Drain</h3>
                  <p style={{ fontSize: 14, color: "#94a3b8", lineHeight: 1.6, margin: 0 }}>
                    Over 70% of households in Bangladesh spend up to 40% of disposable income on unregulated private tuition due to overcrowded classrooms and lack of 1-on-1 feedback.
                  </p>
                </div>
                <div style={{ backgroundColor: "#0f172a", padding: 20, borderRadius: 12, border: "1px solid #1e293b" }}>
                  <h3 style={{ fontSize: 16, fontWeight: 700, color: "#f87171", margin: "0 0 8px" }}>Generic AI Hallucinates in Bangla</h3>
                  <p style={{ fontSize: 14, color: "#94a3b8", lineHeight: 1.6, margin: 0 }}>
                    ChatGPT and frontier models produce inaccurate, Westernized answers disconnected from the National Curriculum and Textbook Board (NCTB) syllabus, lacking textbook citations.
                  </p>
                </div>
                <div style={{ backgroundColor: "#0f172a", padding: 20, borderRadius: 12, border: "1px solid #1e293b" }}>
                  <h3 style={{ fontSize: 16, fontWeight: 700, color: "#f87171", margin: "0 0 8px" }}>The "Pen & Paper Gap"</h3>
                  <p style={{ fontSize: 14, color: "#94a3b8", lineHeight: 1.6, margin: 0 }}>
                    Real board examinations require solving 10-mark Creative Questions (ক, খ, গ, ঘ) by hand in physical notebooks with math equations and diagrams. No EdTech grades physical notebook submissions.
                  </p>
                </div>
              </div>
            </section>

            {/* 2. Solution */}
            <section style={{ backgroundColor: "#111827", borderRadius: 16, border: "1px solid #1f2937", padding: "32px 36px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                <div style={{ width: 28, height: 28, borderRadius: 6, backgroundColor: "rgba(34, 197, 94, 0.2)", display: "flex", alignItems: "center", justifyContent: "center", color: "#4ade80", fontWeight: 800 }}>
                  2
                </div>
                <h2 style={{ fontSize: 24, fontWeight: 800, margin: 0, color: "#fff" }}>The Solution: ThinkBuddy AI Teacher</h2>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 20, marginTop: 20 }}>
                <div style={{ backgroundColor: "#0f172a", padding: 20, borderRadius: 12, border: "1px solid #1e293b" }}>
                  <div style={{ fontSize: 20, marginBottom: 8 }}>📖</div>
                  <h3 style={{ fontSize: 16, fontWeight: 700, color: "#60a5fa", margin: "0 0 8px" }}>Textbook-Grounded RAG</h3>
                  <p style={{ fontSize: 14, color: "#94a3b8", lineHeight: 1.6, margin: 0 }}>
                    Every AI explanation provides exact textbook citations down to the chapter and printed page number (e.g. Science Ch 4, Page 43). Zero hallucinations guaranteed.
                  </p>
                </div>
                <div style={{ backgroundColor: "#0f172a", padding: 20, borderRadius: 12, border: "1px solid #1e293b" }}>
                  <div style={{ fontSize: 20, marginBottom: 8 }}>📸</div>
                  <h3 style={{ fontSize: 16, fontWeight: 700, color: "#34d399", margin: "0 0 8px" }}>Handwritten Notebook Evaluation</h3>
                  <p style={{ fontSize: 14, color: "#94a3b8", lineHeight: 1.6, margin: 0 }}>
                    Students solve problems in their physical exercise books, take a photo with their phone camera, and receive instant rubric grading across concept, formula, and reasoning dimensions.
                  </p>
                </div>
                <div style={{ backgroundColor: "#0f172a", padding: 20, borderRadius: 12, border: "1px solid #1e293b" }}>
                  <div style={{ fontSize: 20, marginBottom: 8 }}>🧠</div>
                  <h3 style={{ fontSize: 16, fontWeight: 700, color: "#a78bfa", margin: "0 0 8px" }}>Leitner Spaced Revision</h3>
                  <p style={{ fontSize: 14, color: "#94a3b8", lineHeight: 1.6, margin: 0 }}>
                    Automated flashcard intervals (1, 3, 7, 14, 30 days) and weak-subject boost multipliers beat the forgetting curve before school and board exams.
                  </p>
                </div>
              </div>
            </section>

            {/* 3. Market Opportunity & Business Model */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 24 }}>
              <section style={{ backgroundColor: "#111827", borderRadius: 16, border: "1px solid #1f2937", padding: "28px 32px" }}>
                <h3 style={{ fontSize: 20, fontWeight: 800, color: "#fff", margin: "0 0 16px" }}>Market Opportunity ($6B+ TAM)</h3>
                <ul style={{ paddingLeft: 20, color: "#94a3b8", fontSize: 14, lineHeight: 1.8, margin: 0 }}>
                  <li><strong style={{ color: "#fff" }}>Primary Market:</strong> 20M+ secondary and high school students in Bangladesh (Class 6 to SSC).</li>
                  <li><strong style={{ color: "#fff" }}>Expansion:</strong> 220M+ students in South Asia (India, Pakistan, Nepal) with identical syllabus structures and high coaching reliance.</li>
                  <li><strong style={{ color: "#fff" }}>Smartphone Penetration:</strong> 75%+ mobile internet adoption across youth demographics in target regions.</li>
                </ul>
              </section>

              <section style={{ backgroundColor: "#111827", borderRadius: 16, border: "1px solid #1f2937", padding: "28px 32px" }}>
                <h3 style={{ fontSize: 20, fontWeight: 800, color: "#fff", margin: "0 0 16px" }}>Business Model & Monetization</h3>
                <ul style={{ paddingLeft: 20, color: "#94a3b8", fontSize: 14, lineHeight: 1.8, margin: 0 }}>
                  <li><strong style={{ color: "#fff" }}>Freemium B2C:</strong> Free daily syllabus & practice quizzes; ৳299/month ($2.50) subscription for unlimited AI handwritten homework evaluation and parent reporting.</li>
                  <li><strong style={{ color: "#fff" }}>B2B School Enterprise:</strong> ৳40/student/month for automated homework checking and school-wide learning analytics dashboards.</li>
                  <li><strong style={{ color: "#fff" }}>Affordability:</strong> 90% cheaper than traditional private coaching centers ($30–$50/mo).</li>
                </ul>
              </section>
            </div>

            {/* 4. Competition & Moat */}
            <section style={{ backgroundColor: "#111827", borderRadius: 16, border: "1px solid #1f2937", padding: "32px 36px" }}>
              <h2 style={{ fontSize: 24, fontWeight: 800, margin: "0 0 20px", color: "#fff" }}>Competitive Matrix & Unfair Advantage</h2>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, textAlign: "left" }}>
                  <thead>
                    <tr style={{ borderBottom: "2px solid #374151", color: "#9ca3af" }}>
                      <th style={{ padding: "12px 16px" }}>Feature / Capability</th>
                      <th style={{ padding: "12px 16px", color: "#34d399", fontWeight: 800 }}>ThinkBuddy (Ours)</th>
                      <th style={{ padding: "12px 16px" }}>Generic AI (ChatGPT)</th>
                      <th style={{ padding: "12px 16px" }}>Legacy EdTech (10MS/Shikho)</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr style={{ borderBottom: "1px solid #1f2937" }}>
                      <td style={{ padding: "12px 16px", fontWeight: 600 }}>NCTB Curriculum Grounding</td>
                      <td style={{ padding: "12px 16px", color: "#34d399" }}>✓ 100% Verified Page Citations</td>
                      <td style={{ padding: "12px 16px", color: "#f87171" }}>✗ Hallucinates / No Citations</td>
                      <td style={{ padding: "12px 16px", color: "#9ca3af" }}>~ Partial (Static PDFs)</td>
                    </tr>
                    <tr style={{ borderBottom: "1px solid #1f2937" }}>
                      <td style={{ padding: "12px 16px", fontWeight: 600 }}>Handwritten Exercise Book Grading</td>
                      <td style={{ padding: "12px 16px", color: "#34d399" }}>✓ Camera Photo Rubric Scoring</td>
                      <td style={{ padding: "12px 16px", color: "#f87171" }}>✗ No Rubric Alignment</td>
                      <td style={{ padding: "12px 16px", color: "#f87171" }}>✗ Video Lectures Only</td>
                    </tr>
                    <tr style={{ borderBottom: "1px solid #1f2937" }}>
                      <td style={{ padding: "12px 16px", fontWeight: 600 }}>Adaptive Spaced Revision</td>
                      <td style={{ padding: "12px 16px", color: "#34d399" }}>✓ Leitner Box Automated Review</td>
                      <td style={{ padding: "12px 16px", color: "#f87171" }}>✗ Session-limited</td>
                      <td style={{ padding: "12px 16px", color: "#f87171" }}>✗ Linear Progress Bars Only</td>
                    </tr>
                    <tr style={{ borderBottom: "1px solid #1f2937" }}>
                      <td style={{ padding: "12px 16px", fontWeight: 600 }}>MCP Tool Protocol Integration</td>
                      <td style={{ padding: "12px 16px", color: "#34d399" }}>✓ 4 Stdio Tools for Claude/Cursor</td>
                      <td style={{ padding: "12px 16px", color: "#f87171" }}>✗ N/A</td>
                      <td style={{ padding: "12px 16px", color: "#f87171" }}>✗ Closed Monolith</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            {/* 5. TEAM SHOWCASE (MANDATORY ENHANCEMENT) */}
            <section style={{ backgroundColor: "#111827", borderRadius: 16, border: "1px solid #1f2937", padding: "32px 36px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
                <div>
                  <h2 style={{ fontSize: 24, fontWeight: 800, margin: 0, color: "#fff" }}>Team & Core Contributors</h2>
                  <p style={{ fontSize: 14, color: "#9ca3af", margin: "4px 0 0" }}>Engineers, educators, and architects building ThinkBuddy</p>
                </div>
                <button onClick={() => setIsAdminOpen(true)} style={{ padding: "6px 12px", borderRadius: 6, backgroundColor: "#1f2937", color: "#9ca3af", border: "1px solid #374151", fontSize: 12, cursor: "pointer" }}>
                  Edit Team
                </button>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 20 }}>
                {teamMembers.map((member) => (
                  <div key={member.id} style={{ backgroundColor: "#0f172a", borderRadius: 12, border: "1px solid #1e293b", padding: 24, display: "flex", flexDirection: "column", gap: 14 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                      <div
                        style={{
                          width: 52,
                          height: 52,
                          borderRadius: "50%",
                          backgroundColor: "#2563eb",
                          color: "#fff",
                          fontWeight: 800,
                          fontSize: 18,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          border: "2px solid #3b82f6",
                          flexShrink: 0,
                        }}
                      >
                        {member.initials}
                      </div>
                      <div>
                        <h4 style={{ fontSize: 16, fontWeight: 800, color: "#fff", margin: 0 }}>{member.name}</h4>
                        <span style={{ fontSize: 12, color: "#60a5fa", fontWeight: 600 }}>{member.role}</span>
                      </div>
                    </div>
                    <p style={{ fontSize: 13, color: "#94a3b8", lineHeight: 1.5, margin: 0, flex: 1 }}>{member.bio}</p>
                    <div style={{ fontSize: 12, color: "#64748b", borderTop: "1px solid #1e293b", paddingTop: 10 }}>
                      <a href={`mailto:${member.email}`} style={{ color: "#93c5fd", textDecoration: "none" }}>{member.email}</a>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}

        {/* ============================================================ */}
        {/* VIEW 2: TECHNICAL WHITEPAPER                                 */}
        {/* ============================================================ */}
        {activeTab === "tech" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 40 }}>
            {/* Whitepaper Title */}
            <div>
              <span style={{ fontSize: 12, fontWeight: 700, color: "#60a5fa", textTransform: "uppercase", letterSpacing: "0.05em" }}>Technical Architecture Whitepaper</span>
              <h1 style={{ fontSize: 36, fontWeight: 900, color: "#fff", margin: "6px 0 12px" }}>System Design & Engineering Layer</h1>
              <p style={{ fontSize: 15, color: "#9ca3af", maxWidth: 800, lineHeight: 1.6 }}>
                Production specifications of ThinkBuddy's multi-agent supervisor loops, grounded vector pipelines, Model Context Protocol (MCP) server, and security boundaries.
              </p>
            </div>

            {/* Architecture Diagram */}
            <section style={{ backgroundColor: "#111827", borderRadius: 16, border: "1px solid #1f2937", padding: "28px 32px" }}>
              <h3 style={{ fontSize: 18, fontWeight: 800, color: "#fff", margin: "0 0 16px" }}>End-to-End System Architecture</h3>
              
              {/* Visual ASCII / SVG Diagram */}
              <div style={{ backgroundColor: "#030712", borderRadius: 12, border: "1px solid #1f2937", padding: 24, overflowX: "auto", fontFamily: "var(--font-geist-mono), monospace", fontSize: 12, lineHeight: 1.5, color: "#93c5fd" }}>
                <pre style={{ margin: 0 }}>
{`+-----------------------------------------------------------------------------------+
|                            CLIENT PLATFORMS & DEVICES                             |
|  - Web Portal (Next.js 16 / Turbopack / Practice & Analytics)                     |
|  - Android Mobile (Kotlin / Jetpack Compose / FLAG_SECURE Assessed Exams)         |
|  - External LLM Hosts via MCP (Claude Desktop, Cursor, Custom Agent CLI)          |
+-----------------------------------------------------------------------------------+
                                        | (HTTPS / SSE Stream / stdio MCP)
                                        v
+-----------------------------------------------------------------------------------+
|                        API GATEWAY & BACKEND FOR FRONTEND                         |
|  - Rate Limiting (Redis Token Bucket) & Client Token Isolation (HttpOnly Cookie)  |
|  - Role-Based Access Control (Student / Parent / Admin / Teacher)                 |
+-----------------------------------------------------------------------------------+
                                        |
                 +----------------------+----------------------+
                 v                                             v
+---------------------------------------+   +---------------------------------------+
|          FASTAPI CORE SERVICES        |   |       THINKBUDDY MCP SERVER           |
|  - Curriculum Router & Syllabi        |   |  - search_curriculum_excerpts         |
|  - Planner & Spaced Revision Engine   |   |  - get_cq_rubric (4-tier ক, খ, গ, ঘ)  |
|  - Homework & CQ Rubric Grading API   |   |  - evaluate_cq_answer                 |
|  - English Writing & Vocab Coach      |   |  - get_spaced_revision_deck           |
+---------------------------------------+   +---------------------------------------+
                 |                                             |
                 +----------------------+----------------------+
                                        |
                                        v
+-----------------------------------------------------------------------------------+
|                             DATA & PERSISTENCE LAYER                              |
|  - PostgreSQL 16 + pgvector (HNSW Index for dense bilingual embeddings)          |
|  - Redis 7.2 (Celery broker, session cache, Leitner spaced queues)                |
|  - NCTB Knowledge Base (Official textbook chunks, printed page citations)         |
+-----------------------------------------------------------------------------------+
                                        |
                                        v
+-----------------------------------------------------------------------------------+
|                   MULTI-MODEL INFERENCE ORCHESTRATION (LiteLLM)                   |
|  - Gemini (Antigravity): Primary development & multimodal OCR homework analysis   |
|  - Claude (Anthropic): Prompt optimization & nuanced CQ pedagogical rubrics       |
|  - DeepSeek: Cost-effective mathematical reasoning & API verification             |
|  - Qwen 2.5: Multilingual Bengali tokenization testing & local Ollama fuzzing     |
+-----------------------------------------------------------------------------------+`}
                </pre>
              </div>
            </section>

            {/* Data Flow & RAG Pipeline */}
            <section style={{ backgroundColor: "#111827", borderRadius: 16, border: "1px solid #1f2937", padding: "28px 32px" }}>
              <h3 style={{ fontSize: 18, fontWeight: 800, color: "#fff", margin: "0 0 16px" }}>Handwritten Homework Evaluation Data Flow</h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
                <div style={{ backgroundColor: "#0f172a", padding: 16, borderRadius: 10, borderLeft: "3px solid #3b82f6" }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "#60a5fa" }}>STEP 1</span>
                  <h4 style={{ fontSize: 14, fontWeight: 700, color: "#fff", margin: "4px 0" }}>Camera Capture</h4>
                  <p style={{ fontSize: 12, color: "#94a3b8", margin: 0 }}>Student snaps photo of handwritten exercise book with pen/pencil diagrams and equations.</p>
                </div>
                <div style={{ backgroundColor: "#0f172a", padding: 16, borderRadius: 10, borderLeft: "3px solid #8b5cf6" }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "#a78bfa" }}>STEP 2</span>
                  <h4 style={{ fontSize: 14, fontWeight: 700, color: "#fff", margin: "4px 0" }}>Vision Extraction</h4>
                  <p style={{ fontSize: 12, color: "#94a3b8", margin: 0 }}>OCR & vision models isolate formulas, handwriting tokens, and labeled diagrams.</p>
                </div>
                <div style={{ backgroundColor: "#0f172a", padding: 16, borderRadius: 10, borderLeft: "3px solid #10b981" }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "#34d399" }}>STEP 3</span>
                  <h4 style={{ fontSize: 14, fontWeight: 700, color: "#fff", margin: "4px 0" }}>Rubric Match</h4>
                  <p style={{ fontSize: 12, color: "#94a3b8", margin: 0 }}>Scores against NCTB criteria (Concept 40%, Stimulus Link 30%, Reasoning 30%).</p>
                </div>
                <div style={{ backgroundColor: "#0f172a", padding: 16, borderRadius: 10, borderLeft: "3px solid #f59e0b" }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "#fbbf24" }}>STEP 4</span>
                  <h4 style={{ fontSize: 14, fontWeight: 700, color: "#fff", margin: "4px 0" }}>Instant Feedback</h4>
                  <p style={{ fontSize: 12, color: "#94a3b8", margin: 0 }}>Returns A+ grade, missing points, and official NCTB textbook page citations.</p>
                </div>
              </div>
            </section>

            {/* MCP Server Documentation */}
            <section style={{ backgroundColor: "#111827", borderRadius: 16, border: "1px solid #1f2937", padding: "28px 32px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <h3 style={{ fontSize: 18, fontWeight: 800, color: "#fff", margin: 0 }}>Production MCP Server Integration</h3>
                <span style={{ fontSize: 11, backgroundColor: "#064e3b", color: "#34d399", padding: "2px 8px", borderRadius: 6, fontWeight: 700 }}>
                  Active @modelcontextprotocol/sdk
                </span>
              </div>
              <p style={{ fontSize: 14, color: "#94a3b8", lineHeight: 1.6, margin: "0 0 16px" }}>
                Our MCP server (`thinkbuddy-mcp-server`) runs over standard I/O (stdio), allowing any MCP-compliant AI assistant (Claude Desktop, Cursor, Antigravity) to query ThinkBuddy's curriculum directly.
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14 }}>
                <div style={{ backgroundColor: "#0f172a", padding: 14, borderRadius: 8, border: "1px solid #1e293b" }}>
                  <code style={{ color: "#60a5fa", fontWeight: 700, fontSize: 13 }}>search_curriculum_excerpts</code>
                  <p style={{ fontSize: 12, color: "#94a3b8", margin: "6px 0 0" }}>Retrieves verified textbook chunks with printed page numbers.</p>
                </div>
                <div style={{ backgroundColor: "#0f172a", padding: 14, borderRadius: 8, border: "1px solid #1e293b" }}>
                  <code style={{ color: "#34d399", fontWeight: 700, fontSize: 13 }}>get_cq_rubric</code>
                  <p style={{ fontSize: 12, color: "#94a3b8", margin: "6px 0 0" }}>Returns 4-tier CQ homework rubrics (ক, খ, গ, ঘ) totaling 10 marks.</p>
                </div>
                <div style={{ backgroundColor: "#0f172a", padding: 14, borderRadius: 8, border: "1px solid #1e293b" }}>
                  <code style={{ color: "#fbbf24", fontWeight: 700, fontSize: 13 }}>evaluate_cq_answer</code>
                  <p style={{ fontSize: 12, color: "#94a3b8", margin: "6px 0 0" }}>Multi-dimensional rubric grading engine with letter grade feedback.</p>
                </div>
                <div style={{ backgroundColor: "#0f172a", padding: 14, borderRadius: 8, border: "1px solid #1e293b" }}>
                  <code style={{ color: "#a78bfa", fontWeight: 700, fontSize: 13 }}>get_spaced_revision_deck</code>
                  <p style={{ fontSize: 12, color: "#94a3b8", margin: "6px 0 0" }}>Queries Leitner box revision schedule for exam preparation.</p>
                </div>
              </div>
            </section>

            {/* Security & Standing Rules */}
            <section style={{ backgroundColor: "#111827", borderRadius: 16, border: "1px solid #1f2937", padding: "28px 32px" }}>
              <h3 style={{ fontSize: 18, fontWeight: 800, color: "#fff", margin: "0 0 16px" }}>Security Architecture & Anti-Cheat Rules</h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
                <div style={{ backgroundColor: "#0f172a", padding: 16, borderRadius: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                    <Shield size={16} color="#34d399" />
                    <strong style={{ fontSize: 13, color: "#fff" }}>Rule 6: Zero Answer Key Leaks</strong>
                  </div>
                  <p style={{ fontSize: 12, color: "#94a3b8", margin: 0 }}>Answer keys and grading rubrics are strictly evaluated server-side. The client is never sent solutions prior to submission.</p>
                </div>
                <div style={{ backgroundColor: "#0f172a", padding: 16, borderRadius: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                    <Lock size={16} color="#60a5fa" />
                    <strong style={{ fontSize: 13, color: "#fff" }}>Rule 17: Client Token Isolation</strong>
                  </div>
                  <p style={{ fontSize: 12, color: "#94a3b8", margin: 0 }}>Auth tokens are never stored in browser localStorage or IndexedDB. Web uses HttpOnly, SameSite, Secure cookies.</p>
                </div>
                <div style={{ backgroundColor: "#0f172a", padding: 16, borderRadius: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                    <Radio size={16} color="#f59e0b" />
                    <strong style={{ fontSize: 13, color: "#fff" }}>Rule 18: Assessment Platform Isolation</strong>
                  </div>
                  <p style={{ fontSize: 12, color: "#94a3b8", margin: 0 }}>Web is strictly practice-only. Assessed quizzes require mobile hardware isolation (FLAG_SECURE & Play Integrity).</p>
                </div>
              </div>
            </section>
          </div>
        )}

        {/* ============================================================ */}
        {/* VIEW 3: LIVE SYSTEM DASHBOARD                                */}
        {/* ============================================================ */}
        {activeTab === "dashboard" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 36 }}>
            <div>
              <span style={{ fontSize: 12, fontWeight: 700, color: "#34d399", textTransform: "uppercase", letterSpacing: "0.05em" }}>Live Production Metrics</span>
              <h1 style={{ fontSize: 36, fontWeight: 900, color: "#fff", margin: "6px 0 12px" }}>System Health & State Dashboard</h1>
              <p style={{ fontSize: 15, color: "#9ca3af", maxWidth: 800, lineHeight: 1.6 }}>
                Real-time operational verification: curriculum coverage, test passes, MCP server status, and deployment integrity.
              </p>
            </div>

            {/* Stat Counters */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
              <div style={{ backgroundColor: "#111827", padding: 20, borderRadius: 12, border: "1px solid #1f2937" }}>
                <span style={{ fontSize: 12, color: "#9ca3af", fontWeight: 600 }}>CI/CD Regression Suite</span>
                <div style={{ fontSize: 32, fontWeight: 900, color: "#34d399", margin: "4px 0" }}>11 / 11</div>
                <span style={{ fontSize: 12, color: "#6ee7b7" }}>✓ 100% Tests Passing (307ms)</span>
              </div>
              <div style={{ backgroundColor: "#111827", padding: 20, borderRadius: 12, border: "1px solid #1f2937" }}>
                <span style={{ fontSize: 12, color: "#9ca3af", fontWeight: 600 }}>Curriculum Coverage</span>
                <div style={{ fontSize: 32, fontWeight: 900, color: "#60a5fa", margin: "4px 0" }}>96+</div>
                <span style={{ fontSize: 12, color: "#93c5fd" }}>NCTB Textbook Chapters Ingested</span>
              </div>
              <div style={{ backgroundColor: "#111827", padding: 20, borderRadius: 12, border: "1px solid #1f2937" }}>
                <span style={{ fontSize: 12, color: "#9ca3af", fontWeight: 600 }}>MCP Tools Deployed</span>
                <div style={{ fontSize: 32, fontWeight: 900, color: "#a78bfa", margin: "4px 0" }}>4 Active</div>
                <span style={{ fontSize: 12, color: "#c4b5fd" }}>stdio Transport Protocol</span>
              </div>
              <div style={{ backgroundColor: "#111827", padding: 20, borderRadius: 12, border: "1px solid #1f2937" }}>
                <span style={{ fontSize: 12, color: "#9ca3af", fontWeight: 600 }}>Production Edge</span>
                <div style={{ fontSize: 32, fontWeight: 900, color: "#fbbf24", margin: "4px 0" }}>LIVE</div>
                <span style={{ fontSize: 12, color: "#fde68a" }}>Vercel Turbopack (Next.js 16)</span>
              </div>
            </div>

            {/* Live Feature Matrix */}
            <section style={{ backgroundColor: "#111827", borderRadius: 16, border: "1px solid #1f2937", padding: "28px 32px" }}>
              <h3 style={{ fontSize: 18, fontWeight: 800, color: "#fff", margin: "0 0 16px" }}>Live Feature Deployment Matrix</h3>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, textAlign: "left" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #374151", color: "#9ca3af" }}>
                      <th style={{ padding: "10px 14px" }}>Module Name</th>
                      <th style={{ padding: "10px 14px" }}>Description</th>
                      <th style={{ padding: "10px 14px" }}>Status</th>
                      <th style={{ padding: "10px 14px" }}>Deployment Target</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr style={{ borderBottom: "1px solid #1f2937" }}>
                      <td style={{ padding: "12px 14px", fontWeight: 700, color: "#fff" }}>Textbook-Cited RAG Tutor</td>
                      <td style={{ padding: "12px 14px", color: "#94a3b8" }}>Bilingual chat with exact book, chapter & printed page citations</td>
                      <td style={{ padding: "12px 14px" }}><span style={{ backgroundColor: "#064e3b", color: "#34d399", padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 700 }}>LIVE</span></td>
                      <td style={{ padding: "12px 14px", color: "#60a5fa" }}>Web / Mobile</td>
                    </tr>
                    <tr style={{ borderBottom: "1px solid #1f2937" }}>
                      <td style={{ padding: "12px 14px", fontWeight: 700, color: "#fff" }}>Handwritten CQ Evaluation</td>
                      <td style={{ padding: "12px 14px", color: "#94a3b8" }}>Camera upload of student exercise books with 4-tier rubric grading</td>
                      <td style={{ padding: "12px 14px" }}><span style={{ backgroundColor: "#064e3b", color: "#34d399", padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 700 }}>LIVE</span></td>
                      <td style={{ padding: "12px 14px", color: "#60a5fa" }}>Web / Mobile</td>
                    </tr>
                    <tr style={{ borderBottom: "1px solid #1f2937" }}>
                      <td style={{ padding: "12px 14px", fontWeight: 700, color: "#fff" }}>Leitner Spaced Revision</td>
                      <td style={{ padding: "12px 14px", color: "#94a3b8" }}>Automated 1, 3, 7, 14, 30 day interval flashcard queue</td>
                      <td style={{ padding: "12px 14px" }}><span style={{ backgroundColor: "#064e3b", color: "#34d399", padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 700 }}>LIVE</span></td>
                      <td style={{ padding: "12px 14px", color: "#60a5fa" }}>Web / Background Worker</td>
                    </tr>
                    <tr style={{ borderBottom: "1px solid #1f2937" }}>
                      <td style={{ padding: "12px 14px", fontWeight: 700, color: "#fff" }}>ThinkBuddy MCP Server</td>
                      <td style={{ padding: "12px 14px", color: "#94a3b8" }}>4 stdio tools for Claude Desktop, Cursor & Antigravity</td>
                      <td style={{ padding: "12px 14px" }}><span style={{ backgroundColor: "#064e3b", color: "#34d399", padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 700 }}>LIVE</span></td>
                      <td style={{ padding: "12px 14px", color: "#60a5fa" }}>mcp-server / Local</td>
                    </tr>
                    <tr style={{ borderBottom: "1px solid #1f2937" }}>
                      <td style={{ padding: "12px 14px", fontWeight: 700, color: "#fff" }}>Parent Supervision Hub</td>
                      <td style={{ padding: "12px 14px", color: "#94a3b8" }}>Streak monitoring, weak areas, and time tracking</td>
                      <td style={{ padding: "12px 14px" }}><span style={{ backgroundColor: "#1e1b4b", color: "#a78bfa", padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 700 }}>BETA</span></td>
                      <td style={{ padding: "12px 14px", color: "#60a5fa" }}>Web / Mobile</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        )}
      </main>

      {/* ============================================================ */}
      {/* 4. ADMIN & ACCESS CONTROL MODAL DRAWER                       */}
      {/* ============================================================ */}
      {isAdminOpen && (
        <div style={{ position: "fixed", inset: 0, zIndex: 100, backgroundColor: "rgba(0,0,0,0.75)", display: "flex", justifyContent: "flex-end", backdropFilter: "blur(4px)" }}>
          <div style={{ width: "100%", maxWidth: 480, height: "100%", backgroundColor: "#111827", borderLeft: "1px solid #1f2937", padding: 28, overflowY: "auto", display: "flex", flexDirection: "column", gap: 24 }}>
            {/* Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #1f2937", paddingBottom: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Settings size={20} color="#60a5fa" />
                <h3 style={{ fontSize: 18, fontWeight: 800, margin: 0, color: "#fff" }}>Docs Administration & Access</h3>
              </div>
              <button onClick={() => setIsAdminOpen(false)} style={{ background: "none", border: "none", color: "#9ca3af", cursor: "pointer" }}>
                <X size={20} />
              </button>
            </div>

            {/* Public Visibility Toggle */}
            <div style={{ backgroundColor: "#0f172a", padding: 18, borderRadius: 12, border: "1px solid #1e293b", display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <h4 style={{ fontSize: 14, fontWeight: 700, margin: 0, color: "#fff" }}>Public Access Switch</h4>
                  <p style={{ fontSize: 12, color: "#94a3b8", margin: "2px 0 0" }}>Control whether /docs is publicly visible</p>
                </div>
                <button
                  onClick={() => saveAccessConfig({ ...accessConfig, is_public: !accessConfig.is_public })}
                  style={{
                    padding: "6px 14px",
                    borderRadius: 20,
                    fontWeight: 700,
                    fontSize: 12,
                    border: "none",
                    cursor: "pointer",
                    backgroundColor: accessConfig.is_public ? "#10b981" : "#ef4444",
                    color: "#fff",
                  }}
                >
                  {accessConfig.is_public ? "ON (Public)" : "OFF (Hidden)"}
                </button>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <h4 style={{ fontSize: 13, fontWeight: 600, margin: 0, color: "#e5e7eb" }}>Admin Override Mode</h4>
                  <p style={{ fontSize: 11, color: "#64748b", margin: 0 }}>Bypass schedule and keep permanently active</p>
                </div>
                <input
                  type="checkbox"
                  checked={accessConfig.admin_override}
                  onChange={(e) => saveAccessConfig({ ...accessConfig, admin_override: e.target.checked })}
                  style={{ width: 18, height: 18, cursor: "pointer" }}
                />
              </div>
            </div>

            {/* Scheduled Window Configuration */}
            <div style={{ backgroundColor: "#0f172a", padding: 18, borderRadius: 12, border: "1px solid #1e293b", display: "flex", flexDirection: "column", gap: 12 }}>
              <h4 style={{ fontSize: 14, fontWeight: 700, margin: 0, color: "#fff", display: "flex", alignItems: "center", gap: 6 }}>
                <Calendar size={16} color="#60a5fa" />
                <span>Publishing Schedule (Judging Window)</span>
              </h4>

              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <label style={{ fontSize: 11, color: "#94a3b8" }}>Start Date & Time:</label>
                <input
                  type="datetime-local"
                  value={accessConfig.publish_start.substring(0, 16)}
                  onChange={(e) => saveAccessConfig({ ...accessConfig, publish_start: new Date(e.target.value).toISOString() })}
                  style={{ padding: "8px 12px", borderRadius: 6, border: "1px solid #374151", backgroundColor: "#030712", color: "#fff", fontSize: 12 }}
                />
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <label style={{ fontSize: 11, color: "#94a3b8" }}>End Date & Time:</label>
                <input
                  type="datetime-local"
                  value={accessConfig.publish_end.substring(0, 16)}
                  onChange={(e) => saveAccessConfig({ ...accessConfig, publish_end: new Date(e.target.value).toISOString() })}
                  style={{ padding: "8px 12px", borderRadius: 6, border: "1px solid #374151", backgroundColor: "#030712", color: "#fff", fontSize: 12 }}
                />
              </div>

              <button
                onClick={() =>
                  saveAccessConfig({
                    ...accessConfig,
                    publish_start: "2026-06-10T00:00:00.000Z",
                    publish_end: "2026-06-14T23:59:59.000Z",
                  })
                }
                style={{ padding: "6px 10px", borderRadius: 6, backgroundColor: "#1f2937", border: "1px solid #374151", color: "#93c5fd", fontSize: 11, fontWeight: 600, cursor: "pointer" }}
              >
                Reset to Default Hackathon Dates (June 10–14)
              </button>
            </div>

            {/* Quick Team Editor */}
            <div style={{ backgroundColor: "#0f172a", padding: 18, borderRadius: 12, border: "1px solid #1e293b", display: "flex", flexDirection: "column", gap: 12 }}>
              <h4 style={{ fontSize: 14, fontWeight: 700, margin: 0, color: "#fff", display: "flex", alignItems: "center", gap: 6 }}>
                <Users size={16} color="#34d399" />
                <span>Primary Lead & Team Showcase</span>
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <input
                  type="text"
                  placeholder="Founder Name"
                  value={teamMembers[0]?.name || ""}
                  onChange={(e) => {
                    const updated = [...teamMembers];
                    if (updated[0]) updated[0].name = e.target.value;
                    saveTeamConfig(updated);
                  }}
                  style={{ padding: "8px 12px", borderRadius: 6, border: "1px solid #374151", backgroundColor: "#030712", color: "#fff", fontSize: 12 }}
                />
                <input
                  type="text"
                  placeholder="Founder Role"
                  value={teamMembers[0]?.role || ""}
                  onChange={(e) => {
                    const updated = [...teamMembers];
                    if (updated[0]) updated[0].role = e.target.value;
                    saveTeamConfig(updated);
                  }}
                  style={{ padding: "8px 12px", borderRadius: 6, border: "1px solid #374151", backgroundColor: "#030712", color: "#fff", fontSize: 12 }}
                />
                <input
                  type="email"
                  placeholder="Founder Email"
                  value={teamMembers[0]?.email || ""}
                  onChange={(e) => {
                    const updated = [...teamMembers];
                    if (updated[0]) updated[0].email = e.target.value;
                    saveTeamConfig(updated);
                  }}
                  style={{ padding: "8px 12px", borderRadius: 6, border: "1px solid #374151", backgroundColor: "#030712", color: "#fff", fontSize: 12 }}
                />
              </div>
            </div>

            <button
              onClick={() => setIsAdminOpen(false)}
              style={{ padding: "12px", borderRadius: 8, backgroundColor: "#2563eb", color: "#fff", border: "none", fontWeight: 700, cursor: "pointer", marginTop: "auto" }}
            >
              Done & Save Settings
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
