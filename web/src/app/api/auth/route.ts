import { NextRequest, NextResponse } from "next/server";
import {
  getSession,
  saveSession,
  destroySession,
  generateRandomId,
  BACKEND_GATEWAY_URL,
  CSRF_HEADER_NAME,
  ABSOLUTE_TIMEOUT_SECONDS,
} from "@/lib/session";
import { SessionUser } from "@/lib/types";

function validateOrigin(req: NextRequest): boolean {
  const origin = req.headers.get("origin");
  const host = req.headers.get("host");
  if (!origin || !host) return true;
  try {
    const originHost = new URL(origin).host;
    return originHost === host;
  } catch {
    return false;
  }
}

export async function GET() {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ authenticated: false }, { status: 401 });
  }
  return NextResponse.json({
    authenticated: true,
    user: session.user,
    csrfToken: session.csrfToken,
  });
}

export async function POST(req: NextRequest) {
  if (!validateOrigin(req)) {
    return NextResponse.json({ error: "Invalid request origin" }, { status: 403 });
  }

  try {
    const body = await req.json();
    const {
      role = "student",
      name = "Test User",
      auth_provider = "fake",
      id_token,
    } = body;

    const existingSession = await getSession();
    const deviceId = existingSession?.deviceId || generateRandomId("dev_web");
    const csrfToken = generateRandomId("csrf");
    let user: SessionUser;
    let accessToken = "access_token_demo_" + generateRandomId();
    let refreshToken = "refresh_token_demo_" + generateRandomId();

    const isFirebaseEnabled = process.env.NEXT_PUBLIC_ENABLE_FIREBASE_AUTH === "true";

    if (auth_provider === "firebase") {
      if (!isFirebaseEnabled) {
        return NextResponse.json({ error: "Firebase authentication is not enabled" }, { status: 403 });
      }
      if (!id_token) {
        return NextResponse.json({ error: "Missing Firebase id_token" }, { status: 400 });
      }

      // Forward to backend gateway exchange
      const backendRes = await fetch(`${BACKEND_GATEWAY_URL}/v1/auth/exchange`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Client-Platform": "web",
          "X-Client-Form-Factor": "expanded",
          "X-App-Version": "1.0.0",
          "X-Device-Id": deviceId,
        },
        body: JSON.stringify({
          auth_provider: "firebase",
          id_token: id_token,
          role: role,
        }),
      });

      if (!backendRes.ok) {
        const errorData = await backendRes.json().catch(() => ({}));
        return NextResponse.json(
          { error: errorData.message || "Failed to exchange Firebase token" },
          { status: backendRes.status }
        );
      }

      const data = await backendRes.json();
      accessToken = data.access_token || accessToken;
      refreshToken = data.refresh_token || refreshToken;
      user = {
        id: data.user?.id || generateRandomId("u"),
        name: data.user?.name || name,
        role: role as "student" | "parent",
        student_id: data.user?.student_id || (role === "student" ? generateRandomId("stu") : undefined),
        active_child_id: role === "parent" ? (data.user?.active_child_id || "stu_101") : undefined,
      };
    } else if (auth_provider === "fake") {
      // Connect to backend fake exchange or local bootstrap
      try {
        const backendRes = await fetch(`${BACKEND_GATEWAY_URL}/v1/auth/exchange`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Client-Platform": "web",
            "X-Client-Form-Factor": "expanded",
            "X-App-Version": "1.0.0",
            "X-Device-Id": deviceId,
          },
          body: JSON.stringify({
            auth_provider: "fake",
            id_token: `fake_${role}_${generateRandomId()}`,
            role: role,
          }),
        });

        if (backendRes.ok) {
          const data = await backendRes.json();
          accessToken = data.access_token || accessToken;
          refreshToken = data.refresh_token || refreshToken;
          user = {
            id: data.user?.id || generateRandomId("u"),
            name: data.user?.name || name,
            role: role as "student" | "parent",
            student_id: data.user?.student_id || (role === "student" ? generateRandomId("stu") : undefined),
            active_child_id: role === "parent" ? (data.user?.active_child_id || "stu_101") : undefined,
          };
        } else {
          user = {
            id: generateRandomId("u"),
            name: name,
            role: role as "student" | "parent",
            student_id: role === "student" ? generateRandomId("stu") : undefined,
            active_child_id: role === "parent" ? "stu_101" : undefined,
          };
        }
      } catch {
        user = {
          id: generateRandomId("u"),
          name: name,
          role: role as "student" | "parent",
          student_id: role === "student" ? generateRandomId("stu") : undefined,
          active_child_id: role === "parent" ? "stu_101" : undefined,
        };
      }
    } else {
      return NextResponse.json({ error: "Unsupported auth provider" }, { status: 400 });
    }

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

export async function DELETE(req: NextRequest) {
  if (!validateOrigin(req)) {
    return NextResponse.json({ error: "Invalid request origin" }, { status: 403 });
  }

  const session = await getSession();
  if (session) {
    // CSRF verification on logout
    const csrfHeader = req.headers.get(CSRF_HEADER_NAME);
    if (!csrfHeader || csrfHeader !== session.csrfToken) {
      return NextResponse.json({ error: "Invalid CSRF token" }, { status: 403 });
    }
    await destroySession();
  }
  return NextResponse.json({ success: true });
}
