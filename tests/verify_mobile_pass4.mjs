import { createRequire } from "module";
const require = createRequire(import.meta.url);
const { chromium } = require("../web/node_modules/@playwright/test");
import fs from "fs";
import path from "path";

const ARTIFACT_DIR = "C:/Users/UseR/.gemini/antigravity/brain/da5ef18b-be24-4494-88af-3250aded895a";

async function run() {
  console.log("Launching browser at viewport 390x844 (Mobile Phone)...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
  });

  const page = await context.newPage();

  console.log("Navigating to http://localhost:3000...");
  await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);

  // If on login page, click student role submit button
  const submitLogin = page.locator("#btn-login-submit").first();
  if (await submitLogin.isVisible()) {
    console.log("Logging into student portal...");
    await submitLogin.click();
    await page.waitForTimeout(2000);
  }

  // Click on "সহায়ক এআই" tab in bottom nav or nav bar
  console.log("Navigating to AI Chat tab...");
  const chatTab = page.locator("button:has-text('সহায়ক এআই'), a:has-text('সহায়ক এআই'), button:has-text('AI Tutor')").first();
  if (await chatTab.isVisible()) {
    await chatTab.click();
    await page.waitForTimeout(2000);
  } else {
    // Navigate via query param
    await page.goto("http://localhost:3000/?tab=chat", { waitUntil: "networkidle" });
    await page.waitForTimeout(2000);
  }

  // ----------------------------------------------------
  // Scenario C: "Ssc books?"
  // ----------------------------------------------------
  console.log("--- Testing Scenario C: 'Ssc books?' ---");
  const input = page.locator("input[type='text']").first();
  await input.fill("Ssc books?");
  const sendBtn = page.locator("button[aria-label='জিজ্ঞাসা করুন'], button:has-text('Send')").first();
  await sendBtn.click();

  // Wait for streaming to finish (stop button disappears, send button reappears)
  console.log("Waiting for Scenario C response...");
  await page.waitForSelector("button[aria-label='জিজ্ঞাসা করুন']", { timeout: 60000 });
  await page.waitForTimeout(3000);

  const shotC = path.join(ARTIFACT_DIR, "mobile_pass4_scenario_c.png");
  await page.screenshot({ path: shotC, fullPage: false });
  console.log(`Saved screenshot: ${shotC}`);

  const messagesC = await page.locator(".math-rendered-text").allInnerTexts();
  console.log("Scenario C Response:\n", messagesC[messagesC.length - 1]);

  // ----------------------------------------------------
  // Scenario A: "Class 8 math boi er chapter 1 er 3 no kore deo"
  // ----------------------------------------------------
  console.log("\n--- Testing Scenario A (Turn 1): Class 8 Math Chapter 1 Question 3 ---");
  await input.fill("Class 8 math boi er chapter 1 er 3 no kore deo");
  await sendBtn.click();

  console.log("Waiting for Scenario A Turn 1 response...");
  await page.waitForSelector("button[aria-label='জিজ্ঞাসা করুন']", { timeout: 60000 });
  await page.waitForTimeout(3000);

  const shotA1 = path.join(ARTIFACT_DIR, "mobile_pass4_scenario_a_turn1.png");
  await page.screenshot({ path: shotA1, fullPage: false });
  console.log(`Saved screenshot: ${shotA1}`);

  const messagesA1 = await page.locator(".math-rendered-text").allInnerTexts();
  console.log("Scenario A Turn 1 Response:\n", messagesA1[messagesA1.length - 1]);

  // Turn 2: "Onushiloni theke question 3 kore deo"
  console.log("\n--- Testing Scenario A (Turn 2): Co-reference 'Onushiloni theke question 3 kore deo' ---");
  await input.fill("Onushiloni theke question 3 kore deo");
  await sendBtn.click();

  console.log("Waiting for Scenario A Turn 2 response...");
  await page.waitForSelector("button[aria-label='জিজ্ঞাসা করুন']", { timeout: 60000 });
  await page.waitForTimeout(3000);

  const shotA2 = path.join(ARTIFACT_DIR, "mobile_pass4_scenario_a_turn2.png");
  await page.screenshot({ path: shotA2, fullPage: false });
  console.log(`Saved screenshot: ${shotA2}`);

  const messagesA2 = await page.locator(".math-rendered-text").allInnerTexts();
  console.log("Scenario A Turn 2 Response:\n", messagesA2[messagesA2.length - 1]);

  // ----------------------------------------------------
  // Scenario B: "SSC trigonometry 9.1 er 5 no. Answer ta bujhiye deo"
  // ----------------------------------------------------
  console.log("\n--- Testing Scenario B: SSC trigonometry 9.1 er 5 no ---");
  await input.fill("SSC trigonometry 9.1 er 5 no. Answer ta bujhiye deo");
  await sendBtn.click();

  console.log("Waiting for Scenario B response...");
  await page.waitForSelector("button[aria-label='জিজ্ঞাসা করুন']", { timeout: 60000 });
  await page.waitForTimeout(3000);

  const shotB = path.join(ARTIFACT_DIR, "mobile_pass4_scenario_b.png");
  await page.screenshot({ path: shotB, fullPage: false });
  console.log(`Saved screenshot: ${shotB}`);

  const messagesB = await page.locator(".math-rendered-text").allInnerTexts();
  console.log("Scenario B Response:\n", messagesB[messagesB.length - 1]);

  // ----------------------------------------------------
  // Scenario D: "Try again"
  // ----------------------------------------------------
  console.log("\n--- Testing Scenario D: 'Try again' ---");
  await input.fill("Try again");
  await sendBtn.click();

  console.log("Waiting for Scenario D response...");
  await page.waitForSelector("button[aria-label='জিজ্ঞাসা করুন']", { timeout: 60000 });
  await page.waitForTimeout(3000);

  const shotD = path.join(ARTIFACT_DIR, "mobile_pass4_scenario_d.png");
  await page.screenshot({ path: shotD, fullPage: false });
  console.log(`Saved screenshot: ${shotD}`);

  const messagesD = await page.locator(".math-rendered-text").allInnerTexts();
  console.log("Scenario D Response:\n", messagesD[messagesD.length - 1]);

  console.log("\nAll 5 mobile test scenarios completed successfully!");
  await browser.close();
}

run().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
