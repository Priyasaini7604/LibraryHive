import type { Metadata } from "next";

import { MembershipDetailScreen } from "@/components/student/membership-detail-screen";

export const metadata: Metadata = { title: "Membership" };

export default async function StudentMembershipPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <MembershipDetailScreen id={id} />;
}
