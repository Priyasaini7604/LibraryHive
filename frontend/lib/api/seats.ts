/** Seat maps and holds (BACKEND_ARCHITECTURE.md #16, #30-#40). */

import { api } from "../api-client";
import type { OwnerSeat, PublicSeat, SeatMap, StudentHold } from "../types";

export function fetchPublicSeats(libraryId: string, signal?: AbortSignal): Promise<SeatMap<PublicSeat>> {
  return api.get<SeatMap<PublicSeat>>(`/libraries/${libraryId}/seats/`, { auth: false, signal });
}

export function fetchOwnerSeats(includeInactive = false): Promise<SeatMap<OwnerSeat>> {
  return api.get<SeatMap<OwnerSeat>>("/owner/seats/", { query: { include_inactive: includeInactive ? "true" : undefined } });
}

export type AddSeatsInput =
  | { mode: "grid"; rows: string[]; seats_per_row: number }
  | { mode: "list"; seats: { label: string; row_label?: string; position?: number | null }[] };

export function addSeats(input: AddSeatsInput): Promise<{ created: OwnerSeat[]; skipped: unknown[] }> {
  return api.post("/owner/seats/", input);
}

export function updateSeat(
  seatId: string,
  input: { label?: string; row_label?: string; position?: number | null },
): Promise<OwnerSeat> {
  return api.patch<OwnerSeat>(`/owner/seats/${seatId}/`, input);
}

export function deactivateSeat(seatId: string, reason: string): Promise<OwnerSeat> {
  return api.post<OwnerSeat>(`/owner/seats/${seatId}/deactivate/`, { reason });
}

export function disableSeat(seatId: string, reason: string): Promise<OwnerSeat> {
  return api.post<OwnerSeat>(`/owner/seats/${seatId}/disable/`, { reason });
}

export function enableSeat(seatId: string): Promise<OwnerSeat> {
  return api.post<OwnerSeat>(`/owner/seats/${seatId}/enable/`);
}

export function placeManualHold(seatId: string, reason: string): Promise<{ id: string }> {
  return api.post(`/owner/seats/${seatId}/manual-hold/`, { reason });
}

export function releaseHold(holdId: string, reason: string): Promise<{ id: string }> {
  return api.post(`/owner/holds/${holdId}/release/`, { reason });
}

/** Start a booking: hold the seat for the configured window (#38). */
export function createHold(input: { seat_id: string; plan_id: string }): Promise<StudentHold> {
  return api.post<StudentHold>("/student/holds/", input);
}

export function fetchCurrentHolds(): Promise<StudentHold[]> {
  return api.get<StudentHold[]>("/student/holds/current/");
}

export function cancelHold(holdId: string): Promise<StudentHold> {
  return api.post<StudentHold>(`/student/holds/${holdId}/cancel/`);
}
