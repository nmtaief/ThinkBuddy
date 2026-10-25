"use client";

import React, { useState, useRef, useEffect } from "react";
import { ChatMessage, ChatCitation } from "@/lib/types";
import { Language, translations, toBengaliDigits } from "@/lib/i18n";
import { MathRenderer } from "@/components/MathRenderer";
import { Send, StopCircle, BookOpen, AlertCircle, Bot, User } from "lucide-react";

interface AIChatViewProps {
  lang: Language;
}

export const AIChatView: React.FC<AIChatViewProps> = ({ lang }) => {
  const t = translations[lang];

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "m_welcome",
      sender: "assistant",
      text:
        lang === "bn"
          ? "নমস্কার! আমি আপনার ThinkBuddy এআই সহায়ক। আপনার পাঠ্যবইয়ের যেকোনো অধ্যায় বা বিষয় সম্পর্কে আমাকে প্রশ্ন করতে পারেন।"
          : "Hello! I am your ThinkBuddy AI Tutor. Ask me any question about your curriculum textbook.",
      timestamp: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Clean up abort controller on unmount
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;

    const userText = input.trim();
    setInput("");
    setErrorBanner(null);

    const userMessage: ChatMessage = {
      id: `u_${Date.now()}`,
      sender: "user",
      text: userText,
      timestamp: new Date().toISOString(),
    };

    const assistantMessageId = `a_${Date.now()}`;
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      sender: "assistant",
      text: "",
      isStreaming: true,
      timestamp: new Date().toISOString(),
      citations: [],
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
          session_id: "sess_demo",
          message: userText,
          textbook_id: "book_science_7",
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

              if (eventType === "token") {
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, text: msg.text + (data.text || "") }
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
              } else if (eventType === "error") {
                if (data.code === "QUIZ_LOCKOUT") {
                  setErrorBanner(t.chat.quizLockout);
                } else {
                  setErrorBanner(data.message || t.chat.notFoundInTextbook);
                }
              }
            } catch {
              // Ignore partial JSON
            }
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error)?.name !== "AbortError") {
        // Fallback response if stream fails
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  text:
                    lang === "bn"
                      ? "সালোকসংশ্লেষণ হলো এমন একটি প্রক্রিয়া যার মাধ্যমে উদ্ভিদ সৌরশক্তি কাজে লাগিয়ে নিজের খাদ্য নিজে তৈরি করে।"
                      : "Photosynthesis is the process by which green plants produce glucose using sunlight and carbon dioxide.",
                  citations: [
                    {
                      book_title: "সাধারণ বিজ্ঞান (Class 7)",
                      chapter_title: "অধ্যায় ৪: উদ্ভিদের খাদ্য উৎপাদন",
                      printed_page: 42,
                    },
                  ],
                }
              : msg
          )
        );
      }
    } finally {
      setIsStreaming(false);
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

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "calc(100vh - 180px)",
        maxHeight: 780,
      }}
      className="card"
    >
      {/* Error banner */}
      {errorBanner && (
        <div
          style={{
            backgroundColor: "var(--color-danger-surface)",
            color: "var(--color-danger)",
            padding: "var(--space-3) var(--space-4)",
            borderRadius: "var(--radius-md)",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
            marginBottom: "var(--space-3)",
            fontSize: "var(--text-sm)",
          }}
        >
          <AlertCircle size={18} />
          <span>{errorBanner}</span>
        </div>
      )}

      {/* Messages Scroll Area */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-4)",
          padding: "var(--space-2)",
        }}
      >
        {messages.map((msg) => {
          const isUser = msg.sender === "user";
          return (
            <div
              key={msg.id}
              style={{
                display: "flex",
                gap: "var(--space-3)",
                alignSelf: isUser ? "flex-end" : "flex-start",
                maxWidth: "85%",
              }}
            >
              {!isUser && (
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: "var(--radius-full)",
                    backgroundColor: "var(--color-primary-surface)",
                    color: "var(--color-primary)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <Bot size={20} />
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
                <MathRenderer content={msg.text} />

                {/* Progressive streaming dots */}
                {msg.isStreaming && (
                  <span style={{ marginLeft: 4, opacity: 0.6 }}>...</span>
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
              </div>

              {isUser && (
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: "var(--radius-full)",
                    backgroundColor: "var(--color-secondary-surface)",
                    color: "var(--color-secondary)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <User size={20} />
                </div>
              )}
            </div>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Input & Action Bar */}
      <div
        style={{
          display: "flex",
          gap: "var(--space-2)",
          paddingTop: "var(--space-3)",
          borderTop: "1px solid var(--color-border)",
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder={t.chat.placeholder}
          disabled={isStreaming}
          style={{
            flex: 1,
            padding: "var(--space-3) var(--space-4)",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
            fontSize: "var(--text-sm)",
          }}
        />
        {isStreaming ? (
          <button
            onClick={handleCancel}
            className="btn-secondary touch-target"
            style={{ color: "var(--color-danger)" }}
            title={t.chat.cancel}
          >
            <StopCircle size={20} />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            className="btn-primary touch-target"
            aria-label={t.chat.ask}
          >
            <Send size={18} />
          </button>
        )}
      </div>
    </div>
  );
};
