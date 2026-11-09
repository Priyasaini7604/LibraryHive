import type { Metadata } from "next";

import { UpiSettingsScreen } from "@/components/owner/upi-settings-screen";

export const metadata: Metadata = { title: "UPI payment settings" };

export default function Page() {
  return <UpiSettingsScreen />;
}
