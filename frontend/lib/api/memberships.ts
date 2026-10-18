/** Members, dues, admission, renewal and archival (BACKEND_ARCHITECTURE.md #48-#57). */

import { api } from "../api-client";
import type {
  AdmissionLookup,
  AdmissionResult,
  DueRow,
  OfflineMethod,
  OwnerMember,
  OwnerMemberDetail,
  Page,
  PaymentPeriod,
  StudentMembership,
  StudentMembershipDetail,
} from "../types";

export function fetchStudentMemberships(includeArchived = false): Promise<StudentMembership[]> {
  return api.get<StudentMembership[]>("/student/memberships/", { query: { include_archived: includeArchived ? "true" : undefined } });
}

export function fetchStudentMembership(id: string): Promise<StudentMembershipDetail> {
  return api.get<StudentMembershipDetail>(`/student/memberships/${id}/`);
}

export interface MemberFilters {
  status?: "active" | "due" | "overdue" | "archived" | "current";
  domain?: string;
  source?: "online" | "offline";
  search?: string;
  page?: number;
}

export function fetchMembers(filters: MemberFilters = {}): Promise<Page<OwnerMember>> {
  return api.get<Page<OwnerMember>>("/owner/members/", { query: { ...filters } });
}

export function fetchMember(id: string): Promise<OwnerMemberDetail> {
  return api.get<OwnerMemberDetail>(`/owner/members/${id}/`);
}

export interface RenewalInput {
  method: OfflineMethod;
  plan_id?: string;
  paid_at?: string;
  notes?: string;
}

/** Record an offline renewal payment (#48). The amount is the plan price on the server. */
export function recordRenewal(membershipId: string, input: RenewalInput): Promise<{ payment: PaymentPeriod; membership: OwnerMember }> {
  return api.post(`/owner/members/${membershipId}/renewals/`, input);
}

export function archiveMember(membershipId: string, reason: string): Promise<OwnerMember> {
  return api.post<OwnerMember>(`/owner/members/${membershipId}/archive/`, { reason });
}

export function fetchDues(query: { status?: "due" | "overdue"; bucket?: "1-7" | "8-15" | "15+"; page?: number } = {}): Promise<Page<DueRow>> {
  return api.get<Page<DueRow>>("/owner/dues/", { query });
}

/** One-time claim code for a walk-in student (#55). The code is returned once and never stored. */
export function issueClaimCode(studentId: string): Promise<{ code: string; expires_at: string }> {
  return api.post<{ code: string; expires_at: string }>(`/owner/students/${studentId}/claim-code/`);
}

export function lookupAdmission(input: { phone: string; email?: string }): Promise<AdmissionLookup> {
  return api.post<AdmissionLookup>("/owner/admissions/lookup/", input);
}

export interface AdmissionInput {
  student: { name: string; phone: string; email?: string; domain_code?: string };
  seat_id: string;
  plan_id: string;
  start_date?: string;
  payment: { method: OfflineMethod; paid_at?: string; notes?: string };
}

/** Student, membership and cash payment in one transaction (#54). */
export function admitStudent(input: AdmissionInput): Promise<AdmissionResult> {
  return api.post<AdmissionResult>("/owner/admissions/", input);
}
