/**
 * Access-token store (SEC-1, SECURITY.md section 4.2).
 *
 * The access token lives in memory only: never in localStorage, sessionStorage
 * or cookies readable by JavaScript. The refresh token is an HttpOnly cookie
 * the browser sends to /api/v1/auth/* automatically; this module never sees it.
 */

type Listener = (token: string | null) => void;

let accessToken: string | null = null;
const listeners = new Set<Listener>();

export const tokenStore = {
  get(): string | null {
    return accessToken;
  },
  set(token: string | null): void {
    accessToken = token;
    listeners.forEach((listener) => listener(token));
  },
  clear(): void {
    tokenStore.set(null);
  },
  subscribe(listener: Listener): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};
