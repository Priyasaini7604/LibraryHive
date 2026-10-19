import type { Metadata } from "next";

import { CheckoutScreen } from "@/components/booking/checkout-screen";

export const metadata: Metadata = { title: "Complete your booking" };

export default async function BookPage({ params }: { params: Promise<{ holdId: string }> }) {
  const { holdId } = await params;
  return <CheckoutScreen holdId={holdId} />;
}
