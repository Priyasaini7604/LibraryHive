/**
 * The only place in the frontend that talks to the backend (AGENTS.md 2.3).
 *
 * - Unwraps the standard envelope and throws ApiError with the backend's code.
 * - Sends the in-memory access token; on a 401 it refreshes once (a single
 *   shared refresh for concurrent requests) and retries the request once.
 * - /auth/* calls go to the frontend origin (proxied, SEC-1) with cookies;
 *   all other calls go straight to the API without cookies.
 * - Keeps the server clock offset from the Date header for countdowns.
 */

import { API_URL, AUTH_BASE } from "./config";
import { ApiError, NETWORK_ERROR } from "./errors";
import { tokenStore } from "./auth";
import type { AccessTokenResponse, Envelope } from "./types";

export type HttpMethod = "GET" | "POST" | "PATCH" | "DELETE";
export type QueryValue = string | number | boolean | null | undefined | Array<string | number>;

export interface RequestOptions {
  method?: HttpMethod;
  body?: unknown;
  query?: Record<string, QueryValue>;
  signal?: AbortSignal;
  /** Send the access token (default true). */
  auth?: boolean;
}

// Endpoints that must never trigger the refresh-and-retry flow.
const NO_REFRESH_PREFIXES = [
  "/auth/refresh/",
  "/auth/login/",
  "/auth/logout/",
  "/auth/register/",
  "/auth/claim/",
  "/auth/password-reset/",
];

let serverOffsetMs = 0;
let refreshInFlight: Promise<boolean> | null = null;
let sessionExpiredHandler: (() => void) | null = null;

/** Current time according to the server clock (UI_ARCHITECTURE.md 5.3). */
export function serverNow(): number {
  return Date.now() + serverOffsetMs;
}

/** Called once when a refresh fails and the user must log in again. */
export function onSessionExpired(handler: (() => void) | null): void {
  sessionExpiredHandler = handler;
}

function isAuthPath(path: string): boolean {
  return path.startsWith("/auth/");
}

export function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const base = isAuthPath(path) ? `${AUTH_BASE}${path.slice("/auth".length)}` : `${API_URL}${path}`;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((item) => params.append(key, String(item)));
    else params.append(key, String(value));
  }
  const search = params.toString();
  return search ? `${base}?${search}` : base;
}

function updateServerOffset(response: Response): void {
  const header = response.headers.get("Date");
  const serverTime = header ? Date.parse(header) : Number.NaN;
  if (!Number.isNaN(serverTime)) serverOffsetMs = serverTime - Date.now();
}

async function send<T>(path: string, options: RequestOptions, token: string | null): Promise<T> {
  const { method = "GET", body, query, signal, auth = true } = options;
  const headers: Record<string, string> = { Accept: "application/json" };
  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body; // the browser sets the multipart boundary
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: payload,
      signal,
      credentials: isAuthPath(path) ? "same-origin" : "omit",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError({ status: 0, code: NETWORK_ERROR, message: "Network request failed." });
  }

  updateServerOffset(response);
  const isJson = response.headers.get("Content-Type")?.includes("application/json") ?? false;
  const envelope = (isJson ? await response.json() : null) as Envelope<T> | null;

  if (!response.ok || !envelope || envelope.success === false) {
    throw new ApiError({
      status: response.status,
      code: envelope?.error_code ?? `HTTP_${response.status}`,
      message: envelope?.error ?? response.statusText ?? "Request failed.",
      details: envelope?.details ?? null,
      requestId: envelope?.request_id ?? response.headers.get("X-Request-ID"),
    });
  }
  return envelope.data as T;
}

/**
 * Get a new access token using the HttpOnly refresh cookie.
 * Concurrent callers share one in-flight refresh.
 */
export function refreshAccessToken(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = send<AccessTokenResponse>("/auth/refresh/", { method: "POST", body: {}, auth: false }, null)
      .then((result) => {
        tokenStore.set(result.access);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  try {
    return await send<T>(path, options, tokenStore.get());
  } catch (error) {
    const canRefresh =
      error instanceof ApiError &&
      error.status === 401 &&
      options.auth !== false &&
      !NO_REFRESH_PREFIXES.some((prefix) => path.startsWith(prefix));
    if (!canRefresh) throw error;

    if (await refreshAccessToken()) {
      return send<T>(path, options, tokenStore.get());
    }
    tokenStore.clear();
    sessionExpiredHandler?.();
    throw error;
  }
}

export const api = {
  get: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "POST", body }),
  patch: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "PATCH", body }),
  delete: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "DELETE" }),
};
