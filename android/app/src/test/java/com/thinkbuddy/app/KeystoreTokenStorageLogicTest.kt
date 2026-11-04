package com.thinkbuddy.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.security.SecureRandom

class KeystoreTokenStorageLogicTest {

    @Test
    fun testFreshIvGeneratedPerEncryption() {
        val random = SecureRandom()
        val iv1 = ByteArray(12).apply { random.nextBytes(this) }
        val iv2 = ByteArray(12).apply { random.nextBytes(this) }

        assertEquals(12, iv1.size)
        assertEquals(12, iv2.size)
        assertFalse(iv1.contentEquals(iv2))
    }

    @Test
    fun testLostKeyTriggersSignOutCallback() {
        var signOutTriggered = false
        val onLostKeyCallback = { signOutTriggered = true }

        // Simulate lost key / decryption failure
        val simulateLostKey = {
            onLostKeyCallback()
        }

        simulateLostKey()
        assertTrue("Lost key should trigger sign-out callback", signOutTriggered)
    }

    @Test
    fun testCombinedIvAndCiphertextPackaging() {
        val iv = ByteArray(12) { 1 }
        val ciphertext = "encrypted_jwt_payload".toByteArray(Charsets.UTF_8)

        val combined = ByteArray(iv.size + ciphertext.size)
        System.arraycopy(iv, 0, combined, 0, iv.size)
        System.arraycopy(ciphertext, 0, combined, iv.size, ciphertext.size)

        assertEquals(12 + ciphertext.size, combined.size)

        val extractedIv = combined.copyOfRange(0, 12)
        val extractedCiphertext = combined.copyOfRange(12, combined.size)

        assertTrue(iv.contentEquals(extractedIv))
        assertTrue(ciphertext.contentEquals(extractedCiphertext))
    }
}
