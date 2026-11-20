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

  // Switch to English language if needed
  const langToggle = page.locator('button:has-text("English"), button:has-text("EN")');
  if (await langToggle.count() > 0 && await langToggle.first().isVisible()) {
    try {
      await langToggle.first().click();
      await page.waitForTimeout(500);
    } catch {}
  }

  // Click on the Chat tab if not already active
  const chatNav = page.locator('[data-testid="nav-chat"]');
  if (await chatNav.isVisible()) {
    await chatNav.click();
    await page.waitForTimeout(1000);
  }

  const input = page.locator('input[type="text"]');
  await input.waitFor({ state: "visible", timeout: 10000 });

  // 1. Test "How can I improve my maths"
  console.log("Testing: How can I improve my maths");
  await input.fill("How can I improve my maths");
  await page.keyboard.press("Enter");

  await page.waitForTimeout(3000);
  await page.waitForFunction(() => !document.querySelector('input[type="text"]')?.disabled, { timeout: 30000 });
  await page.waitForTimeout(2000);

  const shot1 = path.join(ARTIFACT_DIR, "chrome_test_maths_improvement.png");
  await page.screenshot({ path: shot1, fullPage: true });
  console.log(`Saved screenshot 1 (Maths Improvement): ${shot1}`);

  // 2. Test specific Class 8 math topic: "What is Pythagoras theorem"
  console.log("Testing: What is Pythagoras theorem");
  await input.fill("What is Pythagoras theorem");
  await page.keyboard.press("Enter");

  await page.waitForTimeout(3000);
  await page.waitForFunction(() => !document.querySelector('input[type="text"]')?.disabled, { timeout: 30000 });
  await page.waitForTimeout(2000);

  const shot2 = path.join(ARTIFACT_DIR, "chrome_test_pythagoras.png");
  await page.screenshot({ path: shot2, fullPage: true });
  console.log(`Saved screenshot 2 (Pythagoras Theorem): ${shot2}`);

  console.log("All tests completed successfully! Closing automated test browser...");
  await page.waitForTimeout(2000);
  await browser.close();
}

run().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
