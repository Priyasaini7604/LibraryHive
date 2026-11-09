"use client";

import { AuthGuard } from "@/components/layout/auth-guard";
import { PlatformShell } from "@/components/layout/shells";

/**
 * Internal LibraryHive team area. This guard only improves the experience: every /platform API call is
 * permission-checked on the backend (superuser + staff), so hiding this route is not the security boundary.
 */
export default function PlatformLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard requiredRole="platform">
      <PlatformShell>{children}</PlatformShell>
    </AuthGuard>
  );
}
