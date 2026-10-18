import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LibraryProfileForm } from "@/components/owner/library-profile-form";
import { LibrarySettings } from "@/components/owner/library-settings";
import { PhotosPanel } from "@/components/owner/photos-panel";
import { PlansPanel } from "@/components/owner/plans-panel";
import { PublishChecklist } from "@/components/owner/publish-checklist";
import { ApiError } from "@/lib/errors";
import type { OwnerLibrary, OwnerPhoto, OwnerPlan } from "@/lib/types";

import { expectNoAxeViolations } from "./axe";

const mocks = vi.hoisted(() => ({
  reloadUser: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  fetchOwnerLibrary: vi.fn(),
  createLibrary: vi.fn(),
  updateLibrary: vi.fn(),
  fetchOwnerPlans: vi.fn(),
  createPlan: vi.fn(),
  updatePlan: vi.fn(),
  setPlanActive: vi.fn(),
  fetchOwnerPhotos: vi.fn(),
  uploadPhoto: vi.fn(),
  updatePhoto: vi.fn(),
  setPhotoCover: vi.fn(),
  deletePhoto: vi.fn(),
  fetchDomains: vi.fn(),
  fetchAmenities: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { success: mocks.toastSuccess, error: mocks.toastError } }));
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ reloadUser: mocks.reloadUser }) }));
vi.mock("@/lib/api/libraries", async (original) => ({
  ...(await original<typeof import("@/lib/api/libraries")>()),
  fetchOwnerLibrary: mocks.fetchOwnerLibrary,
  createLibrary: mocks.createLibrary,
  updateLibrary: mocks.updateLibrary,
  fetchOwnerPlans: mocks.fetchOwnerPlans,
  createPlan: mocks.createPlan,
  updatePlan: mocks.updatePlan,
  setPlanActive: mocks.setPlanActive,
  fetchOwnerPhotos: mocks.fetchOwnerPhotos,
  uploadPhoto: mocks.uploadPhoto,
  updatePhoto: mocks.updatePhoto,
  setPhotoCover: mocks.setPhotoCover,
  deletePhoto: mocks.deletePhoto,
  fetchDomains: mocks.fetchDomains,
  fetchAmenities: mocks.fetchAmenities,
}));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const library: OwnerLibrary = {
  id: "l1",
  name: "Silent Hive",
  description: "Quiet.",
  address: "12 Civil Lines",
  city: "Prayagraj",
  area: "Civil Lines",
  latitude: 25.4358,
  longitude: 81.8463,
  contact_phone: "+919876543210",
  contact_email: "hello@silenthive.example",
  opens_at: "06:00:00",
  closes_at: "22:00:00",
  operating_notes: "",
  domains: [{ code: "upsc", name: "UPSC" }],
  amenities: [{ code: "wifi", name: "WiFi" }],
  is_published: false,
  is_active: true,
  publish_checklist: { has_profile: true, has_location: true, has_active_plan: false, has_active_seat: false },
};

const plan = (overrides: Partial<OwnerPlan> = {}): OwnerPlan => ({
  id: "p1",
  name: "Monthly",
  duration_days: 30,
  price: "1200.00",
  timing_note: "6 AM - 2 PM",
  is_active: true,
  in_use: false,
  ...overrides,
});

const photo = (overrides: Partial<OwnerPhoto> = {}): OwnerPhoto => ({
  id: "ph1",
  url: "/media/public/a.webp",
  thumb_url: "/media/public/a_thumb.webp",
  caption: "Reading hall",
  is_cover: true,
  display_order: 0,
  width: 800,
  height: 600,
  ...overrides,
});

const serverError = (code: string, status: number, details: Record<string, string[]> | null = null) =>
  new ApiError({ status, code, message: "x", details });

beforeEach(() => {
  for (const mock of Object.values(mocks)) mock.mockReset();
  mocks.fetchDomains.mockResolvedValue([
    { code: "upsc", name: "UPSC" },
    { code: "neet", name: "NEET" },
  ]);
  mocks.fetchAmenities.mockResolvedValue([
    { code: "wifi", name: "WiFi" },
    { code: "ac", name: "Air conditioning" },
  ]);
});

describe("PublishChecklist", () => {
  it("lists each condition and says the library is not live yet", async () => {
    const { container } = render(<PublishChecklist library={library} />);
    expect(screen.getByText("Not live yet")).toBeInTheDocument();
    expect(screen.getByText(/At least one active plan/)).toHaveTextContent("not done yet");
    expect(screen.getByText(/Location/)).toHaveTextContent("done");
    expect(screen.queryByRole("button")).not.toBeInTheDocument(); // publishing is automatic
    await expectNoAxeViolations(container);
  });

  it("links to the public page once live", () => {
    render(
      <PublishChecklist
        library={{ ...library, is_published: true, publish_checklist: { has_profile: true, has_location: true, has_active_plan: true, has_active_seat: true } }}
      />,
    );
    expect(screen.getByText("Your library is live")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view the public page/i })).toHaveAttribute("href", "/libraries/l1");
  });
});

describe("LibraryProfileForm", () => {
  it("validates before calling the server", async () => {
    renderWithClient(<LibraryProfileForm library={null} />);
    await userEvent.click(screen.getByRole("button", { name: "Create library" }));
    expect(await screen.findByText("Enter the library name.")).toBeInTheDocument();
    expect(screen.getByText("Enter the full address.")).toBeInTheDocument();
    expect(screen.getByText("Enter the city.")).toBeInTheDocument();
    expect(mocks.createLibrary).not.toHaveBeenCalled();
  });

  it("creates the library with normalised values and reloads the user", async () => {
    mocks.createLibrary.mockResolvedValue(library);
    renderWithClient(<LibraryProfileForm library={null} />);
    await userEvent.type(screen.getByLabelText(/library name/i), "Silent Hive");
    await userEvent.type(screen.getByLabelText(/^address/i), "12 Civil Lines");
    await userEvent.type(screen.getByLabelText(/^city/i), "Prayagraj");
    await userEvent.type(screen.getByLabelText("Latitude"), "25.4358");
    await userEvent.type(screen.getByLabelText("Longitude"), "81.8463");
    await userEvent.click(await screen.findByRole("button", { name: "UPSC" }));
    await userEvent.click(screen.getByRole("button", { name: "Create library" }));

    await waitFor(() => expect(mocks.createLibrary).toHaveBeenCalledTimes(1));
    expect(mocks.createLibrary.mock.calls[0]?.[0]).toMatchObject({
      name: "Silent Hive",
      city: "Prayagraj",
      latitude: 25.4358,
      longitude: 81.8463,
      opens_at: null,
      closes_at: null,
      domain_codes: ["upsc"],
      amenity_codes: [],
    });
    await waitFor(() => expect(mocks.reloadUser).toHaveBeenCalled());
    expect(mocks.toastSuccess).toHaveBeenCalledWith("Library created.");
  });

  it("edits an existing library and shows server field errors on their fields", async () => {
    mocks.updateLibrary.mockRejectedValueOnce(serverError("VALIDATION_ERROR", 400, { contact_phone: ["Enter a valid Indian mobile number."] }));
    renderWithClient(<LibraryProfileForm library={library} />);
    expect(screen.getByLabelText(/library name/i)).toHaveValue("Silent Hive");
    expect(screen.getByLabelText("Opens at")).toHaveValue("06:00");
    expect(await screen.findByRole("button", { name: "UPSC", pressed: true })).toBeInTheDocument();

    await userEvent.clear(screen.getByLabelText(/library name/i));
    await userEvent.type(screen.getByLabelText(/library name/i), "Renamed Hive");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Enter a valid Indian mobile number.")).toBeInTheDocument();
    expect(mocks.updateLibrary).toHaveBeenCalledWith(expect.objectContaining({ name: "Renamed Hive" }));
    expect(mocks.reloadUser).not.toHaveBeenCalled();

    mocks.updateLibrary.mockResolvedValueOnce({ ...library, name: "Renamed Hive" });
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(mocks.toastSuccess).toHaveBeenCalledWith("Library details saved."));
  });

  it("shows other server errors in an alert", async () => {
    mocks.updateLibrary.mockRejectedValue(serverError("RATE_LIMITED", 429));
    renderWithClient(<LibraryProfileForm library={library} />);
    await userEvent.type(screen.getByLabelText(/library name/i), "!");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/too many attempts/i);
  });

  it("is accessible", async () => {
    const { container } = renderWithClient(<LibraryProfileForm library={library} />);
    await screen.findByRole("button", { name: "NEET" });
    await expectNoAxeViolations(container);
  });
});

describe("PlansPanel", () => {
  it("shows a loading state and then the plans, hidden ones marked", async () => {
    mocks.fetchOwnerPlans.mockResolvedValue([plan(), plan({ id: "p2", name: "Old", price: "900.00", is_active: false, in_use: true })]);
    const { container } = renderWithClient(<PlansPanel />);
    expect(screen.getByText("Loading plans")).toBeInTheDocument();
    expect(await screen.findByText("Monthly")).toBeInTheDocument();
    expect(screen.getByText(/₹1,200 · 30 days · 6 AM - 2 PM/)).toBeInTheDocument();
    expect(screen.getByText("Hidden")).toBeInTheDocument();
    expect(screen.getByText(/can be hidden but not removed/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /delete|remove/i })).not.toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("shows the empty state without any pre-filled plan", async () => {
    mocks.fetchOwnerPlans.mockResolvedValue([]);
    renderWithClient(<PlansPanel />);
    expect(await screen.findByText("No plans yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add your first plan" })).toBeInTheDocument();
  });

  it("shows a retryable error", async () => {
    mocks.fetchOwnerPlans.mockRejectedValueOnce(serverError("SERVER_ERROR", 500));
    mocks.fetchOwnerPlans.mockResolvedValue([plan()]);
    renderWithClient(<PlansPanel />);
    expect(await screen.findByText("We couldn't load your plans.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Monthly")).toBeInTheDocument();
  });

  it("adds a plan after validating, sending the price as entered", async () => {
    mocks.fetchOwnerPlans.mockResolvedValue([]);
    mocks.createPlan.mockResolvedValue(plan());
    renderWithClient(<PlansPanel />);
    await userEvent.click(await screen.findByRole("button", { name: "Add your first plan" }));
    const dialog = await screen.findByRole("dialog", { name: "Add a plan" });

    await userEvent.type(within(dialog).getByLabelText(/duration/i), "0");
    await userEvent.type(within(dialog).getByLabelText(/price/i), "0");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add plan" }));
    expect(await within(dialog).findByText("Enter a plan name.")).toBeInTheDocument();
    expect(within(dialog).getByText("Duration is between 1 and 366 days.")).toBeInTheDocument();
    expect(within(dialog).getByText("The price must be more than zero.")).toBeInTheDocument();
    expect(mocks.createPlan).not.toHaveBeenCalled();

    await userEvent.type(within(dialog).getByLabelText(/plan name/i), "Monthly");
    await userEvent.clear(within(dialog).getByLabelText(/duration/i));
    await userEvent.type(within(dialog).getByLabelText(/duration/i), "30");
    await userEvent.clear(within(dialog).getByLabelText(/price/i));
    await userEvent.type(within(dialog).getByLabelText(/price/i), "1200.50");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add plan" }));
    await waitFor(() =>
      expect(mocks.createPlan).toHaveBeenCalledWith({ name: "Monthly", duration_days: 30, price: "1200.50", timing_note: "" }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(mocks.toastSuccess).toHaveBeenCalledWith("Plan added.");
  });

  it("puts a duplicate-name conflict on the name field", async () => {
    mocks.fetchOwnerPlans.mockResolvedValue([plan()]);
    mocks.createPlan.mockRejectedValue(serverError("PLAN_NAME_TAKEN", 409));
    renderWithClient(<PlansPanel />);
    await userEvent.click(await screen.findByRole("button", { name: "Add plan" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText(/plan name/i), "Monthly");
    await userEvent.type(within(dialog).getByLabelText(/duration/i), "30");
    await userEvent.type(within(dialog).getByLabelText(/price/i), "1000");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add plan" }));
    expect(await within(dialog).findByText("You already have an active plan with this name.")).toBeInTheDocument();
  });

  it("edits a plan with its current values", async () => {
    mocks.fetchOwnerPlans.mockResolvedValue([plan()]);
    mocks.updatePlan.mockResolvedValue(plan({ price: "1300.00" }));
    renderWithClient(<PlansPanel />);
    await userEvent.click(await screen.findByRole("button", { name: /edit monthly/i }));
    const dialog = await screen.findByRole("dialog", { name: "Edit plan" });
    expect(within(dialog).getByLabelText(/price/i)).toHaveValue("1200.00");
    await userEvent.clear(within(dialog).getByLabelText(/price/i));
    await userEvent.type(within(dialog).getByLabelText(/price/i), "1300");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save plan" }));
    await waitFor(() => expect(mocks.updatePlan).toHaveBeenCalledWith("p1", expect.objectContaining({ price: "1300", duration_days: 30 })));
  });

  it("hides and shows a plan", async () => {
    mocks.fetchOwnerPlans.mockResolvedValue([plan()]);
    mocks.setPlanActive.mockResolvedValue(plan({ is_active: false }));
    renderWithClient(<PlansPanel />);
    await userEvent.click(await screen.findByRole("button", { name: /hide monthly/i }));
    await waitFor(() => expect(mocks.setPlanActive).toHaveBeenCalledWith("p1", false));
    expect(mocks.toastSuccess).toHaveBeenCalledWith("Plan hidden from booking.");
  });

  it("reports a failed toggle", async () => {
    mocks.fetchOwnerPlans.mockResolvedValue([plan({ is_active: false })]);
    mocks.setPlanActive.mockRejectedValue(serverError("PLAN_NAME_TAKEN", 409));
    renderWithClient(<PlansPanel />);
    await userEvent.click(await screen.findByRole("button", { name: /show monthly/i }));
    await waitFor(() => expect(mocks.toastError).toHaveBeenCalledWith("You already have an active plan with this name."));
  });
});

describe("PhotosPanel", () => {
  it("shows the gallery with the cover marked", async () => {
    mocks.fetchOwnerPhotos.mockResolvedValue([photo(), photo({ id: "ph2", caption: "", is_cover: false, display_order: 1 })]);
    const { container } = renderWithClient(<PhotosPanel />);
    expect(screen.getByText("Loading photos")).toBeInTheDocument();
    expect(await screen.findByText("Cover photo")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /make cover/i })).toHaveLength(1);
    await expectNoAxeViolations(container);
  });

  it("shows the empty state", async () => {
    mocks.fetchOwnerPhotos.mockResolvedValue([]);
    renderWithClient(<PhotosPanel />);
    expect(await screen.findByText("No photos yet")).toBeInTheDocument();
  });

  it("shows a retryable error", async () => {
    mocks.fetchOwnerPhotos.mockRejectedValueOnce(serverError("SERVER_ERROR", 500));
    mocks.fetchOwnerPhotos.mockResolvedValue([photo()]);
    renderWithClient(<PhotosPanel />);
    expect(await screen.findByText("We couldn't load your photos.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Cover photo")).toBeInTheDocument();
  });

  it("uploads several files one by one and reports each result", async () => {
    mocks.fetchOwnerPhotos.mockResolvedValue([]);
    mocks.uploadPhoto.mockResolvedValueOnce(photo()).mockRejectedValueOnce(serverError("FILE_TYPE", 400));
    renderWithClient(<PhotosPanel />);
    await screen.findByText("No photos yet");
    const files = [new File(["a"], "good.jpg", { type: "image/jpeg" }), new File(["b"], "bad.jpg", { type: "image/jpeg" })];
    await userEvent.upload(screen.getByLabelText("Choose photos to upload"), files);
    expect(await screen.findByText(/good\.jpg: uploaded/)).toBeInTheDocument();
    expect(await screen.findByText(/bad\.jpg: Upload a JPG, PNG or WEBP image\./)).toBeInTheDocument();
    expect(mocks.uploadPhoto).toHaveBeenCalledTimes(2);
  });

  it("refuses files over 5 MB without calling the server", async () => {
    mocks.fetchOwnerPhotos.mockResolvedValue([]);
    renderWithClient(<PhotosPanel />);
    await screen.findByText("No photos yet");
    const big = new File([new Uint8Array(5 * 1024 * 1024 + 1)], "huge.jpg", { type: "image/jpeg" });
    await userEvent.upload(screen.getByLabelText("Choose photos to upload"), big);
    expect(await screen.findByText(/huge\.jpg: This file is over 5 MB\./)).toBeInTheDocument();
    expect(mocks.uploadPhoto).not.toHaveBeenCalled();
  });

  it("changes the cover and saves a caption", async () => {
    mocks.fetchOwnerPhotos.mockResolvedValue([photo(), photo({ id: "ph2", caption: "", is_cover: false, display_order: 1 })]);
    mocks.setPhotoCover.mockResolvedValue(photo({ id: "ph2", is_cover: true }));
    mocks.updatePhoto.mockResolvedValue(photo({ id: "ph2", caption: "Desks" }));
    renderWithClient(<PhotosPanel />);
    await userEvent.click(await screen.findByRole("button", { name: /make cover/i }));
    await waitFor(() => expect(mocks.setPhotoCover).toHaveBeenCalledWith("ph2"));

    const caption = screen.getByLabelText("Caption for photo 2");
    await userEvent.type(caption, " Desks ");
    const card = caption.closest("li") as HTMLElement;
    await userEvent.click(within(card).getByRole("button", { name: "Save caption" }));
    await waitFor(() => expect(mocks.updatePhoto).toHaveBeenCalledWith("ph2", { caption: "Desks" }));
  });

  it("asks before deleting a photo", async () => {
    mocks.fetchOwnerPhotos.mockResolvedValue([photo()]);
    mocks.deletePhoto.mockResolvedValue({});
    renderWithClient(<PhotosPanel />);
    await userEvent.click(await screen.findByRole("button", { name: /delete photo 1/i }));
    const dialog = await screen.findByRole("dialog", { name: "Delete this photo?" });
    expect(dialog).toHaveTextContent(/cover photo/i);
    expect(mocks.deletePhoto).not.toHaveBeenCalled();
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete photo" }));
    await waitFor(() => expect(mocks.deletePhoto).toHaveBeenCalledWith("ph1"));
  });
});

describe("LibrarySettings", () => {
  it("shows the checklist and the three tabs for an owner with a library", async () => {
    mocks.fetchOwnerLibrary.mockResolvedValue(library);
    mocks.fetchOwnerPlans.mockResolvedValue([plan()]);
    const { container } = renderWithClient(<LibrarySettings />);
    expect(await screen.findByRole("heading", { name: "Go-live checklist" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Profile" })).toHaveAttribute("aria-selected", "true");
    await userEvent.click(screen.getByRole("tab", { name: "Plans" }));
    expect(await screen.findByText("Monthly")).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("offers library creation when the owner has none", async () => {
    mocks.fetchOwnerLibrary.mockResolvedValue(null);
    renderWithClient(<LibrarySettings />);
    expect(await screen.findByRole("button", { name: "Create library" })).toBeInTheDocument();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  });

  it("shows a retryable error when the library cannot be loaded", async () => {
    mocks.fetchOwnerLibrary.mockRejectedValueOnce(serverError("SERVER_ERROR", 500));
    mocks.fetchOwnerLibrary.mockResolvedValue(library);
    renderWithClient(<LibrarySettings />);
    expect(await screen.findByText("We couldn't load your library.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByRole("heading", { name: "Go-live checklist" })).toBeInTheDocument();
  });
});
