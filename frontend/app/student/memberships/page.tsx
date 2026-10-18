import type { Metadata } from "next";

import { MembershipsScreen } from "@/components/student/memberships-screen";

export const metadata: Metadata = { title: "My membership" };

export default function StudentMembershipsPage() {
  return <MembershipsScreen />;
}
