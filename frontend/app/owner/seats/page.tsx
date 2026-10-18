import type { Metadata } from "next";

import { SeatManager } from "@/components/owner/seat-manager";

export const metadata: Metadata = { title: "Seats" };

export default function OwnerSeatsPage() {
  return <SeatManager />;
}
