import { NextResponse, NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const response = NextResponse.next();
  const isProduction = process.env.NODE_ENV === "production";
  const enableFirebase = process.env.NEXT_PUBLIC_ENABLE_FIREBASE_AUTH === "true";

  // Strict Content Security Policy (P08 Deliverables 11 & 12)
  // In production: strictly NO 'unsafe-inline' or 'unsafe-eval' for scripts
  const scriptSrc = isProduction
    ? enableFirebase
      ? "'self' https://apis.google.com https://www.gstatic.com https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/"
      : "'self'"
    : enableFirebase
      ? "'self' 'unsafe-inline' 'unsafe-eval' https://apis.google.com https://www.gstatic.com https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/"
      : "'self' 'unsafe-inline' 'unsafe-eval'";

  const connectSrc = isProduction
    ? enableFirebase
      ? "'self' https://identitytoolkit.googleapis.com https://securetoken.googleapis.com"
      : "'self'"
    : enableFirebase
      ? "'self' http://127.0.0.1:* http://localhost:* https://identitytoolkit.googleapis.com https://securetoken.googleapis.com"
      : "'self' http://127.0.0.1:* http://localhost:*";

  const frameSrc = enableFirebase
    ? "'self' https://www.google.com/recaptcha/ https://recaptcha.google.com/recaptcha/ https://*.firebaseapp.com"
    : "'none'";

  const cspHeader = `
    default-src 'self';
    script-src ${scriptSrc};
    style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
    font-src 'self' https://fonts.gstatic.com data:;
    img-src 'self' data: blob: https:;
    connect-src ${connectSrc};
    frame-src ${frameSrc};
    frame-ancestors 'none';
    form-action 'self';
    base-uri 'self';
    object-src 'none';
  `
    .replace(/\s{2,}/g, " ")
    .trim();

  response.headers.set("Content-Security-Policy", cspHeader);
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set(
    "Permissions-Policy",
    "camera=(self), microphone=(), geolocation=(), payment=()"
  );

  return response;
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for static files:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
