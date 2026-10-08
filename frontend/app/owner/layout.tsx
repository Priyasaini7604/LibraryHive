"use client";

import { AuthGuard } from "@/components/layout/auth-guard";
import { OwnerShell } from "@/components/layout/shells";

/** Owner area: role-guarded; owners without a library are sent to onboarding (UI_ARCHITECTURE.md 3.4). */
export default function OwnerLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard requiredRole="owner">
      <OwnerShell>{children}</OwnerShell>
    </AuthGuard>
  );
}
