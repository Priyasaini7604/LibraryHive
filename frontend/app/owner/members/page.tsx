import type { Metadata } from "next";

import { MembersScreen } from "@/components/owner/members-screen";

export const metadata: Metadata = { title: "Members" };

export default function OwnerMembersPage() {
  return <MembersScreen />;
}
