import type { Metadata } from "next";

import { OwnerVisitsScreen } from "@/components/visits/visits-screens";

export const metadata: Metadata = { title: "Visit requests" };

export default function OwnerVisitsPage() {
  return <OwnerVisitsScreen />;
}
