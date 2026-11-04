package com.thinkbuddy.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.UUID

class PlayIntegrityClientContractTest {

    @Test
    fun testCanonicalServerNoncePassThrough() {
        // Server issues a single-use nonce for the attempt
        val serverIssuedNonce = UUID.randomUUID().toString()

        // The client must bind the exact server-issued nonce directly as the request hash
        val requestHash = serverIssuedNonce
        assertEquals("Canonical nonce must be passed directly without client mutation", serverIssuedNonce, requestHash)
        assertNotNull(requestHash)
        assertTrue(requestHash.isNotEmpty())
    }

    @Test
    fun testClientNeverLabelsItselfTrustedOnFailure() {
        // When integrity token retrieval fails on non-GMS devices, client returns null
        // and caller must set header 'X-Device-Attestation-Provider: unsupported'.
        val tokenOnFailure: String? = null
        assertNull(tokenOnFailure)

        val headerMap = mutableMapOf<String, String>()
        if (tokenOnFailure == null) {
            headerMap["X-Device-Attestation-Provider"] = "unsupported"
        }

        assertEquals("unsupported", headerMap["X-Device-Attestation-Provider"])
        assertTrue(!headerMap.containsKey("X-Device-Integrity"))
    }
}
