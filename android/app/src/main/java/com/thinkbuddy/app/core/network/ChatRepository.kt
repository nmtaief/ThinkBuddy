package com.thinkbuddy.app.core.network

import android.content.Context
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import java.io.BufferedReader
import java.io.IOException

open class ChatRepository(
    private val context: Context? = null,
    apiService: ApiService? = null,
    httpClient: OkHttpClient? = null
) {

    private val api: ApiService by lazy {
        apiService ?: (context?.let { ApiClient.getService(it) } ?: throw IllegalStateException("Context or ApiService required"))
    }
    private val okHttpClient: OkHttpClient by lazy {
        httpClient ?: (context?.let { ApiClient.getOkHttpClient(it) } ?: throw IllegalStateException("Context or OkHttpClient required"))
    }
    private val gson = Gson()

    open suspend fun createSession(subject: String? = null, title: String? = null): Result<ChatSessionResponse> =
        withContext(Dispatchers.IO) {
            try {
                val resp = api.createChatSession(ChatSessionCreateRequest(title = title, subject = subject))
                if (resp.isSuccessful && resp.body() != null) {
                    Result.success(resp.body()!!)
                } else {
                    Result.failure(Exception("Failed to create chat session: HTTP ${resp.code()}"))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }

    open suspend fun listSessions(limit: Int = 20): Result<List<ChatSessionResponse>> =
        withContext(Dispatchers.IO) {
            try {
                val resp = api.listChatSessions(limit = limit)
                if (resp.isSuccessful && resp.body() != null) {
                    Result.success(resp.body()!!)
                } else {
                    Result.failure(Exception("Failed to list chat sessions: HTTP ${resp.code()}"))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }

    open suspend fun getSessionHistory(sessionId: String): Result<ChatSessionDetailResponse> =
        withContext(Dispatchers.IO) {
            try {
                val resp = api.getChatSession(sessionId)
                if (resp.isSuccessful && resp.body() != null) {
                    Result.success(resp.body()!!)
                } else {
                    Result.failure(Exception("Failed to load chat history: HTTP ${resp.code()}"))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }

    /**
     * SSE Streaming chat turn with cooperative cancellation on disposal or stop tap.
     * Enforces active quiz lockout, quota checks, and textbook citation streams.
     * ZERO logging of full student question content or response text (Rule 15).
     */
    open fun streamMessage(
        sessionId: String,
        content: String,
        chapterContext: Map<String, Any>? = null,
        maxRetries: Int = 2
    ): Flow<ChatStreamEvent> = flow {
        var attempt = 0
        var succeeded = false
        var hasReceivedTokens = false
        val idempotencyKey = java.util.UUID.randomUUID().toString()

        while (attempt <= maxRetries && !succeeded) {
            attempt++
            try {
                val url = "${ApiClient.baseUrl}v1/chat/sessions/$sessionId/messages"
                val jsonPayload = gson.toJson(
                    ChatMessageCreateRequest(
                        content = content,
                        stream = true,
                        context = chapterContext,
                        idempotencyKey = idempotencyKey
                    )
                )

                val request = Request.Builder()
                    .url(url)
                    .post(jsonPayload.toRequestBody("application/json; charset=utf-8".toMediaType()))
                    .header("Accept", "text/event-stream")
                    .header("Idempotency-Key", idempotencyKey)
                    .build()

                val call = okHttpClient.newCall(request)

                try {
                    val response: Response = call.execute()

                    if (response.code == 403) {
                        emit(ChatStreamEvent.Error(code = "QUIZ_LOCKOUT", message = "একটি মূল্যায়ন কুইজ চলমান থাকায় এআই সহায়তা সাময়িকভাবে বন্ধ রয়েছে।"))
                        succeeded = true
                        response.close()
                        return@flow
                    }

                    if (response.code == 429) {
                        emit(ChatStreamEvent.Error(code = "QUOTA_EXCEEDED", message = "আজকের দৈনিক প্রশ্ন কোটা সমাপ্ত হয়েছে।"))
                        succeeded = true
                        response.close()
                        return@flow
                    }

                    if (!response.isSuccessful) {
                        emit(ChatStreamEvent.Error(code = "HTTP_${response.code}", message = "সার্ভার ত্রুটি (${response.code})"))
                        succeeded = true
                        response.close()
                        return@flow
                    }

                    val reader = BufferedReader(response.body!!.charStream())
                    var currentEvent = "message"
                    var line: String?

                    while (reader.readLine().also { line = it } != null) {
                        val currentLine = line!!.trim()
                        if (currentLine.isEmpty()) continue

                        if (currentLine.startsWith("event:")) {
                            currentEvent = currentLine.removePrefix("event:").trim()
                        } else if (currentLine.startsWith("data:")) {
                            val dataStr = currentLine.removePrefix("data:").trim()
                            val parsedEvent = parseSSEChunk(currentEvent, dataStr)
                            if (parsedEvent != null) {
                                if (parsedEvent is ChatStreamEvent.Token) {
                                    hasReceivedTokens = true
                                }
                                emit(parsedEvent)
                            }
                        }
                    }

                    succeeded = true
                    response.close()
                } finally {
                    call.cancel()
                }

            } catch (e: CancellationException) {
                // Cancelled on leave / stop
                throw e
            } catch (e: IOException) {
                // Rule: Retry only BEFORE the first token arrives.
                // If the stream dropped after partial output arrived, do not retry automatically (prevents duplicate messages or quota burn).
                if (hasReceivedTokens) {
                    emit(ChatStreamEvent.Error(code = "STREAM_INTERRUPTED", message = "সংযোগ বিচ্ছিন্ন হয়েছে। উত্তর অসম্পূর্ণ থাকতে পারে।"))
                    succeeded = true
                } else if (attempt > maxRetries) {
                    emit(ChatStreamEvent.Error(code = "NETWORK_ERROR", message = "নেটওয়ার্ক সংযোগ বিচ্ছিন্ন হয়েছে: ${e.message}"))
                } else {
                    // Exponential backoff retry before any tokens were received
                    delay(500L * attempt)
                }
            } catch (e: Exception) {
                emit(ChatStreamEvent.Error(code = "UNKNOWN_ERROR", message = e.message ?: "অপ্রত্যাশিত ত্রুটি ঘটেছে"))
                succeeded = true
            }
        }
    }.flowOn(Dispatchers.IO)

    internal fun parseSSEChunk(event: String, data: String): ChatStreamEvent? {
        return try {
            val json = JsonParser.parseString(data).asJsonObject
            when (event) {
                "meta" -> {
                    val msgId = json.get("message_id")?.asString ?: ""
                    val conf = json.get("retrieval_confidence")?.asDouble ?: 0.0
                    ChatStreamEvent.Meta(msgId, conf)
                }
                "token" -> {
                    val delta = json.get("delta")?.asString ?: ""
                    ChatStreamEvent.Token(delta)
                }
                "citation" -> {
                    val chunkId = json.get("chunk_id")?.asString
                    val bookTitle = json.get("book_title")?.asString ?: "পাঠ্যবই"
                    val chapterTitle = json.get("chapter_title")?.asString
                    val chapterNumber = json.get("chapter_number")?.asInt
                    val printedPage = json.get("printed_page")?.asInt ?: 0
                    ChatStreamEvent.Citation(
                        ChatCitationItem(
                            chunkId = chunkId,
                            bookTitle = bookTitle,
                            chapterTitle = chapterTitle,
                            chapterNumber = chapterNumber,
                            printedPage = printedPage
                        )
                    )
                }
                "done" -> {
                    val tin = json.get("tokens_in")?.asInt ?: 0
                    val tout = json.get("tokens_out")?.asInt ?: 0
                    val lat = json.get("latency_ms")?.asInt ?: 0
                    ChatStreamEvent.Done(tin, tout, lat)
                }
                else -> null
            }
        } catch (_: Exception) {
            null
        }
    }
}
