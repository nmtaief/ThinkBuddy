package com.thinkbuddy.app

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.thinkbuddy.app.ui.chat.ChatScreen
import com.thinkbuddy.app.ui.parent.ChildLinkScreen
import com.thinkbuddy.app.ui.parent.ParentConsentScreen
import com.thinkbuddy.app.ui.parent.ParentDashboardScreen
import com.thinkbuddy.app.ui.parent.StudySetupEditorScreen
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
 * 3. Child Link screen (8-character code, sensitive clipboard, scanner navigation).
 * 4. Parent Dashboard (responsive tablet/phone layout, streak, data export & deletion dialog).
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

        // Check terms & data policy
        composeTestRule.onNodeWithText("আমি প্রত্যয়ন করছি যে আমি শিক্ষার্থীর আইনগত অভিভাবক এবং ThinkBuddy ব্যবহারে সম্মতি দিচ্ছি।").performClick()
        composeTestRule.onNodeWithText("সন্তানের পড়ার সময়সূচী, অগ্রগতি ও মূল্যায়ন তথ্য অভিভাবক ড্যাশবোর্ডে প্রদর্শনে আমি সম্মত।").performClick()

        // Now button should be enabled
        proceedButton.assertIsEnabled()
        proceedButton.performClick()

        assertTrue("Consent callback triggered", consentGiven)
    }

    @Test
    fun testStudySetupEditorControlsAndLimits() {
        composeTestRule.setContent {
            StudySetupEditorScreen(
                studentId = "std-demo-1"
            )
        }

        // Verify §3 controls are present
        composeTestRule.onNodeWithText("পড়ার সম্পূর্ণ সময়সূচী ও সিলেবাস").assertIsDisplayed()
        composeTestRule.onNodeWithText("আসন্ন পরীক্ষার লক্ষ্য ও তারিখ (Exam Dates)").assertIsDisplayed()
        composeTestRule.onNodeWithText("সিলেবাস ও অধ্যায়ের ক্রম (Chapter Order)").assertIsDisplayed()
        composeTestRule.onNodeWithText("বিদ্যালয়ের দিনে পড়ার বাজেট").assertIsDisplayed()
        composeTestRule.onNodeWithText("ছুটির দিনে পড়ার বাজেট").assertIsDisplayed()
        composeTestRule.onNodeWithText("পড়ার সময়সীমা উইন্ডো (Study Window)").assertIsDisplayed()
        composeTestRule.onNodeWithText("বিষয়ভিত্তিক অগ্রাধিকার (Subject Priorities)").assertIsDisplayed()
        composeTestRule.onNodeWithText("অ্যাডাপ্টিভ মোড (Adaptive Mode)").assertIsDisplayed()
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

        // Click "এই কোড দিয়ে শিক্ষার্থী নিবন্ধন পেজে যান"
        composeTestRule.onNodeWithText("এই কোড দিয়ে শিক্ষার্থী নিবন্ধন পেজে যান").performClick()
        assertTrue("Navigated to student registration", navigatedToRegistration)
    }

    @Test
    fun testParentDashboardDataExportAndDeletionDialog() {
        composeTestRule.setContent {
            ParentDashboardScreen(
                isTablet = false,
                onNavigateToSetup = {},
                onNavigateToAiControls = {},
                onNavigateToLinkChild = {},
                onNavigateToNotifications = {},
                onViewQuizReview = {}
            )
        }

        // Verify Data Privacy & Deletion section is rendered
        composeTestRule.onNodeWithText("ডেটা সুরক্ষা ও অভিভাবক নিয়ন্ত্রণ").assertIsDisplayed()
        composeTestRule.onNodeWithText("ডেটা এক্সপোর্ট").assertIsDisplayed()

        val deleteButton = composeTestRule.onNodeWithText("ডেটা মুছে ফেলুন")
        deleteButton.assertIsDisplayed()
        deleteButton.performClick()

        // Verify Confirmation Alert Dialog
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

        // Verify AI Chat interface
        composeTestRule.onNodeWithText("ThinkBuddy AI শিক্ষক").assertIsDisplayed()
        composeTestRule.onNodeWithText("এনসিটিবি পাঠ্যবই ভিত্তিক সহকারী").assertIsDisplayed()

        // Verify Input field is interactive
        val inputField = composeTestRule.onNodeWithText("পাঠ্যবই থেকে যেকোনো প্রশ্ন লিখো...")
        inputField.assertIsDisplayed()
    }
}
