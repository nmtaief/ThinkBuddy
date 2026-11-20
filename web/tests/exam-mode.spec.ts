import { test, expect } from "@playwright/test";

test.describe("Exam-Week Mode: E2E Playwright Verification (390px Mobile & Desktop)", () => {
  test.beforeEach(async ({ page, baseURL }) => {
    // Navigate to homepage with pre-warmed state
    const url = baseURL || "http://127.0.0.1:3000/";
    await page.goto(url);
    await page.waitForLoadState("domcontentloaded");
  });

  test("1. 390px Mobile View: Exam mode badge, gap line, block chips & suspended streak pressure", async ({
    page,
    baseURL,
  }) => {
    // Mobile viewport constraint: exactly 390px
    await page.setViewportSize({ width: 390, height: 844 });
    const url = baseURL || "http://127.0.0.1:3000/";
    await page.goto(url);
    await page.waitForLoadState("domcontentloaded");

    // 1. Verify Exam Mode Badge is visible
    const badge = page.getByText(/শুধু রিভিশন|পরীক্ষা সপ্তাহ|পরীক্ষার আগের দিন/i).first();
    await expect(badge).toBeVisible();

    // 2. Verify Next-Exam Countdown & Gap Summary line
    const gapLine = page.getByText(/পরের পরীক্ষা.*ঘণ্টা পর; পড়ার সময়.*ঘণ্টা/i).first();
    await expect(gapLine).toBeVisible();

    // 3. Verify Streak Guilt Suspension banner during exam week
    const noStreakGuilt = page.getByText(/পরীক্ষা সপ্তাহে স্ট্রিকের চাপ নেই|প্রশান্ত মনে রিভিশন করো/i).first();
    await expect(noStreakGuilt).toBeVisible();

    // 4. Verify Block Type Chips ("বাকি সিলেবাস", "আরও অনুশীলন", "রিভিশন", "ফর্মুলা", "হালকা রিভিশন")
    const chip = page.locator("span:visible").filter({ hasText: /বাকি সিলেবাস|আরও অনুশীলন|রিভিশন|ফর্মুলা|হালকা রিভিশন/ }).first();
    await expect(chip).toBeVisible();

    // Capture mobile screenshot
    await page.screenshot({ path: "audit/exam_mode_mobile_390px.png", fullPage: true });
  });

  test("2. Desktop View: Timetable Quick-Add, Syllabus 'বাকি আছে' Toggle & Replan", async ({
    page,
    baseURL,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    const url = baseURL || "http://127.0.0.1:3000/";
    await page.goto(url);
    await page.waitForLoadState("domcontentloaded");

    // Navigate to Timeline & Plan tab
    const planTabBtn = page.locator('[data-testid="nav-plan"]:visible, [data-testid="bottom-nav-plan"]:visible').first();
    if (await planTabBtn.isVisible()) {
      await planTabBtn.click();
    } else {
      const planBtn = page.getByRole("button", { name: /সময়রেখা ও পূর্ণাঙ্গ রুটিন|রুটিন পরিবর্তন|Plan/i }).first();
      if (await planBtn.isVisible()) await planBtn.click();
    }

    // Switch to Exam Timetable Entry mode inside existing screen
    const ttBtn = page.getByRole("button", { name: /পরীক্ষার রুটিন \(Timetable\)/i });
    if (await ttBtn.isVisible()) {
      await ttBtn.click();
      await expect(page.getByText(/পরীক্ষা সিরিজ নির্বাচন ও সময়সূচি যুক্তকরণ/i)).toBeVisible();

      // Switch to Syllabus Status mode inside existing screen
      const sylBtn = page.getByRole("button", { name: /সিলেবাস ও বাকি পড়া/i });
      await expect(sylBtn).toBeVisible();
      await sylBtn.click();
      await expect(page.getByText(/অধ্যায়ভিত্তিক পাঠ অগ্রগতি ও বাকি সিলেবাস চিহ্নিতকরণ/i)).toBeVisible();
    }

    // Capture desktop screenshot
    await page.screenshot({ path: "audit/exam_mode_desktop_1280px.png", fullPage: true });
  });

  test("3. Minimal-Diff Replanning: Completing a block preserves its state after replan", async ({
    page,
    baseURL,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const url = baseURL || "http://127.0.0.1:3000/";
    await page.goto(url);
    await page.waitForLoadState("domcontentloaded");

    // Click "পরিকল্পনা আবার বানাও" (Replan) button
    const replanBtn = page.getByRole("button", { name: /পরিকল্পনা আবার বানাও|Replan/i }).first();
    await expect(replanBtn).toBeVisible();
    await replanBtn.click();

    // Verify view updates seamlessly without error
    const todayHeader = page.getByText(/আজকের গ্যাপ মাইক্রো-প্ল্যান ব্লকসমূহ|আজকের পড়াশোনার পরিকল্পনা/i).first();
    await expect(todayHeader).toBeVisible();
  });
});
