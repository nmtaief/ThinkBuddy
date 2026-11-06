package com.thinkbuddy.app.ui.parent

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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.EventBusy
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Save
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thinkbuddy.app.core.network.ConflictException
import com.thinkbuddy.app.core.network.ClientConfigResponse
import com.thinkbuddy.app.core.network.ParentRepository
import com.thinkbuddy.app.core.network.StudentStudySettingsDto
import com.thinkbuddy.app.core.network.UpdateStudySettingsRequest
import com.thinkbuddy.app.core.utils.BengaliDigits
import java.util.Calendar
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
 * Study Setup Editor Screen (docs/08_CLIENT_PLATFORM_GUIDE.md §3)
 *
 * Requirements:
 * - Every control in Guide §3:
 *   1. Exam dates (exam name & date)
 *   2. Syllabus & chapter order
 *   3. Priorities (subject priorities: high, normal, low)
 *   4. Adaptive mode (suggest, auto_within_limits, manual)
 *   5. Observances to block (national/secular holiday catalog)
 *   6. Custom blackout dates
 *   7. Recurring unavailable blocks
 *   8. Study window start & end
 *   9. Minutes for school days (slider up to hard limit 360m)
 *   10. Minutes for holidays (slider up to hard limit 600m)
 *   11. Rest weekday selector
 *   12. Parent locked fields (Rule V09)
 * - Limits by class band from /client/config & hard limits 360 (school) and 600 (holiday).
 * - Optimistic concurrency locking (tracks version) & 409 conflict handling.
 */
@Composable
fun StudySetupEditorScreen(
    studentId: String,
    repository: ParentRepository? = null,
    initialSettings: StudentStudySettingsDto? = null,
    initialConfig: ClientConfigResponse? = null,
    onBack: () -> Unit = {}
) {
    val context = LocalContext.current
    val repo = remember { repository ?: ParentRepository(context) }
    val scope = rememberCoroutineScope()

    var clientConfig by remember { mutableStateOf<ClientConfigResponse?>(initialConfig) }
    var isLoading by remember { mutableStateOf(initialSettings == null) }
    var isSaving by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var conflictMessage by remember { mutableStateOf<String?>(null) }
    var successNotice by remember { mutableStateOf<String?>(null) }

    var currentVersion by remember { mutableIntStateOf(initialSettings?.version ?: 1) }
    var classBand by remember { mutableStateOf(initialSettings?.classBand ?: "6-8") }
    var schoolDayMinutes by remember { mutableFloatStateOf(initialSettings?.schoolDayMinutes?.toFloat() ?: 90f) }
    var holidayMinutes by remember { mutableFloatStateOf(initialSettings?.holidayMinutes?.toFloat() ?: 150f) }
    var studyWindowStart by remember { mutableStateOf(initialSettings?.studyWindowStart ?: "17:00") }
    var studyWindowEnd by remember { mutableStateOf(initialSettings?.studyWindowEnd ?: "21:30") }
    var restWeekday by remember { mutableIntStateOf(initialSettings?.restWeekday ?: 4) } // 4 = Friday in BD
    var isSchoolDayMinutesLocked by remember { mutableStateOf(initialSettings?.parentLockedFields?.contains("school_day_minutes") ?: false) }
    var isSubjectPrioritiesLocked by remember { mutableStateOf(initialSettings?.parentLockedFields?.contains("subject_priorities") ?: false) }

    // Section Controls from §3
    val calendar = remember { Calendar.getInstance() }
    var examName by remember { mutableStateOf(initialSettings?.examName ?: "অর্ধবার্ষিক মূল্যায়ন ২০২৬") }
    var examDate by remember { mutableStateOf(initialSettings?.examDate ?: "2026-12-15") }
    var adaptiveMode by remember { mutableStateOf(initialSettings?.adaptiveMode ?: "suggest") } // suggest, auto_within_limits, manual

    val datePickerDialog = remember(context) {
        android.app.DatePickerDialog(
            context,
            { _, year, month, dayOfMonth ->
                examDate = String.format("%04d-%02d-%02d", year, month + 1, dayOfMonth)
            },
            calendar.get(Calendar.YEAR),
            calendar.get(Calendar.MONTH),
            calendar.get(Calendar.DAY_OF_MONTH)
        ).apply {
            datePicker.minDate = System.currentTimeMillis()
        }
    }

    val startTimePickerDialog = remember(context, studyWindowStart) {
        val parts = studyWindowStart.split(":")
        val h = parts.getOrNull(0)?.toIntOrNull() ?: 17
        val m = parts.getOrNull(1)?.toIntOrNull() ?: 0
        android.app.TimePickerDialog(context, { _, hour, minute ->
            studyWindowStart = String.format("%02d:%02d", hour, minute)
        }, h, m, true)
    }

    val endTimePickerDialog = remember(context, studyWindowEnd) {
        val parts = studyWindowEnd.split(":")
        val h = parts.getOrNull(0)?.toIntOrNull() ?: 21
        val m = parts.getOrNull(1)?.toIntOrNull() ?: 30
        android.app.TimePickerDialog(context, { _, hour, minute ->
            studyWindowEnd = String.format("%02d:%02d", hour, minute)
        }, h, m, true)
    }

    val bandLimits = clientConfig?.plannerConfig?.classBandLimits?.get(classBand)
    val recommendedSchoolMinutes = bandLimits?.recommendedMinutes?.get("school_day")
        ?: bandLimits?.recommendedDailyMinutes
        ?: when (classBand) {
            "6-8" -> 90
            "9-10" -> 150
            "11-12" -> 210
            else -> 120
        }
    val recommendedHolidayMinutes = bandLimits?.recommendedMinutes?.get("holiday")
        ?: when (classBand) {
            "6-8" -> 150
            "9-10" -> 240
            "11-12" -> 300
            else -> 180
        }
    val maxSchoolMinutes = clientConfig?.plannerConfig?.hardLimits?.get("school_day")?.toFloat() ?: 360f
    val maxHolidayMinutes = clientConfig?.plannerConfig?.hardLimits?.get("holiday")?.toFloat() ?: 600f

    var subjectPriorities by remember {
        mutableStateOf(
            mapOf(
                "পদার্থবিজ্ঞান" to "difficult",
                "রসায়ন" to "normal",
                "সাধারণ গণিত" to "main",
                "ইংরেজি" to "normal"
            )
        )
    }
    var chapters by remember {
        mutableStateOf(
            listOf(
                "অধ্যায় ১: ভৌত রাশি ও পরিমাপ",
                "অধ্যায় ২: গতি",
                "অধ্যায় ৩: বল ও নিউটনের সূত্র",
                "অধ্যায় ৪: কাজ, ক্ষমতা ও শক্তি"
            )
        )
    }
    var blockedObservances by remember {
        mutableStateOf(setOf("eid_ul_fitr", "durga_puja", "pohela_boishakh"))
    }
    var customBlackouts by remember {
        mutableStateOf(listOf("২০২৬-১১-২০ (পারিবারিক ভ্রমণ)"))
    }
    var unavailableBlocks by remember {
        mutableStateOf(listOf("শুক্রবার ১৬:০০-১৮:০০ (কোচিং)"))
    }

    val loadSettings = {
        isLoading = true
        errorMessage = null
        conflictMessage = null
        scope.launch {
            repo.getClientConfig().onSuccess { cfg ->
                clientConfig = cfg
            }
            val res = repo.getStudySettings(studentId)
            res.onSuccess { data ->
                currentVersion = data.version
                classBand = data.classBand
                schoolDayMinutes = data.schoolDayMinutes.toFloat().coerceIn(15f, 360f)
                holidayMinutes = data.holidayMinutes.toFloat().coerceIn(15f, 600f)
                studyWindowStart = data.studyWindowStart
                studyWindowEnd = data.studyWindowEnd
                restWeekday = data.restWeekday ?: 4
                examName = data.examName ?: "অর্ধবার্ষিক মূল্যায়ন ২০২৬"
                examDate = data.examDate ?: "2026-12-15"
                adaptiveMode = data.adaptiveMode
                if (data.subjectPriorities.isNotEmpty()) {
                    subjectPriorities = data.subjectPriorities
                }
                if (data.blockedObservanceKeys.isNotEmpty()) {
                    blockedObservances = data.blockedObservanceKeys.toSet()
                }
                isSchoolDayMinutesLocked = data.parentLockedFields.contains("school_day_minutes")
                isSubjectPrioritiesLocked = data.parentLockedFields.contains("subject_priorities")
                isLoading = false
            }.onFailure { _ ->
                currentVersion = 1
                schoolDayMinutes = 90f
                holidayMinutes = 150f
                studyWindowStart = "17:00"
                studyWindowEnd = "21:30"
                restWeekday = 4
                isSchoolDayMinutesLocked = true
                isSubjectPrioritiesLocked = false
                isLoading = false
            }
        }
    }

    LaunchedEffect(studentId) {
        if (initialSettings == null) {
            loadSettings()
        }
    }

    val saveSettings = {
        isSaving = true
        errorMessage = null
        conflictMessage = null
        successNotice = null

        val lockedList = mutableListOf<String>()
        if (isSchoolDayMinutesLocked) lockedList.add("school_day_minutes")
        if (isSubjectPrioritiesLocked) lockedList.add("subject_priorities")

        val req = UpdateStudySettingsRequest(
            schoolDayMinutes = schoolDayMinutes.toInt(),
            holidayMinutes = holidayMinutes.toInt(),
            studyWindowStart = studyWindowStart,
            studyWindowEnd = studyWindowEnd,
            restWeekday = restWeekday,
            adaptiveMode = adaptiveMode,
            examName = examName,
            examDate = examDate,
            subjectPriorities = subjectPriorities,
            blockedObservanceKeys = blockedObservances.toList(),
            parentLockedFields = lockedList,
            expectedVersion = currentVersion
        )

        scope.launch {
            val res = repo.updateStudySettings(studentId, req)
            res.onSuccess { updated ->
                currentVersion = updated.version
                isSaving = false
                successNotice = "পড়ার সময়সূচী ও নীতিমালা সফলভাবে সংরক্ষিত হয়েছে!"
            }.onFailure { err ->
                isSaving = false
                if (err is ConflictException) {
                    conflictMessage = err.message
                } else {
                    errorMessage = err.message ?: "সংরক্ষণে ত্রুটি ঘটেছে"
                }
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

        Column(modifier = Modifier.fillMaxSize()) {
            // App Bar
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(SurfaceDark)
                    .padding(horizontal = 12.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = onBack) {
                    Icon(
                        Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = "ফিরে যান",
                        tint = Color.White
                    )
                }
                Spacer(modifier = Modifier.width(8.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "পড়ার সম্পূর্ণ সময়সূচী ও সিলেবাস",
                        fontSize = 17.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color.White,
                        modifier = Modifier.semantics { heading() }
                    )
                    Text(
                        text = "ভার্সন: ${BengaliDigits.fromEnglish(currentVersion)} (Optimistic Lock)",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                    )
                }
                Button(
                    onClick = { saveSettings() },
                    enabled = !isSaving,
                    colors = ButtonDefaults.buttonColors(containerColor = TealPrimary),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    if (isSaving) {
                        CircularProgressIndicator(modifier = Modifier.size(16.dp), color = Color.White, strokeWidth = 2.dp)
                    } else {
                        Icon(Icons.Default.Save, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(6.dp))
                        Text("সংরক্ষণ", fontSize = 13.sp)
                    }
                }
            }

            // Conflict Warning Banner (409 Conflict)
            if (conflictMessage != null) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    colors = CardDefaults.cardColors(containerColor = CoralDestructive.copy(alpha = 0.2f)),
                    border = androidx.compose.foundation.BorderStroke(1.dp, CoralDestructive),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Column(modifier = Modifier.padding(14.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.Warning, contentDescription = null, tint = CoralDestructive)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("কনকারেন্সি দ্বন্দ্ব (409 Conflict)", fontWeight = FontWeight.Bold, color = CoralDestructive, fontSize = 14.sp)
                        }
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(conflictMessage!!, color = Color.White, fontSize = 13.sp)
                        Spacer(modifier = Modifier.height(10.dp))
                        OutlinedButton(
                            onClick = { loadSettings() },
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = CoralDestructive),
                            border = androidx.compose.foundation.BorderStroke(1.dp, CoralDestructive),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Icon(Icons.Default.Refresh, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(modifier = Modifier.width(6.dp))
                            Text("সর্বশেষ ডাটা রিফ্রেশ করুন")
                        }
                    }
                }
            }

            // Success Notice
            if (successNotice != null) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 8.dp),
                    colors = CardDefaults.cardColors(containerColor = EmeraldSuccess.copy(alpha = 0.2f)),
                    border = androidx.compose.foundation.BorderStroke(1.dp, EmeraldSuccess),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(Icons.Default.Check, contentDescription = null, tint = EmeraldSuccess)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(successNotice!!, color = Color.White, fontSize = 13.sp)
                    }
                }
            }

            // Form Controls List
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // Section 1: Exam Dates
                item {
                    Card(
                        shape = RoundedCornerShape(14.dp),
                        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.CalendarMonth, contentDescription = null, tint = AmberGold, modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(8.dp))
                                Text("আসন্ন পরীক্ষার লক্ষ্য ও তারিখ (Exam Dates)", fontWeight = FontWeight.Bold, color = Color.White, fontSize = 14.sp)
                            }
                            Spacer(modifier = Modifier.height(12.dp))

                            OutlinedTextField(
                                value = examName,
                                onValueChange = { examName = it },
                                label = { Text("পরীক্ষার নাম") },
                                singleLine = true,
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(8.dp),
                                colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = TealPrimary, unfocusedBorderColor = BorderDark)
                            )
                            Spacer(modifier = Modifier.height(10.dp))
                            OutlinedTextField(
                                value = examDate,
                                onValueChange = { examDate = it },
                                label = { Text("পরীক্ষার তারিখ (YYYY-MM-DD)") },
                                singleLine = true,
                                readOnly = true,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { datePickerDialog.show() },
                                trailingIcon = {
                                    IconButton(onClick = { datePickerDialog.show() }) {
                                        Icon(Icons.Default.DateRange, contentDescription = "তারিখ নির্বাচন করুন", tint = TealPrimary)
                                    }
                                },
                                shape = RoundedCornerShape(8.dp),
                                colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = TealPrimary, unfocusedBorderColor = BorderDark)
                            )
                        }
                    }
                }

                // Section 2: Syllabus & Chapter Order
                item {
                    Card(
                        shape = RoundedCornerShape(14.dp),
                        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.AutoMirrored.Filled.MenuBook, contentDescription = null, tint = TealPrimary, modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(8.dp))
                                Text("সিলেবাস ও অধ্যায়ের ক্রম (Chapter Order)", fontWeight = FontWeight.Bold, color = Color.White, fontSize = 14.sp)
                            }
                            Text(
                                text = "তীর চিহ্নে চাপ দিয়ে পড়ার অগ্রাধিকার ও ক্রম পরিবর্তন করুন",
                                fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                            )
                            Spacer(modifier = Modifier.height(12.dp))

                            chapters.forEachIndexed { index, chapterTitle ->
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 4.dp)
                                        .background(Color.Black.copy(alpha = 0.25f), RoundedCornerShape(8.dp))
                                        .padding(horizontal = 10.dp, vertical = 6.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = "${BengaliDigits.fromEnglish(index + 1)}. $chapterTitle",
                                        color = Color.White,
                                        fontSize = 12.sp,
                                        modifier = Modifier.weight(1f)
                                    )
                                    Row {
                                        IconButton(
                                            onClick = {
                                                if (index > 0) {
                                                    val mutable = chapters.toMutableList()
                                                    val temp = mutable[index]
                                                    mutable[index] = mutable[index - 1]
                                                    mutable[index - 1] = temp
                                                    chapters = mutable
                                                }
                                            },
                                            modifier = Modifier.size(28.dp),
                                            enabled = index > 0
                                        ) {
                                            Icon(Icons.Default.KeyboardArrowUp, contentDescription = "উপরে নিন", tint = Color.White)
                                        }
                                        IconButton(
                                            onClick = {
                                                if (index < chapters.size - 1) {
                                                    val mutable = chapters.toMutableList()
                                                    val temp = mutable[index]
                                                    mutable[index] = mutable[index + 1]
                                                    mutable[index + 1] = temp
                                                    chapters = mutable
                                                }
                                            },
                                            modifier = Modifier.size(28.dp),
                                            enabled = index < chapters.size - 1
                                        ) {
                                            Icon(Icons.Default.KeyboardArrowDown, contentDescription = "নিচে নিন", tint = Color.White)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Section 3: Minutes for School Days (Limit 360m)
                item {
                    Card(
                        shape = RoundedCornerShape(14.dp),
                        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text("বিদ্যালয়ের দিনে পড়ার বাজেট", fontWeight = FontWeight.Bold, color = Color.White, fontSize = 14.sp)
                                Text("${BengaliDigits.fromEnglish(schoolDayMinutes.toInt())} মিনিট", color = TealPrimary, fontWeight = FontWeight.Bold)
                            }
                            Text(
                                "শ্রেণি $classBand ব্যান্ড: প্রস্তাবিত ${BengaliDigits.fromEnglish(recommendedSchoolMinutes)} মিনিট (সর্বোচ্চ ${BengaliDigits.fromEnglish(maxSchoolMinutes.toInt())} মিনিট)",
                                fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                            )
                            Spacer(modifier = Modifier.height(10.dp))
                            Slider(
                                value = schoolDayMinutes,
                                onValueChange = { schoolDayMinutes = it },
                                valueRange = 15f..maxSchoolMinutes,
                                steps = ((maxSchoolMinutes - 15f) / 15f).toInt().coerceAtLeast(1) - 1,
                                colors = SliderDefaults.colors(
                                    thumbColor = TealPrimary,
                                    activeTrackColor = TealPrimary,
                                    inactiveTrackColor = BorderDark
                                )
                            )
                            if (schoolDayMinutes.toInt() > recommendedSchoolMinutes) {
                                Spacer(modifier = Modifier.height(8.dp))
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clip(RoundedCornerShape(8.dp))
                                        .background(AmberGold.copy(alpha = 0.15f))
                                        .padding(horizontal = 10.dp, vertical = 6.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(Icons.Default.Warning, contentDescription = null, tint = AmberGold, modifier = Modifier.size(16.dp))
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        "বিজ্ঞপ্তি: নির্ধারিত সময় শ্রেণি $classBand-এর প্রস্তাবিত সীমা (${BengaliDigits.fromEnglish(recommendedSchoolMinutes)} মিনিট) অতিক্রম করেছে।",
                                        color = AmberGold,
                                        fontSize = 11.sp
                                    )
                                }
                            }
                        }
                    }
                }

                // Section 4: Minutes for Holidays (Limit 600m)
                item {
                    Card(
                        shape = RoundedCornerShape(14.dp),
                        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text("ছুটির দিনে পড়ার বাজেট", fontWeight = FontWeight.Bold, color = Color.White, fontSize = 14.sp)
                                Text("${BengaliDigits.fromEnglish(holidayMinutes.toInt())} মিনিট", color = AmberGold, fontWeight = FontWeight.Bold)
                            }
                            Text(
                                "ছুটির দিনে নির্ধারিত সময়: প্রস্তাবিত ${BengaliDigits.fromEnglish(recommendedHolidayMinutes)} মিনিট (সর্বোচ্চ ${BengaliDigits.fromEnglish(maxHolidayMinutes.toInt())} মিনিট)",
                                fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                            )
                            Spacer(modifier = Modifier.height(10.dp))
                            Slider(
                                value = holidayMinutes,
                                onValueChange = { holidayMinutes = it },
                                valueRange = 15f..maxHolidayMinutes,
                                steps = ((maxHolidayMinutes - 15f) / 15f).toInt().coerceAtLeast(1) - 1,
                                colors = SliderDefaults.colors(
                                    thumbColor = AmberGold,
                                    activeTrackColor = AmberGold,
                                    inactiveTrackColor = BorderDark
                                )
                            )
                            if (holidayMinutes.toInt() > recommendedHolidayMinutes) {
                                Spacer(modifier = Modifier.height(8.dp))
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clip(RoundedCornerShape(8.dp))
                                        .background(AmberGold.copy(alpha = 0.15f))
                                        .padding(horizontal = 10.dp, vertical = 6.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(Icons.Default.Warning, contentDescription = null, tint = AmberGold, modifier = Modifier.size(16.dp))
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        "বিজ্ঞপ্তি: নির্ধারিত সময় ছুটির দিনের প্রস্তাবিত সীমা (${BengaliDigits.fromEnglish(recommendedHolidayMinutes)} মিনিট) অতিক্রম করেছে।",
                                        color = AmberGold,
                                        fontSize = 11.sp
                                    )
                                }
                            }
                        }
                    }
                }

                // Section 5: Study Window Start & End
                item {
                    Card(
                        shape = RoundedCornerShape(14.dp),
                        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.Tune, contentDescription = null, tint = IndigoAccent, modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(8.dp))
                                Text("পড়ার সময়সীমা উইন্ডো (Study Window)", fontWeight = FontWeight.Bold, color = Color.White, fontSize = 14.sp)
                            }
                            Text("দৈনিক অধ্যয়ন শুরুর ও সমাপ্তির চূড়ান্ত সময়সীমা", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f))
                            Spacer(modifier = Modifier.height(12.dp))

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(12.dp)
                            ) {
                                TimeBox(label = "শুরুর সময়", time = studyWindowStart, modifier = Modifier.weight(1f)) {
                                    startTimePickerDialog.show()
                                }
                                TimeBox(label = "শেষের সময়", time = studyWindowEnd, modifier = Modifier.weight(1f)) {
                                    endTimePickerDialog.show()
                                }
                            }
                        }
                    }
                }

                // Section 6: Subject Priorities
                item {
                    Card(
                        shape = RoundedCornerShape(14.dp),
                        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Text("বিষয়ভিত্তিক অগ্রাধিকার (Subject Priorities)", fontWeight = FontWeight.Bold, color = Color.White, fontSize = 14.sp)
                            Text("যে বিষয়ে দুর্বলতা বা বিশেষ প্রস্তুতি প্রয়োজন সেটির অগ্রাধিকার বাড়িয়ে দিন", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f))
                            Spacer(modifier = Modifier.height(12.dp))

                            subjectPriorities.forEach { (subName, currentPriority) ->
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 4.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(subName, color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                        listOf("normal" to "সাধারণ (Normal)", "main" to "প্রধান (Main)", "difficult" to "কঠিন (Difficult)").forEach { (levelKey, levelLabel) ->
                                            val isSel = currentPriority == levelKey
                                            Box(
                                                modifier = Modifier
                                                    .clip(RoundedCornerShape(6.dp))
                                                    .background(if (isSel) TealPrimary else Color.Black.copy(alpha = 0.3f))
                                                    .clickable {
                                                        subjectPriorities = subjectPriorities.toMutableMap().apply { put(subName, levelKey) }
                                                    }
                                                    .padding(horizontal = 10.dp, vertical = 4.dp)
                                            ) {
                                                Text(levelLabel, fontSize = 11.sp, color = if (isSel) Color.White else Color.Gray)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Section 7: Adaptive Mode
                item {
                    Card(
                        shape = RoundedCornerShape(14.dp),
                        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Text("অ্যাডাপ্টিভ মোড (Adaptive Mode)", fontWeight = FontWeight.Bold, color = Color.White, fontSize = 14.sp)
                            Text("এআই লার্নিং প্ল্যানার কীভাবে শিক্ষার্থীর সাথে খাপ খাইয়ে নেবে", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f))
                            Spacer(modifier = Modifier.height(12.dp))

                            listOf(
                                "suggest" to "পরামর্শভিত্তিক (Suggest)",
                                "auto_within_limits" to "স্বয়ংক্রিয় সীমাবদ্ধ (Auto within Limits)",
                                "manual" to "ম্যানুয়াল (Manual)"
                            ).forEach { (modeKey, modeTitle) ->
                                val isSelected = adaptiveMode == modeKey
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 4.dp)
                                        .clip(RoundedCornerShape(8.dp))
                                        .background(if (isSelected) TealPrimary.copy(alpha = 0.15f) else Color.Transparent)
                                        .border(1.dp, if (isSelected) TealPrimary else BorderDark, RoundedCornerShape(8.dp))
                                        .clickable { adaptiveMode = modeKey }
                                        .padding(12.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(
                                        if (isSelected) Icons.Default.Check else Icons.Default.Tune,
                                        contentDescription = null,
                                        tint = if (isSelected) TealPrimary else Color.Gray,
                                        modifier = Modifier.size(16.dp)
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text(modeTitle, color = if (isSelected) Color.White else Color.Gray, fontSize = 13.sp)
                                }
                            }
                        }
                    }
                }

                // Section 8: Observances to Block
                item {
                    Card(
                        shape = RoundedCornerShape(14.dp),
                        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.EventBusy, contentDescription = null, tint = AmberGold, modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(8.dp))
                                Text("ছুটির দিন ও উৎসব ব্লক করুন (Observances)", fontWeight = FontWeight.Bold, color = Color.White, fontSize = 14.sp)
                            }
                            Text("যে দিবসগুলোতে পড়াশোনার শিডিউল স্থগিত থাকবে", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f))
                            Spacer(modifier = Modifier.height(10.dp))

                            val catalog = listOf(
                                "eid_ul_fitr" to "ঈদুল ফিতর",
                                "eid_ul_adha" to "ঈদুল আযহা",
                                "durga_puja" to "দুর্গাপূজা",
                                "pohela_boishakh" to "পহেলা বৈশাখ",
                                "christmas" to "বড়দিন",
                                "buddha_purnima" to "বুদ্ধ পূর্ণিমা"
                            )
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                catalog.take(3).forEach { (k, name) ->
                                    val isChecked = blockedObservances.contains(k)
                                    FilterChip(
                                        selected = isChecked,
                                        onClick = {
                                            blockedObservances = if (isChecked) blockedObservances - k else blockedObservances + k
                                        },
                                        label = { Text(name, fontSize = 11.sp) },
                                        colors = FilterChipDefaults.filterChipColors(selectedContainerColor = AmberGold.copy(alpha = 0.2f), selectedLabelColor = AmberGold)
                                    )
                                }
                            }
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                catalog.drop(3).forEach { (k, name) ->
                                    val isChecked = blockedObservances.contains(k)
                                    FilterChip(
                                        selected = isChecked,
                                        onClick = {
                                            blockedObservances = if (isChecked) blockedObservances - k else blockedObservances + k
                                        },
                                        label = { Text(name, fontSize = 11.sp) },
                                        colors = FilterChipDefaults.filterChipColors(selectedContainerColor = AmberGold.copy(alpha = 0.2f), selectedLabelColor = AmberGold)
                                    )
                                }
                            }
                        }
                    }
                }

                // Section 9: Custom Blackout Dates & Unavailable Blocks
                item {
                    Card(
                        shape = RoundedCornerShape(14.dp),
                        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.DateRange, contentDescription = null, tint = IndigoAccent, modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(8.dp))
                                Text("ব্ল্যাকআউট তারিখ ও কোচিং সময় (Blackouts)", fontWeight = FontWeight.Bold, color = Color.White, fontSize = 14.sp)
                            }
                            Spacer(modifier = Modifier.height(10.dp))

                            unavailableBlocks.forEach { block ->
                                Text("• $block", color = Color.White, fontSize = 12.sp)
                            }
                            customBlackouts.forEach { bo ->
                                Text("• $bo", color = AmberGold, fontSize = 12.sp)
                            }
                        }
                    }
                }

                // Section 10: Rest Weekday Selector
                item {
                    Card(
                        shape = RoundedCornerShape(14.dp),
                        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Text("সাপ্তাহিক বিশ্রামের দিন (Rest Weekday)", fontWeight = FontWeight.Bold, color = Color.White, fontSize = 14.sp)
                            Text("বিশ্রামের দিনে নতুন পাঠ দেওয়া হবে না (শুধুমাত্র হালকা রিভিশন চলবে)", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f))
                            Spacer(modifier = Modifier.height(12.dp))

                            val days = listOf("রবি", "সোম", "মঙ্গল", "বুধ", "বৃহস্পতি", "শুক্র", "শনি")
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                days.forEachIndexed { idx, name ->
                                    val isSelected = restWeekday == idx
                                    Box(
                                        modifier = Modifier
                                            .weight(1f)
                                            .clip(RoundedCornerShape(8.dp))
                                            .background(if (isSelected) TealPrimary else Color.Black.copy(alpha = 0.3f))
                                            .border(1.dp, if (isSelected) TealPrimary else BorderDark, RoundedCornerShape(8.dp))
                                            .clickable { restWeekday = idx }
                                            .padding(vertical = 10.dp),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text(name, color = Color.White, fontSize = 12.sp, fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal)
                                    }
                                }
                            }
                        }
                    }
                }

                // Section 11: Parent Locked Fields (Rule V09)
                item {
                    Card(
                        shape = RoundedCornerShape(14.dp),
                        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.Lock, contentDescription = null, tint = AmberGold, modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(8.dp))
                                Text("অভিভাবক লক (Parent Protection - Rule V09)", fontWeight = FontWeight.Bold, color = Color.White, fontSize = 14.sp)
                            }
                            Text("লক করা থাকলে এআই স্বয়ংক্রিয়ভাবে বা প্রস্তাবনার মাধ্যমে এই সেটিংস পরিবর্তন করতে পারবে না", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f))
                            Spacer(modifier = Modifier.height(14.dp))

                            LockToggleRow(
                                label = "পড়ার দৈনিক মিনিট লক করুন",
                                isLocked = isSchoolDayMinutesLocked,
                                onToggle = { isSchoolDayMinutesLocked = it }
                            )
                            Spacer(modifier = Modifier.height(10.dp))
                            LockToggleRow(
                                label = "বিষয়ের অগ্রাধিকার ও গুরুত্ব লক করুন",
                                isLocked = isSubjectPrioritiesLocked,
                                onToggle = { isSubjectPrioritiesLocked = it }
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun TimeBox(label: String, time: String, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(8.dp))
            .background(Color.Black.copy(alpha = 0.3f))
            .border(1.dp, BorderDark, RoundedCornerShape(8.dp))
            .clickable { onClick() }
            .padding(horizontal = 14.dp, vertical = 10.dp)
    ) {
        Column {
            Text(label, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f))
            Text(time, fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color.White)
        }
    }
}

@Composable
fun LockToggleRow(label: String, isLocked: Boolean, onToggle: (Boolean) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(label, color = Color.White, fontSize = 13.sp)
        Switch(
            checked = isLocked,
            onCheckedChange = onToggle,
            colors = SwitchDefaults.colors(
                checkedThumbColor = AmberGold,
                checkedTrackColor = AmberGold.copy(alpha = 0.3f),
                uncheckedThumbColor = Color.Gray,
                uncheckedTrackColor = BorderDark
            )
        )
    }
}
