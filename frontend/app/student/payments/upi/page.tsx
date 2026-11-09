import type { Metadata } from "next";

import { StudentUpiRequestsScreen } from "@/components/student/upi-requests-screen";

export const metadata: Metadata = { title: "My UPI payment requests" };

export default function Page() {
  return <StudentUpiRequestsScreen />;
}
