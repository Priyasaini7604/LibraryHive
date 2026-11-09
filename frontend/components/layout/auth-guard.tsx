"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { FullPageSkeleton } from "@/components/ui/states";
import { useAuth } from "@/lib/auth-context";
import { homeFor, loginUrl } from "@/lib/navigation";
import type { Role, User } from "@/lib/types";

const ONBOARDING_PATH = "/owner/onboarding";

type GuardDecision = { kind: "wait" } | { kind: "redirect"; to: string } | { kind: "allow" };

/** Pure decision logic (UI_ARCHITECTURE.md 3.4), unit tested separately. */
export function decideAccess(
  status: "loading" | "authenticated" | "anonymous",
  user: User | null,
  role: Role | "platform",
  pathname: string,
): GuardDecision {
  if (status === "loading") return { kind: "wait" };
  if (status === "anonymous" || !user) return { kind: "redirect", to: loginUrl(pathname) };
  const platformAdmin = user.is_platform_admin === true;
  if (role === "platform") {
    return platformAdmin ? { kind: "allow" } : { kind: "redirect", to: homeFor(user.role) };
  }
  // The team has no library or student account to manage: send them to their own area.
  if (platformAdmin) return { kind: "redirect", to: homeFor(user.role, true) };
  if (user.role !== role) return { kind: "redirect", to: homeFor(user.role) };
  if (role === "owner" && user.has_library === false && !pathname.startsWith(ONBOARDING_PATH)) {
    return { kind: "redirect", to: ONBOARDING_PATH };
  }
  return { kind: "allow" };
}

/**
 * Client-side routing guard for /student and /owner. It improves the
 * experience only; every permission is enforced by the backend.
 */
export function AuthGuard({ requiredRole, children }: { requiredRole: Role | "platform"; children: React.ReactNode }) {
  const { status, user } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const decision = decideAccess(status, user, requiredRole, pathname);

  useEffect(() => {
    if (decision.kind === "redirect") router.replace(decision.to);
  }, [decision, router]);

  return decision.kind === "allow" ? <>{children}</> : <FullPageSkeleton />;
}
