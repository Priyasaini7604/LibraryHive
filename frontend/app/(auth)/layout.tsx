import { PublicShell } from "@/components/layout/shells";

/** Login, register, claim and password reset (UI_ARCHITECTURE.md 3.1).. */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return <PublicShell>{children}</PublicShell>;
}
