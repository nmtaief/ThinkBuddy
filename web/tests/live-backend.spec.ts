import { test, expect } from "@playwright/test";

test.describe("Live-Backend Integration: Sign-in, Session, and Proxy", () => {
  test("Performs end-to-end auth, session check, live Gateway proxy, and logout", async ({ request }) => {
    // 1. Sign in as fake parent
    const loginRes = await request.post("/api/auth", {
      data: {
        role: "parent",
        name: "Test Parent Live",
        auth_provider: "fake",
      },
    });

    expect(loginRes.ok()).toBeTruthy();
    const loginData = await loginRes.json();
    expect(loginData.authenticated).toBe(true);
    expect(loginData.user.role).toBe("parent");
    expect(loginData.csrfToken).toBeTruthy();

    const csrfToken = loginData.csrfToken;

    // 2. Session verification (GET /api/auth)
    const sessionRes = await request.get("/api/auth");
    expect(sessionRes.ok()).toBeTruthy();
    const sessionData = await sessionRes.json();
    expect(sessionData.authenticated).toBe(true);
    expect(sessionData.user.name).toBe("Test Parent Live");

    // 3. Live proxy call to backend Gateway (/api/proxy/client/config)
    const proxyRes = await request.get("/api/proxy/client/config", {
      headers: {
        "accept-language": "bn",
      },
    });

    expect(proxyRes.ok()).toBeTruthy();
    const configData = await proxyRes.json();
    // Verify live backend Gateway fields from container
    expect(configData.min_supported_version).toBeDefined();
    expect(configData.quiz_security.allowed_mode).toBe("practice_only");

    // 4. Logout with CSRF token
    const logoutRes = await request.delete("/api/auth", {
      headers: {
        "x-csrf-token": csrfToken,
      },
    });
    expect(logoutRes.ok()).toBeTruthy();

    // 5. Verify session is destroyed
    const postLogoutSessionRes = await request.get("/api/auth");
    expect(postLogoutSessionRes.status()).toBe(401);
  });
});
