import type { Metadata } from "next";

import { LibrarySettings } from "@/components/owner/library-settings";

export const metadata: Metadata = { title: "Your library" };

export default function OwnerLibraryPage() {
  return <LibrarySettings />;
}
