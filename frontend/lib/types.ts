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

/** Response of the password-reset endpoints (#13a, #13b): a neutral message only, never tokens. */
export interface MessageResponse {
  message: string;
}

/** Libraries, plans and photos (BACKEND_ARCHITECTURE.md #14, #15, #17-#29). */

export interface PricingPlan {
  id: string;
  name: string;
  duration_days: number;
  /** Decimal string such as "1200.00"; format it with formatMoney. */
  price: string;
  timing_note: string;
}

export interface OwnerPlan extends PricingPlan {
  is_active: boolean;
  /** True once a membership, payment or hold references the plan (it can only be deactivated). */
  in_use: boolean;
}

export interface PublicPhoto {
  id: string;
  url: string;
  thumb_url: string;
  caption: string;
  is_cover: boolean;
}

export interface OwnerPhoto extends PublicPhoto {
  display_order: number;
  width: number;
  height: number;
}

/** Present only once the seat inventory exists (T10); never invented by the client. */
export interface SeatCounts {
  total: number;
  empty: number;
  reserved: number;
  occupied: number;
}

/** One card of the discovery list (#14). */
export interface LibrarySummary {
  id: string;
  name: string;
  city: string;
  area: string;
  cover?: { thumb_url: string };
  amenities: string[];
  domains: string[];
  starting_price: string | null;
  seat_counts?: SeatCounts;
  distance_km?: number;
}

/** The public explore page (#15). */
export interface LibraryDetail {
  id: string;
  name: string;
  description: string;
  address: string;
  city: string;
  area: string;
  latitude: number | null;
  longitude: number | null;
  contact_phone: string | null;
  contact_email: string | null;
  opens_at: string | null;
  closes_at: string | null;
  operating_notes: string;
  amenities: Vocabulary[];
  domains: Vocabulary[];
  plans: PricingPlan[];
  photos: PublicPhoto[];
  seat_counts?: SeatCounts;
}

export interface PublishChecklist {
  has_profile: boolean;
  has_location: boolean;
  has_active_plan: boolean;
  has_active_seat: boolean;
}

/** The owner's own library (#17-#19). */
export interface OwnerLibrary {
  id: string;
  name: string;
  description: string;
  address: string;
  city: string;
  area: string;
  latitude: number | null;
  longitude: number | null;
  contact_phone: string | null;
  contact_email: string | null;
  opens_at: string | null;
  closes_at: string | null;
  operating_notes: string;
  domains: Vocabulary[];
  amenities: Vocabulary[];
  is_published: boolean;
  is_active: boolean;
  publish_checklist: PublishChecklist;
}

export type LibrarySort = "distance" | "price" | "available";

export interface LibraryFilters {
  search?: string;
  domain?: string;
  amenity?: string[];
  lat?: number;
  lng?: number;
  radius_km?: number;
  sort?: LibrarySort;
  page?: number;
  page_size?: number;
}

export * from "./ops-types";
