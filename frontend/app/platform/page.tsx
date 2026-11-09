import type { Metadata } from "next";

import { PlatformOverviewScreen } from "@/components/platform/overview-screen";

export const metadata: Metadata = { title: "Platform analytics", robots: { index: false, follow: false } };

export default function PlatformPage() {
  return <PlatformOverviewScreen />;
}
