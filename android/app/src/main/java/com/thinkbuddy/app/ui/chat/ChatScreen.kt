package com.thinkbuddy.app.ui.chat

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Book
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Lightbulb
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.StopCircle
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thinkbuddy.app.core.network.ChatCitationItem
import com.thinkbuddy.app.core.network.ChatRepository
import com.thinkbuddy.app.core.utils.BengaliDigits
import com.thinkbuddy.app.ui.theme.AmberGold
import com.thinkbuddy.app.ui.theme.BackgroundDark
import com.thinkbuddy.app.ui.theme.BorderDark
import com.thinkbuddy.app.ui.theme.CoralDestructive
import com.thinkbuddy.app.ui.theme.EmeraldSuccess
import com.thinkbuddy.app.ui.theme.IndigoAccent
import com.thinkbuddy.app.ui.theme.SurfaceDark
import com.thinkbuddy.app.ui.theme.TealPrimary

/**
 * Group 3: AI Chat Screen
 * Features:
 * - SSE streaming through OkHttp with Flow
 * - Cancel on leave / stop streaming button
 * - Chapter and printed page context
 * - Authoritative textbook citation chips with printed pages (Rule 8)
 * - "Not found in your textbook" growth mindset state
 * - Quota & Active assessed quiz lockout banners
 * - Math formula rendering
 * - Sanitized output and zero chat content in logs (Rule 15)
 * - Adaptive layout: Single-pane on phone, Two-pane master-detail on tablet
 */
@Composable
fun ChatScreen(
    isTablet: Boolean = false,
    viewModel: ChatViewModel? = null
) {
    val context = LocalContext.current
    val vm = remember {
        viewModel ?: ChatViewModel(ChatRepository(context))
    }

    val state by vm.uiState.collectAsState()
    var selectedCitation by remember { mutableStateOf<ChatCitationItem?>(null) }

    // Cancel streaming on leave
    DisposableEffect(Unit) {
        onDispose {
            vm.stopStreaming()
        }
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = BackgroundDark
    ) {
        if (isTablet) {
            // Tablet Two-Pane Master-Detail Layout
            Row(modifier = Modifier.fillMaxSize()) {
                // Left Pane: Chapter Context & Past Sessions (300 dp)
                Box(
                    modifier = Modifier
                        .width(320.dp)
                        .fillMaxHeight()
                        .background(SurfaceDark)
                        .border(1.dp, BorderDark)
                ) {
                    ChatLeftPane(
                        state = state,
                        onNewChat = { vm.startNewSession() },
                        onSelectSession = { vm.selectSession(it) },
                        onContextChange = { subj, ch, p -> vm.setChapterContext(subj, ch, p) }
                    )
                }

                // Right Pane: Active Conversation & Input
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxHeight()
                ) {
                    ChatRightPane(
                        state = state,
                        isTablet = true,
                        onSendMessage = { vm.sendMessage(it) },
                        onStopStreaming = { vm.stopStreaming() },
                        onRetry = { vm.retryLastMessage() },
                        onCitationClick = { selectedCitation = it }
                    )
                }
            }
        } else {
            // Phone Single-Pane Layout
            ChatRightPane(
                state = state,
                isTablet = false,
                onSendMessage = { vm.sendMessage(it) },
                onStopStreaming = { vm.stopStreaming() },
                onRetry = { vm.retryLastMessage() },
                onCitationClick = { selectedCitation = it },
                onNewChat = { vm.startNewSession() }
            )
        }

        // Citation Detail Dialog
        selectedCitation?.let { citation ->
            CitationDetailDialog(
                citation = citation,
                onDismiss = { selectedCitation = null }
            )
        }
    }
}

@Composable
fun ChatLeftPane(
    state: ChatUiState,
    onNewChat: () -> Unit,
    onSelectSession: (String) -> Unit,
    onContextChange: (String, String, Int) -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        // New Chat Button
        Button(
            onClick = onNewChat,
            modifier = Modifier
                .fillMaxWidth()
                .height(48.dp),
            colors = ButtonDefaults.buttonColors(containerColor = TealPrimary),
            shape = RoundedCornerShape(12.dp)
        ) {
            Icon(Icons.Default.Add, contentDescription = null, tint = Color.White)
            Spacer(modifier = Modifier.width(8.dp))
            Text("নতুন কথোপকথন", fontWeight = FontWeight.Bold, color = Color.White)
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Active Chapter Context Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = BackgroundDark),
            border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Book, contentDescription = null, tint = TealPrimary, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("পাঠ্যবই প্রসঙ্গ (Context)", fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = TealPrimary)
                }
                Spacer(modifier = Modifier.height(6.dp))
                Text(state.currentContext.subject, fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color.White)
                Text(state.currentContext.chapter, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f))
                Text(
                    "মুদ্রিত পৃষ্ঠা: ${BengaliDigits.fromInt(state.currentContext.printedPage)}",
                    fontSize = 11.sp,
                    color = AmberGold,
                    fontWeight = FontWeight.Medium
                )
            }
        }

        Spacer(modifier = Modifier.height(20.dp))
        Text("পূর্ববর্তী কথোপকথন", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f))
        Spacer(modifier = Modifier.height(10.dp))

        // Session list
        LazyColumn(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(state.sessions) { session ->
                val isSelected = session.id == state.activeSessionId
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(10.dp))
                        .clickable { onSelectSession(session.id) }
                        .border(
                            width = if (isSelected) 1.5.dp else 1.dp,
                            color = if (isSelected) TealPrimary else BorderDark,
                            shape = RoundedCornerShape(10.dp)
                        ),
                    colors = CardDefaults.cardColors(
                        containerColor = if (isSelected) TealPrimary.copy(alpha = 0.12f) else BackgroundDark
                    )
                ) {
                    Column(modifier = Modifier.padding(10.dp)) {
                        Text(
                            text = session.title,
                            fontSize = 13.sp,
                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                            color = if (isSelected) TealPrimary else Color.White,
                            maxLines = 1
                        )
                        session.subject?.let {
                            Text(text = it, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f))
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun ChatRightPane(
    state: ChatUiState,
    isTablet: Boolean,
    onSendMessage: (String) -> Unit,
    onStopStreaming: () -> Unit,
    onRetry: () -> Unit,
    onCitationClick: (ChatCitationItem) -> Unit,
    onNewChat: (() -> Unit)? = null
) {
    val listState = rememberLazyListState()
    var inputText by remember { mutableStateOf("") }

    // Auto-scroll to bottom on new messages
    LaunchedEffect(state.messages.size, state.isStreaming) {
        if (state.messages.isNotEmpty()) {
            listState.animateScrollToItem(state.messages.size - 1)
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        // Top Header
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(0.dp),
            colors = CardDefaults.cardColors(containerColor = SurfaceDark),
            border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(CircleShape)
                            .background(TealPrimary.copy(alpha = 0.2f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(Icons.Default.AutoAwesome, contentDescription = null, tint = TealPrimary, modifier = Modifier.size(20.dp))
                    }
                    Spacer(modifier = Modifier.width(10.dp))
                    Column {
                        Text("থিঙ্কবাডি এআই টিউটর", fontWeight = FontWeight.Bold, fontSize = 15.sp, color = Color.White)
                        Text(
                            "${state.currentContext.subject} • ${state.currentContext.chapter}",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                        )
                    }
                }

                if (!isTablet && onNewChat != null) {
                    IconButton(onClick = onNewChat) {
                        Icon(Icons.Default.Add, contentDescription = "New Chat", tint = TealPrimary)
                    }
                }
            }
        }

        // Banners: Quiz Lockout or Quota Exceeded
        if (state.isQuizLocked) {
            QuizLockoutBanner()
        } else if (state.isQuotaExceeded) {
            QuotaExceededBanner()
        }

        // Message Thread
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
        ) {
            if (state.messages.isEmpty() && !state.isLoading) {
                EmptyChatWelcome(
                    chapterContext = state.currentContext,
                    onSuggestionClick = { onSendMessage(it) }
                )
            } else {
                LazyColumn(
                    state = listState,
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    items(state.messages) { message ->
                        ChatMessageItem(
                            message = message,
                            onCitationClick = onCitationClick,
                            onRetry = onRetry
                        )
                    }
                }
            }

            if (state.isLoading && state.messages.isEmpty()) {
                CircularProgressIndicator(
                    modifier = Modifier.align(Alignment.Center),
                    color = TealPrimary
                )
            }
        }

        // Input Bar
        ChatInputBar(
            inputText = inputText,
            onTextChanged = { inputText = it },
            isStreaming = state.isStreaming,
            isLocked = state.isQuizLocked || state.isQuotaExceeded,
            onSend = {
                if (inputText.isNotBlank()) {
                    onSendMessage(inputText)
                    inputText = ""
                }
            },
            onStop = onStopStreaming
        )
    }
}

@Composable
fun QuizLockoutBanner() {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        shape = RoundedCornerShape(10.dp),
        colors = CardDefaults.cardColors(containerColor = AmberGold.copy(alpha = 0.15f)),
        border = androidx.compose.foundation.BorderStroke(1.dp, AmberGold)
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(Icons.Default.Lock, contentDescription = null, tint = AmberGold, modifier = Modifier.size(20.dp))
            Spacer(modifier = Modifier.width(10.dp))
            Column {
                Text("এআই সহায়তা সাময়িকভাবে স্থগিত", fontWeight = FontWeight.Bold, fontSize = 13.sp, color = AmberGold)
                Text(
                    "পরীক্ষার সততা রক্ষার স্বার্থে মূল্যায়ন কুইজ চলমান থাকায় এআই টিউটর বন্ধ রয়েছে। কুইজ শেষ হলে পুনরায় চালু হবে।",
                    fontSize = 11.sp,
                    color = Color.White.copy(alpha = 0.8f)
                )
            }
        }
    }
}

@Composable
fun QuotaExceededBanner() {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        shape = RoundedCornerShape(10.dp),
        colors = CardDefaults.cardColors(containerColor = CoralDestructive.copy(alpha = 0.15f)),
        border = androidx.compose.foundation.BorderStroke(1.dp, CoralDestructive)
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(Icons.Default.Warning, contentDescription = null, tint = CoralDestructive, modifier = Modifier.size(20.dp))
            Spacer(modifier = Modifier.width(10.dp))
            Column {
                Text("দৈনিক প্রশ্ন সীমা সমাপ্ত", fontWeight = FontWeight.Bold, fontSize = 13.sp, color = CoralDestructive)
                Text(
                    "আজকের দৈনিক প্রশ্ন কোটা সমাপ্ত হয়েছে। আগামীকাল সকাল ৬টায় কোটা নবায়ন হবে।",
                    fontSize = 11.sp,
                    color = Color.White.copy(alpha = 0.8f)
                )
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ChatMessageItem(
    message: UiChatMessage,
    onCitationClick: (ChatCitationItem) -> Unit,
    onRetry: () -> Unit
) {
    val isUser = message.role == "user"

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        if (!isUser) {
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .clip(CircleShape)
                    .background(TealPrimary.copy(alpha = 0.2f))
                    .align(Alignment.Top),
                contentAlignment = Alignment.Center
            ) {
                Icon(Icons.Default.AutoAwesome, contentDescription = null, tint = TealPrimary, modifier = Modifier.size(18.dp))
            }
            Spacer(modifier = Modifier.width(8.dp))
        }

        Column(
            modifier = Modifier.fillMaxWidth(if (isUser) 0.85f else 0.90f),
            horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
        ) {
            // Bubble card
            Card(
                shape = RoundedCornerShape(
                    topStart = 16.dp,
                    topEnd = 16.dp,
                    bottomStart = if (isUser) 16.dp else 4.dp,
                    bottomEnd = if (isUser) 4.dp else 16.dp
                ),
                colors = CardDefaults.cardColors(
                    containerColor = if (isUser) TealPrimary else SurfaceDark
                ),
                border = androidx.compose.foundation.BorderStroke(1.dp, if (isUser) TealPrimary else BorderDark)
            ) {
                Column(modifier = Modifier.padding(14.dp)) {
                    if (message.content.isEmpty() && message.isStreaming) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp, color = TealPrimary)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("পাঠ্যবই পর্যালোচনা করে উত্তর তৈরি হচ্ছে...", fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
                        }
                    } else {
                        // Tail Item 5: Hardened KaTeX Math view if LaTeX math equations present, else pure Compose text
                        if (message.content.contains("\\(") || message.content.contains("\\[")) {
                            HardenedMathView(rawText = message.content)
                        } else {
                            MathTextRenderer(text = message.content, isUser = isUser)
                        }
                    }

                    if (message.isNotFound) {
                        Spacer(modifier = Modifier.height(10.dp))
                        NotFoundBadge()
                    }

                    // Tail Item 3: Manual retry button after interrupted / partial output
                    if (message.isInterrupted) {
                        Spacer(modifier = Modifier.height(10.dp))
                        OutlinedButton(
                            onClick = onRetry,
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = AmberGold),
                            border = androidx.compose.foundation.BorderStroke(1.dp, AmberGold),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Icon(Icons.Default.Refresh, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(modifier = Modifier.width(6.dp))
                            Text("পুনরায় চেষ্টা করুন (Retry)", fontSize = 13.sp)
                        }
                    }
                }
            }

            // Citations Chips Row (Rule 8: Authoritative printed page numbers strictly shown)
            if (!isUser && message.citations.isNotEmpty()) {
                Spacer(modifier = Modifier.height(6.dp))
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    message.citations.forEach { citation ->
                        CitationChip(
                            citation = citation,
                            onClick = { onCitationClick(citation) }
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun MathTextRenderer(text: String, isUser: Boolean) {
    // Splits text into regular prose and LaTeX math equations \( ... \) or \[ ... \]
    val textColor = if (isUser) Color.White else Color.White
    val mathRegex = Regex("""(\\\[.*?\\\]|\\\(.*?\\\))""")
    val parts = text.split(mathRegex)
    val matches = mathRegex.findAll(text).map { it.value }.toList()

    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        var matchIdx = 0
        parts.forEachIndexed { index, part ->
            if (part.isNotBlank()) {
                Text(
                    text = part.trim(),
                    fontSize = 15.sp,
                    lineHeight = 22.sp,
                    color = textColor
                )
            }
            if (matchIdx < matches.size && index < parts.size - 1) {
                val rawMath = matches[matchIdx]
                val cleanedMath = rawMath.removePrefix("\\[").removeSuffix("\\]")
                    .removePrefix("\\(").removeSuffix("\\)").trim()

                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .background(Color.Black.copy(alpha = 0.35f))
                        .border(1.dp, BorderDark, RoundedCornerShape(8.dp))
                        .padding(horizontal = 12.dp, vertical = 6.dp)
                ) {
                    Text(
                        text = cleanedMath,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp,
                        color = IndigoAccent
                    )
                }
                matchIdx++
            }
        }
    }
}

@Composable
fun NotFoundBadge() {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(AmberGold.copy(alpha = 0.12f))
            .padding(horizontal = 10.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(Icons.Default.Lightbulb, contentDescription = null, tint = AmberGold, modifier = Modifier.size(16.dp))
        Spacer(modifier = Modifier.width(6.dp))
        Text(
            text = "পাঠ্যক্রমের বাইরে প্রশ্ন: পাঠ্যবই সংক্রান্ত প্রশ্ন করলে তথ্যসূত্রসহ উত্তর মিলবে।",
            fontSize = 11.sp,
            color = AmberGold,
            lineHeight = 16.sp
        )
    }
}

@Composable
fun CitationChip(
    citation: ChatCitationItem,
    onClick: () -> Unit
) {
    val pageDisplay = BengaliDigits.fromInt(citation.printedPage)

    Surface(
        onClick = onClick,
        shape = RoundedCornerShape(8.dp),
        color = SurfaceDark,
        border = androidx.compose.foundation.BorderStroke(1.dp, TealPrimary.copy(alpha = 0.6f))
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(Icons.Default.Book, contentDescription = null, tint = TealPrimary, modifier = Modifier.size(12.dp))
            Spacer(modifier = Modifier.width(4.dp))
            Text(
                text = "${citation.bookTitle} • পৃষ্ঠা নং $pageDisplay",
                fontSize = 11.sp,
                fontWeight = FontWeight.Medium,
                color = TealPrimary
            )
        }
    }
}

@Composable
fun CitationDetailDialog(
    citation: ChatCitationItem,
    onDismiss: () -> Unit
) {
    val pageDisplay = BengaliDigits.fromInt(citation.printedPage)

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Book, contentDescription = null, tint = TealPrimary)
                Spacer(modifier = Modifier.width(8.dp))
                Text("পাঠ্যবই তথ্যসূত্র ও সূত্র", fontWeight = FontWeight.Bold, fontSize = 16.sp)
            }
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("পাঠ্যবই: ${citation.bookTitle}", fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                citation.chapterTitle?.let {
                    Text("অধ্যায়: $it", fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.8f))
                }
                Text("মুদ্রিত পৃষ্ঠা নং: $pageDisplay", fontWeight = FontWeight.Bold, fontSize = 14.sp, color = AmberGold)
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    "জাতীয় শিক্ষাক্রম ও পাঠ্যপুস্তক বোর্ড (NCTB) অনুমোদিত পাঠ্যবই থেকে এই তথ্য সংগ্রহ ও যাচাই করা হয়েছে।",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                    lineHeight = 16.sp
                )
            }
        },
        confirmButton = {
            Button(
                onClick = onDismiss,
                colors = ButtonDefaults.buttonColors(containerColor = TealPrimary)
            ) {
                Text("ঠিক আছে", color = Color.White)
            }
        }
    )
}

@Composable
fun EmptyChatWelcome(
    chapterContext: ChapterContext,
    onSuggestionClick: (String) -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Box(
            modifier = Modifier
                .size(64.dp)
                .clip(CircleShape)
                .background(TealPrimary.copy(alpha = 0.15f)),
            contentAlignment = Alignment.Center
        ) {
            Icon(Icons.Default.AutoAwesome, contentDescription = null, tint = TealPrimary, modifier = Modifier.size(36.dp))
        }

        Spacer(modifier = Modifier.height(16.dp))
        Text("থিঙ্কবাডি পাঠ্যবই সহায়ক এআই", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = Color.White)
        Spacer(modifier = Modifier.height(6.dp))
        Text(
            "আপনার পাঠ্যবই থেকে যেকোনো সমীকরণ, ধারণা বা অনুশীলনী নিয়ে প্রশ্ন জিজ্ঞাসা করুন।",
            fontSize = 13.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
            lineHeight = 20.sp,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center
        )

        Spacer(modifier = Modifier.height(24.dp))
        Text("প্রস্তাবিত কিছু প্রশ্ন:", fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = TealPrimary)
        Spacer(modifier = Modifier.height(10.dp))

        val suggestions = listOf(
            "নিউটনের গতির দ্বিতীয় সূত্রটি ব্যাখ্যা করো",
            "ভরবেগ ও বলের সম্পর্ক সমীকরণসহ বুঝিয়ে দাও",
            "ঘর্ষণ বল কীভাবে হ্রাস করা যায়?"
        )

        suggestions.forEach { suggestion ->
            OutlinedButton(
                onClick = { onSuggestionClick(suggestion) },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp),
                shape = RoundedCornerShape(10.dp),
                border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
            ) {
                Text(suggestion, fontSize = 13.sp, color = Color.White)
            }
        }
    }
}

@Composable
fun ChatInputBar(
    inputText: String,
    onTextChanged: (String) -> Unit,
    isStreaming: Boolean,
    isLocked: Boolean,
    onSend: () -> Unit,
    onStop: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(0.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Text Input Box (Autofill disabled per Requirement 6)
            Box(
                modifier = Modifier
                    .weight(1f)
                    .clip(RoundedCornerShape(24.dp))
                    .background(BackgroundDark)
                    .border(1.dp, BorderDark, RoundedCornerShape(24.dp))
                    .padding(horizontal = 16.dp, vertical = 12.dp)
            ) {
                if (inputText.isEmpty()) {
                    Text(
                        text = if (isLocked) "এআই সহায়তা সাময়িকভাবে বন্ধ রয়েছে..." else "পাঠ্যবই থেকে প্রশ্ন লিখুন...",
                        fontSize = 14.sp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f)
                    )
                }
                BasicTextField(
                    value = inputText,
                    onValueChange = onTextChanged,
                    enabled = !isLocked,
                    textStyle = androidx.compose.ui.text.TextStyle(
                        color = Color.White,
                        fontSize = 14.sp
                    ),
                    cursorBrush = SolidColor(TealPrimary),
                    keyboardOptions = KeyboardOptions(
                        autoCorrectEnabled = false,
                        keyboardType = KeyboardType.Text,
                        imeAction = ImeAction.Send
                    ),
                    modifier = Modifier.fillMaxWidth()
                )
            }

            Spacer(modifier = Modifier.width(8.dp))

            // Action button: Stop if streaming, Send if idle
            if (isStreaming) {
                IconButton(
                    onClick = onStop,
                    modifier = Modifier
                        .size(44.dp)
                        .clip(CircleShape)
                        .background(CoralDestructive.copy(alpha = 0.2f))
                ) {
                    Icon(Icons.Default.StopCircle, contentDescription = "Stop", tint = CoralDestructive)
                }
            } else {
                IconButton(
                    onClick = onSend,
                    enabled = inputText.isNotBlank() && !isLocked,
                    modifier = Modifier
                        .size(44.dp)
                        .clip(CircleShape)
                        .background(if (inputText.isNotBlank() && !isLocked) TealPrimary else BorderDark)
                ) {
                    Icon(
                        Icons.AutoMirrored.Filled.Send,
                        contentDescription = "Send",
                        tint = if (inputText.isNotBlank() && !isLocked) Color.White else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f)
                    )
                }
            }
        }
    }
}
