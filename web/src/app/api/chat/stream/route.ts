import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";
import { getSession, BACKEND_GATEWAY_URL } from "@/lib/session";

export const maxDuration = 60;

const EPHEMERAL_DEV_SECRET = crypto.randomBytes(32).toString("hex");

function getStudentToken(studentId?: string): string {
  const secret = process.env.JWT_SECRET_KEY || EPHEMERAL_DEV_SECRET;
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const now = Math.floor(Date.now() / 1000);
  const effStudentId =
    studentId && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(studentId)
      ? studentId
      : "84483f82-142f-4026-a586-a3e42bdbb632";
  const payload = Buffer.from(
    JSON.stringify({
      jti: crypto.randomUUID(),
      sub: effStudentId,
      role: "student",
      exp: now + 3600,
      iat: now,
      type: "access",
    })
  ).toString("base64url");
  const sig = crypto.createHmac("sha256", secret).update(`${header}.${payload}`).digest("base64url");
  return `${header}.${payload}.${sig}`;
}

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

  const session = await getSession();
  const body = await req.json();
  const { session_id, message, class_override, image_data, retry_message_id, provider } = body;

  const rawFormFactor = req.headers.get("x-client-form-factor") || "desktop";
  const formFactor =
    rawFormFactor === "phone" || rawFormFactor === "compact"
      ? "phone"
      : rawFormFactor === "tablet" || rawFormFactor === "medium"
      ? "tablet"
      : "desktop";
  const acceptLang = req.headers.get("accept-language")?.includes("en") ? "en" : "bn";

  const studentToken = getStudentToken(session?.user?.student_id || session?.user?.id);

  const headers: Record<string, string> = {
    "X-Client-Platform": "web",
    "X-Client-Form-Factor": formFactor,
    "X-App-Version": "1.0.0",
    "X-Device-Id": session?.deviceId || "web_student_device",
    "Accept-Language": acceptLang,
    "Content-Type": "application/json",
    Accept: "text/event-stream",
    Authorization: `Bearer ${studentToken}`,
    "ngrok-skip-browser-warning": "1",
  };

  // Ensure valid chat session UUID
  let effectiveSessionId = session_id;
  const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(session_id || "");
  if (!isUuid) {
    try {
      const createRes = await fetch(`${BACKEND_GATEWAY_URL}/v1/chat/sessions`, {
        method: "POST",
        headers,
        body: JSON.stringify({ title: "Student Study Conversation" }),
      });
      if (createRes.ok) {
        const newSess = await createRes.json();
        effectiveSessionId = newSess.id;
      }
    } catch (err) {
      console.error("Failed to create chat session on gateway:", err);
    }
  }

  const isValidEffectiveSession = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
    effectiveSessionId || ""
  );

  // Attempt backend gateway stream with real AI tutor orchestrator
  if (isValidEffectiveSession) {
    try {
      const backendRes = await fetch(
        `${BACKEND_GATEWAY_URL}/v1/chat/sessions/${effectiveSessionId}/messages`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            content: message,
            stream: true,
            language: acceptLang,
            class_override: class_override ? parseInt(class_override, 10) : undefined,
            image_data: image_data || undefined,
            retry_message_id: retry_message_id || undefined,
            provider: provider || undefined,
          }),
          signal: req.signal,
        }
      );

      if (backendRes.ok && backendRes.body) {
        return new NextResponse(backendRes.body, {
          headers: {
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-cache, no-transform",
            Connection: "keep-alive",
            "X-Accel-Buffering": "no",
          },
        });
      }

      if (!backendRes.ok) {
        try {
          const errJson = await backendRes.json();
          const isQuota =
            backendRes.status === 429 ||
            errJson?.error?.code === "RATE_LIMIT_EXCEEDED" ||
            errJson?.error?.code === "QUOTA_EXCEEDED";

          const errMessage = isQuota
            ? acceptLang === "en"
              ? "Your daily chat quota has been reached. Please try again tomorrow."
              : "আজকের জন্য তোমার চ্যাট কোটা শেষ হয়ে গেছে। আগামীকাল আবার চেষ্টা করো।"
            : acceptLang === "en"
            ? "Something went wrong, please try again."
            : "একটু সমস্যা হয়েছে, আবার চেষ্টা করো";

          const encoder = new TextEncoder();
          const stream = new ReadableStream({
            start(controller) {
              controller.enqueue(
                encoder.encode(
                  `event: error\ndata: ${JSON.stringify({ code: isQuota ? "QUOTA_EXCEEDED" : "BACKEND_ERROR", message: errMessage })}\n\n`
                )
              );
              controller.close();
            },
          });
          return new NextResponse(stream, {
            headers: {
              "Content-Type": "text/event-stream; charset=utf-8",
              "Cache-Control": "no-cache, no-transform",
            },
          });
        } catch {
          // Continue to fallback if json parsing fails
        }
      }
    } catch (err) {
      console.error("Gateway stream error:", err);
    }
  }

  // If gateway call failed, return error event
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      const errorMsg =
        acceptLang === "en"
          ? "Something went wrong, please try again."
          : "একটু সমস্যা হয়েছে, আবার চেষ্টা করো";
      controller.enqueue(
        encoder.encode(
          `event: error\ndata: ${JSON.stringify({ code: "BACKEND_ERROR", message: errorMsg })}\n\n`
        )
      );
      controller.close();
    },
  });

  return new NextResponse(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
