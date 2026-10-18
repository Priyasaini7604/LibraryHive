import type { Metadata } from "next";

import { AdmissionScreen } from "@/components/owner/admission-screen";

export const metadata: Metadata = { title: "Admit a student" };

export default async function OwnerAdmissionPage({ searchParams }: { searchParams: Promise<{ seat?: string }> }) {
  const { seat } = await searchParams;
  return <AdmissionScreen initialSeatId={seat} />;
}
