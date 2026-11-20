import { chromium } from "@playwright/test";
import path from "path";

const ARTIFACT_DIR = "C:/Users/UseR/.gemini/antigravity/brain/da5ef18b-be24-4494-88af-3250aded895a";

async function run() {
  console.log("Launching Chrome browser...");
  const browser = await chromium.launch({
    channel: "chrome",
    headless: false,
    slowMo: 100,
  });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    locale: "en-US",
  });
  const page = await context.newPage();

  console.log("Navigating to http://localhost:3000/?tab=chat...");
  await page.goto("http://localhost:3000/?tab=chat", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2000);

  // Switch to English language if present
  const langToggle = page.locator('button:has-text("English"), button:has-text("EN")');
  if (await langToggle.count() > 0 && await langToggle.first().isVisible()) {
    try {
      await langToggle.first().click();
      await page.waitForTimeout(500);
    } catch {}
  }

  // Click on Chat tab
  const chatNav = page.locator('[data-testid="nav-chat"]');
  if (await chatNav.isVisible()) {
    await chatNav.click();
    await page.waitForTimeout(1000);
  }

  const input = page.locator('input[type="text"]');
  await input.waitFor({ state: "visible", timeout: 10000 });

  // Test 1: "I am really bad at English so how can I improve it?"
  console.log("Testing 1: I am really bad at English so how can I improve it?");
  await input.fill("I am really bad at English so how can I improve it?");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(2000);
  await page.waitForFunction(() => !document.querySelector('input[type="text"]')?.disabled, { timeout: 35000 });
  await page.waitForTimeout(2000);

  const shot1 = path.join(ARTIFACT_DIR, "chrome_test_english_improvement.png");
  await page.screenshot({ path: shot1, fullPage: true });
  console.log(`Saved screenshot 1: ${shot1}`);

  // Test 2: "How to improve stat chapter"
  console.log("Testing 2: How to improve stat chapter");
  await input.fill("How to improve stat chapter");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(2000);
  await page.waitForFunction(() => !document.querySelector('input[type="text"]')?.disabled, { timeout: 35000 });
  await page.waitForTimeout(2000);

  const shot2 = path.join(ARTIFACT_DIR, "chrome_test_stat_improvement.png");
  await page.screenshot({ path: shot2, fullPage: true });
  console.log(`Saved screenshot 2: ${shot2}`);

  // Test 3: "its the last chapter of math"
  console.log("Testing 3: its the last chapter of math");
  await input.fill("its the last chapter of math");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(2000);
  await page.waitForFunction(() => !document.querySelector('input[type="text"]')?.disabled, { timeout: 35000 });
  await page.waitForTimeout(2000);

  const shot3 = path.join(ARTIFACT_DIR, "chrome_test_last_chapter_math.png");
  await page.screenshot({ path: shot3, fullPage: true });
  console.log(`Saved screenshot 3: ${shot3}`);

  console.log("Browser test sequence finished successfully!");
  await page.waitForTimeout(2000);
  await browser.close();
}

run().catch((err) => {
  console.error("Test execution failed:", err);
  process.exit(1);
});

