package com.thinkbuddy.app.core.network

import com.google.gson.annotations.SerializedName
import java.util.UUID

// -----------------------------------------------------------------------------
// Parent Dashboard & Student Overview Schemas (P07)
// -----------------------------------------------------------------------------

data class ParentStudentSummary(
    @SerializedName("student_id") val studentId: String,
    @SerializedName("name") val name: String,
    @SerializedName("class_band") val classBand: String,
    @SerializedName("group") val group: String,
    @SerializedName("avatar_url") val avatarUrl: String? = null
)

data class ParentProgressSummary(
    @SerializedName("total_minutes_studied") val totalMinutesStudied: Int = 0,
    @SerializedName("total_tasks_completed") val totalTasksCompleted: Int = 0,
    @SerializedName("completion_rate_pct") val completionRatePct: Double = 0.0,
    @SerializedName("active_streak_days") val activeStreakDays: Int = 0,
    @SerializedName("weekly_grace_available") val weeklyGraceAvailable: Boolean = true,
    @SerializedName("quiz_score_avg") val quizScoreAvg: Double? = null
)

data class ParentMasterySubjectSummary(
    @SerializedName("subject") val subject: String,
    @SerializedName("mastery_score") val masteryScore: Double,
    @SerializedName("confidence") val confidence: Double,
    @SerializedName("status") val status: String, // "mastered", "in_progress", "needs_practice"
    @SerializedName("status_bn") val statusBn: String, // "দক্ষতা অর্জিত", "অগ্রগতি চলমান", "অনুশীলন প্রয়োজন"
    @SerializedName("focus_areas") val focusAreas: List<String> = emptyList()
)

data class ParentRevisionSummary(
    @SerializedName("due_count") val dueCount: Int = 0,
    @SerializedName("boxes_distribution") val boxesDistribution: Map<String, Int> = emptyMap()
)

data class ParentExamCountdown(
    @SerializedName("subject") val subject: String,
    @SerializedName("exam_name") val examName: String,
    @SerializedName("exam_date") val examDate: String,
    @SerializedName("days_remaining") val daysRemaining: Int
)

data class ParentAiSuggestionView(
    @SerializedName("id") val id: String,
    @SerializedName("student_id") val studentId: String,
    @SerializedName("type") val type: String, // "ai_priority_suggestion" | "ai_minute_suggestion"
    @SerializedName("subject") val subject: String? = null,
    @SerializedName("field") val field: String? = null,
    @SerializedName("current_value") val currentValue: Any? = null,
    @SerializedName("suggested_value") val suggestedValue: Any? = null,
    @SerializedName("rationale") val rationale: String,
    @SerializedName("rationale_bn") val rationaleBn: String,
    @SerializedName("evidence_codes") val evidenceCodes: List<String> = emptyList(),
    @SerializedName("status") val status: String = "pending",
    @SerializedName("created_at") val createdAt: String? = null
)

data class ParentAiAdjustmentView(
    @SerializedName("adjustment_id") val adjustmentId: String,
    @SerializedName("type") val type: String,
    @SerializedName("summary") val summary: String,
    @SerializedName("summary_bn") val summaryBn: String,
    @SerializedName("applied_at") val appliedAt: String,
    @SerializedName("can_undo") val canUndo: Boolean = true
)

data class ParentChatTopicSummary(
    @SerializedName("topic") val topic: String,
    @SerializedName("subject") val subject: String? = null,
    @SerializedName("question_count") val questionCount: Int = 1,
    @SerializedName("last_asked_at") val lastAskedAt: String? = null
)

data class StudentDashboardResponse(
    @SerializedName("student") val student: ParentStudentSummary,
    @SerializedName("progress") val progress: ParentProgressSummary,
    @SerializedName("subjects_mastery") val subjectsMastery: List<ParentMasterySubjectSummary> = emptyList(),
    @SerializedName("spaced_revision") val spacedRevision: ParentRevisionSummary = ParentRevisionSummary(),
    @SerializedName("upcoming_exams") val upcomingExams: List<ParentExamCountdown> = emptyList(),
    @SerializedName("ai_suggestions") val aiSuggestions: List<ParentAiSuggestionView> = emptyList(),
    @SerializedName("recent_ai_adjustments") val recentAiAdjustments: List<ParentAiAdjustmentView> = emptyList(),
    @SerializedName("chat_topics") val chatTopics: List<ParentChatTopicSummary> = emptyList(),
    @SerializedName("adaptive_mode") val adaptiveMode: String = "suggest"
)

data class ParentOverviewResponse(
    @SerializedName("parent_id") val parentId: String,
    @SerializedName("students") val students: List<StudentDashboardResponse> = emptyList()
)

// -----------------------------------------------------------------------------
// Study Settings & Setup Schemas (docs/08_CLIENT_PLATFORM_GUIDE.md §3)
// -----------------------------------------------------------------------------

data class UnavailableBlockDto(
    @SerializedName("day") val day: String = "fri",
    @SerializedName("start") val start: String = "16:00",
    @SerializedName("end") val end: String = "18:00",
    @SerializedName("label") val label: String = "কোচিং"
)

data class BlackoutDateDto(
    @SerializedName("date") val date: String,
    @SerializedName("reason") val reason: String
)

data class SyllabusChapterDto(
    @SerializedName("id") val id: String,
    @SerializedName("title") val title: String,
    @SerializedName("subject") val subject: String = "পদার্থবিজ্ঞান",
    @SerializedName("order_index") val orderIndex: Int = 1,
    @SerializedName("priority") val priority: String = "normal" // high, normal, low
)

data class StudentStudySettingsDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("student_id") val studentId: String,
    @SerializedName("class_band") val classBand: String = "6-8",
    @SerializedName("school_day_minutes") val schoolDayMinutes: Int = 60,
    @SerializedName("holiday_minutes") val holidayMinutes: Int = 90,
    @SerializedName("study_window_start") val studyWindowStart: String = "18:00",
    @SerializedName("study_window_end") val studyWindowEnd: String = "21:00",
    @SerializedName("rest_weekday") val restWeekday: Int? = 4, // 4 = Friday in BD
    @SerializedName("adaptive_mode") val adaptiveMode: String = "suggest", // suggest, auto_within_limits, manual
    @SerializedName("exam_name") val examName: String? = "অর্ধবার্ষিক মূল্যায়ন ২০২৬",
    @SerializedName("exam_date") val examDate: String? = "2026-12-15",
    @SerializedName("subject_priorities") val subjectPriorities: Map<String, String> = mapOf("পদার্থবিজ্ঞান" to "main", "গণিত" to "normal"),
    @SerializedName("blocked_observance_keys") val blockedObservanceKeys: List<String> = listOf("eid_ul_fitr", "durga_puja", "pohela_boishakh"),
    @SerializedName("custom_blackout_dates") val customBlackoutDates: List<BlackoutDateDto> = emptyList(),
    @SerializedName("recurring_unavailable_blocks") val recurringUnavailableBlocks: List<UnavailableBlockDto> = emptyList(),
    @SerializedName("syllabus_chapters") val syllabusChapters: List<SyllabusChapterDto> = emptyList(),
    @SerializedName("parent_locked_fields") val parentLockedFields: List<String> = emptyList(),
    @SerializedName("version") val version: Int = 1,
    @SerializedName("warnings") val warnings: List<String> = emptyList()
)

data class UpdateStudySettingsRequest(
    @SerializedName("school_day_minutes") val schoolDayMinutes: Int? = null,
    @SerializedName("holiday_minutes") val holidayMinutes: Int? = null,
    @SerializedName("study_window_start") val studyWindowStart: String? = null,
    @SerializedName("study_window_end") val studyWindowEnd: String? = null,
    @SerializedName("rest_weekday") val restWeekday: Int? = null,
    @SerializedName("adaptive_mode") val adaptiveMode: String? = null,
    @SerializedName("exam_name") val examName: String? = null,
    @SerializedName("exam_date") val examDate: String? = null,
    @SerializedName("subject_priorities") val subjectPriorities: Map<String, String>? = null,
    @SerializedName("blocked_observance_keys") val blockedObservanceKeys: List<String>? = null,
    @SerializedName("custom_blackout_dates") val customBlackoutDates: List<BlackoutDateDto>? = null,
    @SerializedName("recurring_unavailable_blocks") val recurringUnavailableBlocks: List<UnavailableBlockDto>? = null,
    @SerializedName("syllabus_chapters") val syllabusChapters: List<SyllabusChapterDto>? = null,
    @SerializedName("parent_locked_fields") val parentLockedFields: List<String>? = null,
    @SerializedName("expected_version") val expectedVersion: Int
)

// -----------------------------------------------------------------------------
// Change Requests & AI Approvals
// -----------------------------------------------------------------------------

data class StudentChangeRequestItem(
    @SerializedName("id") val id: String,
    @SerializedName("student_id") val studentId: String,
    @SerializedName("requested_changes") val requestedChanges: Map<String, Any> = emptyMap(),
    @SerializedName("status") val status: String = "pending",
    @SerializedName("created_at") val createdAt: String? = null
)

data class ReviewChangeRequestBody(
    @SerializedName("comment") val comment: String? = null
)

// -----------------------------------------------------------------------------
// Notification Preferences Schemas
// -----------------------------------------------------------------------------

data class NotificationPreferencesDto(
    @SerializedName("user_id") val userId: String? = null,
    @SerializedName("channels") val channels: Map<String, Boolean> = mapOf("in_app" to true, "push" to true),
    @SerializedName("quiet_hours_start") val quietHoursStart: String? = "22:00",
    @SerializedName("quiet_hours_end") val quietHoursEnd: String? = "07:00",
    @SerializedName("categories") val categories: Map<String, Boolean> = mapOf(
        "daily_reminder" to true,
        "task_missed" to true,
        "quiz_ready" to true,
        "plan_changed" to true,
        "weekly_parent_summary" to true
    )
)

data class UpdateNotificationPreferencesRequest(
    @SerializedName("channels") val channels: Map<String, Boolean>? = null,
    @SerializedName("quiet_hours_start") val quietHoursStart: String? = null,
    @SerializedName("quiet_hours_end") val quietHoursEnd: String? = null,
    @SerializedName("categories") val categories: Map<String, Boolean>? = null
)

// -----------------------------------------------------------------------------
// Family & Child Link Schemas
// -----------------------------------------------------------------------------

data class CreateFamilyRequest(
    @SerializedName("name") val name: String
)

data class CreateFamilyResponse(
    @SerializedName("id") val id: String,
    @SerializedName("name") val name: String
)

data class AddChildRequest(
    @SerializedName("display_name") val displayName: String,
    @SerializedName("class_level") val classLevel: Int,
    @SerializedName("group") val group: String = "general",
    @SerializedName("medium") val medium: String = "bn",
    @SerializedName("daily_minutes") val dailyMinutes: Int = 60,
    @SerializedName("school") val school: String? = null
)

data class AddChildResponse(
    @SerializedName("student_id") val studentId: String,
    @SerializedName("link_code") val linkCode: String,
    @SerializedName("link_id") val linkId: String,
    @SerializedName("expires_at") val expiresAt: String
)

// -----------------------------------------------------------------------------
// Quiz Review & Allow Schemas
// -----------------------------------------------------------------------------

data class AttemptItemReviewDto(
    @SerializedName("position") val position: Int,
    @SerializedName("question") val question: Map<String, Any>,
    @SerializedName("student_response") val studentResponse: Map<String, Any>? = null,
    @SerializedName("is_correct") val isCorrect: Boolean? = null,
    @SerializedName("points") val points: Double = 0.0,
    @SerializedName("correct_answer") val correctAnswer: Map<String, Any> = emptyMap(),
    @SerializedName("explanation") val explanation: Map<String, Any> = emptyMap()
)

data class AttemptReviewResponseDto(
    @SerializedName("attempt_id") val attemptId: String,
    @SerializedName("quiz_id") val quizId: String,
    @SerializedName("quiz_title") val quizTitle: String,
    @SerializedName("mode") val mode: String,
    @SerializedName("state") val state: String,
    @SerializedName("score") val score: Double,
    @SerializedName("total_possible_score") val totalPossibleScore: Double,
    @SerializedName("integrity_score") val integrityScore: Double,
    @SerializedName("unverified_device") val unverifiedDevice: Boolean = false,
    @SerializedName("started_at") val startedAt: String? = null,
    @SerializedName("submitted_at") val submittedAt: String? = null,
    @SerializedName("items") val items: List<AttemptItemReviewDto> = emptyList()
)

data class AllowAttemptRequestDto(
    @SerializedName("reason") val reason: String
)
