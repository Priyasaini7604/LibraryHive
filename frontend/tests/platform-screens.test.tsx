import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PlatformLibrariesScreen } from "@/components/platform/libraries-screen";
import { PlatformOverviewScreen } from "@/components/platform/overview-screen";
import { PRESETS } from "@/components/platform/range-filter";
import { ApiError } from "@/lib/errors";
import { OWNER_NAV, PLATFORM_NAV, STUDENT_NAV, homeFor } from "@/lib/navigation";
import type { BookingAnalytics, PlatformLibraryRow, PlatformOverview, SubscriptionAnalytics } from "@/lib/platform-types";
import type { Page } from "@/lib/types";

import { expectNoAxeViolations } from "./axe";

vi.setConfig({ testTimeout: 20_000 });

const mocks = vi.hoisted(() => ({
  fetchPlatformOverview: vi.fn(),
  fetchPlatformBookings: vi.fn(),
  fetchPlatformSubscriptions: vi.fn(),
  fetchPlatformLibraries: vi.fn(),
}));
vi.mock("@/lib/api/platform", () => mocks);

const overview: PlatformOverview = {
  as_of: "2026-11-06",
  students: { registered: 120, offline_walk_ins: 15 },
  libraries: { registered: 9, published: 7, active: 6 },
  bookings: { total: 300, online: 210, offline: 90, unique_students: 95, monthly_active_students: 40 },
};

const bookings: BookingAnalytics = {
  range: { from: "2026-10-08", to: "2026-11-06" },
  granularity: "day",
  today: 3,
  this_week: 11,
  this_month: 25,
  in_range: {
    bookings: 60,
    online: 45,
    offline: 15,
    unique_students: 40,
    repeat_students: 10,
    repeat_booking_percent: 25,
    renewals: 12,
    archived_memberships: 2,
    check_ins: 200,
    students_checked_in: 33,
  },
  holds: { completed: 60, cancelled: 4, expired: 6, still_pending: 1, abandoned: 10, abandoned_percent: 14.3 },
  trend: [
    { date: "2026-11-05", bookings: 4, unique_students: 4 },
    { date: "2026-11-06", bookings: 3, unique_students: 3 },
  ],
  by_library: [{ library_id: "l1", name: "Central Reading Room", bookings: 30, unique_students: 20 }],
};

const subscriptions: SubscriptionAnalytics = {
  range: bookings.range,
  libraries: 9,
  averages_per_library: { bookings: 6.67, unique_booking_students: 4.4 },
  platform_unique_students: 40,
  student_payments_online: {
    successful: 45,
    failed: 3,
    cancelled: 1,
    pending: 0,
    needs_refund: 0,
    amount_successful: "54000.00",
    is_platform_revenue: false,
  },
  unavailable: [
    { key: "subscription_plan", label: "Library subscription plan and status", reason: "No subscription model exists." },
    { key: "platform_revenue", label: "Subscription revenue, MRR and revenue by plan", reason: "No library subscription payments exist." },
  ],
};

const row: PlatformLibraryRow = {
  id: "l1",
  name: "Central Reading Room",
  city: "Jaipur",
  is_published: true,
  registered_members: 22,
  active_members: 18,
  online_students: 14,
  total_bookings: 30,
  bookings_in_range: 12,
  unique_students_in_range: 10,
  check_ins_in_range: 80,
  subscription_plan: null,
  subscription_status: null,
};

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  Object.values(mocks).forEach((mock) => mock.mockReset());
  mocks.fetchPlatformOverview.mockResolvedValue(overview);
  mocks.fetchPlatformBookings.mockResolvedValue(bookings);
  mocks.fetchPlatformSubscriptions.mockResolvedValue(subscriptions);
});

describe("platform overview", () => {
  it("shows platform totals, booking cards and the unavailable metrics", async () => {
    const { container } = renderWithClient(<PlatformOverviewScreen />);
    expect(await screen.findByText("Registered students")).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument();
    expect(screen.getByText("Booked in the current calendar month")).toBeInTheDocument();
    expect(await screen.findByText("Renewals paid")).toBeInTheDocument();
    expect(screen.getByText("25%")).toBeInTheDocument();
    expect(screen.getByText("Central Reading Room")).toBeInTheDocument();
    const warning = await screen.findByText("Not available yet: subscription and revenue metrics");
    expect(warning).toBeInTheDocument();
    expect(screen.getByText(/No subscription model exists/)).toBeInTheDocument();
    expect(screen.getByText(/Not LibraryHive revenue/)).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("asks the backend for the chosen date range", async () => {
    renderWithClient(<PlatformOverviewScreen />);
    await screen.findByText("Renewals paid");
    const firstRange = mocks.fetchPlatformBookings.mock.calls[0]![0] as { from: string; to: string };
    await userEvent.click(screen.getByRole("button", { name: "7 days" }));
    await waitFor(() => {
      const last = mocks.fetchPlatformBookings.mock.calls.at(-1)![0] as { from: string; to: string };
      expect(last.from > firstRange.from).toBe(true);
      expect(last.to).toBe(firstRange.to);
    });
    expect(PRESETS.map((preset) => preset.label)).toEqual(["7 days", "30 days", "90 days", "Custom"]);
  });

  it("shows an error with retry when the backend refuses", async () => {
    mocks.fetchPlatformOverview.mockRejectedValue(new ApiError({ status: 403, code: "PERMISSION_DENIED", message: "Only the LibraryHive team can do this." }));
    renderWithClient(<PlatformOverviewScreen />);
    expect(await screen.findByText("We could not load the overview.")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Try again" }).length).toBeGreaterThan(0);
  });

  it("shows an empty state when there are no bookings in the range", async () => {
    mocks.fetchPlatformBookings.mockResolvedValue({
      ...bookings,
      in_range: { ...bookings.in_range, bookings: 0 },
      by_library: [],
    });
    renderWithClient(<PlatformOverviewScreen />);
    expect((await screen.findAllByText("No bookings in this range")).length).toBeGreaterThan(0);
  });
});

describe("platform libraries", () => {
  it("renders the paginated table with a dash for subscription data", async () => {
    const page: Page<PlatformLibraryRow> = { items: [row], page: 1, page_size: 20, total: 1 };
    mocks.fetchPlatformLibraries.mockResolvedValue(page);
    renderWithClient(<PlatformLibrariesScreen />);
    const table = await screen.findByRole("table", { name: "Library performance" });
    expect(within(table).getByText("Central Reading Room")).toBeInTheDocument();
    expect(within(table).getByText("80")).toBeInTheDocument();
    expect(within(table).getAllByText("—").length).toBeGreaterThan(0);
  });

  it("sends the sort order to the backend", async () => {
    mocks.fetchPlatformLibraries.mockResolvedValue({ items: [row], page: 1, page_size: 20, total: 1 });
    renderWithClient(<PlatformLibrariesScreen />);
    await screen.findByRole("table", { name: "Library performance" });
    await userEvent.selectOptions(screen.getByLabelText("Sort by"), "members");
    await waitFor(() => {
      expect(mocks.fetchPlatformLibraries.mock.calls.at(-1)![0]).toMatchObject({ ordering: "members", page: 1 });
    });
  });

  it("shows an empty state", async () => {
    mocks.fetchPlatformLibraries.mockResolvedValue({ items: [], page: 1, page_size: 20, total: 0 });
    renderWithClient(<PlatformLibrariesScreen />);
    expect(await screen.findByText("No libraries yet")).toBeInTheDocument();
  });
});

describe("platform navigation", () => {
  it("is never part of the owner or student navigation", () => {
    const hrefs = [...OWNER_NAV, ...STUDENT_NAV].map((item) => item.href);
    expect(hrefs.some((href) => href.startsWith("/platform"))).toBe(false);
    expect(PLATFORM_NAV.every((item) => item.href.startsWith("/platform"))).toBe(true);
  });

  it("routes only platform admins to /platform", () => {
    expect(homeFor("owner", true)).toBe("/platform");
    expect(homeFor("owner")).toBe("/owner");
    expect(homeFor("student")).toBe("/student");
  });
});
