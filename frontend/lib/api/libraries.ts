/** Libraries, plans and photos (BACKEND_ARCHITECTURE.md #2, #3, #14, #15, #17-#29). */

import { api } from "../api-client";
import { API_URL } from "../config";
import { isApiError } from "../errors";
import type {
  LibraryDetail,
  LibraryFilters,
  LibrarySummary,
  OwnerLibrary,
  OwnerPhoto,
  OwnerPlan,
  Page,
  Vocabulary,
} from "../types";

/** Photo URLs are relative in local development (served by the backend) and absolute in production. */
export function mediaUrl(url: string): string {
  return /^https?:\/\//.test(url) ? url : new URL(url, API_URL).href;
}

export function fetchDomains(): Promise<Vocabulary[]> {
  return api.get<Vocabulary[]>("/meta/domains/", { auth: false });
}

export function fetchAmenities(): Promise<Vocabulary[]> {
  return api.get<Vocabulary[]>("/meta/amenities/", { auth: false });
}

export function fetchLibraries(filters: LibraryFilters = {}, signal?: AbortSignal): Promise<Page<LibrarySummary>> {
  return api.get<Page<LibrarySummary>>("/libraries/", { query: { ...filters }, auth: false, signal });
}

export function fetchLibrary(id: string, signal?: AbortSignal): Promise<LibraryDetail> {
  return api.get<LibraryDetail>(`/libraries/${id}/`, { auth: false, signal });
}

/** Writable profile fields (#17, #19). Codes refer to the vocabularies of #2 and #3. */
export interface LibraryInput {
  name: string;
  description: string;
  address: string;
  city: string;
  area: string;
  latitude: number | null;
  longitude: number | null;
  contact_phone: string;
  contact_email: string;
  opens_at: string | null;
  closes_at: string | null;
  operating_notes: string;
  domain_codes: string[];
  amenity_codes: string[];
}

/** The owner's library, or null before onboarding step 1 (409 LIBRARY_REQUIRED). */
export async function fetchOwnerLibrary(): Promise<OwnerLibrary | null> {
  try {
    return await api.get<OwnerLibrary>("/owner/library/");
  } catch (error) {
    if (isApiError(error, "LIBRARY_REQUIRED")) return null;
    throw error;
  }
}

export function createLibrary(input: LibraryInput): Promise<OwnerLibrary> {
  return api.post<OwnerLibrary>("/owner/library/", input);
}

export function updateLibrary(input: Partial<LibraryInput>): Promise<OwnerLibrary> {
  return api.patch<OwnerLibrary>("/owner/library/", input);
}

export interface PlanInput {
  name: string;
  duration_days: number;
  price: string;
  timing_note: string;
}

export function fetchOwnerPlans(): Promise<OwnerPlan[]> {
  return api.get<OwnerPlan[]>("/owner/library/plans/");
}

export function createPlan(input: PlanInput): Promise<OwnerPlan> {
  return api.post<OwnerPlan>("/owner/library/plans/", input);
}

export function updatePlan(id: string, input: Partial<PlanInput>): Promise<OwnerPlan> {
  return api.patch<OwnerPlan>(`/owner/library/plans/${id}/`, input);
}

export function setPlanActive(id: string, active: boolean): Promise<OwnerPlan> {
  return api.post<OwnerPlan>(`/owner/library/plans/${id}/${active ? "activate" : "deactivate"}/`);
}

export function fetchOwnerPhotos(): Promise<OwnerPhoto[]> {
  return api.get<OwnerPhoto[]>("/owner/library/photos/");
}

export function uploadPhoto(file: File, caption = ""): Promise<OwnerPhoto> {
  const body = new FormData();
  body.append("image", file);
  if (caption) body.append("caption", caption);
  return api.post<OwnerPhoto>("/owner/library/photos/", body);
}

export function updatePhoto(id: string, input: { caption?: string; display_order?: number }): Promise<OwnerPhoto> {
  return api.patch<OwnerPhoto>(`/owner/library/photos/${id}/`, input);
}

export function setPhotoCover(id: string): Promise<OwnerPhoto> {
  return api.post<OwnerPhoto>(`/owner/library/photos/${id}/set-cover/`);
}

export function deletePhoto(id: string): Promise<Record<string, never>> {
  return api.delete<Record<string, never>>(`/owner/library/photos/${id}/`);
}
