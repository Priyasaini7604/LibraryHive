import { PublicShell } from "@/components/layout/shells";

/** Public pages: landing, discover, library pages (UI_ARCHITECTURE.md 3.1). Pages arrive in T16. */
export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return <PublicShell>{children}</PublicShell>;
}
