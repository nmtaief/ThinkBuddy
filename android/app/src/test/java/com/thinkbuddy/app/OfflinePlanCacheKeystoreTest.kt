package com.thinkbuddy.app

import android.content.Context
import android.content.SharedPreferences
import com.thinkbuddy.app.core.network.TodayTask
import com.thinkbuddy.app.core.storage.CachedTodayPlan
import com.thinkbuddy.app.core.storage.OfflinePlanCache
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.security.SecureRandom
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey

/**
 * Unit tests for Keystore-backed Offline Plan Cache (Requirement 5).
 *
 * Verifies:
 * 1. AES-256-GCM encryption at rest (ciphertext does not leak plaintext syllabus or tasks).
 * 2. Proper decryption with correct account key.
 * 3. Automatic purge on account change (Student A -> Student B returns null and deletes cache).
 * 4. Cache purge on logout and HTTP 401.
 */
class OfflinePlanCacheKeystoreTest {

    private lateinit var testKey: SecretKey
    private lateinit var fakeStorage: MutableMap<String, String>
    private lateinit var fakePrefs: SharedPreferences
    private lateinit var fakeContext: Context

    @Before
    fun setUp() {
        val keyGen = KeyGenerator.getInstance("AES")
        keyGen.init(256, SecureRandom())
        testKey = keyGen.generateKey()

        fakeStorage = mutableMapOf()

        val fakeEditor = object : SharedPreferences.Editor {
            override fun putString(key: String, value: String?): SharedPreferences.Editor {
                if (value != null) fakeStorage[key] = value else fakeStorage.remove(key)
                return this
            }
            override fun remove(key: String): SharedPreferences.Editor {
                fakeStorage.remove(key)
                return this
            }
            override fun clear(): SharedPreferences.Editor {
                fakeStorage.clear()
                return this
            }
            override fun apply() {}
            override fun commit(): Boolean = true
            override fun putStringSet(key: String, values: Set<String>?): SharedPreferences.Editor = this
            override fun putInt(key: String, value: Int): SharedPreferences.Editor = this
            override fun putLong(key: String, value: Long): SharedPreferences.Editor = this
            override fun putFloat(key: String, value: Float): SharedPreferences.Editor = this
            override fun putBoolean(key: String, value: Boolean): SharedPreferences.Editor = this
        }

        fakePrefs = object : SharedPreferences {
            override fun getAll(): Map<String, *> = fakeStorage
            override fun getString(key: String, defValue: String?): String? = fakeStorage[key] ?: defValue
            override fun getStringSet(key: String, defValues: Set<String>?): Set<String>? = null
            override fun getInt(key: String, defValue: Int): Int = defValue
            override fun getLong(key: String, defValue: Long): Long = defValue
            override fun getFloat(key: String, defValue: Float): Float = defValue
            override fun getBoolean(key: String, defValue: Boolean): Boolean = defValue
            override fun contains(key: String): Boolean = fakeStorage.containsKey(key)
            override fun edit(): SharedPreferences.Editor = fakeEditor
            override fun registerOnSharedPreferenceChangeListener(listener: SharedPreferences.OnSharedPreferenceChangeListener?) {}
            override fun unregisterOnSharedPreferenceChangeListener(listener: SharedPreferences.OnSharedPreferenceChangeListener?) {}
        }

        fakeContext = object : FakeContext() {
            override fun getSharedPreferences(name: String, mode: Int): SharedPreferences = fakePrefs
        }
    }

    @Test
    fun testEncryptionAtRestDoesNotLeakPlaintextTaskContent() {
        val sampleTask = TodayTask(
            id = "task-101",
            subject = "Physics",
            subjectBn = "পদার্থবিজ্ঞান",
            chapter = "Chapter 2: Kinematics",
            chapterBn = "গতি ও গতিবিদ্যা",
            targetMinutes = 45,
            completedMinutes = 0,
            status = "pending"
        )
        val plan = CachedTodayPlan(
            studentId = "std-alice-001",
            streakDays = 5,
            dailyTargetMinutes = 90,
            dailyCompletedMinutes = 45,
            tasks = listOf(sampleTask)
        )

        OfflinePlanCache.saveTodayPlan(fakeContext, "std-alice-001", plan, testKey)

        val rawStoredCiphertext = fakeStorage["encrypted_today_plan_aes_gcm"]
        assertNotNull("Encrypted ciphertext must be saved in storage", rawStoredCiphertext)
        assertTrue("Ciphertext must be non-empty", rawStoredCiphertext!!.isNotEmpty())

        // Verify plaintext strings are NEVER stored unencrypted (Rule 15: Log, don't leak)
        assertFalse("Ciphertext must not contain plaintext studentId", rawStoredCiphertext.contains("std-alice-001"))
        assertFalse("Ciphertext must not contain plaintext subject", rawStoredCiphertext.contains("পদার্থবিজ্ঞান"))
        assertFalse("Ciphertext must not contain plaintext chapter", rawStoredCiphertext.contains("গতিবিদ্যা"))
    }

    @Test
    fun testDecryptionRestoresExactCachedPlanForSameStudent() {
        val plan = CachedTodayPlan(
            studentId = "std-alice-001",
            streakDays = 7,
            dailyTargetMinutes = 120,
            dailyCompletedMinutes = 60,
            tasks = listOf(
                TodayTask("t1", "Math", "গণিত", "Ch 1", "বাস্তব সংখ্যা", 40, 40, "completed"),
                TodayTask("t2", "Chemistry", "রসায়ন", "Ch 2", "পদার্থের গঠন", 20, 0, "pending")
            )
        )

        OfflinePlanCache.saveTodayPlan(fakeContext, "std-alice-001", plan, testKey)

        val restored = OfflinePlanCache.getCachedTodayPlan(fakeContext, "std-alice-001", testKey)
        assertNotNull("Plan must be successfully decrypted and restored", restored)
        assertEquals("std-alice-001", restored!!.studentId)
        assertEquals(7, restored.streakDays)
        assertEquals(120, restored.dailyTargetMinutes)
        assertEquals(60, restored.dailyCompletedMinutes)
        assertEquals(2, restored.tasks.size)
        assertEquals("গণিত", restored.tasks[0].subjectBn)
    }

    @Test
    fun testAccountChangeAutomaticallyPurgesCacheAndReturnsNull() {
        val planAlice = CachedTodayPlan(
            studentId = "std-alice-001",
            streakDays = 10,
            dailyTargetMinutes = 60,
            dailyCompletedMinutes = 60,
            tasks = emptyList()
        )

        OfflinePlanCache.saveTodayPlan(fakeContext, "std-alice-001", planAlice, testKey)
        assertTrue("Storage has Alice's cached data", fakeStorage.containsKey("encrypted_today_plan_aes_gcm"))

        // Now Bob logs in on the same device and queries cached plan
        val bobPlan = OfflinePlanCache.getCachedTodayPlan(fakeContext, "std-bob-002", testKey)

        // Must return null AND purge Alice's cache immediately
        assertNull("Cross-account read must return null", bobPlan)
        assertFalse("Alice's cache must be purged from storage upon account switch", fakeStorage.containsKey("encrypted_today_plan_aes_gcm"))
    }

    @Test
    fun testLogoutOr401PurgesOfflinePlanCache() {
        val plan = CachedTodayPlan(
            studentId = "std-alice-001",
            streakDays = 3,
            dailyTargetMinutes = 60,
            dailyCompletedMinutes = 30,
            tasks = emptyList()
        )

        OfflinePlanCache.saveTodayPlan(fakeContext, "std-alice-001", plan, testKey)
        assertTrue("Cache is present before logout/401", fakeStorage.containsKey("encrypted_today_plan_aes_gcm"))

        // Trigger purge (simulating user logout or HTTP 401 response)
        OfflinePlanCache.clearCache(fakeContext)

        assertFalse("Cache must be completely removed on logout/401", fakeStorage.containsKey("encrypted_today_plan_aes_gcm"))
        assertNull(OfflinePlanCache.getCachedTodayPlan(fakeContext, "std-alice-001", testKey))
    }
}

private open class FakeContext : android.content.ContextWrapper(null)
