import type { Metadata } from "next";

import { UpiRequestsScreen } from "@/components/owner/upi-requests-screen";

export const metadata: Metadata = { title: "Payments to check" };

export default function Page() {
  return <UpiRequestsScreen />;
}
