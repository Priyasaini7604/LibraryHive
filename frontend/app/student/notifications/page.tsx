"use client";

import { useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { authStorage } from "@/lib/auth";
import { Notification } from "@/lib/types";

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [markingId, setMarkingId] = useState<string | null>(null);

  useEffect(() => {
    const loadNotifications = async () => {
      const token = authStorage.getAccessToken();

      if (!token) {
        setError("Please login to view notifications.");
        setLoading(false);
        return;
      }

      try {
        const data = await apiClient.getNotifications();
        setNotifications(data);
      } catch (err) {
        console.error("Failed to load notifications:", err);
        setError("Failed to load notifications.");
      } finally {
        setLoading(false);
      }
    };

    loadNotifications();
  }, []);

  const handleMarkAsRead = async (notificationId: string) => {
    try {
      setMarkingId(notificationId);

      const updatedNotification =
        await apiClient.markNotificationAsRead(notificationId);

      setNotifications((currentNotifications) =>
        currentNotifications.map((notification) =>
          notification.id === updatedNotification.id
            ? updatedNotification
            : notification
        )
      );
    } catch (err) {
      console.error("Failed to mark notification as read:", err);
      setError("Failed to mark notification as read.");
    } finally {
      setMarkingId(null);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 px-6 py-10">
      <div className="mx-auto max-w-3xl">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            Notifications
          </h1>

          <p className="mt-2 text-gray-600">
            Membership and payment reminders
          </p>
        </div>

        {loading && (
          <div className="rounded-lg bg-white p-6 shadow">
            <p className="text-gray-600">Loading notifications...</p>
          </div>
        )}

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
            {error}
          </div>
        )}

        {!loading && notifications.length === 0 && (
          <div className="rounded-lg bg-white p-6 shadow">
            <p className="text-gray-600">
              You have no notifications.
            </p>
          </div>
        )}

        <div className="space-y-4">
          {notifications.map((notification) => (
            <div
              key={notification.id}
              className={`rounded-lg border bg-white p-6 shadow-sm ${
                notification.is_read
                  ? "border-gray-200"
                  : "border-blue-300"
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold text-gray-900">
                    {notification.title}
                  </h2>

                  <p className="mt-2 text-gray-700">
                    {notification.message}
                  </p>

                  {notification.created_at && (
                    <p className="mt-3 text-sm text-gray-500">
                      {new Date(
                        notification.created_at
                      ).toLocaleString()}
                    </p>
                  )}
                </div>

                {!notification.is_read && (
                  <span className="rounded-full bg-blue-100 px-3 py-1 text-sm font-medium text-blue-700">
                    New
                  </span>
                )}
              </div>

              {!notification.is_read && (
                <button
                  type="button"
                  onClick={() =>
                    handleMarkAsRead(notification.id)
                  }
                  disabled={markingId === notification.id}
                  className="mt-5 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {markingId === notification.id
                    ? "Marking..."
                    : "Mark as read"}
                </button>
              )}

              {notification.is_read && (
                <p className="mt-5 text-sm font-medium text-green-600">
                  ✓ Read
                </p>
              )}
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}