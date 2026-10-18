import type { Metadata } from "next";
import { Suspense } from "react";

import { DiscoverView } from "@/components/library/discover-view";
import { FullPageSkeleton } from "@/components/ui/states";

export const metadata: Metadata = { title: "Discover libraries" };

export default function DiscoverPage() {
  // useSearchParams (filters in the URL) needs a Suspense boundary.
  return (
    <Suspense fallback={<FullPageSkeleton />}>
      <DiscoverView />
    </Suspense>
  );
}
