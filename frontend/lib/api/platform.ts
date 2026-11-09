/** Internal platform analytics. Every call is permission-checked on the backend (superuser + staff only). */

import { api } from "../api-client";
import type {
  BookingAnalytics,
  DateRange,
  Granularity,
  LibraryOrdering,
  PlatformLibraryRow,
  PlatformOverview,
  SubscriptionAnalytics,
} from "../platform-types";
import type { Page } from "../types";

export function fetchPlatformOverview(): Promise<PlatformOverview> {
  return api.get<PlatformOverview>("/platform/analytics/overview/");
}

export function fetchPlatformBookings(range: DateRange, granularity: Granularity): Promise<BookingAnalytics> {
  return api.get<BookingAnalytics>("/platform/analytics/bookings/", { query: { ...range, granularity } });
}

export function fetchPlatformSubscriptions(range: DateRange): Promise<SubscriptionAnalytics> {
  return api.get<SubscriptionAnalytics>("/platform/analytics/subscriptions/", { query: { ...range } });
}

export interface PlatformLibrariesFilters extends DateRange {
  page: number;
  search: string;
  ordering: LibraryOrdering;
  descending: boolean;
}

export function fetchPlatformLibraries(filters: PlatformLibrariesFilters): Promise<Page<PlatformLibraryRow>> {
  return api.get<Page<PlatformLibraryRow>>("/platform/analytics/libraries/", {
    query: {
      from: filters.from,
      to: filters.to,
      page: filters.page,
      search: filters.search,
      ordering: `${filters.descending ? "-" : ""}${filters.ordering}`,
    },
  });
}
