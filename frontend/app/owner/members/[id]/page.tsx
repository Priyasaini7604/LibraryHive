import type { Metadata } from "next";

import { MemberDetailScreen } from "@/components/owner/member-detail-screen";

export const metadata: Metadata = { title: "Member" };

export default async function OwnerMemberPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <MemberDetailScreen id={id} />;
}
