package com.thinkbuddy.app.ui.session

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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thinkbuddy.app.ui.theme.AmberGold
import com.thinkbuddy.app.ui.theme.BorderDark
import com.thinkbuddy.app.ui.theme.CoralDestructive
import com.thinkbuddy.app.ui.theme.EmeraldSuccess
import com.thinkbuddy.app.ui.theme.SurfaceDark
import com.thinkbuddy.app.ui.theme.TealPrimary
import kotlinx.coroutines.delay

@Composable
fun StudySessionScreen(
    subject: String,
    chapter: String,
    targetMins: Int,
    onFinishSession: (elapsedSeconds: Int) -> Unit,
    onCancelSession: () -> Unit
) {
    var isRunning by remember { mutableStateOf(true) }
    var elapsedSeconds by remember { mutableIntStateOf(0) }
    var isOnBreak by remember { mutableStateOf(false) }

    // Timer loop
    LaunchedEffect(isRunning, isOnBreak) {
        while (isRunning && !isOnBreak) {
            delay(1000L)
            elapsedSeconds++
        }
    }

    val minutes = elapsedSeconds / 60
    val seconds = elapsedSeconds % 60
    val timeFormatted = String.format(java.util.Locale.ROOT, "%02d:%02d", minutes, seconds)

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(24.dp)
    ) {
        // Exit / Cancel button
        IconButton(
            onClick = onCancelSession,
            modifier = Modifier
                .align(Alignment.TopStart)
                .clip(CircleShape)
                .background(SurfaceDark)
        ) {
            Icon(imageVector = Icons.Default.Close, contentDescription = "Cancel", tint = Color.White)
        }

        // Center Content
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(top = 40.dp, bottom = 40.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Text(
                text = subject,
                style = MaterialTheme.typography.titleLarge,
                color = TealPrimary,
                fontSize = 26.sp
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = chapter,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.8f)
            )

            Spacer(modifier = Modifier.height(40.dp))

            // Glowing Timer Circle
            Box(
                modifier = Modifier
                    .size(250.dp)
                    .clip(CircleShape)
                    .background(SurfaceDark)
                    .padding(8.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        text = timeFormatted,
                        fontSize = 54.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        color = if (isOnBreak) AmberGold else Color.White
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = if (isOnBreak) "বিরতি চলছে" else "লক্ষ্য: $targetMins মিনিট",
                        fontSize = 14.sp,
                        color = if (isOnBreak) AmberGold else TealPrimary
                    )
                }
            }

            Spacer(modifier = Modifier.height(40.dp))

            // Action buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Break toggle
                Button(
                    onClick = { isOnBreak = !isOnBreak },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (isOnBreak) TealPrimary else AmberGold.copy(alpha = 0.2f)
                    ),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text(
                        text = if (isOnBreak) "বিরতি শেষ" else "৫ মি. বিরতি ☕",
                        color = if (isOnBreak) Color.White else AmberGold
                    )
                }

                // Pause / Resume
                Button(
                    onClick = { isRunning = !isRunning },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (isRunning) SurfaceDark else EmeraldSuccess
                    ),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text(
                        text = if (isRunning) "পজ করুন" else "চালিয়ে যান",
                        color = Color.White
                    )
                }
            }

            Spacer(modifier = Modifier.height(30.dp))

            // Finish Session Button
            Button(
                onClick = {
                    isRunning = false
                    onFinishSession(elapsedSeconds)
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = EmeraldSuccess),
                shape = RoundedCornerShape(14.dp)
            ) {
                Text(
                    text = "পড়া শেষ ও রেকর্ড সংরক্ষণ করুন",
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp
                )
            }
        }
    }
}
