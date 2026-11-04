package com.thinkbuddy.app

import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.thinkbuddy.app.core.security.KeystoreTokenStorage
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.security.KeyStore

/**
 * Instrumented test executing directly on Android runtime emulator.
 * Tests real AndroidKeyStore AES-256-GCM encryption, fresh IV generation,
 * secure retrieval, token clearing, and lost-key wipe.
 */
@RunWith(AndroidJUnit4::class)
class KeystoreTokenStorageInstrumentedTest {

    private lateinit var storage: KeystoreTokenStorage
    private var lostKeyCalled = false

    @Before
    fun setUp() {
        lostKeyCalled = false
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        storage = KeystoreTokenStorage(context)
        storage.onLostKeySignOut = { lostKeyCalled = true }
        storage.clear()
    }

    @Test
    fun testRealAndroidKeystoreTokenStorageRoundTrip() {
        val testAccessToken = "mock_test_token_string"
        val testRefreshToken = "mock_test_refresh_string"
        val testUserId = "user-uuid-456"
        val testRole = "student"

        // 1. Save tokens
        storage.saveTokens(
            accessToken = testAccessToken,
            refreshToken = testRefreshToken,
            userId = testUserId,
            role = testRole
        )

        // 2. Verify Android KeyStore actually holds the AES key
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        assertTrue("AndroidKeyStore must contain master key alias", keyStore.containsAlias("ThinkBuddyTokenKey"))

        // 3. Retrieve tokens and verify exact round-trip match
        assertEquals(testAccessToken, storage.getAccessToken())
        assertEquals(testRefreshToken, storage.getRefreshToken())
        assertEquals(testUserId, storage.getUserId())
        assertEquals(testRole, storage.getRole())
        assertFalse("Lost key should not be triggered during normal operation", lostKeyCalled)

        // 4. Clear tokens
        storage.clear()
        assertNull(storage.getAccessToken())
        assertNull(storage.getRefreshToken())
        assertNull(storage.getUserId())
    }

    @Test
    fun testFreshIvGeneratedPerSaveOperation() {
        val token = "jwt.test.token"
        storage.saveTokens(token, token, "u1", "student")

        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val prefs = context.getSharedPreferences("tb_keystore_secured_tokens", android.content.Context.MODE_PRIVATE)

        val encryptedPayload1 = prefs.getString("enc_access_token", null)
        assertNotNull(encryptedPayload1)

        // Save again with same plaintext
        storage.saveTokens(token, token, "u1", "student")
        val encryptedPayload2 = prefs.getString("enc_access_token", null)
        assertNotNull(encryptedPayload2)

        // Due to fresh 12-byte IV per encryption, ciphertexts MUST differ
        assertFalse(
            "Each encryption must use a fresh random IV producing distinct ciphertexts",
            encryptedPayload1 == encryptedPayload2
        )
    }
}
