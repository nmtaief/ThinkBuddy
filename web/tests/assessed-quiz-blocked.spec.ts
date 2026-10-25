import { test, expect } from "@playwright/test";

test.describe("Security: Assessed Quiz Guard on Web", () => {
  test("Starting an assessed quiz attempt from web is blocked with 403 WEB_PLATFORM_PRACTICE_ONLY", async ({
    request,
  }) => {
    // Direct attempt initiation with mode: "assessed"
    const response = await request.post("/api/proxy/quizzes/quiz_demo/attempts", {
      data: {
        mode: "assessed",
      },
    });

    expect(response.status()).toBe(403);
    const body = await response.json();
    expect(body.error?.code).toBe("WEB_PLATFORM_PRACTICE_ONLY");
  });

  test("UI displays assessed quiz app-only banner and directs to Android app", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Click Quiz tab
    await page.locator('[data-testid="nav-quiz"]:visible, [data-testid="bottom-nav-quiz"]:visible').first().click({ force: true });

    // Click Assessed Quiz Tab
    const assessedTab = page.getByRole("button", { name: /মূল্যায়ন কুইজ ThinkBuddy অ্যাপে উপলব্ধ/i });
    await expect(assessedTab).toBeVisible();
    await assessedTab.click();

    // Verify blocking banner
    await expect(page.getByText(/ন্যায্যতা ও নিরাপত্তার স্বার্থে মূল্যায়ন কুইজ শুধুমাত্র অ্যান্ড্রয়েড ThinkBuddy অ্যাপে/i)).toBeVisible();
    await expect(page.getByRole("link", { name: /অ্যান্ড্রয়েড অ্যাপ ডাউনলোড করুন/i })).toBeVisible();
  });
});
