import type { Metadata } from "next";

import { PlatformLibrariesScreen } from "@/components/platform/libraries-screen";

export const metadata: Metadata = { title: "Library performance", robots: { index: false, follow: false } };

export default function PlatformLibrariesPage() {
  return <PlatformLibrariesScreen />;
}
