package com.thinkbuddy.app.core.network

import com.thinkbuddy.app.ThinkBuddyApp
import com.thinkbuddy.app.core.security.KeystoreTokenStorage
import com.thinkbuddy.app.core.storage.OfflinePlanCache
import okhttp3.Interceptor
import okhttp3.Response

class AuthInterceptor(
    private val tokenStorage: KeystoreTokenStorage
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        val accessToken = tokenStorage.getAccessToken()

        val request = if (accessToken != null && !originalRequest.header("Authorization").isNullOrEmpty()) {
            originalRequest
        } else if (accessToken != null) {
            originalRequest.newBuilder()
                .header("Authorization", "Bearer $accessToken")
                .build()
        } else {
            originalRequest
        }

        val response = chain.proceed(request)

        // If 401 Unauthorized, clear stale session tokens to force re-auth and purge offline cache (Item 5)
        if (response.code == 401) {
            tokenStorage.clear()
            try {
                OfflinePlanCache.clearCache(ThinkBuddyApp.instance)
            } catch (_: Exception) {}
        }

        return response
    }
}
