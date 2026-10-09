import { type NextRequest, NextResponse } from "next/server";

import { buildCsp } from "@/lib/security/csp";

/** Adds a per-request CSP nonce to every page response (SECURITY.md section 8). */
export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const csp = buildCsp({
    nonce,
    apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1",
    mediaOrigin: process.env.MEDIA_ORIGIN,
    isDev: process.env.NODE_ENV === "development",
  });

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    {
      // Pages only: not the proxied API, static assets or prefetches.
      source: "/((?!api|_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
