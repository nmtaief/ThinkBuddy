package com.thinkbuddy.app.core.storage

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.util.Base64
import com.google.gson.Gson
import com.thinkbuddy.app.core.network.TodayTask
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Keystore-backed Offline Plan Cache (Rule 17 & docs/08_CLIENT_PLATFORM_GUIDE.md §2 & §6)
 *
 * Requirements:
 * 1. Hardware Keystore-backed AES-256-GCM encryption at rest.
 * 2. Purge immediately on user logout.
 * 3. Purge immediately on HTTP 401 Unauthorized.
 * 4. Purge immediately on account change (Student A -> Student B).
 */
data class CachedTodayPlan(
    val studentId: String,
    val streakDays: Int,
    val dailyTargetMinutes: Int,
    val dailyCompletedMinutes: Int,
    val tasks: List<TodayTask>,
    val timestampMs: Long = System.currentTimeMillis()
)

object OfflinePlanCache {

    private const val PREFS_NAME = "thinkbuddy_offline_plan_cache"
    private const val KEY_ENCRYPTED_PLAN = "encrypted_today_plan_aes_gcm"
    private const val KEYSTORE_ALIAS = "thinkbuddy_offline_plan_cache_key"
    private const val KEYSTORE_PROVIDER = "AndroidKeyStore"
    private const val TRANSFORMATION = "AES/GCM/NoPadding"
    private const val GCM_TAG_LENGTH = 128
    private const val IV_LENGTH = 12

    private val gson = Gson()

    fun saveTodayPlan(
        context: Context,
        studentId: String,
        plan: CachedTodayPlan,
        injectedKey: SecretKey? = null
    ) {
        try {
            val key = injectedKey ?: getOrCreateSecretKey() ?: return
            val planToStore = plan.copy(studentId = studentId)
            val json = gson.toJson(planToStore)
            val encryptedBase64 = encrypt(json, key)
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            prefs.edit().putString(KEY_ENCRYPTED_PLAN, encryptedBase64).apply()
        } catch (_: Exception) {
            // Best effort cache write
        }
    }

    fun getCachedTodayPlan(
        context: Context,
        expectedStudentId: String,
        injectedKey: SecretKey? = null
    ): CachedTodayPlan? {
        return try {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val encryptedBase64 = prefs.getString(KEY_ENCRYPTED_PLAN, null) ?: return null
            val key = injectedKey ?: getOrCreateSecretKey() ?: run {
                clearCache(context)
                return null
            }
            val json = decrypt(encryptedBase64, key) ?: run {
                clearCache(context)
                return null
            }
            val plan = gson.fromJson(json, CachedTodayPlan::class.java)

            // Account change detection: if stored studentId does not match current student, PURGE cache
            if (plan.studentId != expectedStudentId) {
                clearCache(context)
                null
            } else {
                plan
            }
        } catch (_: Exception) {
            clearCache(context)
            null
        }
    }

    /**
     * Purges all cached offline plan data.
     * Called on:
     * - User Logout
     * - HTTP 401 Unauthorized
     * - Account or Student Switch
     */
    fun clearCache(context: Context) {
        try {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            prefs.edit().remove(KEY_ENCRYPTED_PLAN).apply()
        } catch (_: Exception) {
            // Best effort purge
        }
    }

    fun encrypt(plainText: String, secretKey: SecretKey): String {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, secretKey)
        val iv = cipher.iv
        val cipherText = cipher.doFinal(plainText.toByteArray(Charsets.UTF_8))
        val combined = ByteArray(iv.size + cipherText.size)
        System.arraycopy(iv, 0, combined, 0, iv.size)
        System.arraycopy(cipherText, 0, combined, iv.size, cipherText.size)
        return Base64.getEncoder().encodeToString(combined)
    }

    fun decrypt(cipherTextBase64: String, secretKey: SecretKey): String? {
        return try {
            val combined = Base64.getDecoder().decode(cipherTextBase64)
            if (combined.size < IV_LENGTH) return null
            val iv = combined.copyOfRange(0, IV_LENGTH)
            val cipherText = combined.copyOfRange(IV_LENGTH, combined.size)
            val spec = GCMParameterSpec(GCM_TAG_LENGTH, iv)
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.DECRYPT_MODE, secretKey, spec)
            String(cipher.doFinal(cipherText), Charsets.UTF_8)
        } catch (_: Exception) {
            null
        }
    }

    private fun getOrCreateSecretKey(): SecretKey? {
        return try {
            val ks = KeyStore.getInstance(KEYSTORE_PROVIDER).apply { load(null) }
            if (!ks.containsAlias(KEYSTORE_ALIAS)) {
                val keyGen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE_PROVIDER)
                val spec = KeyGenParameterSpec.Builder(
                    KEYSTORE_ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
                )
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build()
                keyGen.init(spec)
                keyGen.generateKey()
            }
            ks.getKey(KEYSTORE_ALIAS, null) as SecretKey
        } catch (_: Exception) {
            null
        }
    }
}
