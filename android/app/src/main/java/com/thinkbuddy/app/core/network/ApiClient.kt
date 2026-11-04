package com.thinkbuddy.app.core.network

import android.content.Context
import com.thinkbuddy.app.BuildConfig
import com.thinkbuddy.app.ThinkBuddyApp
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {
    val baseUrl: String get() = BuildConfig.API_BASE_URL

    private var apiServiceInstance: ApiService? = null
    private var okHttpClientInstance: OkHttpClient? = null

    fun getOkHttpClient(context: Context): OkHttpClient {
        if (okHttpClientInstance == null) {
            val loggingInterceptor = HttpLoggingInterceptor().apply {
                level = if (BuildConfig.LOG_HTTP_BODIES) {
                    HttpLoggingInterceptor.Level.BODY
                } else {
                    HttpLoggingInterceptor.Level.NONE
                }
            }

            val tokenStorage = ThinkBuddyApp.instance.tokenStorage

            okHttpClientInstance = OkHttpClient.Builder()
                .addInterceptor(HeaderInterceptor(context))
                .addInterceptor(AuthInterceptor(tokenStorage))
                .addInterceptor(loggingInterceptor)
                .addNetworkInterceptor { chain ->
                    val request = chain.request()
                    val response = chain.proceed(request)
                    // Requirement (6): no-store for quiz responses
                    if (request.url.encodedPath.contains("/quiz")) {
                        response.newBuilder()
                            .header("Cache-Control", "no-store, no-cache, must-revalidate")
                            .header("Pragma", "no-cache")
                            .build()
                    } else {
                        response
                    }
                }
                .connectTimeout(15, TimeUnit.SECONDS)
                .readTimeout(60, TimeUnit.SECONDS) // Extended for SSE streaming
                .writeTimeout(15, TimeUnit.SECONDS)
                .build()
        }
        return okHttpClientInstance!!
    }

    fun getService(context: Context): ApiService {
        if (apiServiceInstance == null) {
            val client = getOkHttpClient(context)
            val retrofit = Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build()

            apiServiceInstance = retrofit.create(ApiService::class.java)
        }
        return apiServiceInstance!!
    }
}
