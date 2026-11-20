"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Sparkles,
  Key,
  Database,
  Send,
  BookOpen,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Eye,
  EyeOff,
  Zap,
  ShieldCheck,
  ExternalLink,
  Copy,
  Check,
  Activity,
  Cpu,
  Globe,
  Search,
  CheckCircle,
  Brain,
} from "lucide-react";
import AnalyticsDashboard from "./AnalyticsDashboard";

interface AITutorConfig {
  id: string;
  llm_provider: string;
  has_api_key: boolean;
  api_key_masked: string | null;
  api_base: string | null;
  primary_model: string;
  fallback_model: string;
  temperature: number;
  system_prompt: string | null;
  embedding_provider: string;
  has_embedding_api_key: boolean;
  embedding_api_key_masked: string | null;
  embedding_model: string;
  embedding_dimensions: number;
  confidence_threshold: number;
  max_chunks: number;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

interface RAGStats {
  total_books: number;
  total_chapters: number;
  total_chunks: number;
  total_chat_sessions: number;
  total_chat_messages: number;
  active_llm_provider: string;
  active_primary_model: string;
  active_embedding_provider: string;
  rag_chat_enabled: boolean;
}

interface RAGChunk {
  chunk_id: string;
  book_title: string;
  chapter_title: string;
  chapter_number: number | null;
  printed_page: number;
  pdf_page_index: number;
  score: number;
  snippet: string;
}

interface ProviderOption {
  id: string;
  name: string;
  badge?: string;
  tagline: string;
  defaultBase?: string;
  recommendedModels: { id: string; name: string; tag?: string }[];
  accentGradient: string;
  borderActive: string;
}

const PROVIDERS: ProviderOption[] = [
  {
    id: "openrouter",
    name: "OpenRouter",
    badge: "RECOMMENDED",
    tagline: "One unified API key for 200+ models (Gemini, Claude, Llama 3, DeepSeek)",
    defaultBase: "https://openrouter.ai/api/v1",
    accentGradient: "from-blue-600 to-indigo-600",
    borderActive: "border-blue-500 bg-blue-50/50 dark:bg-blue-950/20",
    recommendedModels: [
      { id: "openrouter/auto", name: "Auto Router (Free/Smart)", tag: "RECOMMENDED" },
      { id: "openrouter/free", name: "OpenRouter Free ($0 Balance)", tag: "100% FREE" },
      { id: "openai/gpt-4o-mini", name: "GPT-4o Mini", tag: "FAST" },
      { id: "meta-llama/llama-3.3-70b-instruct", name: "Llama 3.3 70B", tag: "SMART" },
      { id: "deepseek/deepseek-chat", name: "DeepSeek V3", tag: "CODE" },
      { id: "anthropic/claude-3.5-sonnet", name: "Claude 3.5 Sonnet", tag: "NUANCED" },
    ],
  },
  {
    id: "gemini",
    name: "Google Gemini",
    badge: "DIRECT",
    tagline: "Official Google DeepMind Gemini API with native multimodal speed",
    accentGradient: "from-emerald-600 to-teal-600",
    borderActive: "border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/20",
    recommendedModels: [
      { id: "gemini/gemini-1.5-flash", name: "Gemini 1.5 Flash", tag: "DEFAULT" },
      { id: "gemini/gemini-1.5-pro", name: "Gemini 1.5 Pro", tag: "REASONING" },
      { id: "gemini/gemini-2.0-flash-exp", name: "Gemini 2.0 Flash Exp", tag: "LATEST" },
    ],
  },
  {
    id: "openai",
    name: "OpenAI",
    badge: "DIRECT",
    tagline: "Direct official OpenAI developer API for GPT-4o series",
    defaultBase: "https://api.openai.com/v1",
    accentGradient: "from-sky-600 to-blue-700",
    borderActive: "border-sky-500 bg-sky-50/50 dark:bg-sky-950/20",
    recommendedModels: [
      { id: "openai/gpt-4o-mini", name: "GPT-4o Mini", tag: "RECOMMENDED" },
      { id: "openai/gpt-4o", name: "GPT-4o", tag: "FLAGSHIP" },
    ],
  },
  {
    id: "anthropic",
    name: "Anthropic",
    badge: "DIRECT",
    tagline: "Claude 3.5 Sonnet and Haiku via Anthropic direct API",
    accentGradient: "from-amber-600 to-orange-600",
    borderActive: "border-amber-500 bg-amber-50/50 dark:bg-amber-950/20",
    recommendedModels: [
      { id: "anthropic/claude-3-5-sonnet-20241022", name: "Claude 3.5 Sonnet", tag: "NUANCED" },
      { id: "anthropic/claude-3-5-haiku-20241022", name: "Claude 3.5 Haiku", tag: "SPEED" },
    ],
  },
  {
    id: "groq",
    name: "Groq Cloud",
    badge: "FASTEST",
    tagline: "Sub-second LPU inference for Llama 3 models",
    defaultBase: "https://api.groq.com/openai/v1",
    accentGradient: "from-purple-600 to-pink-600",
    borderActive: "border-purple-500 bg-purple-50/50 dark:bg-purple-950/20",
    recommendedModels: [
      { id: "groq/llama-3.3-70b-versatile", name: "Llama 3.3 70B", tag: "FAST" },
      { id: "groq/llama-3.1-8b-instant", name: "Llama 3.1 8B", tag: "INSTANT" },
    ],
  },
  {
    id: "ollama",
    name: "Ollama (Local)",
    badge: "PRIVATE",
    tagline: "Offline self-hosted local inference without internet dependency",
    defaultBase: "http://localhost:11434/v1",
    accentGradient: "from-slate-600 to-slate-800",
    borderActive: "border-slate-500 bg-slate-50/50 dark:bg-slate-900/40",
    recommendedModels: [
      { id: "ollama/llama3.2", name: "Llama 3.2 3B", tag: "LOCAL" },
      { id: "ollama/mistral", name: "Mistral 7B", tag: "LOCAL" },
    ],
  },
  {
    id: "custom",
    name: "Custom Base URL",
    badge: "OPENAI-COMPATIBLE",
    tagline: "Any standard OpenAI-compatible API endpoint, proxy, or gateway",
    accentGradient: "from-zinc-600 to-neutral-800",
    borderActive: "border-zinc-500 bg-zinc-50/50 dark:bg-zinc-900/40",
    recommendedModels: [
      { id: "default-model", name: "Default Custom Model" },
    ],
  },
];

export const AdminAITutorView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"llm" | "analytics" | "rag" | "diagnostics" | "stats">("llm");
  const [config, setConfig] = useState<AITutorConfig | null>(null);
  const [stats, setStats] = useState<RAGStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [copiedResponse, setCopiedResponse] = useState<boolean>(false);

  // Form Fields
  const [llmProvider, setLlmProvider] = useState<string>("openrouter");
  const [apiKey, setApiKey] = useState<string>("");
  const [showApiKey, setShowApiKey] = useState<boolean>(false);
  const [apiBase, setApiBase] = useState<string>("https://openrouter.ai/api/v1");
  const [primaryModel, setPrimaryModel] = useState<string>("google/gemini-2.0-flash-exp:free");
  const [fallbackModel, setFallbackModel] = useState<string>("openai/gpt-4o-mini");
  const [temperature, setTemperature] = useState<number>(0.3);
  const [systemPrompt, setSystemPrompt] = useState<string>("");

  const [embeddingProvider, setEmbeddingProvider] = useState<string>("bge-m3");
  const [embeddingApiKey, setEmbeddingApiKey] = useState<string>("");
  const [showEmbeddingApiKey, setShowEmbeddingApiKey] = useState<boolean>(false);
  const [embeddingModel, setEmbeddingModel] = useState<string>("bge-m3");
  const [embeddingDimensions, setEmbeddingDimensions] = useState<number>(1024);
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(0.10);
  const [maxChunks, setMaxChunks] = useState<number>(4);
  const [isEnabled, setIsEnabled] = useState<boolean>(true);

  // Diagnostic states
  const [testPrompt, setTestPrompt] = useState<string>(
    "Say hello and introduce yourself as ThinkBuddy AI Tutor in one sentence in English and Bangla."
  );
  const [testingLLM, setTestingLLM] = useState<boolean>(false);
  const [llmResult, setLlmResult] = useState<{
    success: boolean;
    content: string;
    tokens_in: number;
    tokens_out: number;
    latency_ms: number;
    model_used: string;
    error?: string | null;
  } | null>(null);

  // RAG Testing states
  const [ragQuery, setRagQuery] = useState<string>("সালোকসংশ্লেষণ কী এবং উদ্ভিদ কীভাবে খাদ্য তৈরি করে?");
  const [testingRAG, setTestingRAG] = useState<boolean>(false);
  const [ragResult, setRagResult] = useState<{
    confidence: number;
    chunks: RAGChunk[];
    latency_ms: number;
  } | null>(null);

  // Load config & stats
  const fetchData = useCallback(async () => {
    try {
      const [resConfig, resStats] = await Promise.all([
        fetch("/api/admin/ai-tutor/config", {
          headers: { "x-client-platform": "web" },
        }),
        fetch("/api/admin/ai-tutor/stats", {
          headers: { "x-client-platform": "web" },
        }),
      ]);

      if (resConfig.ok) {
        const data: AITutorConfig = await resConfig.json();
        setConfig(data);
        setLlmProvider(data.llm_provider);
        setApiBase(data.api_base || (data.llm_provider === "openrouter" ? "https://openrouter.ai/api/v1" : ""));
        setPrimaryModel(data.primary_model);
        setFallbackModel(data.fallback_model);
        setTemperature(data.temperature);
        setSystemPrompt(data.system_prompt || "");
        setEmbeddingProvider(data.embedding_provider);
        setEmbeddingModel(data.embedding_model);
        setEmbeddingDimensions(data.embedding_dimensions);
        setConfidenceThreshold(data.confidence_threshold);
        setMaxChunks(data.max_chunks);
        setIsEnabled(data.is_enabled);
      }

      if (resStats.ok) {
        const dataStats: RAGStats = await resStats.json();
        setStats(dataStats);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setSaveError("Failed to fetch current AI Tutor settings: " + msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchData();
  }, [fetchData]);

  const selectProvider = (p: ProviderOption) => {
    setLlmProvider(p.id);
    if (p.defaultBase) {
      setApiBase(p.defaultBase);
    } else if (p.id !== "custom") {
      setApiBase("");
    }
    if (p.recommendedModels.length > 0) {
      setPrimaryModel(p.recommendedModels[0].id);
      if (p.recommendedModels.length > 1) {
        setFallbackModel(p.recommendedModels[1].id);
      }
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveSuccess(null);
    setSaveError(null);

    const payload: Record<string, unknown> = {
      llm_provider: llmProvider,
      api_base: apiBase || null,
      primary_model: primaryModel,
      fallback_model: fallbackModel,
      temperature,
      system_prompt: systemPrompt,
      embedding_provider: embeddingProvider,
      embedding_model: embeddingModel,
      embedding_dimensions: embeddingDimensions,
      confidence_threshold: confidenceThreshold,
      max_chunks: maxChunks,
      is_enabled: isEnabled,
    };

    if (apiKey.trim()) {
      payload.api_key = apiKey.trim();
    }
    if (embeddingApiKey.trim()) {
      payload.embedding_api_key = embeddingApiKey.trim();
    }

    try {
      const res = await fetch("/api/admin/ai-tutor/config", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "x-client-platform": "web",
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to update AI Tutor configuration");
      }

      const updated: AITutorConfig = await res.json();
      setConfig(updated);
      setApiKey("");
      setEmbeddingApiKey("");
      setSaveSuccess("AI Tutor (Buddy) & RAG configuration successfully saved and activated!");
      setTimeout(() => setSaveSuccess(null), 5000);
      void fetchData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setSaveError(msg);
    } finally {
      setSaving(false);
    }
  };

  const handleTestLLM = async () => {
    setTestingLLM(true);
    setLlmResult(null);
    try {
      const payload: Record<string, unknown> = {
        prompt: testPrompt,
        provider: llmProvider,
        model: primaryModel,
      };
      if (apiKey.trim()) payload.api_key = apiKey.trim();
      if (apiBase.trim()) payload.api_base = apiBase.trim();

      const res = await fetch("/api/admin/ai-tutor/test-llm", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-client-platform": "web",
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      setLlmResult(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setLlmResult({
        success: false,
        content: "",
        latency_ms: 0,
        tokens_in: 0,
        tokens_out: 0,
        model_used: primaryModel,
        error: msg,
      });
    } finally {
      setTestingLLM(false);
    }
  };

  const handleTestRAG = async () => {
    setTestingRAG(true);
    setRagResult(null);
    try {
      const res = await fetch("/api/admin/ai-tutor/test-rag", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-client-platform": "web",
        },
        body: JSON.stringify({
          query: ragQuery,
          limit: maxChunks,
        }),
      });

      const data = await res.json();
      setRagResult(data);
    } catch (err: unknown) {
      console.error("RAG test error:", err);
    } finally {
      setTestingRAG(false);
    }
  };

  const copyResponseText = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedResponse(true);
    setTimeout(() => setCopiedResponse(false), 2000);
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[460px] text-slate-500">
        <RefreshCw className="w-9 h-9 animate-spin text-blue-600 mb-3" />
        <p className="text-sm font-medium tracking-wide">Loading AI Tutor & RAG Governance Dashboard...</p>
      </div>
    );
  }

  const activeProviderObj = PROVIDERS.find((p) => p.id === llmProvider) || PROVIDERS[0];

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Top Banner / Hero Header */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 border border-slate-800 p-6 sm:p-8 text-white shadow-2xl">
        <div className="absolute top-0 right-0 -mt-12 -mr-12 w-80 h-80 rounded-full bg-blue-500/10 blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-1/3 -mb-12 w-64 h-64 rounded-full bg-indigo-500/10 blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2.5">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold tracking-wider uppercase bg-blue-500/20 text-blue-300 border border-blue-500/30">
                <Sparkles className="w-3.5 h-3.5 text-blue-400" />
                ThinkBuddy Admin Suite
              </span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                <ShieldCheck className="w-3.5 h-3.5" />
                Server Authority
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
              Buddy AI Tutor & RAG Management
            </h1>
            <p className="text-slate-300 text-sm max-w-2xl leading-relaxed">
              Configure LLM providers with OpenRouter, Google Gemini, OpenAI, or Anthropic. Manage curriculum RAG embeddings, test live API connectivity, and inspect real NCTB textbook citations.
            </p>
          </div>

          {/* Status Badge Box */}
          <div className="flex flex-col sm:flex-row md:flex-col gap-2 shrink-0 bg-white/5 border border-white/10 rounded-2xl p-4 backdrop-blur-md">
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${config?.has_api_key ? "bg-emerald-400 animate-pulse" : "bg-amber-400"}`} />
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-200">
                {config?.has_api_key ? "Live API Connected" : "Ready for API Key"}
              </span>
            </div>
            <div className="text-[11px] text-slate-400 space-y-0.5">
              <div className="truncate max-w-[220px]">
                Provider: <span className="text-slate-200 font-medium capitalize">{config?.llm_provider || "openrouter"}</span>
              </div>
              <div className="truncate max-w-[220px]">
                Model: <span className="text-blue-300 font-mono text-[10px]">{config?.primary_model || "google/gemini-2.0-flash"}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* AI Not Configured Alert Banner */}
      {!config?.has_api_key && (
        <div className="flex items-center gap-3 p-4 rounded-2xl bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 text-amber-900 dark:text-amber-200 text-sm shadow-sm">
          <AlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0" />
          <div>
            <div className="font-semibold">AI Not Configured</div>
            <div className="text-xs text-amber-800 dark:text-amber-300">
              Student chat will display &quot;একটু সমস্যা হয়েছে, আবার চেষ্টা করো&quot; until an active OpenRouter API key is saved.
            </div>
          </div>
        </div>
      )}

      {/* Notifications */}
      {saveSuccess && (
        <div className="flex items-center gap-3 p-4 rounded-2xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 text-sm shadow-sm animate-in fade-in">
          <CheckCircle className="w-5 h-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
          <p className="font-medium">{saveSuccess}</p>
        </div>
      )}

      {saveError && (
        <div className="flex items-center gap-3 p-4 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-sm shadow-sm">
          <AlertCircle className="w-5 h-5 shrink-0 text-rose-600 dark:text-rose-400" />
          <p className="font-medium">{saveError}</p>
        </div>
      )}

      {/* Modern Tab Bar */}
      <div className="flex items-center gap-2 p-1.5 rounded-2xl bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-x-auto">
        <button
          onClick={() => setActiveTab("llm")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all whitespace-nowrap ${
            activeTab === "llm"
              ? "bg-white dark:bg-slate-800 text-blue-600 dark:text-blue-400 shadow-sm border border-slate-200/80 dark:border-slate-700"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
          }`}
        >
          <Key className="w-4 h-4" />
          Chatbot API & Models
        </button>

        <button
          onClick={() => setActiveTab("analytics")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all whitespace-nowrap ${
            activeTab === "analytics"
              ? "bg-white dark:bg-slate-800 text-indigo-600 dark:text-indigo-400 shadow-sm border border-slate-200/80 dark:border-slate-700"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
          }`}
        >
          <Brain className="w-4 h-4 text-indigo-500" />
          Weakness & Strength Pipeline
        </button>

        <button
          onClick={() => setActiveTab("rag")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all whitespace-nowrap ${
            activeTab === "rag"
              ? "bg-white dark:bg-slate-800 text-blue-600 dark:text-blue-400 shadow-sm border border-slate-200/80 dark:border-slate-700"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
          }`}
        >
          <Database className="w-4 h-4" />
          RAG & Vector Retrieval
        </button>

        <button
          onClick={() => setActiveTab("diagnostics")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all whitespace-nowrap ${
            activeTab === "diagnostics"
              ? "bg-white dark:bg-slate-800 text-blue-600 dark:text-blue-400 shadow-sm border border-slate-200/80 dark:border-slate-700"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
          }`}
        >
          <Zap className="w-4 h-4" />
          Live Diagnostics Console
        </button>

        <button
          onClick={() => setActiveTab("stats")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all whitespace-nowrap ${
            activeTab === "stats"
              ? "bg-white dark:bg-slate-800 text-blue-600 dark:text-blue-400 shadow-sm border border-slate-200/80 dark:border-slate-700"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
          }`}
        >
          <BookOpen className="w-4 h-4" />
          Curriculum Knowledge Base
        </button>
      </div>

      {/* TAB 1: LLM & OPENROUTER PROVIDER */}
      {activeTab === "llm" && (
        <form onSubmit={handleSave} className="space-y-6">
          {/* Featured Provider Selector Cards */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                Select LLM Provider
              </label>
              <span className="text-[11px] text-slate-500">
                Click any provider to auto-configure optimal settings
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {PROVIDERS.map((p) => {
                const isSelected = llmProvider === p.id;
                return (
                  <div
                    key={p.id}
                    onClick={() => selectProvider(p)}
                    className={`cursor-pointer rounded-2xl border p-4 transition-all relative overflow-hidden ${
                      isSelected
                        ? `${p.borderActive} shadow-md`
                        : "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-slate-300 dark:hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      <div className="flex items-center gap-2 font-bold text-sm text-slate-900 dark:text-slate-100">
                        <span className={`w-2.5 h-2.5 rounded-full bg-gradient-to-r ${p.accentGradient}`} />
                        {p.name}
                      </div>
                      {p.badge && (
                        <span className={`text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-md ${
                          p.id === "openrouter"
                            ? "bg-blue-600 text-white shadow-sm"
                            : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
                        }`}>
                          {p.badge}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400 leading-snug line-clamp-2">
                      {p.tagline}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* OpenRouter Callout Box if OpenRouter is selected */}
          {llmProvider === "openrouter" && (
            <div className="rounded-2xl bg-gradient-to-r from-blue-500/10 via-indigo-500/10 to-transparent border border-blue-200 dark:border-blue-900/60 p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-xs font-bold text-blue-700 dark:text-blue-300">
                  <Globe className="w-4 h-4" />
                  OpenRouter Unified Gateway Active
                </div>
                <p className="text-xs text-slate-600 dark:text-slate-400">
                  Select <strong className="text-blue-500">openrouter/auto</strong> or <strong className="text-blue-500">openai/gpt-4o-mini</strong> with your OpenRouter key for high availability. Note: Standalone free models (<code className="font-mono">:free</code>) are subject to upstream shared pool rate limits.
                </p>
              </div>
              <a
                href="https://openrouter.ai/keys"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors shrink-0"
              >
                Get OpenRouter Key
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
          )}

          {/* Model Quick Select Pills */}
          <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 space-y-4 shadow-sm">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-2">
                Recommended Models for {activeProviderObj.name} (Click to Set as Primary)
              </label>
              <div className="flex flex-wrap gap-2">
                {activeProviderObj.recommendedModels.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setPrimaryModel(m.id)}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                      primaryModel === m.id
                        ? "bg-blue-600 text-white shadow-sm ring-2 ring-blue-500/30"
                        : "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-200/60 dark:border-slate-700"
                    }`}
                  >
                    <span>{m.name}</span>
                    {m.tag && (
                      <span className={`text-[10px] uppercase font-bold px-1.5 py-0.2 rounded ${
                        primaryModel === m.id ? "bg-white/20 text-white" : "bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300"
                      }`}>
                        {m.tag}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Credentials & Models Inputs */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              {/* API Key */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    {activeProviderObj.name} API Key
                  </label>
                  {config?.has_api_key && (
                    <span className="text-[11px] font-mono text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded-md border border-emerald-200 dark:border-emerald-800">
                      Configured: {config.api_key_masked}
                    </span>
                  )}
                </div>
                <div className="relative">
                  <input
                    type={showApiKey ? "text" : "password"}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder={config?.has_api_key ? "Leave blank to keep existing key, or paste new key..." : "Paste your API key here (sk-...)"}
                    className="w-full pl-3.5 pr-10 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                  >
                    {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-[11px] text-slate-500">
                  Stored securely on the server. Never sent to browser clients or leaked in transcripts (Rule 15).
                </p>
              </div>

              {/* API Base URL */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Custom Base URL (Optional)
                </label>
                <input
                  type="text"
                  value={apiBase}
                  onChange={(e) => setApiBase(e.target.value)}
                  placeholder="https://openrouter.ai/api/v1 (or custom endpoint)"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                />
                <p className="text-[11px] text-slate-500">
                  For OpenRouter: <code className="bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded">https://openrouter.ai/api/v1</code>
                </p>
              </div>

              {/* Primary Model */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Primary Model Identifier
                </label>
                <input
                  type="text"
                  value={primaryModel}
                  onChange={(e) => setPrimaryModel(e.target.value)}
                  placeholder="google/gemini-2.0-flash-exp:free or openai/gpt-4o-mini"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                />
              </div>

              {/* Fallback Model */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Fallback Model Identifier
                </label>
                <input
                  type="text"
                  value={fallbackModel}
                  onChange={(e) => setFallbackModel(e.target.value)}
                  placeholder="openai/gpt-4o-mini or anthropic/claude-3-5-haiku"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                />
              </div>
            </div>

            {/* Temperature Slider */}
            <div className="pt-2">
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Generation Temperature: <span className="font-mono text-blue-600 dark:text-blue-400 font-bold">{temperature}</span>
                </label>
                <span className="text-[11px] text-slate-500">
                  {temperature <= 0.3 ? "Strict Fact-adherent (Recommended for NCTB)" : temperature <= 0.7 ? "Balanced Explanations" : "Creative"}
                </span>
              </div>
              <input
                type="range"
                min="0.0"
                max="1.0"
                step="0.05"
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                className="w-full accent-blue-600 cursor-pointer"
              />
            </div>

            {/* Persona & System Prompt */}
            <div className="space-y-1.5 pt-2">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                Buddy&apos;s Persona & System Prompt Instructions
              </label>
              <textarea
                rows={4}
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                placeholder="Custom instruction prompt for Buddy the AI Tutor..."
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs focus:ring-2 focus:ring-blue-500 outline-none leading-relaxed"
              />
              <p className="text-[11px] text-slate-500">
                Controls tone, language policy (natural Bangla & English), and adherence to cited textbook pages.
              </p>
            </div>
          </div>

          {/* Action Row */}
          <div className="flex items-center justify-between pt-2">
            <button
              type="button"
              onClick={() => setActiveTab("diagnostics")}
              className="inline-flex items-center gap-2 text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline"
            >
              <Zap className="w-4 h-4" />
              Test This Model in Diagnostic Console →
            </button>

            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm shadow-md transition-colors disabled:opacity-50"
            >
              {saving ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Saving & Activating...
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  Save & Activate AI Tutor Configuration
                </>
              )}
            </button>
          </div>
        </form>
      )}

      {/* TAB: WEAKNESS & STRENGTH INTELLIGENCE PIPELINE */}
      {activeTab === "analytics" && (
        <AnalyticsDashboard />
      )}

      {/* TAB 2: RAG & VECTOR RETRIEVAL */}
      {activeTab === "rag" && (
        <form onSubmit={handleSave} className="space-y-6">
          <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-5 shadow-sm">
            <div className="border-b border-slate-200 dark:border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wide">
                NCTB Textbook Vector Knowledge Base Settings
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Configure textbook embedding models, minimum similarity score threshold, and maximum retrieved context chunks.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Embedding Provider */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Embedding Provider
                </label>
                <select
                  value={embeddingProvider}
                  onChange={(e) => setEmbeddingProvider(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  <option value="bge-m3">BGE-M3 (Multilingual Bengali-English Optimized)</option>
                  <option value="openai">OpenAI (text-embedding-3-small)</option>
                  <option value="gemini">Google Gemini Embedding</option>
                  <option value="mock">Local Deterministic (Mock Mode)</option>
                </select>
              </div>

              {/* Embedding Model */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Embedding Model Identifier
                </label>
                <input
                  type="text"
                  value={embeddingModel}
                  onChange={(e) => setEmbeddingModel(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                />
              </div>

              {/* Embedding Dimensions */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Vector Dimensions
                </label>
                <input
                  type="number"
                  value={embeddingDimensions}
                  onChange={(e) => setEmbeddingDimensions(parseInt(e.target.value, 10))}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                />
                <p className="text-[11px] text-slate-500">Standard: 1024 (BGE-M3), 1536 (OpenAI text-embedding-3-small)</p>
              </div>

              {/* Max Chunks */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Max Authoritative Chunks per Turn ({maxChunks})
                </label>
                <input
                  type="range"
                  min="1"
                  max="8"
                  value={maxChunks}
                  onChange={(e) => setMaxChunks(parseInt(e.target.value, 10))}
                  className="w-full accent-blue-600 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-400">
                  <span>1 Chunk (Compact)</span>
                  <span>4 Chunks (Recommended)</span>
                  <span>8 Chunks (Detailed)</span>
                </div>
              </div>
            </div>

            {/* Confidence Threshold */}
            <div className="space-y-1.5 pt-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Minimum Confidence Threshold: <span className="font-mono text-blue-600 font-bold">{confidenceThreshold}</span>
                </label>
                <span className="text-[11px] text-slate-500">
                  Chunks below this similarity score are excluded from student responses
                </span>
              </div>
              <input
                type="range"
                min="0.05"
                max="0.8"
                step="0.01"
                value={confidenceThreshold}
                onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
                className="w-full accent-blue-600 cursor-pointer"
              />
            </div>

            {/* Embedding API Key */}
            <div className="space-y-1.5 pt-2">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                Embedding API Key (Optional if using BGE-M3 or local inference)
              </label>
              <div className="relative">
                <input
                  type={showEmbeddingApiKey ? "text" : "password"}
                  value={embeddingApiKey}
                  onChange={(e) => setEmbeddingApiKey(e.target.value)}
                  placeholder="Paste embedding API key if using cloud embeddings..."
                  className="w-full pl-3.5 pr-10 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowEmbeddingApiKey(!showEmbeddingApiKey)}
                  className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
                >
                  {showEmbeddingApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm shadow-md transition-colors disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save RAG Retrieval Settings"}
            </button>
          </div>
        </form>
      )}

      {/* TAB 3: DIAGNOSTICS CONSOLE */}
      {activeTab === "diagnostics" && (
        <div className="space-y-6">
          {/* Diagnostic Ping Container */}
          <div className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-md">
            {/* Console Mac-style Topbar */}
            <div className="bg-slate-100 dark:bg-slate-800/80 px-4 py-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-rose-500/80" />
                <div className="w-3 h-3 rounded-full bg-amber-500/80" />
                <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
                <span className="text-xs font-mono text-slate-500 dark:text-slate-400 ml-2">
                  live-llm-diagnostic: {llmProvider} / {primaryModel}
                </span>
              </div>
              <span className="text-[11px] font-mono text-slate-400 uppercase">
                Latency & Token Telemetry
              </span>
            </div>

            <div className="p-6 space-y-4">
              {/* Sample Prompts */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Prompt to Send to Buddy AI Tutor
                </label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {[
                    "Say hello and introduce yourself as ThinkBuddy AI Tutor in English and Bangla.",
                    "সালোকসংশ্লেষণ কী? সংক্ষিপ্ত এবং সহজ ভাষায় বুঝিয়ে বলো।",
                    "What is Pythagoras theorem with a practical math example?",
                  ].map((p, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => setTestPrompt(p)}
                      className="text-[11px] px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950/40 border border-slate-200/60 dark:border-slate-700 transition-colors"
                    >
                      {p.slice(0, 40)}...
                    </button>
                  ))}
                </div>
                <textarea
                  rows={3}
                  value={testPrompt}
                  onChange={(e) => setTestPrompt(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs focus:ring-2 focus:ring-blue-500 outline-none leading-relaxed"
                />
              </div>

              <div className="flex justify-between items-center pt-2">
                <div className="text-[11px] text-slate-500">
                  Target: <code className="bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded font-mono">{primaryModel}</code> via <span className="capitalize font-semibold">{llmProvider}</span>
                </div>
                <button
                  type="button"
                  onClick={handleTestLLM}
                  disabled={testingLLM}
                  className="inline-flex items-center gap-2 px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs shadow-md transition-colors disabled:opacity-50"
                >
                  {testingLLM ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      Testing API...
                    </>
                  ) : (
                    <>
                      <Send className="w-3.5 h-3.5" />
                      Run Live Ping Test
                    </>
                  )}
                </button>
              </div>

              {/* Result Area */}
              {llmResult && (
                <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-800 space-y-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold ${
                      llmResult.success
                        ? "bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800"
                        : "bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border border-rose-300 dark:border-rose-800"
                    }`}>
                      {llmResult.success ? "200 Success" : "API Error"}
                    </span>

                    <span className="inline-flex items-center gap-1.5 text-xs font-mono text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2.5 py-1 rounded-lg">
                      <Activity className="w-3.5 h-3.5 text-blue-500" />
                      Latency: <strong className="text-slate-900 dark:text-slate-100">{llmResult.latency_ms}ms</strong>
                    </span>

                    <span className="inline-flex items-center gap-1.5 text-xs font-mono text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2.5 py-1 rounded-lg">
                      <Cpu className="w-3.5 h-3.5 text-purple-500" />
                      Tokens: <strong>{llmResult.tokens_in} in / {llmResult.tokens_out} out</strong>
                    </span>

                    <span className="inline-flex items-center gap-1.5 text-[11px] font-mono text-slate-500 bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded-lg">
                      Model: {llmResult.model_used}
                    </span>
                  </div>

                  {llmResult.error && (
                    <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-xs font-mono">
                      {llmResult.error}
                    </div>
                  )}

                  {llmResult.content && (
                    <div className="relative rounded-2xl bg-slate-50 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 p-4">
                      <button
                        type="button"
                        onClick={() => copyResponseText(llmResult.content)}
                        className="absolute right-3 top-3 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded-lg bg-white/60 dark:bg-slate-900/60"
                        title="Copy Response"
                      >
                        {copiedResponse ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
                      </button>
                      <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2">
                        Buddy AI Tutor Response:
                      </h4>
                      <p className="text-xs sm:text-sm text-slate-800 dark:text-slate-200 leading-relaxed whitespace-pre-wrap">
                        {llmResult.content}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* RAG Retrieval Evaluation Box */}
          <div className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4 shadow-sm">
            <div className="border-b border-slate-200 dark:border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wide flex items-center gap-2">
                <Search className="w-4 h-4 text-blue-600" />
                RAG Curriculum Textbook Retrieval Evaluation
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Test how the vector knowledge base indexes and retrieves NCTB textbooks with printed page citations.
              </p>
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                value={ragQuery}
                onChange={(e) => setRagQuery(e.target.value)}
                placeholder="Enter a curriculum topic query..."
                className="flex-1 px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs focus:ring-2 focus:ring-blue-500 outline-none"
              />
              <button
                type="button"
                onClick={handleTestRAG}
                disabled={testingRAG}
                className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-sm transition-colors shrink-0 disabled:opacity-50"
              >
                {testingRAG ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                Search Chunks
              </button>
            </div>

            {ragResult && (
              <div className="space-y-3 pt-2">
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span>
                    Confidence Score: <strong className="text-blue-600 font-mono">{(ragResult.confidence * 100).toFixed(1)}%</strong>
                  </span>
                  <span className="text-slate-500 font-mono text-[11px]">
                    Latency: {ragResult.latency_ms}ms • Retrieved: {ragResult.chunks.length} chunks
                  </span>
                </div>

                <div className="space-y-2.5">
                  {ragResult.chunks.map((chunk, idx) => (
                    <div
                      key={chunk.chunk_id || idx}
                      className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 text-xs space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                          <BookOpen className="w-3.5 h-3.5 text-blue-500" />
                          {chunk.book_title} — {chunk.chapter_title}
                        </span>
                        <span className="font-mono text-[11px] bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300 px-2 py-0.5 rounded-md font-bold">
                          Printed Page {chunk.printed_page}
                        </span>
                      </div>
                      <p className="text-slate-600 dark:text-slate-300 leading-relaxed font-serif text-[11px]">
                        &quot;{chunk.snippet}&quot;
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: KNOWLEDGE BASE STATS */}
      {activeTab === "stats" && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
            <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-1">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Total Textbooks</div>
              <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">{stats?.total_books ?? 0}</div>
              <div className="text-[10px] text-emerald-600 font-semibold">NCTB Curriculum</div>
            </div>

            <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-1">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Chapters Mapped</div>
              <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">{stats?.total_chapters ?? 0}</div>
              <div className="text-[10px] text-blue-600 font-semibold">Class 6 to 10</div>
            </div>

            <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-1">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Vector Chunks</div>
              <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">{stats?.total_chunks ?? 0}</div>
              <div className="text-[10px] text-indigo-600 font-semibold">pgvector Indexed</div>
            </div>

            <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-1">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Chat Sessions</div>
              <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">{stats?.total_chat_sessions ?? 0}</div>
              <div className="text-[10px] text-purple-600 font-semibold">Student Inquiries</div>
            </div>

            <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-1">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Total Messages</div>
              <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">{stats?.total_chat_messages ?? 0}</div>
              <div className="text-[10px] text-teal-600 font-semibold">AI Explanations</div>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4 shadow-sm">
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wide">
              How Buddy AI Tutor & RAG Citations Work
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-slate-600 dark:text-slate-300">
              <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60 space-y-2">
                <div className="font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                  <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px]">1</span>
                  Hybrid Semantic Retrieval
                </div>
                <p className="leading-relaxed">
                  When a student asks a study question, pgvector runs dense embeddings (BGE-M3) + sparse keyword search over authoritative NCTB textbooks.
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60 space-y-2">
                <div className="font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                  <span className="w-5 h-5 rounded-full bg-indigo-600 text-white flex items-center justify-center text-[10px]">2</span>
                  Printed Page Grounding
                </div>
                <p className="leading-relaxed">
                  Citations are strictly bound to printed page numbers (Rule 8: printed page ≠ PDF index), ensuring students can match the textbook in their hands.
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60 space-y-2">
                <div className="font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                  <span className="w-5 h-5 rounded-full bg-purple-600 text-white flex items-center justify-center text-[10px]">3</span>
                  OpenRouter / LLM Generation
                </div>
                <p className="leading-relaxed">
                  The active LLM receives the grounded chunks and generates an encouraging, pedagogically sound explanation in natural Bangla and English.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
