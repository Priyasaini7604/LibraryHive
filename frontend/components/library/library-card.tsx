import { Building2, MapPin } from "lucide-react";
import Link from "next/link";

import { Badge, Card, ProgressBar } from "@/components/ui/surface";
import { mediaUrl } from "@/lib/api/libraries";
import { formatMoney } from "@/lib/format";
import type { LibrarySummary } from "@/lib/types";

const MAX_AMENITIES = 3;
const MAX_DOMAINS = 2;

/** One library of the discovery list (UI_ARCHITECTURE.md 5.1). Everything shown comes from the API. */
export function LibraryCard({
  library,
  names,
}: {
  library: LibrarySummary;
  /** code -> display name for amenities and domains (from #2 and #3). */
  names: Record<string, string>;
}) {
  const place = [library.area, library.city].filter(Boolean).join(", ");
  const counts = library.seat_counts;
  return (
    <Card className="overflow-hidden transition-shadow focus-within:ring-2 focus-within:ring-blue-600 hover:shadow-md">
      <div className="flex gap-4 p-3 sm:p-4">
        {library.cover ? (
          // eslint-disable-next-line @next/next/no-img-element -- photos come from the object store, already resized
          <img
            src={mediaUrl(library.cover.thumb_url)}
            alt=""
            width={112}
            height={112}
            loading="lazy"
            className="size-24 shrink-0 rounded-lg object-cover sm:size-28"
          />
        ) : (
          <span
            aria-hidden="true"
            className="flex size-24 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-400 sm:size-28"
          >
            <Building2 className="size-8" />
          </span>
        )}
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <h2 className="truncate text-base font-semibold text-slate-900">
            <Link
              href={`/libraries/${library.id}`}
              className="after:absolute after:inset-0 focus-visible:outline-none"
            >
              {library.name}
            </Link>
          </h2>
          <p className="flex items-center gap-1 text-sm text-slate-600">
            <MapPin aria-hidden="true" className="size-4 shrink-0" />
            <span className="truncate">{place}</span>
            {library.distance_km !== undefined && <span className="shrink-0">· {library.distance_km} km</span>}
          </p>
          {library.starting_price !== null && (
            <p className="text-sm font-medium text-slate-900">From {formatMoney(library.starting_price)}</p>
          )}
          {counts && (
            <div className="flex flex-col gap-1">
              <p className="text-sm text-slate-700">
                {counts.empty} of {counts.total} seats free
              </p>
              <ProgressBar value={counts.total - counts.empty} max={counts.total} label="Seats taken" />
            </div>
          )}
          <ul className="flex flex-wrap gap-1.5" aria-label="Amenities and exams">
            {library.amenities.slice(0, MAX_AMENITIES).map((code) => (
              <li key={`a-${code}`}>
                <Badge>{names[code] ?? code}</Badge>
              </li>
            ))}
            {library.domains.slice(0, MAX_DOMAINS).map((code) => (
              <li key={`d-${code}`}>
                <Badge tone="brand">{names[code] ?? code}</Badge>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Card>
  );
}
