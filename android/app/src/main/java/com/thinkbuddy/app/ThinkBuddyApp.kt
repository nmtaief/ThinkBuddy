package com.thinkbuddy.app

import android.app.Application
import com.thinkbuddy.app.core.security.KeystoreTokenStorage

class ThinkBuddyApp : Application() {
    lateinit var tokenStorage: KeystoreTokenStorage
        private set

    override fun onCreate() {
        super.onCreate()
        instance = this
        tokenStorage = KeystoreTokenStorage(this)
    }

    companion object {
        lateinit var instance: ThinkBuddyApp
            private set
    }
}
