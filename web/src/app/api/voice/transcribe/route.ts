import { NextRequest, NextResponse } from "next/server";
import { BACKEND_GATEWAY_URL } from "@/lib/session";

export const maxDuration = 60;

export async function POST(req: NextRequest) {
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
    const formData = await req.formData();
    const headers: Record<string, string> = {
      "ngrok-skip-browser-warning": "1",
    };
    if (process.env.INTERNAL_SERVICE_TOKEN) {
      headers["X-Internal-Service-Token"] = process.env.INTERNAL_SERVICE_TOKEN;
    }

    const upstream = await fetch(`${configuredBackendUrl}/v1/voice/transcribe`, {
      method: "POST",
      headers,
      body: formData,
      signal: req.signal,
    });

    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    console.error("Voice transcribe proxy error:", err);
    return NextResponse.json(
      { error: { code: "VOICE_TRANSCRIBE_ERROR", message: "Failed to transcribe audio." } },
      { status: 502 }
    );
  }
}
