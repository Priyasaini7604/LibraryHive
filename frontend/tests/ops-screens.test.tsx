import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OwnerAttendanceScreen } from "@/components/attendance/owner-attendance-screen";
import { CheckInCard } from "@/components/attendance/check-in-card";
import { StudentAttendanceScreen } from "@/components/attendance/student-attendance-screen";
import { OwnerComplaintDetail, OwnerComplaintsScreen } from "@/components/complaints/owner-complaints";
import { StudentComplaintDetail, StudentComplaintsScreen } from "@/components/complaints/student-complaints";
import { NotificationBell } from "@/components/notifications/notification-bell";
import { NotificationsScreen, notificationTarget } from "@/components/notifications/notifications-screen";
import { ActivityScreen } from "@/components/owner/activity-screen";
import { OnboardingWizard } from "@/components/owner/onboarding-wizard";
import { ReportsScreen } from "@/components/owner/reports-screen";
import { StudentDashboardScreen } from "@/components/student/dashboard-screen";
import { MembershipsScreen } from "@/components/student/memberships-screen";
import { PaymentsScreen } from "@/components/student/payments-screen";
import { ReceiptScreen } from "@/components/student/receipt-screen";
import { OwnerVisitsScreen, StudentVisitsScreen } from "@/components/visits/visits-screens";
import { ApiError } from "@/lib/errors";
import type { AppNotification, AttendanceRecord, Complaint, OwnerComplaint, StudentMembership, Visit } from "@/lib/types";

import { expectNoAxeViolations } from "./axe";

// Radix selects and dialogs are slow to drive in jsdom on a busy machine; a generous limit avoids false failures.
vi.setConfig({ testTimeout: 20_000 });

const mocks = vi.hoisted(() => ({
  checkIn: vi.fn(),
  checkOut: vi.fn(),
  fetchCurrentAttendance: vi.fn(),
  fetchAttendanceHistory: vi.fn(),
  fetchLiveAttendance: vi.fn(),
  fetchOwnerAttendance: vi.fn(),
  ownerCheckOut: vi.fn(),
  correctAttendance: vi.fn(),
  raiseComplaint: vi.fn(),
  fetchStudentComplaints: vi.fn(),
  fetchStudentComplaint: vi.fn(),
  fetchOwnerComplaints: vi.fn(),
  fetchOwnerComplaint: vi.fn(),
  respondToComplaint: vi.fn(),
  fetchStudentVisits: vi.fn(),
  cancelVisit: vi.fn(),
  fetchOwnerVisits: vi.fn(),
  decideVisit: vi.fn(),
  fetchNotifications: vi.fn(),
  fetchUnreadCount: vi.fn(),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
  fetchStudentDashboard: vi.fn(),
  fetchOccupancyReport: vi.fn(),
  fetchRevenueReport: vi.fn(),
  fetchComplaintReport: vi.fn(),
  fetchDomainReport: vi.fn(),
  fetchAuditLog: vi.fn(),
  downloadExport: vi.fn(),
  fetchStudentMemberships: vi.fn(),
  fetchStudentPayments: vi.fn(),
  fetchStudentReceipt: vi.fn(),
  fetchOwnerLibrary: vi.fn(),
  fetchOwnerPlans: vi.fn(),
}));

vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ status: "authenticated", user: { name: "Asha Verma", role: "student" } }) }));
vi.mock("@/lib/api/operations", () => ({
  checkIn: mocks.checkIn,
  checkOut: mocks.checkOut,
  fetchCurrentAttendance: mocks.fetchCurrentAttendance,
  fetchAttendanceHistory: mocks.fetchAttendanceHistory,
  fetchLiveAttendance: mocks.fetchLiveAttendance,
  fetchOwnerAttendance: mocks.fetchOwnerAttendance,
  ownerCheckOut: mocks.ownerCheckOut,
  correctAttendance: mocks.correctAttendance,
  raiseComplaint: mocks.raiseComplaint,
  fetchStudentComplaints: mocks.fetchStudentComplaints,
  fetchStudentComplaint: mocks.fetchStudentComplaint,
  fetchOwnerComplaints: mocks.fetchOwnerComplaints,
  fetchOwnerComplaint: mocks.fetchOwnerComplaint,
  respondToComplaint: mocks.respondToComplaint,
  fetchStudentVisits: mocks.fetchStudentVisits,
  cancelVisit: mocks.cancelVisit,
  fetchOwnerVisits: mocks.fetchOwnerVisits,
  decideVisit: mocks.decideVisit,
  fetchNotifications: mocks.fetchNotifications,
  fetchUnreadCount: mocks.fetchUnreadCount,
  markNotificationRead: mocks.markNotificationRead,
  markAllNotificationsRead: mocks.markAllNotificationsRead,
  fetchStudentDashboard: mocks.fetchStudentDashboard,
  fetchOccupancyReport: mocks.fetchOccupancyReport,
  fetchRevenueReport: mocks.fetchRevenueReport,
  fetchComplaintReport: mocks.fetchComplaintReport,
  fetchDomainReport: mocks.fetchDomainReport,
  fetchAuditLog: mocks.fetchAuditLog,
  downloadExport: mocks.downloadExport,
}));
vi.mock("@/lib/api/memberships", () => ({ fetchStudentMemberships: mocks.fetchStudentMemberships }));
vi.mock("@/lib/api/payments", () => ({ fetchStudentPayments: mocks.fetchStudentPayments, fetchStudentReceipt: mocks.fetchStudentReceipt }));
vi.mock("@/lib/api/libraries", () => ({ fetchOwnerLibrary: mocks.fetchOwnerLibrary, fetchOwnerPlans: mocks.fetchOwnerPlans }));
vi.mock("@/components/owner/library-profile-form", () => ({ LibraryProfileForm: () => <div>Profile form</div> }));
vi.mock("@/components/owner/plans-panel", () => ({ PlansPanel: () => <div>Plans panel</div> }));
vi.mock("@/components/owner/photos-panel", () => ({ PhotosPanel: () => <div>Photos panel</div> }));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const page = <T,>(items: T[]) => ({ items, page: 1, page_size: 20, total: items.length });

beforeEach(() => {
  for (const mock of Object.values(mocks)) mock.mockReset();
});

async function choose(label: RegExp | string, option: RegExp | string) {
  await userEvent.click(await screen.findByRole("combobox", { name: label }));
  await userEvent.click(await screen.findByRole("option", { name: option }));
}

const membership = (overrides: Partial<StudentMembership> = {}): StudentMembership => ({
  id: "m1",
  library: { id: "lib1", name: "Silent Hive" },
  seat: { label: "A-1" },
  plan: { id: "p1", name: "Monthly", price: "1200.00", duration_days: 30 },
  source: "online",
  status: "active",
  start_date: "2026-10-01",
  next_due_date: "2026-10-31",
  days_to_due: 13,
  renewal_open: false,
  ...overrides,
});

const record = (overrides: Partial<AttendanceRecord> = {}): AttendanceRecord => ({
  id: "r1",
  library: { id: "lib1", name: "Silent Hive" },
  seat_label: "A-1",
  date: "2026-10-18",
  check_in_at: "2026-10-18T04:00:00Z",
  check_out_at: null,
  duration_minutes: null,
  check_in_method: "self",
  check_out_method: null,
  status: "open",
  ...overrides,
});

describe("CheckInCard", () => {
  it("offers a check-in per library and checks the student in", async () => {
    mocks.fetchCurrentAttendance.mockResolvedValue(null);
    mocks.fetchStudentMemberships.mockResolvedValue([membership()]);
    mocks.checkIn.mockResolvedValue(record());
    renderWithClient(<CheckInCard />);
    await userEvent.click(await screen.findByRole("button", { name: /Check in at Silent Hive/ }));
    await waitFor(() => expect(mocks.checkIn).toHaveBeenCalledWith("lib1"));
  });

  it("shows check-out while checked in", async () => {
    mocks.fetchCurrentAttendance.mockResolvedValue(record());
    mocks.fetchStudentMemberships.mockResolvedValue([membership()]);
    mocks.checkOut.mockResolvedValue(record({ status: "closed" }));
    renderWithClient(<CheckInCard />);
    expect(await screen.findByText(/You're checked in at/)).toHaveTextContent("Silent Hive");
    expect(screen.queryByRole("button", { name: /Check in at/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Check out/ }));
    await waitFor(() => expect(mocks.checkOut).toHaveBeenCalledTimes(1));
  });

  it("explains that check-in needs a seat", async () => {
    mocks.fetchCurrentAttendance.mockResolvedValue(null);
    mocks.fetchStudentMemberships.mockResolvedValue([membership({ status: "archived" })]);
    renderWithClient(<CheckInCard />);
    expect(await screen.findByText(/Check-in is available once you have a seat/)).toBeInTheDocument();
  });

  it("tells the student when the server refuses the check-in", async () => {
    mocks.fetchCurrentAttendance.mockResolvedValue(null);
    mocks.fetchStudentMemberships.mockResolvedValue([membership()]);
    mocks.checkIn.mockRejectedValue(new ApiError({ status: 409, code: "ALREADY_CHECKED_IN", message: "x" }));
    renderWithClient(<CheckInCard />);
    await userEvent.click(await screen.findByRole("button", { name: /Check in at Silent Hive/ }));
    await waitFor(() => expect(mocks.fetchCurrentAttendance.mock.calls.length).toBeGreaterThan(1)); // re-read the truth
  });
});

describe("attendance screens", () => {
  it("shows the student's month with a summary", async () => {
    mocks.fetchCurrentAttendance.mockResolvedValue(null);
    mocks.fetchStudentMemberships.mockResolvedValue([membership()]);
    mocks.fetchAttendanceHistory.mockResolvedValue({
      ...page([record({ status: "closed", check_out_at: "2026-10-18T07:30:00Z", duration_minutes: 210 })]),
      summary: { days_present: 5, total_minutes: 750 },
    });
    renderWithClient(<StudentAttendanceScreen />);
    expect(await screen.findByText("12 h 30 min")).toBeInTheDocument();
    expect(screen.getAllByText("3 h 30 min").length).toBeGreaterThan(0);
    expect(mocks.fetchAttendanceHistory).toHaveBeenCalledWith(expect.objectContaining({ month: expect.stringMatching(/^\d{4}-\d{2}$/) }));
  });

  it("lists who is in and lets the owner check them out", async () => {
    mocks.fetchLiveAttendance.mockResolvedValue([{ record_id: "r1", student: { id: "u1", name: "Asha Verma" }, seat_label: "A-1", check_in_at: "2026-10-18T04:00:00Z" }]);
    mocks.fetchOwnerAttendance.mockResolvedValue(page([]));
    mocks.ownerCheckOut.mockResolvedValue({});
    renderWithClient(<OwnerAttendanceScreen />);
    expect(await screen.findByText("In the library now (1)")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Check out Asha Verma" }));
    await waitFor(() => expect(mocks.ownerCheckOut).toHaveBeenCalledWith("r1"));
    expect(await screen.findByText("No attendance recorded")).toBeInTheDocument();
  });

  it("corrects a record only with a reason", async () => {
    mocks.fetchLiveAttendance.mockResolvedValue([]);
    mocks.fetchOwnerAttendance.mockResolvedValue(page([{ ...record({ status: "closed", check_out_at: "2026-10-18T07:00:00Z", duration_minutes: 180 }), student: { id: "u1", name: "Asha Verma" } }]));
    mocks.correctAttendance.mockResolvedValue({});
    renderWithClient(<OwnerAttendanceScreen />);
    await userEvent.click((await screen.findAllByRole("button", { name: "Correct Asha Verma's times" }))[0]!);
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save correction" }));
    expect(await within(dialog).findByText(/Enter a reason of at least 3 characters/)).toBeInTheDocument();
    expect(mocks.correctAttendance).not.toHaveBeenCalled();
    await userEvent.type(within(dialog).getByLabelText(/Reason/), "Forgot to tap");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save correction" }));
    await waitFor(() => expect(mocks.correctAttendance).toHaveBeenCalledWith("r1", expect.objectContaining({ reason: "Forgot to tap", check_in_at: expect.any(String), check_out_at: expect.any(String) })));
  });
});

const complaint = (overrides: Partial<Complaint> = {}): Complaint => ({
  id: "c1",
  library: { id: "lib1", name: "Silent Hive" },
  category: "ac",
  description: "The air conditioning on the second floor has not worked for three days.",
  status: "open",
  owner_response: "",
  responded_at: null,
  resolved_at: null,
  created_at: "2026-10-17T05:00:00Z",
  ...overrides,
});
const ownerComplaint = (overrides: Partial<OwnerComplaint> = {}): OwnerComplaint => ({ ...complaint(), student: { id: "u1", name: "Asha Verma" }, seat_label: "A-1", ...overrides });

describe("complaints", () => {
  it("lets a member raise a complaint and checks the text first", { timeout: 30_000 }, async () => {
    mocks.fetchStudentComplaints.mockResolvedValue(page([]));
    mocks.fetchStudentMemberships.mockResolvedValue([membership()]);
    mocks.raiseComplaint.mockResolvedValue(complaint());
    renderWithClient(<StudentComplaintsScreen />);
    expect(await screen.findByText("No complaints")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: /Raise a complaint/ })[0]!);
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Send complaint" }));
    expect(await within(dialog).findByText("Choose what this is about.")).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("combobox", { name: /About/ }));
    await userEvent.click(await screen.findByRole("option", { name: "Air conditioning" }));
    await userEvent.type(within(dialog).getByRole("textbox"), "short");
    await userEvent.click(within(dialog).getByRole("button", { name: "Send complaint" }));
    expect(await within(dialog).findByText(/at least 10 characters/)).toBeInTheDocument();
    expect(mocks.raiseComplaint).not.toHaveBeenCalled();
    await userEvent.type(within(dialog).getByRole("textbox"), " — it is very hot by afternoon");
    await userEvent.click(within(dialog).getByRole("button", { name: "Send complaint" }));
    await waitFor(() => expect(mocks.raiseComplaint).toHaveBeenCalledWith({ library_id: "lib1", category: "ac", description: "short — it is very hot by afternoon" }));
  });

  it("lists the student's complaints with status and shows the owner's reply", async () => {
    mocks.fetchStudentComplaints.mockResolvedValue(page([complaint({ status: "resolved", owner_response: "Fixed on Monday", resolved_at: "2026-10-18T05:00:00Z" })]));
    const { unmount } = renderWithClient(<StudentComplaintsScreen />);
    expect(await screen.findByText("Resolved")).toBeInTheDocument();
    unmount();
    mocks.fetchStudentComplaint.mockResolvedValue(complaint({ status: "resolved", owner_response: "Fixed on Monday", responded_at: "2026-10-18T05:00:00Z", resolved_at: "2026-10-18T05:00:00Z" }));
    const { container } = renderWithClient(<StudentComplaintDetail id="c1" />);
    expect(await screen.findByText("Fixed on Monday")).toBeInTheDocument();
    expect(screen.getByText("Reply from Silent Hive")).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("tells the student when nobody has replied yet", async () => {
    mocks.fetchStudentComplaint.mockResolvedValue(complaint());
    renderWithClient(<StudentComplaintDetail id="c1" />);
    expect(await screen.findByText(/hasn't replied yet/)).toBeInTheDocument();
  });

  it("filters the owner's inbox", async () => {
    mocks.fetchOwnerComplaints.mockResolvedValue(page([ownerComplaint()]));
    renderWithClient(<OwnerComplaintsScreen />);
    expect((await screen.findAllByRole("link", { name: "Air conditioning" }))[0]).toHaveAttribute("href", "/owner/complaints/c1");
    await choose("Status", "Open");
    await waitFor(() => expect(mocks.fetchOwnerComplaints).toHaveBeenLastCalledWith(expect.objectContaining({ status: "open", page: 1 })));
  });

  it("will not resolve without a reply, then resolves with one", async () => {
    mocks.fetchOwnerComplaint.mockResolvedValue(ownerComplaint());
    mocks.respondToComplaint.mockResolvedValue(ownerComplaint({ status: "resolved", owner_response: "Fixed", resolved_at: "2026-10-18T05:00:00Z" }));
    renderWithClient(<OwnerComplaintDetail id="c1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Resolve" }));
    expect(await screen.findByText("Write a reply before resolving.")).toBeInTheDocument();
    expect(mocks.respondToComplaint).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText(/Your reply/), "Fixed");
    await userEvent.click(screen.getByRole("button", { name: "Resolve" }));
    await waitFor(() => expect(mocks.respondToComplaint).toHaveBeenCalledWith("c1", { status: "resolved", owner_response: "Fixed" }));
    expect((await screen.findAllByText("Resolved")).length).toBeGreaterThan(0);
  });

  it("can mark in progress and offers no controls once resolved", async () => {
    mocks.fetchOwnerComplaint.mockResolvedValue(ownerComplaint());
    mocks.respondToComplaint.mockResolvedValue(ownerComplaint({ status: "in_progress" }));
    const { unmount } = renderWithClient(<OwnerComplaintDetail id="c1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Mark in progress" }));
    await waitFor(() => expect(mocks.respondToComplaint).toHaveBeenCalledWith("c1", { status: "in_progress" }));
    unmount();
    mocks.fetchOwnerComplaint.mockResolvedValue(ownerComplaint({ status: "resolved", owner_response: "Done", resolved_at: "2026-10-18T05:00:00Z" }));
    renderWithClient(<OwnerComplaintDetail id="c1" />);
    expect(await screen.findByText("Done")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Resolve" })).not.toBeInTheDocument();
  });
});

const visit = (overrides: Partial<Visit> = {}): Visit => ({
  id: "v1",
  library: { id: "lib1", name: "Silent Hive" },
  preferred_date: "2026-10-25",
  preferred_slot: "morning",
  student_note: "",
  status: "pending",
  owner_note: "",
  decided_at: null,
  created_at: "2026-10-18T05:00:00Z",
  ...overrides,
});

describe("visits", () => {
  it("lets the student cancel a pending request after confirming", async () => {
    mocks.fetchStudentVisits.mockResolvedValue(page([visit(), visit({ id: "v2", status: "accepted", owner_note: "Come at 10" })]));
    mocks.cancelVisit.mockResolvedValue(visit({ status: "cancelled" }));
    renderWithClient(<StudentVisitsScreen />);
    expect(await screen.findByText("Library says: Come at 10")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Cancel your visit request/ })).toHaveLength(1); // only the pending one
    await userEvent.click(screen.getByRole("button", { name: /Cancel your visit request/ }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Cancel request" }));
    await waitFor(() => expect(mocks.cancelVisit).toHaveBeenCalledWith("v1"));
  });

  it("shows how to get started when there are none", async () => {
    mocks.fetchStudentVisits.mockResolvedValue(page([]));
    renderWithClient(<StudentVisitsScreen />);
    expect(await screen.findByText("No visit requests")).toBeInTheDocument();
  });

  it("lets the owner accept with a note, and decline", async () => {
    const owned = { ...visit(), student: { id: "u1", name: "Asha Verma", phone: "+919123456780" } };
    mocks.fetchOwnerVisits.mockResolvedValue(page([owned]));
    mocks.decideVisit.mockResolvedValue(owned);
    renderWithClient(<OwnerVisitsScreen />);
    expect(mocks.fetchOwnerVisits).toHaveBeenCalledWith(expect.objectContaining({ status: "pending" })); // starts on what needs a decision
    await userEvent.click((await screen.findAllByRole("button", { name: "Accept Asha Verma's visit" }))[0]!);
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByRole("textbox"), "Come at 10");
    await userEvent.click(within(dialog).getByRole("button", { name: "Accept visit" }));
    await waitFor(() => expect(mocks.decideVisit).toHaveBeenCalledWith("v1", { decision: "accept", owner_note: "Come at 10" }));
  });

  it("declines without a note", async () => {
    const owned = { ...visit(), student: { id: "u1", name: "Asha Verma", phone: "+919123456780" } };
    mocks.fetchOwnerVisits.mockResolvedValue(page([owned]));
    mocks.decideVisit.mockResolvedValue(owned);
    renderWithClient(<OwnerVisitsScreen />);
    await userEvent.click((await screen.findAllByRole("button", { name: "Decline Asha Verma's visit" }))[0]!);
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Decline visit" }));
    await waitFor(() => expect(mocks.decideVisit).toHaveBeenCalledWith("v1", { decision: "reject" }));
  });
});

const notification = (overrides: Partial<AppNotification> = {}): AppNotification => ({
  id: "n1",
  type: "booking_confirmed",
  title: "Your seat is booked",
  body: "Seat A-1 is yours.",
  entity_type: "membership",
  entity_id: "m1",
  created_at: "2026-10-18T05:00:00Z",
  read_at: null,
  ...overrides,
});

describe("notifications", () => {
  it("maps each notification to the right page for the student and the owner", () => {
    expect(notificationTarget(notification(), "student")).toBe("/student/memberships/m1");
    expect(notificationTarget(notification({ entity_type: "payment", entity_id: "p1" }), "student")).toBe("/student/payments/p1");
    expect(notificationTarget(notification({ entity_type: "complaint", entity_id: "c1" }), "owner")).toBe("/owner/complaints/c1");
    expect(notificationTarget(notification({ entity_type: "visit", entity_id: "v1" }), "owner")).toBe("/owner/visits");
    expect(notificationTarget(notification({ entity_type: "library", entity_id: "l1" }), "student")).toBe("/libraries/l1");
    expect(notificationTarget(notification({ entity_type: "library", entity_id: "l1" }), "owner")).toBe("/owner/dues");
    expect(notificationTarget(notification({ entity_type: "library", entity_id: "l1" }), "owner")).toBe("/owner/dues");
    expect(notificationTarget(notification({ entity_type: null, entity_id: null }), "student")).toBeNull();
    expect(notificationTarget(notification({ entity_type: "unknown", entity_id: "x" }), "student")).toBeNull();
  });

  it("lists notifications, marks one read and marks all read", async () => {
    mocks.fetchNotifications.mockResolvedValue(page([notification(), notification({ id: "n2", title: "Old news", read_at: "2026-10-17T05:00:00Z" })]));
    mocks.markNotificationRead.mockResolvedValue(notification({ read_at: "now" }));
    mocks.markAllNotificationsRead.mockResolvedValue({ updated: 1 });
    const { container } = renderWithClient(<NotificationsScreen viewer="student" />);
    expect(await screen.findByText("Your seat is booked")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Mark ".*" as read/ })).toHaveLength(1); // only the unread one
    await userEvent.click(screen.getByRole("button", { name: /Mark "Your seat is booked" as read/ }));
    await waitFor(() => expect(mocks.markNotificationRead).toHaveBeenCalledWith("n1"));
    await userEvent.click(screen.getByRole("button", { name: /Mark all as read/ }));
    await waitFor(() => expect(mocks.markAllNotificationsRead).toHaveBeenCalledTimes(1));
    await expectNoAxeViolations(container);
  });

  it("asks only for unread notifications when filtered", async () => {
    mocks.fetchNotifications.mockResolvedValue(page([]));
    renderWithClient(<NotificationsScreen viewer="owner" />);
    expect(await screen.findByText("No notifications yet")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: "Show unread only" }));
    await waitFor(() => expect(mocks.fetchNotifications).toHaveBeenLastCalledWith(expect.objectContaining({ unread: true })));
    expect(await screen.findByText("Nothing unread")).toBeInTheDocument();
  });

  it("shows the unread count on the bell", async () => {
    mocks.fetchUnreadCount.mockResolvedValue(3);
    renderWithClient(<NotificationBell href="/student/notifications" />);
    const link = await screen.findByRole("link", { name: "Notifications, 3 unread" });
    expect(link).toHaveAttribute("href", "/student/notifications");
  });

  it("shows a plain bell when everything is read, and caps big numbers", async () => {
    mocks.fetchUnreadCount.mockResolvedValue(0);
    const { unmount } = renderWithClient(<NotificationBell href="/owner/notifications" />);
    expect(await screen.findByRole("link", { name: "Notifications" })).toBeInTheDocument();
    unmount();
    mocks.fetchUnreadCount.mockResolvedValue(250);
    renderWithClient(<NotificationBell href="/owner/notifications" />);
    expect(await screen.findByText("99+")).toBeInTheDocument();
  });
});

describe("student pages", () => {
  it("shows the dashboard sections, with the booking in progress first", async () => {
    mocks.fetchStudentDashboard.mockResolvedValue({
      memberships: [membership({ renewal_open: true, status: "due" })],
      current_attendance: null,
      recent_payments: [{ id: "pay1", library: { id: "lib1", name: "Silent Hive" }, purpose: "renewal", method: "gateway", amount: "1200.00", status: "success", receipt_number: "LH-1", period_start: null, period_end: null, paid_at: "2026-10-01T05:00:00Z", created_at: "2026-10-01T05:00:00Z" }],
      open_complaints: 2,
      visits: [{ id: "v1", library: { id: "lib2", name: "Calm Corner" }, preferred_date: "2026-10-25", preferred_slot: "evening", status: "pending" }],
      pending_hold: { id: "h1", library: { id: "lib1", name: "Silent Hive" }, seat_label: "B-4", plan: { id: "p1", name: "Monthly" }, expires_at: "2026-10-18T06:00:00Z" },
    });
    mocks.fetchCurrentAttendance.mockResolvedValue(null);
    mocks.fetchStudentMemberships.mockResolvedValue([membership()]);
    const { container } = renderWithClient(<StudentDashboardScreen />);
    expect(await screen.findByRole("heading", { level: 1, name: "Hello, Asha" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Continue your booking" })).toHaveAttribute("href", "/student/book/h1");
    expect(screen.getByRole("link", { name: "Renew" })).toHaveAttribute("href", "/student/memberships/m1/renew");
    expect(screen.getByRole("link", { name: /Open complaints/ })).toHaveAttribute("href", "/student/complaints");
    expect(screen.getByText(/Calm Corner/)).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("guides a student with nothing yet to find a library", async () => {
    mocks.fetchStudentDashboard.mockResolvedValue({ memberships: [], current_attendance: null, recent_payments: [], open_complaints: 0, visits: [], pending_hold: null });
    renderWithClient(<StudentDashboardScreen />);
    expect(await screen.findByText("You don't have a seat yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Find a library" })).toHaveAttribute("href", "/discover");
    expect(screen.getByText("No payments yet.")).toBeInTheDocument();
  });

  it("lists memberships, with past ones only on request", async () => {
    mocks.fetchStudentMemberships.mockResolvedValue([membership({ renewal_open: true })]);
    renderWithClient(<MembershipsScreen />);
    expect(await screen.findByRole("link", { name: "Renew" })).toBeInTheDocument();
    expect(mocks.fetchStudentMemberships).toHaveBeenLastCalledWith(false);
    await userEvent.click(screen.getByRole("checkbox", { name: "Show past memberships" }));
    await waitFor(() => expect(mocks.fetchStudentMemberships).toHaveBeenLastCalledWith(true));
  });

  it("lists payments with receipts only for paid ones", async () => {
    const base = { library: { id: "lib1", name: "Silent Hive" }, purpose: "new_membership" as const, method: "gateway" as const, amount: "1200.00", period_start: null, period_end: null, paid_at: null, created_at: "2026-10-01T05:00:00Z" };
    mocks.fetchStudentPayments.mockResolvedValue(page([{ ...base, id: "a", status: "success" as const, receipt_number: "LH-A" }, { ...base, id: "b", status: "pending" as const, receipt_number: "LH-B" }]));
    renderWithClient(<PaymentsScreen />);
    expect((await screen.findAllByRole("link", { name: "Receipt LH-A" }))[0]).toHaveAttribute("href", "/student/payments/a");
    expect(screen.queryByRole("link", { name: "Receipt LH-B" })).not.toBeInTheDocument();
  });

  it("shows a printable receipt and a refund notice when a payment needs one", async () => {
    mocks.fetchStudentReceipt.mockResolvedValue({
      id: "a", library: { id: "lib1", name: "Silent Hive" }, purpose: "new_membership", method: "gateway", amount: "1200.00", status: "needs_refund", receipt_number: "LH-2026-000007",
      period_start: null, period_end: null, paid_at: "2026-10-01T05:00:00Z", created_at: "2026-10-01T05:00:00Z",
      library_contact: { phone: "+919876543210", email: null, address: "12 Civil Lines" }, plan_name: "Monthly", seat_label: "A-1",
    });
    const { container } = renderWithClient(<ReceiptScreen id="a" />);
    expect(await screen.findByText("A refund is due to you")).toBeInTheDocument();
    expect(screen.getAllByText("LH-2026-000007").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /Print receipt/ })).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("says when a receipt doesn't exist", async () => {
    mocks.fetchStudentReceipt.mockRejectedValue(new ApiError({ status: 404, code: "NOT_FOUND", message: "x" }));
    renderWithClient(<ReceiptScreen id="nope" />);
    expect(await screen.findByText("We couldn't find this receipt")).toBeInTheDocument();
  });
});

describe("owner reports and activity", () => {
  beforeEach(() => {
    mocks.fetchOccupancyReport.mockResolvedValue({ counts: { total: 4, empty: 1, reserved: 1, occupied: 2 }, by_row: [{ row_label: "A", total: 4, occupied: 2, reserved: 1, empty: 1 }] });
    mocks.fetchRevenueReport.mockResolvedValue({ total: "3600.00", count: 3, by_method: { cash: { total: "2400.00", count: 2 }, gateway: { total: "1200.00", count: 1 } }, by_purpose: { renewal: { total: "3600.00", count: 3 } }, by_month: [{ month: "2026-10", total: "3600.00", count: 3 }] });
    mocks.fetchComplaintReport.mockResolvedValue({ by_status: { open: 2 }, by_category: { wifi: 2 } });
    mocks.fetchDomainReport.mockResolvedValue([{ code: "upsc", name: "UPSC", count: 3 }]);
  });

  it("shows every report with its numbers", async () => {
    const { container } = renderWithClient(<ReportsScreen />);
    expect(await screen.findByText("₹3,600")).toBeInTheDocument();
    expect(await screen.findByText(/2 taken · 1 reserved · 1 free/)).toBeInTheDocument();
    expect(await screen.findByText("Wi-Fi")).toBeInTheDocument();
    expect(await screen.findByText("UPSC")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Activity log" })).toHaveAttribute("href", "/owner/activity");
    await expectNoAxeViolations(container);
  });

  it("rejects an impossible revenue range before asking the server", async () => {
    renderWithClient(<ReportsScreen />);
    await screen.findByText("₹3,600");
    const calls = mocks.fetchRevenueReport.mock.calls.length;
    const from = screen.getByLabelText("From");
    await userEvent.clear(from);
    await userEvent.type(from, "2020-01-01");
    expect(await screen.findByRole("alert")).toHaveTextContent(/at most 366 days/);
    expect(mocks.fetchRevenueReport.mock.calls.length).toBe(calls);
  });

  it("downloads the members CSV", async () => {
    mocks.downloadExport.mockResolvedValue({ blob: new Blob(["x"]), filename: "members.csv" });
    const createObjectURL = vi.fn(() => "blob:x");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() }));
    renderWithClient(<ReportsScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Export members" }));
    await waitFor(() => expect(mocks.downloadExport).toHaveBeenCalledWith("members", undefined));
    await waitFor(() => expect(createObjectURL).toHaveBeenCalled());
    vi.unstubAllGlobals();
  });

  it("shows the activity log and filters it", async () => {
    mocks.fetchAuditLog.mockResolvedValue(page([{ id: "a1", created_at: "2026-10-18T05:00:00Z", actor: { name: "Owner", role: "owner" }, action: "membership.renew", entity_type: "membership", entity_id: "m1", changes: {}, reason: "" }]));
    renderWithClient(<ActivityScreen />);
    expect((await screen.findAllByText("Membership renew"))[0]).toHaveAttribute("title", "membership.renew");
    await userEvent.type(screen.getByLabelText("Action"), "attendance");
    await waitFor(() => expect(mocks.fetchAuditLog).toHaveBeenLastCalledWith(expect.objectContaining({ action: "attendance" })));
  });
});

describe("OnboardingWizard", () => {
  const library = (checklist: Partial<Record<string, boolean>>, published = false) => ({
    id: "lib1",
    name: "Silent Hive",
    is_published: published,
    publish_checklist: { has_profile: true, has_location: true, has_active_plan: false, has_active_seat: false, ...checklist },
  });

  it("starts at the library step for a new owner and can't skip it", async () => {
    mocks.fetchOwnerLibrary.mockResolvedValue(null);
    renderWithClient(<OnboardingWizard />);
    expect(await screen.findByText("Profile form")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("resumes at the first step that still needs work", async () => {
    mocks.fetchOwnerLibrary.mockResolvedValue(library({}));
    renderWithClient(<OnboardingWizard />);
    expect(await screen.findByText("Plans panel")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled(); // no plan yet
  });

  it("moves on once the step is done, treating photos as optional", async () => {
    mocks.fetchOwnerLibrary.mockResolvedValue(library({ has_active_plan: true }));
    renderWithClient(<OnboardingWizard />);
    expect(await screen.findByRole("heading", { name: "Seats" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(await screen.findByText("Photos panel")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue" })).toBeEnabled();
  });

  it("celebrates when the library is live", async () => {
    mocks.fetchOwnerLibrary.mockResolvedValue(library({ has_active_plan: true, has_active_seat: true }, true));
    renderWithClient(<OnboardingWizard />);
    expect(await screen.findByText("Your library is live")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to your dashboard" })).toHaveAttribute("href", "/owner");
    expect(screen.getByRole("link", { name: "View your public page" })).toHaveAttribute("href", "/libraries/lib1");
  });
});
