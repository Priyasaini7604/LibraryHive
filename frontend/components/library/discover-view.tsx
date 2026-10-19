"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { LocateFixed, Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/choice";
import { Input } from "@/components/ui/input";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { Alert } from "@/components/ui/surface";
import { fetchAmenities, fetchDomains, fetchLibraries } from "@/lib/api/libraries";
import { cn } from "@/lib/cn";
import { queryKeys } from "@/lib/query-keys";
import type { LibraryFilters, LibrarySort, Vocabulary } from "@/lib/types";

import { LibraryCard } from "./library-card";

const PAGE_SIZE = 12;
const SEARCH_DEBOUNCE_MS = 300;
const SORTS: LibrarySort[] = ["distance", "price"];

/** Filters live in the URL so a search is shareable and the back button works (UI_ARCHITECTURE.md 5.1). */
function readFilters(params: URLSearchParams): LibraryFilters {
  const number = (key: string) => {
    const raw = params.get(key);
    const value = raw === null || raw === "" ? Number.NaN : Number(raw);
    return Number.isFinite(value) ? value : undefined;
  };
  const sort = params.get("sort");
  return {
    search: params.get("search") || undefined,
    domain: params.get("domain") || undefined,
    amenity: params.getAll("amenity"),
    lat: number("lat"),
    lng: number("lng"),
    radius_km: number("radius_km"),
    sort: SORTS.includes(sort as LibrarySort) ? (sort as LibrarySort) : undefined,
  };
}

function toParams(filters: LibraryFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.domain) params.set("domain", filters.domain);
  filters.amenity?.forEach((code) => params.append("amenity", code));
  if (filters.lat !== undefined && filters.lng !== undefined) {
    params.set("lat", String(filters.lat));
    params.set("lng", String(filters.lng));
  }
  if (filters.radius_km !== undefined) params.set("radius_km", String(filters.radius_km));
  if (filters.sort) params.set("sort", filters.sort);
  return params;
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "h-9 rounded-full border px-3.5 text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 motion-reduce:transition-none",
        active
          ? "border-transparent bg-blue-600 text-white shadow-[0_6px_20px_-6px_rgb(99_102_241/0.7)]"
          : "border-slate-300 bg-slate-100/40 text-slate-700 hover:border-blue-400/60 hover:bg-blue-50 hover:text-slate-900",
      )}
    >
      {children}
    </button>
  );
}

function FilterGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap items-center gap-2">
      <span aria-hidden="true" className="w-full text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 sm:w-24">
        {label}
      </span>
      {children}
    </div>
  );
}

export function DiscoverView() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const filters = useMemo(() => readFilters(new URLSearchParams(searchParams.toString())), [searchParams]);
  const [searchText, setSearchText] = useState(filters.search ?? "");
  const [locationMessage, setLocationMessage] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);

  const update = (next: LibraryFilters) => {
    const query = toParams(next).toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  };

  // Debounced search: the URL changes 300 ms after typing stops.
  useEffect(() => {
    if ((filters.search ?? "") === searchText.trim()) return;
    const timer = setTimeout(() => update({ ...filters, search: searchText.trim() || undefined }), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `update` only closes over router and pathname
  }, [searchText, filters]);

  const domains = useQuery({ queryKey: queryKeys.domains, queryFn: fetchDomains, staleTime: 60 * 60 * 1000 });
  const amenities = useQuery({ queryKey: queryKeys.amenities, queryFn: fetchAmenities, staleTime: 60 * 60 * 1000 });
  const names = useMemo(() => {
    const map: Record<string, string> = {};
    for (const item of [...(domains.data ?? []), ...(amenities.data ?? [])] as Vocabulary[]) map[item.code] = item.name;
    return map;
  }, [domains.data, amenities.data]);

  const list = useInfiniteQuery({
    queryKey: queryKeys.libraries(filters),
    queryFn: ({ pageParam, signal }) => fetchLibraries({ ...filters, page: pageParam, page_size: PAGE_SIZE }, signal),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.page * last.page_size < last.total ? last.page + 1 : undefined),
  });

  const hasLocation = filters.lat !== undefined && filters.lng !== undefined;
  const items = list.data?.pages.flatMap((page) => page.items) ?? [];
  const hasFilters = Boolean(filters.search || filters.domain || filters.amenity?.length || hasLocation);

  const useMyLocation = () => {
    if (!("geolocation" in navigator)) {
      setLocationMessage("Your browser can't share its location. Search by area name instead.");
      return;
    }
    setLocating(true);
    setLocationMessage(null);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocating(false);
        update({ ...filters, lat: position.coords.latitude, lng: position.coords.longitude, sort: "distance" });
      },
      () => {
        setLocating(false);
        setLocationMessage(
          "We couldn't get your location. Allow location access in your browser settings, or search by area name instead.",
        );
      },
      { timeout: 10_000 },
    );
  };

  const toggleAmenity = (code: string) => {
    const current = filters.amenity ?? [];
    update({ ...filters, amenity: current.includes(code) ? current.filter((c) => c !== code) : [...current, code] });
  };

  const clearFilters = () => {
    setSearchText("");
    update({});
  };

  return (
    <div className="flex flex-col">
      <section className="relative isolate overflow-hidden border-b border-white/5">
        <div aria-hidden="true" className="pointer-events-none absolute -left-24 -top-32 -z-10 size-[26rem] rounded-full bg-indigo-500/20 blur-3xl" />
        <div aria-hidden="true" className="pointer-events-none absolute -right-20 top-10 -z-10 size-[22rem] rounded-full bg-violet-500/15 blur-3xl" />
        <div className="mx-auto flex max-w-7xl flex-col gap-8 px-4 pb-12 pt-12 sm:px-6 sm:pb-16 sm:pt-20">
          <header className="flex max-w-3xl flex-col gap-5">
            <p className="inline-flex w-fit items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
              <span aria-hidden="true" className="size-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_2px_rgb(52_211_153/0.6)]" />
              Live seat availability
            </p>
            <h1 className="text-4xl font-extrabold leading-[1.06] tracking-[-0.03em] text-slate-900 sm:text-6xl">
              Find a study library
              <span className="gradient-text block">that fits how you work.</span>
            </h1>
            <p className="max-w-xl text-lg text-slate-600">Search by name or area, compare plans and seats, then book the one that suits you.</p>
          </header>

          <form
            role="search"
            aria-label="Search libraries"
            className="glass flex flex-col gap-3 rounded-2xl border border-white/10 p-3 shadow-[0_24px_60px_-30px_rgb(0_0_0/0.8)] sm:flex-row sm:items-center"
            onSubmit={(event) => {
              event.preventDefault();
              update({ ...filters, search: searchText.trim() || undefined });
            }}
          >
            <div className="relative flex-1">
              <Search aria-hidden="true" className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-slate-500" />
              <Input
                type="search"
                aria-label="Search area or library"
                placeholder="Search area or library…"
                value={searchText}
                onChange={(event) => setSearchText(event.target.value)}
                className="h-12 border-transparent bg-slate-50/70 pl-11 text-base"
              />
            </div>
            <Button variant="secondary" size="lg" onClick={useMyLocation} loading={locating}>
              <LocateFixed aria-hidden="true" className="size-4" /> Use my location
            </Button>
            <div className="sm:w-52">
              <label htmlFor="sort-libraries" className="sr-only">
                Sort libraries
              </label>
              <Select
                id="sort-libraries"
                value={filters.sort ?? "default"}
                onValueChange={(value) => update({ ...filters, sort: value === "default" ? undefined : (value as LibrarySort) })}
                options={[
                  { value: "default", label: hasLocation ? "Sort: Nearest" : "Sort: Name" },
                  { value: "distance", label: "Nearest first", disabled: !hasLocation },
                  { value: "price", label: "Lowest price" },
                ]}
              />
            </div>
          </form>

          {locationMessage && <Alert tone="warning">{locationMessage}</Alert>}

          <section aria-label="Filters" className="flex flex-col gap-3">
            {(domains.data?.length ?? 0) > 0 && (
              <FilterGroup label="Exam">
                {domains.data?.map((domain) => (
                  <Chip
                    key={domain.code}
                    active={filters.domain === domain.code}
                    onClick={() => update({ ...filters, domain: filters.domain === domain.code ? undefined : domain.code })}
                  >
                    {domain.name}
                  </Chip>
                ))}
              </FilterGroup>
            )}
            {(amenities.data?.length ?? 0) > 0 && (
              <FilterGroup label="Amenities">
                {amenities.data?.map((amenity) => (
                  <Chip key={amenity.code} active={filters.amenity?.includes(amenity.code) ?? false} onClick={() => toggleAmenity(amenity.code)}>
                    {amenity.name}
                  </Chip>
                ))}
              </FilterGroup>
            )}
          </section>
        </div>
      </section>

      <section aria-label="Libraries" aria-live="polite" className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-10 sm:px-6">
        {list.isPending ? (
          <div aria-busy="true" className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <span className="sr-only" role="status">
              Loading libraries
            </span>
            {Array.from({ length: 6 }, (_, i) => (
              <div key={i} className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                <Skeleton className="aspect-[16/10] w-full rounded-none" />
                <div className="flex flex-col gap-3 p-5">
                  <Skeleton className="h-5 w-2/3" />
                  <Skeleton className="h-4 w-1/2" />
                  <Skeleton className="h-2 w-full" />
                </div>
              </div>
            ))}
          </div>
        ) : list.isError ? (
          <ErrorState error={list.error} onRetry={() => void list.refetch()} title="We couldn't load libraries." />
        ) : items.length === 0 ? (
          <EmptyState
            title="No libraries found here yet"
            description="Try a larger area, another search or fewer filters."
            action={
              hasFilters ? (
                <Button variant="secondary" onClick={clearFilters}>
                  Clear filters
                </Button>
              ) : undefined
            }
          />
        ) : (
          <>
            <div className="flex items-baseline justify-between gap-3">
              <p className="text-sm text-slate-600">
                {list.data?.pages[0]?.total} {list.data?.pages[0]?.total === 1 ? "library" : "libraries"}
              </p>
              {hasFilters && (
                <button
                  type="button"
                  onClick={clearFilters}
                  className="rounded text-sm font-medium text-blue-700 underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                >
                  Reset filters
                </button>
              )}
            </div>
            <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((library) => (
                <li key={library.id} className="relative">
                  <LibraryCard library={library} names={names} />
                </li>
              ))}
            </ul>
            {list.hasNextPage && (
              <Button variant="secondary" size="lg" className="self-center" loading={list.isFetchingNextPage} onClick={() => void list.fetchNextPage()}>
                Load more
              </Button>
            )}
          </>
        )}
      </section>
    </div>
  );
}
