package com.thinkbuddy.app.core.network

import com.google.gson.annotations.SerializedName
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

// --- Config & Auth Models ---

data class ClientConfigResponse(
    @SerializedName("min_supported_version") val minSupportedVersion: String = "1.0.0",
    @SerializedName("quiz_security_mode") val quizSecurityMode: String = "assessed_app_only",
    @SerializedName("features") val features: Map<String, Boolean> = emptyMap(),
    @SerializedName("allowed_assessment_modes") val allowedAssessmentModes: List<String> = listOf("practice", "assessed"),
    @SerializedName("locale") val locale: String = "bn"
)

data class AuthExchangeRequest(
    @SerializedName("provider_token") val providerToken: String,
    @SerializedName("role") val role: String = "student",
    @SerializedName("link_code") val linkCode: String? = null,
    @SerializedName("display_name") val displayName: String? = null,
    @SerializedName("locale") val locale: String = "bn"
)

data class UserProfileResponse(
    @SerializedName("id") val id: String,
    @SerializedName("auth_provider") val authProvider: String = "fake",
    @SerializedName("auth_uid") val authUid: String = "uid-1",
    @SerializedName("role") val role: String = "student",
    @SerializedName("display_name") val displayName: String = "শিক্ষার্থী",
    @SerializedName("phone") val phone: String? = null,
    @SerializedName("email") val email: String? = null,
    @SerializedName("locale") val locale: String = "bn",
    @SerializedName("status") val status: String = "active"
)

data class AuthExchangeResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String,
    @SerializedName("token_type") val tokenType: String = "bearer",
    @SerializedName("expires_in") val expiresIn: Int = 3600,
    @SerializedName("user_id") val userId: String? = null,
    @SerializedName("role") val role: String = "student"
)

// --- Planner & Tasks Models ---

data class PlannerTaskResponse(
    @SerializedName("id") val id: String,
    @SerializedName("plan_day_id") val planDayId: String? = null,
    @SerializedName("student_id") val studentId: String? = null,
    @SerializedName("subject") val subject: String,
    @SerializedName("type") val type: String = "study",
    @SerializedName("chapter_id") val chapterId: String? = null,
    @SerializedName("refs") val refs: Map<String, Any?>? = null,
    @SerializedName("est_minutes") val estMinutes: Int = 30,
    @SerializedName("status") val status: String = "pending",
    @SerializedName("source") val source: String = "curriculum",
    @SerializedName("completed_at") val completedAt: String? = null
)

data class TodayTask(
    @SerializedName("id") val id: String,
    @SerializedName("subject") val subject: String,
    @SerializedName("subject_bn") val subjectBn: String,
    @SerializedName("chapter") val chapter: String,
    @SerializedName("chapter_bn") val chapterBn: String,
    @SerializedName("target_minutes") val targetMinutes: Int,
    @SerializedName("completed_minutes") val completedMinutes: Int,
    @SerializedName("status") val status: String,
    @SerializedName("printed_pages") val printedPages: String = "৪২ – ৫৬",
    @SerializedName("guideline") val guideline: String = "",
    @SerializedName("has_practice_quiz") val hasPracticeQuiz: Boolean = true
)

data class TodayScheduleResponse(
    @SerializedName("date") val date: String = "",
    @SerializedName("student_id") val studentId: String? = null,
    @SerializedName("study_tasks") val studyTasks: List<PlannerTaskResponse> = emptyList(),
    @SerializedName("revision_tasks") val revisionTasks: List<PlannerTaskResponse> = emptyList(),
    @SerializedName("homework_tasks") val homeworkTasks: List<PlannerTaskResponse> = emptyList(),
    @SerializedName("quiz_tasks") val quizTasks: List<PlannerTaskResponse> = emptyList(),
    @SerializedName("total_planned_minutes") val totalPlannedMinutes: Int = 135,
    @SerializedName("completed_minutes") val completedMinutes: Int = 20,
    @SerializedName("completion_percentage") val completionPercentage: Float = 14.8f,
    @SerializedName("exam_countdown_days") val examCountdownDays: Map<String, Int> = emptyMap(),
    @SerializedName("streak") val streak: Int = 7,
    @SerializedName("provider") val provider: String = "deterministic",
    @SerializedName("reason_for_parents") val reasonForParents: String? = null,
    @SerializedName("tasks") val tasks: List<TodayTask> = emptyList()
)

data class PlanDayResponse(
    @SerializedName("date") val date: String,
    @SerializedName("planned_minutes") val plannedMinutes: Int,
    @SerializedName("day_type") val dayType: String,
    @SerializedName("tasks") val tasks: List<PlannerTaskResponse> = emptyList()
)

data class PlanResponse(
    @SerializedName("setup_id") val setupId: String? = null,
    @SerializedName("student_id") val studentId: String? = null,
    @SerializedName("version") val version: Int = 1,
    @SerializedName("generated_at") val generatedAt: String? = null,
    @SerializedName("reason") val reason: String? = null,
    @SerializedName("status") val status: String = "active",
    @SerializedName("days") val days: List<PlanDayResponse> = emptyList(),
    @SerializedName("warnings") val warnings: List<String> = emptyList()
)

data class UpdateTaskStatusRequest(
    @SerializedName("status") val status: String,
    @SerializedName("completed_minutes") val completedMinutes: Int? = null
)

// --- Revision & Spaced Repetition Models ---

data class RevisionItemResponse(
    @SerializedName("id") val id: String,
    @SerializedName("chapter_id") val chapterId: String? = null,
    @SerializedName("chapter_title") val chapterTitle: String,
    @SerializedName("subject") val subject: String,
    @SerializedName("question_id") val questionId: String? = null,
    @SerializedName("box") val box: Int = 1,
    @SerializedName("due_at") val dueAt: String? = null,
    @SerializedName("is_overdue") val isOverdue: Boolean = false,
    @SerializedName("last_result") val lastResult: String? = null
)

data class RevisionReviewRequest(
    @SerializedName("quality") val quality: Int
)

// --- Progress & Mastery Models ---

data class ProgressSummaryResponse(
    @SerializedName("student_id") val studentId: String? = null,
    @SerializedName("overall_mastery") val overallMastery: Float = 0.0f,
    @SerializedName("confidence") val confidence: Float = 0.0f,
    @SerializedName("status") val status: String = "not_enough_data",
    @SerializedName("status_label_bn") val statusLabelBn: String = "পর্যাপ্ত তথ্য নেই",
    @SerializedName("streak_days") val streakDays: Int = 0,
    @SerializedName("study_minutes_today") val studyMinutesToday: Int = 0,
    @SerializedName("tasks_completed_today") val tasksCompletedToday: Int = 0,
    @SerializedName("tasks_total_today") val tasksTotalToday: Int = 0
)

data class ChapterMasteryItem(
    @SerializedName("chapter_id") val chapterId: String,
    @SerializedName("chapter_title") val chapterTitle: String,
    @SerializedName("chapter_number") val chapterNumber: Int? = null,
    @SerializedName("subject") val subject: String,
    @SerializedName("score") val score: Float = 0.0f,
    @SerializedName("confidence") val confidence: Float = 0.0f,
    @SerializedName("status") val status: String = "not_enough_data",
    @SerializedName("status_label_bn") val statusLabelBn: String = "পর্যাপ্ত তথ্য নেই",
    @SerializedName("last_seen_at") val lastSeenAt: String? = null
)

data class NeedsPracticeTopic(
    @SerializedName("chapter_id") val chapterId: String,
    @SerializedName("chapter_title") val chapterTitle: String,
    @SerializedName("subject") val subject: String,
    @SerializedName("score") val score: Float = 0.0f,
    @SerializedName("confidence") val confidence: Float = 0.0f,
    @SerializedName("suggested_action") val suggestedAction: String = "",
    @SerializedName("suggested_action_bn") val suggestedActionBn: String = ""
)

// --- Quizzes & Secure Assessment Models ---

data class StartAttemptRequest(
    @SerializedName("attempt_id") val attemptId: String? = null,
    @SerializedName("device_id") val deviceId: String? = null,
    @SerializedName("integrity_verdict") val integrityVerdict: String? = null,
    @SerializedName("integrity_token") val integrityToken: String? = null
)

data class CreateAttemptInitResponse(
    @SerializedName("attempt_id") val attemptId: String,
    @SerializedName("state") val state: String,
    @SerializedName("nonce") val nonce: String,
    @SerializedName("deadline_at") val deadlineAt: String? = null,
    @SerializedName("attempt_token") val attemptToken: String? = null
)

data class QuestionOptionPublic(
    @SerializedName("id") val id: Int,
    @SerializedName("text") val text: String,
    @SerializedName("text_bn") val textBn: String
)

data class AttemptItemPublic(
    @SerializedName("id") val id: String,
    @SerializedName("position") val position: Int,
    @SerializedName("type") val type: String = "mcq",
    @SerializedName("prompt") val prompt: String = "",
    @SerializedName("prompt_bn") val promptBn: String = "",
    @SerializedName("options") val options: List<QuestionOptionPublic> = emptyList(),
    @SerializedName("nonce") val nonce: String = ""
)

data class StartAttemptResponse(
    @SerializedName("attempt_id") val attemptId: String,
    @SerializedName("state") val state: String,
    @SerializedName("current_position") val currentPosition: Int = 1,
    @SerializedName("total_items") val totalItems: Int = 5,
    @SerializedName("current_item") val currentItem: AttemptItemPublic? = null,
    @SerializedName("time_limit_s") val timeLimitS: Int = 900,
    @SerializedName("deadline_at") val deadlineAt: String? = null,
    @SerializedName("attempt_token") val attemptToken: String? = null
)

data class AnswerItemRequest(
    @SerializedName("nonce") val nonce: String,
    @SerializedName("response") val response: Map<String, Any>,
    @SerializedName("time_spent_ms") val timeSpentMs: Int = 0
)

data class AnswerItemResponse(
    @SerializedName("recorded") val recorded: Boolean = true,
    @SerializedName("position") val position: Int,
    @SerializedName("next_position") val nextPosition: Int? = null,
    @SerializedName("is_last") val isLast: Boolean = false,
    @SerializedName("next_item") val nextItem: AttemptItemPublic? = null,
    @SerializedName("feedback") val feedback: Map<String, Any>? = null
)

data class AttemptEventRequest(
    @SerializedName("type") val type: String,
    @SerializedName("meta") val meta: Map<String, Any> = emptyMap()
)

data class AttemptEventResponse(
    @SerializedName("recorded") val recorded: Boolean,
    @SerializedName("integrity_score") val integrityScore: Float,
    @SerializedName("state") val state: String
)

data class SubmitAttemptResponse(
    @SerializedName("attempt_id") val attemptId: String,
    @SerializedName("score") val score: Float = 0.0f,
    @SerializedName("total_score") val totalScore: Float = 5.0f,
    @SerializedName("percentage") val percentage: Float = 0.0f,
    @SerializedName("passed") val passed: Boolean = false,
    @SerializedName("mastery_updated") val masteryUpdated: Boolean = false,
    @SerializedName("parent_flag") val parentFlag: Boolean = false,
    @SerializedName("feedback_summary_bn") val feedbackSummaryBn: String? = null
)

data class AttemptItemReview(
    @SerializedName("position") val position: Int,
    @SerializedName("question_id") val questionId: String,
    @SerializedName("prompt") val prompt: String = "",
    @SerializedName("prompt_bn") val promptBn: String = "",
    @SerializedName("options") val options: List<QuestionOptionPublic> = emptyList(),
    @SerializedName("student_response") val studentResponse: Map<String, Any> = emptyMap(),
    @SerializedName("is_correct") val isCorrect: Boolean = false,
    @SerializedName("correct_response") val correctResponse: Map<String, Any> = emptyMap(),
    @SerializedName("explanation") val explanation: String? = null,
    @SerializedName("explanation_bn") val explanationBn: String? = null,
    @SerializedName("printed_page") val printedPage: Int? = null,
    @SerializedName("chapter_title") val chapterTitle: String? = null
)

data class AttemptReviewResponse(
    @SerializedName("attempt_id") val attemptId: String,
    @SerializedName("quiz_id") val quizId: String,
    @SerializedName("student_id") val studentId: String,
    @SerializedName("mode") val mode: String,
    @SerializedName("score") val score: Float,
    @SerializedName("total_score") val totalScore: Float,
    @SerializedName("percentage") val percentage: Float,
    @SerializedName("passed") val passed: Boolean,
    @SerializedName("submitted_at") val submittedAt: String? = null,
    @SerializedName("items") val items: List<AttemptItemReview> = emptyList()
)

// Legacy compatibility for simple callers
data class CreateAttemptRequestLegacy(
    @SerializedName("mode") val mode: String = "practice",
    @SerializedName("integrity_verdict") val integrityVerdict: String? = null
)

// --- Parent & Study Settings Models ---

data class ChildSummary(
    @SerializedName("student_id") val studentId: String,
    @SerializedName("name") val name: String,
    @SerializedName("class_band") val classBand: String,
    @SerializedName("streak_days") val streakDays: Int,
    @SerializedName("daily_target_minutes") val dailyTargetMinutes: Int,
    @SerializedName("daily_completed_minutes") val dailyCompletedMinutes: Int,
    @SerializedName("mastery_score") val masteryScore: Float
)

data class StudySettingsResponse(
    @SerializedName("student_id") val studentId: String,
    @SerializedName("school_day_minutes") val schoolDayMinutes: Int,
    @SerializedName("holiday_minutes") val holidayMinutes: Int,
    @SerializedName("adaptive_mode_enabled") val adaptiveModeEnabled: Boolean,
    @SerializedName("blackout_dates") val blackoutDates: List<String> = emptyList(),
    @SerializedName("version") val version: Int
)

data class AISuggestion(
    @SerializedName("id") val id: String,
    @SerializedName("title_bn") val titleBn: String,
    @SerializedName("rationale_bn") val rationaleBn: String,
    @SerializedName("proposed_minutes") val proposedMinutes: Int,
    @SerializedName("status") val status: String
)

data class RedeemLinkRequest(
    @SerializedName("code") val code: String
)

data class RedeemLinkResponse(
    @SerializedName("family_id") val familyId: String,
    @SerializedName("student_id") val studentId: String,
    @SerializedName("student_name") val studentName: String
)

// --- Retrofit API Service ---

interface ApiService {
    @GET("v1/client/config")
    suspend fun getClientConfig(): Response<ClientConfigResponse>

    @GET("v1/auth/me")
    suspend fun getMe(): Response<UserProfileResponse>

    @POST("v1/auth/exchange")
    suspend fun exchangeToken(
        @Body request: AuthExchangeRequest
    ): Response<AuthExchangeResponse>

    // Planner & Today
    @GET("v1/students/{student_id}/today")
    suspend fun getTodaySchedule(
        @Path("student_id") studentId: String
    ): Response<TodayScheduleResponse>

    @GET("v1/students/{student_id}/plan")
    suspend fun getStudentPlan(
        @Path("student_id") studentId: String
    ): Response<PlanResponse>

    @PATCH("v1/tasks/{task_id}")
    suspend fun updateTaskStatus(
        @Path("task_id") taskId: String,
        @Body request: UpdateTaskStatusRequest
    ): Response<PlannerTaskResponse>

    // Revision & Spaced Repetition
    @GET("v1/revision/daily")
    suspend fun getDailyRevision(): Response<List<RevisionItemResponse>>

    @POST("v1/revision/{item_id}/review")
    suspend fun submitRevisionReview(
        @Path("item_id") itemId: String,
        @Body request: RevisionReviewRequest
    ): Response<Map<String, Any>>

    // Progress & Mastery
    @GET("v1/progress/summary")
    suspend fun getProgressSummary(
        @Query("student_id") studentId: String? = null
    ): Response<ProgressSummaryResponse>

    @GET("v1/progress/mastery")
    suspend fun getProgressMastery(
        @Query("student_id") studentId: String? = null
    ): Response<List<ChapterMasteryItem>>

    @GET("v1/progress/weak-points")
    suspend fun getWeakPoints(
        @Query("student_id") studentId: String? = null
    ): Response<List<NeedsPracticeTopic>>

    // Quizzes & Assessments
    @POST("v1/quizzes/{quiz_id}/attempts/create")
    suspend fun createQuizAttempt(
        @Path("quiz_id") quizId: String,
        @Body request: StartAttemptRequest
    ): Response<CreateAttemptInitResponse>

    @POST("v1/quizzes/{quiz_id}/attempts")
    suspend fun startQuizAttempt(
        @Path("quiz_id") quizId: String,
        @Body request: StartAttemptRequest
    ): Response<StartAttemptResponse>

    @POST("v1/attempts/{attempt_id}/attest")
    suspend fun attestQuizAttempt(
        @Path("attempt_id") attemptId: String,
        @Body request: StartAttemptRequest
    ): Response<StartAttemptResponse>

    @POST("v1/attempts/{attempt_id}/items/{position}/answer")
    suspend fun answerQuizItem(
        @Path("attempt_id") attemptId: String,
        @Path("position") position: Int,
        @Body request: AnswerItemRequest
    ): Response<AnswerItemResponse>

    @POST("v1/attempts/{attempt_id}/events")
    suspend fun recordAttemptEvent(
        @Path("attempt_id") attemptId: String,
        @Body request: AttemptEventRequest
    ): Response<AttemptEventResponse>

    @POST("v1/attempts/{attempt_id}/submit")
    suspend fun submitQuiz(
        @Path("attempt_id") attemptId: String
    ): Response<SubmitAttemptResponse>

    @GET("v1/attempts/{attempt_id}/review")
    suspend fun reviewQuiz(
        @Path("attempt_id") attemptId: String
    ): Response<AttemptReviewResponse>

    // AI Chat Sessions & History (Rule 15: server authority, no local persistence)
    @POST("v1/chat/sessions")
    suspend fun createChatSession(
        @Body request: ChatSessionCreateRequest
    ): Response<ChatSessionResponse>

    @GET("v1/chat/sessions")
    suspend fun listChatSessions(
        @Query("limit") limit: Int = 20,
        @Query("offset") offset: Int = 0
    ): Response<List<ChatSessionResponse>>

    @GET("v1/chat/sessions/{session_id}")
    suspend fun getChatSession(
        @Path("session_id") sessionId: String
    ): Response<ChatSessionDetailResponse>

    @POST("v1/chat/sessions/{session_id}/messages")
    suspend fun sendChatMessage(
        @Path("session_id") sessionId: String,
        @Body request: ChatMessageCreateRequest
    ): Response<ChatMessageResponse>

    // Parent Endpoints (P07 & P08a Group 4)
    @GET("v1/parents/me/dashboard")
    suspend fun getParentOverviewDashboard(): Response<ParentOverviewResponse>

    @GET("v1/parents/me/students/{student_id}/dashboard")
    suspend fun getParentStudentDashboard(
        @Path("student_id") studentId: String
    ): Response<StudentDashboardResponse>

    @GET("v1/parents/me/students")
    suspend fun getParentStudents(): Response<List<ChildSummary>>

    @GET("v1/students/{student_id}/study-settings")
    suspend fun getStudySettings(
        @Path("student_id") studentId: String
    ): Response<StudentStudySettingsDto>

    @PUT("v1/students/{student_id}/study-settings")
    suspend fun updateStudySettings(
        @Path("student_id") studentId: String,
        @Body request: UpdateStudySettingsRequest
    ): Response<StudentStudySettingsDto>

    @GET("v1/students/{student_id}/ai-suggestions")
    suspend fun getAISuggestions(
        @Path("student_id") studentId: String
    ): Response<List<ParentAiSuggestionView>>

    @POST("v1/students/{student_id}/ai-suggestions/{suggestion_id}/approve")
    suspend fun approveSuggestion(
        @Path("student_id") studentId: String,
        @Path("suggestion_id") suggestionId: String
    ): Response<Map<String, Any>>

    @POST("v1/students/{student_id}/ai-suggestions/{suggestion_id}/reject")
    suspend fun rejectSuggestion(
        @Path("student_id") studentId: String,
        @Path("suggestion_id") suggestionId: String
    ): Response<Map<String, Any>>

    @POST("v1/students/{student_id}/ai-adjustments/{adjustment_id}/undo")
    suspend fun undoAdjustment(
        @Path("student_id") studentId: String,
        @Path("adjustment_id") adjustmentId: String,
        @Query("expected_version") expectedVersion: Int? = null
    ): Response<Map<String, Any>>

    @POST("v1/parents/me/students/{student_id}/change-requests/{request_id}/approve")
    suspend fun approveStudentChangeRequest(
        @Path("student_id") studentId: String,
        @Path("request_id") requestId: String,
        @Body body: ReviewChangeRequestBody? = null
    ): Response<Map<String, Any>>

    @POST("v1/parents/me/students/{student_id}/change-requests/{request_id}/decline")
    suspend fun declineStudentChangeRequest(
        @Path("student_id") studentId: String,
        @Path("request_id") requestId: String,
        @Body body: ReviewChangeRequestBody? = null
    ): Response<Map<String, Any>>

    @GET("v1/notifications/preferences")
    suspend fun getNotificationPreferences(): Response<NotificationPreferencesDto>

    @PUT("v1/notifications/preferences")
    suspend fun updateNotificationPreferences(
        @Body request: UpdateNotificationPreferencesRequest
    ): Response<NotificationPreferencesDto>

    @POST("v1/families")
    suspend fun createFamily(
        @Body request: CreateFamilyRequest
    ): Response<CreateFamilyResponse>

    @POST("v1/families/{family_id}/students")
    suspend fun addChildToFamily(
        @Path("family_id") familyId: String,
        @Body request: AddChildRequest
    ): Response<AddChildResponse>

    @POST("v1/attempts/{attempt_id}/allow")
    suspend fun allowQuizAttempt(
        @Path("attempt_id") attemptId: String,
        @Body request: AllowAttemptRequestDto
    ): Response<Map<String, Any>>

    @POST("v1/links/redeem")
    suspend fun redeemLinkCode(
        @Body request: RedeemLinkRequest
    ): Response<RedeemLinkResponse>
}
