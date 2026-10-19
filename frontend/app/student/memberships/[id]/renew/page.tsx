import type { Metadata } from "next";

import { RenewalScreen } from "@/components/booking/renewal-screen";

export const metadata: Metadata = { title: "Renew your membership" };

export default async function RenewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RenewalScreen membershipId={id} />;
}
