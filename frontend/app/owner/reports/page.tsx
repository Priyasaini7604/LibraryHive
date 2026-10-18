import type { Metadata } from "next";

import { ReportsScreen } from "@/components/owner/reports-screen";

export const metadata: Metadata = { title: "Reports" };

export default function OwnerReportsPage() {
  return <ReportsScreen />;
}
