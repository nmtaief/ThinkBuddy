import { test, expect } from "@playwright/test";

test.describe("Responsive User Flows & Learning Loop", () => {
  test("Student Today schedule loads with streak and textbook citations", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Streak badge visible
    await expect(page.getByText(/দিনের ধারাবাহিকতা/i)).toBeVisible();

    // Today's tasks visible with printed page numbers
    await expect(page.getByText(/সালোকসংশ্লেষণ ও ক্লোরোপ্লাস্টের ভূমিকা/i)).toBeVisible();
    await expect(page.getByText(/মুদ্রিত পৃষ্ঠা নং/i).first()).toBeVisible();
  });

  test("Language toggle seamlessly switches between Bangla and English", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Toggle to English
    const langBtn = page.getByRole("button", { name: /English-এ পরিবর্তন করুন/i });
    await expect(langBtn).toBeVisible();
    await langBtn.click();

    // Verify English text
    await expect(page.getByText(/Today's Study Plan/i).first()).toBeVisible();
    await expect(page.getByText(/Daily Streak/i)).toBeVisible();

    // Toggle back to Bangla
    const banglaBtn = page.getByRole("button", { name: /বাংলায় পরিবর্তন করুন/i });
    await expect(banglaBtn).toBeVisible();
    await banglaBtn.click();

    // Verify Bangla text restored
    await expect(page.getByText(/আজকের অধ্যয়ন পরিকল্পনা/i)).toBeVisible();
  });

  test("Practice quiz runner provides immediate feedback and explanation", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Open Quiz tab
    await page.locator('[data-testid="nav-quiz"]:visible, [data-testid="bottom-nav-quiz"]:visible').first().click({ force: true });

    // Start practice quiz
    const startBtn = page.getByRole("button", { name: /অনুশীলন শুরু করুন/i });
    if (await startBtn.isVisible()) {
      await startBtn.click();
    }

    // Select option (Oxygen)
    const option = page.getByRole("button", { name: /অক্সিজেন/i });
    await expect(option).toBeVisible();
    await option.click();

    // Submit answer
    await page.getByRole("button", { name: /উত্তর জমা দিন/i }).click();

    // Explanation or review feedback visible
    await expect(page.getByText(/অনুশীলনী কুইজ সমাপ্ত!|সঠিক উত্তর!/i)).toBeVisible();
  });

  test("AI Chat streams response with textbook citation chips", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Open Chat tab
    await page.locator('[data-testid="nav-chat"]:visible, [data-testid="bottom-nav-chat"]:visible').first().click({ force: true });

    // Input question
    const chatInput = page.getByPlaceholder(/পাঠ্যবই থেকে যেকোনো প্রশ্ন জিজ্ঞাসা করুন.../i);
    await expect(chatInput).toBeVisible();
    await chatInput.fill("সালোকসংশ্লেষণ কি?");

    // Send
    await page.getByRole("button", { name: /Ask/i }).or(page.locator("button[aria-label='জিজ্ঞাসা করুন']")).click();

    // Verify citation appears
    await expect(page.getByText(/পাঠ্যবই রেফারেন্স ও সূত্র:/i)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/সাধারণ বিজ্ঞান \(Class 7\)/i).first()).toBeVisible();
    await expect(page.getByText(/পৃষ্ঠা নং ৪২/i).first()).toBeVisible();
  });

  test("Parent switch, dashboard metrics, and study setup editor", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Switch to Parent Role
    await page.getByRole("button", { name: /অভিভাবক \(Parent\)/i }).click();

    // Dashboard metrics visible
    await expect(page.getByText(/আজকের কাজ সমাপ্তি/i)).toBeVisible();
    await expect(page.getByText(/সামগ্রিক বিষয় দক্ষতা/i)).toBeVisible();

    // Navigate to Study Setup
    await page.locator('[data-testid="nav-study-setup"]:visible, [data-testid="bottom-nav-study-setup"]:visible').first().click({ force: true });
    await expect(page.getByText(/বিদ্যালয় দিবসের দৈনিক পড়ার সময়/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /সেটআপ সংরক্ষণ করুন/i })).toBeVisible();
  });
});
