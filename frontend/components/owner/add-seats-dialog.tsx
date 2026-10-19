"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent } from "@/components/ui/overlay";
import { Tabs, TabsContent, TabsList } from "@/components/ui/navigation";
import { Alert } from "@/components/ui/surface";
import { addSeats, type AddSeatsInput } from "@/lib/api/seats";
import { userMessage } from "@/lib/errors";
import { queryKeys } from "@/lib/query-keys";

const MAX_SEATS = 500;

function parseList(text: string): string[] {
  return text
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

/** Add seats as a grid (rows × seats per row) or as an explicit list of labels (#31). Existing labels are skipped. */
export function AddSeatsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"grid" | "list">("grid");
  const [rows, setRows] = useState("A, B, C");
  const [perRow, setPerRow] = useState("10");
  const [labels, setLabels] = useState("");
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (input: AddSeatsInput) => addSeats(input),
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.ownerSeats }),
        queryClient.invalidateQueries({ queryKey: queryKeys.ownerLibrary, exact: true }),
      ]);
      const skipped = result.skipped.length;
      toast.success(`${result.created.length} seat${result.created.length === 1 ? "" : "s"} added${skipped ? `, ${skipped} already existed` : ""}.`);
      onOpenChange(false);
    },
    onError: (failure) => setError(userMessage(failure)),
  });

  function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (mode === "grid") {
      const rowNames = parseList(rows);
      const count = Number(perRow);
      if (rowNames.length === 0) return setError("Enter at least one row name, for example A, B, C.");
      if (!Number.isInteger(count) || count < 1 || count > 50) return setError("Seats per row must be between 1 and 50.");
      if (rowNames.length * count > MAX_SEATS) return setError(`Add at most ${MAX_SEATS} seats at a time.`);
      save.mutate({ mode: "grid", rows: rowNames, seats_per_row: count });
    } else {
      const items = parseList(labels);
      if (items.length === 0) return setError("Enter at least one seat label.");
      if (items.length > MAX_SEATS) return setError(`Add at most ${MAX_SEATS} seats at a time.`);
      save.mutate({ mode: "list", seats: items.map((label) => ({ label })) });
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Add seats" description="Seats you add are free immediately. Labels that already exist are skipped, never changed.">
        <form onSubmit={submit} noValidate className="flex flex-col gap-4">
          <Tabs value={mode} onValueChange={(value) => setMode(value as "grid" | "list")}>
            <TabsList label="How to add seats" items={[{ value: "grid", label: "Grid" }, { value: "list", label: "List" }]} />
            <TabsContent value="grid" className="flex flex-col gap-4 pt-4">
              <FormField label="Rows" hint="Separate row names with commas, for example A, B, C. Seats are labelled A-1, A-2 …">
                <Input value={rows} onChange={(event) => setRows(event.target.value)} />
              </FormField>
              <FormField label="Seats per row">
                <Input inputMode="numeric" value={perRow} onChange={(event) => setPerRow(event.target.value)} />
              </FormField>
            </TabsContent>
            <TabsContent value="list" className="pt-4">
              <FormField label="Seat labels" hint="One per line or separated by commas.">
                <textarea
                  value={labels}
                  onChange={(event) => setLabels(event.target.value)}
                  rows={5}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-base focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/30"
                />
              </FormField>
            </TabsContent>
          </Tabs>
          {error && <Alert tone="danger">{error}</Alert>}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={save.isPending}>
              Cancel
            </Button>
            <Button type="submit" loading={save.isPending}>
              Add seats
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
