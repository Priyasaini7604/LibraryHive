"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Textarea } from "@/components/ui/input";
import { Dialog, DialogContent } from "@/components/ui/overlay";
import { Alert } from "@/components/ui/surface";

/**
 * Asks for a short reason before an owner action that changes what others see (UI_ARCHITECTURE.md 10.4).
 * The reason goes to the audit trail; the confirm button is on the right and shows progress.
 */
export function ReasonDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  onSubmit,
  loading,
  error,
  minLength = 3,
  maxLength = 200,
  destructive = false,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  onSubmit: (reason: string) => void;
  loading?: boolean;
  error?: string | null;
  minLength?: number;
  maxLength?: number;
  destructive?: boolean;
}) {
  const [reason, setReason] = useState("");
  const [touched, setTouched] = useState(false);
  const trimmed = reason.trim();
  const invalid = trimmed.length < minLength;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={title} description={description}>
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            setTouched(true);
            if (!invalid) onSubmit(trimmed);
          }}
        >
          <FormField
            label="Reason"
            required
            hint={`${minLength}–${maxLength} characters. It is saved in the activity log.`}
            error={touched && invalid ? `Enter at least ${minLength} characters.` : undefined}
          >
            <Textarea value={reason} maxLength={maxLength} rows={3} onChange={(event) => setReason(event.target.value)} />
          </FormField>
          {error && <Alert tone="danger">{error}</Alert>}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={loading}>
              Cancel
            </Button>
            <Button type="submit" variant={destructive ? "danger" : "primary"} loading={loading}>
              {confirmLabel}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
