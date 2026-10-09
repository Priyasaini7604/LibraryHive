/**
 * Shared API types mirroring BACKEND_ARCHITECTURE.md.
 *
 * Once the backend schema is available these are checked against the types
 * generated from /api/v1/schema/ (`npm run api:types` -> lib/api-types.gen.ts).
 */

import type { FieldErrors } from "./errors";

/** Standard response envelope (BACKEND_ARCHITECTURE.md 4.1). */
export interface Envelope<T> {
  success: boolean;
  data: T | null;
  error: string | null;
  error_code: string | null;
  details: FieldErrors | null;
  request_id: string | null;
}

/** Paginated list payload (BACKEND_ARCHITECTURE.md 4.4). */
export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export type Role = "owner" | "student";

export interface Vocabulary {
  code: string;
  name: string;
}

/** Current user (BACKEND_ARCHITECTURE.md #10). */
export interface User {
  id: string;
  name: string;
  email: string;
  phone: string;
  role: Role;
  domain: Vocabulary | null;
  has_library?: boolean;
  created_at: string;
}

/** Login / refresh responses (SEC-1: the refresh token is a cookie, never in JSON). */
export interface AccessTokenResponse {
  access: string;
}

export interface LoginResponse extends AccessTokenResponse {
  user: User;
}
