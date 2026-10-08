/** Runtime configuration. Only NEXT_PUBLIC_* values reach the browser. */

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1").replace(/\/+$/, "");

/**
 * Auth endpoints go to the frontend's own origin and are proxied to the backend
 * by a Next.js rewrite, so the HttpOnly refresh cookie is first-party (SEC-1).
 */
export const AUTH_BASE = "/api/v1/auth";
