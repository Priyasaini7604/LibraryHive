import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdmissionScreen } from "@/components/owner/admission-screen";
import { OwnerDashboardScreen } from "@/components/owner/dashboard-screen";
import { DuesScreen } from "@/components/owner/dues-screen";
import { MemberDetailScreen } from "@/components/owner/member-detail-screen";
import { MembersScreen } from "@/components/owner/members-screen";
import { OwnerPaymentsScreen } from "@/components/owner/owner-payments-screen";
import { SeatManager } from "@/components/owner/seat-manager";
import { ApiError } from "@/lib/errors";
import type { DueRow, OwnerDashboard, OwnerMember, OwnerMemberDetail, OwnerPayment, OwnerSeat } from "@/lib/types";

import { expectNoAxeViolations } from "./axe";

// Radix selects and dialogs are slow to drive in jsdom on a busy machine; a generous limit avoids false failures.
vi.setConfig({ testTimeout: 20_000 });

const mocks = vi.hoisted(() => ({
  fetchOwnerPlans: vi.fn(),
  fetchDomains: vi.fn(),
  fetchMembers: vi.fn(),
  fetchMember: vi.fn(),
  archiveMember: vi.fn(),
  recordRenewal: vi.fn(),
  fetchDues: vi.fn(),
  lookupAdmission: vi.fn(),
  admitStudent: vi.fn(),
  fetchOwnerPayments: vi.fn(),
  fetchOwnerPayment: vi.fn(),
  fetchOwnerDashboard: vi.fn(),
  fetchOwnerSeats: vi.fn(),
  placeManualHold: vi.fn(),
  releaseHold: vi.fn(),
  disableSeat: vi.fn(),
  enableSeat: vi.fn(),
  deactivateSeat: vi.fn(),
  updateSeat: vi.fn(),
  addSeats: vi.fn(),
  downloadExport: vi.fn(),
}));

vi.mock("@/lib/api/libraries", () => ({ fetchOwnerPlans: mocks.fetchOwnerPlans, fetchDomains: mocks.fetchDomains }));
vi.mock("@/lib/api/memberships", () => ({
  fetchMembers: mocks.fetchMembers,
  fetchMember: mocks.fetchMember,
  archiveMember: mocks.archiveMember,
  recordRenewal: mocks.recordRenewal,
  fetchDues: mocks.fetchDues,
  lookupAdmission: mocks.lookupAdmission,
  admitStudent: mocks.admitStudent,
}));
vi.mock("@/lib/api/payments", () => ({ fetchOwnerPayments: mocks.fetchOwnerPayments, fetchOwnerPayment: mocks.fetchOwnerPayment }));
vi.mock("@/lib/api/operations", () => ({ fetchOwnerDashboard: mocks.fetchOwnerDashboard, downloadExport: mocks.downloadExport }));
vi.mock("@/lib/api/seats", () => ({
  fetchOwnerSeats: mocks.fetchOwnerSeats,
  placeManualHold: mocks.placeManualHold,
  releaseHold: mocks.releaseHold,
  disableSeat: mocks.disableSeat,
  enableSeat: mocks.enableSeat,
  deactivateSeat: mocks.deactivateSeat,
  updateSeat: mocks.updateSeat,
  addSeats: mocks.addSeats,
}));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const page = <T,>(items: T[]) => ({ items, page: 1, page_size: 20, total: items.length });

const plans = [
  { id: "p1", name: "Monthly", duration_days: 30, price: "1200.00", timing_note: "", is_active: true, in_use: true },
  { id: "p2", name: "Quarterly", duration_days: 90, price: "3200.00", timing_note: "", is_active: true, in_use: false },
];

const seat = (overrides: Partial<OwnerSeat> = {}): OwnerSeat => ({
  id: "s1",
  label: "A-1",
  row_label: "A",
  position: 1,
  is_active: true,
  is_disabled: false,
  disabled_reason: "",
  status: "empty",
  occupant: null,
  hold: null,
  ...overrides,
});

const member = (overrides: Partial<OwnerMember> = {}): OwnerMember => ({
  membership_id: "m1",
  student: { id: "u1", name: "Asha Verma", phone: "+919123456780", email: "asha@example.com", domain: "UPSC", is_offline: false },
  seat: { id: "s1", label: "A-1" },
  plan: { id: "p1", name: "Monthly" },
  source: "online",
  status: "active",
  start_date: "2026-10-01",
  next_due_date: "2026-10-31",
  ...overrides,
});

const detail = (overrides: Partial<OwnerMemberDetail> = {}): OwnerMemberDetail => ({
  ...member(),
  archived_at: null,
  archive_reason: "",
  attendance_summary: { this_month_days: 4, last_check_in: "2026-10-17T04:00:00Z" },
  complaints_count: 1,
  payments: [
    { id: "pay1", receipt_number: "LH-2026-000001", purpose: "new_membership", channel: "offline", method: "cash", amount: "1200.00", plan: "Monthly", period_start: "2026-10-01", period_end: "2026-10-31", paid_at: "2026-10-01T05:00:00Z" },
  ],
  other_memberships_here: [],
  ...overrides,
});

beforeEach(() => {
  for (const mock of Object.values(mocks)) mock.mockReset();
  mocks.fetchOwnerPlans.mockResolvedValue(plans);
  mocks.fetchDomains.mockResolvedValue([{ code: "upsc", name: "UPSC" }]);
  mocks.fetchOwnerSeats.mockResolvedValue({
    seats: [seat(), seat({ id: "s2", label: "A-2", position: 2, status: "occupied", occupant: { membership_id: "m1", student_name: "Asha Verma" } })],
    counts: { total: 2, empty: 1, reserved: 0, occupied: 1 },
  });
});

async function choose(label: RegExp | string, option: RegExp | string) {
  await userEvent.click(await screen.findByRole("combobox", { name: label }));
  await userEvent.click(await screen.findByRole("option", { name: option }));
}

describe("AdmissionScreen", () => {
  async function fillIdentity(phone = "9123456780") {
    await userEvent.type(await screen.findByLabelText(/Full name/), "Ravi Kumar");
    await userEvent.type(screen.getByLabelText(/Mobile number/), phone);
  }

  it("offers only free seats and active plans, and shows no amount field", async () => {
    const { container } = renderWithClient(<AdmissionScreen />);
    await userEvent.click(await screen.findByRole("combobox", { name: /Seat/ }));
    expect(await screen.findByRole("option", { name: "A-1" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "A-2" })).not.toBeInTheDocument(); // occupied
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByLabelText(/amount/i)).not.toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("preselects the seat the owner came from", async () => {
    renderWithClient(<AdmissionScreen initialSeatId="s1" />);
    expect(await screen.findByRole("combobox", { name: /Seat/ })).toHaveTextContent("A-1");
  });

  it("checks identity: a new student", async () => {
    mocks.lookupAdmission.mockResolvedValue({ match: "none" });
    renderWithClient(<AdmissionScreen />);
    await fillIdentity();
    await userEvent.click(screen.getByRole("button", { name: /Check if they already have an account/ }));
    expect(await screen.findByText(/new student record will be created/)).toBeInTheDocument();
    expect(mocks.lookupAdmission).toHaveBeenCalledWith({ phone: "9123456780" });
  });

  it("checks identity: an existing account is shown masked and flagged to confirm", async () => {
    mocks.lookupAdmission.mockResolvedValue({
      match: "existing",
      student: { id: "u1", name: "Asha Verma", masked_phone: "+91******6780", masked_email: "a***@example.com", is_offline: false, is_member_here: false },
    });
    renderWithClient(<AdmissionScreen />);
    await fillIdentity();
    await userEvent.click(screen.getByRole("button", { name: /Check if they already have an account/ }));
    expect(await screen.findByText("This student already has an account")).toBeInTheDocument();
    expect(screen.getByText(/\+91\*{6}6780/)).toBeInTheDocument();
    expect(screen.queryByText(/9123456780/)).not.toBeInTheDocument(); // the full number is never shown back
  });

  it("blocks admission for someone who is already a member here", async () => {
    mocks.lookupAdmission.mockResolvedValue({
      match: "existing",
      student: { id: "u1", name: "Asha Verma", masked_phone: "+91******6780", masked_email: null, is_offline: false, is_member_here: true },
    });
    renderWithClient(<AdmissionScreen />);
    await fillIdentity();
    await userEvent.click(screen.getByRole("button", { name: /Check if they already have an account/ }));
    expect(await screen.findByText("Already a member here")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Admit student and record payment" })).toBeDisabled();
  });

  it("blocks admission when the phone and email belong to different accounts", async () => {
    mocks.lookupAdmission.mockRejectedValue(new ApiError({ status: 409, code: "IDENTITY_CONFLICT", message: "x" }));
    renderWithClient(<AdmissionScreen />);
    await fillIdentity();
    await userEvent.click(screen.getByRole("button", { name: /Check if they already have an account/ }));
    expect(await screen.findByText(/belong to different accounts/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Admit student and record payment" })).toBeDisabled();
  });

  it("says why an owner account cannot be admitted instead of a generic error", async () => {
    const message = "Library owners cannot be admitted as students.";
    mocks.lookupAdmission.mockRejectedValue(new ApiError({ status: 409, code: "CONFLICT", message, requestId: "r1" }));
    renderWithClient(<AdmissionScreen />);
    await fillIdentity();
    await userEvent.click(screen.getByRole("button", { name: /Check if they already have an account/ }));
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.queryByText(/went wrong/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Admit student and record payment" })).toBeDisabled();
  });

  it("shows the reason when the server refuses the admission with a conflict", async () => {
    const message = "Library owners cannot be admitted as students.";
    mocks.admitStudent.mockRejectedValue(new ApiError({ status: 409, code: "CONFLICT", message, requestId: "r1" }));
    renderWithClient(<AdmissionScreen />);
    await fillIdentity();
    await choose(/Seat/, "A-1");
    await choose(/Plan/, /Monthly/);
    await userEvent.click(screen.getByRole("button", { name: "Admit student and record payment" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.queryByText(/went wrong/i)).not.toBeInTheDocument();
  });

  it("validates before sending anything", async () => {
    renderWithClient(<AdmissionScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Admit student and record payment" }));
    expect(await screen.findByText("Enter the student's name.")).toBeInTheDocument();
    expect(screen.getByText("Enter a valid Indian mobile number.")).toBeInTheDocument();
    expect(screen.getByText("Choose a seat.")).toBeInTheDocument();
    expect(mocks.admitStudent).not.toHaveBeenCalled();
  });

  it("admits the student with the chosen seat, plan and method, and shows the receipt", async () => {
    mocks.admitStudent.mockResolvedValue({
      student: { id: "u9", name: "Ravi Kumar", is_offline: true, created: true },
      membership: member({ membership_id: "m9", seat: { id: "s1", label: "A-1" }, next_due_date: "2026-11-17" }),
      payment: { id: "pay9", receipt_number: "LH-2026-000009", purpose: "new_membership", channel: "offline", method: "cash", amount: "1200.00", plan: "Monthly", period_start: "2026-10-18", period_end: "2026-11-17", paid_at: null },
    });
    renderWithClient(<AdmissionScreen />);
    await fillIdentity();
    await choose(/Seat/, "A-1");
    await choose(/Plan/, /Monthly/);
    await userEvent.click(screen.getByRole("button", { name: "Admit student and record payment" }));
    await waitFor(() => expect(mocks.admitStudent).toHaveBeenCalledTimes(1));
    expect(mocks.admitStudent).toHaveBeenCalledWith({
      student: { name: "Ravi Kumar", phone: "9123456780" },
      seat_id: "s1",
      plan_id: "p1",
      payment: { method: "cash" },
    });
    expect(await screen.findByText("Ravi Kumar is admitted")).toBeInTheDocument();
    expect(screen.getByText(/receipt LH-2026-000009/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View member" })).toHaveAttribute("href", "/owner/members/m9");
  });

  it("puts a seat conflict on the seat field and lets the owner choose again", async () => {
    mocks.admitStudent.mockRejectedValue(new ApiError({ status: 409, code: "SEAT_UNAVAILABLE", message: "x" }));
    renderWithClient(<AdmissionScreen />);
    await fillIdentity();
    await choose(/Seat/, "A-1");
    await choose(/Plan/, /Monthly/);
    await userEvent.click(screen.getByRole("button", { name: "Admit student and record payment" }));
    expect(await screen.findByText("That seat was just taken. Please pick another.")).toBeInTheDocument();
    expect(screen.queryByText("Ravi Kumar is admitted")).not.toBeInTheDocument();
  });
});

describe("MemberDetailScreen", () => {
  beforeEach(() => mocks.fetchMember.mockResolvedValue(detail()));

  it("shows the member, their period history and the actions", async () => {
    const { container } = renderWithClient(<MemberDetailScreen id="m1" />);
    expect(await screen.findByRole("heading", { level: 1, name: "Asha Verma" })).toBeInTheDocument();
    expect(screen.getAllByText("LH-2026-000001").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Record a renewal" })).toBeInTheDocument();
    expect(screen.getByText("Days present this month").nextSibling).toHaveTextContent("4");
    expect(screen.getByText("Complaints raised").nextSibling).toHaveTextContent("1");
    await expectNoAxeViolations(container);
  });

  it("archives only with a reason and reports success", async () => {
    mocks.archiveMember.mockResolvedValue(member({ status: "archived" }));
    renderWithClient(<MemberDetailScreen id="m1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Archive member" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Archive member" }));
    expect(await within(dialog).findByText(/Enter at least 3 characters/)).toBeInTheDocument();
    expect(mocks.archiveMember).not.toHaveBeenCalled();
    await userEvent.type(within(dialog).getByRole("textbox"), "Left the city");
    await userEvent.click(within(dialog).getByRole("button", { name: "Archive member" }));
    await waitFor(() => expect(mocks.archiveMember).toHaveBeenCalledWith("m1", "Left the city"));
  });

  it("records a renewal for the current plan without a plan id or amount", async () => {
    mocks.recordRenewal.mockResolvedValue({ payment: { receipt_number: "LH-2026-000002" }, membership: member() });
    renderWithClient(<MemberDetailScreen id="m1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Record a renewal" }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText(/Amount to record/)).toHaveTextContent("₹1,200");
    await userEvent.click(within(dialog).getByRole("button", { name: "Record renewal" }));
    await waitFor(() => expect(mocks.recordRenewal).toHaveBeenCalledWith("m1", { method: "cash" }));
  });

  it("sends the new plan id when the owner changes the plan", async () => {
    mocks.recordRenewal.mockResolvedValue({ payment: { receipt_number: "LH-2026-000002" }, membership: member() });
    renderWithClient(<MemberDetailScreen id="m1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Record a renewal" }));
    await choose(/^Plan/, /Quarterly/);
    await userEvent.click(screen.getByRole("button", { name: "Record renewal" }));
    await waitFor(() => expect(mocks.recordRenewal).toHaveBeenCalledWith("m1", { method: "cash", plan_id: "p2" }));
  });

  it("hides the actions for an ended membership", async () => {
    mocks.fetchMember.mockResolvedValue(detail({ status: "archived", archived_at: "2026-10-10T00:00:00Z", archive_reason: "Moved away" }));
    renderWithClient(<MemberDetailScreen id="m1" />);
    expect(await screen.findByText("Moved away")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Record a renewal" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Archive member" })).not.toBeInTheDocument();
  });

  it("explains a missing member and offers a retry for other errors", async () => {
    mocks.fetchMember.mockRejectedValueOnce(new ApiError({ status: 404, code: "NOT_FOUND", message: "x" }));
    const { unmount } = renderWithClient(<MemberDetailScreen id="nope" />);
    expect(await screen.findByText("We couldn't find this member")).toBeInTheDocument();
    unmount();
    mocks.fetchMember.mockRejectedValueOnce(new ApiError({ status: 500, code: "SERVER_ERROR", message: "x" }));
    mocks.fetchMember.mockResolvedValue(detail());
    renderWithClient(<MemberDetailScreen id="m1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Asha Verma" })).toBeInTheDocument();
  });
});

describe("MembersScreen", () => {
  it("lists members with their status and filters through the API", async () => {
    mocks.fetchMembers.mockResolvedValue(page([member(), member({ membership_id: "m2", student: { ...member().student, id: "u2", name: "Ravi Kumar", is_offline: true }, status: "overdue" })]));
    renderWithClient(<MembersScreen />);
    expect((await screen.findAllByRole("link", { name: "Asha Verma" }))[0]).toHaveAttribute("href", "/owner/members/m1");
    expect(screen.getAllByText("Overdue").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Added by you").length).toBeGreaterThan(0);
    await choose("Status", "Overdue");
    await waitFor(() => expect(mocks.fetchMembers).toHaveBeenLastCalledWith(expect.objectContaining({ status: "overdue", page: 1 })));
  });

  it("shows an empty state with a way forward", async () => {
    mocks.fetchMembers.mockResolvedValue(page([]));
    renderWithClient(<MembersScreen />);
    expect(await screen.findByText("No members yet")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Admit a student/ }).length).toBeGreaterThan(0);
  });

  it("shows a retryable error", async () => {
    mocks.fetchMembers.mockRejectedValueOnce(new ApiError({ status: 500, code: "SERVER_ERROR", message: "x" }));
    mocks.fetchMembers.mockResolvedValue(page([member()]));
    renderWithClient(<MembersScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Try again" }));
    expect((await screen.findAllByRole("link", { name: "Asha Verma" })).length).toBeGreaterThan(0);
  });
});

const due = (overrides: Partial<DueRow> = {}): DueRow => ({
  membership_id: "m1",
  student: { name: "Asha Verma", phone: "+919123456780" },
  seat_label: "A-1",
  plan: { id: "p1", name: "Monthly", price: "1200.00" },
  status: "overdue",
  next_due_date: "2026-10-12",
  days_overdue: 6,
  amount_due: "1200.00",
  ...overrides,
});

describe("DuesScreen", () => {
  it("lists dues with how late and the amount, and records a payment from the row", async () => {
    mocks.fetchDues.mockResolvedValue(page([due(), due({ membership_id: "m2", student: { name: "Ravi Kumar", phone: "+919123456781" }, status: "due", days_overdue: 0 })]));
    mocks.recordRenewal.mockResolvedValue({ payment: { receipt_number: "LH-1" }, membership: member() });
    renderWithClient(<DuesScreen />);
    expect(await screen.findByText("6 days overdue")).toBeInTheDocument();
    expect(screen.getAllByText("Due soon").length).toBeGreaterThan(0);
    await userEvent.click(screen.getAllByRole("button", { name: "Record payment for Asha Verma" })[0]!);
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByText(/Amount to record/);
    await userEvent.click(within(dialog).getByRole("button", { name: "Record renewal" }));
    // The row knows the member's plan, so paying from the dues list never changes it.
    await waitFor(() => expect(mocks.recordRenewal).toHaveBeenCalledWith("m1", { method: "cash" }));
  });

  it("filters by status and lateness", async () => {
    mocks.fetchDues.mockResolvedValue(page([due()]));
    renderWithClient(<DuesScreen />);
    await screen.findByText("6 days overdue");
    await choose("Show", "Overdue");
    await waitFor(() => expect(mocks.fetchDues).toHaveBeenLastCalledWith(expect.objectContaining({ status: "overdue" })));
    await choose("How late", /8–15/);
    await waitFor(() => expect(mocks.fetchDues).toHaveBeenLastCalledWith(expect.objectContaining({ status: "overdue", bucket: "8-15" })));
  });

  it("celebrates an empty list", async () => {
    mocks.fetchDues.mockResolvedValue(page([]));
    renderWithClient(<DuesScreen />);
    expect(await screen.findByText("Nothing is due")).toBeInTheDocument();
  });
});

const payment = (overrides: Partial<OwnerPayment> = {}): OwnerPayment => ({
  id: "pay1",
  library: { id: "lib1", name: "Silent Hive" },
  purpose: "new_membership",
  method: "cash",
  amount: "1200.00",
  status: "success",
  receipt_number: "LH-2026-000001",
  period_start: "2026-10-01",
  period_end: "2026-10-31",
  paid_at: "2026-10-01T05:00:00Z",
  created_at: "2026-10-01T05:00:00Z",
  channel: "offline",
  student: { id: "u1", name: "Asha Verma", phone: "+919123456780" },
  recorded_by: { name: "Owner" },
  ...overrides,
});

describe("OwnerPaymentsScreen", () => {
  it("lists payments, filters by status and opens the details", async () => {
    mocks.fetchOwnerPayments.mockResolvedValue(page([payment(), payment({ id: "pay2", receipt_number: "LH-2026-000002", status: "needs_refund", method: "gateway", channel: "online" })]));
    mocks.fetchOwnerPayment.mockResolvedValue({ ...payment(), plan_name: "Monthly", seat_label: "A-1", failure_reason: "", notes: "UPI ref 123" });
    renderWithClient(<OwnerPaymentsScreen />);
    expect(await screen.findAllByText("Refund due")).not.toHaveLength(0);
    await choose("Status", "Paid");
    await waitFor(() => expect(mocks.fetchOwnerPayments).toHaveBeenLastCalledWith(expect.objectContaining({ status: "success" })));
    await userEvent.click(screen.getAllByRole("button", { name: "Details of LH-2026-000001" })[0]!);
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("UPI ref 123")).toBeInTheDocument();
    expect(within(dialog).getByText(/recorded by Owner/)).toBeInTheDocument();
  });

  it("explains an empty ledger", async () => {
    mocks.fetchOwnerPayments.mockResolvedValue(page([]));
    renderWithClient(<OwnerPaymentsScreen />);
    expect(await screen.findByText("No payments match")).toBeInTheDocument();
  });
});

const dashboard = (overrides: Partial<OwnerDashboard> = {}): OwnerDashboard => ({
  seats: { total: 10, empty: 4, reserved: 1, occupied: 5, disabled: 0 },
  members: { active: 3, due: 1, overdue: 2 },
  today: { new_bookings: 1, check_ins: 4, present_now: 2 },
  upcoming_renewals_7d: 2,
  revenue: { this_month_total: "5200.00", by_method: { cash: { total: "5200.00", count: 4 } } },
  open_complaints: 3,
  pending_visits: 1,
  domain_breakdown: [{ code: "upsc", name: "UPSC", count: 3 }],
  publish_checklist: { has_profile: true, has_location: true, has_active_plan: true, has_active_seat: true },
  ...overrides,
});

describe("OwnerDashboardScreen", () => {
  it("shows the numbers and links each card to the list it counts", async () => {
    mocks.fetchOwnerDashboard.mockResolvedValue(dashboard());
    const { container } = renderWithClient(<OwnerDashboardScreen />);
    expect(await screen.findByText("₹5,200")).toBeInTheDocument();
    const link = (name: RegExp) => screen.getByRole("link", { name });
    expect(link(/Overdue/)).toHaveAttribute("href", "/owner/dues");
    expect(link(/Open complaints/)).toHaveAttribute("href", "/owner/complaints");
    expect(link(/Visit requests waiting/)).toHaveAttribute("href", "/owner/visits");
    expect(link(/In the library now/)).toHaveAttribute("href", "/owner/attendance");
    expect(link(/Revenue this month/)).toHaveAttribute("href", "/owner/payments");
    expect(screen.getByText(/5 taken · 1 reserved · 4 free · 10 seats/)).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("says what is missing before the library can go live", async () => {
    mocks.fetchOwnerDashboard.mockResolvedValue(dashboard({ publish_checklist: { has_profile: true, has_location: false, has_active_plan: false, has_active_seat: true } }));
    renderWithClient(<OwnerDashboardScreen />);
    expect(await screen.findByText(/Still to do: location, an active plan/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Finish setup" })).toHaveAttribute("href", "/owner/library");
  });

  it("invites the owner to add seats when there are none", async () => {
    mocks.fetchOwnerDashboard.mockResolvedValue(dashboard({ seats: { total: 0, empty: 0, reserved: 0, occupied: 0, disabled: 0 }, domain_breakdown: [], revenue: { this_month_total: "0", by_method: {} } }));
    renderWithClient(<OwnerDashboardScreen />);
    expect(await screen.findByText(/haven't added any seats yet/)).toBeInTheDocument();
    expect(screen.getByText("No payments this month.")).toBeInTheDocument();
  });

  it("shows a retryable error", async () => {
    mocks.fetchOwnerDashboard.mockRejectedValueOnce(new ApiError({ status: 500, code: "SERVER_ERROR", message: "x" }));
    mocks.fetchOwnerDashboard.mockResolvedValue(dashboard());
    renderWithClient(<OwnerDashboardScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Try again" }));
    expect(await screen.findByText("₹5,200")).toBeInTheDocument();
  });
});

describe("SeatManager", () => {
  it("shows actions that fit the selected seat's status", async () => {
    renderWithClient(<SeatManager />);
    await userEvent.click(await screen.findByRole("button", { name: "Seat A-1, free" }));
    const panel = screen.getByRole("complementary", { name: "Seat details" });
    expect(within(panel).getByRole("link", { name: "Admit a student" })).toHaveAttribute("href", "/owner/members/new?seat=s1");
    expect(within(panel).getByRole("button", { name: "Block seat" })).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Remove seat" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Seat A-2, taken" }));
    expect(within(panel).getByRole("link", { name: "Asha Verma" })).toHaveAttribute("href", "/owner/members/m1");
    expect(within(panel).queryByRole("button", { name: "Remove seat" })).not.toBeInTheDocument();
    expect(within(panel).queryByRole("button", { name: "Block seat" })).not.toBeInTheDocument();
  });

  it("blocks a seat only with a reason", async () => {
    mocks.placeManualHold.mockResolvedValue({ id: "h1" });
    renderWithClient(<SeatManager />);
    await userEvent.click(await screen.findByRole("button", { name: "Seat A-1, free" }));
    await userEvent.click(screen.getByRole("button", { name: "Block seat" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Block seat" }));
    expect(await within(dialog).findByText(/Enter at least 3 characters/)).toBeInTheDocument();
    expect(mocks.placeManualHold).not.toHaveBeenCalled();
    await userEvent.type(within(dialog).getByRole("textbox"), "Kept for Mr Singh");
    await userEvent.click(within(dialog).getByRole("button", { name: "Block seat" }));
    await waitFor(() => expect(mocks.placeManualHold).toHaveBeenCalledWith("s1", "Kept for Mr Singh"));
  });

  it("offers to release a hold and to end maintenance", async () => {
    mocks.fetchOwnerSeats.mockResolvedValue({
      seats: [
        seat({ id: "s1", label: "A-1", status: "reserved", hold: { id: "h1", kind: "owner_manual", reason: "Kept for Mr Singh" } }),
        seat({ id: "s2", label: "A-2", status: "disabled", is_disabled: true, disabled_reason: "Fan broken" }),
      ],
      counts: { total: 2, empty: 0, reserved: 1, occupied: 0 },
    });
    mocks.enableSeat.mockResolvedValue(seat());
    renderWithClient(<SeatManager />);
    await userEvent.click(await screen.findByRole("button", { name: "Seat A-1, reserved" }));
    expect(screen.getByText(/Blocked by you: Kept for Mr Singh/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Release hold" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Seat A-2, under maintenance" }));
    expect(screen.getByText(/Maintenance note: Fan broken/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "End maintenance" }));
    await waitFor(() => expect(mocks.enableSeat).toHaveBeenCalledWith("s2"));
  });

  it("asks owners with no seats to add some, with a grid", async () => {
    mocks.fetchOwnerSeats.mockResolvedValue({ seats: [], counts: { total: 0, empty: 0, reserved: 0, occupied: 0 } });
    mocks.addSeats.mockResolvedValue({ created: [seat()], skipped: [] });
    renderWithClient(<SeatManager />);
    expect(await screen.findByText("You haven't added any seats")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Add seats" })[0]!);
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add seats" }));
    await waitFor(() => expect(mocks.addSeats).toHaveBeenCalledWith({ mode: "grid", rows: ["A", "B", "C"], seats_per_row: 10 }));
  });

  it("refuses an oversized grid before calling the server", async () => {
    mocks.fetchOwnerSeats.mockResolvedValue({ seats: [], counts: { total: 0, empty: 0, reserved: 0, occupied: 0 } });
    renderWithClient(<SeatManager />);
    await userEvent.click((await screen.findAllByRole("button", { name: "Add seats" }))[0]!);
    const dialog = await screen.findByRole("dialog");
    const rows = within(dialog).getByLabelText("Rows");
    await userEvent.clear(rows);
    await userEvent.type(rows, Array.from({ length: 11 }, (_, i) => `R${i}`).join(", "));
    const perRow = within(dialog).getByLabelText("Seats per row");
    await userEvent.clear(perRow);
    await userEvent.type(perRow, "50");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add seats" }));
    expect(await within(dialog).findByText(/at most 500 seats/)).toBeInTheDocument();
    expect(mocks.addSeats).not.toHaveBeenCalled();
  });
});
