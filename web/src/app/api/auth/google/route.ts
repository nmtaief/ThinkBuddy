import { NextRequest, NextResponse } from "next/server";
import {
  getSession,
  saveSession,
  generateRandomId,
  BACKEND_GATEWAY_URL,
  ABSOLUTE_TIMEOUT_SECONDS,
} from "@/lib/session";
import { SessionUser } from "@/lib/types";

function validateOrigin(req: NextRequest): boolean {
  const origin = req.headers.get("origin");
  const forwardedHost = req.headers.get("x-forwarded-host");
  const host = req.headers.get("host");
  if (!origin || (!host && !forwardedHost)) return true;
  try {
    const originHost = new URL(origin).host;
    return originHost === host || (forwardedHost !== null && originHost === forwardedHost);
  } catch {
    return false;
  }
}

export async function POST(req: NextRequest) {
  if (!validateOrigin(req)) {
    return NextResponse.json({ error: "Invalid request origin" }, { status: 403 });
  }

  try {
    const body = await req.json();
    const { id_token, role = "student" } = body;

    if (!id_token) {
      return NextResponse.json({ error: "Missing Google ID token" }, { status: 400 });
    }

    const existingSession = await getSession();
    const deviceId = existingSession?.deviceId || generateRandomId("dev_web");
    const csrfToken = generateRandomId("csrf");

    // Forward to backend gateway Google exchange
    const backendRes = await fetch(`${BACKEND_GATEWAY_URL}/v1/auth/google`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Client-Platform": "web",
        "X-Client-Form-Factor": "desktop",
        "X-App-Version": "1.0.0",
        "X-Device-Id": deviceId,
        "Accept-Language": "bn",
      },
      body: JSON.stringify({
        id_token,
        role,
      }),
    });

    if (!backendRes.ok) {
      const errData = await backendRes.json().catch(() => ({}));
      const msg = errData?.detail?.message || errData?.error?.message || "Google authentication failed";
      return NextResponse.json({ error: msg }, { status: backendRes.status });
    }

    const data = await backendRes.json();
    const accessToken = data.access_token;
    const refreshToken = data.refresh_token;

    const user: SessionUser = {
      id: data.user?.id || generateRandomId("u"),
      name: data.user?.display_name || data.user?.name || "Google User",
      role: (data.user?.role || role) as "student" | "parent",
      student_id: data.user?.role === "student" ? data.user.id : undefined,
      active_child_id: data.user?.role === "parent" ? (data.user?.active_child_id || "stu_101") : undefined,
    };

    // Session rotation: generate new session ID and revoke old session
    const newSessionId = generateRandomId("sess");
    const now = Date.now();

    await saveSession(
      {
        sessionId: newSessionId,
        accessToken,
        refreshToken,
        previousRefreshTokens: existingSession?.refreshToken ? [existingSession.refreshToken] : [],
        deviceId,
        csrfToken,
        user,
        createdAt: now,
        lastActivityAt: now,
        absoluteExpiresAt: now + ABSOLUTE_TIMEOUT_SECONDS * 1000,
        isActive: true,
      },
      existingSession?.sessionId
    );

    return NextResponse.json({
      authenticated: true,
      user,
      csrfToken,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Authentication error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
