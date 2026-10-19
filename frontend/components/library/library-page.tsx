"use client";

import { useQuery } from "@tanstack/react-query";
import { Clock, ExternalLink, Mail, MapPin, Phone } from "lucide-react";
import Link from "next/link";

import { BookingPanel } from "@/components/library/booking-panel";
import { RequestVisitButton } from "@/components/visits/request-visit-dialog";
import { PhotoGallery } from "@/components/library/photo-gallery";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { Badge, Card, CardContent, CardHeader, CardTitle } from "@/components/ui/surface";
import { fetchLibrary } from "@/lib/api/libraries";
import { isApiError } from "@/lib/errors";
import { formatMoney, formatPhone, formatTime } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { LibraryDetail } from "@/lib/types";

function mapLink(library: LibraryDetail): string {
  if (library.latitude !== null && library.longitude !== null) {
    return `https://www.openstreetmap.org/?mlat=${library.latitude}&mlon=${library.longitude}#map=17/${library.latitude}/${library.longitude}`;
  }
  return `https://www.openstreetmap.org/search?query=${encodeURIComponent(`${library.address}, ${library.city}`)}`;
}

function hours(library: LibraryDetail): string {
  const open = formatTime(library.opens_at);
  const close = formatTime(library.closes_at);
  if (open && close) return `${open} – ${close}`;
  return open || close;
}

function LoadingPage() {
  return (
    <div aria-busy="true" className="mx-auto flex max-w-5xl flex-col gap-4 px-4 py-6 sm:px-6">
      <span className="sr-only" role="status">
        Loading library
      </span>
      <Skeleton className="h-64 w-full" />
      <Skeleton className="h-8 w-2/3" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}

/** The public explore page (UI_ARCHITECTURE.md 5.2): gallery, facts, amenities and plans from #15. */
export function LibraryPage({ id }: { id: string }) {
  const query = useQuery({ queryKey: queryKeys.library(id), queryFn: ({ signal }) => fetchLibrary(id, signal) });

  if (query.isPending) return <LoadingPage />;
  if (query.isError) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        {isApiError(query.error, "NOT_FOUND") ? (
          <EmptyState
            title="This library isn't available"
            description="It may not be open for bookings yet, or the link is incorrect."
            action={
              <Button asChild variant="secondary">
                <Link href="/discover">Browse libraries</Link>
              </Button>
            }
          />
        ) : (
          <ErrorState error={query.error} onRetry={() => void query.refetch()} title="We couldn't load this library." />
        )}
      </div>
    );
  }

  const library = query.data;
  const place = [library.area, library.city].filter(Boolean).join(", ");
  const opening = hours(library);
  const counts = library.seat_counts;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-10 px-4 py-8 sm:px-6">
      <PhotoGallery photos={library.photos} libraryName={library.name} />

      <header className="flex flex-col gap-3">
        <h1 className="text-4xl font-extrabold leading-tight tracking-[-0.03em] text-slate-900 sm:text-5xl">{library.name}</h1>
        <p className="flex flex-wrap items-center gap-x-2 text-slate-700">
          <MapPin aria-hidden="true" className="size-4 shrink-0" />
          <span>
            {library.address}
            {place && `, ${place}`}
          </span>
          <a href={mapLink(library)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm font-medium text-blue-700 hover:underline">
            Open in maps <ExternalLink aria-hidden="true" className="size-3.5" />
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
        </p>
        <ul className="flex flex-wrap gap-2 text-sm text-slate-700 [&>li]:rounded-full [&>li]:border [&>li]:border-slate-200 [&>li]:bg-slate-100 [&>li]:px-3.5 [&>li]:py-1.5">
          {opening && (
            <li className="flex items-center gap-1.5">
              <Clock aria-hidden="true" className="size-4" /> {opening}
              {library.operating_notes && <span className="text-slate-600">· {library.operating_notes}</span>}
            </li>
          )}
          {library.contact_phone && (
            <li className="flex items-center gap-1.5">
              <Phone aria-hidden="true" className="size-4" />
              <a href={`tel:${library.contact_phone}`} className="hover:underline">
                {formatPhone(library.contact_phone)}
              </a>
            </li>
          )}
          {library.contact_email && (
            <li className="flex items-center gap-1.5">
              <Mail aria-hidden="true" className="size-4" />
              <a href={`mailto:${library.contact_email}`} className="hover:underline">
                {library.contact_email}
              </a>
            </li>
          )}
        </ul>
        {library.domains.length > 0 && (
          <ul aria-label="Exams" className="flex flex-wrap gap-1.5">
            {library.domains.map((domain) => (
              <li key={domain.code}>
                <Badge tone="brand">{domain.name}</Badge>
              </li>
            ))}
          </ul>
        )}
        {library.description && <p className="max-w-3xl whitespace-pre-line text-slate-700">{library.description}</p>}
        <div>
          <RequestVisitButton libraryId={library.id} libraryName={library.name} />
        </div>
      </header>

      {counts && (
        <section aria-labelledby="seats-heading">
          <h2 id="seats-heading" className="mb-4 text-2xl font-bold text-slate-900">
            Seats
          </h2>
          <div className="rounded-2xl border border-slate-200 bg-white bg-gradient-to-b from-white/[0.035] to-transparent p-5 sm:p-7">
            <BookingPanel libraryId={library.id} plans={library.plans} />
          </div>
        </section>
      )}

      {library.amenities.length > 0 && (
        <section aria-labelledby="amenities-heading">
          <h2 id="amenities-heading" className="mb-4 text-2xl font-bold text-slate-900">
            Amenities
          </h2>
          <ul className="flex flex-wrap gap-2">
            {library.amenities.map((amenity) => (
              <li key={amenity.code}>
                <Badge>{amenity.name}</Badge>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="plans-heading">
        <h2 id="plans-heading" className="mb-4 text-2xl font-bold text-slate-900">
          Plans
        </h2>
        {library.plans.length === 0 ? (
          <EmptyState title="No plans yet" description="This library hasn't published its plans." />
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {library.plans.map((plan) => (
              <li key={plan.id}>
                <Card className="card-glow">
                  <CardHeader>
                    <CardTitle>{plan.name}</CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-1">
                    <p className="text-xl font-semibold text-slate-900">{formatMoney(plan.price)}</p>
                    <p className="text-sm text-slate-700">{plan.duration_days} days</p>
                    {plan.timing_note && <p className="text-sm text-slate-600">{plan.timing_note}</p>}
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
