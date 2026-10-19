import type { Metadata } from "next";

import { ActivityScreen } from "@/components/owner/activity-screen";

export const metadata: Metadata = { title: "Activity log" };

export default function OwnerActivityPage() {
  return <ActivityScreen />;
}
