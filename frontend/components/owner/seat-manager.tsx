"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AddSeatsDialog } from "@/components/owner/add-seats-dialog";
import { SeatLegend, SeatMap, STATUS_TEXT, type MapSeat } from "@/components/seat-map/seat-map";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent } from "@/components/ui/overlay";
import { Page, PageHeader } from "@/components/ui/page";
import { ReasonDialog } from "@/components/ui/reason-dialog";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { Alert, Badge, Card, CardContent, CardHeader, CardTitle } from "@/components/ui/surface";
import {
  deactivateSeat,
  disableSeat,
  enableSeat,
  fetchOwnerSeats,
  placeManualHold,
  releaseHold,
  updateSeat,
} from "@/lib/api/seats";
import { userMessage } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { OwnerSeat } from "@/lib/types";

type Action = "block" | "release" | "disable" | "remove" | "edit";

function EditSeatDialog({ seat, onClose }: { seat: OwnerSeat; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [label, setLabel] = useState(seat.label);
  const [row, setRow] = useState(seat.row_label);
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => updateSeat(seat.id, { label: label.trim(), row_label: row.trim() }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.ownerSeats });
      toast.success("Seat updated.");
      onClose();
    },
    onError: (failure) => setError(userMessage(failure)),
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent title={`Rename seat ${seat.label}`} description="Members keep their seat; only its name and row change.">
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (!label.trim()) return setError("Enter a label.");
            setError(null);
            save.mutate();
          }}
        >
          <FormField label="Label" required>
            <Input value={label} maxLength={50} onChange={(event) => setLabel(event.target.value)} />
          </FormField>
          <FormField label="Row" hint="Optional, for example A.">
            <Input value={row} maxLength={10} onChange={(event) => setRow(event.target.value)} />
          </FormField>
          {error && <Alert tone="danger">{error}</Alert>}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
              Cancel
            </Button>
            <Button type="submit" loading={save.isPending}>
              Save
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** Side panel for the chosen seat: what is there and the actions that apply to its status (SEAT-07). */
function SeatPanel({ seat }: { seat: OwnerSeat }) {
  const queryClient = useQueryClient();
  const [action, setAction] = useState<Action | null>(null);
  const [error, setError] = useState<string | null>(null);
  const status = seat.status ?? "disabled";

  const refresh = async (message: string) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.ownerSeats }),
      queryClient.invalidateQueries({ queryKey: queryKeys.ownerLibrary, exact: true }),
      queryClient.invalidateQueries({ queryKey: queryKeys.ownerDashboard }),
    ]);
    toast.success(message);
    setAction(null);
    setError(null);
  };
  const failed = (failure: unknown) => setError(userMessage(failure));

  const block = useMutation({ mutationFn: (reason: string) => placeManualHold(seat.id, reason), onSuccess: () => refresh("Seat blocked."), onError: failed });
  const release = useMutation({
    mutationFn: (reason: string) => releaseHold((seat.hold as NonNullable<OwnerSeat["hold"]>).id, reason),
    onSuccess: () => refresh("Hold released. The seat is free."),
    onError: failed,
  });
  const disable = useMutation({ mutationFn: (reason: string) => disableSeat(seat.id, reason), onSuccess: () => refresh("Seat is under maintenance."), onError: failed });
  const remove = useMutation({ mutationFn: (reason: string) => deactivateSeat(seat.id, reason), onSuccess: () => refresh("Seat removed."), onError: failed });
  const enable = useMutation({ mutationFn: () => enableSeat(seat.id), onSuccess: () => refresh("Seat is available again."), onError: (failure) => toast.error(userMessage(failure)) });

  const close = () => {
    setAction(null);
    setError(null);
  };

  return (
    <Card aria-label={`Seat ${seat.label}`}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Seat {seat.label}
          <Badge tone={status === "empty" ? "success" : status === "occupied" ? "neutral" : "warning"}>{STATUS_TEXT[status]}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {seat.occupant && (
          <p className="text-sm text-slate-700">
            Taken by{" "}
            <Link href={`/owner/members/${seat.occupant.membership_id}`} className="font-medium text-blue-700 hover:underline">
              {seat.occupant.student_name}
            </Link>
          </p>
        )}
        {seat.hold?.kind === "booking" && (
          <p className="text-sm text-slate-700">
            {seat.hold.student_name} is paying for this seat
            {seat.hold.expires_at && `. The hold ends ${formatDateTime(seat.hold.expires_at)}.`}
          </p>
        )}
        {seat.hold?.kind === "owner_manual" && <p className="text-sm text-slate-700">Blocked by you: {seat.hold.reason}</p>}
        {seat.is_disabled && seat.disabled_reason && <p className="text-sm text-slate-700">Maintenance note: {seat.disabled_reason}</p>}

        <div className="flex flex-wrap gap-2">
          {status === "empty" && (
            <>
              <Button asChild size="sm">
                <Link href={`/owner/members/new?seat=${seat.id}`}>Admit a student</Link>
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setAction("block")}>
                Block seat
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setAction("disable")}>
                Mark under maintenance
              </Button>
            </>
          )}
          {status === "reserved" && seat.hold && (
            <Button size="sm" variant="secondary" onClick={() => setAction("release")}>
              Release hold
            </Button>
          )}
          {status === "disabled" && (
            <Button size="sm" variant="secondary" loading={enable.isPending} onClick={() => enable.mutate()}>
              End maintenance
            </Button>
          )}
          <Button size="sm" variant="secondary" onClick={() => setAction("edit")}>
            Rename
          </Button>
          {status !== "occupied" && status !== "reserved" && (
            <Button size="sm" variant="danger" onClick={() => setAction("remove")}>
              Remove seat
            </Button>
          )}
        </div>
        {status === "occupied" && (
          <p className="text-xs text-slate-600">To free this seat, archive the member from the Members page.</p>
        )}
      </CardContent>

      <ReasonDialog
        open={action === "block"}
        onOpenChange={(open) => !open && close()}
        title={`Block seat ${seat.label}`}
        description="Students can't book a blocked seat. Use this for a reservation made offline. It stays blocked until you release it or admit a student there."
        confirmLabel="Block seat"
        onSubmit={(reason) => block.mutate(reason)}
        loading={block.isPending}
        error={error}
      />
      <ReasonDialog
        open={action === "release"}
        onOpenChange={(open) => !open && close()}
        title={`Release the hold on seat ${seat.label}`}
        description="The seat becomes free at once. A student who is still paying for it will be told it is no longer available."
        confirmLabel="Release hold"
        onSubmit={(reason) => release.mutate(reason)}
        loading={release.isPending}
        error={error}
      />
      <ReasonDialog
        open={action === "disable"}
        onOpenChange={(open) => !open && close()}
        title={`Mark seat ${seat.label} under maintenance`}
        description="Students can't book it until you end the maintenance."
        confirmLabel="Mark under maintenance"
        onSubmit={(reason) => disable.mutate(reason)}
        loading={disable.isPending}
        error={error}
      />
      <ReasonDialog
        open={action === "remove"}
        onOpenChange={(open) => !open && close()}
        title={`Remove seat ${seat.label}`}
        description="The seat disappears from the map. Past members and payments keep their history."
        confirmLabel="Remove seat"
        destructive
        onSubmit={(reason) => remove.mutate(reason)}
        loading={remove.isPending}
        error={error}
      />
      {action === "edit" && <EditSeatDialog seat={seat} onClose={close} />}
    </Card>
  );
}

/** The owner's seat manager (UI_ARCHITECTURE.md 6, T17): live map, per-seat actions and adding seats. */
export function SeatManager() {
  const [adding, setAdding] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const seats = useQuery({ queryKey: queryKeys.ownerSeats, queryFn: () => fetchOwnerSeats(), refetchInterval: 30_000 });

  const selected = seats.data?.seats.find((seat) => seat.id === selectedId) ?? null;

  return (
    <Page>
      <PageHeader
        title="Seats"
        description="Everything students see on your library page comes from this map. Select a seat to manage it."
        actions={
          <Button onClick={() => setAdding(true)}>
            <Plus aria-hidden="true" className="size-4" /> Add seats
          </Button>
        }
      />

      {seats.isPending ? (
        <div aria-busy="true" className="flex flex-col gap-3">
          <span className="sr-only" role="status">
            Loading seats
          </span>
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-3/4" />
        </div>
      ) : seats.isError ? (
        <ErrorState error={seats.error} onRetry={() => void seats.refetch()} title="We couldn't load your seats." />
      ) : seats.data.seats.length === 0 ? (
        <EmptyState
          title="You haven't added any seats"
          description="Add your seats to open bookings. You can add a whole grid at once and rename seats later."
          action={<Button onClick={() => setAdding(true)}>Add seats</Button>}
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
          <section aria-label="Seat map" className="flex flex-col gap-4">
            <p className="text-slate-700">
              {seats.data.counts.empty} free · {seats.data.counts.reserved} reserved · {seats.data.counts.occupied} taken ·{" "}
              {seats.data.counts.total} in total
            </p>
            <SeatLegend />
            <SeatMap
              label="Your seats. Select a seat to manage it."
              seats={seats.data.seats as MapSeat[]}
              selectedId={selectedId}
              onSelect={(seat) => setSelectedId(seat.id)}
              isSelectable={() => true}
            />
          </section>
          <aside aria-label="Seat details">
            {selected ? (
              <SeatPanel key={selected.id} seat={selected} />
            ) : (
              <EmptyState title="No seat selected" description="Select a seat on the map to see who is there and what you can do." />
            )}
          </aside>
        </div>
      )}

      {adding && <AddSeatsDialog open onOpenChange={setAdding} />}
    </Page>
  );
}
