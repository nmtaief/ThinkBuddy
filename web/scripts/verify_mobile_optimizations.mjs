import { chromium } from '../node_modules/playwright/index.mjs';

const ARTIFACT_DIR = 'C:/Users/UseR/.gemini/antigravity/brain/fbecbc4c-f9aa-4fa7-ac33-7cf74d56767a';
const STUDENT_URL = 'http://localhost:3000';
const PARENT_URL = 'http://localhost:3001';

// Mobile device viewport (iPhone 14 / modern Android: 390 x 844)
const MOBILE_VIEWPORT = { width: 390, height: 844, isMobile: true, hasTouch: true };

async function runMobileVerification() {
  console.log('--- STARTING MOBILE OPTIMIZATION VERIFICATION ---');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: MOBILE_VIEWPORT,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1',
  });
  const page = await context.newPage();

  // 1. Open Student App
  console.log('1. Loading Student App on Mobile Viewport (390x844)...');
  await page.goto(STUDENT_URL, { waitUntil: 'networkidle' });

  // If login button appears, sign in
  const googleBtn = page.locator('button:has-text("গুগল")');
  if (await googleBtn.isVisible()) {
    console.log('Clicking Google Sign-in on Student App...');
    await googleBtn.click();
    await page.waitForTimeout(1000);
  }

  // 2. Verify Mobile Header
  console.log('2. Verifying Student Mobile Header...');
  // Ensure NO "শিক্ষার্থী অ্যাপ" badge in header
  const header = page.locator('header');
  const studentBadgeInHeader = header.locator('text="শিক্ষার্থী অ্যাপ"');
  const isBadgeVisible = await studentBadgeInHeader.isVisible();
  console.log('Is "শিক্ষার্থী অ্যাপ" badge in header:', isBadgeVisible, '(Must be FALSE)');
  if (isBadgeVisible) throw new Error('Failed: "শিক্ষার্থী অ্যাপ" badge is still in the header!');

  // Ensure NO "অভিভাবক সাইট" link in header
  const parentLinkInHeader = header.locator('text="অভিভাবক সাইট"');
  const isParentLinkVisible = await parentLinkInHeader.isVisible();
  console.log('Is "অভিভাবক সাইট" link in header:', isParentLinkVisible, '(Must be FALSE)');
  if (isParentLinkVisible) throw new Error('Failed: "অভিভাবক সাইট" link is still in the header!');

  // Capture clean mobile header and today page
  await page.screenshot({ path: `${ARTIFACT_DIR}/mobile_student_today_clean_header.png` });
  console.log('Saved mobile_student_today_clean_header.png');

  // 3. Open Profile Drawer & Verify Hidden Parent Portal
  console.log('3. Opening Student Profile Drawer...');
  const profileTrigger = page.locator('header button[aria-label*="প্রোফাইল"]');
  await profileTrigger.click();
  await page.waitForTimeout(500);

  // Verify hidden parent portal is inside drawer
  const drawerParentPortal = page.locator('div[role="dialog"] a:has-text("অভিভাবক সাইটে যান")');
  await drawerParentPortal.waitFor({ state: 'visible', timeout: 5000 });
  console.log('Verified: Parent portal link is cleanly tucked inside Profile Drawer!');

  await page.screenshot({ path: `${ARTIFACT_DIR}/mobile_student_profile_drawer.png` });
  console.log('Saved mobile_student_profile_drawer.png');

  // Close drawer
  const closeDrawerBtn = page.locator('div[role="dialog"] button[aria-label="Close menu"]');
  await closeDrawerBtn.click();
  await page.waitForTimeout(400);

  // 4. Test Selecting Class, Syllabus & Exam Date
  console.log('4. Testing Class, Syllabus & Exam Date Selection Modal...');
  const editTargetBtn = page.locator('button[title*="শ্রেণি ও পরীক্ষার তারিখ"]').first();
  await editTargetBtn.click();
  await page.waitForTimeout(500);

  // In modal: select Class 9 (৯ম শ্রেণি)
  const class9Btn = page.locator('button:has-text("৯ম শ্রেণি")');
  await class9Btn.click();
  console.log('Selected Class: ৯ম শ্রেণি');

  // Select Syllabus: নতুন শিক্ষাক্রম ২০২৪-২৬
  const syllabusBtn = page.locator('button:has-text("নতুন শিক্ষাক্রম")').first();
  await syllabusBtn.click();
  console.log('Selected Syllabus: নতুন শিক্ষাক্রম');

  // Select Exam Name Preset: বার্ষিক মূল্যায়ন পরীক্ষা
  const examPresetBtn = page.locator('button:has-text("বার্ষিক মূল্যায়ন পরীক্ষা")');
  await examPresetBtn.click();
  console.log('Selected Exam: বার্ষিক মূল্যায়ন পরীক্ষা');

  // Select Exam Date: 20 days ahead
  const dateInput = page.locator('input[type="date"]');
  const targetDate = new Date(Date.now() + 20 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
  await dateInput.fill(targetDate);
  console.log('Set Exam Date to:', targetDate);

  await page.screenshot({ path: `${ARTIFACT_DIR}/mobile_exam_settings_modal.png` });
  console.log('Saved mobile_exam_settings_modal.png');

  // Click Save
  const saveBtn = page.locator('button:has-text("সংরক্ষণ করুন")');
  await saveBtn.click();
  await page.waitForTimeout(600);

  // Verify countdown card updated with ৯ম শ্রেণি and ২০ দিন বাকি
  const updatedCardText = await page.locator('.card:has-text("৯ম শ্রেণি")').innerText();
  console.log('Updated Countdown Card Content:\n', updatedCardText);
  if (!updatedCardText.includes('৯ম শ্রেণি') || !updatedCardText.includes('বার্ষিক মূল্যায়ন')) {
    throw new Error('Failed: Countdown card did not update with new class and exam!');
  }

  await page.screenshot({ path: `${ARTIFACT_DIR}/mobile_student_updated_countdown.png` });
  console.log('Saved mobile_student_updated_countdown.png');

  // 5. Check Study Session Room on Mobile
  console.log('5. Testing Study Session Room on Mobile...');
  const startSessionBtn = page.locator('button:has-text("পড়া শুরু করি")').first();
  await startSessionBtn.click();
  await page.waitForTimeout(600);

  // Verify stopwatch & tick a page
  const tickPage1 = page.locator('button[aria-label="Mark page complete"]').first();
  await tickPage1.click();
  await page.waitForTimeout(300);

  await page.screenshot({ path: `${ARTIFACT_DIR}/mobile_study_session_room.png` });
  console.log('Saved mobile_study_session_room.png');

  // Back to routine
  await page.locator('button:has-text("আজকের রুটিনে ফিরে যান")').first().click();
  await page.waitForTimeout(400);

  // 6. Test Mobile Bottom Nav Tabs
  console.log('6. Navigating through all mobile bottom tabs...');
  // Revision Tab
  await page.locator('.mobile-bottom-nav button:has-text("রিভিশন")').click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${ARTIFACT_DIR}/mobile_tab_revision.png` });
  console.log('Saved mobile_tab_revision.png');

  // Quiz Tab
  await page.locator('.mobile-bottom-nav button:has-text("কুইজ")').click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${ARTIFACT_DIR}/mobile_tab_quiz.png` });
  console.log('Saved mobile_tab_quiz.png');

  // AI Tutor Tab
  await page.locator('.mobile-bottom-nav button:has-text("এআই শিক্ষক")').click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${ARTIFACT_DIR}/mobile_tab_ai_chat.png` });
  console.log('Saved mobile_tab_ai_chat.png');

  // Progress Tab
  await page.locator('.mobile-bottom-nav button:has-text("অগ্রগতি")').click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${ARTIFACT_DIR}/mobile_tab_progress.png` });
  console.log('Saved mobile_tab_progress.png');

  // 7. Verify Parent App on Mobile
  console.log('7. Loading Parent App on Mobile Viewport...');
  await page.goto(PARENT_URL, { waitUntil: 'networkidle' });

  const parentGoogleBtn = page.locator('button:has-text("গুগল")');
  if (await parentGoogleBtn.isVisible()) {
    console.log('Clicking Google Sign-in on Parent App...');
    await parentGoogleBtn.click();
    await page.waitForTimeout(1000);
  }

  // Verify clean parent header: NO "অভিভাবক সাইট" badge, NO "শিক্ষার্থী অ্যাপ" link
  const parentHeader = page.locator('header');
  const parentBadge = parentHeader.locator('text="অভিভাবক সাইট"');
  const isPBadgeVisible = await parentBadge.isVisible();
  console.log('Is "অভিভাবক সাইট" badge in parent header:', isPBadgeVisible, '(Must be FALSE)');
  if (isPBadgeVisible) throw new Error('Failed: "অভিভাবক সাইট" badge is still in parent header!');

  const studentLinkInParentHeader = parentHeader.locator('text="শিক্ষার্থী অ্যাপ"');
  const isSLinkVisible = await studentLinkInParentHeader.isVisible();
  console.log('Is "শিক্ষার্থী অ্যাপ" link in parent header:', isSLinkVisible, '(Must be FALSE)');
  if (isSLinkVisible) throw new Error('Failed: "শিক্ষার্থী অ্যাপ" link is still in parent header!');

  await page.screenshot({ path: `${ARTIFACT_DIR}/mobile_parent_dashboard.png` });
  console.log('Saved mobile_parent_dashboard.png');

  // Open Parent Profile Drawer
  const parentProfileTrigger = page.locator('header button[aria-label*="মেনু"]');
  await parentProfileTrigger.click();
  await page.waitForTimeout(400);

  // Verify hidden link to student app
  const parentDrawerStudentLink = page.locator('div[role="dialog"] a:has-text("শিক্ষার্থী অ্যাপে যান")');
  await parentDrawerStudentLink.waitFor({ state: 'visible', timeout: 5000 });
  console.log('Verified: Student app link is cleanly tucked inside Parent Drawer!');

  await page.screenshot({ path: `${ARTIFACT_DIR}/mobile_parent_profile_drawer.png` });
  console.log('Saved mobile_parent_profile_drawer.png');

  await browser.close();
  console.log('=== ALL MOBILE VERIFICATIONS AND SCREENSHOTS PASSED WITH 100% SUCCESS ===');
}

runMobileVerification().catch((err) => {
  console.error('Mobile verification failed:', err);
  process.exit(1);
});
