package com.thinkbuddy.app.ui.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thinkbuddy.app.ui.theme.AmberGold
import com.thinkbuddy.app.ui.theme.BorderDark
import com.thinkbuddy.app.ui.theme.CoralDestructive
import com.thinkbuddy.app.ui.theme.EmeraldSuccess
import com.thinkbuddy.app.ui.theme.SurfaceDark
import com.thinkbuddy.app.ui.theme.TealPrimary

@Composable
fun ProfileScreen(
    userEmail: String,
    userRole: String,
    isParent: Boolean,
    onRoleSwitch: ((String) -> Unit)? = null,
    onLogout: () -> Unit
) {
    var offlineSyncEnabled by remember { mutableStateOf(true) }
    var flagSecureEnabled by remember { mutableStateOf(true) }
    var selectedLanguage by remember { mutableStateOf("bn") } // "bn" or "en"
    var linkCode by remember { mutableStateOf("TB-789-KID") }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .verticalScroll(rememberScrollState())
            .padding(20.dp)
    ) {
        // Top Header
        Text(
            text = if (selectedLanguage == "bn") "প্রোফাইল ও সেটিংস" else "Profile & Settings",
            style = MaterialTheme.typography.titleLarge,
            fontSize = 24.sp
        )

        Spacer(modifier = Modifier.height(20.dp))

        // Profile Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = SurfaceDark),
            shape = RoundedCornerShape(16.dp),
            border = CardDefaults.outlinedCardBorder().copy(brush = androidx.compose.ui.graphics.SolidColor(BorderDark))
        ) {
            Row(
                modifier = Modifier.padding(16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .size(60.dp)
                        .clip(CircleShape)
                        .background(TealPrimary.copy(alpha = 0.2f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = Icons.Default.Person,
                        contentDescription = "User Avatar",
                        tint = TealPrimary,
                        modifier = Modifier.size(36.dp)
                    )
                }

                Spacer(modifier = Modifier.width(16.dp))

                Column {
                    Text(
                        text = if (isParent) "অভিভাবক অ্যাকাউন্ট" else "শিক্ষার্থী অ্যাকাউন্ট",
                        fontWeight = FontWeight.Bold,
                        fontSize = 17.sp,
                        color = Color.White
                    )
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        text = userEmail.ifBlank { "rahim@example.com" },
                        fontSize = 14.sp,
                        color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f)
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "রোল: ${userRole.uppercase()}",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = TealPrimary
                    )
                    if (onRoleSwitch != null) {
                        Spacer(modifier = Modifier.height(6.dp))
                        OutlinedButton(
                            onClick = {
                                val nextRole = if (userRole == "parent") "student" else "parent"
                                onRoleSwitch(nextRole)
                            },
                            shape = RoundedCornerShape(8.dp),
                            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 8.dp, vertical = 2.dp)
                        ) {
                            Text(
                                text = if (userRole == "parent") "শিক্ষার্থী মোডে যান (Switch)" else "অভিভাবক মোডে যান (Switch)",
                                fontSize = 11.sp,
                                color = TealPrimary
                            )
                        }
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(20.dp))

        // Parent / Student Family Linking Section
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = SurfaceDark),
            shape = RoundedCornerShape(16.dp),
            border = CardDefaults.outlinedCardBorder().copy(brush = androidx.compose.ui.graphics.SolidColor(BorderDark))
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    text = if (isParent) "সন্তানের সাথে সংযোগ (Link Code)" else "প্যারেন্ট লিংক কোড",
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 16.sp,
                    color = Color.White
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = if (isParent)
                        "এই কোডটি আপনার শিক্ষার্থীর অ্যাপে প্রবেশ করালে অ্যাকাউন্ট সংযুক্ত হবে।"
                    else
                        "অভিভাবকের সাথে সংযুক্ত থাকলে আপনার পড়ার রুটিন ও কুইজ রিপোর্ট সিঙ্ক হবে।",
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f)
                )

                Spacer(modifier = Modifier.height(14.dp))

                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .background(Color.Black.copy(alpha = 0.4f))
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = linkCode,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        fontSize = 18.sp,
                        color = AmberGold
                    )
                    IconButton(onClick = { /* share */ }) {
                        Icon(imageVector = Icons.Default.Share, contentDescription = "Share", tint = TealPrimary)
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(20.dp))

        // App Security & Hardware Settings
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = SurfaceDark),
            shape = RoundedCornerShape(16.dp),
            border = CardDefaults.outlinedCardBorder().copy(brush = androidx.compose.ui.graphics.SolidColor(BorderDark))
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    text = "নিরাপত্তা ও হার্ডওয়্যার সেটিংস",
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 16.sp,
                    color = Color.White
                )

                Spacer(modifier = Modifier.height(14.dp))

                // FLAG_SECURE toggle
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(text = "স্ক্রিনশট ব্লকিং (FLAG_SECURE)", fontWeight = FontWeight.Medium, color = Color.White)
                        Text(
                            text = "কুইজ চলাকালীন স্ক্রিনশট ও রেকর্ডিং ব্লক করে",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.6f)
                        )
                    }
                    Switch(
                        checked = flagSecureEnabled,
                        onCheckedChange = { flagSecureEnabled = it },
                        colors = SwitchDefaults.colors(checkedThumbColor = TealPrimary)
                    )
                }

                HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), color = BorderDark)

                // Encrypted Storage Info
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(text = "হার্ডওয়্যার কী-স্টোর (Android Keystore)", fontWeight = FontWeight.Medium, color = Color.White)
                        Text(
                            text = "টোকেন ও সেশন ডেটা AES-256 দিয়ে নিরাপদে এনক্রিপ্টেড",
                            fontSize = 12.sp,
                            color = EmeraldSuccess
                        )
                    }
                    Icon(imageVector = Icons.Default.Lock, contentDescription = "Encrypted", tint = EmeraldSuccess)
                }
            }
        }

        Spacer(modifier = Modifier.height(20.dp))

        // Language Switcher
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = SurfaceDark),
            shape = RoundedCornerShape(16.dp),
            border = CardDefaults.outlinedCardBorder().copy(brush = androidx.compose.ui.graphics.SolidColor(BorderDark))
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(text = "ভাষা নির্বাচন (Language)", fontWeight = FontWeight.SemiBold, fontSize = 16.sp, color = Color.White)
                Spacer(modifier = Modifier.height(10.dp))
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Button(
                        onClick = { selectedLanguage = "bn" },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = if (selectedLanguage == "bn") TealPrimary else Color.Transparent
                        ),
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(10.dp),
                        border = androidx.compose.foundation.BorderStroke(1.dp, if (selectedLanguage == "bn") TealPrimary else BorderDark)
                    ) {
                        Text(text = "বাংলা", color = Color.White)
                    }
                    Button(
                        onClick = { selectedLanguage = "en" },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = if (selectedLanguage == "en") TealPrimary else Color.Transparent
                        ),
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(10.dp),
                        border = androidx.compose.foundation.BorderStroke(1.dp, if (selectedLanguage == "en") TealPrimary else BorderDark)
                    ) {
                        Text(text = "English", color = Color.White)
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(30.dp))

        // Logout Button
        Button(
            onClick = onLogout,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            colors = ButtonDefaults.buttonColors(containerColor = CoralDestructive),
            shape = RoundedCornerShape(14.dp)
        ) {
            Icon(imageVector = Icons.AutoMirrored.Filled.ExitToApp, contentDescription = "Logout")
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = if (selectedLanguage == "bn") "লগআউট করুন" else "Log Out",
                fontWeight = FontWeight.Bold,
                fontSize = 16.sp
            )
        }

        Spacer(modifier = Modifier.height(20.dp))
    }
}
