package com.thinkbuddy.app.ui.quiz

import android.app.Activity
import android.app.assist.AssistContent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import com.thinkbuddy.app.core.network.ApiClient
import com.thinkbuddy.app.core.network.AttemptEventRequest
import com.thinkbuddy.app.core.security.AssessedQuizSecurity
import com.thinkbuddy.app.ui.theme.ThinkBuddyTheme
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.util.function.Consumer

/**
 * Dedicated Quiz Activity for Practice and Assessed Quizzes (Group 2):
 * - Rule 18 & docs/05_SECURE_QUIZ.md strictly enforced.
 * - FLAG_SECURE applied in onCreate before content is drawn; cleared on exit.
 * - android:excludeFromRecents="true" configured in AndroidManifest.
 * - Window overlay hiding enabled (API 31+).
 * - Screenshot and screen-recording callbacks reported to backend.
 * - Multi-window & floating/freeform bounds detection and pause policy.
 * - Assist data blocked (onProvideAssistData / onProvideAssistContent zeroed).
 * - Non-system accessibility services reported as low-weight telemetry only (assistive tech remains usable).
 * - Clipboard cleared on entry, pause, and exit.
 * - onSaveInstanceState explicitly saves ONLY attempt ID, zero question text!
 */
class QuizActivity : ComponentActivity() {

    companion object {
        const val EXTRA_QUIZ_ID = "extra_quiz_id"
        const val EXTRA_MODE = "extra_mode" // "practice" or "assessed"
        const val EXTRA_ATTEMPT_ID = "extra_attempt_id"

        fun start(context: Context, quizId: String, mode: String = "assessed", attemptId: String? = null) {
            val intent = Intent(context, QuizActivity::class.java).apply {
                putExtra(EXTRA_QUIZ_ID, quizId)
                putExtra(EXTRA_MODE, mode)
                attemptId?.let { putExtra(EXTRA_ATTEMPT_ID, it) }
            }
            context.startActivity(intent)
        }
    }

    private var quizId: String = ""
    private var mode: String = "assessed"
    private var activeAttemptId: String? = null

    private var screenshotCallback: Activity.ScreenCaptureCallback? = null
    private var screenRecordingConsumer: Consumer<Int>? = null

    private var isMultiWindowActive by mutableStateOf(false)
    private var showExitConfirmDialog by mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        quizId = intent.getStringExtra(EXTRA_QUIZ_ID) ?: "quiz_1"
        mode = intent.getStringExtra(EXTRA_MODE) ?: "assessed"
        activeAttemptId = intent.getStringExtra(EXTRA_ATTEMPT_ID) ?: savedInstanceState?.getString("saved_attempt_id")

        // 1. Apply FLAG_SECURE before content is drawn (Assessed and high-trust quizzes)
        if (mode == "assessed") {
            AssessedQuizSecurity.enableScreenProtection(this)
            AssessedQuizSecurity.hideOverlayWindows(this)
        }

        // 2. Clear clipboard on entry
        AssessedQuizSecurity.clearClipboard(this)

        // 3. Handle Predictive Back and exit confirmation
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                showExitConfirmDialog = true
            }
        })

        setContent {
            ThinkBuddyTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    QuizScreen(
                        quizId = quizId,
                        mode = mode,
                        initialAttemptId = activeAttemptId,
                        isMultiWindow = isMultiWindowActive,
                        showExitDialog = showExitConfirmDialog,
                        onDismissExitDialog = { showExitConfirmDialog = false },
                        onConfirmExit = { finish() },
                        onAttemptActivated = { attemptId ->
                            activeAttemptId = attemptId
                        },
                        onFinishQuiz = {
                            finish()
                        }
                    )
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        // Clipboard sanitization on return
        AssessedQuizSecurity.clearClipboard(this)

        // Check Multi-window & Floating / Windowed bounds mode
        val windowRestricted = AssessedQuizSecurity.isFloatingOrWindowedMode(this)
        isMultiWindowActive = windowRestricted
        if (windowRestricted && mode == "assessed") {
            reportSecurityEvent("multi_window", mapOf("in_multi_window" to true, "policy" to "pause"))
        }

        // Report non-system accessibility services as low-weight telemetry signal only
        if (mode == "assessed") {
            val nonSystemServices = AssessedQuizSecurity.checkNonSystemAccessibilityServices(this)
            if (nonSystemServices.isNotEmpty()) {
                reportSecurityEvent(
                    "accessibility_service_detected",
                    mapOf("non_system_services" to nonSystemServices, "weight" to 0.05)
                )
            }
        }

        // Register screenshot callback (API 34+)
        if (mode == "assessed" && screenshotCallback == null) {
            screenshotCallback = AssessedQuizSecurity.registerScreenshotCallback(this) {
                reportSecurityEvent("screenshot", mapOf("timestamp" to System.currentTimeMillis()))
            }
        }

        // Register screen recording callback (API 35+)
        if (mode == "assessed" && screenRecordingConsumer == null) {
            screenRecordingConsumer = AssessedQuizSecurity.registerScreenRecordingCallback(this) { isRecording ->
                if (isRecording) {
                    reportSecurityEvent("screen_recording", mapOf("active" to true))
                }
            }
        }
    }

    override fun onPause() {
        super.onPause()
        // Clear clipboard when pausing to prevent question leaking
        AssessedQuizSecurity.clearClipboard(this)

        if (mode == "assessed") {
            reportSecurityEvent("background", mapOf("timestamp" to System.currentTimeMillis()))
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        // Unregister callbacks
        AssessedQuizSecurity.unregisterScreenshotCallback(this, screenshotCallback)
        AssessedQuizSecurity.unregisterScreenRecordingCallback(this, screenRecordingConsumer)

        // Clear FLAG_SECURE
        if (mode == "assessed") {
            AssessedQuizSecurity.disableScreenProtection(this)
        }
        AssessedQuizSecurity.clearClipboard(this)
    }

    @Deprecated("Deprecated in Java", ReplaceWith("onMultiWindowModeChanged(isInMultiWindowMode, newConfig)"))
    @Suppress("DEPRECATION")
    override fun onMultiWindowModeChanged(isInMultiWindowMode: Boolean) {
        super.onMultiWindowModeChanged(isInMultiWindowMode)
        isMultiWindowActive = isInMultiWindowMode || AssessedQuizSecurity.isFloatingOrWindowedMode(this)
        if (isMultiWindowActive && mode == "assessed") {
            reportSecurityEvent("multi_window", mapOf("in_multi_window" to true, "policy" to "pause"))
        }
    }

    /**
     * Requirement (5): Block assist data on quiz views.
     */
    override fun onProvideAssistData(data: Bundle?) {
        super.onProvideAssistData(data)
        if (mode == "assessed") {
            data?.clear()
        }
    }

    /**
     * Requirement (5): Leave assist content empty on quiz views.
     */
    override fun onProvideAssistContent(outContent: AssistContent?) {
        super.onProvideAssistContent(outContent)
        if (mode == "assessed") {
            outContent?.intent = null
            outContent?.clipData = null
            outContent?.structuredData = null
            outContent?.webUri = null
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        // STRICT RULE 6 & 7: Save ONLY attempt ID metadata!
        // NEVER save question prompt, options, answer keys, or question text in Bundle!
        activeAttemptId?.let { outState.putString("saved_attempt_id", it) }
        outState.putString("saved_quiz_id", quizId)
        outState.putString("saved_mode", mode)
    }

    private fun reportSecurityEvent(eventType: String, meta: Map<String, Any>) {
        val attemptId = activeAttemptId ?: return
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val api = ApiClient.getService(applicationContext)
                api.recordAttemptEvent(
                    attemptId = attemptId,
                    request = AttemptEventRequest(type = eventType, meta = meta)
                )
            } catch (_: Exception) {
                // Event logged best-effort over network
            }
        }
    }
}
