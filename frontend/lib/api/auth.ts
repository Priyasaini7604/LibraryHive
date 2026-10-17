/** Auth endpoints (BACKEND_ARCHITECTURE.md #7–#10, SEC-1). Implemented by the backend in T04. */

import { api, refreshAccessToken } from "../api-client";
import { tokenStore } from "../auth";
import type { LoginResponse, MessageResponse, User } from "../types";

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

/**
 * Ask for a password-reset code (#13a). The answer is the same for every email,
 * so the UI must always show the neutral confirmation.
 */
export function requestPasswordReset(email: string): Promise<MessageResponse> {
  return api.post<MessageResponse>("/auth/password-reset/request/", { email }, { auth: false });
}

/** Set a new password with the emailed code (#13b). Issues no session; the user logs in afterwards. */
export function confirmPasswordReset(input: { email: string; code: string; newPassword: string }): Promise<MessageResponse> {
  return api.post<MessageResponse>(
    "/auth/password-reset/confirm/",
    { email: input.email, code: input.code, new_password: input.newPassword },
    { auth: false },
  );
}
