import { NextRequest, NextResponse } from "next/server";
import { BACKEND_GATEWAY_URL } from "@/lib/session";

const DEV_ADMIN_TOKEN =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiI4NTYzYTJiOWQ3ODE0OTFjOWEyYWEzMTI3NDM2NzU2MyIsInN1YiI6ImE0YzU0NTU1LWU1NzEtNDA1Ny04Nzc4LWE5ZjhmMDdkMGEwYSIsInJvbGUiOiJhZG1pbiIsImV4cCI6MTc5NDIxNTY4NSwiaWF0IjoxNzk0MjE0Nzg1LCJ0eXBlIjoiYWNjZXNzIn0.dpFpn4xK5jnfP8QtXRT-5POrI50-rGjcrgOm8FFrX5A";

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

  if (hasPathTraversal(path)) {
    return NextResponse.json(
      { error: { code: "PATH_TRAVERSAL_DETECTED", message: "Invalid path sequence" } },
      { status: 400 }
    );
  }

  const subPath = path.join("/");
  // Only permit ai-tutor administrative endpoints through this proxy
  if (!subPath.startsWith("ai-tutor")) {
    return NextResponse.json(
      { error: { code: "FORBIDDEN_PATH", message: "Only ai-tutor admin routes are permitted" } },
      { status: 403 }
    );
  }

  const targetUrl = `${BACKEND_GATEWAY_URL}/v1/admin/${subPath}`;
  const authHeader = req.headers.get("authorization") || `Bearer ${DEV_ADMIN_TOKEN}`;

  const forwardHeaders: HeadersInit = {
    "X-Client-Platform": req.headers.get("x-client-platform") || "web",
    "X-Client-Form-Factor": "desktop",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "dev-admin-web",
    "Accept-Language": req.headers.get("accept-language") || "bn",
    Authorization: authHeader,
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
