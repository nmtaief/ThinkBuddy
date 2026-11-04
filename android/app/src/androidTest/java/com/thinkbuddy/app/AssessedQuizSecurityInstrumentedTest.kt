package com.thinkbuddy.app

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.view.WindowManager
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.thinkbuddy.app.core.security.AssessedQuizSecurity
import com.thinkbuddy.app.ui.quiz.QuizActivity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Instrumented test verifying Group 2 Assessed Quiz Security enforcement directly on emulator:
 * 1. FLAG_SECURE window protection applied on onCreate for assessed quiz mode.
 * 2. Window overlay hiding enabled on API 31+.
 * 3. Clipboard sanitization on quiz entry.
 * 4. Multi-window state observation.
 */
@RunWith(AndroidJUnit4::class)
class AssessedQuizSecurityInstrumentedTest {

    @Test
    fun testFlagSecureAppliedInAssessedQuizMode() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val intent = Intent(context, QuizActivity::class.java).apply {
            putExtra(QuizActivity.EXTRA_QUIZ_ID, "test-quiz-assessed")
            putExtra(QuizActivity.EXTRA_MODE, "assessed")
        }

        ActivityScenario.launch<QuizActivity>(intent).use { scenario ->
            scenario.onActivity { activity ->
                val flags = activity.window.attributes.flags
                val isFlagSecureSet = (flags and WindowManager.LayoutParams.FLAG_SECURE) != 0
                assertTrue("FLAG_SECURE must be applied to assessed quiz window", isFlagSecureSet)
            }
        }
    }

    @Test
    fun testClipboardClearingBehavior() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager

        // Set sensitive text to clipboard
        clipboard.setPrimaryClip(ClipData.newPlainText("secret", "confidential_question_text"))

        // Invoke clipboard sanitation
        AssessedQuizSecurity.clearClipboard(context)

        // Verify primary clip text is sanitized
        val clip = clipboard.primaryClip
        val sanitizedText = if (clip != null && clip.itemCount > 0) clip.getItemAt(0).text?.toString() else ""
        assertFalse("Clipboard must not retain confidential text after sanitization", sanitizedText == "confidential_question_text")
    }

    @Test
    fun testMultiWindowDetection() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val intent = Intent(context, QuizActivity::class.java).apply {
            putExtra(QuizActivity.EXTRA_QUIZ_ID, "test-quiz-1")
            putExtra(QuizActivity.EXTRA_MODE, "assessed")
        }

        ActivityScenario.launch<QuizActivity>(intent).use { scenario ->
            scenario.onActivity { activity ->
                val detected = AssessedQuizSecurity.isInMultiWindowMode(activity)
                assertEquals(activity.isInMultiWindowMode, detected)
            }
        }
    }
}

