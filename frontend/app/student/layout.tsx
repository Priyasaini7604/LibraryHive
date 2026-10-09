"use client";

import { AuthGuard } from "@/components/layout/auth-guard";
import { StudentShell } from "@/components/layout/shells";

/** Student area: role-guarded (UI_ARCHITECTURE.md 3.4); the backend enforces every permission. */
export default function StudentLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard requiredRole="student">
      <StudentShell>{children}</StudentShell>
    </AuthGuard>
  );
}
