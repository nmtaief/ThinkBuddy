package com.thinkbuddy.app.ui.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.thinkbuddy.app.core.network.ChatCitationItem
import com.thinkbuddy.app.core.network.ChatRepository
import com.thinkbuddy.app.core.network.ChatSessionResponse
import com.thinkbuddy.app.core.network.ChatStreamEvent
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID

data class UiChatMessage(
    val id: String = UUID.randomUUID().toString(),
    val role: String, // "user" or "assistant"
    val content: String,
    val citations: List<ChatCitationItem> = emptyList(),
    val isStreaming: Boolean = false,
    val isNotFound: Boolean = false,
    val isInterrupted: Boolean = false,
    val likelyChapter: String? = null
)

data class ChapterContext(
    val subject: String = "পদার্থবিজ্ঞান (Physics)",
    val chapter: String = "অধ্যায় ৩: বল ও গতি",
    val printedPage: Int = 42
)

data class ChatUiState(
    val isLoading: Boolean = false,
    val activeSessionId: String? = null,
    val sessions: List<ChatSessionResponse> = emptyList(),
    val messages: List<UiChatMessage> = emptyList(),
    val isStreaming: Boolean = false,
    val isQuizLocked: Boolean = false,
    val isQuotaExceeded: Boolean = false,
    val currentContext: ChapterContext = ChapterContext(),
    val errorMessage: String? = null
)

class ChatViewModel(
    private val repository: ChatRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    private var streamJob: Job? = null
    private var lastPrompt: String? = null

    init {
        loadSessions()
    }

    fun loadSessions() {
        _uiState.update { it.copy(isLoading = true, errorMessage = null) }
        viewModelScope.launch {
            val result = repository.listSessions()
            result.onSuccess { sessions ->
                _uiState.update { state ->
                    state.copy(
                        isLoading = false,
                        sessions = sessions,
                        activeSessionId = state.activeSessionId ?: sessions.firstOrNull()?.id
                    )
                }
                val activeId = _uiState.value.activeSessionId
                if (activeId != null) {
                    loadSessionHistory(activeId)
                }
            }.onFailure {
                _uiState.update { state -> state.copy(isLoading = false) }
            }
        }
    }

    fun selectSession(sessionId: String) {
        if (streamJob?.isActive == true) {
            stopStreaming()
        }
        _uiState.update { it.copy(activeSessionId = sessionId) }
        loadSessionHistory(sessionId)
    }

    fun startNewSession(subject: String? = null) {
        if (streamJob?.isActive == true) {
            stopStreaming()
        }
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            val subj = subject ?: _uiState.value.currentContext.subject
            val res = repository.createSession(subject = subj, title = "নতুন প্রশ্নোত্তর ($subj)")
            res.onSuccess { session ->
                _uiState.update { state ->
                    state.copy(
                        isLoading = false,
                        activeSessionId = session.id,
                        sessions = listOf(session) + state.sessions,
                        messages = emptyList(),
                        isQuizLocked = false,
                        isQuotaExceeded = false
                    )
                }
            }.onFailure { err ->
                _uiState.update { it.copy(isLoading = false, errorMessage = err.message) }
            }
        }
    }

    fun loadSessionHistory(sessionId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            val res = repository.getSessionHistory(sessionId)
            res.onSuccess { detail ->
                val uiMsgs = detail.messages.map { m ->
                    val isNotFound = m.content.contains("খুঁজে পাওয়া যায়নি") || m.content.contains("couldn't find")
                    UiChatMessage(
                        id = m.id,
                        role = m.role,
                        content = m.content,
                        citations = m.citations,
                        isNotFound = isNotFound
                    )
                }
                _uiState.update { state ->
                    state.copy(
                        isLoading = false,
                        messages = uiMsgs,
                        isQuizLocked = false,
                        isQuotaExceeded = false
                    )
                }
            }.onFailure { err ->
                _uiState.update { it.copy(isLoading = false, errorMessage = err.message) }
            }
        }
    }

    fun setChapterContext(subject: String, chapter: String, printedPage: Int) {
        _uiState.update {
            it.copy(currentContext = ChapterContext(subject, chapter, printedPage))
        }
    }

    fun sendMessage(rawPrompt: String) {
        val sanitized = sanitizePrompt(rawPrompt)
        if (sanitized.isBlank()) return
        lastPrompt = sanitized

        var activeId = _uiState.value.activeSessionId
        if (activeId == null) {
            viewModelScope.launch {
                val res = repository.createSession(
                    subject = _uiState.value.currentContext.subject,
                    title = sanitized.take(30)
                )
                res.onSuccess { session ->
                    _uiState.update { it.copy(activeSessionId = session.id, sessions = listOf(session) + it.sessions) }
                    executeSend(session.id, sanitized)
                }.onFailure { _ ->
                    // Graceful fallback to local session id so message appears and retry is enabled
                    val localSessionId = "sess_" + UUID.randomUUID().toString().take(8)
                    _uiState.update { it.copy(activeSessionId = localSessionId) }
                    executeSend(localSessionId, sanitized)
                }
            }
        } else {
            executeSend(activeId, sanitized)
        }
    }

    private fun executeSend(sessionId: String, prompt: String) {
        val userMsg = UiChatMessage(role = "user", content = prompt)
        val assistantMsgId = UUID.randomUUID().toString()
        val assistantPlaceholder = UiChatMessage(
            id = assistantMsgId,
            role = "assistant",
            content = "",
            isStreaming = true
        )

        _uiState.update { state ->
            state.copy(
                messages = state.messages + userMsg + assistantPlaceholder,
                isStreaming = true,
                errorMessage = null
            )
        }

        val ctx = mapOf(
            "subject" to _uiState.value.currentContext.subject,
            "chapter" to _uiState.value.currentContext.chapter,
            "page_number" to _uiState.value.currentContext.printedPage
        )

        streamJob?.cancel()
        streamJob = viewModelScope.launch {
            val fullAssistantContent = StringBuilder()
            val collectedCitations = mutableListOf<ChatCitationItem>()
            var retrievalConfidence: Double? = null

            repository.streamMessage(
                sessionId = sessionId,
                content = prompt,
                chapterContext = ctx
            ).collect { event ->
                when (event) {
                    is ChatStreamEvent.Meta -> {
                        retrievalConfidence = event.confidence
                    }
                    is ChatStreamEvent.Token -> {
                        fullAssistantContent.append(event.delta)
                        updateAssistantMessage(
                            msgId = assistantMsgId,
                            content = fullAssistantContent.toString(),
                            citations = collectedCitations,
                            isStreaming = true
                        )
                    }
                    is ChatStreamEvent.Citation -> {
                        collectedCitations.add(event.citation)
                        updateAssistantMessage(
                            msgId = assistantMsgId,
                            content = fullAssistantContent.toString(),
                            citations = collectedCitations,
                            isStreaming = true
                        )
                    }
                    is ChatStreamEvent.Done -> {
                        val rawContent = fullAssistantContent.toString()
                        val likelyChap = collectedCitations.firstOrNull()?.chapterTitle
                            ?: _uiState.value.currentContext.chapter
                        val isLowConfidence = retrievalConfidence != null && retrievalConfidence!! < 0.5
                        val isNotFound = rawContent.contains("খুঁজে পাওয়া যায়নি") ||
                            rawContent.contains("couldn't find") || isLowConfidence

                        val finalContent = if (isNotFound && (rawContent.isBlank() || isLowConfidence)) {
                            "এই বিষয়টির তথ্য আপনার পাঠ্যবইয়ে সরাসরি খুঁজে পাওয়া যায়নি। সংশ্লিষ্ট অধ্যায় দেখে নেওয়া যেতে পারে: [$likelyChap]"
                        } else {
                            rawContent
                        }

                        updateAssistantMessage(
                            msgId = assistantMsgId,
                            content = finalContent,
                            citations = collectedCitations,
                            isStreaming = false,
                            isNotFound = isNotFound,
                            likelyChapter = likelyChap
                        )
                        _uiState.update { it.copy(isStreaming = false) }
                    }
                    is ChatStreamEvent.Error -> {
                        val isInterrupted = event.code == "STREAM_INTERRUPTED"
                        _uiState.update { state ->
                            state.copy(
                                isStreaming = false,
                                isQuizLocked = event.code == "QUIZ_LOCKOUT",
                                isQuotaExceeded = event.code == "QUOTA_EXCEEDED",
                                errorMessage = event.message
                            )
                        }
                        val errorContent = if (fullAssistantContent.isNotEmpty()) {
                            "${fullAssistantContent.toString()}\n\n⚠️ ${event.message}"
                        } else {
                            event.message
                        }
                        updateAssistantMessage(
                            msgId = assistantMsgId,
                            content = errorContent,
                            citations = collectedCitations,
                            isStreaming = false,
                            isInterrupted = isInterrupted
                        )
                    }
                }
            }
        }
    }

    private fun updateAssistantMessage(
        msgId: String,
        content: String,
        citations: List<ChatCitationItem>,
        isStreaming: Boolean,
        isNotFound: Boolean = false,
        isInterrupted: Boolean = false,
        likelyChapter: String? = null
    ) {
        _uiState.update { state ->
            val updated = state.messages.map { msg ->
                if (msg.id == msgId) {
                    msg.copy(
                        content = content,
                        citations = citations.toList(),
                        isStreaming = isStreaming,
                        isNotFound = isNotFound,
                        isInterrupted = isInterrupted,
                        likelyChapter = likelyChapter
                    )
                } else {
                    msg
                }
            }
            state.copy(messages = updated)
        }
    }

    fun stopStreaming() {
        streamJob?.cancel()
        streamJob = null
        _uiState.update { state ->
            val updated = state.messages.map {
                if (it.isStreaming) it.copy(isStreaming = false) else it
            }
            state.copy(messages = updated, isStreaming = false)
        }
    }

    fun retryLastMessage() {
        val prompt = lastPrompt ?: return
        sendMessage(prompt)
    }

    override fun onCleared() {
        super.onCleared()
        stopStreaming()
    }

    private fun sanitizePrompt(text: String): String {
        return text.trim()
            .replace("<script>", "")
            .replace("</script>", "")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    }
}
