import { CheckCircle2, Circle } from "lucide-react";
import Link from "next/link";

import { Alert } from "@/components/ui/surface";
import type { OwnerLibrary } from "@/lib/types";

const ITEMS = [
  { key: "has_profile", label: "Library profile (name and address)" },
  { key: "has_location", label: "Location (latitude and longitude)" },
  { key: "has_active_plan", label: "At least one active plan" },
  { key: "has_active_seat", label: "At least one active seat" },
] as const;

/**
 * What still stands between the library and going live (LIB-07). Publishing is automatic
 * (decision D12): there is no submit button, the server publishes as soon as every item is met.
 */
export function PublishChecklist({ library }: { library: OwnerLibrary }) {
  const { publish_checklist: checklist } = library;
  return (
    <section aria-labelledby="checklist-heading" className="flex flex-col gap-3">
      <h2 id="checklist-heading" className="text-lg font-semibold text-slate-900">
        Go-live checklist
      </h2>
      {library.is_published ? (
        <Alert tone="success" title="Your library is live">
          Students can find it and see its plans.{" "}
          <Link href={`/libraries/${library.id}`} className="font-medium underline">
            View the public page
          </Link>
        </Alert>
      ) : (
        <Alert tone="info" title="Not live yet">
          Your library goes live automatically once every item below is done.
        </Alert>
      )}
      <ul className="flex flex-col gap-2">
        {ITEMS.map(({ key, label }) => {
          const done = checklist[key];
          return (
            <li key={key} className="flex items-center gap-2 text-sm text-slate-800">
              {done ? (
                <CheckCircle2 aria-hidden="true" className="size-5 text-green-600" />
              ) : (
                <Circle aria-hidden="true" className="size-5 text-slate-400" />
              )}
              <span>
                {label}
                <span className="sr-only">{done ? ": done" : ": not done yet"}</span>
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
