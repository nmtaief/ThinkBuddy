package com.thinkbuddy.app.core.utils

/**
 * Utility to format Arabic numerals (0-9) to Bengali numerals (০-৯).
 */
object BengaliDigits {
    private val bengaliDigits = charArrayOf('০', '১', '২', '৩', '৪', '৫', '৬', '৭', '৮', '৯')

    fun format(number: Number): String {
        return format(number.toString())
    }

    fun fromEnglish(number: Number): String {
        return format(number)
    }

    fun fromEnglish(text: String): String {
        return format(text)
    }

    fun fromInt(value: Int): String {
        return format(value)
    }

    fun toBengali(number: Number): String {
        return format(number)
    }

    fun convertNumbers(text: String): String {
        return format(text)
    }

    fun format(text: String): String {
        val builder = java.lang.StringBuilder()
        for (char in text) {
            if (char in '0'..'9') {
                builder.append(bengaliDigits[char - '0'])
            } else {
                builder.append(char)
            }
        }
        return builder.toString()
    }
}
