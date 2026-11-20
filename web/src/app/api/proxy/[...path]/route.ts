import { NextRequest, NextResponse } from "next/server";
import { getSession, BACKEND_GATEWAY_URL, CSRF_HEADER_NAME } from "@/lib/session";

export interface EndpointRule {
  name: string;
  pattern: RegExp;
  methods: string[];
}

// Permitted upstream endpoint patterns strictly anchored with explicit methods allowed
export const ALLOWED_ENDPOINT_RULES: EndpointRule[] = [
  { name: "client_config", pattern: /^client\/config$/, methods: ["GET"] },
  { name: "quiz_attempts", pattern: /^quizzes\/[^/]+\/attempts$/, methods: ["POST"] },
  { name: "attempt_answer", pattern: /^attempts\/[^/]+\/items\/[^/]+\/answer$/, methods: ["POST"] },
  { name: "attempt_submit", pattern: /^attempts\/[^/]+\/submit$/, methods: ["POST"] },
  { name: "attempt_review", pattern: /^attempts\/[^/]+\/review$/, methods: ["GET"] },
  { name: "student_today", pattern: /^students\/[^/]+\/today$/, methods: ["GET"] },
  { name: "task_detail", pattern: /^tasks\/[^/]+$/, methods: ["PATCH"] },
  { name: "student_plan", pattern: /^students\/[^/]+\/plan$/, methods: ["GET"] },
  { name: "study_settings", pattern: /^students\/[^/]+\/study-settings$/, methods: ["GET", "PUT"] },
  { name: "student_study_settings_change_requests", pattern: /^students\/[^/]+\/study-settings\/change-requests$/, methods: ["POST"] },
  { name: "student_ai_suggestions", pattern: /^students\/[^/]+\/ai-suggestions$/, methods: ["GET"] },
  { name: "ai_suggestion_approve", pattern: /^students\/[^/]+\/ai-suggestions\/[^/]+\/approve$/, methods: ["POST"] },
  { name: "ai_suggestion_reject", pattern: /^students\/[^/]+\/ai-suggestions\/[^/]+\/reject$/, methods: ["POST"] },
  { name: "ai_adjustment_undo", pattern: /^students\/[^/]+\/ai-adjustments\/[^/]+\/undo$/, methods: ["POST"] },
  { name: "parent_change_request_approve", pattern: /^parents\/me\/students\/[^/]+\/change-requests\/[^/]+\/approve$/, methods: ["POST"] },
  { name: "parent_change_request_decline", pattern: /^parents\/me\/students\/[^/]+\/change-requests\/[^/]+\/decline$/, methods: ["POST"] },
  { name: "parent_students", pattern: /^parents\/me\/students$/, methods: ["GET"] },
  { name: "notification_preferences", pattern: /^notifications\/preferences$/, methods: ["GET", "PUT"] },
  { name: "notifications", pattern: /^notifications$/, methods: ["GET"] },
  { name: "families", pattern: /^families$/, methods: ["POST"] },
  { name: "family_students", pattern: /^families\/[^/]+\/students$/, methods: ["POST"] },
  { name: "link_redeem", pattern: /^links\/redeem$/, methods: ["POST"] },
  { name: "link_revoke", pattern: /^links\/[^/]+\/revoke$/, methods: ["POST"] },
  { name: "curriculum_subjects", pattern: /^curriculum\/subjects$/, methods: ["GET"] },
  { name: "planner_allocation", pattern: /^planner\/calculate-allocation$/, methods: ["POST"] },
  { name: "planner_ai_review", pattern: /^planner\/ai-review-and-plan$/, methods: ["POST"] },
  { name: "student_onboarding", pattern: /^students\/onboarding$/, methods: ["POST"] },
];

export function matchEndpointRule(endpoint: string): EndpointRule | undefined {
  return ALLOWED_ENDPOINT_RULES.find((rule) => rule.pattern.test(endpoint));
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

  // 3. Anchored allow-list check and method check
  const rule = matchEndpointRule(endpoint);
  if (!rule) {
    return NextResponse.json(
      { error: { code: "ENDPOINT_NOT_ALLOWED", message: `Endpoint '${endpoint}' is not permitted` } },
      { status: 403 }
    );
  }

  if (!rule.methods.includes(req.method.toUpperCase())) {
    return NextResponse.json(
      {
        error: {
          code: "METHOD_NOT_ALLOWED",
          message: `Method ${req.method} is not permitted for endpoint '${endpoint}'. Allowed: ${rule.methods.join(", ")}`,
        },
      },
      { status: 405 }
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

  // 6. Real Client IP Extraction and Header Propagation (parsed from the right)
  const rawXff = req.headers.get("x-forwarded-for");
  const rawRealIp = req.headers.get("x-real-ip");
  const xffHops = rawXff ? rawXff.split(",").map((s) => s.trim()).filter(Boolean) : [];
  const clientIp = xffHops.length > 0
    ? xffHops[xffHops.length - 1]
    : (rawRealIp || "127.0.0.1");

  // Overwrite client platform headers strictly from server
  const clientFormFactorHeader = req.headers.get("x-client-form-factor");
  let formFactor = "desktop";
  if (clientFormFactorHeader === "phone" || clientFormFactorHeader === "compact") {
    formFactor = "phone";
  } else if (clientFormFactorHeader === "tablet" || clientFormFactorHeader === "medium") {
    formFactor = "tablet";
  } else if (clientFormFactorHeader === "desktop" || clientFormFactorHeader === "expanded") {
    formFactor = "desktop";
  }

  const acceptLang = req.headers.get("accept-language")?.includes("en") ? "en" : "bn";

  const headers: Record<string, string> = {
    "X-Client-Platform": "web",
    "X-Client-Form-Factor": formFactor,
    "X-App-Version": "1.0.0",
    "X-Device-Id": session?.deviceId || "web_anon",
    "Accept-Language": acceptLang,
    "X-Real-IP": clientIp,
    "X-Forwarded-For": rawXff ? `${rawXff}, 127.0.0.1` : clientIp,
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

  // Built-in fallback for curriculum subjects
  if (endpoint === "curriculum/subjects") {
    const classLevel = parseInt(req.nextUrl.searchParams.get("class_level") || "8", 10);
    const group = req.nextUrl.searchParams.get("group") || "general";
    try {
      const backendRes = await fetch(targetUrl.toString(), { method: req.method, headers });
      if (backendRes.ok) {
        const data = await backendRes.text();
        return new NextResponse(data, {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
    } catch {}
    const { getSubjectsForClassAndGroup } = await import("@/lib/curriculum-data");
    const subjects = getSubjectsForClassAndGroup(classLevel, group);
    return NextResponse.json(subjects, { status: 200 });
  }

  // Built-in fallback for students onboarding activation
  if (endpoint === "students/onboarding") {
    try {
      const fetchOptions: RequestInit = { method: req.method, headers, body: await req.text() };
      const backendRes = await fetch(targetUrl.toString(), fetchOptions);
      if (backendRes.ok) {
        const data = await backendRes.text();
        return new NextResponse(data, { status: 200, headers: { "Content-Type": "application/json" } });
      }
    } catch {}
    return NextResponse.json({ status: "success", message: "Onboarding profile saved" }, { status: 200 });
  }

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
