package com.thinkbuddy.app

import com.thinkbuddy.app.core.utils.BengaliDigits
import org.junit.Assert.assertEquals
import org.junit.Test

class BengaliDigitsTest {

    @Test
    fun testSingleDigits() {
        assertEquals("০", BengaliDigits.toBengali(0))
        assertEquals("১", BengaliDigits.toBengali(1))
        assertEquals("৫", BengaliDigits.toBengali(5))
        assertEquals("৯", BengaliDigits.toBengali(9))
    }

    @Test
    fun testMultiDigitNumbers() {
        assertEquals("৪৫", BengaliDigits.toBengali(45))
        assertEquals("১২০", BengaliDigits.toBengali(120))
        assertEquals("২০২৬", BengaliDigits.toBengali(2026))
    }

    @Test
    fun testStringConversion() {
        assertEquals("পৃষ্ঠা ৪২ – ৫৬", BengaliDigits.convertNumbers("পৃষ্ঠা 42 – 56"))
        assertEquals("স্কোর: ১০ / ১০", BengaliDigits.convertNumbers("স্কোর: 10 / 10"))
    }
}

