import { NextRequest, NextResponse } from "next/server";
import { BACKEND_GATEWAY_URL, getSession } from "@/lib/session";

export const maxDuration = 60;

export async function POST(req: NextRequest) {
  const session = await getSession();
  const authHeader = req.headers.get("authorization");
  if (!session && (!authHeader || !authHeader.startsWith("Bearer "))) {
    return NextResponse.json(
      { error: { code: "UNAUTHORIZED", message: "অনুগ্রহ করে আবার লগইন করুন।" } },
      { status: 401 }
    );
  }
  const userId = session?.user?.id || "bearer_user";

  const configuredBackendUrl = process.env.BACKEND_GATEWAY_URL || process.env.CORE_INTERNAL_URL || BACKEND_GATEWAY_URL;
  if (
    process.env.NODE_ENV === "production" &&
    (!configuredBackendUrl || configuredBackendUrl.includes("localhost") || configuredBackendUrl.includes("127.0.0.1"))
  ) {
    return NextResponse.json(
      { error: { code: "BACKEND_URL_MISCONFIGURED", message: "BACKEND_GATEWAY_URL must be configured in production." } },
      { status: 500 }
    );
  }

  try {
    const body = await req.json();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "ngrok-skip-browser-warning": "1",
      "X-User-Id": userId,
    };
    if (process.env.INTERNAL_SERVICE_TOKEN) {
      headers["X-Internal-Service-Token"] = process.env.INTERNAL_SERVICE_TOKEN;
    }

    const upstream = await fetch(`${configuredBackendUrl}/v1/voice/speak`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal: req.signal,
    });

    if (!upstream.ok) {
      const errData = await upstream.json().catch(() => ({ fallback: "browser_tts" }));
      return NextResponse.json(errData, {
        status: upstream.status,
        headers: { "Cache-Control": "no-store" },
      });
    }

    const contentType = upstream.headers.get("content-type") || "audio/wav";
    return new NextResponse(upstream.body, {
      status: 200,
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "no-store",
      },
    });
  } catch (err) {
    console.error("Voice speak proxy error:", err);
    return NextResponse.json(
      { fallback: "browser_tts" },
      { status: 503, headers: { "Cache-Control": "no-store" } }
    );
  }
}
