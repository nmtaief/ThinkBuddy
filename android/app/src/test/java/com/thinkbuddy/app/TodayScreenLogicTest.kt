package com.thinkbuddy.app

import com.thinkbuddy.app.ui.home.getTimeBasedGreeting
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TodayScreenLogicTest {

    @Test
    fun testTimeBasedGreetingAcrossAll24Hours() {
        val studentName = "তাহমিদ"
        val forbiddenReligiousPatterns = listOf("সালাম", "আসসালামু", "নমস্কার", "আদাব", "বিসমিল্লাহ", "ধর্ম", "আল্লাহ", "খোদা", "ঈশ্বর")

        for (hour in 0..23) {
            val (title, subtitle) = getTimeBasedGreeting(studentName, hour)

            assertTrue("Title should contain student name at hour $hour", title.contains(studentName))
            assertTrue("Title should be non-empty at hour $hour", title.isNotBlank())
            assertTrue("Subtitle should be non-empty at hour $hour", subtitle.isNotBlank())

            // Rule: strictly zero religious phrasing
            for (forbidden in forbiddenReligiousPatterns) {
                assertFalse("Greeting must not contain '$forbidden' at hour $hour", title.contains(forbidden))
                assertFalse("Subtitle must not contain '$forbidden' at hour $hour", subtitle.contains(forbidden))
            }

            // Verify appropriate time-of-day Bengali prefixes
            when (hour) {
                in 5..11 -> assertTrue("Morning greeting prefix at hour $hour", title.startsWith("শুভ সকাল"))
                in 12..15 -> assertTrue("Noon greeting prefix at hour $hour", title.startsWith("শুভ দুপুর"))
                in 16..18 -> assertTrue("Afternoon greeting prefix at hour $hour", title.startsWith("শুভ বিকাল"))
                in 19..22 -> assertTrue("Evening greeting prefix at hour $hour", title.startsWith("শুভ সন্ধ্যা"))
                else -> assertTrue("Night greeting prefix at hour $hour", title.startsWith("শুভ রাত্রি"))
            }
        }
    }
}

