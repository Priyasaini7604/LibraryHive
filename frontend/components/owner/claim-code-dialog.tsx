"use client";

import { useMutation } from "@tanstack/react-query";
import { Copy } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/overlay";
import { Alert } from "@/components/ui/surface";
import { issueClaimCode } from "@/lib/api/memberships";
import { userMessage } from "@/lib/errors";
import { formatDate } from "@/lib/format";

/**
 * Give a walk-in student a one-time code so they can claim their account (OFF-04, #55). The code is created only
 * when the owner asks, is shown once, and creating a new one cancels the old one. Nothing is kept after closing.
 */
export function ClaimCodeDialog({ studentId, studentName, onClose }: { studentId: string; studentName: string; onClose: () => void }) {
  const [issued, setIssued] = useState<{ code: string; expires_at: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const issue = useMutation({
    mutationFn: () => issueClaimCode(studentId),
    onSuccess: setIssued,
    onError: (failure) => setError(userMessage(failure)),
  });

  async function copy(code: string) {
    try {
      await navigator.clipboard.writeText(code);
      toast.success("Code copied.");
    } catch {
      toast.error("Couldn't copy. Please read the code out instead.");
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={`Claim code for ${studentName}`}
        description="With this code the student can sign up with their own password and keep their seat, payments and attendance."
        footer={
          <Button variant="secondary" onClick={onClose}>
            {issued ? "Done" : "Cancel"}
          </Button>
        }
      >
        {issued ? (
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-300 bg-slate-50 p-4">
              <p aria-label="Claim code" className="font-mono text-2xl font-semibold tracking-widest text-slate-900">
                {issued.code}
              </p>
              <Button variant="secondary" size="sm" onClick={() => void copy(issued.code)}>
                <Copy aria-hidden="true" className="size-4" /> Copy
              </Button>
            </div>
            <Alert tone="warning" title="This is the only time you will see this code">
              It works once and expires on {formatDate(issued.expires_at.slice(0, 10))}. Closing this window hides it for good; you can create a new one, which cancels this one.
            </Alert>
            <p className="text-sm text-slate-700">
              Ask {studentName} to open LibraryHive, choose <strong>Claim your account</strong>, and enter their phone number and this code.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-slate-700">The code is shown once and can&apos;t be looked up later. Creating a new code cancels any earlier one.</p>
            {error && <Alert tone="danger">{error}</Alert>}
            <Button className="self-start" loading={issue.isPending} onClick={() => issue.mutate()}>
              Create a claim code
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
