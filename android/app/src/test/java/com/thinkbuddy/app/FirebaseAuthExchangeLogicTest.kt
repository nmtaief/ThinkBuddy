package com.thinkbuddy.app

import com.google.gson.Gson
import com.thinkbuddy.app.core.network.AuthExchangeRequest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class FirebaseAuthExchangeLogicTest {

    private val gson = Gson()

    @Test
    fun testFakePhoneTokenFormatting() {
        val rawPhone = "+8801711111111"
        val fakeToken = "fake:phone:$rawPhone"

        assertTrue(fakeToken.startsWith("fake:phone:"))
        assertEquals("fake:phone:+8801711111111", fakeToken)
    }

    @Test
    fun testAuthExchangeRequestSerialization() {
        val request = AuthExchangeRequest(
            providerToken = "fake:phone:+8801711111111",
            role = "student",
            displayName = "তাহমিদ আলিম",
            locale = "bn"
        )

        val json = gson.toJson(request)
        assertTrue(json.contains("\"provider_token\":\"fake:phone:+8801711111111\""))
        assertTrue(json.contains("\"role\":\"student\""))
        assertTrue(json.contains("\"display_name\":\"তাহমিদ আলিম\""))
        assertTrue(json.contains("\"locale\":\"bn\""))
    }

    @Test
    fun testParentRoleExchangeRequest() {
        val request = AuthExchangeRequest(
            providerToken = "fake:phone:+8801722222222",
            role = "parent",
            displayName = "রফিকুল ইসলাম",
            locale = "bn"
        )

        assertEquals("parent", request.role)
        assertEquals("fake:phone:+8801722222222", request.providerToken)
        assertEquals("রফিকুল ইসলাম", request.displayName)
    }
}

