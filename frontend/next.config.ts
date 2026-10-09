import type { NextConfig } from "next";

const backendOrigin = (process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
const isProduction = process.env.NODE_ENV === "production";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "geolocation=(self), camera=(), microphone=()" },
  ...(isProduction ? [{ key: "Strict-Transport-Security", value: "max-age=31536000" }] : []),
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Django URLs end with a slash; keep them intact through the auth rewrite.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      {
        // SEC-1: only the auth endpoints are proxied, so the HttpOnly refresh cookie is first-party.
        source: "/api/v1/auth/:path*",
        // The matcher drops the trailing slash; Django auth URLs require it.
        destination: `${backendOrigin}/api/v1/auth/:path*/`,
      },
    ];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
