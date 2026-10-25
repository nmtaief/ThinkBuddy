import { NextRequest, NextResponse } from "next/server";
import {
  getSession,
  saveSession,
  destroySession,
  generateRandomId,
  BACKEND_GATEWAY_URL,
  CSRF_HEADER_NAME,
} from "@/lib/session";
import { SessionUser } from "@/lib/types";

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
  try {
    const body = await req.json();
    const { role = "student", name = "Test User", auth_provider = "fake" } = body;

    const deviceId = generateRandomId("dev_web");
    const csrfToken = generateRandomId("csrf");
    let user: SessionUser;
    let accessToken = "fake_access_token";
    let refreshToken = "fake_refresh_token";

    if (auth_provider === "fake") {
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
            active_child_id: role === "parent" ? generateRandomId("stu") : undefined,
          };
        } else {
          // Dev fallback
          user = {
            id: generateRandomId("u"),
            name: name,
            role: role as "student" | "parent",
            student_id: role === "student" ? generateRandomId("stu") : undefined,
            active_child_id: role === "parent" ? generateRandomId("stu") : undefined,
          };
        }
      } catch {
        // Fallback mock session in offline/test environment
        user = {
          id: generateRandomId("u"),
          name: name,
          role: role as "student" | "parent",
          student_id: role === "student" ? generateRandomId("stu") : undefined,
          active_child_id: role === "parent" ? generateRandomId("stu") : undefined,
        };
      }
    } else {
      return NextResponse.json({ error: "Unsupported auth provider" }, { status: 400 });
    }

    const sessionId = generateRandomId("sess");
    await saveSession({
      sessionId,
      accessToken,
      refreshToken,
      deviceId,
      csrfToken,
      user,
      expiresAt: Date.now() + 1000 * 60 * 60 * 24 * 7,
    });

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
