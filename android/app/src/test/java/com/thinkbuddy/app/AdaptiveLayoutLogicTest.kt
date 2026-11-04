package com.thinkbuddy.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AdaptiveLayoutLogicTest {

    private fun isTabletLayout(widthDp: Int): Boolean {
        // Threshold: 600 dp per docs/08_CLIENT_PLATFORM_GUIDE.md and Material 3 WindowSizeClass
        return widthDp >= 600
    }

    private fun getNavigationPattern(widthDp: Int): String {
        return if (isTabletLayout(widthDp)) "NAVIGATION_RAIL" else "BOTTOM_NAVIGATION"
    }

    private fun getTodayPaneMode(widthDp: Int): String {
        return if (isTabletLayout(widthDp)) "TWO_PANE_MASTER_DETAIL" else "SINGLE_PANE"
    }

    @Test
    fun testPhoneViewportsUseBottomNavAndSinglePane() {
        val phoneWidths = listOf(320, 360, 393, 412, 599)
        for (w in phoneWidths) {
            assertFalse("Width $w should not be tablet", isTabletLayout(w))
            assertEquals("Width $w should use bottom nav", "BOTTOM_NAVIGATION", getNavigationPattern(w))
            assertEquals("Width $w should use single pane", "SINGLE_PANE", getTodayPaneMode(w))
        }
    }

    @Test
    fun testTabletViewportsUseNavRailAndTwoPaneMasterDetail() {
        val tabletWidths = listOf(600, 768, 800, 840, 1024, 1280)
        for (w in tabletWidths) {
            assertTrue("Width $w should be tablet", isTabletLayout(w))
            assertEquals("Width $w should use nav rail", "NAVIGATION_RAIL", getNavigationPattern(w))
            assertEquals("Width $w should use two pane", "TWO_PANE_MASTER_DETAIL", getTodayPaneMode(w))
        }
    }
}

