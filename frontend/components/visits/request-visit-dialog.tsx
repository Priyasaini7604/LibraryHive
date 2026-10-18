"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/choice";
import { FormField } from "@/components/ui/form-field";
import { DateField, Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/overlay";
import { SLOT_LABEL } from "@/components/ui/status-badges";
import { Alert } from "@/components/ui/surface";
import { requestVisit } from "@/lib/api/operations";
import { useAuth } from "@/lib/auth-context";
import { isApiError, userMessage } from "@/lib/errors";
import { addDays, businessDate } from "@/lib/format";
import { loginUrl } from "@/lib/navigation";
import type { VisitSlot } from "@/lib/types";

const SLOT_OPTIONS = (Object.keys(SLOT_LABEL) as VisitSlot[]).map((value) => ({ value, label: SLOT_LABEL[value] }));

function VisitForm({ libraryId, libraryName, onClose }: { libraryId: string; libraryName: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const today = businessDate();
  const [date, setDate] = useState(addDays(today, 1));
  const [slot, setSlot] = useState<VisitSlot>("morning");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => requestVisit({ library_id: libraryId, preferred_date: date, preferred_slot: slot, ...(note.trim() ? { student_note: note.trim() } : {}) }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["student"] });
      toast.success(`Your visit request was sent to ${libraryName}.`);
      onClose();
    },
    onError: (failure) => setError(isApiError(failure, "VISIT_PENDING_EXISTS") ? "You already have a pending visit request here. Cancel it first or wait for the reply." : userMessage(failure)),
  });

  return (
    <form
      noValidate
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (!date || date < today || date > addDays(today, 60)) return setError("Choose a date within the next 60 days.");
        setError(null);
        save.mutate();
      }}
    >
      <FormField label="Preferred date" required hint="Within the next 60 days.">
        <DateField value={date} min={today} max={addDays(today, 60)} onChange={(event) => setDate(event.target.value)} />
      </FormField>
      <FormField label="Time of day" required>
        <Select value={slot} onValueChange={(value) => setSlot(value as VisitSlot)} options={SLOT_OPTIONS} />
      </FormField>
      <FormField label="Note for the library" hint="Optional.">
        <Input value={note} maxLength={500} onChange={(event) => setNote(event.target.value)} />
      </FormField>
      {error && <Alert tone="danger">{error}</Alert>}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
          Cancel
        </Button>
        <Button type="submit" loading={save.isPending}>
          Send request
        </Button>
      </div>
    </form>
  );
}

/** "Request a visit" on the public library page (#77). Anonymous visitors are sent to log in first. */
export function RequestVisitButton({ libraryId, libraryName }: { libraryId: string; libraryName: string }) {
  const { status, user } = useAuth();
  const [open, setOpen] = useState(false);

  if (status === "anonymous") {
    return (
      <Button asChild variant="secondary">
        <Link href={loginUrl(`/libraries/${libraryId}`)}>Log in to request a visit</Link>
      </Button>
    );
  }
  if (status === "loading" || user?.role !== "student") return null;
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="secondary">Request a visit</Button>
      </DialogTrigger>
      <DialogContent title={`Visit ${libraryName}`} description="See the library before you book. The owner will accept or decline.">
        <VisitForm libraryId={libraryId} libraryName={libraryName} onClose={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  );
}
