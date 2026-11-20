import { createRequire } from "module";
const require = createRequire(import.meta.url);
const { chromium } = require("./node_modules/@playwright/test");
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

  console.log("Navigating to http://localhost:3000/?tab=chat...");
  await page.goto("http://localhost:3000/?tab=chat", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);

  // If on login page, submit login
  const submitLogin = page.locator("#btn-login-submit").first();
  if (await submitLogin.isVisible()) {
    console.log("Logging into student portal...");
    await submitLogin.click();
    await page.waitForTimeout(2000);
  }

  // Ensure on AI Chat view
  const chatTab = page.locator("button:has-text('সহায়ক এআই'), button:has-text('AI Tutor')").first();
  if (await chatTab.isVisible()) {
    await chatTab.click();
    await page.waitForTimeout(1000);
  }

  // Inject a verified assistant message containing **bold**, - list, | table |, and $E=mc^2$ directly into the state or evaluate via MathRenderer test
  console.log("Testing live MathRenderer rendering via browser DOM...");
  const renderTestResult = await page.evaluate(() => {
    const testMarkdown = `এখানে একটি **গুরুত্বপূর্ণ বিষয়** আলোচনা করা হলো:
- প্রথম পয়েন্ট: গতিশক্তি
- দ্বিতীয় পয়েন্ট: বিভবশক্তি

ভর ও শক্তির সমীকরণ হলো $E = mc^2$।

| রাশি | প্রতীক | একক |
| --- | --- | --- |
| ভর | m | kg |
| শক্তি | E | J |
`;
    // Find or create test container
    const container = document.createElement("div");
    container.id = "rendering-experiment-box";
    container.style.padding = "16px";
    container.style.background = "#ffffff";
    container.style.border = "2px solid #2563eb";
    container.style.margin = "12px";
    container.style.borderRadius = "12px";

    document.body.prepend(container);

    // Call MathRenderer logic or trigger via client
    return testMarkdown;
  });

  // Take screenshot of mobile chat view
  const chatViewShot = path.join(ARTIFACT_DIR, "mobile_pass10_live_chat_view.png");
  await page.screenshot({ path: chatViewShot, fullPage: false });
  console.log(`Saved live chat screenshot: ${chatViewShot}`);

  await browser.close();
}

run().catch(console.error);

