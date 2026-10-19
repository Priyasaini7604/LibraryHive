"use client";

import { Download } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { downloadExport, type ExportKind } from "@/lib/api/operations";
import { userMessage } from "@/lib/errors";
import { saveBlob } from "@/lib/files";

/** Download a CSV of the library's own data through the authenticated client (#87). */
export function ExportButton({
  kind,
  query,
  label = "Export CSV",
}: {
  kind: ExportKind;
  query?: { from?: string; to?: string; status?: string };
  label?: string;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <Button
      variant="secondary"
      loading={busy}
      onClick={async () => {
        setBusy(true);
        try {
          const { blob, filename } = await downloadExport(kind, query);
          saveBlob(blob, filename);
        } catch (error) {
          toast.error(userMessage(error));
        } finally {
          setBusy(false);
        }
      }}
    >
      <Download aria-hidden="true" className="size-4" /> {label}
    </Button>
  );
}
