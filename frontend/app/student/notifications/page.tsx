import type { Metadata } from "next";

import { NotificationsScreen } from "@/components/notifications/notifications-screen";

export const metadata: Metadata = { title: "Notifications" };

export default function StudentNotificationsPage() {
  return <NotificationsScreen viewer="student" />;
}
