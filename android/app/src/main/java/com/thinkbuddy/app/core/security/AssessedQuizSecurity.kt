package com.thinkbuddy.app.core.security

import android.app.Activity
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.pm.ApplicationInfo
import android.os.Build
import android.view.View
import android.view.WindowManager
import android.view.accessibility.AccessibilityManager
import com.google.android.gms.tasks.Task
import com.google.android.play.core.integrity.IntegrityManagerFactory
import com.google.android.play.core.integrity.StandardIntegrityManager
import kotlinx.coroutines.suspendCancellableCoroutine
import java.util.concurrent.Executor
import java.util.function.Consumer
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * Assessed Quiz Security Enforcement satisfying Rule 18 and docs/05_SECURE_QUIZ.md:
 * 1. FLAG_SECURE window protection against screen capture/recording and recents preview.
 * 2. Hide overlay windows (API 31+) and filter obscured touches against tapjacking.
 * 3. Screenshot callback (API 34+) and screen recording callback (API 35+).
 * 4. Multi-window / Split-screen & Floating / Freeform window detection and pause policy.
 * 5. Clipboard clearing on entry and exit.
 * 6. Play Integrity attestation bound to attempt ID / server nonce.
 * 7. Non-system accessibility services low-weight telemetry (assistive tech remains usable).
 */
object AssessedQuizSecurity {

    private suspend fun <T> Task<T>.awaitTask(): T = suspendCancellableCoroutine { cont ->
        addOnSuccessListener { cont.resume(it) }
        addOnFailureListener { cont.resumeWithException(it) }
        addOnCanceledListener { cont.cancel() }
    }

    /**
     * Enables FLAG_SECURE to prevent screen capture, mirroring, and task switcher previews.
     * Must be called in onCreate before content is drawn.
     */
    fun enableScreenProtection(activity: Activity) {
        activity.window.setFlags(
            WindowManager.LayoutParams.FLAG_SECURE,
            WindowManager.LayoutParams.FLAG_SECURE
        )
    }

    /**
     * Disables FLAG_SECURE when exiting assessed mode.
     */
    fun disableScreenProtection(activity: Activity) {
        activity.window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
    }

    /**
     * Hides non-system overlay windows on Android 12+ (API 31+) to prevent screen overlays.
     */
    fun hideOverlayWindows(activity: Activity) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            try {
                activity.window.setHideOverlayWindows(true)
            } catch (_: SecurityException) {
                // Defensive degradation if permission not granted
            }
        }
    }

    /**
     * Configures a View to filter obscured touches (tapjacking prevention).
     */
    fun filterObscuredTouches(view: View) {
        view.filterTouchesWhenObscured = true
    }

    /**
     * Clears primary clipboard data on entering or exiting a quiz to prevent question leakage.
     */
    fun clearClipboard(context: Context) {
        try {
            val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
            if (clipboard != null) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                    clipboard.clearPrimaryClip()
                } else {
                    clipboard.setPrimaryClip(ClipData.newPlainText("", ""))
                }
            }
        } catch (_: Exception) {
            // Best effort clipboard sanitation
        }
    }

    /**
     * Registers a callback for screenshot attempts (Android 14+ / API 34+).
     */
    fun registerScreenshotCallback(
        activity: Activity,
        onScreenshotDetected: () -> Unit
    ): Activity.ScreenCaptureCallback? {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            try {
                val callback = Activity.ScreenCaptureCallback {
                    onScreenshotDetected()
                }
                activity.registerScreenCaptureCallback(activity.mainExecutor, callback)
                return callback
            } catch (_: SecurityException) {
                // Defensive degradation if permission not granted
            }
        }
        return null
    }

    /**
     * Unregisters the screenshot callback.
     */
    fun unregisterScreenshotCallback(
        activity: Activity,
        callback: Activity.ScreenCaptureCallback?
    ) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE && callback != null) {
            try {
                activity.unregisterScreenCaptureCallback(callback)
            } catch (_: Exception) {
                // Ignore if not registered
            }
        }
    }

    /**
     * Registers a callback for screen recording detection (Android 15+ / API 35+).
     */
    fun registerScreenRecordingCallback(
        activity: Activity,
        onRecordingChanged: (Boolean) -> Unit
    ): Consumer<Int>? {
        if (Build.VERSION.SDK_INT >= 35) {
            val consumer = Consumer<Int> { state ->
                // WindowManager.SCREEN_RECORDING_STATE_ACTIVE = 1
                val isRecording = state == 1
                onRecordingChanged(isRecording)
            }
            try {
                activity.windowManager.addScreenRecordingCallback(activity.mainExecutor, consumer)
                return consumer
            } catch (_: Exception) {
                // Fallback if platform does not support
            }
        }
        return null
    }

    /**
     * Unregisters the screen recording callback.
     */
    fun unregisterScreenRecordingCallback(
        activity: Activity,
        consumer: Consumer<Int>?
    ) {
        if (Build.VERSION.SDK_INT >= 35 && consumer != null) {
            try {
                activity.windowManager.removeScreenRecordingCallback(consumer)
            } catch (_: Exception) {
                // Ignore if not registered
            }
        }
    }

    /**
     * Checks if the activity is currently running in multi-window or split-screen mode.
     */
    fun isInMultiWindowMode(activity: Activity): Boolean {
        return activity.isInMultiWindowMode
    }

    /**
     * Detects floating, freeform, or windowed mode on tablets and foldables
     * by comparing window bounds with display bounds and checking multi-window mode.
     */
    fun isFloatingOrWindowedMode(activity: Activity): Boolean {
        if (activity.isInMultiWindowMode) return true
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            try {
                val windowBounds = activity.windowManager.currentWindowMetrics.bounds
                val maxBounds = activity.windowManager.maximumWindowMetrics.bounds
                val widthRatio = windowBounds.width().toFloat() / maxBounds.width().toFloat()
                val heightRatio = windowBounds.height().toFloat() / maxBounds.height().toFloat()
                if (widthRatio < 0.85f || heightRatio < 0.85f) {
                    return true
                }
            } catch (_: Exception) {
                // Defensive degradation
            }
        }
        return false
    }

    /**
     * Inspects running accessibility services. Returns package names of any non-system
     * services for low-weight telemetry. Never invalidates or blocks assistive technology.
     */
    fun checkNonSystemAccessibilityServices(context: Context): List<String> {
        val nonSystemServices = mutableListOf<String>()
        try {
            val am = context.getSystemService(Context.ACCESSIBILITY_SERVICE) as? AccessibilityManager ?: return emptyList()
            val services = am.getEnabledAccessibilityServiceList(android.accessibilityservice.AccessibilityServiceInfo.FEEDBACK_ALL_MASK)
            for (service in services) {
                val appInfo = service.resolveInfo?.serviceInfo?.applicationInfo
                if (appInfo != null) {
                    val isSystem = (appInfo.flags and ApplicationInfo.FLAG_SYSTEM) != 0
                    if (!isSystem) {
                        service.resolveInfo?.serviceInfo?.packageName?.let { nonSystemServices.add(it) }
                    }
                }
            }
        } catch (_: Exception) {}
        return nonSystemServices
    }

    /**
     * Requests a Google Play Integrity token cryptographically bound to the attempt ID or nonce.
     */
    suspend fun requestPlayIntegrityToken(
        context: Context,
        cloudProjectNumber: Long,
        nonceOrAttemptId: String
    ): String? {
        return try {
            val integrityManager = IntegrityManagerFactory.createStandard(context)
            val tokenProvider = integrityManager.prepareIntegrityToken(
                StandardIntegrityManager.PrepareIntegrityTokenRequest.builder()
                    .setCloudProjectNumber(cloudProjectNumber)
                    .build()
            ).awaitTask()

            val response = tokenProvider.request(
                StandardIntegrityManager.StandardIntegrityTokenRequest.builder()
                    .setRequestHash(nonceOrAttemptId)
                    .build()
            ).awaitTask()

            response.token()
        } catch (e: Exception) {
            // Google Play Services unavailable or attestation failure.
            // Client never labels itself trusted. Returns null so caller can
            // supply header 'X-Device-Attestation-Provider: unsupported'.
            null
        }
    }
}
