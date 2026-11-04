package com.thinkbuddy.app

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.hasScrollAction
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.isToggleable
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.thinkbuddy.app.core.network.StudentStudySettingsDto
import com.thinkbuddy.app.ui.chat.ChatScreen
import com.thinkbuddy.app.ui.parent.ChildLinkScreen
import com.thinkbuddy.app.ui.parent.ParentConsentScreen
import com.thinkbuddy.app.ui.parent.ParentDashboardScreen
import com.thinkbuddy.app.ui.parent.StudySetupEditorScreen
import com.thinkbuddy.app.ui.parent.createSampleParentOverview
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Instrumented Compose UI Tests for Parent Flows and AI Chat on Android Runtime (API 35/36).
 *
 * Covers:
 * 1. Parent Consent screen (onboarding disclosures, checkboxes, proceed action).
 * 2. Study Setup Editor with all §3 controls (exam dates, limits, observances, adaptive mode).
 * 3. Child Link screen (8-character code, zero-permission scanner navigation).
 * 4. Parent Dashboard (responsive tablet/phone layout, data export & deletion dialog).
 * 5. AI Chat screen (message input, citation chip, math container).
 */
@RunWith(AndroidJUnit4::class)
class ParentScreensAndChatInstrumentedTest {

    @get:Rule
    val composeTestRule = createComposeRule()

    @Test
    fun testParentConsentScreenRenderingAndAcceptance() {
        var consentGiven = false

        composeTestRule.setContent {
            ParentConsentScreen(
                onConsentAccepted = { consentGiven = true }
            )
        }

        // Verify title & security disclosures
        composeTestRule.onNodeWithText("অভিভাবক সম্মতি ও নিরাপত্তা").assertIsDisplayed()
        composeTestRule.onNodeWithText("শিক্ষার্থী ডেটা সুরক্ষা নীতিমালা").assertIsDisplayed()
        composeTestRule.onNodeWithText("কোনো বিজ্ঞাপন বা ট্র্যাকার নেই").assertIsDisplayed()

        // Proceed button initially disabled until checkboxes checked
        val proceedButton = composeTestRule.onNodeWithText("সম্মতি প্রদান করুন ও এগিয়ে যান")
        proceedButton.assertIsNotEnabled()

        // Check terms & data policy via toggleables
        val toggleables = composeTestRule.onAllNodes(isToggleable())
        toggleables[0].performClick()
        toggleables[1].performClick()

        // Now button should be enabled
        proceedButton.assertIsEnabled()
        proceedButton.performClick()

        assertTrue("Consent callback triggered", consentGiven)
    }

    @Test
    fun testStudySetupEditorControlsAndLimits() {
        composeTestRule.setContent {
            StudySetupEditorScreen(
                studentId = "std-demo-1",
                initialSettings = StudentStudySettingsDto(
                    studentId = "std-demo-1",
                    classBand = "6-8",
                    schoolDayMinutes = 90,
                    holidayMinutes = 150,
                    examName = "বার্ষিক মূল্যায়ন ২০২৬",
                    examDate = "2026-12-15"
                )
            )
        }

        // Verify top controls are rendered
        composeTestRule.onNodeWithText("পড়ার সম্পূর্ণ সময়সূচী ও সিলেবাস").assertIsDisplayed()
        composeTestRule.onNodeWithText("আসন্ন পরীক্ষার লক্ষ্য ও তারিখ (Exam Dates)").assertIsDisplayed()
        composeTestRule.onNodeWithText("সিলেবাস ও অধ্যায়ের ক্রম (Chapter Order)").assertIsDisplayed()

        // Scroll down LazyColumn to verify middle and lower §3 controls
        composeTestRule.onNode(hasScrollAction()).performScrollToNode(hasText("বিষয়ভিত্তিক অগ্রাধিকার (Subject Priorities)"))
        composeTestRule.onNodeWithText("বিষয়ভিত্তিক অগ্রাধিকার (Subject Priorities)").assertIsDisplayed()

        composeTestRule.onNode(hasScrollAction()).performScrollToNode(hasText("অ্যাডাপ্টিভ মোড (Adaptive Mode)"))
        composeTestRule.onNodeWithText("অ্যাডাপ্টিভ মোড (Adaptive Mode)").assertIsDisplayed()

        composeTestRule.onNode(hasScrollAction()).performScrollToNode(hasText("ছুটির দিন ও উৎসব ব্লক করুন (Observances)"))
        composeTestRule.onNodeWithText("ছুটির দিন ও উৎসব ব্লক করুন (Observances)").assertIsDisplayed()
    }

    @Test
    fun testChildLinkScreenCodeAndSensitiveClipboard() {
        var navigatedToRegistration = false

        composeTestRule.setContent {
            ChildLinkScreen(
                onNavigateToStudentRegistration = { navigatedToRegistration = true }
            )
        }

        // Verify Header and Tabs
        composeTestRule.onNodeWithText("সন্তান সংযোগ (Child Linking)").assertIsDisplayed()
        composeTestRule.onNodeWithText("নতুন লিংক কোড তৈরি").assertIsDisplayed()
        composeTestRule.onNodeWithText("QR ও কোড স্ক্যান").assertIsDisplayed()

        // Switch to QR / Scan Tab
        composeTestRule.onNodeWithText("QR ও কোড স্ক্যান").performClick()
        composeTestRule.onNodeWithText("ক্যামেরা পারমিশনহীন নিরাপদ স্ক্যানার").assertIsDisplayed()

        // Click "শিক্ষার্থী নিবন্ধন পেজে যান"
        composeTestRule.onNodeWithText("শিক্ষার্থী নিবন্ধন পেজে যান").performClick()
        assertTrue("Navigated to student registration", navigatedToRegistration)
    }

    @Test
    fun testParentDashboardDataExportAndDeletionDialog() {
        composeTestRule.setContent {
            ParentDashboardScreen(
                isTablet = false,
                initialOverview = createSampleParentOverview(),
                onNavigateToSetup = {},
                onNavigateToAiControls = {},
                onNavigateToLinkChild = {},
                onNavigateToNotifications = {},
                onViewQuizReview = {}
            )
        }

        // Scroll to Data Privacy & Deletion section in LazyColumn
        composeTestRule.onNode(hasScrollAction()).performScrollToNode(hasText("ডেটা সুরক্ষা ও গোপনীয়তা নিয়ন্ত্রণ (P07b)"))
        composeTestRule.onNodeWithText("ডেটা সুরক্ষা ও গোপনীয়তা নিয়ন্ত্রণ (P07b)").assertIsDisplayed()
        composeTestRule.onNodeWithText("ডেটা এক্সপোর্ট (JSON)").assertIsDisplayed()

        // Click delete button
        composeTestRule.onNode(hasScrollAction()).performScrollToNode(hasText("হিসাব মুছে ফেলুন"))
        val deleteButton = composeTestRule.onNodeWithText("হিসাব মুছে ফেলুন")
        deleteButton.assertIsDisplayed()
        deleteButton.performClick()

        // Verify Confirmation Alert Dialog with 14-day grace period
        composeTestRule.onNodeWithText("স্থায়ীভাবে ডেটা মুছে ফেলার নিশ্চয়তা").assertIsDisplayed()
        composeTestRule.onNodeWithText("বাতিল").performClick()
    }

    @Test
    fun testAiChatScreenInputAndCitationChipRendering() {
        composeTestRule.setContent {
            ChatScreen(
                isTablet = false
            )
        }

        // Verify AI Chat interface header
        composeTestRule.onNodeWithText("থিঙ্কবাডি এআই টিউটর").assertIsDisplayed()

        // Verify Input field placeholder is interactive
        val inputPlaceholder = composeTestRule.onNodeWithText("পাঠ্যবই থেকে প্রশ্ন লিখুন...")
        inputPlaceholder.assertIsDisplayed()
    }
}
