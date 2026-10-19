import type { Metadata } from "next";

import { OwnerPaymentsScreen } from "@/components/owner/owner-payments-screen";

export const metadata: Metadata = { title: "Payments" };

export default function OwnerPaymentsPage() {
  return <OwnerPaymentsScreen />;
}
