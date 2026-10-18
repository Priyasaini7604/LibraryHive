/** Auth endpoints (BACKEND_ARCHITECTURE.md #7–#10, SEC-1). Implemented by the backend in T04. */

import { api, refreshAccessToken } from "../api-client";
import { tokenStore } from "../auth";
import type { ClaimChannel, ClaimStartResponse, LoginResponse, MessageResponse, Role, User, Vocabulary } from "../types";

export interface RegisterInput {
  role: Role;
  name: string;
  email: string;
  phone: string;
  password: string;
  domain_code?: string;
}

export interface ClaimCompleteInput {
  phone: string;
  code: string;
  password: string;
  email?: string;
  name?: string;
}

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

/** Create an owner or student account and sign it in (#6). Throws CLAIM_REQUIRED when an offline record matches. */
export async function register(input: RegisterInput): Promise<User> {
  const result = await api.post<LoginResponse>("/auth/register/", input, { auth: false });
  tokenStore.set(result.access);
  return result.user;
}

/** Edit name, phone and (students) exam domain (#11). Email is not editable. */
export function updateProfile(input: { name?: string; phone?: string; domain_code?: string | null }): Promise<User> {
  return api.patch<User>("/auth/me/", input);
}

/** Public exam-domain vocabulary (#2). */
export function fetchDomains(): Promise<Vocabulary[]> {
  return api.get<Vocabulary[]>("/meta/domains/", { auth: false });
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

/**
 * Begin claiming an offline account (#12). The answer is the same for every phone, so the UI
 * must always show the neutral "check your email" step. A record with no email on file gets
 * CLAIM_INVALID: the student must ask the library for a claim code instead.
 */
export function startClaim(input: { phone: string; channel: ClaimChannel; email?: string }): Promise<ClaimStartResponse> {
  return api.post<ClaimStartResponse>("/auth/claim/start/", input, { auth: false });
}

/** Finish the claim with the emailed or owner-issued code (#13). Signs the student in like login. */
export async function completeClaim(input: ClaimCompleteInput): Promise<User> {
  const result = await api.post<LoginResponse>("/auth/claim/complete/", input, { auth: false });
  tokenStore.set(result.access);
  return result.user;
}
