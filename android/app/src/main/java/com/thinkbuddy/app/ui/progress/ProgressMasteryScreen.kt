package com.thinkbuddy.app.ui.progress

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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.EmojiEvents
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.Inbox
import androidx.compose.material.icons.filled.LocalFireDepartment
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
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
import com.thinkbuddy.app.core.network.ApiClient
import com.thinkbuddy.app.core.network.ChapterMasteryItem
import com.thinkbuddy.app.core.network.ProgressSummaryResponse
import com.thinkbuddy.app.core.utils.BengaliDigits
import com.thinkbuddy.app.ui.theme.AmberGold
import com.thinkbuddy.app.ui.theme.CoralDestructive
import com.thinkbuddy.app.ui.theme.EmeraldSuccess
import com.thinkbuddy.app.ui.theme.IndigoAccent
import com.thinkbuddy.app.ui.theme.SurfaceDark
import com.thinkbuddy.app.ui.theme.TealPrimary
import kotlinx.coroutines.launch
import java.io.IOException

/**
 * Progress & Mastery Screen (Group 1):
 * Concept mastery metrics, streak days, study minutes, and dynamic learning signal remediations.
 * Fully wired to real endpoints /v1/progress/summary and /v1/progress/mastery.
 * Handles Loading, Empty ("পর্যাপ্ত তথ্য নেই"), Error, and Offline states.
 */
@Composable
fun ProgressMasteryScreen(
    isTablet: Boolean = false
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var isLoading by remember { mutableStateOf(false) }
    var isOffline by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var summary by remember { mutableStateOf<ProgressSummaryResponse?>(null) }
    var chapterMasteries by remember { mutableStateOf<List<ChapterMasteryItem>>(emptyList()) }

    fun loadProgress() {
        isLoading = true
        isOffline = false
        errorMessage = null
        scope.launch {
            try {
                val api = ApiClient.getService(context)
                val sumResp = api.getProgressSummary()
                if (sumResp.isSuccessful && sumResp.body() != null) {
                    summary = sumResp.body()
                }

                val mastResp = api.getProgressMastery()
                if (mastResp.isSuccessful && mastResp.body() != null) {
                    chapterMasteries = mastResp.body()!!
                } else {
                    chapterMasteries = emptyList()
                }
            } catch (e: IOException) {
                isOffline = true
                errorMessage = "ইন্টারনেট সংযোগ বিচ্ছিন্ন। অফলাইন মোডে আছেন।"
            } catch (e: Exception) {
                errorMessage = "অগ্রগতি লোড করা যায়নি: ${e.message}"
            } finally {
                isLoading = false
            }
        }
    }

    LaunchedEffect(Unit) {
        loadProgress()
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
                    text = "অগ্রগতি ও পারদর্শিতা (Mastery)",
                    style = MaterialTheme.typography.headlineSmall,
                    color = TealPrimary,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "অধ্যায়ভিত্তিক দক্ষতা ও সাপ্তাহিক অধ্যয়ন পরিসংখ্যান",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f)
                )
            }
            Icon(
                imageVector = Icons.Default.EmojiEvents,
                contentDescription = null,
                tint = AmberGold,
                modifier = Modifier.size(32.dp)
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
                        text = "অফলাইন মোড: পারদর্শিতা ডেটা সিঙ্ক করা যায়নি।",
                        color = CoralDestructive,
                        fontSize = 13.sp,
                        modifier = Modifier.weight(1f)
                    )
                    IconButton(onClick = { loadProgress() }) {
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
                            text = "পারদর্শিতা ডেটা লোড হচ্ছে...",
                            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f),
                            fontSize = 14.sp
                        )
                    }
                }
            }

            errorMessage != null && summary == null && chapterMasteries.isEmpty() -> {
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
                            onClick = { loadProgress() },
                            colors = ButtonDefaults.buttonColors(containerColor = TealPrimary)
                        ) {
                            Text("পুনরায় চেষ্টা করুন (Retry)", color = Color.White)
                        }
                    }
                }
            }

            summary == null && chapterMasteries.isEmpty() -> {
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
                            text = "পারদর্শিতা বিশ্লেষণের জন্য প্রয়োজনীয় কুইজ ও পাঠের তথ্য এখনো জমা হয়নি।",
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                            fontSize = 13.sp
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(
                            onClick = { loadProgress() },
                            colors = ButtonDefaults.buttonColors(containerColor = TealPrimary)
                        ) {
                            Text("রিফ্রেশ করুন", color = Color.White)
                        }
                    }
                }
            }

            else -> {
                val currentSummary = summary ?: ProgressSummaryResponse()
                val overallPercent = (currentSummary.overallMastery * 100).toInt()

                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    item {
                        // Streak & Total Study Time Card
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(16.dp),
                            colors = CardDefaults.cardColors(containerColor = SurfaceDark)
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(20.dp),
                                horizontalArrangement = Arrangement.SpaceAround,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                // Streak
                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Icon(
                                            imageVector = Icons.Default.LocalFireDepartment,
                                            contentDescription = null,
                                            tint = AmberGold,
                                            modifier = Modifier.size(28.dp)
                                        )
                                        Text(
                                            text = "${BengaliDigits.fromInt(currentSummary.streakDays)} দিন",
                                            fontSize = 24.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = Color.White
                                        )
                                    }
                                    Text(
                                        text = "ধারাবাহিক অধ্যয়ন",
                                        fontSize = 12.sp,
                                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                                    )
                                }

                                Box(
                                    modifier = Modifier
                                        .height(40.dp)
                                        .background(MaterialTheme.colorScheme.onSurface.copy(alpha = 0.1f))
                                )

                                // Today Minutes
                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    Text(
                                        text = "${BengaliDigits.fromInt(currentSummary.studyMinutesToday)} মিনিট",
                                        fontSize = 24.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = TealPrimary
                                    )
                                    Text(
                                        text = "আজকের অধ্যয়ন সময়",
                                        fontSize = 12.sp,
                                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                                    )
                                }

                                Box(
                                    modifier = Modifier
                                        .height(40.dp)
                                        .background(MaterialTheme.colorScheme.onSurface.copy(alpha = 0.1f))
                                )

                                // Overall Mastery
                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    Text(
                                        text = "${BengaliDigits.fromInt(overallPercent)}%",
                                        fontSize = 24.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = EmeraldSuccess
                                    )
                                    Text(
                                        text = currentSummary.statusLabelBn.ifBlank { "সার্বিক দক্ষতা" },
                                        fontSize = 12.sp,
                                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                                    )
                                }
                            }
                        }
                    }

                    item {
                        Text(
                            text = "অধ্যায়ভিত্তিক পারদর্শিতা (${BengaliDigits.fromInt(chapterMasteries.size)}টি অধ্যায়)",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                    }

                    if (chapterMasteries.isEmpty()) {
                        item {
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(12.dp),
                                colors = CardDefaults.cardColors(containerColor = SurfaceDark)
                            ) {
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(24.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                        text = "অধ্যায়ভিত্তিক পারদর্শিতা তথ্যের জন্য পর্যাপ্ত তথ্য নেই।",
                                        fontSize = 13.sp,
                                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                                    )
                                }
                            }
                        }
                    } else {
                        items(chapterMasteries) { item ->
                            val scorePercent = (item.score * 100).toInt()
                            val progressColor = when {
                                item.score >= 0.8f -> EmeraldSuccess
                                item.score >= 0.5f -> TealPrimary
                                else -> AmberGold
                            }

                            Card(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp),
                                shape = RoundedCornerShape(14.dp),
                                colors = CardDefaults.cardColors(containerColor = SurfaceDark)
                            ) {
                                Column(modifier = Modifier.padding(16.dp)) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Column(modifier = Modifier.weight(1f)) {
                                            Text(
                                                text = item.subject,
                                                fontSize = 12.sp,
                                                color = TealPrimary,
                                                fontWeight = FontWeight.SemiBold
                                            )
                                            Text(
                                                text = item.chapterTitle,
                                                fontWeight = FontWeight.SemiBold,
                                                fontSize = 15.sp,
                                                color = Color.White
                                            )
                                        }
                                        Text(
                                            text = "${BengaliDigits.fromInt(scorePercent)}%",
                                            fontWeight = FontWeight.Bold,
                                            fontSize = 16.sp,
                                            color = progressColor
                                        )
                                    }

                                    Spacer(modifier = Modifier.height(8.dp))

                                    LinearProgressIndicator(
                                        progress = { item.score },
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .height(8.dp)
                                            .clip(RoundedCornerShape(4.dp)),
                                        color = progressColor,
                                        trackColor = MaterialTheme.colorScheme.surface
                                    )

                                    Spacer(modifier = Modifier.height(6.dp))

                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween
                                    ) {
                                        Text(
                                            text = item.statusLabelBn,
                                            fontSize = 12.sp,
                                            color = progressColor,
                                            fontWeight = FontWeight.Medium
                                        )
                                        Text(
                                            text = "আত্মবিশ্বাস: ${(item.confidence * 100).toInt()}%",
                                            fontSize = 11.sp,
                                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                                        )
                                    }
                                }
                            }
                        }
                    }

                    item {
                        // Remediated Signals Card (Requirement 4: approved wording)
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(16.dp),
                            colors = CardDefaults.cardColors(containerColor = SurfaceDark)
                        ) {
                            Column(modifier = Modifier.padding(18.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        imageVector = Icons.Default.CheckCircle,
                                        contentDescription = null,
                                        tint = EmeraldSuccess,
                                        modifier = Modifier.padding(end = 8.dp)
                                    )
                                    Text(
                                        text = "স্বয়ংক্রিয় সমাধানকৃত অনুশীলন সংকেত (Remediated Practice Signals)",
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 15.sp,
                                        color = Color.White
                                    )
                                }
                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    text = "কুইজে চিহ্নিত শিখন ঘাটতিগুলো ৩ দিনের ব্যবধানী রিভিশনে সাফল্যের সাথে সমাধান করা হয়েছে।",
                                    fontSize = 13.sp,
                                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.8f),
                                    lineHeight = 18.sp
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
