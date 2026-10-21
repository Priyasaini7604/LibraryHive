"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/choice";
import { Pagination } from "@/components/ui/navigation";
import { LoadingList, Page, PageHeader } from "@/components/ui/page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { cn } from "@/lib/cn";
import { fetchNotifications, markAllNotificationsRead, markNotificationRead } from "@/lib/api/operations";
import { userMessage } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { AppNotification, Role } from "@/lib/types";

/** Where a notification leads, from its entity type and the viewer's role (the deep link of SPEC.md 3.13). */
export function notificationTarget(notification: AppNotification, role: Role): string | null {
  const { entity_type: type, entity_id: id } = notification;
  if (!type || !id) return null;
  if (role === "student") {
    if (type === "membership") return `/student/memberships/${id}`;
    if (type === "payment") return `/student/payments/${id}`;
    if (type === "complaint") return `/student/complaints/${id}`;
    if (type === "visit") return "/student/visits";
    if (type === "library") return `/libraries/${id}`;
    return null;
  }
  if (type === "membership") return `/owner/members/${id}`;
  if (type === "payment") return "/owner/payments";
  if (type === "complaint") return `/owner/complaints/${id}`;
  if (type === "visit") return "/owner/visits";
  if (type === "library") return "/owner/dues";
  return null;
}

/** `/student/notifications` and `/owner/notifications`: the in-app inbox (#58-#61). */
export function NotificationsScreen({ viewer }: { viewer: Role }) {
  const queryClient = useQueryClient();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(1);
  const filters = { unread: unreadOnly, page };
  const query = useQuery({ queryKey: queryKeys.notifications(filters), queryFn: () => fetchNotifications(filters), placeholderData: (previous) => previous });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["notifications"] });
  const markOne = useMutation({ mutationFn: (id: string) => markNotificationRead(id), onSuccess: refresh, onError: (error) => toast.error(userMessage(error)) });
  const markAll = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: async (result) => {
      await refresh();
      toast.success(result.updated === 0 ? "Everything was already read." : `${result.updated} marked as read.`);
    },
    onError: (error) => toast.error(userMessage(error)),
  });

  return (
    <Page>
      <PageHeader
        title="Notifications"
        description="Reminders and updates from your library and from LibraryHive."
        actions={
          <Button variant="secondary" loading={markAll.isPending} onClick={() => markAll.mutate()}>
            <CheckCheck aria-hidden="true" className="size-4" /> Mark all as read
          </Button>
        }
      />
      <Checkbox label="Show unread only" checked={unreadOnly} onCheckedChange={(value) => { setUnreadOnly(value === true); setPage(1); }} />

      {query.isPending ? (
        <LoadingList label="Loading notifications" />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load your notifications." />
      ) : query.data.items.length === 0 ? (
        <EmptyState title={unreadOnly ? "Nothing unread" : "No notifications yet"} description="Reminders and updates will appear here." />
      ) : (
        <>
          <ul className="flex flex-col gap-2">
            {query.data.items.map((notification) => {
              const unread = notification.read_at === null;
              const target = notificationTarget(notification, viewer);
              return (
                <li key={notification.id} className={cn("flex flex-wrap items-start justify-between gap-3 rounded-xl border p-4", unread ? "border-blue-200 bg-blue-50" : "border-slate-200 bg-white")}>
                  <div className="flex flex-col gap-1">
                    <p className="font-medium text-slate-900">
                      {unread && <span className="sr-only">Unread: </span>}
                      {notification.title}
                    </p>
                    <p className="text-sm text-slate-700">{notification.body}</p>
                    <p className="text-xs text-slate-600">{formatDateTime(notification.created_at)}</p>
                  </div>
                  <div className="flex gap-2">
                    {target && (
                      <Button asChild size="sm" variant="secondary">
                        <Link href={target} onClick={() => unread && markOne.mutate(notification.id)}>
                          Open
                        </Link>
                      </Button>
                    )}
                    {unread && (
                      <Button size="sm" variant="ghost" aria-label={`Mark "${notification.title}" as read`} loading={markOne.isPending && markOne.variables === notification.id} onClick={() => markOne.mutate(notification.id)}>
                        Mark read
                      </Button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
          <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPageChange={setPage} />
        </>
      )}
    </Page>
  );
}
