package com.thinkbuddy.app.ui.revision

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Autorenew
import androidx.compose.material.icons.filled.Book
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
import com.thinkbuddy.app.core.network.ApiClient
import com.thinkbuddy.app.core.network.RevisionItemResponse
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
 * Revision Screen (Group 1):
 * Spaced Repetition Review Queue and Leitner 5-Box Reinforcement System.
 * Fully wired to real endpoint /v1/revision/daily.
 * Handles Loading, Empty ("পর্যাপ্ত তথ্য নেই"), Error, and Offline states.
 */
@Composable
fun RevisionScreen(
    isTablet: Boolean = false,
    onStartRevision: (RevisionItemResponse) -> Unit = {}
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var isLoading by remember { mutableStateOf(false) }
    var isOffline by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var reviewItems by remember { mutableStateOf<List<RevisionItemResponse>>(emptyList()) }

    fun loadRevision() {
        isLoading = true
        isOffline = false
        errorMessage = null
        scope.launch {
            try {
                val api = ApiClient.getService(context)
                val resp = api.getDailyRevision()
                if (resp.isSuccessful && resp.body() != null) {
                    reviewItems = resp.body()!!
                } else {
                    reviewItems = emptyList()
                }
            } catch (e: IOException) {
                isOffline = true
                errorMessage = "ইন্টারনেট সংযোগ বিচ্ছিন্ন। অফলাইন মোডে আছেন।"
            } catch (e: Exception) {
                errorMessage = "রিভিশন তথ্য লোড করা যায়নি: ${e.message}"
            } finally {
                isLoading = false
            }
        }
    }

    LaunchedEffect(Unit) {
        loadRevision()
    }

    val box1Count = reviewItems.count { it.box == 1 }
    val box2Count = reviewItems.count { it.box == 2 }
    val box3Count = reviewItems.count { it.box == 3 }
    val box4Count = reviewItems.count { it.box == 4 }
    val box5Count = reviewItems.count { it.box == 5 }

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
                    text = "স্মৃতিস্থকরণ ও পুনরাবৃত্তি (Revision)",
                    style = MaterialTheme.typography.headlineSmall,
                    color = TealPrimary,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "ব্যবধানী শিখন ও অনুশীলন প্রয়োজনীয় বিষয়ের চর্চা",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f)
                )
            }
            Icon(
                imageVector = Icons.Default.Autorenew,
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
                        text = "অফলাইন মোড: রিভিশন ডেটা সিঙ্ক করা যায়নি।",
                        color = CoralDestructive,
                        fontSize = 13.sp,
                        modifier = Modifier.weight(1f)
                    )
                    IconButton(onClick = { loadRevision() }) {
                        Icon(
                            imageVector = Icons.Default.Refresh,
                            contentDescription = "Retry",
                            tint = CoralDestructive
                        )
                    }
                }
            }
        }

        // Leitner 5-Box Status Card (Rule: 5 boxes from backend)
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(containerColor = SurfaceDark)
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    text = "লাইটনার মেমোরি বক্স স্থিতি (Leitner 5-Box System)",
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp,
                    color = Color.White
                )
                Spacer(modifier = Modifier.height(10.dp))
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    LeitnerBoxSummary(boxNum = 1, interval = "১ দিন", count = box1Count, color = CoralDestructive)
                    LeitnerBoxSummary(boxNum = 2, interval = "৩ দিন", count = box2Count, color = AmberGold)
                    LeitnerBoxSummary(boxNum = 3, interval = "৭ দিন", count = box3Count, color = TealPrimary)
                    LeitnerBoxSummary(boxNum = 4, interval = "১৪ দিন", count = box4Count, color = IndigoAccent)
                    LeitnerBoxSummary(boxNum = 5, interval = "৩০ দিন", count = box5Count, color = EmeraldSuccess)
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        when {
            isLoading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator(color = TealPrimary)
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = "রিভিশন তালিকা লোড হচ্ছে...",
                            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f),
                            fontSize = 14.sp
                        )
                    }
                }
            }

            errorMessage != null && reviewItems.isEmpty() -> {
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
                            onClick = { loadRevision() },
                            colors = ButtonDefaults.buttonColors(containerColor = TealPrimary)
                        ) {
                            Text("পুনরায় চেষ্টা করুন (Retry)", color = Color.White)
                        }
                    }
                }
            }

            reviewItems.isEmpty() -> {
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
                            text = "আজকের জন্য কোনো রিভিশন টপিক অপেক্ষমান নেই।",
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                            fontSize = 13.sp
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(
                            onClick = { loadRevision() },
                            colors = ButtonDefaults.buttonColors(containerColor = TealPrimary)
                        ) {
                            Text("রিফ্রেশ করুন", color = Color.White)
                        }
                    }
                }
            }

            else -> {
                Text(
                    text = "আজকের রিভিশন তালিকা (${BengaliDigits.fromInt(reviewItems.size)}টি টপিক)",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = Color.White
                )

                Spacer(modifier = Modifier.height(12.dp))

                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    items(reviewItems) { item ->
                        RevisionCard(
                            item = item,
                            onStartRevision = onStartRevision
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun LeitnerBoxSummary(
    boxNum: Int,
    interval: String,
    count: Int,
    color: Color
) {
    Box(
        modifier = Modifier
            .width(84.dp)
            .clip(RoundedCornerShape(10.dp))
            .background(color.copy(alpha = 0.12f))
            .padding(vertical = 10.dp, horizontal = 6.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = "${BengaliDigits.fromInt(count)}টি",
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold,
                color = color
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = "বক্স ${BengaliDigits.fromInt(boxNum)}",
                fontSize = 11.sp,
                fontWeight = FontWeight.SemiBold,
                color = color.copy(alpha = 0.9f)
            )
            Text(
                text = interval,
                fontSize = 10.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
            )
        }
    }
}

@Composable
fun RevisionCard(
    item: RevisionItemResponse,
    onStartRevision: (RevisionItemResponse) -> Unit
) {
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
                    text = "${item.subject} • ${item.chapterTitle}",
                    fontSize = 13.sp,
                    color = TealPrimary,
                    fontWeight = FontWeight.SemiBold
                )
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(6.dp))
                        .background(if (item.isOverdue) CoralDestructive.copy(alpha = 0.15f) else AmberGold.copy(alpha = 0.15f))
                        .padding(horizontal = 8.dp, vertical = 4.dp)
                ) {
                    Text(
                        text = if (item.isOverdue) "বকেয়া (Overdue)" else "বক্স ${BengaliDigits.fromInt(item.box)}",
                        color = if (item.isOverdue) CoralDestructive else AmberGold,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = item.chapterTitle,
                fontWeight = FontWeight.Bold,
                fontSize = 16.sp,
                color = Color.White
            )

            Spacer(modifier = Modifier.height(10.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Book,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                        modifier = Modifier.height(16.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = "স্মৃতিস্থকরণ ও পুনরাবৃত্তি",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                    )
                }

                Button(
                    onClick = { onStartRevision(item) },
                    colors = ButtonDefaults.buttonColors(containerColor = TealPrimary),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.PlayArrow,
                        contentDescription = null,
                        tint = Color.White,
                        modifier = Modifier.padding(end = 4.dp)
                    )
                    Text("রিভিশন শুরু", fontSize = 13.sp, color = Color.White)
                }
            }
        }
    }
}
