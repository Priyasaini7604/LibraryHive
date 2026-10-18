import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DiscoverView } from "@/components/library/discover-view";
import { LibraryPage } from "@/components/library/library-page";
import { PhotoGallery } from "@/components/library/photo-gallery";
import { ApiError } from "@/lib/errors";
import type { LibraryDetail, LibrarySummary, Page } from "@/lib/types";

import { expectNoAxeViolations } from "./axe";

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  search: new URLSearchParams(),
  fetchLibraries: vi.fn(),
  fetchLibrary: vi.fn(),
  fetchDomains: vi.fn(),
  fetchAmenities: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mocks.replace }),
  usePathname: () => "/discover",
  useSearchParams: () => mocks.search,
}));
vi.mock("@/lib/api/libraries", async (original) => ({
  ...(await original<typeof import("@/lib/api/libraries")>()),
  fetchLibraries: mocks.fetchLibraries,
  fetchLibrary: mocks.fetchLibrary,
  fetchDomains: mocks.fetchDomains,
  fetchAmenities: mocks.fetchAmenities,
}));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const summary = (overrides: Partial<LibrarySummary> = {}): LibrarySummary => ({
  id: "l1",
  name: "Silent Hive",
  city: "Prayagraj",
  area: "Civil Lines",
  amenities: ["wifi", "ac", "locker", "cctv"],
  domains: ["upsc", "ssc", "neet"],
  starting_price: "1200.00",
  ...overrides,
});

const page = (items: LibrarySummary[], overrides: Partial<Page<LibrarySummary>> = {}): Page<LibrarySummary> => ({
  items,
  page: 1,
  page_size: 12,
  total: items.length,
  ...overrides,
});

const detail: LibraryDetail = {
  id: "l1",
  name: "Silent Hive",
  description: "A quiet place to prepare.",
  address: "12 Civil Lines",
  city: "Prayagraj",
  area: "Civil Lines",
  latitude: 25.4358,
  longitude: 81.8463,
  contact_phone: "+919876543210",
  contact_email: "hello@silenthive.example",
  opens_at: "06:00:00",
  closes_at: "22:00:00",
  operating_notes: "Open 24x7 during exams",
  amenities: [{ code: "wifi", name: "WiFi" }],
  domains: [{ code: "upsc", name: "UPSC" }],
  plans: [
    { id: "p1", name: "Monthly", duration_days: 30, price: "1200.00", timing_note: "6 AM - 2 PM" },
    { id: "p2", name: "Quarterly", duration_days: 90, price: "3200.00", timing_note: "" },
  ],
  photos: [
    { id: "ph1", url: "/media/public/a.webp", thumb_url: "/media/public/a_thumb.webp", caption: "Reading hall", is_cover: true },
    { id: "ph2", url: "/media/public/b.webp", thumb_url: "/media/public/b_thumb.webp", caption: "", is_cover: false },
  ],
};

beforeEach(() => {
  mocks.replace.mockReset();
  for (const key of [...mocks.search.keys()]) mocks.search.delete(key);
  mocks.fetchLibraries.mockReset();
  mocks.fetchLibrary.mockReset();
  mocks.fetchDomains.mockResolvedValue([
    { code: "upsc", name: "UPSC" },
    { code: "ssc", name: "SSC" },
    { code: "neet", name: "NEET" },
  ]);
  mocks.fetchAmenities.mockResolvedValue([
    { code: "wifi", name: "WiFi" },
    { code: "ac", name: "Air conditioning" },
    { code: "locker", name: "Lockers" },
    { code: "cctv", name: "CCTV" },
  ]);
});

describe("DiscoverView", () => {
  it("shows skeletons while loading, then the cards with real names and prices", async () => {
    mocks.fetchLibraries.mockResolvedValue(page([summary()]));
    const { container } = renderWithClient(<DiscoverView />);
    expect(screen.getByText("Loading libraries")).toBeInTheDocument();

    const link = await screen.findByRole("link", { name: "Silent Hive" });
    expect(link).toHaveAttribute("href", "/libraries/l1");
    expect(screen.getByText("From ₹1,200")).toBeInTheDocument();
    expect(screen.getByText("Civil Lines, Prayagraj")).toBeInTheDocument();
    // at most 3 amenity chips and 2 domain chips per card, shown by name
    const card = link.closest("li") as HTMLElement;
    await waitFor(() => expect(within(card).getByText("Air conditioning")).toBeInTheDocument());
    expect(within(card).queryByText("CCTV")).not.toBeInTheDocument();
    expect(within(card).getByText("SSC")).toBeInTheDocument();
    expect(within(card).queryByText("NEET")).not.toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("never shows seat figures the API did not send, and shows them when it does", async () => {
    mocks.fetchLibraries.mockResolvedValue(
      page([summary(), summary({ id: "l2", name: "Busy Hive", seat_counts: { total: 10, empty: 4, reserved: 1, occupied: 5 } })]),
    );
    renderWithClient(<DiscoverView />);
    await screen.findByRole("link", { name: "Busy Hive" });
    expect(screen.getAllByText(/seats free/i)).toHaveLength(1);
    expect(screen.getByText("4 of 10 seats free")).toBeInTheDocument();
  });

  it("shows the empty state with a way to clear filters", async () => {
    mocks.search.set("domain", "upsc");
    mocks.fetchLibraries.mockResolvedValue(page([]));
    renderWithClient(<DiscoverView />);
    expect(await screen.findByText("No libraries found here yet")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(mocks.replace).toHaveBeenCalledWith("/discover", { scroll: false });
  });

  it("shows an error with a retry that reloads", async () => {
    mocks.fetchLibraries.mockRejectedValueOnce(new ApiError({ status: 500, code: "SERVER_ERROR", message: "x" }));
    mocks.fetchLibraries.mockResolvedValue(page([summary()]));
    renderWithClient(<DiscoverView />);
    expect(await screen.findByText("We couldn't load libraries.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByRole("link", { name: "Silent Hive" })).toBeInTheDocument();
  });

  it("puts filters in the URL and sends them to the API", async () => {
    mocks.search.set("domain", "ssc");
    mocks.search.append("amenity", "wifi");
    mocks.fetchLibraries.mockResolvedValue(page([summary()]));
    renderWithClient(<DiscoverView />);
    await screen.findByRole("link", { name: "Silent Hive" });
    expect(mocks.fetchLibraries).toHaveBeenCalledWith(
      expect.objectContaining({ domain: "ssc", amenity: ["wifi"], page: 1, page_size: 12 }),
      expect.anything(),
    );
    expect(await screen.findByRole("button", { name: "SSC", pressed: true })).toBeInTheDocument();

    await userEvent.click(await screen.findByRole("button", { name: "Lockers" }));
    expect(mocks.replace).toHaveBeenLastCalledWith("/discover?domain=ssc&amenity=wifi&amenity=locker", { scroll: false });
    await userEvent.click(screen.getByRole("button", { name: "SSC" }));
    expect(mocks.replace).toHaveBeenLastCalledWith("/discover?amenity=wifi", { scroll: false });
  });

  it("loads the next page on demand", async () => {
    mocks.fetchLibraries.mockImplementation(async (filters: { page: number }) =>
      filters.page === 1
        ? page([summary()], { total: 2, page_size: 1 })
        : page([summary({ id: "l2", name: "Second Hive" })], { page: 2, total: 2, page_size: 1 }),
    );
    renderWithClient(<DiscoverView />);
    await screen.findByRole("link", { name: "Silent Hive" });
    await userEvent.click(screen.getByRole("button", { name: "Load more" }));
    expect(await screen.findByRole("link", { name: "Second Hive" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
  });

  it("explains when location access is denied instead of failing", async () => {
    mocks.fetchLibraries.mockResolvedValue(page([summary()]));
    const getCurrentPosition = vi.fn((_ok: PositionCallback, fail: PositionErrorCallback) =>
      fail({ code: 1, message: "denied" } as GeolocationPositionError),
    );
    vi.stubGlobal("navigator", { ...navigator, geolocation: { getCurrentPosition } });
    renderWithClient(<DiscoverView />);
    await userEvent.click(screen.getByRole("button", { name: /use my location/i }));
    expect(await screen.findByText(/couldn't get your location/i)).toBeInTheDocument();
    expect(mocks.replace).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it("uses the position and sorts by distance when location is allowed", async () => {
    mocks.fetchLibraries.mockResolvedValue(page([summary({ distance_km: 1.2 })]));
    const getCurrentPosition = vi.fn((success: PositionCallback) =>
      success({ coords: { latitude: 25.43, longitude: 81.84 } } as GeolocationPosition),
    );
    vi.stubGlobal("navigator", { ...navigator, geolocation: { getCurrentPosition } });
    renderWithClient(<DiscoverView />);
    await userEvent.click(screen.getByRole("button", { name: /use my location/i }));
    expect(mocks.replace).toHaveBeenCalledWith("/discover?lat=25.43&lng=81.84&sort=distance", { scroll: false });
    vi.unstubAllGlobals();
  });

  it("debounces typing into the search box", async () => {
    mocks.fetchLibraries.mockResolvedValue(page([summary()]));
    renderWithClient(<DiscoverView />);
    await screen.findByRole("link", { name: "Silent Hive" });
    await userEvent.type(screen.getByRole("searchbox", { name: /search area or library/i }), "civil");
    expect(mocks.replace).not.toHaveBeenCalled();
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/discover?search=civil", { scroll: false }), {
      timeout: 2000,
    });
  });
});

describe("LibraryPage", () => {
  it("shows a loading state, then the library with its real plans and facts", async () => {
    mocks.fetchLibrary.mockResolvedValue(detail);
    const { container } = renderWithClient(<LibraryPage id="l1" />);
    expect(screen.getByText("Loading library")).toBeInTheDocument();

    expect(await screen.findByRole("heading", { level: 1, name: "Silent Hive" })).toBeInTheDocument();
    expect(screen.getByText(/12 Civil Lines, Civil Lines, Prayagraj/)).toBeInTheDocument();
    expect(screen.getByText(/6:00 am – 10:00 pm/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "+91 98765 43210" })).toHaveAttribute("href", "tel:+919876543210");
    expect(screen.getByRole("link", { name: /open in maps/i })).toHaveAttribute(
      "href",
      expect.stringContaining("mlat=25.4358"),
    );
    const plans = within(screen.getByRole("region", { name: "Plans" }));
    expect(plans.getByText("₹1,200")).toBeInTheDocument();
    expect(plans.getByText("30 days")).toBeInTheDocument();
    expect(plans.getByText("6 AM - 2 PM")).toBeInTheDocument();
    expect(plans.getByText("₹3,200")).toBeInTheDocument();
    expect(screen.getByText("WiFi")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Seats" })).not.toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("shows seat counts only when the API provides them", async () => {
    mocks.fetchLibrary.mockResolvedValue({ ...detail, seat_counts: { total: 20, empty: 8, reserved: 2, occupied: 10 } });
    renderWithClient(<LibraryPage id="l1" />);
    expect(await screen.findByText(/8 free · 2 reserved · 10 occupied · 20 in total/)).toBeInTheDocument();
  });

  it("explains an unavailable library on 404 instead of a generic error", async () => {
    mocks.fetchLibrary.mockRejectedValue(new ApiError({ status: 404, code: "NOT_FOUND", message: "x" }));
    renderWithClient(<LibraryPage id="gone" />);
    expect(await screen.findByText("This library isn't available")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse libraries" })).toHaveAttribute("href", "/discover");
  });

  it("shows a retryable error for other failures", async () => {
    mocks.fetchLibrary.mockRejectedValueOnce(new ApiError({ status: 500, code: "SERVER_ERROR", message: "x" }));
    mocks.fetchLibrary.mockResolvedValue(detail);
    renderWithClient(<LibraryPage id="l1" />);
    expect(await screen.findByText("We couldn't load this library.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByRole("heading", { level: 1, name: "Silent Hive" })).toBeInTheDocument();
  });

  it("handles a library with no photos, plans or amenities", async () => {
    mocks.fetchLibrary.mockResolvedValue({ ...detail, photos: [], plans: [], amenities: [], domains: [], description: "" });
    renderWithClient(<LibraryPage id="l1" />);
    expect(await screen.findByRole("img", { name: /no photos of silent hive yet/i })).toBeInTheDocument();
    expect(screen.getByText("No plans yet")).toBeInTheDocument();
  });
});

describe("PhotoGallery", () => {
  it("opens a lightbox with captions and navigates with the arrow keys", async () => {
    renderWithClient(<PhotoGallery photos={detail.photos} libraryName="Silent Hive" />);
    expect(screen.getByRole("img", { name: "Reading hall" })).toHaveAttribute(
      "src",
      "http://127.0.0.1:8000/media/public/a.webp",
    );
    await userEvent.click(screen.getByRole("button", { name: /view all 2 photos/i }));
    const dialog = await screen.findByRole("dialog", { name: /silent hive photos/i });
    expect(within(dialog).getByText("Reading hall")).toBeInTheDocument();
    expect(within(dialog).getByText("Photo 1 of 2")).toBeInTheDocument();

    await userEvent.keyboard("{ArrowRight}");
    expect(within(dialog).getByText("Photo 2 of 2")).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Next photo" }));
    expect(within(dialog).getByText("Photo 1 of 2")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
