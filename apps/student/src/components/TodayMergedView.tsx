import React, { useState } from "react";
import {
  RoutineSlot,
  Language,
  translations,
  toBengaliDigits,
  UserProfile,
  saveStoredRoutineSlots,
  StudentExamSettings,
  calculateDaysRemaining,
} from "@thinkbuddy/shared";
import {
  Clock,
  BookOpen,
  Play,
  Sparkles,
  Flame,
  Calendar,
  CheckCircle2,
  Circle,
  Edit3,
  Plus,
  Share2,
  Copy,
  Check,
  X,
  Layers,
  Settings,
  GraduationCap,
} from "lucide-react";
import { StudySessionRoomView } from "./StudySessionRoomView";

interface TodayMergedViewProps {
  user: UserProfile;
  lang: Language;
  routineSlots: RoutineSlot[];
  onUpdateRoutineSlots: (slots: RoutineSlot[]) => void;
  examSettings: StudentExamSettings;
  onOpenExamSettings: () => void;
}

export const TodayMergedView: React.FC<TodayMergedViewProps> = ({
  user,
  lang,
  routineSlots,
  onUpdateRoutineSlots,
  examSettings,
  onOpenExamSettings,
}) => {
  const t = translations[lang];
  const [selectedSlot, setSelectedSlot] = useState<RoutineSlot | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editedSlots, setEditedSlots] = useState<RoutineSlot[]>(routineSlots);
  const [copiedCode, setCopiedCode] = useState(false);

  // If a study session is active, render the StudySessionRoomView
  if (selectedSlot) {
    return (
      <StudySessionRoomView
        slot={selectedSlot}
        lang={lang}
        studentName={user.name}
        studentUid={user.uid}
        onBack={() => setSelectedSlot(null)}
        onComplete={(slotId) => {
          const updated = routineSlots.map((s) =>
            s.id === slotId ? { ...s, status: "completed" as const } : s
          );
          onUpdateRoutineSlots(updated);
          saveStoredRoutineSlots(updated);
          setSelectedSlot(null);
        }}
      />
    );
  }

  const handleToggleStatus = (slotId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updated = routineSlots.map((s) => {
      if (s.id === slotId) {
        return {
          ...s,
          status: s.status === "completed" ? ("pending" as const) : ("completed" as const),
        };
      }
      return s;
    });
    onUpdateRoutineSlots(updated);
    saveStoredRoutineSlots(updated);
  };

  const handleCopyInviteCode = () => {
    const code = user.inviteCode || "TB-8392";
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(code);
    }
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2500);
  };

  // Routine Edit Actions
  const handleSaveRoutine = () => {
    onUpdateRoutineSlots(editedSlots);
    saveStoredRoutineSlots(editedSlots);
    setIsEditModalOpen(false);
  };

  const handleAddNewSlot = () => {
    const newSlot: RoutineSlot = {
      id: `slot_custom_${Date.now()}`,
      timeSlot: "২০:৩০ - ২১:১৫",
      timeSlotEn: "08:30 PM - 09:15 PM",
      subject: "বাংলাদেশ ও বিশ্বপরিচয়",
      subjectEn: "Bangladesh & Global Studies",
      chapterTitle: "অধ্যায় ৪: বাংলাদেশের অর্থনীতি ও প্রাকৃতিক সম্পদ",
      chapterTitleEn: "Chapter 4: Economy of Bangladesh",
      estimatedMinutes: 45,
      printedPages: "৫২ - ৫৪",
      printedPagesEn: "52 - 54",
      status: "pending",
      bookTitle: "বাংলাদেশ ও বিশ্বপরিচয় (NCTB)",
      guidelines: "পাঠ্যবইয়ের ৫২-৫৪ পৃষ্ঠা মনোযোগ দিয়ে রিডিং পড়ো এবং মূল পয়েন্টগুলো খাতায় নোট করো।",
      chapterPart: 1,
      chapterTotalParts: 2,
    };
    setEditedSlots([...editedSlots, newSlot]);
  };

  const handleDeleteSlot = (id: string) => {
    setEditedSlots(editedSlots.filter((s) => s.id !== id));
  };

  const completedCount = routineSlots.filter((s) => s.status === "completed").length;
  const totalMinutes = routineSlots.reduce((acc, s) => acc + s.estimatedMinutes, 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      {/* 1. Daily Overview Banner */}
      <div
        className="card"
        style={{
          background: "linear-gradient(135deg, rgba(37, 99, 235, 0.05) 0%, rgba(16, 185, 129, 0.06) 100%)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "var(--space-4)",
          padding: "var(--space-5) var(--space-6)",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Sparkles size={16} style={{ color: "var(--color-primary)" }} />
            <span style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-primary)" }}>
              {t.today.title}
            </span>
          </div>
          <h1 style={{ fontSize: "var(--text-xl)", fontWeight: 800, marginTop: 4, color: "var(--color-text-main)" }}>
            {t.today.subtitle}
          </h1>
        </div>

        {/* Routine Edit Trigger */}
        <button
          onClick={() => {
            setEditedSlots(routineSlots);
            setIsEditModalOpen(true);
          }}
          className="btn-secondary touch-target"
          style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--text-xs)" }}
        >
          <Edit3 size={15} />
          <span>{t.today.editRoutine}</span>
        </button>
      </div>

      {/* 2. Streak & Exam Countdown Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: "var(--space-4)",
        }}
      >
        {/* Streak */}
        <div
          className="card"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-4)",
            borderLeft: "4px solid var(--color-warning)",
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: "var(--radius-full)",
              backgroundColor: "var(--color-warning-surface)",
              color: "var(--color-warning)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Flame size={26} />
          </div>
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
              {t.today.streakBadge}
            </div>
            <div style={{ fontSize: "var(--text-xl)", fontWeight: 800 }}>
              {lang === "bn" ? toBengaliDigits(7) : 7} {t.today.streakDays}
            </div>
          </div>
        </div>

        {/* Dynamic Exam Countdown with Edit Target Button */}
        <div
          className="card"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "var(--space-3)",
            borderLeft: "4px solid var(--color-primary)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: "var(--radius-full)",
                backgroundColor: "var(--color-primary-surface)",
                color: "var(--color-primary)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <Calendar size={24} />
            </div>
            <div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
                {examSettings.classNameBn} • {examSettings.exam_title}
              </div>
              <div style={{ fontSize: "var(--text-xl)", fontWeight: 800, color: "var(--color-text-main)" }}>
                {(() => {
                  const days = calculateDaysRemaining(examSettings.exam_date);
                  if (days > 0) {
                    return lang === "bn" ? `${toBengaliDigits(days)} দিন বাকি` : `${days} days left`;
                  } else if (days === 0) {
                    return lang === "bn" ? "আজই পরীক্ষা!" : "Today is exam!";
                  } else {
                    return lang === "bn" ? "পরীক্ষা সম্পন্ন" : "Exam ended";
                  }
                })()}
              </div>
            </div>
          </div>

          <button
            onClick={onOpenExamSettings}
            className="btn-secondary touch-target"
            style={{
              padding: "6px 10px",
              fontSize: "var(--text-xs)",
              display: "flex",
              alignItems: "center",
              gap: 4,
              borderRadius: "var(--radius-md)",
            }}
            title={lang === "bn" ? "শ্রেণি ও পরীক্ষার তারিখ পরিবর্তন করুন" : "Change Class & Exam Date"}
          >
            <Edit3 size={13} />
            <span>{t.examSettings.editGoal}</span>
          </button>
        </div>

        {/* Parent Link Invite Card */}
        <div
          className="card"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "var(--space-3)",
            backgroundColor: "var(--color-surface-subtle)",
            border: "1px dashed var(--color-primary-border)",
          }}
        >
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-primary)", fontWeight: 700 }}>
              {t.invite.studentCardTitle}
            </div>
            <div style={{ fontSize: "var(--text-sm)", fontWeight: 800, marginTop: 2, fontFamily: "monospace" }}>
              {user.inviteCode || "TB-8392"}
            </div>
          </div>
          <button
            onClick={handleCopyInviteCode}
            className="btn-secondary touch-target"
            style={{
              padding: "6px 12px",
              fontSize: "var(--text-xs)",
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
            title={t.invite.copyCode}
          >
            {copiedCode ? <Check size={14} style={{ color: "var(--color-success)" }} /> : <Copy size={14} />}
            <span>{copiedCode ? t.invite.copied : t.invite.copyCode}</span>
          </button>
        </div>
      </div>

      {/* 3. PART (A): Today's Routine Timeline at the Top */}
      <div className="card" style={{ padding: "var(--space-5) var(--space-6)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <Clock size={18} style={{ color: "var(--color-primary)" }} />
            <h2 style={{ fontSize: "var(--text-base)", fontWeight: 700, margin: 0 }}>
              {t.today.routineSection}
            </h2>
          </div>
          <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600 }}>
            {lang === "bn"
              ? `মোট সময়: ${toBengaliDigits(totalMinutes)} মিনিট (${toBengaliDigits(completedCount)}/${toBengaliDigits(routineSlots.length)} সম্পন্ন)`
              : `Total: ${totalMinutes} min (${completedCount}/${routineSlots.length} completed)`}
          </span>
        </div>

        {/* Timeline Horizontal / Responsive Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: "var(--space-3)",
          }}
        >
          {routineSlots.map((slot, index) => {
            const isCompleted = slot.status === "completed";
            return (
              <div
                key={slot.id}
                onClick={() => setSelectedSlot(slot)}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "var(--space-2)",
                  padding: "var(--space-3) var(--space-4)",
                  borderRadius: "var(--radius-lg)",
                  backgroundColor: isCompleted ? "var(--color-success-surface)" : "var(--color-surface-hover)",
                  border: `1px solid ${isCompleted ? "var(--color-success)" : "var(--color-border)"}`,
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                  position: "relative",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span
                    style={{
                      fontSize: "var(--text-xs)",
                      fontWeight: 700,
                      color: isCompleted ? "var(--color-success)" : "var(--color-primary)",
                    }}
                  >
                    {lang === "bn" ? slot.timeSlot : slot.timeSlotEn}
                  </span>
                  <button
                    onClick={(e) => handleToggleStatus(slot.id, e)}
                    className="touch-target"
                    style={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      padding: 2,
                      color: isCompleted ? "var(--color-success)" : "var(--color-text-muted)",
                    }}
                    aria-label={isCompleted ? t.today.markIncomplete : t.today.markComplete}
                  >
                    {isCompleted ? <CheckCircle2 size={18} /> : <Circle size={18} />}
                  </button>
                </div>

                <div style={{ fontWeight: 700, fontSize: "var(--text-sm)", color: "var(--color-text-main)" }}>
                  {lang === "bn" ? slot.subject : slot.subjectEn}
                </div>

                <div
                  style={{
                    fontSize: "var(--text-xs)",
                    color: "var(--color-text-secondary)",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {lang === "bn" ? slot.chapterTitle : slot.chapterTitleEn}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 4. PART (B): Today's Tasks & Study Session Triggers Below */}
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 700 }}>
              {t.today.tasksSection}
            </h2>
            <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              {lang === "bn"
                ? "যেকোনো বিষয় নির্বাচন করে বিস্তারিত পৃষ্ঠাভিত্তিক পড়াশোনা শুরু করুন"
                : "Select any subject to launch interactive page-by-page study"}
            </p>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          {routineSlots.map((slot) => {
            const isCompleted = slot.status === "completed";
            const minDisplay = lang === "bn" ? toBengaliDigits(slot.estimatedMinutes) : slot.estimatedMinutes;

            return (
              <div
                key={slot.id}
                className="card"
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "var(--space-3)",
                  opacity: isCompleted ? 0.9 : 1,
                  borderLeft: `4px solid ${isCompleted ? "var(--color-success)" : "var(--color-primary)"}`,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "var(--space-2)" }}>
                  <div style={{ display: "flex", alignItems: "flex-start", gap: "var(--space-3)" }}>
                    <button
                      onClick={(e) => handleToggleStatus(slot.id, e)}
                      className="touch-target"
                      style={{
                        padding: 0,
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        color: isCompleted ? "var(--color-success)" : "var(--color-text-muted)",
                        marginTop: 2,
                      }}
                      aria-label={isCompleted ? t.today.markIncomplete : t.today.markComplete}
                    >
                      {isCompleted ? <CheckCircle2 size={24} /> : <Circle size={24} />}
                    </button>

                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap" }}>
                        <span
                          style={{
                            fontSize: "var(--text-xs)",
                            fontWeight: 700,
                            padding: "2px 8px",
                            borderRadius: "var(--radius-full)",
                            backgroundColor: "var(--color-primary-surface)",
                            color: "var(--color-primary)",
                          }}
                        >
                          {lang === "bn" ? slot.subject : slot.subjectEn}
                        </span>

                        <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", display: "flex", alignItems: "center", gap: 4 }}>
                          <Clock size={12} />
                          {minDisplay} {t.today.minutesShort}
                        </span>

                        <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                          • {lang === "bn" ? slot.timeSlot : slot.timeSlotEn}
                        </span>
                      </div>

                      <h3
                        style={{
                          fontSize: "var(--text-base)",
                          fontWeight: 700,
                          marginTop: "var(--space-1)",
                          textDecoration: isCompleted ? "line-through" : "none",
                        }}
                      >
                        {lang === "bn" ? slot.chapterTitle : slot.chapterTitleEn}
                      </h3>
                    </div>
                  </div>

                  {/* Launch Study Session Room Button */}
                  <button
                    onClick={() => setSelectedSlot(slot)}
                    className="btn-primary touch-target"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "var(--space-2)",
                      fontSize: "var(--text-xs)",
                      padding: "8px 16px",
                      borderRadius: "var(--radius-md)",
                    }}
                  >
                    <Play size={14} />
                    <span>{isCompleted ? t.today.reviewSession : t.today.startSession}</span>
                  </button>
                </div>

                {/* Printed Page Citation */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-2)",
                    fontSize: "var(--text-xs)",
                    color: "var(--color-text-secondary)",
                    backgroundColor: "var(--color-surface-hover)",
                    padding: "var(--space-2) var(--space-3)",
                    borderRadius: "var(--radius-md)",
                  }}
                >
                  <BookOpen size={14} style={{ color: "var(--color-primary)" }} />
                  <span>
                    {slot.bookTitle} — {t.today.printedPages}:{" "}
                    <strong>{lang === "bn" ? slot.printedPages : slot.printedPagesEn}</strong>
                  </span>
                </div>

                {slot.guidelines && (
                  <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", margin: 0 }}>
                    {slot.guidelines}
                  </p>
                )}

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                  <span>{t.today.sessionFeatures}</span>
                  {isCompleted && (
                    <span style={{ color: "var(--color-success)", fontWeight: 700 }}>
                      ✓ {t.today.completedBadge}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Routine Edit Modal */}
      {isEditModalOpen && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(15, 23, 42, 0.5)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
            padding: "var(--space-4)",
          }}
        >
          <div
            className="card"
            style={{
              width: "100%",
              maxWidth: 600,
              maxHeight: "90vh",
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-4)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                <Clock size={20} style={{ color: "var(--color-primary)" }} />
                <h3 style={{ fontSize: "var(--text-lg)", fontWeight: 700, margin: 0 }}>
                  {t.today.editRoutine}
                </h3>
              </div>
              <button
                onClick={() => setIsEditModalOpen(false)}
                className="btn-secondary touch-target"
                style={{ padding: 6 }}
              >
                <X size={16} />
              </button>
            </div>

            <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)" }}>
              {lang === "bn"
                ? "এখানে রুটিনের বিষয় বা সময় পরিবর্তন করলে আজকের পড়ার তালিকা ও টাইমলাইনে তা সাথে সাথে হালনাগাদ হবে।"
                : "Editing routine slots here immediately updates today's study timeline and tasks list."}
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
              {editedSlots.map((slot, idx) => (
                <div
                  key={slot.id}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "var(--space-2)",
                    padding: "var(--space-3)",
                    border: "1px solid var(--color-border)",
                    borderRadius: "var(--radius-md)",
                    backgroundColor: "var(--color-surface-hover)",
                  }}
                >
                  <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
                    <input
                      type="text"
                      value={slot.timeSlot}
                      onChange={(e) => {
                        const val = e.target.value;
                        setEditedSlots(
                          editedSlots.map((s, i) => (i === idx ? { ...s, timeSlot: val, timeSlotEn: val } : s))
                        );
                      }}
                      style={{
                        padding: "6px 10px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--color-border)",
                        fontSize: "var(--text-xs)",
                        width: 140,
                      }}
                      placeholder="সময়"
                    />

                    <input
                      type="text"
                      value={slot.subject}
                      onChange={(e) => {
                        const val = e.target.value;
                        setEditedSlots(
                          editedSlots.map((s, i) => (i === idx ? { ...s, subject: val, subjectEn: val } : s))
                        );
                      }}
                      style={{
                        padding: "6px 10px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--color-border)",
                        fontSize: "var(--text-xs)",
                        width: 140,
                      }}
                      placeholder="বিষয়"
                    />

                    <button
                      onClick={() => handleDeleteSlot(slot.id)}
                      className="btn-secondary touch-target"
                      style={{
                        padding: "6px 10px",
                        fontSize: "var(--text-xs)",
                        color: "var(--color-error)",
                        marginLeft: "auto",
                      }}
                    >
                      <X size={14} />
                    </button>
                  </div>

                  <input
                    type="text"
                    value={slot.chapterTitle}
                    onChange={(e) => {
                      const val = e.target.value;
                      setEditedSlots(
                        editedSlots.map((s, i) => (i === idx ? { ...s, chapterTitle: val, chapterTitleEn: val } : s))
                      );
                    }}
                    style={{
                      padding: "6px 10px",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--color-border)",
                      fontSize: "var(--text-xs)",
                      width: "100%",
                    }}
                    placeholder="অধ্যায়ের নাম ও বিষয়বস্তু"
                  />
                </div>
              ))}
            </div>

            <button
              onClick={handleAddNewSlot}
              className="btn-secondary touch-target"
              style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 6, fontSize: "var(--text-xs)" }}
            >
              <Plus size={15} />
              <span>{t.today.addSlot}</span>
            </button>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-3)", marginTop: "var(--space-2)" }}>
              <button
                onClick={() => setIsEditModalOpen(false)}
                className="btn-secondary touch-target"
                style={{ fontSize: "var(--text-xs)" }}
              >
                {t.today.cancel}
              </button>
              <button
                onClick={handleSaveRoutine}
                className="btn-primary touch-target"
                style={{ fontSize: "var(--text-xs)" }}
              >
                {t.today.saveRoutine}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

