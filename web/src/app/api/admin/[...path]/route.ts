import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";
import { BACKEND_GATEWAY_URL, getSession } from "@/lib/session";

function getAdminToken(): string | null {
  const secret = process.env.JWT_SECRET_KEY;
  if (!secret) return null;
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const now = Math.floor(Date.now() / 1000);
  const payload = Buffer.from(
    JSON.stringify({
      jti: crypto.randomUUID(),
      sub: "b7bca8e8-e818-458d-93da-ac58712d07f1",
      role: "admin",
      exp: now + 3600,
      iat: now,
      type: "access",
    })
  ).toString("base64url");
  const sig = crypto.createHmac("sha256", secret).update(`${header}.${payload}`).digest("base64url");
  return `${header}.${payload}.${sig}`;
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

async function handleAdminProxy(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;

  // 1. Enforce admin role authentication
  const session = await getSession();
  const authHeader = req.headers.get("authorization");
  const isAuthorizedAdmin = session?.user?.role === "admin" || (authHeader && authHeader.startsWith("Bearer "));
  if (!isAuthorizedAdmin) {
    return NextResponse.json(
      { error: { code: "UNAUTHORIZED_ADMIN", message: "Administrative privileges required." } },
      { status: 403 }
    );
  }

  if (hasPathTraversal(path)) {
    return NextResponse.json(
      { error: { code: "PATH_TRAVERSAL_DETECTED", message: "Invalid path sequence" } },
      { status: 400 }
    );
  }

  const subPath = path.join("/");
  // Permit ai-tutor, analytics, and administrative endpoints through this proxy
  const allowedPrefixes = ["ai-tutor", "analytics", "content", "users", "privacy"];
  const isAllowed = allowedPrefixes.some((p) => subPath.startsWith(p));
  if (!isAllowed) {
    return NextResponse.json(
      { error: { code: "FORBIDDEN_PATH", message: "Path is not an allowed admin route" } },
      { status: 403 }
    );
  }

  const targetUrl = `${BACKEND_GATEWAY_URL}/v1/admin/${subPath}`;
  const adminToken = getAdminToken();
  const effectiveAuthHeader = authHeader || (adminToken ? `Bearer ${adminToken}` : (session ? `Bearer ${session.accessToken}` : ""));

  const forwardHeaders: HeadersInit = {
    "X-Client-Platform": req.headers.get("x-client-platform") || "web",
    "X-Client-Form-Factor": "desktop",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "dev-admin-web",
    "Accept-Language": req.headers.get("accept-language") || "bn",
    Authorization: effectiveAuthHeader,
  };

  let body: BodyInit | undefined = undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    forwardHeaders["Content-Type"] = "application/json";
    body = await req.text();
  }

  try {
    const backendRes = await fetch(targetUrl, {
      method: req.method,
      headers: forwardHeaders,
      body,
    });

    const responseText = await backendRes.text();
    const contentType = backendRes.headers.get("content-type") || "application/json";

    return new NextResponse(responseText, {
      status: backendRes.status,
      headers: {
        "Content-Type": contentType,
      },
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { error: { code: "GATEWAY_ERROR", message: "Failed to forward request to gateway: " + msg } },
      { status: 502 }
    );
  }
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return handleAdminProxy(req, ctx);
}

export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return handleAdminProxy(req, ctx);
}

export async function PUT(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return handleAdminProxy(req, ctx);
}

