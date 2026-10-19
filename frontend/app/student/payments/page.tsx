import type { Metadata } from "next";

import { PaymentsScreen } from "@/components/student/payments-screen";

export const metadata: Metadata = { title: "My payments" };

export default function StudentPaymentsPage() {
  return <PaymentsScreen />;
}
