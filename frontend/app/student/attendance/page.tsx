import type { Metadata } from "next";

import { StudentAttendanceScreen } from "@/components/attendance/student-attendance-screen";

export const metadata: Metadata = { title: "Attendance" };

export default function StudentAttendancePage() {
  return <StudentAttendanceScreen />;
}
