import type { Metadata } from "next";

import { StudentVisitsScreen } from "@/components/visits/visits-screens";

export const metadata: Metadata = { title: "Visit requests" };

export default function StudentVisitsPage() {
  return <StudentVisitsScreen />;
}
