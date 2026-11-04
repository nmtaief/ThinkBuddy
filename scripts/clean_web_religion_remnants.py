"""
Clean web religion remnants
"""
from pathlib import Path

# 1. TodayView.tsx
p_today = Path("web/src/components/student/TodayView.tsx")
content = p_today.read_text(encoding="utf-8")
old_block = """      {/* Warm Religious Greeting Card */}
      <div
        className="card"
        style={{
          background: "linear-gradient(135deg, rgba(37, 99, 235, 0.06) 0%, rgba(16, 185, 129, 0.08) 100%)",
          border: "1px solid var(--color-border)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "var(--space-3)",
          padding: "var(--space-4) var(--space-6)",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Sparkles size={16} style={{ color: "var(--color-primary)" }} />
            <span style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-primary)" }}>
            </span>
          </div>
          <div style={{ fontSize: "var(--text-lg)", fontWeight: 800, marginTop: 2 }}>
          </div>
          <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", margin: 0 }}>
          </p>
        </div>"""

new_block = """      {/* Daily Overview Header */}
      <div
        className="card"
        style={{
          background: "linear-gradient(135deg, rgba(37, 99, 235, 0.06) 0%, rgba(16, 185, 129, 0.08) 100%)",
          border: "1px solid var(--color-border)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "var(--space-3)",
          padding: "var(--space-4) var(--space-6)",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Sparkles size={16} style={{ color: "var(--color-primary)" }} />
            <span style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-primary)" }}>
              {lang === "bn" ? "দৈনিক ড্যাশবোর্ড" : "Daily Dashboard"}
            </span>
          </div>
          <div style={{ fontSize: "var(--text-lg)", fontWeight: 800, marginTop: 2 }}>
            {lang === "bn" ? "আজকের পড়াশোনার পরিকল্পনা ও অগ্রগতি" : "Today's Study Plan & Progress"}
          </div>
        </div>"""

if old_block in content:
    content = content.replace(old_block, new_block)
    p_today.write_text(content, encoding="utf-8")
    print("Updated TodayView.tsx")
else:
    # try normalize crlf
    content = content.replace(old_block.replace("\n", "\r\n"), new_block.replace("\n", "\r\n"))
    p_today.write_text(content, encoding="utf-8")
    print("Updated TodayView.tsx (CRLF)")

# 2. StudySessionRoomView.tsx
p_session = Path("web/src/components/student/StudySessionRoomView.tsx")
s_content = p_session.read_text(encoding="utf-8")
old_banner = """      {/* Dynamic Religious Blessing Banner */}
      <div
        className="card"
        style={{
          background: "linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(16, 185, 129, 0.10) 100%)",
          border: "1px solid var(--color-border)",
          padding: "var(--space-5) var(--space-6)",
          borderRadius: "var(--radius-xl)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-1)" }}>
          <Sparkles size={18} style={{ color: "var(--color-primary)" }} />
          <span style={{ fontSize: "var(--text-sm)", fontWeight: 700, color: "var(--color-primary)" }}>
          </span>
        </div>
        <h2 style={{ fontSize: "var(--text-xl)", fontWeight: 800, margin: "var(--space-1) 0" }}>
        </h2>
        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", margin: 0, lineHeight: 1.6 }}>
        </p>
      </div>"""

old_prompt = """        {/* Dynamic Religious Note Prompt */}
        <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", marginBottom: "var(--space-3)" }}>
        </p>"""

for b, repl in [(old_banner, ""), (old_prompt, "")]:
    if b in s_content:
        s_content = s_content.replace(b, repl)
    else:
        s_content = s_content.replace(b.replace("\n", "\r\n"), repl)

p_session.write_text(s_content, encoding="utf-8")
print("Updated StudySessionRoomView.tsx")

# 3. StudySetupEditorView.tsx
p_setup = Path("web/src/components/parent/StudySetupEditorView.tsx")
setup_content = p_setup.read_text(encoding="utf-8")
setup_content = setup_content.replace("(ধর্মীয় ও বিশেষ দিবস বিরতি)", "(বিশেষ দিবস ও ছুটির বিরতি)")
p_setup.write_text(setup_content, encoding="utf-8")
print("Updated StudySetupEditorView.tsx")

