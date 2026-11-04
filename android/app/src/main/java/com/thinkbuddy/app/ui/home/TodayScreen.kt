package com.thinkbuddy.app.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Book
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thinkbuddy.app.core.network.ApiClient
import com.thinkbuddy.app.core.network.TodayTask
import com.thinkbuddy.app.core.utils.BengaliDigits
import androidx.compose.material.icons.filled.CloudOff
import com.thinkbuddy.app.core.storage.CachedTodayPlan
import com.thinkbuddy.app.core.storage.OfflinePlanCache
import com.thinkbuddy.app.ui.theme.AmberGold
import com.thinkbuddy.app.ui.theme.BorderDark
import com.thinkbuddy.app.ui.theme.EmeraldSuccess
import com.thinkbuddy.app.ui.theme.IndigoAccent
import com.thinkbuddy.app.ui.theme.TealPrimary
import java.util.Calendar

/**
 * Pure time-based Bengali greeting function satisfying User Directive (3) & (5):
 * strictly zero religious terms or greetings, fully dynamic by hour of day.
 */
fun getTimeBasedGreeting(name: String, hour: Int = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)): Pair<String, String> {
    val greetingPrefix = when (hour) {
        in 5..11 -> "শুভ সকাল"
        in 12..15 -> "শুভ দুপুর"
        in 16..18 -> "শুভ বিকাল"
        in 19..22 -> "শুভ সন্ধ্যা"
        else -> "শুভ রাত্রি"
    }
    val title = "$greetingPrefix, $name!"
    val subtitle = when (hour) {
        in 5..11 -> "আজকের পড়ার লক্ষ্য পূরণ করার চমৎকার একটি দিন।"
        in 12..15 -> "দিনের লক্ষ্যমাত্রা অর্জনে মনোযোগ ধরে রাখো।"
        in 16..18 -> "বিকেলের পড়ার অধিবেশন শুরু করার উপযুক্ত সময়।"
        in 19..22 -> "দিনের বাকি অধ্যায়গুলো শেষ করে রিভিশন সম্পন্ন করো।"
        else -> "আজকের পড়াশোনা পর্যালোচনা করো এবং পর্যাপ্ত বিশ্রাম নাও।"
    }
    return Pair(title, subtitle)
}

@Composable
fun TodayScreen(
    studentName: String = "শিক্ষার্থী",
    studentId: String? = null,
    isTablet: Boolean = false,
    onStartSession: (subject: String, chapter: String, targetMins: Int) -> Unit,
    onOpenAssessedQuiz: (quizId: String) -> Unit,
    onLogout: () -> Unit
) {
    val context = LocalContext.current
    var displayName by remember { mutableStateOf(studentName) }
    var streakDays by remember { mutableIntStateOf(0) }
    var dailyTargetMinutes by remember { mutableIntStateOf(0) }
    var dailyCompletedMinutes by remember { mutableIntStateOf(0) }
    var tasks by remember { mutableStateOf<List<TodayTask>>(emptyList()) }
    var selectedTask by remember { mutableStateOf<TodayTask?>(null) }
    var hasAssessedQuizOffer by remember { mutableStateOf(false) }
    var assessedQuizId by remember { mutableStateOf("quiz_assessed_1") }
    var isLoading by remember { mutableStateOf(false) }
    var isOfflineMode by remember { mutableStateOf(false) }

    val (greetingTitle, greetingSubtitle) = getTimeBasedGreeting(displayName)

    // Connect Today to real API per Item (3)
    LaunchedEffect(studentId) {
        try {
            isLoading = true
            val api = ApiClient.getService(context)

            // 1. Resolve student profile for authentic display name
            try {
                val meResp = api.getMe()
                if (meResp.isSuccessful && meResp.body() != null) {
                    val profile = meResp.body()!!
                    if (profile.displayName.isNotBlank()) {
                        displayName = profile.displayName
                    }
                }
            } catch (_: Exception) {
                // keep current display name
            }

            // 2. Fetch today schedule from /v1/students/{student_id}/today
            val targetId = studentId ?: "std-demo-1"
            val todayResp = api.getTodaySchedule(targetId)
            if (todayResp.isSuccessful && todayResp.body() != null) {
                val data = todayResp.body()!!
                streakDays = data.streak
                dailyTargetMinutes = data.totalPlannedMinutes
                dailyCompletedMinutes = data.completedMinutes

                // Map study tasks dynamically from backend
                val mapped = if (data.studyTasks.isNotEmpty()) {
                    data.studyTasks.map { t ->
                        val printedPages = (t.refs?.get("printed_pages") ?: t.refs?.get("printed_page") ?: "–").toString()
                        val chBn = (t.refs?.get("chapter_title") ?: t.chapterId ?: "সাধারণ অধ্যায়").toString()
                        val subBn = (t.refs?.get("subject_bn") ?: t.subject).toString()
                        TodayTask(
                            id = t.id,
                            subject = t.subject,
                            subjectBn = subBn,
                            chapter = t.chapterId ?: "",
                            chapterBn = chBn,
                            targetMinutes = t.estMinutes,
                            completedMinutes = if (t.status == "done" || t.status == "completed") t.estMinutes else 0,
                            status = if (t.status == "done") "completed" else t.status,
                            printedPages = printedPages,
                            guideline = "মনোযোগ দিয়ে পাঠ্যবই পড়ে উদাহরণ ও অনুশীলনীগুলো সমাধান করো।"
                        )
                    }
                } else if (data.tasks.isNotEmpty()) {
                    data.tasks
                } else {
                    emptyList()
                }

                tasks = mapped
                selectedTask = mapped.firstOrNull()

                // Save to offline cache
                OfflinePlanCache.saveTodayPlan(
                    context,
                    CachedTodayPlan(
                        streakDays = streakDays,
                        dailyTargetMinutes = dailyTargetMinutes,
                        dailyCompletedMinutes = dailyCompletedMinutes,
                        tasks = mapped
                    )
                )
                isOfflineMode = false

                // Rule (5): Only show assessed quiz card when server offers one
                hasAssessedQuizOffer = data.quizTasks.any { it.type == "quiz" || it.type == "review_quiz" }
                if (hasAssessedQuizOffer) {
                    assessedQuizId = data.quizTasks.firstOrNull()?.id ?: "quiz_assessed_1"
                }
            } else {
                val cached = OfflinePlanCache.getCachedTodayPlan(context)
                if (cached != null) {
                    streakDays = cached.streakDays
                    dailyTargetMinutes = cached.dailyTargetMinutes
                    dailyCompletedMinutes = cached.dailyCompletedMinutes
                    tasks = cached.tasks
                    selectedTask = cached.tasks.firstOrNull()
                    isOfflineMode = true
                } else {
                    tasks = emptyList()
                    selectedTask = null
                }
            }
        } catch (_: Exception) {
            val cached = OfflinePlanCache.getCachedTodayPlan(context)
            if (cached != null) {
                streakDays = cached.streakDays
                dailyTargetMinutes = cached.dailyTargetMinutes
                dailyCompletedMinutes = cached.dailyCompletedMinutes
                tasks = cached.tasks
                selectedTask = cached.tasks.firstOrNull()
                isOfflineMode = true
            } else {
                tasks = emptyList()
                selectedTask = null
            }
        } finally {
            isLoading = false
        }
    }

    if (selectedTask == null && tasks.isNotEmpty()) {
        selectedTask = tasks.first()
    }

    if (isTablet) {
        // Tablet: 2-pane layout
        Row(
            modifier = Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background)
                .padding(24.dp)
        ) {
            // Left Pane (Tasks list & stats)
            Column(
                modifier = Modifier
                    .weight(1.1f)
                    .fillMaxHeight()
                    .padding(end = 16.dp)
            ) {
                if (isOfflineMode) {
                    Card(
                        modifier = Modifier.fillMaxWidth().padding(bottom = 12.dp),
                        colors = CardDefaults.cardColors(containerColor = AmberGold.copy(alpha = 0.2f)),
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Row(modifier = Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.CloudOff, contentDescription = "অফলাইন", tint = AmberGold)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("অফলাইন মোড: পূর্বের সংরক্ষিত প্ল্যান প্রদর্শিত হচ্ছে", color = AmberGold, fontSize = 12.sp)
                        }
                    }
                }
                GreetingCard(title = greetingTitle, subtitle = greetingSubtitle)
                Spacer(modifier = Modifier.height(16.dp))
                OverallProgressCard(
                    streakDays = streakDays,
                    completedMinutes = dailyCompletedMinutes,
                    targetMinutes = dailyTargetMinutes
                )
                Spacer(modifier = Modifier.height(16.dp))

                // Assessed quiz card: only when server offers one
                if (hasAssessedQuizOffer) {
                    AssessedQuizCard(onOpenQuiz = { onOpenAssessedQuiz(assessedQuizId) })
                    Spacer(modifier = Modifier.height(16.dp))
                }

                Text(
                    text = "আজকের পাঠ্য তালিকা",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onBackground
                )
                Spacer(modifier = Modifier.height(8.dp))

                LazyColumn(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(tasks) { task ->
                        TaskListItem(
                            task = task,
                            isSelected = selectedTask?.id == task.id,
                            onClick = { selectedTask = task }
                        )
                    }
                }
            }

            // Right Pane (Task Detail & Action)
            Column(
                modifier = Modifier
                    .weight(0.9f)
                    .fillMaxHeight()
                    .padding(start = 16.dp)
            ) {
                selectedTask?.let { task ->
                    TaskDetailCard(
                        task = task,
                        onStartSession = {
                            onStartSession(task.subjectBn, task.chapterBn, task.targetMinutes)
                        }
                    )
                }
            }
        }
    } else {
        // Phone: Single-pane vertical scroll
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            if (isOfflineMode) {
                item {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = AmberGold.copy(alpha = 0.2f)),
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Row(modifier = Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.CloudOff, contentDescription = "অফলাইন", tint = AmberGold)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("অফলাইন মোড: পূর্বের সংরক্ষিত প্ল্যান প্রদর্শিত হচ্ছে", color = AmberGold, fontSize = 12.sp)
                        }
                    }
                }
            }
            item {
                GreetingCard(title = greetingTitle, subtitle = greetingSubtitle)
            }
            item {
                OverallProgressCard(
                    streakDays = streakDays,
                    completedMinutes = dailyCompletedMinutes,
                    targetMinutes = dailyTargetMinutes
                )
            }

            // Rule (5): Assessed quiz card only when offered by server
            if (hasAssessedQuizOffer) {
                item {
                    AssessedQuizCard(onOpenQuiz = { onOpenAssessedQuiz(assessedQuizId) })
                }
            }

            item {
                Text(
                    text = "আজকের পাঠ্য তালিকা",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onBackground
                )
            }

            items(tasks) { task ->
                TaskListItem(
                    task = task,
                    isSelected = selectedTask?.id == task.id,
                    onClick = {
                        selectedTask = task
                        onStartSession(task.subjectBn, task.chapterBn, task.targetMinutes)
                    }
                )
            }
        }
    }
}

@Composable
fun GreetingCard(title: String, subtitle: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Text(
                text = title,
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.ExtraBold,
                color = MaterialTheme.colorScheme.onSurface
            )
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.75f)
            )
        }
    }
}

@Composable
fun OverallProgressCard(streakDays: Int, completedMinutes: Int, targetMinutes: Int) {
    val progress = if (targetMinutes > 0) (completedMinutes.toFloat() / targetMinutes.toFloat()).coerceIn(0f, 1f) else 0f
    val percent = (progress * 100).toInt()

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(CircleShape)
                            .background(AmberGold.copy(alpha = 0.2f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(Icons.Default.Star, contentDescription = "Streak", tint = AmberGold, modifier = Modifier.size(20.dp))
                    }
                    Spacer(modifier = Modifier.width(10.dp))
                    Column {
                        Text(
                            text = "ধারাবাহিকতা (Streak)",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                        )
                        Text(
                            text = "${BengaliDigits.toBengali(streakDays)} দিন একটানা",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                    }
                }

                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        text = "দৈনিক লক্ষ্য",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                    )
                    Text(
                        text = "${BengaliDigits.toBengali(completedMinutes)} / ${BengaliDigits.toBengali(targetMinutes)} মি.",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = TealPrimary
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            LinearProgressIndicator(
                progress = { progress },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(8.dp)
                    .clip(RoundedCornerShape(4.dp)),
                color = TealPrimary,
                trackColor = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.1f)
            )

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = "${BengaliDigits.toBengali(percent)}% লক্ষ্য সম্পন্ন",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
            )
        }
    }
}

@Composable
fun TaskListItem(task: TodayTask, isSelected: Boolean, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isSelected) TealPrimary.copy(alpha = 0.12f) else MaterialTheme.colorScheme.surface
        ),
        border = androidx.compose.foundation.BorderStroke(
            if (isSelected) 1.5.dp else 1.dp,
            if (isSelected) TealPrimary else BorderDark
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(42.dp)
                    .clip(CircleShape)
                    .background(
                        when (task.status) {
                            "completed" -> EmeraldSuccess.copy(alpha = 0.2f)
                            "in_progress" -> IndigoAccent.copy(alpha = 0.2f)
                            else -> MaterialTheme.colorScheme.onSurface.copy(alpha = 0.08f)
                        }
                    ),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = when (task.status) {
                        "completed" -> Icons.Default.CheckCircle
                        "in_progress" -> Icons.Default.PlayArrow
                        else -> Icons.Default.Book
                    },
                    contentDescription = task.status,
                    tint = when (task.status) {
                        "completed" -> EmeraldSuccess
                        "in_progress" -> IndigoAccent
                        else -> MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                    },
                    modifier = Modifier.size(22.dp)
                )
            }

            Spacer(modifier = Modifier.width(14.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = task.subjectBn,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Text(
                    text = task.chapterBn,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                )
            }

            Text(
                text = "${BengaliDigits.toBengali(task.targetMinutes)} মি.",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Bold,
                color = TealPrimary
            )
        }
    }
}

@Composable
fun TaskDetailCard(task: TodayTask, onStartSession: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Text(
                text = "নির্বাচিত পাঠ্য",
                style = MaterialTheme.typography.labelMedium,
                color = TealPrimary,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "${task.subjectBn} – ${task.chapterBn}",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface
            )

            Spacer(modifier = Modifier.height(14.dp))

            // Rule 7 & 8: Printed page numbers citation
            Card(
                shape = RoundedCornerShape(10.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.background),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.Default.Book, contentDescription = "Textbook", tint = TealPrimary, modifier = Modifier.size(20.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "পাঠ্যবই রেফারেন্স: পৃষ্ঠা ${task.printedPages} (মুদ্রিত পৃষ্ঠা)",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f)
                    )
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            Text(
                text = "নির্দেশনা: ${task.guideline}",
                style = MaterialTheme.typography.bodyMedium,
                lineHeight = 22.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.8f)
            )

            Spacer(modifier = Modifier.height(20.dp))

            Button(
                onClick = onStartSession,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp),
                colors = ButtonDefaults.buttonColors(containerColor = TealPrimary),
                shape = RoundedCornerShape(12.dp)
            ) {
                Icon(Icons.Default.PlayArrow, contentDescription = "Start Session")
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "পড়ার সেশন শুরু করো (${BengaliDigits.toBengali(task.targetMinutes)} মিনিট)",
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp
                )
            }
        }
    }
}

/**
 * AssessedQuizCard satisfying Rule (5):
 * Replaces technical terms (FLAG_SECURE, Play Integrity, attestation) with
 * simple, reassuring student-friendly wording in Bengali.
 */
@Composable
fun AssessedQuizCard(onOpenQuiz: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = androidx.compose.foundation.BorderStroke(1.dp, IndigoAccent.copy(alpha = 0.5f))
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Default.Security,
                        contentDescription = "Security",
                        tint = IndigoAccent,
                        modifier = Modifier.size(22.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "মূল্যায়িত কুইজ",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(6.dp))
                        .background(IndigoAccent.copy(alpha = 0.15f))
                        .padding(horizontal = 8.dp, vertical = 4.dp)
                ) {
                    Text(
                        text = "সুরক্ষিত মূল্যায়ন",
                        fontSize = 11.sp,
                        color = IndigoAccent,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            Text(
                text = "কুইজের সময় স্ক্রিনশট ও মাল্টি-উইন্ডো বন্ধ রাখা হয়। মনোযোগ সহকারে নিজের মেধা যাচাই করো।",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.75f)
            )

            Spacer(modifier = Modifier.height(16.dp))

            Button(
                onClick = onOpenQuiz,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(46.dp),
                colors = ButtonDefaults.buttonColors(containerColor = IndigoAccent),
                shape = RoundedCornerShape(12.dp)
            ) {
                Icon(Icons.Default.Lock, contentDescription = "Secure Quiz")
                Spacer(modifier = Modifier.width(8.dp))
                Text(text = "মূল্যায়িত কুইজ শুরু করো", fontWeight = FontWeight.Bold)
            }
        }
    }
}
