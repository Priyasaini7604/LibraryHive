import type { Metadata } from "next";

import { StudentComplaintDetail } from "@/components/complaints/student-complaints";

export const metadata: Metadata = { title: "Complaint" };

export default async function StudentComplaintPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <StudentComplaintDetail id={id} />;
}
