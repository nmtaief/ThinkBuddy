import { chromium } from "@playwright/test";

async function testAndCapture() {
  const browser = await chromium.launch();
  const artifactDir = "C:/Users/UseR/.gemini/antigravity/brain/fbecbc4c-f9aa-4fa7-ac33-7cf74d56767a";

  console.log("=== TEST 1: Student App - Login & Merged Today Page ===");
  const studentPage = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await studentPage.goto("http://127.0.0.1:3000");
  await studentPage.waitForLoadState("networkidle");

  // Capture Login view first if visible
  const googleBtn = studentPage.locator('button:has-text("গুগল দিয়ে প্রবেশ করুন"), button:has-text("Sign In with Google")').first();
  if (await googleBtn.isVisible()) {
    console.log("Capturing Student Login Page...");
    await studentPage.screenshot({ path: `${artifactDir}/student_login_page.png` });
    console.log("Clicking Google Sign-In on Student App...");
    await googleBtn.click();
    await studentPage.waitForTimeout(1000);
  }

  await studentPage.screenshot({ path: `${artifactDir}/student_merged_today_desktop.png` });
  console.log("Saved student_merged_today_desktop.png");

  console.log("=== TEST 2: Study Session Room (Stopwatch, Page Ticks, Fixed Badges) ===");
  const startStudyBtn = studentPage.locator('button:has-text("পড়া শুরু করি"), button:has-text("Start Study Session")').first();
  if (await startStudyBtn.isVisible()) {
    await startStudyBtn.click();
    await studentPage.waitForTimeout(800);

    // Tick the first page
    const firstPageCheck = studentPage.locator('button[aria-label="Mark page complete"]').first();
    if (await firstPageCheck.isVisible()) {
      await firstPageCheck.click();
      await studentPage.waitForTimeout(500);
    }

    await studentPage.screenshot({ path: `${artifactDir}/student_study_session_room.png` });
    console.log("Saved student_study_session_room.png");

    // Return back to today
    const backBtn = studentPage.locator('button:has-text("আজকের রুটিনে ফিরে যান"), button:has-text("Back to Today")').first();
    if (await backBtn.isVisible()) {
      await backBtn.click();
      await studentPage.waitForTimeout(500);
    }
  }

  console.log("=== TEST 3: Language Toggle (Bangla <-> English) ===");
  const langBtn = studentPage.locator('button:has-text("English"), button:has-text("বাংলা")').first();
  if (await langBtn.isVisible()) {
    await langBtn.click();
    await studentPage.waitForTimeout(600);
    await studentPage.screenshot({ path: `${artifactDir}/student_english_view.png` });
    console.log("Saved student_english_view.png");

    // Toggle back to Bangla
    await langBtn.click();
    await studentPage.waitForTimeout(600);
  }

  console.log("=== TEST 4: Dark Mode ===");
  const themeBtn = studentPage.locator('button[aria-label*="mode"], button[aria-label*="dark"]').first();
  if (await themeBtn.isVisible()) {
    await themeBtn.click();
    await studentPage.waitForTimeout(600);
    await studentPage.screenshot({ path: `${artifactDir}/student_dark_mode.png` });
    console.log("Saved student_dark_mode.png");

    // Toggle back to light
    await themeBtn.click();
    await studentPage.waitForTimeout(400);
  }

  console.log("=== TEST 5: Student Mobile View ===");
  const mobilePage = await browser.newPage({ viewport: { width: 375, height: 667 } });
  await mobilePage.goto("http://127.0.0.1:3000");
  await mobilePage.waitForLoadState("networkidle");
  const mobileGoogleBtn = mobilePage.locator('button:has-text("গুগল দিয়ে প্রবেশ করুন"), button:has-text("Sign In with Google")').first();
  if (await mobileGoogleBtn.isVisible()) {
    await mobileGoogleBtn.click();
    await mobilePage.waitForTimeout(1000);
  }
  await mobilePage.screenshot({ path: `${artifactDir}/student_mobile_loggedin_today.png` });
  console.log("Saved student_mobile_loggedin_today.png");

  console.log("=== TEST 6: Parent App - Login & Dashboard ===");
  const parentPage = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await parentPage.goto("http://127.0.0.1:3001");
  await parentPage.waitForLoadState("networkidle");

  const parentGoogleBtn = parentPage.locator('button:has-text("গুগল দিয়ে প্রবেশ করুন"), button:has-text("Sign In with Google")').first();
  if (await parentGoogleBtn.isVisible()) {
    console.log("Capturing Parent Login Page...");
    await parentPage.screenshot({ path: `${artifactDir}/parent_login_page.png` });
    console.log("Clicking Google Sign-In on Parent App...");
    await parentGoogleBtn.click();
    await parentPage.waitForTimeout(1000);
  }

  await parentPage.screenshot({ path: `${artifactDir}/parent_dashboard_desktop.png` });
  console.log("Saved parent_dashboard_desktop.png");

  console.log("=== TEST 7: Parent Link Flow (Entering Student Invite Code) ===");
  const linkModalBtn = parentPage.locator('button:has-text("নতুন সন্তান যুক্ত করুন"), button:has-text("Link a Student")').first();
  if (await linkModalBtn.isVisible()) {
    await linkModalBtn.click();
    await parentPage.waitForTimeout(500);

    const input = parentPage.locator('input[placeholder*="TB-"]').first();
    if (await input.isVisible()) {
      await input.fill("TB-8392");
      const submitLinkBtn = parentPage.locator('button[type="submit"]').first();
      await submitLinkBtn.click();
      await parentPage.waitForTimeout(1000);
    }
    await parentPage.screenshot({ path: `${artifactDir}/parent_link_child_success.png` });
    console.log("Saved parent_link_child_success.png");
  }

  await browser.close();
  console.log("ALL PLAYWRIGHT TESTS AND SCREENSHOTS COMPLETED!");
}

testAndCapture().catch((err) => {
  console.error("Test execution error:", err);
  process.exit(1);
});
