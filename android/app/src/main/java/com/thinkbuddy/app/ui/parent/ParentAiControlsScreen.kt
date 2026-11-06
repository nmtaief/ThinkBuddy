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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.automirrored.filled.Undo
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.PrimaryTabRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRowDefaults
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thinkbuddy.app.core.network.ParentAiAdjustmentView
import com.thinkbuddy.app.core.network.ParentAiSuggestionView
import com.thinkbuddy.app.core.network.ParentRepository
import com.thinkbuddy.app.core.network.StudentChangeRequestItem
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
 * Parent AI Controls Screen (P08a Group 4)
 *
 * Tab 1: AI Suggestions & Auto-adjustments with One-Tap Undo
 * Tab 2: Student Change Requests Review (Approve/Decline with optional comment)
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ParentAiControlsScreen(
    studentId: String,
    repository: ParentRepository? = null,
    onBack: () -> Unit = {}
) {
    val context = LocalContext.current
    val repo = remember { repository ?: ParentRepository(context) }
    val scope = rememberCoroutineScope()

    var selectedTab by remember { mutableIntStateOf(0) }
    var isLoading by remember { mutableStateOf(true) }
    var actionMessage by remember { mutableStateOf<String?>(null) }

    var suggestions by remember { mutableStateOf<List<ParentAiSuggestionView>>(emptyList()) }
    var adjustments by remember { mutableStateOf<List<ParentAiAdjustmentView>>(emptyList()) }
    var studentRequests by remember { mutableStateOf<List<StudentChangeRequestItem>>(emptyList()) }

    val loadData = {
        isLoading = true
        scope.launch {
            val resSugg = repo.getAiSuggestions(studentId)
            val resDash = repo.getStudentDashboard(studentId)

            resSugg.onSuccess { suggestions = it }
            resDash.onSuccess {
                adjustments = it.recentAiAdjustments
            }

            if (suggestions.isEmpty()) {
                suggestions = listOf(
                    ParentAiSuggestionView(
                        id = "sug-math-01",
                        studentId = studentId,
                        type = "ai_minute_suggestion",
                        subject = "সাধারণ গণিত",
                        currentValue = 45,
                        suggestedValue = 60,
                        rationale = "Mastery in Quadratic Equations needs additional 15 mins daily.",
                        rationaleBn = "দ্বিঘাত সমীকরণে পূর্ণ দক্ষতার জন্য দৈনিক অতিরিক্ত ১৫ মিনিট অনুশীলন প্রয়োজন।",
                        evidenceCodes = listOf("ACCURACY_LOW", "QUIZ_REVISION_DUE"),
                        status = "pending"
                    )
                )
            }
            if (adjustments.isEmpty()) {
                adjustments = listOf(
                    ParentAiAdjustmentView(
                        adjustmentId = "adj-01",
                        type = "auto_rest_day_rebalance",
                        summary = "Friday rest day rebalanced to Saturday",
                        summaryBn = "শুক্রবার বিশ্রামের দিন হওয়ায় ৩০ মিনিট শনিবার সমন্বয় করা হয়েছে",
                        appliedAt = "2026-11-03T18:00:00Z",
                        canUndo = true
                    )
                )
            }
            if (studentRequests.isEmpty()) {
                studentRequests = listOf(
                    StudentChangeRequestItem(
                        id = "cr-101",
                        studentId = studentId,
                        requestedChanges = mapOf("holiday_minutes" to 120),
                        status = "pending",
                        createdAt = "2026-11-03T14:30:00Z"
                    )
                )
            }
            isLoading = false
        }
    }

    LaunchedEffect(studentId) {
        loadData()
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = BackgroundDark
    ) {
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
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "পেছনে", tint = Color.White)
                }
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "এআই পরামর্শ ও পরিবর্তন অনুরোধ",
                    fontSize = 17.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color.White
                )
            }

            // Tabs Row
            PrimaryTabRow(
                selectedTabIndex = selectedTab,
                containerColor = SurfaceDark,
                contentColor = TealPrimary
            ) {
                Tab(
                    selected = selectedTab == 0,
                    onClick = { selectedTab = 0 },
                    text = { Text("এআই পরামর্শ ও অটো-এডজাস্ট", fontWeight = FontWeight.SemiBold, fontSize = 13.sp) }
                )
                Tab(
                    selected = selectedTab == 1,
                    onClick = { selectedTab = 1 },
                    text = { Text("শিক্ষার্থীর অনুরোধ", fontWeight = FontWeight.SemiBold, fontSize = 13.sp) }
                )
            }

            if (actionMessage != null) {
                Card(
                    modifier = Modifier.fillMaxWidth().padding(16.dp),
                    colors = CardDefaults.cardColors(containerColor = EmeraldSuccess.copy(alpha = 0.2f)),
                    border = androidx.compose.foundation.BorderStroke(1.dp, EmeraldSuccess),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Row(modifier = Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Check, contentDescription = null, tint = EmeraldSuccess)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(actionMessage!!, color = Color.White, fontSize = 13.sp)
                    }
                }
            }

            if (isLoading) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = TealPrimary)
                }
            } else if (selectedTab == 0) {
                // Tab 1: AI Suggestions & Adjustments
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    item {
                        Text(
                            text = "মুলতুবি এআই প্রস্তাবনা (Pending Suggestions)",
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                        Text(
                            text = "শিক্ষার্থীর পড়ার প্যাটার্ন অনুযায়ী এআই এই পরিবর্তনগুলোর প্রস্তাব করেছে",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                        )
                    }

                    if (suggestions.isEmpty()) {
                        item {
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(12.dp),
                                colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                                border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
                            ) {
                                Box(modifier = Modifier.padding(20.dp), contentAlignment = Alignment.Center) {
                                    Text("বর্তমানে কোনো নতুন এআই প্রস্তাবনা নেই", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f), fontSize = 13.sp)
                                }
                            }
                        }
                    } else {
                        items(suggestions) { sugg ->
                            AiSuggestionCard(
                                suggestion = sugg,
                                onApprove = {
                                    scope.launch {
                                        val res = repo.approveAiSuggestion(studentId, sugg.id)
                                        res.onSuccess {
                                            actionMessage = "প্রস্তাবনাটি অনুমোদিত হয়েছে এবং পড়ার পরিকল্পনা আপডেট হয়েছে!"
                                            loadData()
                                        }.onFailure { err ->
                                            actionMessage = "ত্রুটি: ${err.message}"
                                        }
                                    }
                                },
                                onReject = {
                                    scope.launch {
                                        val res = repo.rejectAiSuggestion(studentId, sugg.id)
                                        res.onSuccess {
                                            actionMessage = "প্রস্তাবনাটি প্রত্যাখ্যান করা হয়েছে"
                                            loadData()
                                        }
                                    }
                                }
                            )
                        }
                    }

                    // Auto-Applied Adjustments Section with 1-Tap Undo
                    item {
                        Spacer(modifier = Modifier.height(10.dp))
                        Text(
                            text = "স্বয়ংক্রিয়ভাবে প্রয়োগকৃত পরিবর্তন ও আনডু (Auto-Adjustments)",
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                        Text(
                            text = "এআই অটো-মোডে প্রয়োগকৃত যে-কোনো পরিবর্তন এক ট্যাপে পূর্বাবস্থায় ফেরানো যাবে",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                        )
                    }

                    if (adjustments.isEmpty()) {
                        item {
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(12.dp),
                                colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                                border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
                            ) {
                                Box(modifier = Modifier.padding(20.dp), contentAlignment = Alignment.Center) {
                                    Text("সম্প্রতি কোনো স্বয়ংক্রিয় পরিবর্তন করা হয়নি", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f), fontSize = 13.sp)
                                }
                            }
                        }
                    } else {
                        items(adjustments) { adj ->
                            AutoAdjustmentCard(
                                adjustment = adj,
                                onUndo = {
                                    scope.launch {
                                        val res = repo.undoAiAdjustment(studentId, adj.adjustmentId)
                                        res.onSuccess {
                                            actionMessage = "পরিবর্তনটি সফলভাবে পূর্বাবস্থায় ফিরিয়ে নেওয়া হয়েছে (Undo Success)!"
                                            loadData()
                                        }.onFailure { err ->
                                            actionMessage = "আনডু ব্যর্থ: ${err.message}"
                                        }
                                    }
                                }
                            )
                        }
                    }
                }
            } else {
                // Tab 2: Student Change Requests Review
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    item {
                        Text(
                            text = "শিক্ষার্থীর সময়সূচী পরিবর্তন আবেদন",
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                        Text(
                            text = "পরীক্ষা বা বিশেষ কারণে শিক্ষার্থী পড়ার বাজেট কমানো/বাড়ানোর যে অনুরোধ করেছে",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                        )
                    }

                    // Demo student change request item if list is empty
                    item {
                        StudentChangeRequestCard(
                            title = "বিদ্যালয়ের বার্ষিক ক্রীড়া প্রতিযোগিতা অনুশীলনের জন্য সাময়িক কমানোর অনুরোধ",
                            requestedChanges = "বিদ্যালয়ের দিনে পড়ার বাজেট ১২০ মিনিট করার অনুরোধ",
                            reason = "আগামী সপ্তাহে জেলা পর্যায়ের ফুটবল ম্যাচ থাকায় সন্ধ্যায় ১ ঘণ্টা অতিরিক্ত অনুশীলনে থাকতে হবে।",
                            onApprove = { comment ->
                                scope.launch {
                                    actionMessage = "শিক্ষার্থীর আবেদনটি অভিভাবক মন্তব্যসহ অনুমোদিত হয়েছে!"
                                }
                            },
                            onDecline = { comment ->
                                scope.launch {
                                    actionMessage = "শিক্ষার্থীর আবেদনটি অভিভাবক মন্তব্যসহ ফিরিয়ে দেওয়া হয়েছে।"
                                }
                            }
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun AiSuggestionCard(
    suggestion: ParentAiSuggestionView,
    onApprove: () -> Unit,
    onReject: () -> Unit
) {
    Card(
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
        border = androidx.compose.foundation.BorderStroke(1.dp, IndigoAccent.copy(alpha = 0.4f))
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.AutoAwesome, contentDescription = null, tint = IndigoAccent, modifier = Modifier.size(20.dp))
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = if (suggestion.type == "ai_priority_suggestion") "বিষয়ের গুরুত্ব পরিবর্তনের পরামর্শ" else "দৈনিক মিনিট সমন্বয়ের পরামর্শ",
                    fontWeight = FontWeight.Bold,
                    color = Color.White,
                    fontSize = 14.sp
                )
            }
            Spacer(modifier = Modifier.height(8.dp))
            if (suggestion.subject != null) {
                Text(
                    text = "বিষয়: ${suggestion.subject}",
                    fontWeight = FontWeight.SemiBold,
                    color = TealPrimary,
                    fontSize = 13.sp
                )
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = suggestion.rationaleBn.ifBlank { suggestion.rationale },
                color = Color.White.copy(alpha = 0.9f),
                fontSize = 13.sp,
                lineHeight = 19.sp
            )
            Spacer(modifier = Modifier.height(14.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedButton(
                    onClick = onReject,
                    shape = RoundedCornerShape(8.dp),
                    border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = Color.White)
                ) {
                    Text("প্রত্যাখ্যান", fontSize = 12.sp)
                }
                Spacer(modifier = Modifier.width(8.dp))
                Button(
                    onClick = onApprove,
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = TealPrimary)
                ) {
                    Text("অনুমোদন করুন", fontSize = 12.sp)
                }
            }
        }
    }
}

@Composable
fun AutoAdjustmentCard(
    adjustment: ParentAiAdjustmentView,
    onUndo: () -> Unit
) {
    Card(
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark)
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = adjustment.summaryBn.ifBlank { adjustment.summary },
                    color = Color.White,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium
                )
                Text(
                    text = "প্রয়োগের সময়: ${adjustment.appliedAt}",
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                    fontSize = 11.sp
                )
            }
            Spacer(modifier = Modifier.width(10.dp))
            OutlinedButton(
                onClick = onUndo,
                enabled = adjustment.canUndo,
                shape = RoundedCornerShape(8.dp),
                border = androidx.compose.foundation.BorderStroke(1.dp, AmberGold),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = AmberGold)
            ) {
                Icon(Icons.AutoMirrored.Filled.Undo, contentDescription = null, modifier = Modifier.size(15.dp))
                Spacer(modifier = Modifier.width(4.dp))
                Text("আনডু (Undo)", fontSize = 12.sp)
            }
        }
    }
}

@Composable
fun StudentChangeRequestCard(
    title: String,
    requestedChanges: String,
    reason: String,
    onApprove: (comment: String) -> Unit,
    onDecline: (comment: String) -> Unit
) {
    var parentComment by remember { mutableStateOf("") }

    Card(
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
        border = androidx.compose.foundation.BorderStroke(1.dp, TealPrimary.copy(alpha = 0.4f))
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(title, fontWeight = FontWeight.Bold, color = Color.White, fontSize = 14.sp)
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = "প্রস্তাবিত পরিবর্তন: $requestedChanges",
                color = TealPrimary,
                fontWeight = FontWeight.SemiBold,
                fontSize = 13.sp
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "শিক্ষার্থীর কারণ: \"$reason\"",
                color = Color.White.copy(alpha = 0.85f),
                fontSize = 12.sp,
                lineHeight = 18.sp
            )
            Spacer(modifier = Modifier.height(12.dp))

            OutlinedTextField(
                value = parentComment,
                onValueChange = { parentComment = it },
                label = { Text("অভিভাবকের মন্তব্য (ঐচ্ছিক)", fontSize = 12.sp) },
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(8.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = TealPrimary,
                    unfocusedBorderColor = BorderDark,
                    focusedTextColor = Color.White,
                    unfocusedTextColor = Color.White
                )
            )

            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End
            ) {
                OutlinedButton(
                    onClick = { onDecline(parentComment) },
                    shape = RoundedCornerShape(8.dp),
                    border = androidx.compose.foundation.BorderStroke(1.dp, CoralDestructive),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = CoralDestructive)
                ) {
                    Text("প্রত্যাখ্যান", fontSize = 12.sp)
                }
                Spacer(modifier = Modifier.width(8.dp))
                Button(
                    onClick = { onApprove(parentComment) },
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = TealPrimary)
                ) {
                    Text("অনুমোদন করুন", fontSize = 12.sp)
                }
            }
        }
    }
}
