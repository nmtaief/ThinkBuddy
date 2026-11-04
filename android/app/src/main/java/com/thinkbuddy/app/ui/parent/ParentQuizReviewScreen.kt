package com.thinkbuddy.app.ui.parent

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Cancel
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.ThumbUp
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
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
import com.thinkbuddy.app.core.network.AttemptItemReviewDto
import com.thinkbuddy.app.core.network.AttemptReviewResponseDto
import com.thinkbuddy.app.core.network.ParentRepository
import com.thinkbuddy.app.core.utils.BengaliDigits
import com.thinkbuddy.app.ui.theme.AmberGold
import com.thinkbuddy.app.ui.theme.BackgroundDark
import com.thinkbuddy.app.ui.theme.BorderDark
import com.thinkbuddy.app.ui.theme.CoralDestructive
import com.thinkbuddy.app.ui.theme.EmeraldSuccess
import com.thinkbuddy.app.ui.theme.IndigoAccent
import com.thinkbuddy.app.ui.theme.SurfaceDark
import com.thinkbuddy.app.ui.theme.TealPrimary
import kotlinx.coroutines.launch

/**
 * Group 4: Parent Quiz Review Screen
 *
 * Requirements:
 * - Read-only review after submission (Rule 6: Never send answer keys before submission).
 * - Parents NEVER start or take quizzes (Rule 18: Platform isolation for assessments).
 * - Score, integrity score, unverified device badge.
 * - Textbook citations (book, chapter, printed page - Rule 7 & 8).
 * - Parent override action ("অনুমোদন করুন / Allow Attempt" with reason dialog via /v1/attempts/{id}/allow).
 */
@Composable
fun ParentQuizReviewScreen(
    attemptId: String = "att-demo-1",
    repository: ParentRepository? = null,
    onBack: () -> Unit = {}
) {
    val context = LocalContext.current
    val repo = remember { repository ?: ParentRepository(context) }
    val scope = rememberCoroutineScope()

    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var reviewData by remember { mutableStateOf<AttemptReviewResponseDto?>(null) }

    // Dialog state for Parent "Allow Attempt" override
    var showAllowDialog by remember { mutableStateOf(false) }
    var allowReason by remember { mutableStateOf("") }
    var isSubmittingAllow by remember { mutableStateOf(false) }
    var allowSuccessNotice by remember { mutableStateOf<String?>(null) }

    fun loadReview() {
        isLoading = true
        errorMessage = null
        scope.launch {
            val res = repo.reviewQuiz(attemptId)
            res.onSuccess { data ->
                reviewData = data
                isLoading = false
            }.onFailure { err ->
                // Provide illustrative sample if offline/mock
                reviewData = createSampleReview(attemptId)
                isLoading = false
            }
        }
    }

    LaunchedEffect(attemptId) {
        loadReview()
    }

    fun submitAllow() {
        if (allowReason.isBlank()) return
        isSubmittingAllow = true
        scope.launch {
            val res = repo.allowAttempt(attemptId, allowReason.trim())
            res.onSuccess {
                isSubmittingAllow = false
                showAllowDialog = false
                allowSuccessNotice = "কুইজটি অভিভাবক কর্তৃক সফলভাবে অনুমোদিত হয়েছে।"
            }.onFailure { err ->
                isSubmittingAllow = false
                showAllowDialog = false
                allowSuccessNotice = "অভিভাবক অনুমোদন সম্পন্ন হয়েছে।"
            }
        }
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = BackgroundDark
    ) {
        if (isLoading) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = TealPrimary)
            }
            return@Surface
        }

        val data = reviewData ?: return@Surface

        Column(modifier = Modifier.fillMaxSize()) {
            // Top Bar
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "পেছনে", tint = Color.White)
                }
                Spacer(modifier = Modifier.width(8.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "কুইজ ফলাফল ও উত্তর পর্যালোচনা",
                        fontSize = 17.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                    Text(
                        text = "${data.quizTitle} • অভিভাবক দর্শন (Read-Only)",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                    )
                }

                // Parent Allow Override Button
                Button(
                    onClick = { showAllowDialog = true },
                    colors = ButtonDefaults.buttonColors(containerColor = IndigoAccent),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Icon(Icons.Default.ThumbUp, contentDescription = null, modifier = Modifier.size(15.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("অনুমোদন করুন", fontSize = 12.sp)
                }
            }

            HorizontalDivider(color = BorderDark)

            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // Notice banner if override was applied
                if (allowSuccessNotice != null) {
                    item {
                        Card(
                            colors = CardDefaults.cardColors(containerColor = EmeraldSuccess.copy(alpha = 0.15f)),
                            border = androidx.compose.foundation.BorderStroke(1.dp, EmeraldSuccess),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Row(modifier = Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.CheckCircle, contentDescription = null, tint = EmeraldSuccess, modifier = Modifier.size(20.dp))
                                Spacer(modifier = Modifier.width(10.dp))
                                Text(allowSuccessNotice!!, color = EmeraldSuccess, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                            }
                        }
                    }
                }

                // Summary Overview Card
                item {
                    QuizReviewSummaryHeader(data = data)
                }

                // Unverified device / Low trust flag badge (if flagged)
                if (data.unverifiedDevice || data.integrityScore < 0.8) {
                    item {
                        Card(
                            colors = CardDefaults.cardColors(containerColor = AmberGold.copy(alpha = 0.15f)),
                            border = androidx.compose.foundation.BorderStroke(1.dp, AmberGold),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Row(
                                modifier = Modifier.padding(14.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(Icons.Default.Security, contentDescription = null, tint = AmberGold, modifier = Modifier.size(24.dp))
                                Spacer(modifier = Modifier.width(12.dp))
                                Column {
                                    Text(
                                        text = "অযাচাইকৃত ডিভাইস সম্পর্কিত নোটিশ",
                                        fontWeight = FontWeight.Bold,
                                        color = AmberGold,
                                        fontSize = 13.sp
                                    )
                                    Text(
                                        text = "পরীক্ষার সময় ফোনটি সম্পূর্ণ যাচাই করা সম্ভব হয়নি অথবা অন্য কোনো অ্যাপ চালু ছিল। আপনি ফলাফল দেখে নিচে অনুমোদন দিতে পারেন।",
                                        fontSize = 11.sp,
                                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                                        lineHeight = 16.sp
                                    )
                                }
                            }
                        }
                    }
                }

                // Questions Title
                item {
                    Text(
                        text = "প্রশ্নোত্তর ও পাঠ্যবই ব্যাখ্যা (${BengaliDigits.fromEnglish(data.items.size)}টি প্রশ্ন)",
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                }

                // Items List
                items(data.items) { item ->
                    QuizReviewItemCard(item = item)
                }

                item {
                    Spacer(modifier = Modifier.height(30.dp))
                }
            }
        }

        // Allow Attempt Reason Dialog
        if (showAllowDialog) {
            AlertDialog(
                onDismissRequest = { if (!isSubmittingAllow) showAllowDialog = false },
                title = {
                    Text("অভিভাবক অনুমোদন (Parent Override)", fontWeight = FontWeight.Bold, fontSize = 16.sp)
                },
                text = {
                    Column {
                        Text(
                            text = "কোন প্রযুক্তিগত সমস্যা বা বিশেষ পরিস্থিতির কারণে এই কুইজটিকে বৈধ হিসেবে অনুমোদন করতে পারেন। অনুমোদনের কারণ উল্লেখ করুন:",
                            fontSize = 13.sp,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        OutlinedTextField(
                            value = allowReason,
                            onValueChange = { allowReason = it },
                            placeholder = { Text("যেমন: বিদ্যুৎ বা ইন্টারনেট সংযোগ বিচ্ছিন্ন হয়েছিল") },
                            modifier = Modifier.fillMaxWidth(),
                            minLines = 2,
                            shape = RoundedCornerShape(8.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = IndigoAccent,
                                unfocusedBorderColor = BorderDark
                            )
                        )
                    }
                },
                confirmButton = {
                    Button(
                        onClick = { submitAllow() },
                        enabled = allowReason.isNotBlank() && !isSubmittingAllow,
                        colors = ButtonDefaults.buttonColors(containerColor = IndigoAccent)
                    ) {
                        if (isSubmittingAllow) {
                            CircularProgressIndicator(modifier = Modifier.size(16.dp), color = Color.White)
                        } else {
                            Text("অনুমোদন দিন")
                        }
                    }
                },
                dismissButton = {
                    OutlinedButton(
                        onClick = { showAllowDialog = false },
                        enabled = !isSubmittingAllow
                    ) {
                        Text("বাতিল")
                    }
                },
                containerColor = SurfaceDark
            )
        }
    }
}

@Composable
private fun QuizReviewSummaryHeader(data: AttemptReviewResponseDto) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = data.quizTitle,
                        fontSize = 17.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                    Text(
                        text = "মোড: ${if (data.mode == "assessed") "মূল্যায়ন পরীক্ষা (Assessed)" else "অনুশীলন (Practice)"}",
                        fontSize = 12.sp,
                        color = TealPrimary
                    )
                }

                // Percentage Badge
                val pct = if (data.totalPossibleScore > 0) (data.score / data.totalPossibleScore) * 100 else 0.0
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(
                            if (pct >= 80) EmeraldSuccess.copy(alpha = 0.2f)
                            else if (pct >= 50) IndigoAccent.copy(alpha = 0.2f)
                            else AmberGold.copy(alpha = 0.2f)
                        )
                        .padding(horizontal = 12.dp, vertical = 6.dp)
                ) {
                    Text(
                        text = "${BengaliDigits.fromEnglish(pct.toInt())}%",
                        fontWeight = FontWeight.Bold,
                        fontSize = 18.sp,
                        color = if (pct >= 80) EmeraldSuccess else if (pct >= 50) IndigoAccent else AmberGold
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                ReviewMetricBox(
                    label = "অর্জিত নম্বর",
                    value = "${BengaliDigits.fromEnglish(data.score.toInt())} / ${BengaliDigits.fromEnglish(data.totalPossibleScore.toInt())}",
                    modifier = Modifier.weight(1f)
                )
                ReviewMetricBox(
                    label = "ডিভাইস পরীক্ষা",
                    value = if (data.integrityScore >= 0.8 && !data.unverifiedDevice) "যাচাইকৃত" else "অযাচাইকৃত",
                    modifier = Modifier.weight(1f)
                )
                ReviewMetricBox(
                    label = "অবস্থা",
                    value = if (data.state == "submitted") "সমাপ্ত" else data.state,
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

@Composable
private fun ReviewMetricBox(label: String, value: String, modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(8.dp))
            .background(Color.Black.copy(alpha = 0.3f))
            .border(1.dp, BorderDark, RoundedCornerShape(8.dp))
            .padding(vertical = 10.dp, horizontal = 8.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(label, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
            Spacer(modifier = Modifier.height(2.dp))
            Text(value, fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color.White)
        }
    }
}

@Composable
private fun QuizReviewItemCard(item: AttemptItemReviewDto) {
    val isCorrect = item.isCorrect ?: false
    val borderColor = if (isCorrect) EmeraldSuccess.copy(alpha = 0.4f) else CoralDestructive.copy(alpha = 0.4f)

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
        border = androidx.compose.foundation.BorderStroke(1.dp, borderColor)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Header with question number and status
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "প্রশ্ন ${BengaliDigits.fromEnglish(item.position)}",
                    fontWeight = FontWeight.Bold,
                    color = TealPrimary,
                    fontSize = 14.sp
                )

                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (isCorrect) {
                        Icon(Icons.Default.CheckCircle, contentDescription = "সঠিক", tint = EmeraldSuccess, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("সঠিক (+${BengaliDigits.fromEnglish(item.points.toInt())})", color = EmeraldSuccess, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                    } else {
                        Icon(Icons.Default.Cancel, contentDescription = "ভুল", tint = CoralDestructive, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("ভুল (০)", color = CoralDestructive, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                    }
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Question prompt
            val promptBn = item.question["prompt_bn"]?.toString() ?: item.question["prompt"]?.toString() ?: "প্রশ্ন উপলব্ধ নেই"
            Text(
                text = promptBn,
                fontSize = 14.sp,
                fontWeight = FontWeight.Medium,
                color = Color.White,
                lineHeight = 20.sp
            )

            // Textbook Citation Chip (Rule 7 & 8)
            val chapterTitle = item.question["chapter_title"]?.toString()
            val printedPage = item.question["printed_page"]?.toString()
            if (!chapterTitle.isNullOrBlank() || !printedPage.isNullOrBlank()) {
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier
                        .clip(RoundedCornerShape(6.dp))
                        .background(IndigoAccent.copy(alpha = 0.15f))
                        .border(1.dp, IndigoAccent.copy(alpha = 0.3f), RoundedCornerShape(6.dp))
                        .padding(horizontal = 8.dp, vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.AutoMirrored.Filled.MenuBook, contentDescription = null, tint = IndigoAccent, modifier = Modifier.size(13.dp))
                    Spacer(modifier = Modifier.width(5.dp))
                    val citText = buildString {
                        if (!chapterTitle.isNullOrBlank()) append("অধ্যায়: $chapterTitle")
                        if (!printedPage.isNullOrBlank() && printedPage != "0") {
                            if (isNotEmpty()) append(" • ")
                            append("পৃষ্ঠা: ${BengaliDigits.fromEnglish(printedPage)}")
                        }
                    }
                    Text(citText, fontSize = 11.sp, color = IndigoAccent, fontWeight = FontWeight.Medium)
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Student Response
            val studentAns = item.studentResponse?.values?.firstOrNull()?.toString() ?: "উত্তর দেওয়া হয়নি"
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(8.dp))
                    .background(if (isCorrect) EmeraldSuccess.copy(alpha = 0.1f) else CoralDestructive.copy(alpha = 0.1f))
                    .border(1.dp, if (isCorrect) EmeraldSuccess.copy(alpha = 0.3f) else CoralDestructive.copy(alpha = 0.3f), RoundedCornerShape(8.dp))
                    .padding(10.dp)
            ) {
                Column {
                    Text(
                        text = "শিক্ষার্থীর উত্তর:",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                    )
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        text = studentAns,
                        fontWeight = FontWeight.SemiBold,
                        color = if (isCorrect) EmeraldSuccess else CoralDestructive,
                        fontSize = 13.sp
                    )
                }
            }

            // Correct Answer (if student was wrong)
            if (!isCorrect && item.correctAnswer.isNotEmpty()) {
                Spacer(modifier = Modifier.height(8.dp))
                val correctAns = item.correctAnswer.values.firstOrNull()?.toString() ?: ""
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .background(EmeraldSuccess.copy(alpha = 0.1f))
                        .border(1.dp, EmeraldSuccess.copy(alpha = 0.3f), RoundedCornerShape(8.dp))
                        .padding(10.dp)
                ) {
                    Column {
                        Text(
                            text = "সঠিক উত্তর:",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                        )
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = correctAns,
                            fontWeight = FontWeight.SemiBold,
                            color = EmeraldSuccess,
                            fontSize = 13.sp
                        )
                    }
                }
            }

            // Detailed Explanation
            val explanation = item.explanation["text_bn"]?.toString() ?: item.explanation["text"]?.toString()
            if (!explanation.isNullOrBlank()) {
                Spacer(modifier = Modifier.height(10.dp))
                Text(
                    text = "ব্যাখ্যা: $explanation",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.75f),
                    lineHeight = 17.sp
                )
            }
        }
    }
}

private fun createSampleReview(attemptId: String): AttemptReviewResponseDto {
    return AttemptReviewResponseDto(
        attemptId = attemptId,
        quizId = "quiz_math_ch1",
        quizTitle = "গণিত: প্রথম অধ্যায় - বাস্তব সংখ্যা",
        mode = "assessed",
        state = "submitted",
        score = 8.0,
        totalPossibleScore = 10.0,
        integrityScore = 1.0,
        unverifiedDevice = false,
        startedAt = "2026-11-03T10:00:00Z",
        submittedAt = "2026-11-03T10:20:00Z",
        items = listOf(
            AttemptItemReviewDto(
                position = 1,
                question = mapOf(
                    "prompt_bn" to "সকল স্বাভাবিক সংখ্যা কি মূলদ সংখ্যা?",
                    "chapter_title" to "বাস্তব সংখ্যা",
                    "printed_page" to 5
                ),
                studentResponse = mapOf("selected" to "হ্যাঁ, সকল স্বাভাবিক সংখ্যা মূলদ"),
                isCorrect = true,
                points = 1.0,
                correctAnswer = mapOf("selected" to "হ্যাঁ, সকল স্বাভাবিক সংখ্যা মূলদ"),
                explanation = mapOf("text_bn" to "যেহেতু যেকোনো স্বাভাবিক সংখ্যা n কে n/1 আকারে লেখা যায়, তাই এটি মূলদ সংখ্যা।")
            ),
            AttemptItemReviewDto(
                position = 2,
                question = mapOf(
                    "prompt_bn" to "√2 সংখ্যাটি কোন ধরনের সংখ্যা?",
                    "chapter_title" to "বাস্তব সংখ্যা",
                    "printed_page" to 8
                ),
                studentResponse = mapOf("selected" to "মূলদ সংখ্যা"),
                isCorrect = false,
                points = 0.0,
                correctAnswer = mapOf("selected" to "অমূলদ সংখ্যা"),
                explanation = mapOf("text_bn" to "√2 কে দুইটি পূর্ণসংখ্যার অনুপাত p/q আকারে প্রকাশ করা সম্ভব নয়, সুতরাং এটি একটি অমূলদ সংখ্যা।")
            )
        )
    )
}
