"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LogIn, LogOut } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ErrorState, Skeleton } from "@/components/ui/states";
import { Alert, Card, CardContent } from "@/components/ui/surface";
import { checkIn, checkOut, fetchCurrentAttendance } from "@/lib/api/operations";
import { fetchStudentMemberships } from "@/lib/api/memberships";
import { userMessage } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";

/**
 * The student's check-in button (UI_ARCHITECTURE.md 5.4, ATT-01/02). One open check-in at a time, anywhere:
 * the button shows check-out while checked in. Check-in is trust-based; the owner sees the live roster.
 */
export function CheckInCard() {
  const queryClient = useQueryClient();
  const current = useQuery({ queryKey: queryKeys.attendanceCurrent, queryFn: fetchCurrentAttendance });
  const memberships = useQuery({ queryKey: queryKeys.studentMemberships(false), queryFn: () => fetchStudentMemberships(false) });

  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.attendanceCurrent }),
      queryClient.invalidateQueries({ queryKey: ["student", "attendance"] }),
      queryClient.invalidateQueries({ queryKey: queryKeys.studentDashboard }),
    ]);

  const checkInMutation = useMutation({
    mutationFn: (libraryId: string) => checkIn(libraryId),
    onSuccess: async () => {
      await refresh();
      toast.success("You're checked in.");
    },
    onError: async (error) => {
      toast.error(userMessage(error));
      await refresh();
    },
  });
  const checkOutMutation = useMutation({
    mutationFn: checkOut,
    onSuccess: async () => {
      await refresh();
      toast.success("You're checked out. See you next time.");
    },
    onError: async (error) => {
      toast.error(userMessage(error));
      await refresh();
    },
  });

  if (current.isPending || memberships.isPending) return <Skeleton className="h-24 w-full" />;
  if (current.isError) return <ErrorState error={current.error} onRetry={() => void current.refetch()} title="We couldn't load your attendance." />;
  if (memberships.isError) return <ErrorState error={memberships.error} onRetry={() => void memberships.refetch()} title="We couldn't load your memberships." />;

  const open = current.data;
  const members = memberships.data.filter((item) => item.status !== "archived");

  return (
    <Card aria-label="Check in">
      <CardContent className="flex flex-col gap-3 pt-4">
        {open ? (
          <>
            <p className="text-slate-900">
              You&apos;re checked in at <strong>{open.library.name}</strong>
              {open.seat_label ? ` (seat ${open.seat_label})` : ""} since {formatDateTime(open.check_in_at)}.
            </p>
            <Button className="self-start" variant="secondary" loading={checkOutMutation.isPending} onClick={() => checkOutMutation.mutate()}>
              <LogOut aria-hidden="true" className="size-4" /> Check out
            </Button>
          </>
        ) : members.length === 0 ? (
          <Alert tone="info">Check-in is available once you have a seat at a library.</Alert>
        ) : (
          <>
            <p className="text-slate-700">Let your library know you&apos;re here.</p>
            <div className="flex flex-wrap gap-2">
              {members.map((item) => (
                <Button
                  key={item.id}
                  loading={checkInMutation.isPending && checkInMutation.variables === item.library.id}
                  disabled={checkInMutation.isPending}
                  onClick={() => checkInMutation.mutate(item.library.id)}
                >
                  <LogIn aria-hidden="true" className="size-4" /> Check in at {item.library.name}
                </Button>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
