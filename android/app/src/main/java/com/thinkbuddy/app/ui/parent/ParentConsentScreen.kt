package com.thinkbuddy.app.ui.parent

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thinkbuddy.app.ui.theme.AmberGold
import com.thinkbuddy.app.ui.theme.BackgroundDark
import com.thinkbuddy.app.ui.theme.BorderDark
import com.thinkbuddy.app.ui.theme.EmeraldSuccess
import com.thinkbuddy.app.ui.theme.SurfaceDark
import com.thinkbuddy.app.ui.theme.TealPrimary

/**
 * Parental Consent Screen (docs/08_CLIENT_PLATFORM_GUIDE.md §7)
 *
 * Requirements:
 * - Parental consent screen at onboarding.
 * - Clear disclosure of minimal child data collection, zero third-party trackers, zero ads.
 * - Full compliance with Bangladeshi child data protection norms and Rule 15 (Log, don't leak).
 */
@Composable
fun ParentConsentScreen(
    onConsentAccepted: () -> Unit = {},
    onBack: () -> Unit = {}
) {
    var hasAgreedToTerms by remember { mutableStateOf(false) }
    var hasAgreedToDataPolicy by remember { mutableStateOf(false) }

    val canProceed = hasAgreedToTerms && hasAgreedToDataPolicy

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = BackgroundDark
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(20.dp)
                .verticalScroll(rememberScrollState())
        ) {
            // Top App Bar
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = onBack) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = "ফিরে যান",
                        tint = Color.White
                    )
                }
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "অভিভাবক সম্মতি ও নিরাপত্তা",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color.White,
                    modifier = Modifier.semantics { heading() }
                )
            }

            Spacer(modifier = Modifier.height(20.dp))

            // Main Security Banner
            Card(
                colors = CardDefaults.cardColors(containerColor = SurfaceDark),
                border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark),
                shape = RoundedCornerShape(16.dp)
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(48.dp)
                                .background(TealPrimary.copy(alpha = 0.15f), RoundedCornerShape(12.dp)),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                Icons.Default.Shield,
                                contentDescription = "নিরাপত্তা ঢাল",
                                tint = TealPrimary,
                                modifier = Modifier.size(28.dp)
                            )
                        }
                        Spacer(modifier = Modifier.width(14.dp))
                        Column {
                            Text(
                                text = "শিক্ষার্থী ডেটা সুরক্ষা নীতিমালা",
                                fontWeight = FontWeight.Bold,
                                color = Color.White,
                                fontSize = 16.sp
                            )
                            Text(
                                text = "ThinkBuddy অপ্রাপ্তবয়স্কদের ডেটা সুরক্ষায় প্রতিশ্রুতিবদ্ধ",
                                fontSize = 12.sp,
                                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(18.dp))

                    ConsentFeatureRow(
                        title = "কোনো বিজ্ঞাপন বা ট্র্যাকার নেই",
                        description = "অ্যাপে কোনো তৃতীয় পক্ষের অ্যানালিটিক্স, অ্যাডভার্টাইজিং এসডিকে বা চাইল্ড ট্র্যাকিং নেই।"
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    ConsentFeatureRow(
                        title = "হার্ডওয়্যার-সমর্থিত নিরাপত্তা",
                        description = "লগইন সেশন ও অথরাইজেশন টোকেন সরাসরি অ্যান্ড্রয়েড কী-স্টোরে সুরক্ষিত থাকে।"
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    ConsentFeatureRow(
                        title = "পড়াশোনা ও কুইজের সীমানা",
                        description = "এআই চ্যাট শুধুমাত্র জাতীয় শিক্ষাক্রমের পাঠ্যবইয়ের বিষয়বস্তুর মধ্যে সীমাবদ্ধ।"
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    ConsentFeatureRow(
                        title = "ডেটা এক্সপোর্ট ও মুছে ফেলার অধিকার",
                        description = "অভিভাবক যেকোনো সময় সন্তানের অগ্রগতি ডেটা ডাউনলোড বা স্থায়ীভাবে মুছে দিতে পারেন।"
                    )
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Checkbox 1
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Checkbox(
                    checked = hasAgreedToTerms,
                    onCheckedChange = { hasAgreedToTerms = it },
                    colors = CheckboxDefaults.colors(
                        checkedColor = TealPrimary,
                        uncheckedColor = BorderDark
                    )
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "আমি প্রত্যয়ন করছি যে আমি শিক্ষার্থীর আইনগত অভিভাবক এবং ThinkBuddy ব্যবহারে সম্মতি দিচ্ছি।",
                    fontSize = 13.sp,
                    color = Color.White,
                    lineHeight = 18.sp
                )
            }

            // Checkbox 2
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Checkbox(
                    checked = hasAgreedToDataPolicy,
                    onCheckedChange = { hasAgreedToDataPolicy = it },
                    colors = CheckboxDefaults.colors(
                        checkedColor = TealPrimary,
                        uncheckedColor = BorderDark
                    )
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "সন্তানের পড়ার সময়সূচী, অগ্রগতি ও মূল্যায়ন তথ্য অভিভাবক ড্যাশবোর্ডে প্রদর্শনে আমি সম্মত।",
                    fontSize = 13.sp,
                    color = Color.White,
                    lineHeight = 18.sp
                )
            }

            Spacer(modifier = Modifier.height(30.dp))

            // Consent Button
            Button(
                onClick = onConsentAccepted,
                enabled = canProceed,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(50.dp),
                colors = ButtonDefaults.buttonColors(containerColor = TealPrimary),
                shape = RoundedCornerShape(12.dp)
            ) {
                Icon(Icons.Default.CheckCircle, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "সম্মতি প্রদান করুন ও এগিয়ে যান",
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp
                )
            }
        }
    }
}

@Composable
private fun ConsentFeatureRow(title: String, description: String) {
    Row(verticalAlignment = Alignment.Top) {
        Icon(
            Icons.Default.CheckCircle,
            contentDescription = null,
            tint = EmeraldSuccess,
            modifier = Modifier
                .size(18.dp)
                .padding(top = 2.dp)
        )
        Spacer(modifier = Modifier.width(10.dp))
        Column {
            Text(text = title, fontWeight = FontWeight.Bold, color = Color.White, fontSize = 13.sp)
            Text(
                text = description,
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                lineHeight = 15.sp
            )
        }
    }
}
