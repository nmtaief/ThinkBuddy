# ThinkBuddy Proguard Rules

# Preserve Gson models & serialized properties
-keepattributes *Annotation*
-keepclassmembers class * {
    @com.google.gson.annotations.SerializedName <fields>;
}

# Strip all Android Log output in release builds (Rule 15: Log, don't leak)
-assumenosideeffects class android.util.Log {
    public static boolean isLoggable(java.lang.String, int);
    public static int v(...);
    public static int d(...);
    public static int i(...);
    public static int w(...);
}

# Preserve Play Integrity classes
-keep class com.google.android.play.core.integrity.** { *; }
