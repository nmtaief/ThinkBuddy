import { test, expect } from "@playwright/test";

test.describe("Security: Storage & Token Isolation Audit", () => {
  test("No authentication tokens appear in browser storage or JS-readable cookies", async ({
    page,
  }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // 1. Verify localStorage is completely empty of auth tokens
    const localStorageKeys = await page.evaluate(() => Object.keys(localStorage));
    expect(localStorageKeys).not.toContain("access_token");
    expect(localStorageKeys).not.toContain("refresh_token");
    expect(localStorageKeys).not.toContain("jwt");
    expect(localStorageKeys).not.toContain("token");

    // 2. Verify sessionStorage is completely empty of auth tokens
    const sessionStorageKeys = await page.evaluate(() => Object.keys(sessionStorage));
    expect(sessionStorageKeys).not.toContain("access_token");
    expect(sessionStorageKeys).not.toContain("refresh_token");
    expect(sessionStorageKeys).not.toContain("jwt");

    // 3. Verify document.cookie does not expose httpOnly session cookies or auth tokens
    const clientCookies = await page.evaluate(() => document.cookie);
    expect(clientCookies).not.toContain("access_token");
    expect(clientCookies).not.toContain("refresh_token");
    expect(clientCookies).not.toContain("tb_bff_session"); // Must be httpOnly
  });
});
