package com.thinkbuddy.app.core.network

import android.content.Context
import okhttp3.Interceptor
import okhttp3.Response
import java.util.UUID

/**
 * Injects required standard platform headers per Rule 4 and docs/08_CLIENT_PLATFORM_GUIDE.md.
 * Uses a privacy-preserving random installation ID instead of hardware Android IDs,
 * avoiding sensitive hardware identifiers and eliminating lint suppressions.
 */
class HeaderInterceptor(
    private val context: Context,
    private val formFactorProvider: () -> String = { "compact" },
    private val languageProvider: () -> String = { "bn" }
) : Interceptor {

    private val deviceId: String by lazy {
        getInstallationId(context)
    }

    companion object {
        fun getInstallationId(context: Context): String {
            val prefs = context.getSharedPreferences("thinkbuddy_app_meta", Context.MODE_PRIVATE)
            var id = prefs.getString("install_id", null)
            if (id == null) {
                id = "inst_${UUID.randomUUID()}"
                prefs.edit().putString("install_id", id).apply()
            }
            return id
        }
    }

    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        val requestBuilder = originalRequest.newBuilder()
            .header("X-Client-Platform", "android")
            .header("X-Client-Form-Factor", formFactorProvider())
            .header("X-App-Version", "1.0.0")
            .header("X-Device-Id", deviceId)
            .header("Accept-Language", languageProvider())

        return chain.proceed(requestBuilder.build())
    }
}
