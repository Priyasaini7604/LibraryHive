import type { Metadata } from "next";

import { ReceiptScreen } from "@/components/student/receipt-screen";

export const metadata: Metadata = { title: "Receipt" };

export default async function StudentReceiptPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ReceiptScreen id={id} />;
}
