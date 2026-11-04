package com.thinkbuddy.app

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Instrumented Compose UI test executing on the Android runtime emulator.
 * Tests screen rendering, auth flow, and Today screen arrival.
 */
@RunWith(AndroidJUnit4::class)
class ComposeNavigationInstrumentedTest {

    @get:Rule
    val composeTestRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun testAppLaunchDisplaysAuthScreenAndCanNavigateToToday() {
        // Verify ThinkBuddy title and subtitle are displayed on launch
        composeTestRule.onNodeWithText("ThinkBuddy").assertIsDisplayed()
        composeTestRule.onNodeWithText("পড়াশোনার ব্যক্তিগত স্মার্ট প্ল্যাটফর্ম").assertIsDisplayed()

        // 1. Click "ওটিপি কোড পাঠান (Send OTP)" to reveal the verify button
        composeTestRule.onNodeWithText("ওটিপি কোড পাঠান (Send OTP)").performClick()

        // 2. Click "যাচাই ও প্রবেশ করুন (Verify & Sign In)" to execute login & token storage
        composeTestRule.onNodeWithText("যাচাই ও প্রবেশ করুন (Verify & Sign In)").performClick()

        // 3. Verify navigation to Today screen occurs (e.g. Navigation item or greeting)
        composeTestRule.waitUntil(timeoutMillis = 15000) {
            try {
                composeTestRule.onNodeWithText("আজকে").assertIsDisplayed()
                true
            } catch (e: Throwable) {
                false
            }
        }
        composeTestRule.onNodeWithText("আজকে").assertIsDisplayed()
    }
}
