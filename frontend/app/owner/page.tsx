import type { Metadata } from "next";

import { OwnerDashboardScreen } from "@/components/owner/dashboard-screen";

export const metadata: Metadata = { title: "Dashboard" };

export default function OwnerHomePage() {
  return <OwnerDashboardScreen />;
}
