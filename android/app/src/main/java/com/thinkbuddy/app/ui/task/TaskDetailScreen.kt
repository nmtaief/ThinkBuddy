package com.thinkbuddy.app.ui.task

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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Book
import androidx.compose.material.icons.filled.CheckCircleOutline
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thinkbuddy.app.core.network.PlannerTaskResponse
import com.thinkbuddy.app.core.utils.BengaliDigits
import com.thinkbuddy.app.ui.theme.AmberGold
import com.thinkbuddy.app.ui.theme.EmeraldSuccess
import com.thinkbuddy.app.ui.theme.SurfaceDark
import com.thinkbuddy.app.ui.theme.TealPrimary

/**
 * Task Detail Screen (Group 1):
 * In-depth study task view showing NCTB textbook printed page citations (Rule 8),
 * study objectives, split-target breakdown, and launch controls.
 */
@Composable
fun TaskDetailScreen(
    task: PlannerTaskResponse,
    onBack: () -> Unit = {},
    onStartSession: (PlannerTaskResponse) -> Unit = {}
) {
    val printedPages = task.refs?.get("printed_pages")?.toString() ?: "–"
    val chapterTitle = task.refs?.get("chapter_title")?.toString() ?: task.chapterId ?: "সাধারণ পাঠ"

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(20.dp)
    ) {
        // Top Bar
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(
                onClick = onBack,
                modifier = Modifier
                    .clip(RoundedCornerShape(10.dp))
                    .background(SurfaceDark)
            ) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                    contentDescription = "Back",
                    tint = Color.White
                )
            }
            Spacer(modifier = Modifier.padding(horizontal = 8.dp))
            Text(
                text = "পাঠ্যক্রম বিবরণ (Task Details)",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = Color.White
            )
        }

        Spacer(modifier = Modifier.height(20.dp))

        // Main Task Header Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(containerColor = SurfaceDark)
        ) {
            Column(modifier = Modifier.padding(20.dp)) {
                Text(
                    text = task.subject,
                    style = MaterialTheme.typography.headlineSmall,
                    color = TealPrimary,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "অধ্যায়: $chapterTitle",
                    style = MaterialTheme.typography.bodyLarge,
                    color = Color.White.copy(alpha = 0.9f),
                    modifier = Modifier.padding(top = 4.dp)
                )

                Spacer(modifier = Modifier.height(16.dp))

                // Printed Page Reference Card (Rule 8 strictly observed)
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .background(TealPrimary.copy(alpha = 0.12f))
                        .padding(14.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Book,
                            contentDescription = null,
                            tint = TealPrimary,
                            modifier = Modifier.padding(end = 10.dp)
                        )
                        Column {
                            Text(
                                text = "মুদ্রিত পাঠ্যবই পৃষ্ঠা (Printed Page Number):",
                                fontSize = 12.sp,
                                color = TealPrimary,
                                fontWeight = FontWeight.SemiBold
                            )
                            Text(
                                text = "পৃষ্ঠা $printedPages",
                                fontSize = 18.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color.White
                            )
                        }
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Study Targets & Split Breakdown Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(containerColor = SurfaceDark)
        ) {
            Column(modifier = Modifier.padding(20.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "অধ্যয়ন বিভাজন ও লক্ষ্য",
                        fontWeight = FontWeight.Bold,
                        fontSize = 16.sp,
                        color = Color.White
                    )
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Timer,
                            contentDescription = null,
                            tint = AmberGold,
                            modifier = Modifier.padding(end = 4.dp)
                        )
                        Text(
                            text = "${task.estMinutes} মিনিট",
                            fontWeight = FontWeight.Bold,
                            color = AmberGold
                        )
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                // Split Targets
                val readingMins = (task.estMinutes * 0.55).toInt()
                val practiceMins = (task.estMinutes * 0.35).toInt()
                val reviewMins = task.estMinutes - readingMins - practiceMins

                SplitTargetItem(
                    title = "১. মূল পাঠ্য ও সূত্র অনুধাবন",
                    duration = "$readingMins মিনিট",
                    color = TealPrimary
                )
                SplitTargetItem(
                    title = "২. উদাহরণ ও গাণিতিক অনুশীলন",
                    duration = "$practiceMins মিনিট",
                    color = EmeraldSuccess
                )
                SplitTargetItem(
                    title = "৩. পুনরাবৃত্তি ও সংক্ষিপ্ত সারসংক্ষেপ",
                    duration = "$reviewMins মিনিট",
                    color = AmberGold
                )
            }
        }

        Spacer(modifier = Modifier.weight(1f))

        // Start Session Action CTA
        Button(
            onClick = { onStartSession(task) },
            modifier = Modifier
                .fillMaxWidth()
                .height(54.dp),
            colors = ButtonDefaults.buttonColors(containerColor = TealPrimary),
            shape = RoundedCornerShape(14.dp)
        ) {
            Icon(
                imageVector = Icons.Default.PlayArrow,
                contentDescription = null,
                tint = Color.White,
                modifier = Modifier.padding(end = 8.dp)
            )
            Text(
                text = "পড়ার সেশন শুরু করো (${task.estMinutes} মিনিট)",
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold,
                color = Color.White
            )
        }
    }
}

@Composable
fun SplitTargetItem(
    title: String,
    duration: String,
    color: Color
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                imageVector = Icons.Default.CheckCircleOutline,
                contentDescription = null,
                tint = color,
                modifier = Modifier.padding(end = 8.dp)
            )
            Text(
                text = title,
                fontSize = 14.sp,
                color = Color.White.copy(alpha = 0.85f)
            )
        }
        Text(
            text = duration,
            fontSize = 13.sp,
            fontWeight = FontWeight.SemiBold,
            color = color
        )
    }
}
