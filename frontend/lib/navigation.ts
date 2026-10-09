/**
 * Safe redirects and the role navigation (UI_ARCHITECTURE.md 3.4 and 4).
 * Navigation targets are the routes defined in UI_ARCHITECTURE.md section 3;
 * each screen is built by its task (see IMPLEMENTATION_PLAN.md).
 */

import type { Role } from "./types";

/** Accept only same-origin relative paths for ?next= (SECURITY.md section 7). */
export function safeNextPath(next: string | null | undefined): string | null {
  if (!next || !next.startsWith("/")) return null;
  if (next.startsWith("//") || next.startsWith("/\\")) return null;
  if (/[\u0000-\u001f]/.test(next)) return null;
  return next;
}

export function homeFor(role: Role): string {
  return role === "owner" ? "/owner" : "/student";
}

export function loginUrl(next: string): string {
  return `/login?next=${encodeURIComponent(next)}`;
}

export type NavIcon =
  | "home"
  | "search"
  | "id-card"
  | "clock"
  | "wallet"
  | "bell"
  | "user"
  | "message"
  | "calendar"
  | "layout"
  | "armchair"
  | "users"
  | "alert"
  | "credit-card"
  | "inbox"
  | "building"
  | "chart";

export interface NavItem {
  href: string;
  label: string;
  icon: NavIcon;
  /** Shown in the 5-item bottom bar on small screens. */
  mobile?: boolean;
}

export const STUDENT_NAV: NavItem[] = [
  { href: "/discover", label: "Discover", icon: "search", mobile: true },
  { href: "/student", label: "Home", icon: "home", mobile: true },
  { href: "/student/memberships", label: "Membership", icon: "id-card" },
  { href: "/student/attendance", label: "Attendance", icon: "clock", mobile: true },
  { href: "/student/payments", label: "Payments", icon: "wallet" },
  { href: "/student/notifications", label: "Alerts", icon: "bell", mobile: true },
  { href: "/student/profile", label: "Profile", icon: "user", mobile: true },
];

export const STUDENT_MENU: NavItem[] = [
  { href: "/student/complaints", label: "Complaints", icon: "message" },
  { href: "/student/visits", label: "Visit requests", icon: "calendar" },
  { href: "/student/profile", label: "Profile", icon: "user" },
];

export const OWNER_NAV: NavItem[] = [
  { href: "/owner", label: "Dashboard", icon: "layout", mobile: true },
  { href: "/owner/seats", label: "Seats", icon: "armchair", mobile: true },
  { href: "/owner/members", label: "Members", icon: "users", mobile: true },
  { href: "/owner/dues", label: "Dues", icon: "alert" },
  { href: "/owner/payments", label: "Payments", icon: "credit-card" },
  { href: "/owner/attendance", label: "Attendance", icon: "clock" },
  { href: "/owner/complaints", label: "Complaints", icon: "message" },
  { href: "/owner/visits", label: "Visits", icon: "calendar" },
  { href: "/owner/library", label: "Library", icon: "building" },
  { href: "/owner/reports", label: "Reports", icon: "chart" },
];

/** Owner bottom bar: Inbox groups complaints and visits; More opens the full menu. */
export const OWNER_MOBILE_INBOX: NavItem = { href: "/owner/complaints", label: "Inbox", icon: "inbox", mobile: true };

/** Longest matching prefix wins, so /owner/members/1 highlights Members, not Dashboard. */
export function activeHref(pathname: string, items: NavItem[]): string | null {
  const matches = items.filter((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
  matches.sort((a, b) => b.href.length - a.href.length);
  return matches[0]?.href ?? null;
}
