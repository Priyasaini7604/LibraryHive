import type { Metadata } from "next";

import { StudentDashboardScreen } from "@/components/student/dashboard-screen";

export const metadata: Metadata = { title: "Home" };

export default function StudentHomePage() {
  return <StudentDashboardScreen />;
}
