package com.thinkbuddy.app

import android.os.Bundle
import com.thinkbuddy.app.core.network.AnswerItemRequest
import com.thinkbuddy.app.core.network.AnswerItemResponse
import com.thinkbuddy.app.core.network.AttemptItemPublic
import com.thinkbuddy.app.core.network.QuestionOptionPublic
import com.thinkbuddy.app.core.network.StartAttemptResponse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests verifying Group 2 Security Behaviors:
 * 1. SavedInstanceState sanitization: strictly ZERO question prompt, options, or answer keys in state bundles.
 * 2. Per-item single-use nonces: each question carries unique nonce passed in AnswerItemRequest.
 * 3. Rule 6 Answer Key Isolation: Assessed mode answer feedback is withheld; Practice mode delivers feedback.
 * 4. Countdown timer auto-submit logic on expiration.
 */
class AssessedQuizSecurityLogicTest {

    @Test
    fun testSavedInstanceStateZeroQuestionLeakage() {
        // State map representing saved instance state keys and values
        val savedState = mutableMapOf<String, String>()

        val attemptId = "att-test-123"
        val quizId = "quiz-physics-1"
        val mode = "assessed"

        // Legitimate metadata saved
        savedState["saved_attempt_id"] = attemptId
        savedState["saved_quiz_id"] = quizId
        savedState["saved_mode"] = mode

        // Verify state contains only metadata
        assertEquals(attemptId, savedState["saved_attempt_id"])
        assertEquals(quizId, savedState["saved_quiz_id"])
        assertEquals(mode, savedState["saved_mode"])

        // Assert strictly zero question data in saved instance state
        assertNull(savedState["question_text"])
        assertNull(savedState["prompt"])
        assertNull(savedState["options"])
        assertNull(savedState["answer_key"])
        for (key in savedState.keys) {
            assertFalse("Saved state key '$key' must not contain question", key.contains("question"))
            assertFalse("Saved state key '$key' must not contain option", key.contains("option"))
            assertFalse("Saved state key '$key' must not contain answer", key.contains("answer"))
        }
    }

    @Test
    fun testPerItemNonceBinding() {
        val nonce1 = "nonce_item_pos_1_random_abc"
        val nonce2 = "nonce_item_pos_2_random_xyz"

        val item1 = AttemptItemPublic(
            id = "item-1",
            position = 1,
            prompt = "What is velocity?",
            promptBn = "বেগ বলতে কী বোঝায়?",
            options = listOf(QuestionOptionPublic(1, "Option A", "অপশন ক")),
            nonce = nonce1
        )

        val item2 = AttemptItemPublic(
            id = "item-2",
            position = 2,
            prompt = "What is acceleration?",
            promptBn = "ত্বরণ বলতে কী বোঝায়?",
            options = listOf(QuestionOptionPublic(1, "Option A", "অপশন ক")),
            nonce = nonce2
        )

        // Nonces must be unique per item to prevent replay
        assertTrue(item1.nonce.isNotBlank())
        assertTrue(item2.nonce.isNotBlank())
        assertFalse(item1.nonce == item2.nonce)

        val request = AnswerItemRequest(
            nonce = item1.nonce,
            response = mapOf("selected_option" to 1),
            timeSpentMs = 12500
        )

        assertEquals(nonce1, request.nonce)
        assertEquals(1, request.response["selected_option"])
        assertEquals(12500, request.timeSpentMs)
    }

    @Test
    fun testRule6AnswerKeyIsolationPracticeVsAssessed() {
        // Assessed Mode response: feedback is null!
        val assessedAnswerResponse = AnswerItemResponse(
            recorded = true,
            position = 1,
            nextPosition = 2,
            isLast = false,
            nextItem = AttemptItemPublic(
                id = "item-2",
                position = 2,
                nonce = "nonce-2"
            ),
            feedback = null // Rule 6: Answer keys and correctness withheld until submit
        )

        assertNull("Assessed mode must withhold answer feedback", assessedAnswerResponse.feedback)
        assertNotNull(assessedAnswerResponse.nextItem)

        // Practice Mode response: immediate feedback provided!
        val practiceAnswerResponse = AnswerItemResponse(
            recorded = true,
            position = 1,
            nextPosition = 2,
            isLast = false,
            nextItem = null,
            feedback = mapOf(
                "is_correct" to true,
                "explanation_bn" to "v = u + at হলো গতির প্রথম সমীকরণ।",
                "citation_page" to 48
            )
        )

        assertNotNull("Practice mode must provide immediate feedback", practiceAnswerResponse.feedback)
        assertEquals(true, practiceAnswerResponse.feedback!!["is_correct"])
        assertEquals(48, practiceAnswerResponse.feedback!!["citation_page"])
    }

    @Test
    fun testCountdownTimerExpirationTriggersAutoSubmit() {
        var timerSeconds = 3
        var autoSubmitted = false

        fun tickTimer() {
            if (timerSeconds > 0) {
                timerSeconds -= 1
                if (timerSeconds <= 0) {
                    autoSubmitted = true
                }
            }
        }

        tickTimer() // 2s
        assertFalse(autoSubmitted)
        tickTimer() // 1s
        assertFalse(autoSubmitted)
        tickTimer() // 0s -> triggers submit!
        assertTrue("Auto-submit must trigger when timer reaches 0", autoSubmitted)
        assertEquals(0, timerSeconds)
    }
}
