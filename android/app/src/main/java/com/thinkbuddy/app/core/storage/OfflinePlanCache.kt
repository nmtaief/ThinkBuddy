package com.thinkbuddy.app.core.storage

import android.content.Context
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import com.thinkbuddy.app.core.network.TodayTask

/**
 * Offline Plan Cache (docs/08_CLIENT_PLATFORM_GUIDE.md §2 & §6)
 *
 * Requirements:
 * - Caches today's plan locally so students can view their syllabus tasks offline.
 * - Restores tasks, target minutes, completed minutes, and streak without internet access.
 * - Marks the session as offline mode with a non-intrusive status indicator.
 */
data class CachedTodayPlan(
    val streakDays: Int,
    val dailyTargetMinutes: Int,
    val dailyCompletedMinutes: Int,
    val tasks: List<TodayTask>,
    val timestampMs: Long = System.currentTimeMillis()
)

object OfflinePlanCache {

    private const val PREFS_NAME = "thinkbuddy_offline_plan_cache"
    private const val KEY_PLAN_DATA = "cached_today_plan_json"
    private val gson = Gson()

    fun saveTodayPlan(context: Context, plan: CachedTodayPlan) {
        try {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val json = gson.toJson(plan)
            prefs.edit().putString(KEY_PLAN_DATA, json).apply()
        } catch (_: Exception) {
            // Best effort cache write
        }
    }

    fun getCachedTodayPlan(context: Context): CachedTodayPlan? {
        return try {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val json = prefs.getString(KEY_PLAN_DATA, null) ?: return null
            gson.fromJson(json, CachedTodayPlan::class.java)
        } catch (_: Exception) {
            null
        }
    }

    fun clearCache(context: Context) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().remove(KEY_PLAN_DATA).apply()
    }
}

