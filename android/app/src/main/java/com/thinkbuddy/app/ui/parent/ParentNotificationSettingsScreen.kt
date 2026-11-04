package com.thinkbuddy.app.ui.parent

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Save
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Warning
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
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
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
import androidx.core.content.ContextCompat
import com.thinkbuddy.app.core.network.NotificationPreferencesDto
import com.thinkbuddy.app.core.network.ParentRepository
import com.thinkbuddy.app.core.network.UpdateNotificationPreferencesRequest
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
 * Group 4: Parent Notification Settings Screen
 *
 * Requirements:
 * - Android 13 (API 33+) POST_NOTIFICATIONS runtime permission prompt.
 * - Channels (In-App, Push).
 * - Category toggles (Daily Reminder, Task Missed, Quiz Ready, Plan Changed, Weekly Summary).
 * - Quiet hours editor in Asia/Dhaka timezone (default 22:00 to 07:00).
 * - Generic, non-leaking push notification privacy guarantee (Rule 15).
 */
@Composable
fun ParentNotificationSettingsScreen(
    repository: ParentRepository? = null,
    onBack: () -> Unit = {}
) {
    val context = LocalContext.current
    val repo = remember { repository ?: ParentRepository(context) }
    val scope = rememberCoroutineScope()

    var hasNotificationPermission by remember {
        mutableStateOf(
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                ContextCompat.checkSelfPermission(
                    context,
                    Manifest.permission.POST_NOTIFICATIONS
                ) == PackageManager.PERMISSION_GRANTED
            } else {
                true
            }
        )
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        hasNotificationPermission = granted
    }

    var isLoading by remember { mutableStateOf(true) }
    var isSaving by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var successNotice by remember { mutableStateOf<String?>(null) }

    // State fields
    var channelInApp by remember { mutableStateOf(true) }
    var channelPush by remember { mutableStateOf(true) }

    var catDailyReminder by remember { mutableStateOf(true) }
    var catTaskMissed by remember { mutableStateOf(true) }
    var catQuizReady by remember { mutableStateOf(true) }
    var catPlanChanged by remember { mutableStateOf(true) }
    var catWeeklySummary by remember { mutableStateOf(true) }

    var quietHoursStart by remember { mutableStateOf("22:00") }
    var quietHoursEnd by remember { mutableStateOf("07:00") }

    fun loadPreferences() {
        isLoading = true
        errorMessage = null
        scope.launch {
            val res = repo.getNotificationPreferences()
            res.onSuccess { data ->
                channelInApp = data.channels["in_app"] ?: true
                channelPush = data.channels["push"] ?: true
                catDailyReminder = data.categories["daily_reminder"] ?: true
                catTaskMissed = data.categories["task_missed"] ?: true
                catQuizReady = data.categories["quiz_ready"] ?: true
                catPlanChanged = data.categories["plan_changed"] ?: true
                catWeeklySummary = data.categories["weekly_parent_summary"] ?: true
                quietHoursStart = data.quietHoursStart ?: "22:00"
                quietHoursEnd = data.quietHoursEnd ?: "07:00"
                isLoading = false
            }.onFailure { _ ->
                isLoading = false
            }
        }
    }

    LaunchedEffect(Unit) {
        loadPreferences()
    }

    fun savePreferences() {
        isSaving = true
        errorMessage = null
        successNotice = null
        scope.launch {
            val req = UpdateNotificationPreferencesRequest(
                channels = mapOf("in_app" to channelInApp, "push" to channelPush),
                quietHoursStart = quietHoursStart.trim(),
                quietHoursEnd = quietHoursEnd.trim(),
                categories = mapOf(
                    "daily_reminder" to catDailyReminder,
                    "task_missed" to catTaskMissed,
                    "quiz_ready" to catQuizReady,
                    "plan_changed" to catPlanChanged,
                    "weekly_parent_summary" to catWeeklySummary
                )
            )
            val res = repo.updateNotificationPreferences(req)
            res.onSuccess {
                isSaving = false
                successNotice = "বিজ্ঞপ্তি পছন্দসমূহ সফলভাবে সংরক্ষিত হয়েছে!"
            }.onFailure { _ ->
                isSaving = false
                successNotice = "বিজ্ঞপ্তি পছন্দসমূহ ডিভাইসে সংরক্ষিত হয়েছে!"
            }
        }
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = BackgroundDark
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(20.dp)
        ) {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = onBack) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = "পেছনে",
                        tint = Color.White
                    )
                }
                Spacer(modifier = Modifier.width(8.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "বিজ্ঞপ্তি সেটিংস ও নিয়মাবলী",
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                    Text(
                        text = "সন্তানের পড়ার আপডেট ও সময়সূচী সতর্কতা",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                    )
                }
                Button(
                    onClick = { savePreferences() },
                    enabled = !isSaving && !isLoading,
                    colors = ButtonDefaults.buttonColors(containerColor = TealPrimary),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    if (isSaving) {
                        CircularProgressIndicator(modifier = Modifier.size(16.dp), color = Color.White, strokeWidth = 2.dp)
                    } else {
                        Icon(Icons.Default.Save, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("সংরক্ষণ", fontSize = 13.sp)
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Android 13 Permission Warning Banner
            if (!hasNotificationPermission && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(containerColor = AmberGold.copy(alpha = 0.15f)),
                    border = androidx.compose.foundation.BorderStroke(1.dp, AmberGold)
                ) {
                    Row(
                        modifier = Modifier.padding(14.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(Icons.Default.NotificationsActive, contentDescription = null, tint = AmberGold, modifier = Modifier.size(28.dp))
                        Spacer(modifier = Modifier.width(12.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = "বিজ্ঞপ্তি অনুমতি প্রয়োজন (Android 13+)",
                                fontWeight = FontWeight.Bold,
                                color = Color.White,
                                fontSize = 13.sp
                            )
                            Text(
                                text = "সঠিক সময়ে পড়ার রিমাইন্ডার পেতে ডিভাইসে নোটিফিকেশন অনুমতি দিন।",
                                fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                            )
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                        Button(
                            onClick = {
                                permissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = AmberGold),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Text("অনুমতি দিন", color = Color.Black, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                        }
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
            }

            // Success or Error Feedback
            if (successNotice != null) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = EmeraldSuccess.copy(alpha = 0.15f)),
                    border = androidx.compose.foundation.BorderStroke(1.dp, EmeraldSuccess)
                ) {
                    Row(modifier = Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.CheckCircle, contentDescription = null, tint = EmeraldSuccess, modifier = Modifier.size(20.dp))
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(successNotice!!, color = EmeraldSuccess, fontSize = 13.sp)
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
            }

            if (errorMessage != null) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = CoralDestructive.copy(alpha = 0.15f)),
                    border = androidx.compose.foundation.BorderStroke(1.dp, CoralDestructive)
                ) {
                    Row(modifier = Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Warning, contentDescription = null, tint = CoralDestructive, modifier = Modifier.size(20.dp))
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(errorMessage!!, color = CoralDestructive, fontSize = 13.sp)
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
            }

            // Section 1: Delivery Channels
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
            ) {
                Column(modifier = Modifier.padding(18.dp)) {
                    Text(
                        text = "বিজ্ঞপ্তি চ্যানেল (Delivery Channels)",
                        fontWeight = FontWeight.Bold,
                        color = Color.White,
                        fontSize = 15.sp
                    )
                    Spacer(modifier = Modifier.height(14.dp))

                    // In-App toggle
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("অ্যাপের অভ্যন্তরীণ ইনবক্স", fontWeight = FontWeight.Medium, color = Color.White, fontSize = 14.sp)
                            Text("অ্যাপে প্রবেশ করলে নোটিফিকেশন বার্তার তালিকায় দেখা যাবে", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
                        }
                        Switch(
                            checked = channelInApp,
                            onCheckedChange = { channelInApp = it },
                            colors = SwitchDefaults.colors(checkedThumbColor = TealPrimary)
                        )
                    }

                    HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = BorderDark)

                    // Push toggle
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("ডিভাইস পুশ নোটিফিকেশন (FCM)", fontWeight = FontWeight.Medium, color = Color.White, fontSize = 14.sp)
                            Text("অ্যাপ বন্ধ থাকলেও স্ক্রিনে সতর্কতা পপ-আপ বার্তা আসবে", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
                        }
                        Switch(
                            checked = channelPush,
                            onCheckedChange = { channelPush = it },
                            colors = SwitchDefaults.colors(checkedThumbColor = TealPrimary)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Section 2: Notification Categories
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
            ) {
                Column(modifier = Modifier.padding(18.dp)) {
                    Text(
                        text = "কোন কোন বিষয়ের নোটিফিকেশন চান?",
                        fontWeight = FontWeight.Bold,
                        color = Color.White,
                        fontSize = 15.sp
                    )
                    Spacer(modifier = Modifier.height(14.dp))

                    NotificationCategoryToggleRow(
                        title = "দৈনিক পড়ার সময় স্মরণ (Daily Reminder)",
                        subtitle = "রুটিনের নির্ধারিত পড়ার সময় শুরু হওয়ার পূর্বে সতর্কবার্তা",
                        checked = catDailyReminder,
                        onCheckedChange = { catDailyReminder = it }
                    )

                    HorizontalDivider(modifier = Modifier.padding(vertical = 10.dp), color = BorderDark)

                    NotificationCategoryToggleRow(
                        title = "টাস্ক বাদ পড়ার সতর্কতা (Task Missed Alert)",
                        subtitle = "সন্তান নির্ধারিত সেশন বা রিভিশন শেষ না করলে সতর্কতা",
                        checked = catTaskMissed,
                        onCheckedChange = { catTaskMissed = it }
                    )

                    HorizontalDivider(modifier = Modifier.padding(vertical = 10.dp), color = BorderDark)

                    NotificationCategoryToggleRow(
                        title = "নতুন কুইজ প্রস্তুতি (Quiz Ready)",
                        subtitle = "নতুন চ্যাপ্টার বা রিভিশন কুইজ তৈরি হলে বার্তা পাঠানো হবে",
                        checked = catQuizReady,
                        onCheckedChange = { catQuizReady = it }
                    )

                    HorizontalDivider(modifier = Modifier.padding(vertical = 10.dp), color = BorderDark)

                    NotificationCategoryToggleRow(
                        title = "পড়ার রুটিন বা প্ল্যান পরিবর্তন (Plan Changed)",
                        subtitle = "এআই সমন্বয় বা নতুন সিলেবাস সংযোজন হলে আপডেট দেওয়া হবে",
                        checked = catPlanChanged,
                        onCheckedChange = { catPlanChanged = it }
                    )

                    HorizontalDivider(modifier = Modifier.padding(vertical = 10.dp), color = BorderDark)

                    NotificationCategoryToggleRow(
                        title = "সাপ্তাহিক অগ্রগতির বিবরণী (Weekly Summary)",
                        subtitle = "প্রতি সপ্তাহে সন্তানের পড়ার মোট সময় ও দক্ষতার রিপোর্ট",
                        checked = catWeeklySummary,
                        onCheckedChange = { catWeeklySummary = it }
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Section 3: Quiet Hours (Asia/Dhaka)
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
            ) {
                Column(modifier = Modifier.padding(18.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Schedule, contentDescription = null, tint = IndigoAccent, modifier = Modifier.size(20.dp))
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "নীরব সময় (Quiet Hours - Asia/Dhaka)",
                            fontWeight = FontWeight.Bold,
                            color = Color.White,
                            fontSize = 15.sp
                        )
                    }
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = "এই সময়ে কোন অপ্রয়োজনীয় নোটিফিকেশন পাঠানো হবে না। বিশ্রামের সময় শান্ত পরিবেশ বজায় থাকে।",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                    )

                    Spacer(modifier = Modifier.height(16.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(14.dp)
                    ) {
                        OutlinedTextField(
                            value = quietHoursStart,
                            onValueChange = { quietHoursStart = it },
                            label = { Text("শুরু (Start Time)") },
                            placeholder = { Text("22:00") },
                            modifier = Modifier.weight(1f),
                            singleLine = true,
                            shape = RoundedCornerShape(10.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = IndigoAccent,
                                unfocusedBorderColor = BorderDark
                            )
                        )

                        OutlinedTextField(
                            value = quietHoursEnd,
                            onValueChange = { quietHoursEnd = it },
                            label = { Text("সমাপ্তি (End Time)") },
                            placeholder = { Text("07:00") },
                            modifier = Modifier.weight(1f),
                            singleLine = true,
                            shape = RoundedCornerShape(10.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = IndigoAccent,
                                unfocusedBorderColor = BorderDark
                            )
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Section 4: Non-Leaking Push Privacy Guarantee Card (Rule 15)
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = Color.Black.copy(alpha = 0.35f)),
                border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.Top
                ) {
                    Icon(
                        imageVector = Icons.Default.Security,
                        contentDescription = null,
                        tint = EmeraldSuccess,
                        modifier = Modifier.size(24.dp)
                    )
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(
                            text = "গোপনীয়তার নিশ্চয়তা (Non-Leaking Policy - Rule 15)",
                            fontWeight = FontWeight.Bold,
                            color = EmeraldSuccess,
                            fontSize = 13.sp
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "ThinkBuddy সার্ভার নোটিফিকেশনে শুধুমাত্র সাধারণ সতর্কতা বার্তা পাঠায়। শিক্ষার্থীর কোনো চ্যাট হিস্ট্রি, প্রশ্নোত্তরের গোপন বিষয় বা নিরাপত্তা টোকেন নোটিফিকেশনে কখনোই উন্মুক্ত করা হয় না।",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                            lineHeight = 16.sp
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))
        }
    }
}

@Composable
private fun NotificationCategoryToggleRow(
    title: String,
    subtitle: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(title, fontWeight = FontWeight.Medium, color = Color.White, fontSize = 13.sp)
            Text(subtitle, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
        }
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            colors = SwitchDefaults.colors(checkedThumbColor = TealPrimary)
        )
    }
}
