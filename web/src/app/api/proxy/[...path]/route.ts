import { NextRequest, NextResponse } from "next/server";
import { getSession, BACKEND_GATEWAY_URL, CSRF_HEADER_NAME } from "@/lib/session";

async function handleProxy(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const endpoint = path.join("/");
  const session = await getSession();

  // Block assessed quizzes at BFF layer per Rule 4, 05_SECURE_QUIZ.md, and P08 requirements
  if (endpoint.includes("attempts") && req.method === "POST") {
    try {
      const cloned = req.clone();
      const body = await cloned.json();
      if (body.mode === "assessed") {
        return NextResponse.json(
          {
            error: {
              code: "WEB_PLATFORM_PRACTICE_ONLY",
              message: "Assessed quizzes are only available in the ThinkBuddy Android app.",
            },
          },
          { status: 403 }
        );
      }
    } catch {
      // Body may not be JSON
    }
  }

  // CSRF validation for mutating methods if session exists
  if (session && ["POST", "PUT", "PATCH", "DELETE"].includes(req.method)) {
    const csrfHeader = req.headers.get(CSRF_HEADER_NAME);
    if (!csrfHeader || csrfHeader !== session.csrfToken) {
      return NextResponse.json(
        { error: { code: "CSRF_ERROR", message: "Invalid or missing CSRF token" } },
        { status: 403 }
      );
    }
  }

  const formFactor = req.headers.get("x-client-form-factor") || "expanded";
  const acceptLang = req.headers.get("accept-language") || "bn";

  const headers: Record<string, string> = {
    "X-Client-Platform": "web",
    "X-Client-Form-Factor": formFactor,
    "X-App-Version": "1.0.0",
    "X-Device-Id": session?.deviceId || "web_anon",
    "Accept-Language": acceptLang,
  };

  if (session?.accessToken) {
    headers["Authorization"] = `Bearer ${session.accessToken}`;
  }

  const contentType = req.headers.get("content-type");
  if (contentType) {
    headers["Content-Type"] = contentType;
  }

  const targetUrl = new URL(`${BACKEND_GATEWAY_URL}/v1/${endpoint}`);
  req.nextUrl.searchParams.forEach((val, key) => {
    targetUrl.searchParams.append(key, val);
  });

  try {
    const fetchOptions: RequestInit = {
      method: req.method,
      headers,
    };

    if (["POST", "PUT", "PATCH"].includes(req.method)) {
      fetchOptions.body = await req.text();
    }

    const backendRes = await fetch(targetUrl.toString(), fetchOptions);
    const data = await backendRes.text();

    return new NextResponse(data, {
      status: backendRes.status,
      headers: {
        "Content-Type": backendRes.headers.get("content-type") || "application/json",
      },
    });
  } catch (err: unknown) {
    // If backend is not reached during mock/test, provide deterministic client fallback
    const message = err instanceof Error ? err.message : "Gateway connection error";
    return NextResponse.json(
      { error: { code: "GATEWAY_UNAVAILABLE", message } },
      { status: 503 }
    );
  }
}

export const GET = handleProxy;
export const POST = handleProxy;
export const PUT = handleProxy;
export const PATCH = handleProxy;
export const DELETE = handleProxy;
