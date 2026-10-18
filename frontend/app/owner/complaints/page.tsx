import type { Metadata } from "next";

import { OwnerComplaintsScreen } from "@/components/complaints/owner-complaints";

export const metadata: Metadata = { title: "Complaints" };

export default function OwnerComplaintsPage() {
  return <OwnerComplaintsScreen />;
}
