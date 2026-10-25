import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.describe("Accessibility (axe) Audit", () => {
  test("Student home screen passes accessibility audit", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const accessibilityScanResults = await new AxeBuilder({ page })
      .disableRules(["color-contrast"])
      .analyze();

    if (accessibilityScanResults.violations.length > 0) {
      console.log("Axe violations:", accessibilityScanResults.violations.map(v => ({ id: v.id, description: v.description })));
    }
    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test("Parent dashboard passes accessibility audit", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /অভিভাবক \(Parent\)/i }).click();

    const accessibilityScanResults = await new AxeBuilder({ page })
      .disableRules(["color-contrast"])
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);
  });
});
