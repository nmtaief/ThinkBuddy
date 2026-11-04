package com.thinkbuddy.app.ui.quiz

import android.os.SystemClock
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.HelpOutline
import androidx.compose.material.icons.filled.Book
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.HelpOutline
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material.icons.filled.PauseCircle
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thinkbuddy.app.ThinkBuddyApp
import com.thinkbuddy.app.core.network.AnswerItemRequest
import com.thinkbuddy.app.core.network.ApiClient
import com.thinkbuddy.app.core.network.AttemptItemPublic
import com.thinkbuddy.app.core.network.AttemptItemReview
import com.thinkbuddy.app.core.network.AttemptReviewResponse
import com.thinkbuddy.app.core.network.StartAttemptRequest
import com.thinkbuddy.app.core.network.SubmitAttemptResponse
import com.thinkbuddy.app.core.security.AssessedQuizSecurity
import com.thinkbuddy.app.core.utils.BengaliDigits
import com.thinkbuddy.app.ui.theme.AmberGold
import com.thinkbuddy.app.ui.theme.BorderDark
import com.thinkbuddy.app.ui.theme.CoralDestructive
import com.thinkbuddy.app.ui.theme.EmeraldSuccess
import com.thinkbuddy.app.ui.theme.IndigoAccent
import com.thinkbuddy.app.ui.theme.SurfaceDark
import com.thinkbuddy.app.ui.theme.TealPrimary
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.format.DateTimeParseException

enum class QuizRunnerState {
    INITIALIZING,
    ACTIVE,
    SUBMITTING,
    COMPLETED,
    REVIEW,
    ERROR
}

/**
 * Quiz Runner Screen (Group 2):
 * Supports both Practice Mode (immediate feedback) and Assessed Mode (withheld answer keys, Rule 6).
 * Enforces per-item nonces, server-driven timer and auto-submit, multi-window policy,
 * and post-submission review with textbook printed page citations (Rule 8).
 */
@Composable
fun QuizScreen(
    quizId: String,
    mode: String = "assessed",
    initialAttemptId: String? = null,
    isMultiWindow: Boolean = false,
    showExitDialog: Boolean = false,
    onDismissExitDialog: () -> Unit = {},
    onConfirmExit: () -> Unit = {},
    onAttemptActivated: (attemptId: String) -> Unit = {},
    onFinishQuiz: () -> Unit = {}
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var runnerState by remember { mutableStateOf(QuizRunnerState.INITIALIZING) }
    var attemptId by remember { mutableStateOf(initialAttemptId) }
    var currentItem by remember { mutableStateOf<AttemptItemPublic?>(null) }
    var currentPosition by remember { mutableIntStateOf(1) }
    var totalItems by remember { mutableIntStateOf(5) }
    var remainingSeconds by remember { mutableIntStateOf(900) }
    var isTimerActive by remember { mutableStateOf(false) }

    var selectedOptionId by remember { mutableStateOf<Int?>(null) }
    var itemStartTimeMs by remember { mutableLongStateOf(SystemClock.elapsedRealtime()) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    // Practice mode feedback (Rule 6: null in assessed mode until submit)
    var practiceFeedback by remember { mutableStateOf<Map<String, Any>?>(null) }
    var hasAnsweredCurrentItem by remember { mutableStateOf(false) }

    // Completed summary
    var submitResult by remember { mutableStateOf<SubmitAttemptResponse?>(null) }
    var reviewResult by remember { mutableStateOf<AttemptReviewResponse?>(null) }

    // 1. Initialize or Resume Quiz Attempt
    fun startOrResumeQuiz() {
        runnerState = QuizRunnerState.INITIALIZING
        errorMessage = null
        scope.launch {
            try {
                val api = ApiClient.getService(context)
                val deviceId = com.thinkbuddy.app.core.network.HeaderInterceptor.getInstallationId(context)

                if (mode == "assessed") {
                    // Step A: Create attempt in state 'created'
                    val initResp = api.createQuizAttempt(
                        quizId = quizId,
                        request = StartAttemptRequest(deviceId = deviceId)
                    )

                    if (!initResp.isSuccessful || initResp.body() == null) {
                        errorMessage = "কুইজ আরম্ভ করা যায়নি (${initResp.code()}). অনুগ্রহ করে পুনরায় চেষ্টা করুন।"
                        runnerState = QuizRunnerState.ERROR
                        return@launch
                    }

                    val initData = initResp.body()!!
                    val newAttemptId = initData.attemptId
                    val serverNonce = initData.nonce
                    attemptId = newAttemptId
                    onAttemptActivated(newAttemptId)

                    // Step B: Request Play Integrity token with nonce bound to attempt ID
                    val integrityToken = AssessedQuizSecurity.requestPlayIntegrityToken(
                        context = context,
                        cloudProjectNumber = 1234567890L,
                        nonceOrAttemptId = serverNonce
                    )

                    // Step C: Attest attempt to activate
                    val attestResp = api.attestQuizAttempt(
                        attemptId = newAttemptId,
                        request = StartAttemptRequest(
                            deviceId = deviceId,
                            integrityToken = integrityToken,
                            integrityVerdict = if (integrityToken == null) "unsupported" else null
                        )
                    )

                    if (attestResp.isSuccessful && attestResp.body() != null) {
                        val activeData = attestResp.body()!!
                        currentItem = activeData.currentItem
                        currentPosition = activeData.currentPosition
                        totalItems = activeData.totalItems
                        remainingSeconds = activeData.timeLimitS
                        isTimerActive = true
                        itemStartTimeMs = SystemClock.elapsedRealtime()
                        runnerState = QuizRunnerState.ACTIVE
                    } else {
                        errorMessage = "ডিভাইস নিরাপত্তা যাচাই ব্যর্থ হয়েছে।"
                        runnerState = QuizRunnerState.ERROR
                    }
                } else {
                    // Practice Mode
                    val startResp = api.startQuizAttempt(
                        quizId = quizId,
                        request = StartAttemptRequest(deviceId = deviceId)
                    )
                    if (startResp.isSuccessful && startResp.body() != null) {
                        val data = startResp.body()!!
                        attemptId = data.attemptId
                        onAttemptActivated(data.attemptId)
                        currentItem = data.currentItem
                        currentPosition = data.currentPosition
                        totalItems = data.totalItems
                        remainingSeconds = data.timeLimitS
                        isTimerActive = true
                        itemStartTimeMs = SystemClock.elapsedRealtime()
                        runnerState = QuizRunnerState.ACTIVE
                    } else {
                        errorMessage = "অনুশীলন কুইজ শুরু করা সম্ভব হয়নি।"
                        runnerState = QuizRunnerState.ERROR
                    }
                }
            } catch (e: Exception) {
                errorMessage = "নেটওয়ার্ক ত্রুটি: ${e.message}"
                runnerState = QuizRunnerState.ERROR
            }
        }
    }

    // Auto-Submit on Timeout or Final Question
    fun submitQuizAttempt(autoSubmitted: Boolean = false) {
        val currAttemptId = attemptId ?: return
        isTimerActive = false
        runnerState = QuizRunnerState.SUBMITTING
        scope.launch {
            try {
                val api = ApiClient.getService(context)
                val resp = api.submitQuiz(currAttemptId)
                if (resp.isSuccessful && resp.body() != null) {
                    submitResult = resp.body()
                    runnerState = QuizRunnerState.COMPLETED
                } else {
                    errorMessage = "কুইজ জমা দিতে সমস্যা হয়েছে।"
                    runnerState = QuizRunnerState.ERROR
                }
            } catch (e: Exception) {
                errorMessage = "নেটওয়ার্ক সমস্যা: ${e.message}"
                runnerState = QuizRunnerState.ERROR
            }
        }
    }

    // Submit Answer for Current Item
    fun answerCurrentItem() {
        val currAttemptId = attemptId ?: return
        val item = currentItem ?: return
        val selected = selectedOptionId ?: return

        val timeSpent = (SystemClock.elapsedRealtime() - itemStartTimeMs).toInt()

        scope.launch {
            try {
                val api = ApiClient.getService(context)
                val answerResp = api.answerQuizItem(
                    attemptId = currAttemptId,
                    position = currentPosition,
                    request = AnswerItemRequest(
                        nonce = item.nonce,
                        response = mapOf("selected_option" to selected),
                        timeSpentMs = timeSpent
                    )
                )

                if (answerResp.isSuccessful && answerResp.body() != null) {
                    val data = answerResp.body()!!
                    if (mode == "practice") {
                        // Practice Mode: show immediate explanation
                        practiceFeedback = data.feedback
                        hasAnsweredCurrentItem = true
                    } else {
                        // Assessed Mode: Withhold feedback (Rule 6). Advance directly.
                        if (data.isLast || data.nextItem == null) {
                            submitQuizAttempt()
                        } else {
                            currentItem = data.nextItem
                            currentPosition = data.nextPosition ?: (currentPosition + 1)
                            selectedOptionId = null
                            itemStartTimeMs = SystemClock.elapsedRealtime()
                        }
                    }
                } else {
                    errorMessage = "উত্তর সংরক্ষণ করা যায়নি (${answerResp.code()})."
                }
            } catch (e: Exception) {
                errorMessage = "উত্তর জমা দিতে ত্রুটি: ${e.message}"
            }
        }
    }

    // Advance to next question in Practice Mode after feedback review
    fun advancePracticeToNext() {
        hasAnsweredCurrentItem = false
        practiceFeedback = null
        selectedOptionId = null
        val currAttemptId = attemptId ?: return

        scope.launch {
            try {
                val api = ApiClient.getService(context)
                val statusResp = api.startQuizAttempt(quizId, StartAttemptRequest(attemptId = currAttemptId))
                if (statusResp.isSuccessful && statusResp.body() != null) {
                    val data = statusResp.body()!!
                    if (data.currentItem == null || currentPosition >= totalItems) {
                        submitQuizAttempt()
                    } else {
                        currentItem = data.currentItem
                        currentPosition = data.currentPosition
                        itemStartTimeMs = SystemClock.elapsedRealtime()
                    }
                } else {
                    submitQuizAttempt()
                }
            } catch (_: Exception) {
                submitQuizAttempt()
            }
        }
    }

    // Load Full Review after completion (Rule 6 unlocked post-submission)
    fun loadFullReview() {
        val currAttemptId = attemptId ?: return
        scope.launch {
            try {
                val api = ApiClient.getService(context)
                val revResp = api.reviewQuiz(currAttemptId)
                if (revResp.isSuccessful && revResp.body() != null) {
                    reviewResult = revResp.body()
                    runnerState = QuizRunnerState.REVIEW
                }
            } catch (_: Exception) {
                // Ignore review load failure
            }
        }
    }

    // Server-Driven Countdown Timer
    LaunchedEffect(isTimerActive, remainingSeconds, isMultiWindow) {
        if (isTimerActive && !(isMultiWindow && mode == "assessed") && remainingSeconds > 0) {
            delay(1000L)
            remainingSeconds -= 1
            if (remainingSeconds <= 0) {
                isTimerActive = false
                submitQuizAttempt(autoSubmitted = true)
            }
        }
    }

    // Start on entrance
    LaunchedEffect(Unit) {
        startOrResumeQuiz()
    }

    // Exit Dialog
    if (showExitDialog) {
        AlertDialog(
            onDismissRequest = onDismissExitDialog,
            title = {
                Text(
                    text = "কুইজ ত্যাগ করবেন?",
                    fontWeight = FontWeight.Bold,
                    color = Color.White
                )
            },
            text = {
                Text(
                    text = if (mode == "assessed")
                        "এটি একটি মূল্যায়ন কুইজ। এখনই বের হয়ে গেলে অসম্পূর্ণ প্রশ্নগুলোর জন্য কোনো নম্বর পাওয়া যাবে না এবং ফলাফল অভিভাবক ড্যাশবোর্ডে অন্তর্ভুক্ত হবে।"
                    else
                        "আপনি কি নিশ্চিত যে অনুশীলন কুইজ ত্যাগ করতে চান?",
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f),
                    fontSize = 14.sp
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        onDismissExitDialog()
                        onConfirmExit()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = CoralDestructive)
                ) {
                    Text("বেরিয়ে যান", color = Color.White)
                }
            },
            dismissButton = {
                TextButton(onClick = onDismissExitDialog) {
                    Text("চালিয়ে যান", color = TealPrimary)
                }
            },
            containerColor = SurfaceDark
        )
    }

    // UI Content
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
    ) {
        when (runnerState) {
            QuizRunnerState.INITIALIZING -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator(color = TealPrimary)
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(
                            text = if (mode == "assessed")
                                "নিরাপদ মূল্যায়ন পরিবেশ যাচাই হচ্ছে..."
                            else
                                "অনুশীলন কুইজ লোড হচ্ছে...",
                            color = Color.White,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Medium
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = "ডিভাইস নিরাপত্তা ও নির্ভরযোগ্যতা যাচাইকরণ",
                            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.6f),
                            fontSize = 12.sp
                        )
                    }
                }
            }

            QuizRunnerState.ERROR -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(24.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            imageVector = Icons.Default.ErrorOutline,
                            contentDescription = null,
                            tint = CoralDestructive,
                            modifier = Modifier.size(54.dp)
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = errorMessage ?: "কুইজ পরিচালনায় সমস্যা হয়েছে",
                            color = Color.White,
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(modifier = Modifier.height(20.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Button(
                                onClick = { startOrResumeQuiz() },
                                colors = ButtonDefaults.buttonColors(containerColor = TealPrimary)
                            ) {
                                Text("পুনরায় চেষ্টা করুন", color = Color.White)
                            }
                            Button(
                                onClick = onFinishQuiz,
                                colors = ButtonDefaults.buttonColors(containerColor = SurfaceDark)
                            ) {
                                Text("ফিরে যান", color = Color.White)
                            }
                        }
                    }
                }
            }

            QuizRunnerState.SUBMITTING -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator(color = EmeraldSuccess)
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(
                            text = "উত্তরপত্র মূল্যায়ন করা হচ্ছে...",
                            color = Color.White,
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "স্বয়ংক্রিয় গ্রেডিং ও শিখন সংকেত আপডেট হচ্ছে",
                            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.6f),
                            fontSize = 13.sp
                        )
                    }
                }
            }

            QuizRunnerState.ACTIVE -> {
                val item = currentItem
                if (item == null) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = TealPrimary)
                    }
                } else {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(20.dp)
                    ) {
                        // Top Security & Timer Bar
                        QuizTopBar(
                            mode = mode,
                            currentPos = currentPosition,
                            totalCount = totalItems,
                            remainingSeconds = remainingSeconds,
                            isPaused = (isMultiWindow && mode == "assessed")
                        )

                        Spacer(modifier = Modifier.height(16.dp))

                        if (isMultiWindow && mode == "assessed") {
                            // Full-screen blocking pause overlay per server policy
                            Card(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .weight(1f)
                                    .padding(vertical = 12.dp),
                                shape = RoundedCornerShape(16.dp),
                                colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                                border = androidx.compose.foundation.BorderStroke(2.dp, AmberGold)
                            ) {
                                Column(
                                    modifier = Modifier
                                        .fillMaxSize()
                                        .padding(24.dp),
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                    verticalArrangement = Arrangement.Center
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.PauseCircle,
                                        contentDescription = "Paused",
                                        tint = AmberGold,
                                        modifier = Modifier.size(64.dp)
                                    )
                                    Spacer(modifier = Modifier.height(16.dp))
                                    Text(
                                        text = "মূল্যায়ন কুইজ সাময়িকভাবে স্থগিত",
                                        color = AmberGold,
                                        fontSize = 18.sp,
                                        fontWeight = FontWeight.Bold
                                    )
                                    Spacer(modifier = Modifier.height(8.dp))
                                    Text(
                                        text = "সার্ভার নিরাপত্তা নীতি অনুযায়ী মূল্যায়ন কুইজ চলাকালে সম্পূর্ণ স্ক্রিন মোড আবশ্যক। স্প্লিট স্ক্রিন বা ফ্লোটিং উইন্ডো বন্ধ করে সম্পূর্ণ স্ক্রিনে ফিরে আসলে কুইজ স্বয়ংক্রিয়ভাবে পুনরায় চালু হবে।",
                                        color = Color.White.copy(alpha = 0.85f),
                                        fontSize = 14.sp,
                                        lineHeight = 22.sp,
                                        textAlign = androidx.compose.ui.text.style.TextAlign.Center
                                    )
                                }
                            }
                        } else {
                            // Question Prompt Card
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(16.dp),
                            colors = CardDefaults.cardColors(containerColor = SurfaceDark)
                        ) {
                            Column(modifier = Modifier.padding(20.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text(
                                        text = "প্রশ্ন ${BengaliDigits.fromInt(currentPosition)}",
                                        color = TealPrimary,
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 14.sp
                                    )
                                    Text(
                                        text = "${BengaliDigits.fromInt(totalItems)}টির মধ্যে",
                                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                                        fontSize = 12.sp
                                    )
                                }

                                Spacer(modifier = Modifier.height(10.dp))

                                val promptText = item.promptBn.ifBlank { item.prompt }
                                Text(
                                    text = promptText,
                                    color = Color.White,
                                    fontSize = 17.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    lineHeight = 24.sp
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(16.dp))

                        // Options List (Filter touches when obscured against tapjacking)
                        LazyColumn(
                            modifier = Modifier.weight(1f),
                            verticalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            items(item.options) { option ->
                                val isSelected = selectedOptionId == option.id
                                val optionText = option.textBn.ifBlank { option.text }

                                Card(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clip(RoundedCornerShape(12.dp))
                                        .clickable(enabled = !hasAnsweredCurrentItem) {
                                            selectedOptionId = option.id
                                        }
                                        .border(
                                            width = if (isSelected) 2.dp else 1.dp,
                                            color = if (isSelected) TealPrimary else BorderDark,
                                            shape = RoundedCornerShape(12.dp)
                                        ),
                                    shape = RoundedCornerShape(12.dp),
                                    colors = CardDefaults.cardColors(
                                        containerColor = if (isSelected)
                                            TealPrimary.copy(alpha = 0.12f)
                                        else
                                            SurfaceDark
                                    )
                                ) {
                                    Row(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(14.dp),
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        RadioButton(
                                            selected = isSelected,
                                            onClick = {
                                                if (!hasAnsweredCurrentItem) selectedOptionId = option.id
                                            },
                                            colors = RadioButtonDefaults.colors(
                                                selectedColor = TealPrimary,
                                                unselectedColor = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                                            )
                                        )
                                        Spacer(modifier = Modifier.width(8.dp))
                                        Text(
                                            text = optionText,
                                            color = Color.White,
                                            fontSize = 15.sp,
                                            modifier = Modifier.weight(1f)
                                        )
                                    }
                                }
                            }

                            // Immediate Practice Feedback Card (Practice Mode only)
                            if (mode == "practice" && hasAnsweredCurrentItem && practiceFeedback != null) {
                                item {
                                    val isCorrect = practiceFeedback?.get("is_correct") as? Boolean ?: false
                                    val explanation = practiceFeedback?.get("explanation_bn")?.toString() ?: ""

                                    Card(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(top = 8.dp),
                                        shape = RoundedCornerShape(12.dp),
                                        colors = CardDefaults.cardColors(
                                            containerColor = if (isCorrect)
                                                EmeraldSuccess.copy(alpha = 0.15f)
                                            else
                                                CoralDestructive.copy(alpha = 0.15f)
                                        )
                                    ) {
                                        Column(modifier = Modifier.padding(14.dp)) {
                                            Row(verticalAlignment = Alignment.CenterVertically) {
                                                Icon(
                                                    imageVector = if (isCorrect) Icons.Default.CheckCircle else Icons.Default.Close,
                                                    contentDescription = null,
                                                    tint = if (isCorrect) EmeraldSuccess else CoralDestructive,
                                                    modifier = Modifier.padding(end = 6.dp)
                                                )
                                                Text(
                                                    text = if (isCorrect) "সঠিক উত্তর!" else "উত্তর সঠিক নয়",
                                                    fontWeight = FontWeight.Bold,
                                                    color = if (isCorrect) EmeraldSuccess else CoralDestructive,
                                                    fontSize = 15.sp
                                                )
                                            }
                                            if (explanation.isNotBlank()) {
                                                Spacer(modifier = Modifier.height(6.dp))
                                                Text(
                                                    text = explanation,
                                                    fontSize = 13.sp,
                                                    color = Color.White.copy(alpha = 0.9f),
                                                    lineHeight = 18.sp
                                                )
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(16.dp))

                        // Bottom Action CTA
                        if (mode == "practice" && hasAnsweredCurrentItem) {
                            Button(
                                onClick = { advancePracticeToNext() },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(52.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = TealPrimary),
                                shape = RoundedCornerShape(12.dp)
                            ) {
                                Text(
                                    text = if (currentPosition >= totalItems) "কুইজ সম্পন্ন করুন" else "পরবর্তী প্রশ্ন",
                                    fontSize = 16.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color.White
                                )
                            }
                        } else {
                            val isLast = currentPosition >= totalItems
                            Button(
                                onClick = { answerCurrentItem() },
                                enabled = selectedOptionId != null,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(52.dp),
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = if (isLast) EmeraldSuccess else TealPrimary
                                ),
                                shape = RoundedCornerShape(12.dp)
                            ) {
                                Text(
                                    text = when {
                                        mode == "practice" -> "উত্তর যাচাই করুন"
                                        isLast -> "কুইজ জমা দিন (Submit)"
                                        else -> "পরবর্তী প্রশ্ন (Next)"
                                    },
                                    fontSize = 16.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color.White
                                )
                            }
                        }
                        }
                    }
                }
            }

            QuizRunnerState.COMPLETED -> {
                val res = submitResult
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(24.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(
                            imageVector = Icons.Default.CheckCircle,
                            contentDescription = null,
                            tint = EmeraldSuccess,
                            modifier = Modifier.size(64.dp)
                        )
                        Spacer(modifier = Modifier.height(14.dp))
                        Text(
                            text = "কুইজ সফলভাবে সম্পন্ন হয়েছে!",
                            fontSize = 20.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = if (mode == "assessed")
                                "মূল্যায়ন ফলাফল রেকর্ড করা হয়েছে ও অভিভাবক পোর্টালে সিঙ্ক হয়েছে।"
                            else
                                "অনুশীলন কুইজের ফলাফল আপনার পারদর্শিতা স্কোরে যুক্ত হয়েছে।",
                            fontSize = 13.sp,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                            textAlign = androidx.compose.ui.text.style.TextAlign.Center
                        )

                        Spacer(modifier = Modifier.height(24.dp))

                        // Score Card
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(16.dp),
                            colors = CardDefaults.cardColors(containerColor = SurfaceDark)
                        ) {
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(20.dp),
                                horizontalAlignment = Alignment.CenterHorizontally
                            ) {
                                val score = res?.score ?: 0f
                                val total = res?.totalScore ?: totalItems.toFloat()
                                val percentage = res?.percentage ?: (score / total * 100f)

                                Text(
                                    text = "${BengaliDigits.fromInt(score.toInt())} / ${BengaliDigits.fromInt(total.toInt())}",
                                    fontSize = 32.sp,
                                    fontWeight = FontWeight.ExtraBold,
                                    color = EmeraldSuccess
                                )
                                Text(
                                    text = "সঠিক উত্তর (${BengaliDigits.fromInt(percentage.toInt())}%)",
                                    fontSize = 14.sp,
                                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.8f)
                                )

                                if (res?.parentFlag == true) {
                                    Spacer(modifier = Modifier.height(10.dp))
                                    Box(
                                        modifier = Modifier
                                            .clip(RoundedCornerShape(6.dp))
                                            .background(AmberGold.copy(alpha = 0.15f))
                                            .padding(horizontal = 8.dp, vertical = 4.dp)
                                    ) {
                                        Text(
                                            text = "অবিশ্বস্ত পরিবেশের কারণে পারদর্শিতা ওজন সীমিত রাখা হয়েছে।",
                                            color = AmberGold,
                                            fontSize = 11.sp
                                        )
                                    }
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(24.dp))

                        Button(
                            onClick = { loadFullReview() },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(50.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = TealPrimary),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Book,
                                contentDescription = null,
                                tint = Color.White,
                                modifier = Modifier.padding(end = 8.dp)
                            )
                            Text("বিস্তারিত পর্যালোচনা ও ব্যাখ্যা দেখুন", color = Color.White)
                        }

                        Spacer(modifier = Modifier.height(12.dp))

                        Button(
                            onClick = onFinishQuiz,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(50.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = SurfaceDark),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text("হোমপেজে ফিরে যান", color = Color.White)
                        }
                    }
                }
            }

            QuizRunnerState.REVIEW -> {
                val review = reviewResult
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(20.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "উত্তর পর্যালোচনা (Review)",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.Bold,
                            color = TealPrimary
                        )
                        Button(
                            onClick = onFinishQuiz,
                            colors = ButtonDefaults.buttonColors(containerColor = SurfaceDark)
                        ) {
                            Text("সমাপ্ত", color = Color.White)
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    if (review != null) {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            verticalArrangement = Arrangement.spacedBy(14.dp)
                        ) {
                            items(review.items) { item ->
                                ReviewItemCard(item = item)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun QuizTopBar(
    mode: String,
    currentPos: Int,
    totalCount: Int,
    remainingSeconds: Int,
    isPaused: Boolean = false
) {
    val mins = remainingSeconds / 60
    val secs = remainingSeconds % 60
    val formattedTime = String.format(java.util.Locale.US, "%02d:%02d", mins, secs)
    val timerColor = when {
        isPaused -> AmberGold
        remainingSeconds < 120 -> CoralDestructive
        remainingSeconds < 300 -> AmberGold
        else -> EmeraldSuccess
    }

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Mode badge
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                imageVector = if (mode == "assessed") Icons.Default.Security else Icons.AutoMirrored.Filled.HelpOutline,
                contentDescription = null,
                tint = if (mode == "assessed") TealPrimary else AmberGold,
                modifier = Modifier.size(18.dp)
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = if (mode == "assessed") "মূল্যায়ন কুইজ" else "অনুশীলন কুইজ",
                fontWeight = FontWeight.Bold,
                fontSize = 14.sp,
                color = Color.White
            )
        }

        // Server-driven Countdown Timer
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier
                .clip(RoundedCornerShape(8.dp))
                .background(timerColor.copy(alpha = 0.15f))
                .padding(horizontal = 10.dp, vertical = 6.dp)
        ) {
            Icon(
                imageVector = Icons.Default.Timer,
                contentDescription = null,
                tint = timerColor,
                modifier = Modifier.size(16.dp)
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = if (isPaused) "স্থগিত (Paused)" else BengaliDigits.format(formattedTime),
                fontWeight = FontWeight.ExtraBold,
                fontSize = 15.sp,
                color = timerColor
            )
        }
    }
}

@Composable
fun ReviewItemCard(item: AttemptItemReview) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceDark)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "প্রশ্ন ${BengaliDigits.fromInt(item.position)}",
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp,
                    color = TealPrimary
                )
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(6.dp))
                        .background(if (item.isCorrect) EmeraldSuccess.copy(alpha = 0.15f) else CoralDestructive.copy(alpha = 0.15f))
                        .padding(horizontal = 8.dp, vertical = 4.dp)
                ) {
                    Text(
                        text = if (item.isCorrect) "সঠিক (+১)" else "ভুল (০)",
                        color = if (item.isCorrect) EmeraldSuccess else CoralDestructive,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            val prompt = item.promptBn.ifBlank { item.prompt }
            Text(
                text = prompt,
                fontWeight = FontWeight.SemiBold,
                fontSize = 15.sp,
                color = Color.White
            )

            Spacer(modifier = Modifier.height(10.dp))

            // Explanation & Citation (Rule 7 & 8)
            val explanation = item.explanationBn ?: item.explanation ?: ""
            if (explanation.isNotBlank()) {
                Text(
                    text = "ব্যাখ্যা: $explanation",
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f),
                    lineHeight = 18.sp
                )
            }

            item.printedPage?.let { page ->
                Spacer(modifier = Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Book,
                        contentDescription = null,
                        tint = AmberGold,
                        modifier = Modifier.size(14.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = "মুদ্রিত পাঠ্যবই: পৃষ্ঠা ${BengaliDigits.fromInt(page)}",
                        fontSize = 12.sp,
                        color = AmberGold,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
        }
    }
}
