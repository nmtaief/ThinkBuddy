package com.thinkbuddy.app.core.network

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import retrofit2.Response

class ConflictException(message: String) : Exception(message)

open class ParentRepository(
    private val context: Context? = null,
    apiService: ApiService? = null
) {
    private val api: ApiService by lazy {
        apiService ?: (context?.let { ApiClient.getService(it) }
            ?: throw IllegalStateException("Context or ApiService required for ParentRepository"))
    }

    open suspend fun getOverviewDashboard(): Result<ParentOverviewResponse> = withContext(Dispatchers.IO) {
        try {
            val res = api.getParentOverviewDashboard()
            if (res.isSuccessful && res.body() != null) {
                Result.success(res.body()!!)
            } else {
                Result.failure(Exception("HTTP ${res.code()}: ${res.errorBody()?.string() ?: "Failed to fetch dashboard"}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    open suspend fun getStudentDashboard(studentId: String): Result<StudentDashboardResponse> = withContext(Dispatchers.IO) {
        try {
            val res = api.getParentStudentDashboard(studentId)
            if (res.isSuccessful && res.body() != null) {
                Result.success(res.body()!!)
            } else {
                Result.failure(Exception("HTTP ${res.code()}: ${res.errorBody()?.string() ?: "Failed to fetch student dashboard"}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    open suspend fun getStudySettings(studentId: String): Result<StudentStudySettingsDto> = withContext(Dispatchers.IO) {
        try {
            val res = api.getStudySettings(studentId)
            if (res.isSuccessful && res.body() != null) {
                Result.success(res.body()!!)
            } else {
                Result.failure(Exception("HTTP ${res.code()}: Failed to fetch study settings"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    open suspend fun updateStudySettings(
        studentId: String,
        request: UpdateStudySettingsRequest
    ): Result<StudentStudySettingsDto> = withContext(Dispatchers.IO) {
        try {
            val res = api.updateStudySettings(studentId, request)
            if (res.isSuccessful && res.body() != null) {
                Result.success(res.body()!!)
            } else if (res.code() == 409) {
                Result.failure(ConflictException("অন্য একটি ডিভাইস বা ব্রাউজারে সেটিংস পরিবর্তিত হয়েছে। অনুগ্রহ করে রিফ্রেশ করে আবার চেষ্টা করুন। (409 Conflict)"))
            } else {
                Result.failure(Exception("HTTP ${res.code()}: ${res.errorBody()?.string() ?: "Failed to save settings"}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    open suspend fun getAiSuggestions(studentId: String): Result<List<ParentAiSuggestionView>> = withContext(Dispatchers.IO) {
        try {
            val res = api.getAISuggestions(studentId)
            if (res.isSuccessful && res.body() != null) {
                Result.success(res.body()!!)
            } else {
                Result.failure(Exception("HTTP ${res.code()}: Failed to fetch AI suggestions"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    open suspend fun approveAiSuggestion(studentId: String, suggestionId: String): Result<Map<String, Any>> = withContext(Dispatchers.IO) {
        try {
            val res = api.approveSuggestion(studentId, suggestionId)
            if (res.isSuccessful && res.body() != null) {
                Result.success(res.body()!!)
            } else if (res.code() == 409) {
                Result.failure(ConflictException("প্রস্তাবনাটি ইতিমধ্যে প্রক্রিয়াজাত হয়েছে (409 Conflict)"))
            } else {
                Result.failure(Exception("HTTP ${res.code()}: Failed to approve suggestion"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    open suspend fun rejectAiSuggestion(studentId: String, suggestionId: String): Result<Map<String, Any>> = withContext(Dispatchers.IO) {
        try {
            val res = api.rejectSuggestion(studentId, suggestionId)
            if (res.isSuccessful && res.body() != null) {
                Result.success(res.body()!!)
            } else {
                Result.failure(Exception("HTTP ${res.code()}: Failed to reject suggestion"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    open suspend fun undoAiAdjustment(
        studentId: String,
        adjustmentId: String,
        expectedVersion: Int? = null
    ): Result<Map<String, Any>> = withContext(Dispatchers.IO) {
        try {
            val res = api.undoAdjustment(studentId, adjustmentId, expectedVersion)
            if (res.isSuccessful && res.body() != null) {
                Result.success(res.body()!!)
            } else if (res.code() == 409) {
                Result.failure(ConflictException("সেটিংস ইতিমধ্যে পরিবর্তিত হয়েছে। পূর্বাবস্থায় ফেরানো সম্ভব নয় (409 Conflict)"))
            } else {
                Result.failure(Exception("HTTP ${res.code()}: Failed to undo adjustment"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    open suspend fun approveChangeRequest(
        studentId: String,
        requestId: String,
        comment: String? = null
    ): Result<Map<String, Any>> = withContext(Dispatchers.IO) {
        try {
            val res = api.approveStudentChangeRequest(studentId, requestId, ReviewChangeRequestBody(comment))
            if (res.isSuccessful && res.body() != null) {
                Result.success(res.body()!!)
            } else {
                Result.failure(Exception("HTTP ${res.code()}: Failed to approve change request"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    open suspend fun declineChangeRequest(
        studentId: String,
        requestId: String,
        comment: String? = null
    ): Result<Map<String, Any>> = withContext(Dispatchers.IO) {
        try {
            val res = api.declineStudentChangeRequest(studentId, requestId, ReviewChangeRequestBody(comment))
            if (res.isSuccessful && res.body() != null) {
                Result.success(res.body()!!)
            } else {
                Result.failure(Exception("HTTP ${res.code()}: Failed to decline change request"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    open suspend fun getNotificationPreferences(): Result<NotificationPreferencesDto> = withContext(Dispatchers.IO) {
        try {
            val res = api.getNotificationPreferences()
            if (res.isSuccessful && res.body() != null) {
                Result.success(res.body()!!)
            } else {
                Result.failure(Exception("HTTP ${res.code()}: Failed to load notification preferences"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    open suspend fun updateNotificationPreferences(request: UpdateNotificationPreferencesRequest): Result<NotificationPreferencesDto> = withContext(Dispatchers.IO) {
        try {
            val res = api.updateNotificationPreferences(request)
            if (res.isSuccessful && res.body() != null) {
                Result.success(res.body()!!)
            } else {
                Result.failure(Exception("HTTP ${res.code()}: Failed to save notification preferences"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    open suspend fun createFamily(name: String): Result<CreateFamilyResponse> = withContext(Dispatchers.IO) {
        try {
            val res = api.createFamily(CreateFamilyRequest(name))
            if (res.isSuccessful && res.body() != null) {
                Result.success(res.body()!!)
            } else {
                Result.failure(Exception("HTTP ${res.code()}: Failed to create family"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    open suspend fun addChild(
        familyId: String,
        request: AddChildRequest
    ): Result<AddChildResponse> = withContext(Dispatchers.IO) {
        try {
            val res = api.addChildToFamily(familyId, request)
            if (res.isSuccessful && res.body() != null) {
                Result.success(res.body()!!)
            } else {
                Result.failure(Exception("HTTP ${res.code()}: ${res.errorBody()?.string() ?: "Failed to add child"}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    open suspend fun reviewQuiz(attemptId: String): Result<AttemptReviewResponseDto> = withContext(Dispatchers.IO) {
        try {
            val res = api.reviewQuiz(attemptId)
            if (res.isSuccessful && res.body() != null) {
                // Map to AttemptReviewResponseDto
                val body = res.body()!!
                val mapped = AttemptReviewResponseDto(
                    attemptId = body.attemptId,
                    quizId = body.quizId,
                    quizTitle = "কুইজ মূল্যায়ন",
                    mode = body.mode,
                    state = "submitted",
                    score = body.score.toDouble(),
                    totalPossibleScore = body.totalScore.toDouble(),
                    integrityScore = 1.0,
                    unverifiedDevice = false,
                    startedAt = null,
                    submittedAt = body.submittedAt,
                    items = body.items.mapIndexed { index, item ->
                        AttemptItemReviewDto(
                            position = index + 1,
                            question = mapOf(
                                "prompt" to item.prompt,
                                "prompt_bn" to item.promptBn,
                                "chapter_title" to (item.chapterTitle ?: ""),
                                "printed_page" to (item.printedPage ?: 0)
                            ),
                            studentResponse = item.studentResponse,
                            isCorrect = item.isCorrect,
                            points = if (item.isCorrect) 1.0 else 0.0,
                            correctAnswer = item.correctResponse,
                            explanation = mapOf(
                                "text" to (item.explanation ?: ""),
                                "text_bn" to (item.explanationBn ?: "")
                            )
                        )
                    }
                )
                Result.success(mapped)
            } else {
                Result.failure(Exception("HTTP ${res.code()}: Active attempt or review not found"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    open suspend fun allowAttempt(attemptId: String, reason: String): Result<Map<String, Any>> = withContext(Dispatchers.IO) {
        try {
            val res = api.allowQuizAttempt(attemptId, AllowAttemptRequestDto(reason))
            if (res.isSuccessful && res.body() != null) {
                Result.success(res.body()!!)
            } else {
                Result.failure(Exception("HTTP ${res.code()}: Failed to allow attempt"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
