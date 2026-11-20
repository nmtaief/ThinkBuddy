import { chromium } from "@playwright/test";
import path from "path";

const ARTIFACT_DIR = "C:/Users/UseR/.gemini/antigravity/brain/da5ef18b-be24-4494-88af-3250aded895a";

async function run() {
  console.log("Launching Chrome...");
  const browser = await chromium.launch({
    channel: "chrome",
    headless: false,
  });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    locale: "en-US",
  });
  const page = await context.newPage();

  console.log("Navigating to http://localhost:3000/?tab=chat...");
  await page.goto("http://localhost:3000/?tab=chat", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2000);

  const input = page.locator('input[type="text"]');
  await input.waitFor({ state: "visible", timeout: 15000 });

  // 1. Test "How can I improve my math?"
  console.log("Testing Prompt 1: How can I improve my math?");
  await input.fill("How can I improve my math?");
  await page.keyboard.press("Enter");

  await page.waitForTimeout(3000);
  await page.waitForFunction(() => !document.querySelector('input[type="text"]')?.disabled, { timeout: 45000 });
  await page.waitForTimeout(2000);

  const shot1 = path.join(ARTIFACT_DIR, "chrome_rag_test_1.png");
  await page.screenshot({ path: shot1, fullPage: true });
  console.log(`Saved screenshot 1: ${shot1}`);

  // 2. Test "What is the definition of photosynthesis in my science textbook?"
  console.log("Testing Prompt 2: What is photosynthesis?");
  await input.fill("What is the definition of photosynthesis in my science textbook?");
  await page.keyboard.press("Enter");

  await page.waitForTimeout(3000);
  await page.waitForFunction(() => !document.querySelector('input[type="text"]')?.disabled, { timeout: 45000 });
  await page.waitForTimeout(2000);

  const shot2 = path.join(ARTIFACT_DIR, "chrome_rag_test_2.png");
  await page.screenshot({ path: shot2, fullPage: true });
  console.log(`Saved screenshot 2: ${shot2}`);

  console.log("Testing completed successfully.");
  await browser.close();
}

run().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});

