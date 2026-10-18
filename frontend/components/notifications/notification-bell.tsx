"use client";

import { useQuery } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import Link from "next/link";

import { fetchUnreadCount } from "@/lib/api/operations";
import { queryKeys } from "@/lib/query-keys";

/** The bell in both app shells: a link to the inbox with the unread count, refreshed every minute (NOT-02). */
export function NotificationBell({ href }: { href: string }) {
  const query = useQuery({ queryKey: queryKeys.unreadCount, queryFn: fetchUnreadCount, refetchInterval: 60_000, retry: false });
  const count = query.data ?? 0;
  return (
    <Link
      href={href}
      aria-label={count > 0 ? `Notifications, ${count} unread` : "Notifications"}
      className="relative flex size-10 items-center justify-center rounded-full text-slate-700 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
    >
      <Bell aria-hidden="true" className="size-5" />
      {count > 0 && (
        <span aria-hidden="true" className="absolute right-0.5 top-0.5 flex min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold leading-4 text-white">
          {count > 99 ? "99+" : count}
        </span>
      )}
    </Link>
  );
}
