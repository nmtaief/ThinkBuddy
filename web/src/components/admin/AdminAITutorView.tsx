"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Sparkles,
  Key,
  Database,
  Send,
  BookOpen,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Eye,
  EyeOff,
  Zap,
  Layers,
  MessageSquare,
  ShieldCheck,
} from "lucide-react";

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

export const AdminAITutorView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"llm" | "rag" | "diagnostics" | "stats">("llm");
  const [config, setConfig] = useState<AITutorConfig | null>(null);
  const [stats, setStats] = useState<RAGStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Form Fields
  const [llmProvider, setLlmProvider] = useState<string>("gemini");
  const [apiKey, setApiKey] = useState<string>("");
  const [showApiKey, setShowApiKey] = useState<boolean>(false);
  const [apiBase, setApiBase] = useState<string>("");
  const [primaryModel, setPrimaryModel] = useState<string>("gemini/gemini-1.5-flash");
  const [fallbackModel, setFallbackModel] = useState<string>("openai/gpt-4o-mini");
  const [temperature, setTemperature] = useState<number>(0.3);
  const [systemPrompt, setSystemPrompt] = useState<string>("");

  const [embeddingProvider, setEmbeddingProvider] = useState<string>("bge-m3");
  const [embeddingApiKey, setEmbeddingApiKey] = useState<string>("");
  const [showEmbeddingApiKey, setShowEmbeddingApiKey] = useState<boolean>(false);
  const [embeddingModel, setEmbeddingModel] = useState<string>("bge-m3");
  const [embeddingDimensions, setEmbeddingDimensions] = useState<number>(1024);
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(0.45);
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
    latency_ms: number;
    tokens_in: number;
    tokens_out: number;
    model_used: string;
    error: string | null;
  } | null>(null);

  const [ragQuery, setRagQuery] = useState<string>("সালোকসংশ্লেষণ কি এবং উদ্ভিদে এটি কীভাবে ঘটে?");
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
        setApiBase(data.api_base || "");
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

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-slate-500">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-600 mb-2" />
        <p className="text-sm">Loading AI Tutor & RAG settings...</p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-6">
      {/* Top Banner */}
      <div className="bg-gradient-to-r from-blue-700 via-indigo-700 to-slate-900 rounded-2xl p-6 text-white shadow-lg">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-white/10 backdrop-blur-md flex items-center justify-center border border-white/20">
              <Sparkles className="w-6 h-6 text-yellow-300" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Buddy AI Tutor & RAG Admin Panel</h1>
              <p className="text-xs sm:text-sm text-blue-100/80">
                Configure LLM APIs, knowledge retrieval, and NCTB curriculum grounding.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 bg-white/10 px-3 py-1.5 rounded-full border border-white/20 text-xs">
            <span className={`w-2.5 h-2.5 rounded-full ${isEnabled ? "bg-emerald-400 animate-pulse" : "bg-rose-400"}`} />
            <span>{isEnabled ? "AI Tutor Active" : "Tutor Paused"}</span>
          </div>
        </div>

        {/* Quick Meta Stats */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6 pt-5 border-t border-white/15 text-xs">
            <div>
              <span className="text-blue-200 block">Indexed Textbooks</span>
              <span className="text-lg font-bold">{stats.total_books} Books</span>
            </div>
            <div>
              <span className="text-blue-200 block">Curriculum Chunks</span>
              <span className="text-lg font-bold">{stats.total_chunks} Chunks</span>
            </div>
            <div>
              <span className="text-blue-200 block">Active LLM Model</span>
              <span className="text-sm font-semibold truncate block">{stats.active_primary_model}</span>
            </div>
            <div>
              <span className="text-blue-200 block">Embedding Model</span>
              <span className="text-sm font-semibold truncate block">{stats.active_embedding_provider}</span>
            </div>
          </div>
        )}
      </div>

      {/* Alert Messages */}
      {saveSuccess && (
        <div className="flex items-center gap-2 p-4 bg-emerald-50 text-emerald-800 rounded-xl border border-emerald-200 text-sm">
          <CheckCircle className="w-5 h-5 flex-shrink-0 text-emerald-600" />
          <span>{saveSuccess}</span>
        </div>
      )}
      {saveError && (
        <div className="flex items-center gap-2 p-4 bg-rose-50 text-rose-800 rounded-xl border border-rose-200 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-600" />
          <span>{saveError}</span>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 gap-2 sm:gap-4 overflow-x-auto">
        <button
          onClick={() => setActiveTab("llm")}
          className={`flex items-center gap-2 pb-3 px-2 border-b-2 font-medium text-sm transition-colors whitespace-nowrap ${
            activeTab === "llm"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <Key className="w-4 h-4" />
          Buddy LLM & API Key
        </button>
        <button
          onClick={() => setActiveTab("rag")}
          className={`flex items-center gap-2 pb-3 px-2 border-b-2 font-medium text-sm transition-colors whitespace-nowrap ${
            activeTab === "rag"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <Database className="w-4 h-4" />
          RAG & Vector Retrieval
        </button>
        <button
          onClick={() => setActiveTab("diagnostics")}
          className={`flex items-center gap-2 pb-3 px-2 border-b-2 font-medium text-sm transition-colors whitespace-nowrap ${
            activeTab === "diagnostics"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <Zap className="w-4 h-4" />
          Diagnostics & Testing
        </button>
        <button
          onClick={() => setActiveTab("stats")}
          className={`flex items-center gap-2 pb-3 px-2 border-b-2 font-medium text-sm transition-colors whitespace-nowrap ${
            activeTab === "stats"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <Layers className="w-4 h-4" />
          Knowledge Base Stats
        </button>
      </div>

      {/* Tab 1: LLM & Buddy API Settings */}
      {activeTab === "llm" && (
        <form onSubmit={handleSave} className="space-y-6">
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm space-y-6">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
              <Key className="w-5 h-5 text-blue-600" />
              LLM Provider & API Credentials
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              {/* Provider Selection */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                  LLM Provider
                </label>
                <select
                  value={llmProvider}
                  onChange={(e) => {
                    const p = e.target.value;
                    setLlmProvider(p);
                    if (p === "gemini") setPrimaryModel("gemini/gemini-1.5-flash");
                    else if (p === "openai") setPrimaryModel("openai/gpt-4o-mini");
                    else if (p === "anthropic") setPrimaryModel("anthropic/claude-3-5-sonnet");
                    else if (p === "groq") setPrimaryModel("groq/llama-3.3-70b-versatile");
                    else if (p === "ollama") setPrimaryModel("ollama/llama3");
                  }}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  <option value="gemini">Google Gemini (Recommended for Bangla & Speed)</option>
                  <option value="openai">OpenAI (GPT-4o / GPT-4o-mini)</option>
                  <option value="anthropic">Anthropic (Claude 3.5 Sonnet / Haiku)</option>
                  <option value="groq">Groq (Ultra-fast Llama 3.3)</option>
                  <option value="ollama">Ollama / Local vLLM Inference</option>
                  <option value="custom">Custom OpenAI-Compatible API</option>
                </select>
              </div>

              {/* API Key */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                  API Key
                  {config?.has_api_key && (
                    <span className="ml-2 text-emerald-600 text-[11px] font-normal">
                      (Configured: {config.api_key_masked})
                    </span>
                  )}
                </label>
                <div className="relative">
                  <input
                    type={showApiKey ? "text" : "password"}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder={config?.has_api_key ? "Leave blank to keep existing key" : "Paste API Key (e.g. AIzaSy... or sk-...)"}
                    className="w-full pl-3.5 pr-10 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="absolute right-3 top-3 text-slate-400 hover:text-slate-600"
                  >
                    {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Primary Model */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                  Primary Generation Model
                </label>
                <input
                  type="text"
                  value={primaryModel}
                  onChange={(e) => setPrimaryModel(e.target.value)}
                  placeholder="e.g. gemini/gemini-1.5-flash or openai/gpt-4o-mini"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-blue-500 outline-none font-mono text-xs"
                />
              </div>

              {/* Fallback Model */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                  Fallback Model (Automatic Retry on Outage)
                </label>
                <input
                  type="text"
                  value={fallbackModel}
                  onChange={(e) => setFallbackModel(e.target.value)}
                  placeholder="e.g. openai/gpt-4o-mini"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-blue-500 outline-none font-mono text-xs"
                />
              </div>

              {/* Custom API Base URL */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                  Custom Base URL (Optional)
                </label>
                <input
                  type="text"
                  value={apiBase}
                  onChange={(e) => setApiBase(e.target.value)}
                  placeholder="http://localhost:11434/v1 (for Ollama) or custom proxy"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-blue-500 outline-none text-xs"
                />
              </div>

              {/* Temperature */}
              <div>
                <div className="flex justify-between items-center mb-1.5">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Temperature (Creativity vs Accuracy)
                  </label>
                  <span className="text-xs font-mono text-blue-600 font-bold">{temperature}</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full accent-blue-600"
                />
                <div className="flex justify-between text-[10px] text-slate-400 mt-1">
                  <span>0.0 (Strict / Deterministic)</span>
                  <span>0.3 (Recommended for NCTB)</span>
                  <span>1.0 (Creative)</span>
                </div>
              </div>
            </div>

            {/* Persona & System Prompt */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Buddy&apos;s Persona & System Prompt Instructions
              </label>
              <textarea
                rows={4}
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                placeholder="Custom instruction prompt for Buddy the AI Tutor..."
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs focus:ring-2 focus:ring-blue-500 outline-none leading-relaxed"
              />
              <p className="text-[11px] text-slate-400 mt-1">
                Controls tone, language policy (natural Bangla & English), and adherence to cited textbook pages.
              </p>
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <button
              type="submit"
              disabled={saving}
              className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium text-sm shadow-md transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
              Save & Activate LLM Settings
            </button>
          </div>
        </form>
      )}

      {/* Tab 2: RAG & Vector Retrieval Settings */}
      {activeTab === "rag" && (
        <form onSubmit={handleSave} className="space-y-6">
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm space-y-6">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
              <Database className="w-5 h-5 text-indigo-600" />
              RAG & Multilingual Vector Retrieval
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              {/* Embedding Provider */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                  Embedding Provider
                </label>
                <select
                  value={embeddingProvider}
                  onChange={(e) => setEmbeddingProvider(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  <option value="bge-m3">BAAI/bge-m3 (Recommended SOTA for Bengali & English)</option>
                  <option value="openai">OpenAI (text-embedding-3-small)</option>
                  <option value="gemini">Google (text-embedding-004)</option>
                  <option value="hosted">Generic Hosted / HuggingFace Endpoint</option>
                  <option value="mock">Mock Embeddings (Fast Offline Dev)</option>
                </select>
              </div>

              {/* Embedding API Key */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                  Embedding API Key (Optional for Hosted)
                  {config?.has_embedding_api_key && (
                    <span className="ml-2 text-emerald-600 text-[11px] font-normal">
                      (Configured: {config.embedding_api_key_masked})
                    </span>
                  )}
                </label>
                <div className="relative">
                  <input
                    type={showEmbeddingApiKey ? "text" : "password"}
                    value={embeddingApiKey}
                    onChange={(e) => setEmbeddingApiKey(e.target.value)}
                    placeholder="Leave blank to use primary LLM key or self-hosted"
                    className="w-full pl-3.5 pr-10 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => setShowEmbeddingApiKey(!showEmbeddingApiKey)}
                    className="absolute right-3 top-3 text-slate-400 hover:text-slate-600"
                  >
                    {showEmbeddingApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Model Identifier */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                  Embedding Model
                </label>
                <input
                  type="text"
                  value={embeddingModel}
                  onChange={(e) => setEmbeddingModel(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-blue-500 outline-none font-mono text-xs"
                />
              </div>

              {/* Vector Dimensions */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                  Vector Dimensions
                </label>
                <input
                  type="number"
                  value={embeddingDimensions}
                  onChange={(e) => setEmbeddingDimensions(parseInt(e.target.value) || 1024)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-blue-500 outline-none font-mono text-xs"
                />
              </div>

              {/* Confidence Threshold */}
              <div>
                <div className="flex justify-between items-center mb-1.5">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Minimum Retrieval Confidence Gate
                  </label>
                  <span className="text-xs font-mono text-indigo-600 font-bold">{confidenceThreshold}</span>
                </div>
                <input
                  type="range"
                  min="0.1"
                  max="0.9"
                  step="0.05"
                  value={confidenceThreshold}
                  onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
                  className="w-full accent-indigo-600"
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  Queries below this score trigger cautious fallback rather than hallucinations.
                </p>
              </div>

              {/* Max Chunks */}
              <div>
                <div className="flex justify-between items-center mb-1.5">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Max Authoritative Chunks per Prompt
                  </label>
                  <span className="text-xs font-mono text-indigo-600 font-bold">{maxChunks} chunks</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="8"
                  step="1"
                  value={maxChunks}
                  onChange={(e) => setMaxChunks(parseInt(e.target.value))}
                  className="w-full accent-indigo-600"
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  Top NCTB textbook excerpts provided to Buddy for precise answers.
                </p>
              </div>
            </div>

            {/* Global Activation Toggle */}
            <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <div>
                <span className="text-sm font-semibold text-slate-900 dark:text-white block">
                  Enable Buddy AI Tutor Chat
                </span>
                <span className="text-xs text-slate-500">
                  Allow students to interact with the AI tutor across mobile and web apps.
                </span>
              </div>
              <button
                type="button"
                onClick={() => setIsEnabled(!isEnabled)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  isEnabled ? "bg-blue-600" : "bg-slate-300 dark:bg-slate-700"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    isEnabled ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <button
              type="submit"
              disabled={saving}
              className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-medium text-sm shadow-md transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
              Save & Activate RAG Settings
            </button>
          </div>
        </form>
      )}

      {/* Tab 3: Diagnostics & Testing */}
      {activeTab === "diagnostics" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Test LLM API */}
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm space-y-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-semibold text-slate-900 dark:text-white flex items-center gap-2 text-sm">
                  <Zap className="w-4 h-4 text-amber-500" />
                  Test LLM API Connectivity
                </h3>
                <span className="text-xs text-slate-400 font-mono">{primaryModel}</span>
              </div>
              <p className="text-xs text-slate-500 mb-3">
                Send a real-time prompt to verify that your configured API credentials and model respond correctly.
              </p>
              <textarea
                rows={3}
                value={testPrompt}
                onChange={(e) => setTestPrompt(e.target.value)}
                className="w-full p-3 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>

            <div className="space-y-4">
              <button
                type="button"
                onClick={handleTestLLM}
                disabled={testingLLM}
                className="w-full py-2.5 bg-amber-500 hover:bg-amber-600 text-white rounded-xl font-medium text-xs shadow-sm transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {testingLLM ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                Run Live LLM Test
              </button>

              {llmResult && (
                <div
                  className={`p-4 rounded-xl border text-xs space-y-2 ${
                    llmResult.success
                      ? "bg-slate-50 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700"
                      : "bg-rose-50 border-rose-200 text-rose-800"
                  }`}
                >
                  <div className="flex items-center justify-between font-mono text-[11px] text-slate-500 pb-2 border-b border-slate-200 dark:border-slate-700">
                    <span>Latency: {llmResult.latency_ms} ms</span>
                    <span>Tokens: {llmResult.tokens_in} in / {llmResult.tokens_out} out</span>
                  </div>
                  {llmResult.success ? (
                    <div className="text-slate-800 dark:text-slate-200 whitespace-pre-wrap leading-relaxed">
                      {llmResult.content}
                    </div>
                  ) : (
                    <div className="text-rose-600 font-mono">
                      Error: {llmResult.error}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Test RAG Retrieval */}
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm space-y-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-semibold text-slate-900 dark:text-white flex items-center gap-2 text-sm">
                  <Database className="w-4 h-4 text-blue-500" />
                  Test NCTB Textbook RAG Retrieval
                </h3>
                <span className="text-xs text-slate-400 font-mono">Top {maxChunks} Chunks</span>
              </div>
              <p className="text-xs text-slate-500 mb-3">
                Enter a curriculum study question to verify chunk retrieval and printed page accuracy.
              </p>
              <input
                type="text"
                value={ragQuery}
                onChange={(e) => setRagQuery(e.target.value)}
                placeholder="Ask textbook question..."
                className="w-full p-3 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>

            <div className="space-y-4">
              <button
                type="button"
                onClick={handleTestRAG}
                disabled={testingRAG}
                className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium text-xs shadow-sm transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {testingRAG ? <RefreshCw className="w-4 h-4 animate-spin" /> : <BookOpen className="w-4 h-4" />}
                Search Curriculum Chunks
              </button>

              {ragResult && (
                <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/60 text-xs space-y-3 max-h-[260px] overflow-y-auto">
                  <div className="flex items-center justify-between text-[11px] font-mono text-slate-500 border-b border-slate-200 dark:border-slate-700 pb-2">
                    <span>Confidence: {(ragResult.confidence * 100).toFixed(1)}%</span>
                    <span>Search Latency: {ragResult.latency_ms} ms</span>
                  </div>
                  {ragResult.chunks.length === 0 ? (
                    <p className="text-slate-400 italic">No textbook chunks matched this query.</p>
                  ) : (
                    ragResult.chunks.map((c, i) => (
                      <div key={c.chunk_id || i} className="p-2.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 space-y-1">
                        <div className="flex items-center justify-between text-[11px] font-semibold text-blue-600 dark:text-blue-400">
                          <span>{c.book_title} — {c.chapter_title}</span>
                          <span className="bg-blue-50 dark:bg-blue-900/30 px-2 py-0.5 rounded text-[10px]">
                            Printed Page {c.printed_page}
                          </span>
                        </div>
                        <p className="text-slate-600 dark:text-slate-300 text-[11px] line-clamp-3">
                          {c.snippet}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Knowledge Base Stats */}
      {activeTab === "stats" && stats && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
            <div className="p-6 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-blue-50 dark:bg-blue-950/50 text-blue-600 flex items-center justify-center">
                <BookOpen className="w-6 h-6" />
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Total Textbooks</span>
                <span className="text-2xl font-bold text-slate-900 dark:text-white">{stats.total_books}</span>
                <span className="text-[11px] text-slate-400 block">{stats.total_chapters} Total Chapters</span>
              </div>
            </div>

            <div className="p-6 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 flex items-center justify-center">
                <Database className="w-6 h-6" />
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Vector Store Chunks</span>
                <span className="text-2xl font-bold text-slate-900 dark:text-white">{stats.total_chunks}</span>
                <span className="text-[11px] text-emerald-600 block">Active in pgvector</span>
              </div>
            </div>

            <div className="p-6 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 flex items-center justify-center">
                <MessageSquare className="w-6 h-6" />
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Tutor Conversations</span>
                <span className="text-2xl font-bold text-slate-900 dark:text-white">{stats.total_chat_sessions}</span>
                <span className="text-[11px] text-slate-400 block">{stats.total_chat_messages} Messages Served</span>
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm space-y-4">
            <h3 className="font-semibold text-slate-900 dark:text-white text-sm flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              System Architecture & Grounding Invariants
            </h3>
            <ul className="text-xs text-slate-600 dark:text-slate-300 space-y-2 list-disc pl-5">
              <li>
                <strong>Standing Rule 7:</strong> Every answer produced by Buddy carries textbook, chapter, and page citations. Low confidence queries refuse rather than hallucinate.
              </li>
              <li>
                <strong>Standing Rule 8:</strong> Printed page number (displayed to students) is strictly separated from internal PDF page offsets.
              </li>
              <li>
                <strong>Standing Rule 6 & 18:</strong> Buddy is locked out during active student quizzes to preserve academic integrity.
              </li>
              <li>
                <strong>Standing Rule 15:</strong> LLM API keys and secrets are never stored in browser client storage or logged in plaintext.
              </li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};
