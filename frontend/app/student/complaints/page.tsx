import type { Metadata } from "next";

import { StudentComplaintsScreen } from "@/components/complaints/student-complaints";

export const metadata: Metadata = { title: "Complaints" };

export default function StudentComplaintsPage() {
  return <StudentComplaintsScreen />;
}
