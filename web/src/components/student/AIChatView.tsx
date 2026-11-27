"use client";

import React, { useState, useRef, useEffect } from "react";
import { ChatMessage, ChatCitation } from "@/lib/types";
import { Language, translations, toBengaliDigits } from "@/lib/i18n";
import { MathRenderer } from "@/components/MathRenderer";
import { ThinkBuddyMascot, StaticMascotAvatar, MascotState } from "@/components/student/ThinkBuddyMascot";
import { useVoiceBuddy } from "@/hooks/useVoiceBuddy";
import {
  analyzeEnglishWriting,
  enqueueVocabWordIntoRevision,
  isEnglishWritingSubmission,
  EnglishWritingFeedback,
  VocabularyUpgrade,
} from "@/lib/english-writing-tutor";
import {
  Send,
  StopCircle,
  BookOpen,
  Bot,
  User,
  Camera,
  RotateCcw,
  Sparkles,
  X,
  PenTool,
  Check,
  BookmarkPlus,
  ArrowRight,
  Award,
  Mic,
  Square,
  Volume2,
  VolumeX,
} from "lucide-react";

interface AIChatViewProps {
  lang: Language;
}

const STARTER_CHIPS = [
  { label: "অনুশীলনী ১ এর ৩ নং সমাধান", query: "Class 8 math boi er chapter 1 er 3 no kore deo" },
  { label: "অধ্যায় ১ (প্যাটার্ন) বুঝিয়ে দাও", query: "Class 8 math অধ্যায় ১ প্যাটার্ন এর মূল বিষয়গুলো সহজ করে বুঝিয়ে দাও" },
  { label: "এসএসসি গণিত বই কি আছে?", query: "Ssc books?" },
  { label: "গণিতে কীভাবে ভালো করব?", query: "How can I improve my maths?" },
];

const ENGLISH_STARTER_CHIPS = [
  {
    label: "A Rainy Day (Paragraph Review)",
    query: "A rainy day is very good. It rains heavy all day. The roads are full of big water and people cannot go outside easily. It is hard for poor people.",
  },
  {
    label: "Tree Plantation (Essay Feedback)",
    query: "Trees are very important for our life. They help us in many ways and give oxygen. Deforestation is a very bad problem.",
  },
  {
    label: "My Aim in Life (Vocab Upgrade)",
    query: "My aim in life is to be a doctor. It is a hard profession but I want to help many poor people and make them happy.",
  },
];

export const AIChatView: React.FC<AIChatViewProps> = ({ lang }) => {
  const t = translations[lang];

  const [chatMode, setChatMode] = useState<"curriculum" | "english_writing">("curriculum");
  const [savedVocabWords, setSavedVocabWords] = useState<Record<string, boolean>>({});
  const [selectedClass, setSelectedClass] = useState<number>(8);
  const [selectedProvider, setSelectedProvider] = useState<"gemini" | "deepseek" | "claude">("gemini");
  const [toolStatus, setToolStatus] = useState<string | null>(null);
  const [buddyVoiceEnabled, setBuddyVoiceEnabled] = useState<boolean>(true);
  const [showMascot, setShowMascot] = useState<boolean>(true);
  const [autoSendVoice, setAutoSendVoice] = useState<boolean>(false);
  const [justCompleted, setJustCompleted] = useState<boolean>(false);

  const voice = useVoiceBuddy({
    onTranscriptUpdate: (txt) => setInput(txt),
    autoSend: autoSendVoice,
  });
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "m_welcome",
      sender: "assistant",
      text:
        lang === "bn"
          ? "নমস্কার! আমি বাডি (Buddy), তোমার ThinkBuddy এআই পড়াশোনার সহায়ক। তোমার পাঠ্যবইয়ের যেকোনো অঙ্ক, অধ্যায় বা পড়াশোনা নিয়ে আমাকে প্রশ্ন করতে পারো!"
          : "Hello! I am Buddy, your ThinkBuddy AI study companion. Ask me any question about your curriculum textbook, chapters, or exercises!",
      timestamp: "2026-11-11T00:00:00.000Z",
    },
  ]);
  const [chatSessionId, setChatSessionId] = useState<string>("");
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [attachedImage, setAttachedImage] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const latestAssistantRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const lastMsg = messages[messages.length - 1];
    if (lastMsg && lastMsg.sender === "assistant") {
      // Scroll to top of newest assistant reply so student reads from the beginning
      latestAssistantRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    } else {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length]);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  // Image compression utility
  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement("canvas");
        const maxDim = 1024;
        let width = img.width;
        let height = img.height;

        if (width > maxDim || height > maxDim) {
          if (width > height) {
            height = Math.round((height * maxDim) / width);
            width = maxDim;
          } else {
            width = Math.round((width * maxDim) / height);
            height = maxDim;
          }
        }

        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.drawImage(img, 0, 0, width, height);
          const compressed = canvas.toDataURL("image/jpeg", 0.8);
          setAttachedImage(compressed);
        }
      };
      if (typeof event.target?.result === "string") {
        img.src = event.target.result;
      }
    };
    reader.readAsDataURL(file);
    // Reset file input
    e.target.value = "";
  };

  const handleSend = async (overrideText?: string, explicitRetryId?: string) => {
    let queryToSend = overrideText || input.trim();
    if ((!queryToSend && !attachedImage) || isStreaming) return;

    // If user clicked Retry or typed a retry trigger, resolve to the original question
    const retryKeywords = ["try again", "retry", "আবার চেষ্টা করো", "আবার চেষ্টা কর", "আবার বলো", "আবার বলো তো"];
    const textLower = queryToSend.trim().toLowerCase();
    const isRetry = retryKeywords.some((kw) => textLower === kw || textLower.startsWith(kw));

    let retryIdToSend = explicitRetryId;
    if (isRetry) {
      const prevQuery = findLastUserQuery();
      if (prevQuery) {
        queryToSend = prevQuery;
      }
      if (!retryIdToSend) {
        for (let i = messages.length - 1; i >= 0; i--) {
          if (messages[i].sender === "assistant" && messages[i].retryMessageId) {
            retryIdToSend = messages[i].retryMessageId;
            break;
          }
        }
      }
    }

    if (!overrideText) {
      setInput("");
    }
    setErrorBanner(null);

    const currentImg = attachedImage;
    setAttachedImage(null);

    const userMessage: ChatMessage = {
      id: `u_${Date.now()}`,
      sender: "user",
      text: queryToSend || (lang === "bn" ? "[ছবি সংযুক্ত করা হয়েছে]" : "[Image attached]"),
      timestamp: new Date().toISOString(),
    };

    const assistantMessageId = `a_${Date.now()}`;
    const isWritingMode = chatMode === "english_writing" || isEnglishWritingSubmission(queryToSend);
    let writingEval: EnglishWritingFeedback | undefined = undefined;
    if (isWritingMode && queryToSend.trim().split(/\s+/).length >= 5) {
      writingEval = analyzeEnglishWriting(queryToSend);
    }

    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      sender: "assistant",
      text: "",
      isStreaming: true,
      timestamp: new Date().toISOString(),
      citations: [],
      writingFeedback: writingEval,
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setIsStreaming(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept-Language": lang },
        body: JSON.stringify({
          session_id: chatSessionId || undefined,
          message: queryToSend,
          class_override: selectedClass,
          image_data: currentImg || undefined,
          retry_message_id: retryIdToSend || undefined,
          provider: selectedProvider,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      if (!response.body) {
        throw new Error("No readable stream received");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const block of lines) {
          if (!block.trim()) continue;

          let eventType = "message";
          let dataStr = "";

          const blockLines = block.split("\n");
          for (const line of blockLines) {
            if (line.startsWith("event: ")) {
              eventType = line.substring(7).trim();
            } else if (line.startsWith("data: ")) {
              dataStr = line.substring(6).trim();
            }
          }

          if (dataStr) {
            try {
              const data = JSON.parse(dataStr);

              if (eventType === "meta") {
                if (data.session_id) setChatSessionId(data.session_id);
              } else if (eventType === "status") {
                if (data.status) setToolStatus(data.status);
              } else if (eventType === "token") {
                setToolStatus(null);
                const deltaText = data.text || data.delta || "";
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, text: msg.text + deltaText }
                      : msg
                  )
                );
              } else if (eventType === "citation") {
                const citation: ChatCitation = {
                  book_title: data.book_title,
                  chapter_title: data.chapter_title,
                  printed_page: data.printed_page,
                  snippet: data.snippet,
                };
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? {
                          ...msg,
                          citations: [...(msg.citations || []), citation],
                        }
                      : msg
                  )
                );
              } else if (eventType === "done") {
                setToolStatus(null);
              } else if (eventType === "error") {
                setToolStatus(null);
                const rawMsg = data.message || "";
                const retryMsgId = data.retry_message_id;
                const isTechnical =
                  !rawMsg ||
                  rawMsg.includes("অ্যাডমিন") ||
                  rawMsg.includes("Admin") ||
                  rawMsg.includes("admin") ||
                  rawMsg.includes("API") ||
                  rawMsg.includes("api") ||
                  rawMsg.includes("HTTP") ||
                  rawMsg.includes("500") ||
                  rawMsg.includes("503");
                const errorMsg = isTechnical
                  ? (lang === "bn" ? "একটু সমস্যা হয়েছে, আবার চেষ্টা করো" : "Something went wrong, please try again.")
                  : rawMsg;
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? {
                          ...msg,
                          text: errorMsg,
                          citations: [],
                          retryMessageId: retryMsgId,
                          isError: true,
                        }
                      : msg
                  )
                );
              }
            } catch {
              // Ignore partial JSON
            }
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error)?.name !== "AbortError") {
        const errorMsg = lang === "bn" ? "একটু সমস্যা হয়েছে, আবার চেষ্টা করো" : "Something went wrong, please try again.";
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  text: errorMsg,
                  citations: [],
                }
              : msg
          )
        );
      }
    } finally {
      setIsStreaming(false);
      setToolStatus(null);
      abortControllerRef.current = null;
      setMessages((prev) =>
        prev.map((msg) => (msg.id === assistantMessageId ? { ...msg, isStreaming: false } : msg))
      );
    }
  };

  const handleCancel = () => {
    abortControllerRef.current?.abort();
    setIsStreaming(false);
  };

  const findLastUserQuery = (): string => {
    const retryKeywords = ["try again", "retry", "আবার চেষ্টা করো", "আবার চেষ্টা কর", "আবার বলো", "আবার বলো তো"];
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].sender === "user" && messages[i].text) {
        const textLower = messages[i].text.trim().toLowerCase();
        if (!retryKeywords.some((kw) => textLower === kw || textLower.startsWith(kw))) {
          return messages[i].text;
        }
      }
    }
    return "";
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "calc(100dvh - 120px)",
        maxHeight: "880px",
        width: "100%",
        backgroundColor: "var(--color-surface)",
        borderRadius: "var(--radius-lg)",
        border: "1px solid var(--color-border)",
        overflow: "hidden",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {/* Header Bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "var(--space-3) var(--space-4)",
          borderBottom: "1px solid var(--color-border)",
          backgroundColor: "var(--color-surface-hover)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: "var(--radius-full)",
              backgroundColor: "var(--color-primary-surface)",
              color: "var(--color-primary)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Bot size={18} />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <h2 style={{ fontSize: "var(--text-base)", fontWeight: 600, color: "var(--color-text-primary)" }}>
                {lang === "bn" ? "সহায়ক এআই (বাডি)" : "AI Tutor (Buddy)"}
              </h2>
              <span style={{ fontSize: "10px", color: "var(--color-text-muted)", padding: "1px 6px", borderRadius: 4, backgroundColor: "var(--color-border)" }}>
                v1.0.0 (Math Engine v2)
              </span>
            </div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              {lang === "bn" ? "এনসিটিবি পাঠ্যবই সহায়ক" : "NCTB Curriculum Study Companion"}
            </div>
          </div>
        </div>

        {/* Mode Switcher & Class Selector */}
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flexWrap: "wrap" }}>
          {/* Mode Switcher */}
          <div
            style={{
              display: "flex",
              backgroundColor: "var(--color-surface)",
              padding: 2,
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border)",
            }}
          >
            <button
              onClick={() => setChatMode("curriculum")}
              style={{
                padding: "4px 10px",
                borderRadius: 4,
                border: "none",
                fontSize: "11px",
                fontWeight: 600,
                cursor: "pointer",
                backgroundColor: chatMode === "curriculum" ? "var(--color-primary)" : "transparent",
                color: chatMode === "curriculum" ? "#fff" : "var(--color-text-secondary)",
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              <Bot size={13} />
              <span>{lang === "bn" ? "পাঠ্যবই বাডি" : "Curriculum Buddy"}</span>
            </button>
            <button
              onClick={() => setChatMode("english_writing")}
              style={{
                padding: "4px 10px",
                borderRadius: 4,
                border: "none",
                fontSize: "11px",
                fontWeight: 600,
                cursor: "pointer",
                backgroundColor: chatMode === "english_writing" ? "var(--color-primary)" : "transparent",
                color: chatMode === "english_writing" ? "#fff" : "var(--color-text-secondary)",
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              <PenTool size={13} />
              <span>{lang === "bn" ? "English Writing & Vocab" : "Writing & Vocab"}</span>
            </button>
          </div>

          {/* Class Switcher Selector */}
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <label style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 500 }}>
              {lang === "bn" ? "শ্রেণি:" : "Class:"}
            </label>
            <select
              value={selectedClass}
              onChange={(e) => setSelectedClass(parseInt(e.target.value, 10))}
              style={{
                fontSize: "var(--text-xs)",
                padding: "4px 8px",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--color-border)",
                backgroundColor: "var(--color-surface)",
              color: "var(--color-text-primary)",
              cursor: "pointer",
            }}
          >
            <option value={6}>{lang === "bn" ? "৬ষ্ঠ শ্রেণি" : "Class 6"}</option>
            <option value={7}>{lang === "bn" ? "৭ম শ্রেণি" : "Class 7"}</option>
            <option value={8}>{lang === "bn" ? "৮ম শ্রেণি" : "Class 8"}</option>
            <option value={9}>{lang === "bn" ? "৯ম শ্রেণি (SSC)" : "Class 9 (SSC)"}</option>
            <option value={10}>{lang === "bn" ? "১০ম শ্রেণি (SSC)" : "Class 10 (SSC)"}</option>
          </select>

          {/* Multi-Provider LLM Selector */}
          <select
            aria-label="LLM Provider"
            value={selectedProvider}
            onChange={(e) => setSelectedProvider(e.target.value as "gemini" | "deepseek" | "claude")}
            style={{
              fontSize: "var(--text-xs)",
              padding: "4px 8px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-surface)",
              color: "var(--color-text-primary)",
              cursor: "pointer",
            }}
          >
            <option value="gemini">Gemini</option>
            <option value="deepseek">DeepSeek</option>
            <option value="claude">Claude</option>
          </select>

          <button
            type="button"
            onClick={() => {
              if (voice.isSpeaking) voice.stopSpeaking();
              setBuddyVoiceEnabled((v) => !v);
            }}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              fontSize: "var(--text-xs)",
              padding: "4px 8px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border)",
              backgroundColor: buddyVoiceEnabled ? "rgba(16, 185, 129, 0.12)" : "var(--color-surface)",
              color: "var(--color-text-primary)",
              cursor: "pointer",
            }}
            title="Toggle Buddy Voice"
          >
            {buddyVoiceEnabled ? <Volume2 size={14} /> : <VolumeX size={14} />}
            <span>{buddyVoiceEnabled ? "Voice On" : "Voice Off"}</span>
          </button>

          <button
            type="button"
            onClick={() => setShowMascot((v) => !v)}
            className="rounded-lg border border-slate-200 px-2 py-1 text-[11px] font-medium text-slate-600 hover:bg-slate-50"
            title="মাস্কট চালু/বন্ধ করুন"
          >
            {showMascot ? "মাস্কট চালু" : "মাস্কট বন্ধ"}
          </button>

          {showMascot && (
            <ThinkBuddyMascot
              state={(() => {
                const s = voice.deriveMascotState(isStreaming, toolStatus, justCompleted);
                if (s === "celebrating") return "happy" as MascotState;
                if (s === "transcribing") return "thinking" as MascotState;
                return s as MascotState;
              })()}
              mouthLevel={voice.audioLevel}
              micLevel={voice.audioLevel}
              size={44}
              showCaption={false}
            />
          )}
        </div>
      </div>
    </div>

      {/* Messages Scroll Area */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-4)",
          padding: "var(--space-3) var(--space-4)",
        }}
      >
        {messages.map((msg, idx) => {
          const isUser = msg.sender === "user";
          const isErrorMsg =
            !isUser && (msg.text.includes("সমস্যা হয়েছে") || msg.text.includes("failed"));
          const isLatestAssistant = !isUser && idx === messages.length - 1;

          return (
            <div
              key={msg.id}
              ref={isLatestAssistant ? latestAssistantRef : undefined}
              style={{
                display: "flex",
                gap: "var(--space-2)",
                alignSelf: isUser ? "flex-end" : "flex-start",
                maxWidth: "88%",
              }}
            >
              {!isUser && (
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: "var(--radius-full)",
                    backgroundColor: "var(--color-primary-surface)",
                    color: "var(--color-primary)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    marginTop: 2,
                  }}
                >
                  <StaticMascotAvatar size={30} />
                </div>
              )}

              <div
                style={{
                  backgroundColor: isUser ? "var(--color-primary)" : "var(--color-surface-hover)",
                  color: isUser ? "var(--color-text-inverse)" : "var(--color-text-primary)",
                  padding: "var(--space-3) var(--space-4)",
                  borderRadius: "var(--radius-lg)",
                  fontSize: "var(--text-base)",
                  lineHeight: 1.6,
                }}
              >
                {msg.isStreaming && !msg.text && toolStatus && (
                  <div
                    style={{
                      fontSize: "var(--text-xs)",
                      color: "var(--color-text-muted)",
                      fontStyle: "italic",
                      marginBottom: 4,
                    }}
                  >
                    {toolStatus}
                  </div>
                )}

                <MathRenderer content={msg.text} />

                {/* Progressive streaming dots */}
                {msg.isStreaming && (
                  <span style={{ marginLeft: 4, opacity: 0.6 }}>...</span>
                )}

                {!isUser && !msg.isStreaming && msg.text && (
                  <div style={{ marginTop: 6, display: "flex", gap: 8 }}>
                    <button
                      type="button"
                      onClick={() =>
                        voice.isSpeaking
                          ? voice.stopSpeaking()
                          : voice.speakText(msg.text, "friendly", lang === "bn" ? "bn" : "en")
                      }
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 4,
                        fontSize: "var(--text-xs)",
                        color: "var(--color-text-muted)",
                        background: "transparent",
                        border: "none",
                        cursor: "pointer",
                        padding: 0,
                      }}
                    >
                      <Volume2 size={13} />
                      <span>{voice.isSpeaking ? (lang === "bn" ? "থামাও" : "Stop") : (lang === "bn" ? "শোনো" : "Listen")}</span>
                    </button>
                  </div>
                )}

                {/* Friendly Inline Retry Button */}
                {(isErrorMsg || msg.isError) && !isStreaming && (
                  <div style={{ marginTop: "var(--space-2)" }}>
                    <button
                      onClick={() => handleSend(findLastUserQuery(), msg.retryMessageId)}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 6,
                        backgroundColor: "var(--color-primary)",
                        color: "var(--color-text-inverse)",
                        padding: "6px 12px",
                        borderRadius: "var(--radius-md)",
                        fontSize: "var(--text-xs)",
                        fontWeight: 600,
                        marginTop: 4,
                      }}
                    >
                      <RotateCcw size={14} />
                      <span>{lang === "bn" ? "আবার চেষ্টা করো" : "Try Again"}</span>
                    </button>
                  </div>
                )}

                {/* Textbook Citations (Rule 7, 8) */}
                {msg.citations && msg.citations.length > 0 && (
                  <div
                    style={{
                      marginTop: "var(--space-3)",
                      paddingTop: "var(--space-2)",
                      borderTop: "1px solid var(--color-border)",
                      display: "flex",
                      flexDirection: "column",
                      gap: "var(--space-1)",
                    }}
                  >
                    <div style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--color-text-muted)" }}>
                      {t.chat.citations}
                    </div>
                    {msg.citations.map((cite, idx) => (
                      <div
                        key={idx}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "var(--space-1)",
                          fontSize: "var(--text-xs)",
                          backgroundColor: "var(--color-surface)",
                          color: "var(--color-primary)",
                          padding: "2px 8px",
                          borderRadius: "var(--radius-sm)",
                          border: "1px solid var(--color-border)",
                        }}
                      >
                        <BookOpen size={12} />
                        <span>
                          {cite.book_title} • {cite.chapter_title} • {t.chat.page}{" "}
                          {lang === "bn" ? toBengaliDigits(cite.printed_page) : cite.printed_page}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {/* English Writing Feedback & Contextual Vocabulary Upgrades */}
                {msg.writingFeedback && (
                  <div
                    style={{
                      marginTop: "var(--space-3)",
                      padding: "var(--space-4)",
                      backgroundColor: "var(--color-surface)",
                      borderRadius: "var(--radius-md)",
                      border: "1px solid var(--color-border)",
                      display: "flex",
                      flexDirection: "column",
                      gap: 12,
                    }}
                  >
                    {/* Header: Score & Level */}
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        flexWrap: "wrap",
                        gap: 8,
                        borderBottom: "1px solid var(--color-border)",
                        paddingBottom: 8,
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span
                          style={{
                            fontSize: "12px",
                            fontWeight: 700,
                            color: "var(--color-primary)",
                            display: "flex",
                            alignItems: "center",
                            gap: 4,
                          }}
                        >
                          <PenTool size={14} />
                          Writing Evaluation
                        </span>
                        <span className="badge badge-success" style={{ fontWeight: 700 }}>
                          Score: {msg.writingFeedback.overall_score} / 10
                        </span>
                      </div>
                      <div style={{ fontSize: "11px", color: "var(--color-text-muted)" }}>
                        {msg.writingFeedback.word_count} words • {msg.writingFeedback.sentence_count} sentences • {msg.writingFeedback.estimated_grade_level}
                      </div>
                    </div>

                    {/* Grammar & Structure Feedback */}
                    {msg.writingFeedback.grammar_checks.length > 0 ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        <div style={{ fontSize: "11px", fontWeight: 700, color: "#b45309" }}>
                          Grammar & Structure Checks ({msg.writingFeedback.grammar_checks.length}):
                        </div>
                        {msg.writingFeedback.grammar_checks.map((g: any, gIdx: number) => (
                          <div
                            key={gIdx}
                            style={{
                              padding: "6px 10px",
                              borderRadius: 6,
                              backgroundColor: "#fffbeb",
                              border: "1px solid #fef3c7",
                              fontSize: "11px",
                              lineHeight: 1.5,
                              color: "#78350f",
                            }}
                          >
                            <div style={{ fontWeight: 600 }}>
                              ⚠️ {g.issue} ⟶ <span style={{ color: "#15803d", fontWeight: 700 }}>{g.suggestion}</span>
                            </div>
                            <div style={{ fontSize: "10px", color: "#92400e", marginTop: 2 }}>
                              {g.explanation}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div
                        style={{
                          fontSize: "11px",
                          color: "#15803d",
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                          backgroundColor: "#f0fdf4",
                          padding: "6px 10px",
                          borderRadius: 6,
                        }}
                      >
                        <Check size={14} />
                        <span>No major grammatical flaws detected! Good sentence structure.</span>
                      </div>
                    )}

                    {/* Contextual Vocabulary Upgrades */}
                    {msg.writingFeedback.vocabulary_upgrades.length > 0 && (
                      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 4 }}>
                          <span
                            style={{
                              fontSize: "11px",
                              fontWeight: 700,
                              color: "var(--color-primary)",
                              display: "flex",
                              alignItems: "center",
                              gap: 4,
                            }}
                          >
                            <Sparkles size={13} />
                            Contextual Vocabulary Upgrades (বোর্ড ও স্কুলের জন্য উচ্চতর শব্দ):
                          </span>
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                          {msg.writingFeedback.vocabulary_upgrades.map((v: any, vIdx: number) => {
                            const isSaved = !!savedVocabWords[v.advanced_word];
                            return (
                              <div
                                key={vIdx}
                                style={{
                                  padding: 10,
                                  borderRadius: 8,
                                  backgroundColor: "var(--color-surface-hover)",
                                  border: "1px solid var(--color-border)",
                                  display: "flex",
                                  flexDirection: "column",
                                  gap: 6,
                                }}
                              >
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
                                  <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--color-text)" }}>
                                    <span style={{ textDecoration: "line-through", color: "var(--color-text-muted)", marginRight: 6 }}>
                                      {v.original_word}
                                    </span>
                                    <span style={{ color: "var(--color-primary)" }}>⟶ {v.advanced_word}</span>
                                    <span style={{ fontSize: "10px", color: "var(--color-text-muted)", marginLeft: 6, fontStyle: "italic" }}>
                                      ({v.part_of_speech})
                                    </span>
                                  </div>

                                  <button
                                    onClick={() => {
                                      const success = enqueueVocabWordIntoRevision(v);
                                      if (success) {
                                        setSavedVocabWords((prev) => ({ ...prev, [v.advanced_word]: true }));
                                      }
                                    }}
                                    disabled={isSaved}
                                    style={{
                                      display: "inline-flex",
                                      alignItems: "center",
                                      gap: 4,
                                      padding: "4px 8px",
                                      borderRadius: 6,
                                      fontSize: "10px",
                                      fontWeight: 600,
                                      cursor: isSaved ? "default" : "pointer",
                                      backgroundColor: isSaved ? "#dcfce7" : "var(--color-primary-surface)",
                                      color: isSaved ? "#166534" : "var(--color-primary)",
                                      border: isSaved ? "1px solid #bbf7d0" : "1px solid var(--color-border)",
                                    }}
                                  >
                                    {isSaved ? <Check size={12} /> : <BookmarkPlus size={12} />}
                                    <span>{isSaved ? "রিভিশন বক্সে সংরক্ষিত" : "+ স্পেসড রিভিশনে যোগ করুন"}</span>
                                  </button>
                                </div>

                                <div style={{ fontSize: "11px", color: "var(--color-text-secondary)" }}>
                                  <strong>বাংলা অর্থ:</strong> {v.meaning_bn} • <em>{v.meaning_en}</em>
                                </div>
                                <div
                                  style={{
                                    fontSize: "10px",
                                    color: "var(--color-text-muted)",
                                    backgroundColor: "var(--color-surface)",
                                    padding: "4px 8px",
                                    borderRadius: 4,
                                    borderLeft: "3px solid var(--color-primary)",
                                  }}
                                >
                                  <strong>উদাহরণ বাক্য:</strong> &quot;{v.example_sentence}&quot;
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {isUser && (
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: "var(--radius-full)",
                    backgroundColor: "var(--color-secondary-surface)",
                    color: "var(--color-secondary)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    marginTop: 2,
                  }}
                >
                  <User size={18} />
                </div>
              )}
            </div>
          );
        })}

        {/* Starter Chips on Initial State */}
        {messages.length === 1 && (
          <div
            style={{
              marginTop: "var(--space-2)",
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-2)",
            }}
          >
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "flex", alignItems: "center", gap: 4 }}>
              <Sparkles size={14} />
              <span>{lang === "bn" ? "শুরু করতে যেকোনো একটি চাপুন:" : "Quick suggestions:"}</span>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
              {(chatMode === "english_writing" ? ENGLISH_STARTER_CHIPS : STARTER_CHIPS).map((chip, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSend(chip.query)}
                  style={{
                    fontSize: "var(--text-xs)",
                    padding: "6px 12px",
                    borderRadius: "var(--radius-full)",
                    border: "1px solid var(--color-border)",
                    backgroundColor: "var(--color-surface-hover)",
                    color: "var(--color-text-primary)",
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  {chip.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Image Preview Thumbnail if attached */}
      {attachedImage && (
        <div
          style={{
            padding: "var(--space-2) var(--space-4)",
            backgroundColor: "var(--color-surface-hover)",
            borderTop: "1px solid var(--color-border)",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
          }}
        >
          <div style={{ position: "relative", width: 48, height: 48, borderRadius: 4, overflow: "hidden", border: "1px solid var(--color-border)" }}>
            <img src={attachedImage} alt="Attachment" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            <button
              onClick={() => setAttachedImage(null)}
              style={{
                position: "absolute",
                top: 2,
                right: 2,
                backgroundColor: "rgba(0,0,0,0.6)",
                color: "#fff",
                borderRadius: "50%",
                width: 16,
                height: 16,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <X size={12} />
            </button>
          </div>
          <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
            {lang === "bn" ? "খাতা/বইয়ের ছবি সংযুক্ত হয়েছে" : "Photo attached"}
          </span>
        </div>
      )}

      {/* Input & Action Bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-2)",
          padding: "var(--space-3) var(--space-4)",
          borderTop: "1px solid var(--color-border)",
          backgroundColor: "var(--color-surface)",
        }}
      >
        {/* Voice Mic Control */}
        {voice.isRecording ? (
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: "var(--text-xs)", color: "#EF4444", fontWeight: 600 }}>
              ● {voice.recordingSeconds}s
            </span>
            <button
              type="button"
              onClick={voice.stopRecording}
              aria-label="Stop recording"
              style={{
                padding: "6px 10px",
                borderRadius: "var(--radius-md)",
                backgroundColor: "#EF4444",
                color: "#fff",
                border: "none",
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                fontSize: "var(--text-xs)",
              }}
            >
              <Square size={12} />
              <span>Stop</span>
            </button>
            <button
              type="button"
              onClick={voice.cancelRecording}
              aria-label="Cancel recording"
              style={{
                padding: "6px 8px",
                borderRadius: "var(--radius-md)",
                backgroundColor: "var(--color-surface-hover)",
                color: "var(--color-text-secondary)",
                border: "1px solid var(--color-border)",
                cursor: "pointer",
                fontSize: "var(--text-xs)",
              }}
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={voice.startRecording}
            disabled={isStreaming || voice.isTranscribing}
            aria-label="Start voice recording"
            title={voice.isTranscribing ? "Transcribing..." : "Speak to Buddy"}
            style={{
              padding: "8px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border)",
              backgroundColor: "var(--color-surface-hover)",
              color: "var(--color-text-primary)",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Mic size={16} />
          </button>
        )}
        {/* Hidden Camera/Photo Input */}
        <input
          type="file"
          accept="image/*"
          ref={fileInputRef}
          style={{ display: "none" }}
          onChange={handleImageSelect}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          title={lang === "bn" ? "ছবি তুলুন বা আপলোড করুন" : "Upload or capture photo"}
          style={{
            padding: 8,
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface-hover)",
            color: "var(--color-text-secondary)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Camera size={18} />
        </button>

        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder={
            chatMode === "english_writing"
              ? lang === "bn"
                ? "এখানে ইংরেজি প্যারাগ্রাফ বা বাক্য লিখুন (ব্যাকরণ ও উন্নত শব্দ বিশ্লেষণ হবে)..."
                : "Type your English paragraph, essay or sentence for instant feedback & vocab upgrades..."
              : t.chat.placeholder
          }
          disabled={isStreaming}
          style={{
            flex: 1,
            padding: "var(--space-2) var(--space-3)",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
            fontSize: "var(--text-sm)",
          }}
        />

        {isStreaming ? (
          <button
            onClick={handleCancel}
            className="btn-secondary"
            style={{ color: "var(--color-danger)", padding: 8 }}
            title={t.chat.cancel}
          >
            <StopCircle size={20} />
          </button>
        ) : (
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() && !attachedImage}
            className="btn-primary"
            style={{ padding: "8px 14px" }}
            aria-label={t.chat.ask}
          >
            <Send size={18} />
          </button>
        )}
      </div>
    </div>
  );
};
