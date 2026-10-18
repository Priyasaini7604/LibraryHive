import type { Metadata } from "next";

import { OwnerAttendanceScreen } from "@/components/attendance/owner-attendance-screen";

export const metadata: Metadata = { title: "Attendance" };

export default function OwnerAttendancePage() {
  return <OwnerAttendanceScreen />;
}
