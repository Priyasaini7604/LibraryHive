/** Auth endpoints (BACKEND_ARCHITECTURE.md #7–#10, SEC-1). Implemented by the backend in T04. */

import { api, refreshAccessToken } from "../api-client";
import { tokenStore } from "../auth";
import type { LoginResponse, User } from "../types";

export async function login(email: string, password: string): Promise<User> {
  const result = await api.post<LoginResponse>("/auth/login/", { email, password }, { auth: false });
  tokenStore.set(result.access);
  return result.user;
}

export async function logout(): Promise<void> {
  try {
    await api.post<Record<string, never>>("/auth/logout/", {});
  } finally {
    tokenStore.clear();
  }
}

export function fetchMe(): Promise<User> {
  return api.get<User>("/auth/me/");
}

/** Restore a session on page load from the HttpOnly refresh cookie. */
export function restoreSession(): Promise<boolean> {
  return refreshAccessToken();
}
