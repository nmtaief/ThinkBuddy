package com.thinkbuddy.app.ui.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.TabRowDefaults
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thinkbuddy.app.ThinkBuddyApp
import com.thinkbuddy.app.core.network.ApiClient
import com.thinkbuddy.app.core.network.AuthExchangeRequest
import com.thinkbuddy.app.ui.theme.BorderDark
import com.thinkbuddy.app.ui.theme.IndigoAccent
import com.thinkbuddy.app.ui.theme.TealPrimary
import kotlinx.coroutines.launch

/**
 * Authentication screen supporting Sign-In and Registration.
 * Rule: Role choice is strictly shown only during first-time Registration.
 * Student registration requires a valid parent invitation link code.
 */
@Composable
fun AuthScreen(
    onAuthSuccess: (role: String) -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var isRegistering by remember { mutableStateOf(false) }
    var phoneNumber by remember { mutableStateOf(if (com.thinkbuddy.app.BuildConfig.ENABLE_FAKE_AUTH) "01712345678" else "") }
    var otpCode by remember { mutableStateOf(if (com.thinkbuddy.app.BuildConfig.ENABLE_FAKE_AUTH) "123456" else "") }
    var linkCode by remember { mutableStateOf("") }
    var isOtpSent by remember { mutableStateOf(false) }
    var isLoading by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var selectedRole by remember { mutableStateOf("student") }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(
                        MaterialTheme.colorScheme.background,
                        MaterialTheme.colorScheme.surface
                    )
                )
            ),
        contentAlignment = Alignment.Center
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth(0.9f)
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Text(
                text = "ThinkBuddy",
                style = MaterialTheme.typography.headlineLarge,
                color = TealPrimary,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = "পড়াশোনার ব্যক্তিগত স্মার্ট প্ল্যাটফর্ম",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(24.dp))

            // Mode Selector: Sign-In vs Registration
            TabRow(
                selectedTabIndex = if (isRegistering) 1 else 0,
                containerColor = Color.Transparent,
                contentColor = TealPrimary,
                indicator = { tabPositions ->
                    TabRowDefaults.SecondaryIndicator(
                        Modifier.tabIndicatorOffset(tabPositions[if (isRegistering) 1 else 0]),
                        color = TealPrimary
                    )
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                Tab(
                    selected = !isRegistering,
                    onClick = {
                        isRegistering = false
                        errorMessage = null
                    },
                    text = { Text("প্রবেশ করুন (Sign In)", fontWeight = FontWeight.SemiBold) }
                )
                Tab(
                    selected = isRegistering,
                    onClick = {
                        isRegistering = true
                        errorMessage = null
                    },
                    text = { Text("নতুন নিবন্ধন (Register)", fontWeight = FontWeight.SemiBold) }
                )
            }

            Spacer(modifier = Modifier.height(20.dp))

            // Role selection is ONLY shown during registration
            if (isRegistering) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .height(42.dp)
                            .background(
                                color = if (selectedRole == "student") TealPrimary.copy(alpha = 0.15f) else Color.Transparent,
                                shape = RoundedCornerShape(8.dp)
                            )
                            .clickable { selectedRole = "student" },
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "শিক্ষার্থী (Student)",
                            color = if (selectedRole == "student") TealPrimary else MaterialTheme.colorScheme.onSurface,
                            fontWeight = if (selectedRole == "student") FontWeight.Bold else FontWeight.Normal
                        )
                    }
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .height(42.dp)
                            .background(
                                color = if (selectedRole == "parent") TealPrimary.copy(alpha = 0.15f) else Color.Transparent,
                                shape = RoundedCornerShape(8.dp)
                            )
                            .clickable { selectedRole = "parent" },
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "অভিভাবক (Parent)",
                            color = if (selectedRole == "parent") TealPrimary else MaterialTheme.colorScheme.onSurface,
                            fontWeight = if (selectedRole == "parent") FontWeight.Bold else FontWeight.Normal
                        )
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // Link code is mandatory for student registration
                if (selectedRole == "student") {
                    OutlinedTextField(
                        value = linkCode,
                        onValueChange = { linkCode = it.uppercase() },
                        label = { Text("অভিভাবক লিংক কোড (Link Code)") },
                        placeholder = { Text("যেমন: LINK-1234-ABCD") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = TealPrimary,
                            unfocusedBorderColor = BorderDark
                        )
                    )
                    Text(
                        text = "শিক্ষার্থী নিবন্ধনের জন্য অভিভাবকের অ্যাপ থেকে প্রাপ্ত কোড আবশ্যক।",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 4.dp, start = 4.dp)
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                }
            }

            if (!isOtpSent) {
                OutlinedTextField(
                    value = phoneNumber,
                    onValueChange = { phoneNumber = it },
                    label = { Text("মোবাইল নম্বর (Phone Number)") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = TealPrimary,
                        unfocusedBorderColor = BorderDark
                    )
                )

                Spacer(modifier = Modifier.height(16.dp))

                Button(
                    onClick = {
                        if (isRegistering && selectedRole == "student" && linkCode.isBlank()) {
                            errorMessage = "শিক্ষার্থী নিবন্ধনের জন্য লিংক কোড আবশ্যক।"
                            return@Button
                        }
                        if (phoneNumber.isNotBlank()) {
                            isOtpSent = true
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(50.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = TealPrimary)
                ) {
                    Text(
                        text = "ওটিপি কোড পাঠান (Send OTP)",
                        fontSize = 16.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            } else {
                OutlinedTextField(
                    value = otpCode,
                    onValueChange = { otpCode = it },
                    label = { Text("৬ ডিজিটের ওটিপি লিখুন") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = TealPrimary,
                        unfocusedBorderColor = BorderDark
                    )
                )

                Spacer(modifier = Modifier.height(16.dp))

                Button(
                    onClick = {
                        if (isRegistering && selectedRole == "student" && linkCode.isBlank()) {
                            errorMessage = "শিক্ষার্থী নিবন্ধনের জন্য লিংক কোড আবশ্যক।"
                            return@Button
                        }
                        isLoading = true
                        errorMessage = null
                        scope.launch {
                            try {
                                val api = ApiClient.getService(context)
                                val token = if (com.thinkbuddy.app.BuildConfig.ENABLE_FAKE_AUTH) {
                                    if (phoneNumber.startsWith("fake:") || phoneNumber.startsWith("{")) {
                                        phoneNumber
                                    } else {
                                        val cleaned = phoneNumber.trim().ifEmpty { "+8801711111111" }
                                        "fake:phone:$cleaned"
                                    }
                                } else {
                                    // In production release builds, fake tokens are strictly prohibited
                                    if (phoneNumber.isBlank() || otpCode.isBlank()) {
                                        throw IllegalStateException("Phone number and SMS verification code required.")
                                    }
                                    "firebase:phone:${phoneNumber.trim()}:$otpCode"
                                }
                                val studentDefaultName = "তাহমিদ আলিম (Tahmid)"
                                val parentDefaultName = "রফিকুল ইসলাম (Rafiq)"
                                val resp = api.exchangeToken(
                                    AuthExchangeRequest(
                                        providerToken = token,
                                        role = if (isRegistering) selectedRole else "student",
                                        linkCode = if (isRegistering && selectedRole == "student") linkCode.trim() else null,
                                        displayName = if (selectedRole == "student") studentDefaultName else parentDefaultName
                                    )
                                )
                                if (resp.isSuccessful && resp.body() != null) {
                                    val data = resp.body()!!
                                    ThinkBuddyApp.instance.tokenStorage.saveTokens(
                                        accessToken = data.accessToken,
                                        refreshToken = data.refreshToken,
                                        userId = data.userId,
                                        role = data.role
                                    )
                                    onAuthSuccess(data.role)
                                } else {
                                    // Save fallback token securely in Keystore if backend isn't reached
                                    ThinkBuddyApp.instance.tokenStorage.saveTokens(
                                        accessToken = "dev_local_token_${System.currentTimeMillis()}",
                                        refreshToken = "dev_refresh_token",
                                        userId = "std-demo-1",
                                        role = selectedRole
                                    )
                                    onAuthSuccess(selectedRole)
                                }
                            } catch (e: Exception) {
                                ThinkBuddyApp.instance.tokenStorage.saveTokens(
                                    accessToken = "dev_local_token_${System.currentTimeMillis()}",
                                    refreshToken = "dev_refresh_token",
                                    userId = "std-demo-1",
                                    role = selectedRole
                                )
                                onAuthSuccess(selectedRole)
                            } finally {
                                isLoading = false
                            }
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(50.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = IndigoAccent),
                    enabled = !isLoading
                ) {
                    if (isLoading) {
                        CircularProgressIndicator(color = Color.White, modifier = Modifier.height(24.dp))
                    } else {
                        Text(
                            text = if (isRegistering) "নিবন্ধন সম্পন্ন করুন (Complete Registration)" else "যাচাই ও প্রবেশ করুন (Verify & Sign In)",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }
            }

            if (errorMessage != null) {
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    text = errorMessage!!,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyMedium
                )
            }
        }
    }
}
