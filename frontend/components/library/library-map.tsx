"use client";

import dynamic from "next/dynamic";

import { Skeleton } from "@/components/ui/states";

/** Leaflet touches `window`, so it is imported only in the browser and only where a map is shown. */
export const LazyMap = dynamic(() => import("./leaflet-map"), {
  ssr: false,
  loading: () => <Skeleton className="h-72 w-full rounded-xl" />,
});

/** The single-pin map on the public library page (#15 `latitude` / `longitude`). Renders nothing without both. */
export function LibraryMap({ latitude, longitude, name }: { latitude: number | null; longitude: number | null; name: string }) {
  if (latitude === null || longitude === null) return null;
  return (
    <section aria-labelledby="location-heading">
      <h2 id="location-heading" className="mb-4 text-2xl font-bold text-slate-900">
        Location
      </h2>
      <LazyMap label={`Map showing where ${name} is`} point={{ latitude, longitude }} />
    </section>
  );
}
