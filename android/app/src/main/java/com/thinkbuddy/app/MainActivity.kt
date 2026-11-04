package com.thinkbuddy.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.Autorenew
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.EmojiEvents
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PersonAdd
import androidx.compose.material.icons.filled.PlayCircle
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.NavigationRailItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.windowsizeclass.ExperimentalMaterial3WindowSizeClassApi
import androidx.compose.material3.windowsizeclass.WindowWidthSizeClass
import androidx.compose.material3.windowsizeclass.calculateWindowSizeClass
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.thinkbuddy.app.core.network.PlannerTaskResponse
import com.thinkbuddy.app.core.storage.OfflinePlanCache
import com.thinkbuddy.app.ui.auth.AuthScreen
import com.thinkbuddy.app.ui.chat.ChatScreen
import com.thinkbuddy.app.ui.home.TodayScreen
import com.thinkbuddy.app.ui.parent.ChildLinkScreen
import com.thinkbuddy.app.ui.parent.ParentAiControlsScreen
import com.thinkbuddy.app.ui.parent.ParentDashboardScreen
import com.thinkbuddy.app.ui.parent.ParentNotificationSettingsScreen
import com.thinkbuddy.app.ui.parent.ParentQuizReviewScreen
import com.thinkbuddy.app.ui.parent.StudySetupEditorScreen
import com.thinkbuddy.app.ui.plan.PlanTimelineScreen
import com.thinkbuddy.app.ui.profile.ProfileScreen
import com.thinkbuddy.app.ui.progress.ProgressMasteryScreen
import com.thinkbuddy.app.ui.quiz.QuizActivity
import com.thinkbuddy.app.ui.revision.RevisionScreen
import com.thinkbuddy.app.ui.session.StudySessionScreen
import com.thinkbuddy.app.ui.task.TaskDetailScreen
import com.thinkbuddy.app.ui.theme.TealPrimary
import com.thinkbuddy.app.ui.theme.ThinkBuddyTheme

class MainActivity : ComponentActivity() {

    @OptIn(ExperimentalMaterial3WindowSizeClassApi::class)
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // API 36 Edge-to-edge enforcement
        enableEdgeToEdge()

        setContent {
            val windowSizeClass = calculateWindowSizeClass(this)
            val isTablet = windowSizeClass.widthSizeClass != WindowWidthSizeClass.Compact

            ThinkBuddyTheme {
                MainAppNavHost(
                    isTablet = isTablet,
                    onExit = { finish() }
                )
            }
        }
    }
}

enum class ScreenTab {
    // Student Tabs
    TODAY,
    PLAN,
    REVISION,
    CHAT,
    PROGRESS,
    SESSION,
    TASK_DETAIL,
    PROFILE,

    // Parent Tabs (Group 4)
    PARENT_DASHBOARD,
    STUDY_SETUP,
    PARENT_AI_CONTROLS,
    CHILD_LINK,
    NOTIFICATIONS,
    PARENT_QUIZ_REVIEW
}

@Composable
fun MainAppNavHost(
    isTablet: Boolean,
    onExit: () -> Unit
) {
    var isAuthenticated by remember { mutableStateOf(false) }
    var userRole by remember { mutableStateOf("student") }
    var currentTab by remember { mutableStateOf(ScreenTab.TODAY) }
    var selectedTask by remember { mutableStateOf<PlannerTaskResponse?>(null) }
    var selectedStudentId by remember { mutableStateOf<String?>("std-demo-1") }
    var selectedAttemptId by remember { mutableStateOf<String?>("att-demo-1") }

    // Predictive back navigation handling
    BackHandler(enabled = true) {
        if (!isAuthenticated) {
            onExit()
        } else if (userRole == "parent") {
            if (currentTab != ScreenTab.PARENT_DASHBOARD) {
                currentTab = ScreenTab.PARENT_DASHBOARD
            } else {
                onExit()
            }
        } else {
            if (currentTab == ScreenTab.TASK_DETAIL) {
                currentTab = ScreenTab.PLAN
            } else if (currentTab != ScreenTab.TODAY) {
                currentTab = ScreenTab.TODAY
            } else {
                onExit()
            }
        }
    }

    if (!isAuthenticated) {
        AuthScreen(
            onAuthSuccess = { role ->
                userRole = role
                isAuthenticated = true
                currentTab = if (role == "parent") ScreenTab.PARENT_DASHBOARD else ScreenTab.TODAY
            }
        )
        return
    }

    if (isTablet) {
        // Medium & Expanded screens: Left navigation rail + adaptive content
        Row(
            modifier = Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background)
        ) {
            NavigationRail(
                modifier = Modifier.fillMaxHeight(),
                containerColor = MaterialTheme.colorScheme.surface,
                contentColor = MaterialTheme.colorScheme.onSurface
            ) {
                if (userRole == "parent") {
                    // Parent Tablet Navigation Rail
                    NavigationRailItem(
                        selected = currentTab == ScreenTab.PARENT_DASHBOARD,
                        onClick = { currentTab = ScreenTab.PARENT_DASHBOARD },
                        icon = { Icon(Icons.Default.Dashboard, contentDescription = "ড্যাশবোর্ড") },
                        label = { Text("ড্যাশবোর্ড") },
                        colors = NavigationRailItemDefaults.colors(
                            selectedIconColor = TealPrimary,
                            selectedTextColor = TealPrimary
                        )
                    )
                    NavigationRailItem(
                        selected = currentTab == ScreenTab.STUDY_SETUP,
                        onClick = { currentTab = ScreenTab.STUDY_SETUP },
                        icon = { Icon(Icons.Default.Schedule, contentDescription = "সময়সূচী") },
                        label = { Text("সময়সূচী") },
                        colors = NavigationRailItemDefaults.colors(
                            selectedIconColor = TealPrimary,
                            selectedTextColor = TealPrimary
                        )
                    )
                    NavigationRailItem(
                        selected = currentTab == ScreenTab.PARENT_AI_CONTROLS,
                        onClick = { currentTab = ScreenTab.PARENT_AI_CONTROLS },
                        icon = { Icon(Icons.Default.CheckCircle, contentDescription = "এআই নিয়ন্ত্রণ") },
                        label = { Text("এআই নিয়ন্ত্রণ") },
                        colors = NavigationRailItemDefaults.colors(
                            selectedIconColor = TealPrimary,
                            selectedTextColor = TealPrimary
                        )
                    )
                    NavigationRailItem(
                        selected = currentTab == ScreenTab.CHILD_LINK,
                        onClick = { currentTab = ScreenTab.CHILD_LINK },
                        icon = { Icon(Icons.Default.PersonAdd, contentDescription = "সংযোগ") },
                        label = { Text("সংযোগ") },
                        colors = NavigationRailItemDefaults.colors(
                            selectedIconColor = TealPrimary,
                            selectedTextColor = TealPrimary
                        )
                    )
                    NavigationRailItem(
                        selected = currentTab == ScreenTab.NOTIFICATIONS,
                        onClick = { currentTab = ScreenTab.NOTIFICATIONS },
                        icon = { Icon(Icons.Default.Notifications, contentDescription = "বিজ্ঞপ্তি") },
                        label = { Text("বিজ্ঞপ্তি") },
                        colors = NavigationRailItemDefaults.colors(
                            selectedIconColor = TealPrimary,
                            selectedTextColor = TealPrimary
                        )
                    )
                    NavigationRailItem(
                        selected = currentTab == ScreenTab.PROFILE,
                        onClick = { currentTab = ScreenTab.PROFILE },
                        icon = { Icon(Icons.Default.Person, contentDescription = "প্রোফাইল") },
                        label = { Text("প্রোফাইল") },
                        colors = NavigationRailItemDefaults.colors(
                            selectedIconColor = TealPrimary,
                            selectedTextColor = TealPrimary
                        )
                    )
                } else {
                    // Student Tablet Navigation Rail
                    NavigationRailItem(
                        selected = currentTab == ScreenTab.TODAY,
                        onClick = { currentTab = ScreenTab.TODAY },
                        icon = { Icon(Icons.Default.DateRange, contentDescription = "আজকের লক্ষ্য (Today)") },
                        label = { Text("আজকে") },
                        colors = NavigationRailItemDefaults.colors(
                            selectedIconColor = TealPrimary,
                            selectedTextColor = TealPrimary
                        )
                    )
                    NavigationRailItem(
                        selected = currentTab == ScreenTab.PLAN || currentTab == ScreenTab.TASK_DETAIL,
                        onClick = { currentTab = ScreenTab.PLAN },
                        icon = { Icon(Icons.Default.CalendarMonth, contentDescription = "পরিকল্পনা (Plan)") },
                        label = { Text("প্ল্যান") },
                        colors = NavigationRailItemDefaults.colors(
                            selectedIconColor = TealPrimary,
                            selectedTextColor = TealPrimary
                        )
                    )
                    NavigationRailItem(
                        selected = currentTab == ScreenTab.REVISION,
                        onClick = { currentTab = ScreenTab.REVISION },
                        icon = { Icon(Icons.Default.Autorenew, contentDescription = "রিভিশন (Revision)") },
                        label = { Text("রিভিশন") },
                        colors = NavigationRailItemDefaults.colors(
                            selectedIconColor = TealPrimary,
                            selectedTextColor = TealPrimary
                        )
                    )
                    NavigationRailItem(
                        selected = currentTab == ScreenTab.CHAT,
                        onClick = { currentTab = ScreenTab.CHAT },
                        icon = { Icon(Icons.AutoMirrored.Filled.Chat, contentDescription = "এআই সহায়িকা (AI Chat)") },
                        label = { Text("সহায়িকা") },
                        colors = NavigationRailItemDefaults.colors(
                            selectedIconColor = TealPrimary,
                            selectedTextColor = TealPrimary
                        )
                    )
                    NavigationRailItem(
                        selected = currentTab == ScreenTab.PROGRESS,
                        onClick = { currentTab = ScreenTab.PROGRESS },
                        icon = { Icon(Icons.Default.EmojiEvents, contentDescription = "অগ্রগতি (Progress)") },
                        label = { Text("অগ্রগতি") },
                        colors = NavigationRailItemDefaults.colors(
                            selectedIconColor = TealPrimary,
                            selectedTextColor = TealPrimary
                        )
                    )
                    NavigationRailItem(
                        selected = currentTab == ScreenTab.PROFILE,
                        onClick = { currentTab = ScreenTab.PROFILE },
                        icon = { Icon(Icons.Default.Person, contentDescription = "প্রোফাইল (Profile)") },
                        label = { Text("প্রোফাইল") },
                        colors = NavigationRailItemDefaults.colors(
                            selectedIconColor = TealPrimary,
                            selectedTextColor = TealPrimary
                        )
                    )
                }
            }

            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxHeight()
            ) {
                TabContent(
                    tab = currentTab,
                    isTablet = true,
                    userRole = userRole,
                    selectedTask = selectedTask,
                    selectedStudentId = selectedStudentId,
                    selectedAttemptId = selectedAttemptId,
                    onNavigateToSession = { currentTab = ScreenTab.SESSION },
                    onNavigateToToday = { currentTab = ScreenTab.TODAY },
                    onNavigateToTaskDetail = { task ->
                        selectedTask = task
                        currentTab = ScreenTab.TASK_DETAIL
                    },
                    onNavigateToSetup = { stId ->
                        selectedStudentId = stId
                        currentTab = ScreenTab.STUDY_SETUP
                    },
                    onNavigateToAiControls = { stId ->
                        selectedStudentId = stId
                        currentTab = ScreenTab.PARENT_AI_CONTROLS
                    },
                    onNavigateToLinkChild = {
                        currentTab = ScreenTab.CHILD_LINK
                    },
                    onNavigateToNotifications = {
                        currentTab = ScreenTab.NOTIFICATIONS
                    },
                    onViewQuizReview = { attId ->
                        selectedAttemptId = attId
                        currentTab = ScreenTab.PARENT_QUIZ_REVIEW
                    },
                    onRoleSwitch = { newRole ->
                        userRole = newRole
                        currentTab = if (newRole == "parent") ScreenTab.PARENT_DASHBOARD else ScreenTab.TODAY
                    },
                    onLogout = {
                        OfflinePlanCache.clearCache(ThinkBuddyApp.instance)
                        ThinkBuddyApp.instance.tokenStorage.clear()
                        isAuthenticated = false
                    }
                )
            }
        }
    } else {
        // Compact screens (phones): Bottom navigation bar
        Scaffold(
            bottomBar = {
                NavigationBar(
                    containerColor = MaterialTheme.colorScheme.surface,
                    contentColor = MaterialTheme.colorScheme.onSurface
                ) {
                    if (userRole == "parent") {
                        // Parent Phone Navigation Bar
                        NavigationBarItem(
                            selected = currentTab == ScreenTab.PARENT_DASHBOARD,
                            onClick = { currentTab = ScreenTab.PARENT_DASHBOARD },
                            icon = { Icon(Icons.Default.Dashboard, contentDescription = "ড্যাশবোর্ড") },
                            label = { Text("ড্যাশবোর্ড") },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = TealPrimary,
                                selectedTextColor = TealPrimary
                            )
                        )
                        NavigationBarItem(
                            selected = currentTab == ScreenTab.STUDY_SETUP,
                            onClick = { currentTab = ScreenTab.STUDY_SETUP },
                            icon = { Icon(Icons.Default.Schedule, contentDescription = "সময়সূচী") },
                            label = { Text("সময়সূচী") },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = TealPrimary,
                                selectedTextColor = TealPrimary
                            )
                        )
                        NavigationBarItem(
                            selected = currentTab == ScreenTab.PARENT_AI_CONTROLS,
                            onClick = { currentTab = ScreenTab.PARENT_AI_CONTROLS },
                            icon = { Icon(Icons.Default.CheckCircle, contentDescription = "এআই") },
                            label = { Text("এআই") },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = TealPrimary,
                                selectedTextColor = TealPrimary
                            )
                        )
                        NavigationBarItem(
                            selected = currentTab == ScreenTab.CHILD_LINK,
                            onClick = { currentTab = ScreenTab.CHILD_LINK },
                            icon = { Icon(Icons.Default.PersonAdd, contentDescription = "সংযোগ") },
                            label = { Text("সংযোগ") },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = TealPrimary,
                                selectedTextColor = TealPrimary
                            )
                        )
                        NavigationBarItem(
                            selected = currentTab == ScreenTab.PROFILE,
                            onClick = { currentTab = ScreenTab.PROFILE },
                            icon = { Icon(Icons.Default.Person, contentDescription = "প্রোফাইল") },
                            label = { Text("প্রোফাইল") },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = TealPrimary,
                                selectedTextColor = TealPrimary
                            )
                        )
                    } else {
                        // Student Phone Navigation Bar
                        NavigationBarItem(
                            selected = currentTab == ScreenTab.TODAY,
                            onClick = { currentTab = ScreenTab.TODAY },
                            icon = { Icon(Icons.Default.DateRange, contentDescription = "আজকে") },
                            label = { Text("আজকে") },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = TealPrimary,
                                selectedTextColor = TealPrimary
                            )
                        )
                        NavigationBarItem(
                            selected = currentTab == ScreenTab.PLAN || currentTab == ScreenTab.TASK_DETAIL,
                            onClick = { currentTab = ScreenTab.PLAN },
                            icon = { Icon(Icons.Default.CalendarMonth, contentDescription = "পরিকল্পনা") },
                            label = { Text("প্ল্যান") },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = TealPrimary,
                                selectedTextColor = TealPrimary
                            )
                        )
                        NavigationBarItem(
                            selected = currentTab == ScreenTab.REVISION,
                            onClick = { currentTab = ScreenTab.REVISION },
                            icon = { Icon(Icons.Default.Autorenew, contentDescription = "রিভিশন") },
                            label = { Text("রিভিশন") },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = TealPrimary,
                                selectedTextColor = TealPrimary
                            )
                        )
                        NavigationBarItem(
                            selected = currentTab == ScreenTab.CHAT,
                            onClick = { currentTab = ScreenTab.CHAT },
                            icon = { Icon(Icons.AutoMirrored.Filled.Chat, contentDescription = "সহায়িকা") },
                            label = { Text("সহায়িকা") },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = TealPrimary,
                                selectedTextColor = TealPrimary
                            )
                        )
                        NavigationBarItem(
                            selected = currentTab == ScreenTab.PROGRESS,
                            onClick = { currentTab = ScreenTab.PROGRESS },
                            icon = { Icon(Icons.Default.EmojiEvents, contentDescription = "অগ্রগতি") },
                            label = { Text("অগ্রগতি") },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = TealPrimary,
                                selectedTextColor = TealPrimary
                            )
                        )
                        NavigationBarItem(
                            selected = currentTab == ScreenTab.PROFILE,
                            onClick = { currentTab = ScreenTab.PROFILE },
                            icon = { Icon(Icons.Default.Person, contentDescription = "প্রোফাইল") },
                            label = { Text("প্রোফাইল") },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = TealPrimary,
                                selectedTextColor = TealPrimary
                            )
                        )
                    }
                }
            }
        ) { innerPadding ->
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding)
            ) {
                TabContent(
                    tab = currentTab,
                    isTablet = false,
                    userRole = userRole,
                    selectedTask = selectedTask,
                    selectedStudentId = selectedStudentId,
                    selectedAttemptId = selectedAttemptId,
                    onNavigateToSession = { currentTab = ScreenTab.SESSION },
                    onNavigateToToday = { currentTab = ScreenTab.TODAY },
                    onNavigateToTaskDetail = { task ->
                        selectedTask = task
                        currentTab = ScreenTab.TASK_DETAIL
                    },
                    onNavigateToSetup = { stId ->
                        selectedStudentId = stId
                        currentTab = ScreenTab.STUDY_SETUP
                    },
                    onNavigateToAiControls = { stId ->
                        selectedStudentId = stId
                        currentTab = ScreenTab.PARENT_AI_CONTROLS
                    },
                    onNavigateToLinkChild = {
                        currentTab = ScreenTab.CHILD_LINK
                    },
                    onNavigateToNotifications = {
                        currentTab = ScreenTab.NOTIFICATIONS
                    },
                    onViewQuizReview = { attId ->
                        selectedAttemptId = attId
                        currentTab = ScreenTab.PARENT_QUIZ_REVIEW
                    },
                    onRoleSwitch = { newRole ->
                        userRole = newRole
                        currentTab = if (newRole == "parent") ScreenTab.PARENT_DASHBOARD else ScreenTab.TODAY
                    },
                    onLogout = {
                        OfflinePlanCache.clearCache(ThinkBuddyApp.instance)
                        ThinkBuddyApp.instance.tokenStorage.clear()
                        isAuthenticated = false
                    }
                )
            }
        }
    }
}

@Composable
fun TabContent(
    tab: ScreenTab,
    isTablet: Boolean,
    userRole: String,
    selectedTask: PlannerTaskResponse?,
    selectedStudentId: String?,
    selectedAttemptId: String?,
    onNavigateToSession: () -> Unit,
    onNavigateToToday: () -> Unit,
    onNavigateToTaskDetail: (PlannerTaskResponse) -> Unit,
    onNavigateToSetup: (studentId: String) -> Unit,
    onNavigateToAiControls: (studentId: String) -> Unit,
    onNavigateToLinkChild: () -> Unit,
    onNavigateToNotifications: () -> Unit,
    onViewQuizReview: (attemptId: String) -> Unit,
    onRoleSwitch: (newRole: String) -> Unit,
    onLogout: () -> Unit
) {
    val context = LocalContext.current

    when (tab) {
        ScreenTab.TODAY -> {
            TodayScreen(
                studentName = "শিক্ষার্থী",
                isTablet = isTablet,
                onStartSession = { _, _, _ -> onNavigateToSession() },
                onOpenAssessedQuiz = { quizId ->
                    QuizActivity.start(context, quizId, "assessed")
                },
                onLogout = onLogout
            )
        }
        ScreenTab.PLAN -> {
            PlanTimelineScreen(
                isTablet = isTablet,
                onSelectTask = onNavigateToTaskDetail,
                onStartTaskSession = { onNavigateToSession() }
            )
        }
        ScreenTab.TASK_DETAIL -> {
            TaskDetailScreen(
                task = selectedTask ?: PlannerTaskResponse(
                    id = "t-default",
                    subject = "অধ্যয়ন পাঠ",
                    estMinutes = 30,
                    refs = mapOf("printed_pages" to "–", "chapter_title" to "সাধারণ পাঠ")
                ),
                onBack = onNavigateToToday,
                onStartSession = { onNavigateToSession() }
            )
        }
        ScreenTab.REVISION -> {
            RevisionScreen(
                isTablet = isTablet,
                onStartRevision = { _ ->
                    QuizActivity.start(context, "quiz_revision_1", "practice")
                }
            )
        }
        ScreenTab.CHAT -> {
            ChatScreen(
                isTablet = isTablet
            )
        }
        ScreenTab.PROGRESS -> {
            ProgressMasteryScreen(
                isTablet = isTablet
            )
        }
        ScreenTab.SESSION -> {
            val sessionSubject = selectedTask?.subject ?: "অধ্যয়ন পাঠ"
            val sessionChapter = selectedTask?.refs?.get("chapter_title")?.toString() ?: selectedTask?.chapterId ?: "সাধারণ অধ্যায়"
            val sessionMins = selectedTask?.estMinutes ?: 30
            StudySessionScreen(
                subject = sessionSubject,
                chapter = sessionChapter,
                targetMins = sessionMins,
                onFinishSession = { _ -> onNavigateToToday() },
                onCancelSession = onNavigateToToday
            )
        }
        ScreenTab.PARENT_DASHBOARD -> {
            ParentDashboardScreen(
                isTablet = isTablet,
                onNavigateToSetup = onNavigateToSetup,
                onNavigateToAiControls = onNavigateToAiControls,
                onNavigateToLinkChild = onNavigateToLinkChild,
                onNavigateToNotifications = onNavigateToNotifications,
                onViewQuizReview = onViewQuizReview
            )
        }
        ScreenTab.STUDY_SETUP -> {
            StudySetupEditorScreen(
                studentId = selectedStudentId ?: "std-demo-1",
                onBack = { onNavigateToToday() }
            )
        }
        ScreenTab.PARENT_AI_CONTROLS -> {
            ParentAiControlsScreen(
                studentId = selectedStudentId ?: "std-demo-1",
                onBack = { onNavigateToToday() }
            )
        }
        ScreenTab.CHILD_LINK -> {
            ChildLinkScreen(
                onBack = { onNavigateToToday() },
                onNavigateToStudentRegistration = { _ ->
                    onRoleSwitch("student")
                    onLogout()
                }
            )
        }
        ScreenTab.NOTIFICATIONS -> {
            ParentNotificationSettingsScreen(
                onBack = { onNavigateToToday() }
            )
        }
        ScreenTab.PARENT_QUIZ_REVIEW -> {
            ParentQuizReviewScreen(
                attemptId = selectedAttemptId ?: "att-demo-1",
                onBack = { onNavigateToToday() }
            )
        }
        ScreenTab.PROFILE -> {
            ProfileScreen(
                userEmail = if (userRole == "parent") "parent@thinkbuddy.app" else "student@thinkbuddy.app",
                userRole = userRole,
                isParent = (userRole == "parent"),
                onRoleSwitch = onRoleSwitch,
                onLogout = onLogout
            )
        }
    }
}
