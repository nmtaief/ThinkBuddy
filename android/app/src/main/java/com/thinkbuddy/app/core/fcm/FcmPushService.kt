package com.thinkbuddy.app.core.fcm

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.thinkbuddy.app.MainActivity

/**
 * Push notification service enforcing Rule 15: Log, don't leak.
 * Incoming messages display generic, non-leaking alert text on the notification tray
 * and never expose student chats, OTPs, or question answers.
 */
class FcmPushService : Service() {

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val title = intent?.getStringExtra("title")
        val body = intent?.getStringExtra("body")
        showGenericNotification(this, 1001, title, body)
        return START_NOT_STICKY
    }

    companion object {
        const val CHANNEL_ID = "thinkbuddy_learning_updates"

        fun showGenericNotification(
            context: Context,
            notificationId: Int = 1001,
            title: String? = null,
            body: String? = null
        ) {
            val notificationManager =
                context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

            val channel = NotificationChannel(
                CHANNEL_ID,
                "ThinkBuddy Updates",
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply {
                description = "Study schedule reminders and updates"
            }
            notificationManager.createNotificationChannel(channel)

            // Generic text per Rule 15: non-leaking
            val displayTitle = title ?: "পড়াশোনার নতুন বার্তা (ThinkBuddy)"
            val displayBody = body ?: "তোমার রুটিনে নতুন নির্দেশনা রয়েছে। অ্যাপে প্রবেশ করে দেখে নাও।"

            val intent = Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            val pendingIntent = PendingIntent.getActivity(
                context,
                0,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )

            val notification = NotificationCompat.Builder(context, CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle(displayTitle)
                .setContentText(displayBody)
                .setAutoCancel(true)
                .setContentIntent(pendingIntent)
                .setPriority(NotificationCompat.PRIORITY_DEFAULT)
                .build()

            notificationManager.notify(notificationId, notification)
        }
    }
}
