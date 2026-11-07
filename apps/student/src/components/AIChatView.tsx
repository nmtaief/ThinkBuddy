import React, { useState, useRef, useEffect } from "react";
import { Language, translations, ChatMessage } from "@thinkbuddy/shared";
import { Sparkles, Send, BookOpen, Bot, User } from "lucide-react";
import { MathRenderer } from "./MathRenderer";

interface AIChatViewProps {
  lang: Language;
}

export const AIChatView: React.FC<AIChatViewProps> = ({ lang }) => {
  const t = translations[lang];

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "msg_welcome",
      sender: "ai",
      text:
        lang === "bn"
          ? "আসসালামু আলাইকুম! আমি তোমার ThinkBuddy এআই শিক্ষক। জাতীয় শিক্ষাক্রম ও পাঠ্যপুস্তক বোর্ড (NCTB) অনুমোদিত বিজ্ঞান, গণিত বা যেকোনো পাঠ্যবই সম্পর্কিত প্রশ্ন জিজ্ঞাসা করো। আমি পৃষ্ঠা নম্বরসহ উত্তর দেব।"
          : "Hello! I am your ThinkBuddy AI study assistant. Ask any question from your NCTB textbooks, and I will guide you with exact page citations.",
      citations: [
        { book: "সাধারণ বিজ্ঞান (Class 7)", page: "পৃষ্ঠা ৪২" },
      ],
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
  ]);

  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const userText = input.trim();
    setInput("");

    const userMsg: ChatMessage = {
      id: `msg_u_${Date.now()}`,
      sender: "user",
      text: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsStreaming(true);

    // AI Response generation with realistic token pacing and citation
    setTimeout(() => {
      let aiText = "";
      let citation = { book: "সাধারণ বিজ্ঞান (NCTB)", page: "পৃষ্ঠা ৪২–৪৪" };

      if (userText.includes("সালোকসংশ্লেষণ") || userText.toLowerCase().includes("photosynthesis")) {
        aiText =
          lang === "bn"
            ? "সালোকসংশ্লেষণ হলো সবুজ উদ্ভিদের শর্করা তৈরির জৈব-রাসায়নিক প্রক্রিয়া। প্রধান কাঁচামাল হলো কার্বন ডাই-অক্সাইড ($CO_2$) এবং পানি ($H_2O$)। পাতার মেসোফিল টিস্যুর ক্লোরোপ্লাস্টে সৌরশক্তি শোষণ করে গ্লুকোজ ও অক্সিজেন ($O_2$) উৎপন্ন হয়:\n\n$$6CO_2 + 12H_2O \\xrightarrow[\\text{ক্লোরোফিল}]{\\text{সূর্যালোক}} C_6H_{12}O_6 + 6H_2O + 6O_2$$"
            : "Photosynthesis is the biochemical process by which green plants manufacture carbohydrates. Primary raw materials are Carbon Dioxide ($CO_2$) and Water ($H_2O$). Using solar energy captured by chlorophyll, glucose and oxygen ($O_2$) are formed.";
        citation = { book: "সাধারণ বিজ্ঞান (Class 7)", page: "মুদ্রিত পৃষ্ঠা ৪২" };
      } else if (userText.includes("বর্গ") || userText.includes("সূত্র") || userText.toLowerCase().includes("math")) {
        aiText =
          lang === "bn"
            ? "বর্গ নির্ণয়ের মৌলিক সূত্র হলো:\n\n$$(a + b)^2 = a^2 + 2ab + b^2$$\n$$(a - b)^2 = a^2 - 2ab + b^2$$\n\nএই সূত্রের মাধ্যমে যেকোনো দ্বিপদী রাশির মান সহজে নির্ণয় করা যায়।"
            : "The standard algebraic identities for square expansions are:\n\n$$(a + b)^2 = a^2 + 2ab + b^2$$\n$$(a - b)^2 = a^2 - 2ab + b^2$$";
        citation = { book: "গণিত (Class 7)", page: "মুদ্রিত পৃষ্ঠা ৭২" };
      } else {
        aiText =
          lang === "bn"
            ? `তোমার প্রশ্নের জন্য ধন্যবাদ! পাঠ্যবই অনুসারে এই বিষয়ের মূল ধারণাটি ভালোভাবে পড়ার জন্য তোমার আজকের পড়ার রুটিনের পৃষ্ঠাগুলো দেখে নিতে পারো। কোনো নির্দিষ্ট সমীকরণ বা সংজ্ঞা বুঝতে সমস্যা হলে আমাকে বলো।`
            : "Thank you for asking! Based on your NCTB textbook, you can review the assigned pages from your study plan. Let me know if you need help with any specific formula or concept.";
      }

      const aiMsg: ChatMessage = {
        id: `msg_ai_${Date.now()}`,
        sender: "ai",
        text: aiText,
        citations: [citation],
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setMessages((prev) => [...prev, aiMsg]);
      setIsStreaming(false);
    }, 700);
  };

  return (
    <div
      className="card ai-chat-card"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "calc(100dvh - 210px)",
        minHeight: 460,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--color-border)", paddingBottom: "var(--space-3)", marginBottom: "var(--space-4)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <Sparkles size={20} style={{ color: "var(--color-primary)" }} />
          <div>
            <h2 style={{ fontSize: "var(--text-base)", fontWeight: 700, margin: 0 }}>
              {t.chat.title}
            </h2>
            <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              {t.chat.subtitle}
            </span>
          </div>
        </div>
      </div>

      {/* Message Stream */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-4)",
          paddingRight: "var(--space-2)",
        }}
      >
        {messages.map((m) => {
          const isUser = m.sender === "user";
          return (
            <div
              key={m.id}
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
                    width: 32,
                    height: 32,
                    borderRadius: "var(--radius-full)",
                    backgroundColor: "var(--color-primary-surface)",
                    color: "var(--color-primary)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <Bot size={18} />
                </div>
              )}

              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <div
                  style={{
                    padding: "var(--space-3) var(--space-4)",
                    borderRadius: "var(--radius-lg)",
                    backgroundColor: isUser ? "var(--color-primary)" : "var(--color-surface-hover)",
                    color: isUser ? "#FFFFFF" : "var(--color-text-main)",
                    fontSize: "var(--text-sm)",
                    lineHeight: 1.6,
                    border: isUser ? "none" : "1px solid var(--color-border)",
                  }}
                >
                  <MathRenderer content={m.text} />

                  {/* Textbook Citations */}
                  {m.citations && m.citations.length > 0 && (
                    <div
                      style={{
                        marginTop: "var(--space-3)",
                        paddingTop: "var(--space-2)",
                        borderTop: isUser ? "1px solid rgba(255,255,255,0.2)" : "1px solid var(--color-border)",
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        fontSize: "var(--text-xs)",
                        color: isUser ? "rgba(255,255,255,0.85)" : "var(--color-primary)",
                        fontWeight: 600,
                      }}
                    >
                      <BookOpen size={13} />
                      <span>{t.chat.citationLabel} {m.citations.map((c) => `${c.book} (${c.page})`).join(", ")}</span>
                    </div>
                  )}
                </div>

                <span style={{ fontSize: "10px", color: "var(--color-text-muted)", alignSelf: isUser ? "flex-end" : "flex-start" }}>
                  {m.timestamp}
                </span>
              </div>

              {isUser && (
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: "var(--radius-full)",
                    backgroundColor: "var(--color-border)",
                    color: "var(--color-text-secondary)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <User size={18} />
                </div>
              )}
            </div>
          );
        })}

        {isStreaming && (
          <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center", color: "var(--color-primary)", fontSize: "var(--text-xs)" }}>
            <Sparkles size={14} className="animate-spin" />
            <span>{lang === "bn" ? "পাঠ্যবই থেকে রেফারেন্স তৈরি হচ্ছে..." : "Retrieving from textbooks..."}</span>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      {/* Input Form */}
      <form onSubmit={handleSend} style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-3)" }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t.chat.placeholder}
          style={{
            flex: 1,
            padding: "10px 14px",
            borderRadius: "var(--radius-lg)",
            border: "1.5px solid var(--color-border)",
            backgroundColor: "var(--color-surface)",
            color: "var(--color-text-main)",
            fontSize: "var(--text-sm)",
            fontFamily: "inherit",
          }}
        />
        <button
          type="submit"
          disabled={!input.trim() || isStreaming}
          className="btn-primary touch-target"
          style={{ padding: "0 18px", opacity: input.trim() && !isStreaming ? 1 : 0.6 }}
        >
          <Send size={16} />
        </button>
      </form>
    </div>
  );
};

