package com.thinkbuddy.app.ui.plan

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Book
import androidx.compose.material.icons.filled.CalendarToday
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.Inbox
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import com.thinkbuddy.app.ThinkBuddyApp
import com.thinkbuddy.app.core.network.ApiClient
import com.thinkbuddy.app.core.network.PlannerTaskResponse
import com.thinkbuddy.app.core.utils.BengaliDigits
import com.thinkbuddy.app.ui.theme.AmberGold
import com.thinkbuddy.app.ui.theme.CoralDestructive
import com.thinkbuddy.app.ui.theme.EmeraldSuccess
import com.thinkbuddy.app.ui.theme.SurfaceDark
import com.thinkbuddy.app.ui.theme.TealPrimary
import kotlinx.coroutines.launch
import java.io.IOException

data class PlanDayUi(
    val date: String,
    val dayName: String,
    val dayType: String,
    val tasks: List<PlannerTaskResponse>
)

/**
 * Plan Timeline Screen (Group 1):
 * Day-by-day learning plan, day types, allocated study minutes, and printed page references.
 * Fully wired to real endpoints (/v1/students/{id}/plan and /v1/students/{id}/today).
 * Handles Loading, Empty ("পর্যাপ্ত তথ্য নেই"), Error, and Offline states.
 */
@Composable
fun PlanTimelineScreen(
    isTablet: Boolean = false,
    onSelectTask: (PlannerTaskResponse) -> Unit = {},
    onStartTaskSession: (PlannerTaskResponse) -> Unit = {}
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var isLoading by remember { mutableStateOf(false) }
    var isOffline by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var planDays by remember { mutableStateOf<List<PlanDayUi>>(emptyList()) }

    fun loadPlan() {
        isLoading = true
        isOffline = false
        errorMessage = null
        scope.launch {
            try {
                val api = ApiClient.getService(context)
                val userId = ThinkBuddyApp.instance.tokenStorage.getUserId() ?: "std-demo-1"
                val planResp = api.getStudentPlan(userId)

                if (planResp.isSuccessful && planResp.body() != null && planResp.body()!!.days.isNotEmpty()) {
                    val days = planResp.body()!!.days
                    planDays = days.map { day ->
                        PlanDayUi(
                            date = day.date,
                            dayName = day.dayType,
                            dayType = day.dayType,
                            tasks = day.tasks
                        )
                    }
                } else {
                    // Fallback to today schedule if multi-day plan is not generated yet
                    val todayResp = api.getTodaySchedule(userId)
                    if (todayResp.isSuccessful && todayResp.body() != null) {
                        val body = todayResp.body()!!
                        val taskList = if (body.studyTasks.isNotEmpty()) {
                            body.studyTasks
                        } else {
                            body.tasks.map { t ->
                                PlannerTaskResponse(
                                    id = t.id,
                                    subject = t.subjectBn.ifBlank { t.subject },
                                    chapterId = t.chapter,
                                    refs = mapOf("printed_pages" to t.printedPages, "chapter_title" to t.chapterBn),
                                    estMinutes = t.targetMinutes,
                                    status = t.status
                                )
                            }
                        }
                        if (taskList.isNotEmpty()) {
                            planDays = listOf(
                                PlanDayUi(
                                    date = body.date.ifBlank { "আজকের তারিখ" },
                                    dayName = "আজকের পরিকল্পনা",
                                    dayType = "school_day",
                                    tasks = taskList
                                )
                            )
                        } else {
                            planDays = emptyList()
                        }
                    } else {
                        planDays = emptyList()
                    }
                }
            } catch (e: IOException) {
                isOffline = true
                errorMessage = "ইন্টারনেট সংযোগ পাওয়া যায়নি। অফলাইন মোডে আছেন।"
            } catch (e: Exception) {
                errorMessage = "পরিকল্পনা লোড করতে সমস্যা হয়েছে: ${e.message}"
            } finally {
                isLoading = false
            }
        }
    }

    LaunchedEffect(Unit) {
        loadPlan()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(if (isTablet) 24.dp else 16.dp)
    ) {
        // Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = "অধ্যয়ন পরিকল্পনা (Study Timeline)",
                    style = MaterialTheme.typography.headlineSmall,
                    color = TealPrimary,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "দৈনিক বিষয়বন্টন ও মুদ্রিত পৃষ্ঠা রেফারেন্স",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f)
                )
            }
            Icon(
                imageVector = Icons.Default.CalendarToday,
                contentDescription = null,
                tint = TealPrimary
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Offline Banner
        if (isOffline) {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 12.dp),
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(containerColor = CoralDestructive.copy(alpha = 0.15f))
            ) {
                Row(
                    modifier = Modifier.padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = Icons.Default.CloudOff,
                        contentDescription = "Offline",
                        tint = CoralDestructive,
                        modifier = Modifier.padding(end = 8.dp)
                    )
                    Text(
                        text = "অফলাইন মোড: সংযোগ বিচ্ছিন্ন। ক্যাশ করা ডেটা দেখাচ্ছে অথবা পুনরায় চেষ্টা করুন।",
                        color = CoralDestructive,
                        fontSize = 13.sp,
                        modifier = Modifier.weight(1f)
                    )
                    IconButton(onClick = { loadPlan() }) {
                        Icon(
                            imageVector = Icons.Default.Refresh,
                            contentDescription = "Retry",
                            tint = CoralDestructive
                        )
                    }
                }
            }
        }

        when {
            isLoading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator(color = TealPrimary)
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = "পরিকল্পনা লোড হচ্ছে...",
                            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f),
                            fontSize = 14.sp
                        )
                    }
                }
            }

            errorMessage != null && planDays.isEmpty() -> {
                // Error State
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            imageVector = Icons.Default.ErrorOutline,
                            contentDescription = null,
                            tint = CoralDestructive,
                            modifier = Modifier.height(48.dp)
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = errorMessage ?: "লোড করা সম্ভব হয়নি",
                            color = Color.White,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Medium
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(
                            onClick = { loadPlan() },
                            colors = ButtonDefaults.buttonColors(containerColor = TealPrimary)
                        ) {
                            Text("পুনরায় চেষ্টা করুন (Retry)", color = Color.White)
                        }
                    }
                }
            }

            planDays.isEmpty() -> {
                // Empty State ("পর্যাপ্ত তথ্য নেই")
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            imageVector = Icons.Default.Inbox,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                            modifier = Modifier.height(48.dp)
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "পর্যাপ্ত তথ্য নেই (Not Enough Data)",
                            color = Color.White,
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = "আপনার জন্য এখনও কোনো সক্রিয় অধ্যয়ন পরিকল্পনা প্রস্তুত হয়নি।",
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                            fontSize = 13.sp
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(
                            onClick = { loadPlan() },
                            colors = ButtonDefaults.buttonColors(containerColor = TealPrimary)
                        ) {
                            Text("রিফ্রেশ করুন", color = Color.White)
                        }
                    }
                }
            }

            else -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    items(planDays) { day ->
                        PlanDayCard(
                            day = day,
                            onSelectTask = onSelectTask,
                            onStartTaskSession = onStartTaskSession
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun PlanDayCard(
    day: PlanDayUi,
    onSelectTask: (PlannerTaskResponse) -> Unit,
    onStartTaskSession: (PlannerTaskResponse) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = day.date,
                        fontWeight = FontWeight.Bold,
                        fontSize = 16.sp,
                        color = Color.White
                    )
                    Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                    Text(
                        text = "• ${day.dayName}",
                        fontSize = 14.sp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                    )
                }

                // Day type badge
                val (badgeColor, badgeText) = when (day.dayType) {
                    "holiday" -> AmberGold to "ছুটির দিন"
                    "exam_day" -> Color(0xFFEF4444) to "পরীক্ষার দিন"
                    "blackout" -> Color(0xFF9CA3AF) to "বিরতি"
                    else -> TealPrimary to "স্কুল দিন"
                }
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(6.dp))
                        .background(badgeColor.copy(alpha = 0.15f))
                        .padding(horizontal = 8.dp, vertical = 4.dp)
                ) {
                    Text(
                        text = badgeText,
                        color = badgeColor,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            day.tasks.forEach { task ->
                val isCompleted = task.status == "completed"
                val pages = task.refs?.get("printed_pages")?.toString() ?: "–"

                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                    shape = RoundedCornerShape(10.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.6f))
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(
                            modifier = Modifier
                                .weight(1f)
                                .padding(end = 8.dp)
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                if (isCompleted) {
                                    Icon(
                                        imageVector = Icons.Default.CheckCircle,
                                        contentDescription = null,
                                        tint = EmeraldSuccess,
                                        modifier = Modifier.padding(end = 6.dp)
                                    )
                                }
                                Text(
                                    text = task.subject,
                                    fontWeight = FontWeight.SemiBold,
                                    fontSize = 15.sp,
                                    color = if (isCompleted) MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f) else Color.White
                                )
                            }
                            Spacer(modifier = Modifier.height(2.dp))
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    imageVector = Icons.Default.Book,
                                    contentDescription = null,
                                    tint = TealPrimary,
                                    modifier = Modifier.padding(end = 4.dp)
                                )
                                Text(
                                    text = "পাঠ্যবই: পৃষ্ঠা $pages",
                                    fontSize = 13.sp,
                                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                                )
                                Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                                Text(
                                    text = "• ${BengaliDigits.fromInt(task.estMinutes)} মিনিট",
                                    fontSize = 13.sp,
                                    color = AmberGold
                                )
                            }
                        }

                        IconButton(
                            onClick = { onStartTaskSession(task) },
                            modifier = Modifier
                                .clip(RoundedCornerShape(8.dp))
                                .background(TealPrimary)
                        ) {
                            Icon(
                                imageVector = Icons.Default.PlayArrow,
                                contentDescription = "Start Session",
                                tint = Color.White
                            )
                        }
                    }
                }
            }
        }
    }
}
