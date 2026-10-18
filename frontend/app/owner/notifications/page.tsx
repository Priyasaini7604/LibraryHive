import type { Metadata } from "next";

import { NotificationsScreen } from "@/components/notifications/notifications-screen";

export const metadata: Metadata = { title: "Notifications" };

export default function OwnerNotificationsPage() {
  return <NotificationsScreen viewer="owner" />;
}
