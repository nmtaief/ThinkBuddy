import { NextRequest, NextResponse } from "next/server";
import { getSession, BACKEND_GATEWAY_URL, CSRF_HEADER_NAME } from "@/lib/session";

// Permitted upstream endpoint patterns
const ALLOWED_ENDPOINT_PATTERNS = [
  /^client\/config$/,
  /^quizzes\/[^/]+\/attempts$/,
  /^attempts\/[^/]+\/items\/[^/]+\/answer$/,
  /^attempts\/[^/]+\/submit$/,
  /^attempts\/[^/]+\/review$/,
  /^students\/[^/]+\/plan$/,
  /^students\/[^/]+\/study-settings$/,
  /^students\/[^/]+\/suggestions$/,
  /^suggestions\/[^/]+\/approve$/,
  /^suggestions\/[^/]+\/decline$/,
  /^students\/[^/]+\/auto-adjustments$/,
  /^auto-adjustments\/[^/]+\/undo$/,
  /^students\/[^/]+\/change-requests$/,
  /^parents\/me\/students$/,
  /^parents\/me\/notifications\/preferences$/,
  /^uploads\/sign$/,
  /^tasks\/[^/]+$/,
];

function isPathAllowed(endpoint: string): boolean {
  return ALLOWED_ENDPOINT_PATTERNS.some((pattern) => pattern.test(endpoint));
}

function hasPathTraversal(pathSegments: string[]): boolean {
  for (const seg of pathSegments) {
    const decoded = decodeURIComponent(seg);
    if (
      decoded.includes("..") ||
      decoded.includes("/") ||
      decoded.includes("\\") ||
      decoded.includes("\0")
    ) {
      return true;
    }
  }
  return false;
}

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

async function handleProxy(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;

  // 1. Path traversal rejection
  if (hasPathTraversal(path)) {
    return NextResponse.json(
      { error: { code: "PATH_TRAVERSAL_DETECTED", message: "Invalid path sequence" } },
      { status: 400 }
    );
  }

  const endpoint = path.join("/");

  // 2. Explicitly block internal and admin paths
  const lowerEndpoint = endpoint.toLowerCase();
  if (
    lowerEndpoint.startsWith("internal") ||
    lowerEndpoint.includes("/internal") ||
    lowerEndpoint.startsWith("admin") ||
    lowerEndpoint.includes("/admin") ||
    lowerEndpoint.startsWith("v1/admin")
  ) {
    return NextResponse.json(
      { error: { code: "FORBIDDEN_PATH", message: "Access to internal/admin routes is forbidden" } },
      { status: 403 }
    );
  }

  // 3. Allow-list check
  if (!isPathAllowed(endpoint)) {
    return NextResponse.json(
      { error: { code: "ENDPOINT_NOT_ALLOWED", message: `Endpoint '${endpoint}' is not permitted` } },
      { status: 403 }
    );
  }

  const session = await getSession();

  // 4. Block assessed quizzes at BFF layer per Rule 4, 05_SECURE_QUIZ.md, and P08 requirements
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

  // 5. Origin check and CSRF validation for mutating methods
  // CSRF delivery pattern: Ephemeral csrfToken delivered in auth response body,
  // bound to server session in Redis, validated on every mutating request via x-csrf-token header.
  if (["POST", "PUT", "PATCH", "DELETE"].includes(req.method)) {
    if (!validateOrigin(req)) {
      return NextResponse.json(
        { error: { code: "ORIGIN_MISMATCH", message: "Cross-origin request rejected" } },
        { status: 403 }
      );
    }

    if (session) {
      const csrfHeader = req.headers.get(CSRF_HEADER_NAME);
      if (!csrfHeader || csrfHeader !== session.csrfToken) {
        return NextResponse.json(
          { error: { code: "CSRF_ERROR", message: "Invalid or missing CSRF token" } },
          { status: 403 }
        );
      }
    }
  }

  // 6. Overwrite client platform headers strictly from server
  const clientFormFactorHeader = req.headers.get("x-client-form-factor");
  const formFactor = ["compact", "medium", "expanded"].includes(clientFormFactorHeader || "")
    ? (clientFormFactorHeader as string)
    : "expanded";

  const acceptLang = req.headers.get("accept-language")?.includes("en") ? "en" : "bn";

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

  // 7. Fixed upstream
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
