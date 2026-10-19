import type { Metadata } from "next";

import { OwnerComplaintDetail } from "@/components/complaints/owner-complaints";

export const metadata: Metadata = { title: "Complaint" };

export default async function OwnerComplaintPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <OwnerComplaintDetail id={id} />;
}
