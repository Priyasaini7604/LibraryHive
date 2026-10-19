import { ArrowUpRight, MapPin } from "lucide-react";
import Link from "next/link";

import { Badge, ProgressBar } from "@/components/ui/surface";
import { mediaUrl } from "@/lib/api/libraries";
import { cn } from "@/lib/cn";
import { formatMoney } from "@/lib/format";
import type { LibrarySummary, SeatCounts } from "@/lib/types";

const MAX_AMENITIES = 3;
const MAX_DOMAINS = 2;

/** How full the library is, as a plain-language pill (the number is always shown; colour is only a hint). */
function availability(counts: SeatCounts): { label: string; dot: string } {
  if (counts.total === 0) return { label: "No seats listed", dot: "bg-slate-400" };
  if (counts.empty === 0) return { label: "Full", dot: "bg-red-500" };
  const share = counts.empty / counts.total;
  if (share <= 0.15) return { label: `${counts.empty} free`, dot: "bg-amber-400" };
  return { label: `${counts.empty} free`, dot: "bg-emerald-500" };
}

/** The picture of a library, or a branded tile with its initial when it has no photo. */
function Cover({ library }: { library: LibrarySummary }) {
  return (
    <div className="relative aspect-[16/10] overflow-hidden bg-slate-100">
      {library.cover ? (
        // eslint-disable-next-line @next/next/no-img-element -- photos come from the object store, already resized
        <img
          src={mediaUrl(library.cover.thumb_url)}
          alt=""
          width={640}
          height={400}
          loading="lazy"
          className="size-full object-cover transition-transform duration-500 group-hover:scale-105 motion-reduce:transition-none motion-reduce:group-hover:scale-100"
        />
      ) : (
        <span
          aria-hidden="true"
          className="flex size-full items-center justify-center bg-gradient-to-br from-blue-100 via-slate-100 to-slate-50 font-display text-5xl font-bold text-blue-400"
        >
          {library.name.charAt(0).toUpperCase()}
        </span>
      )}
      <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/10 to-transparent" />
    </div>
  );
}

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
  const status = counts ? availability(counts) : null;

  return (
    <article className="card-glow group relative flex h-full flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="relative">
        <Cover library={library} />
        {status && (
          <span className="absolute right-3 top-3 inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-black/55 px-2.5 py-1 text-xs font-medium text-white backdrop-blur">
            <span aria-hidden="true" className={cn("size-2 rounded-full", status.dot)} />
            {status.label}
          </span>
        )}
        {library.starting_price !== null && (
          <p className="absolute bottom-3 left-3 rounded-lg bg-black/55 px-2.5 py-1 text-sm font-semibold text-white backdrop-blur">
            From {formatMoney(library.starting_price)}
          </p>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4 sm:p-5">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-lg font-semibold leading-snug text-slate-900">
            <Link href={`/libraries/${library.id}`} className="after:absolute after:inset-0 focus-visible:outline-none">
              {library.name}
            </Link>
          </h2>
          <ArrowUpRight
            aria-hidden="true"
            className="mt-1 size-5 shrink-0 text-slate-500 transition-colors group-hover:text-blue-400"
          />
        </div>

        <p className="flex items-center gap-1.5 text-sm text-slate-600">
          <MapPin aria-hidden="true" className="size-4 shrink-0" />
          <span className="truncate">{place}</span>
          {library.distance_km !== undefined && <span className="shrink-0">· {library.distance_km} km</span>}
        </p>

        {counts && (
          <div className="flex flex-col gap-1.5">
            <p className="text-sm text-slate-700">
              {counts.empty} of {counts.total} seats free
            </p>
            <ProgressBar value={counts.total - counts.empty} max={counts.total} label="Seats taken" />
          </div>
        )}

        <ul className="mt-auto flex flex-wrap gap-1.5 pt-1" aria-label="Amenities and exams">
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
    </article>
  );
}
