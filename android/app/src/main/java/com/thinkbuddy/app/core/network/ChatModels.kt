package com.thinkbuddy.app.core.network

import com.google.gson.annotations.SerializedName

data class ChatSessionResponse(
    @SerializedName("id") val id: String,
    @SerializedName("title") val title: String,
    @SerializedName("subject") val subject: String? = null,
    @SerializedName("created_at") val createdAt: String? = null
)

data class ChatSessionCreateRequest(
    @SerializedName("title") val title: String? = null,
    @SerializedName("subject") val subject: String? = null
)

data class ChatMessageCreateRequest(
    @SerializedName("content") val content: String,
    @SerializedName("stream") val stream: Boolean = true,
    @SerializedName("context") val context: Map<String, Any>? = null,
    @SerializedName("idempotency_key") val idempotencyKey: String = java.util.UUID.randomUUID().toString()
)

data class ChatCitationItem(
    @SerializedName("chunk_id") val chunkId: String? = null,
    @SerializedName("book_title") val bookTitle: String,
    @SerializedName("chapter_title") val chapterTitle: String? = null,
    @SerializedName("chapter_number") val chapterNumber: Int? = null,
    @SerializedName("printed_page") val printedPage: Int
)

data class ChatMessageResponse(
    @SerializedName("id") val id: String,
    @SerializedName("role") val role: String, // "user" or "assistant"
    @SerializedName("content") val content: String,
    @SerializedName("citations") val citations: List<ChatCitationItem> = emptyList(),
    @SerializedName("created_at") val createdAt: String? = null,
    @SerializedName("retrieval_confidence") val retrievalConfidence: Double? = null
)

data class ChatSessionDetailResponse(
    @SerializedName("id") val id: String,
    @SerializedName("title") val title: String,
    @SerializedName("subject") val subject: String? = null,
    @SerializedName("messages") val messages: List<ChatMessageResponse> = emptyList()
)

sealed interface ChatStreamEvent {
    data class Meta(val messageId: String, val confidence: Double) : ChatStreamEvent
    data class Token(val delta: String) : ChatStreamEvent
    data class Citation(val citation: ChatCitationItem) : ChatStreamEvent
    data class Done(val tokensIn: Int, val tokensOut: Int, val latencyMs: Int) : ChatStreamEvent
    data class Error(val code: String, val message: String) : ChatStreamEvent
}
