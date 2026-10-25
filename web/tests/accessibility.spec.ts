import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.describe("Comprehensive Accessibility (axe) Audit", () => {
  const languages: ("bn" | "en")[] = ["bn", "en"];
  const themes: ("light" | "dark")[] = ["light", "dark"];

  for (const lang of languages) {
    for (const theme of themes) {
      test.describe(`A11y Audit [Lang: ${lang}, Theme: ${theme}]`, () => {
        test(`Student routes pass axe in ${lang} and ${theme}`, async ({ page }) => {
          await page.goto("/");
          await page.waitForLoadState("networkidle");

          // Ensure student role
          const studentRoleBtn = page.getByRole("button", { name: /শিক্ষার্থী \(Student\)/i });
          if (await studentRoleBtn.isVisible()) {
            await studentRoleBtn.click();
            await page.waitForTimeout(300);
          }

          // Set language if needed
          if (lang === "en") {
            const langBtn = page.getByTitle(/English|বাংলা/i);
            if (await langBtn.isVisible()) {
              const text = await langBtn.textContent();
              if (text?.includes("EN") || text?.includes("English")) {
                await langBtn.click();
                await page.waitForTimeout(200);
              }
            }
          }

          // Set theme if needed
          if (theme === "dark") {
            const themeBtn = page.getByTitle(/Dark Mode|Light Mode/i);
            if (await themeBtn.isVisible()) {
              await themeBtn.click();
              await page.waitForTimeout(200);
            }
          }

          // Test primary view
          let results = await new AxeBuilder({ page })
            .disableRules(["color-contrast"])
            .analyze();
          expect(results.violations).toEqual([]);

          // Student tabs to test
          const studentTabs = ["quiz", "chat", "broad", "progress"];
          for (const tab of studentTabs) {
            const tabBtn = page.locator(`button[data-tab="${tab}"]`).first();
            if (await tabBtn.isVisible()) {
              await tabBtn.click({ force: true });
              await page.waitForTimeout(300);

              results = await new AxeBuilder({ page })
                .disableRules(["color-contrast"])
                .analyze();
              expect(results.violations).toEqual([]);
            }
          }
        });

        test(`Parent routes pass axe in ${lang} and ${theme}`, async ({ page }) => {
          await page.goto("/");
          await page.waitForLoadState("networkidle");

          // Switch to parent role
          const parentRoleBtn = page.getByRole("button", { name: /অভিভাবক \(Parent\)/i });
          if (await parentRoleBtn.isVisible()) {
            await parentRoleBtn.click();
            await page.waitForTimeout(400);
          }

          // Set language if needed
          if (lang === "en") {
            const langBtn = page.getByTitle(/English|বাংলা/i);
            if (await langBtn.isVisible()) {
              const text = await langBtn.textContent();
              if (text?.includes("EN") || text?.includes("English")) {
                await langBtn.click();
                await page.waitForTimeout(200);
              }
            }
          }

          // Set theme if needed
          if (theme === "dark") {
            const themeBtn = page.getByTitle(/Dark Mode|Light Mode/i);
            if (await themeBtn.isVisible()) {
              await themeBtn.click();
              await page.waitForTimeout(200);
            }
          }

          // Test parent dashboard
          let results = await new AxeBuilder({ page })
            .disableRules(["color-contrast"])
            .analyze();
          expect(results.violations).toEqual([]);

          // Parent tabs to test
          const parentTabs = ["setup", "suggestions", "notifications", "onboarding"];
          for (const tab of parentTabs) {
            const tabBtn = page.locator(`button[data-tab="${tab}"]`).first();
            if (await tabBtn.isVisible()) {
              await tabBtn.click({ force: true });
              await page.waitForTimeout(300);

              results = await new AxeBuilder({ page })
                .disableRules(["color-contrast"])
                .analyze();
              expect(results.violations).toEqual([]);
            }
          }
        });
      });
    }
  }
});
