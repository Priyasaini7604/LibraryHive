import type { Metadata } from "next";

import { DuesScreen } from "@/components/owner/dues-screen";

export const metadata: Metadata = { title: "Dues" };

export default function OwnerDuesPage() {
  return <DuesScreen />;
}
