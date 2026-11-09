import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CheckoutScreen } from "@/components/booking/checkout-screen";
import { UpiPayPanel, cleanUtr } from "@/components/payments/upi-pay-panel";
import { UpiRequestsScreen } from "@/components/owner/upi-requests-screen";
import { UpiSettingsScreen } from "@/components/owner/upi-settings-screen";
import { StudentUpiRequestsScreen } from "@/components/student/upi-requests-screen";
import { ApiError } from "@/lib/errors";
import { buildCsp } from "@/lib/security/csp";
import type { OwnerUpiRequest, StudentHold, StudentUpiRequest, UpiPaymentInfo, UpiPaymentSettings } from "@/lib/types";

import { expectNoAxeViolations } from "./axe";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  fetchUpiInfo: vi.fn(),
  submitUpiRequest: vi.fn(),
  fetchStudentUpiRequests: vi.fn(),
  cancelUpiRequest: vi.fn(),
  fetchUpiSettings: vi.fn(),
  saveUpiSettings: vi.fn(),
  uploadUpiQr: vi.fn(),
  removeUpiQr: vi.fn(),
  fetchOwnerUpiRequests: vi.fn(),
  approveUpiRequest: vi.fn(),
  rejectUpiRequest: vi.fn(),
  fetchOwnerUpiScreenshot: vi.fn(),
  fetchOwnerSeats: vi.fn(),
  fetchCurrentHolds: vi.fn(),
  cancelHold: vi.fn(),
  createBookingOrder: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));
vi.mock("@/lib/api/upi", () => ({
  fetchUpiInfo: mocks.fetchUpiInfo,
  submitUpiRequest: mocks.submitUpiRequest,
  fetchStudentUpiRequests: mocks.fetchStudentUpiRequests,
  cancelUpiRequest: mocks.cancelUpiRequest,
  fetchUpiSettings: mocks.fetchUpiSettings,
  saveUpiSettings: mocks.saveUpiSettings,
  uploadUpiQr: mocks.uploadUpiQr,
  removeUpiQr: mocks.removeUpiQr,
  fetchOwnerUpiRequests: mocks.fetchOwnerUpiRequests,
  approveUpiRequest: mocks.approveUpiRequest,
  rejectUpiRequest: mocks.rejectUpiRequest,
  fetchOwnerUpiScreenshot: mocks.fetchOwnerUpiScreenshot,
}));
vi.mock("@/lib/api/seats", () => ({
  fetchOwnerSeats: mocks.fetchOwnerSeats,
  fetchCurrentHolds: mocks.fetchCurrentHolds,
  cancelHold: mocks.cancelHold,
}));
vi.mock("@/lib/api/payments", () => ({
  createBookingOrder: mocks.createBookingOrder,
  createRenewalOrder: vi.fn(),
  verifyPayment: vi.fn(),
  fetchStudentPayments: vi.fn(),
}));
vi.mock("@/lib/razorpay", () => ({ openCheckout: vi.fn() }));

const info: UpiPaymentInfo = {
  library: { id: "lib1", name: "Silent Hive", contact_phone: "+919000000001", contact_email: "hive@example.com" },
  upi_id: "silent.hive@okbank",
  instructions: "Write your name in the payment note.",
  qr_url: "http://127.0.0.1:8000/api/v1/files/private/token/",
  qr_url_expires_in: 600,
};

const studentRequest = (overrides: Partial<StudentUpiRequest> = {}): StudentUpiRequest => ({
  id: "r1",
  status: "pending",
  purpose: "new_membership",
  amount: "1200.00",
  utr: "UTR400012345678",
  student_note: "",
  has_screenshot: false,
  plan: { id: "p1", name: "Monthly", duration_days: 30 },
  seat: { id: "s1", label: "A-3" },
  created_at: "2026-11-08T06:30:00Z",
  waiting_hours: 1,
  overdue: false,
  reviewed_at: null,
  review_note: "",
  receipt_number: null,
  library: { id: "lib1", name: "Silent Hive", contact_phone: "+919000000001", contact_email: "hive@example.com" },
  can_cancel: true,
  ...overrides,
});

const ownerRequest = (overrides: Partial<OwnerUpiRequest> = {}): OwnerUpiRequest => {
  const { library: _library, can_cancel: _cancel, ...base } = studentRequest();
  return { ...base, student: { id: "u1", name: "Asha Rao", phone: "+919000000002" }, reviewed_by: null, ...overrides };
};

const page = <T,>(items: T[]) => ({ items, page: 1, page_size: 20, total: items.length });

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  Object.values(mocks).forEach((mock) => mock.mockReset());
});

describe("cleanUtr", () => {
  it("removes every space", () => {
    expect(cleanUtr(" 4000 1234\t5678 ")).toBe("400012345678");
  });
});

describe("UpiPayPanel (student)", () => {
  const renderPanel = () => renderWithClient(<UpiPayPanel libraryId="lib1" source={{ hold: "h1" }} amount="1200.00" />);

  it("shows the QR, the UPI ID, the amount and says plainly that sending a UTR confirms nothing", async () => {
    mocks.fetchUpiInfo.mockResolvedValue(info);
    renderPanel();
    expect(await screen.findByAltText("UPI QR code of Silent Hive")).toHaveAttribute("src", info.qr_url);
    expect(screen.getByText("silent.hive@okbank")).toBeInTheDocument();
    expect(screen.getByText("Write your name in the payment note.")).toBeInTheDocument();
    expect(screen.getAllByText(/₹1,200/).length).toBeGreaterThan(0);
    expect(screen.getByText(/does not confirm your payment/i)).toBeInTheDocument();
    expect(screen.getByText(/not to LibraryHive/i)).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    mocks.fetchUpiInfo.mockResolvedValue(info);
    const { container } = renderPanel();
    await screen.findByAltText("UPI QR code of Silent Hive");
    await expectNoAxeViolations(container);
  });

  it("asks for a fresh QR link at most twice when the image fails, then stops and offers a manual retry", async () => {
    let call = 0;
    mocks.fetchUpiInfo.mockImplementation(async () => ({ ...info, qr_url: `http://127.0.0.1:8000/api/v1/files/private/token-${++call}/` }));
    renderPanel();
    for (let failure = 1; failure <= 2; failure += 1) {
      fireEvent.error(await screen.findByAltText("UPI QR code of Silent Hive"));
      await waitFor(() => expect(mocks.fetchUpiInfo).toHaveBeenCalledTimes(failure + 1));
      await waitFor(() => expect(screen.getByAltText("UPI QR code of Silent Hive")).toHaveAttribute("src", expect.stringContaining(`token-${failure + 1}`)));
    }
    fireEvent.error(screen.getByAltText("UPI QR code of Silent Hive")); // the third failure
    expect(await screen.findByText("The QR code could not be loaded")).toBeInTheDocument();
    expect(screen.getByText(/Pay using the UPI ID shown here/)).toBeInTheDocument();
    expect(screen.queryByAltText("UPI QR code of Silent Hive")).not.toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(mocks.fetchUpiInfo).toHaveBeenCalledTimes(3); // 1 first load + 2 reloads, never more

    await userEvent.click(screen.getByRole("button", { name: "Load the QR code again" }));
    await waitFor(() => expect(mocks.fetchUpiInfo).toHaveBeenCalledTimes(4));
    expect(await screen.findByAltText("UPI QR code of Silent Hive")).toBeInTheDocument();
  });

  it("a QR that loads resets the retry allowance", async () => {
    let call = 0;
    mocks.fetchUpiInfo.mockImplementation(async () => ({ ...info, qr_url: `http://127.0.0.1:8000/api/v1/files/private/token-${++call}/` }));
    renderPanel();
    fireEvent.error(await screen.findByAltText("UPI QR code of Silent Hive"));
    await waitFor(() => expect(mocks.fetchUpiInfo).toHaveBeenCalledTimes(2));
    fireEvent.load(await screen.findByAltText("UPI QR code of Silent Hive"));
    for (let failure = 0; failure < 2; failure += 1) {
      fireEvent.error(await screen.findByAltText("UPI QR code of Silent Hive"));
      await waitFor(() => expect(mocks.fetchUpiInfo).toHaveBeenCalledTimes(3 + failure));
    }
    expect(screen.queryByText("The QR code could not be loaded")).not.toBeInTheDocument();
  });

  it("will not send a malformed UTR", async () => {
    mocks.fetchUpiInfo.mockResolvedValue(info);
    renderPanel();
    await screen.findByAltText("UPI QR code of Silent Hive");
    await userEvent.type(screen.getByLabelText(/Transaction reference/), "123");
    await userEvent.click(screen.getByRole("button", { name: /I have paid/ }));
    expect(await screen.findByText(/10 to 30 letters and digits/)).toBeInTheDocument();
    expect(mocks.submitUpiRequest).not.toHaveBeenCalled();
  });

  it("sends only the booking, the cleaned UTR and a note: never an amount, library or status", async () => {
    mocks.fetchUpiInfo.mockResolvedValue(info);
    mocks.submitUpiRequest.mockResolvedValue(studentRequest());
    renderPanel();
    await screen.findByAltText("UPI QR code of Silent Hive");
    await userEvent.type(screen.getByLabelText(/Transaction reference/), "utr 4000 1234 5678");
    await userEvent.type(screen.getByLabelText(/Note for the library/), "Paid from my father's phone");
    await userEvent.click(screen.getByRole("button", { name: /I have paid/ }));
    await waitFor(() => expect(mocks.submitUpiRequest).toHaveBeenCalledTimes(1));
    const [source, input] = mocks.submitUpiRequest.mock.calls[0] as [unknown, Record<string, unknown>];
    expect(source).toEqual({ hold: "h1" });
    expect(Object.keys(input).sort()).toEqual(["note", "screenshot", "utr"]);
    expect(input.utr).toBe("utr400012345678");
    expect(await screen.findByText("Request sent to the library")).toBeInTheDocument();
    expect(screen.getAllByText(/not confirmed yet/i).length).toBeGreaterThan(1);
  });

  it("sends the optional screenshot and refuses one that is too large", async () => {
    mocks.fetchUpiInfo.mockResolvedValue(info);
    mocks.submitUpiRequest.mockResolvedValue(studentRequest());
    renderPanel();
    await screen.findByAltText("UPI QR code of Silent Hive");
    await userEvent.type(screen.getByLabelText(/Transaction reference/), "UTR400012345678");

    const big = new File([new Uint8Array(6 * 1024 * 1024)], "big.png", { type: "image/png" });
    await userEvent.upload(screen.getByLabelText(/Payment screenshot/), big);
    await userEvent.click(screen.getByRole("button", { name: /I have paid/ }));
    expect(await screen.findByText(/5 MB or smaller/)).toBeInTheDocument();
    expect(mocks.submitUpiRequest).not.toHaveBeenCalled();

    const small = new File(["x"], "shot.png", { type: "image/png" });
    await userEvent.upload(screen.getByLabelText(/Payment screenshot/), small);
    await userEvent.click(screen.getByRole("button", { name: /I have paid/ }));
    await waitFor(() => expect(mocks.submitUpiRequest).toHaveBeenCalled());
    expect((mocks.submitUpiRequest.mock.calls[0] as [unknown, { screenshot: File }])[1].screenshot).toBe(small);
  });

  it("shows the server's message for a duplicate UTR and keeps the form", async () => {
    mocks.fetchUpiInfo.mockResolvedValue(info);
    mocks.submitUpiRequest.mockRejectedValue(new ApiError({ status: 409, code: "DUPLICATE_UTR", message: "dup" }));
    renderPanel();
    await screen.findByAltText("UPI QR code of Silent Hive");
    await userEvent.type(screen.getByLabelText(/Transaction reference/), "UTR400012345678");
    await userEvent.click(screen.getByRole("button", { name: /I have paid/ }));
    expect(await screen.findByText(/already been submitted/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Transaction reference/)).toHaveValue("UTR400012345678");
  });

  it("says UPI is unavailable instead of showing a broken page when the server refuses the details", async () => {
    mocks.fetchUpiInfo.mockRejectedValue(new ApiError({ status: 404, code: "NOT_FOUND", message: "no" }));
    renderPanel();
    expect(await screen.findByText(/UPI payment isn't available/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Try again/ })).not.toBeInTheDocument();
  });
});

describe("CheckoutScreen with direct UPI", () => {
  const hold = (upi: boolean): StudentHold => ({
    id: "h1",
    seat: { id: "s1", label: "A-3" },
    library: { id: "lib1", name: "Silent Hive", upi_enabled: upi },
    plan: { id: "p1", name: "Monthly", duration_days: 30, price: "1200.00" },
    amount: "1200.00",
    expires_at: new Date(Date.now() + 10 * 60_000).toISOString(),
  });

  it("offers the UPI panel, not the gateway button, when the library takes UPI", async () => {
    mocks.fetchCurrentHolds.mockResolvedValue([hold(true)]);
    mocks.fetchUpiInfo.mockResolvedValue(info);
    renderWithClient(<CheckoutScreen holdId="h1" />);
    expect(await screen.findByAltText("UPI QR code of Silent Hive")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Pay ₹/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel booking" })).toBeInTheDocument();
  });

  it("keeps the gateway button for a library that does not take UPI", async () => {
    mocks.fetchCurrentHolds.mockResolvedValue([hold(false)]);
    renderWithClient(<CheckoutScreen holdId="h1" />);
    expect(await screen.findByRole("button", { name: /^Pay ₹/ })).toBeInTheDocument();
    expect(mocks.fetchUpiInfo).not.toHaveBeenCalled();
  });
});

describe("review-time policy wording", () => {
  it("tells the student who has waited too long to contact the library or cancel, without implying a refund", async () => {
    mocks.fetchStudentUpiRequests.mockResolvedValue(page([studentRequest({ overdue: true, waiting_hours: 30 })]));
    renderWithClient(<StudentUpiRequestsScreen />);
    const note = await screen.findByText(/Still waiting after 30 hours/);
    expect(note).toHaveTextContent(/contact them directly/);
    expect(note).toHaveTextContent(/cancelling does not return any money you already paid/);
    expect(note.textContent).not.toMatch(/refunded|will be refunded/i);
    expect(screen.getByRole("button", { name: "Cancel this request" })).toBeInTheDocument();
  });

  it("says days once a request has waited two days or more, and says nothing for a fresh one", async () => {
    mocks.fetchStudentUpiRequests.mockResolvedValue(page([studentRequest({ overdue: true, waiting_hours: 80 })]));
    const first = renderWithClient(<StudentUpiRequestsScreen />);
    expect(await screen.findByText(/Still waiting after 3 days/)).toBeInTheDocument();
    first.unmount();
    mocks.fetchStudentUpiRequests.mockResolvedValue(page([studentRequest()]));
    renderWithClient(<StudentUpiRequestsScreen />);
    await screen.findByText("Waiting for the library");
    expect(screen.queryByText(/Still waiting after/)).not.toBeInTheDocument();
  });

  it("shows the owner how long each pending request has waited and flags overdue ones", async () => {
    mocks.fetchOwnerUpiRequests.mockResolvedValue(
      page([ownerRequest({ overdue: true, waiting_hours: 30 }), ownerRequest({ id: "r2", utr: "UTR400000000002", waiting_hours: 2 })]),
    );
    renderWithClient(<UpiRequestsScreen />);
    expect(await screen.findByText(/Waiting 30 hours: the student is waiting for your decision/)).toBeInTheDocument();
    expect(screen.getByText("Waiting 2 hours")).toBeInTheDocument();
  });
});

describe("gateway availability on the checkout screens", () => {
  const holdWith = (library: StudentHold["library"]): StudentHold => ({
    id: "h1",
    seat: { id: "s1", label: "A-3" },
    library,
    plan: { id: "p1", name: "Monthly", duration_days: 30, price: "1200.00" },
    amount: "1200.00",
    expires_at: new Date(Date.now() + 10 * 60_000).toISOString(),
  });

  it("hides the gateway button and explains when the gateway is not configured", async () => {
    mocks.fetchCurrentHolds.mockResolvedValue([holdWith({ id: "lib1", name: "Silent Hive", upi_enabled: false, gateway_enabled: false })]);
    renderWithClient(<CheckoutScreen holdId="h1" />);
    expect(await screen.findByText("This library is not taking online payments yet")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Pay ₹/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel booking" })).toBeInTheDocument();
  });

  it("keeps the gateway button when the gateway is configured, and when the server says nothing", async () => {
    mocks.fetchCurrentHolds.mockResolvedValue([holdWith({ id: "lib1", name: "Silent Hive", upi_enabled: false, gateway_enabled: true })]);
    const first = renderWithClient(<CheckoutScreen holdId="h1" />);
    expect(await screen.findByRole("button", { name: /^Pay ₹/ })).toBeInTheDocument();
    first.unmount();
    mocks.fetchCurrentHolds.mockResolvedValue([holdWith({ id: "lib1", name: "Silent Hive" })]);
    renderWithClient(<CheckoutScreen holdId="h1" />);
    expect(await screen.findByRole("button", { name: /^Pay ₹/ })).toBeInTheDocument();
  });

  it("offers UPI, not the unavailable-gateway notice, when UPI is on and the gateway is off", async () => {
    mocks.fetchCurrentHolds.mockResolvedValue([holdWith({ id: "lib1", name: "Silent Hive", upi_enabled: true, gateway_enabled: false })]);
    mocks.fetchUpiInfo.mockResolvedValue(info);
    renderWithClient(<CheckoutScreen holdId="h1" />);
    expect(await screen.findByAltText("UPI QR code of Silent Hive")).toBeInTheDocument();
    expect(screen.queryByText("This library is not taking online payments yet")).not.toBeInTheDocument();
  });
});

describe("StudentUpiRequestsScreen", () => {
  it("shows a pending request with the library's contact details and a cancel button", async () => {
    mocks.fetchStudentUpiRequests.mockResolvedValue(page([studentRequest()]));
    renderWithClient(<StudentUpiRequestsScreen />);
    expect(await screen.findByText("Waiting for the library")).toBeInTheDocument();
    expect(screen.getByText(/Not confirmed yet/)).toBeInTheDocument();
    expect(screen.getByText(/\+919000000001/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel this request" })).toBeInTheDocument();
  });

  it("never implies a refund for a rejected request", async () => {
    mocks.fetchStudentUpiRequests.mockResolvedValue(
      page([studentRequest({ status: "rejected", can_cancel: false, review_note: "No credit of 1200 received" })]),
    );
    renderWithClient(<StudentUpiRequestsScreen />);
    expect(await screen.findByText("Rejected")).toBeInTheDocument();
    expect(screen.getByText(/No credit of 1200 received/)).toBeInTheDocument();
    expect(screen.getByText(/does not refund UPI transfers/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel this request" })).not.toBeInTheDocument();
  });

  it("shows approved with the receipt and cancelled without any action", async () => {
    mocks.fetchStudentUpiRequests.mockResolvedValue(
      page([
        studentRequest({ id: "r2", status: "approved", can_cancel: false, receipt_number: "LH-2026-000042" }),
        studentRequest({ id: "r3", status: "cancelled", can_cancel: false, utr: "UTR400099999999" }),
      ]),
    );
    renderWithClient(<StudentUpiRequestsScreen />);
    expect(await screen.findByText("Approved")).toBeInTheDocument();
    expect(screen.getByText(/LH-2026-000042/)).toBeInTheDocument();
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
  });

  it("cancels after confirmation", async () => {
    mocks.fetchStudentUpiRequests.mockResolvedValue(page([studentRequest()]));
    mocks.cancelUpiRequest.mockResolvedValue(studentRequest({ status: "cancelled", can_cancel: false }));
    renderWithClient(<StudentUpiRequestsScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Cancel this request" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/cancelling does not return your money/i)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Cancel request" }));
    await waitFor(() => expect(mocks.cancelUpiRequest).toHaveBeenCalledWith("r1"));
  });

  it("has loading, empty and error states", async () => {
    mocks.fetchStudentUpiRequests.mockResolvedValueOnce(page([]));
    const first = renderWithClient(<StudentUpiRequestsScreen />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(await screen.findByText("No UPI payment requests")).toBeInTheDocument();
    first.unmount();

    mocks.fetchStudentUpiRequests.mockRejectedValueOnce(new ApiError({ status: 500, code: "SERVER_ERROR", message: "x" }));
    mocks.fetchStudentUpiRequests.mockResolvedValueOnce(page([studentRequest()]));
    renderWithClient(<StudentUpiRequestsScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Waiting for the library")).toBeInTheDocument();
  });
});

describe("UpiRequestsScreen (owner)", () => {
  it("lists pending requests with what the owner needs to match them to the bank history", async () => {
    mocks.fetchOwnerUpiRequests.mockResolvedValue(page([ownerRequest({ has_screenshot: true, student_note: "From my brother's phone" })]));
    renderWithClient(<UpiRequestsScreen />);
    expect(await screen.findByText(/Asha Rao/)).toBeInTheDocument();
    expect(screen.getByText("UTR400012345678")).toBeInTheDocument();
    expect(screen.getAllByText(/₹1,200/).length).toBeGreaterThan(0);
    expect(screen.getByText(/From my brother's phone/)).toBeInTheDocument();
    expect(mocks.fetchOwnerUpiRequests).toHaveBeenCalledWith({ status: "pending", page: 1 });
  });

  it("will not approve until the owner confirms they saw the money, then approves", async () => {
    mocks.fetchOwnerUpiRequests.mockResolvedValue(page([ownerRequest()]));
    mocks.approveUpiRequest.mockResolvedValue(ownerRequest({ status: "approved" }));
    renderWithClient(<UpiRequestsScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    const dialog = await screen.findByRole("dialog");
    const confirm = within(dialog).getByRole("button", { name: "Approve payment" });
    expect(confirm).toBeDisabled();
    await userEvent.click(within(dialog).getByRole("checkbox"));
    expect(confirm).toBeEnabled();
    await userEvent.click(confirm);
    await waitFor(() => expect(mocks.approveUpiRequest).toHaveBeenCalledWith("r1", undefined));
  });

  it("explains a taken seat and offers another seat or a rejection", async () => {
    mocks.fetchOwnerUpiRequests.mockResolvedValue(page([ownerRequest()]));
    mocks.approveUpiRequest.mockRejectedValue(
      new ApiError({
        status: 409,
        code: "SEAT_UNAVAILABLE",
        message: "This seat is no longer free, so no membership was created. Approve the payment onto another free seat, or reject it and refund the student directly.",
      }),
    );
    mocks.fetchOwnerSeats.mockResolvedValue({ seats: [{ id: "s2", label: "A-4", row_label: "A", position: 4, is_active: true, is_disabled: false, disabled_reason: "", status: "empty", occupant: null, hold: null }], counts: {} });
    renderWithClient(<UpiRequestsScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("checkbox"));
    await userEvent.click(within(dialog).getByRole("button", { name: "Approve payment" }));
    expect(await within(dialog).findByText("That seat is no longer free")).toBeInTheDocument();
    expect(within(dialog).getByText(/no membership was created/)).toBeInTheDocument();
    expect(within(dialog).getByText(/refund the student yourself/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Approve on this seat" })).toBeDisabled();
  });

  it("needs a reason to reject, sends it, and warns that LibraryHive cannot refund", async () => {
    mocks.fetchOwnerUpiRequests.mockResolvedValue(page([ownerRequest()]));
    mocks.rejectUpiRequest.mockResolvedValue(ownerRequest({ status: "rejected", review_note: "Not received" }));
    renderWithClient(<UpiRequestsScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Reject" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/cannot return UPI money/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Reject payment" }));
    expect(mocks.rejectUpiRequest).not.toHaveBeenCalled();
    await userEvent.type(within(dialog).getByLabelText(/Reason/), "Not received");
    await userEvent.click(within(dialog).getByRole("button", { name: "Reject payment" }));
    await waitFor(() => expect(mocks.rejectUpiRequest).toHaveBeenCalledWith("r1", "Not received"));
  });

  it("shows the screenshot from a short-lived link and says it is not proof", async () => {
    mocks.fetchOwnerUpiRequests.mockResolvedValue(page([ownerRequest({ has_screenshot: true })]));
    mocks.fetchOwnerUpiScreenshot.mockResolvedValue({ url: "http://127.0.0.1:8000/api/v1/files/private/shot/", expires_in: 600 });
    renderWithClient(<UpiRequestsScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "View screenshot" }));
    expect(await screen.findByAltText("Payment screenshot sent by the student")).toHaveAttribute("src", "http://127.0.0.1:8000/api/v1/files/private/shot/");
    expect(screen.getByText(/not proof of payment/i)).toBeInTheDocument();
  });

  it("shows decided requests with who decided and the receipt, without action buttons", async () => {
    mocks.fetchOwnerUpiRequests.mockResolvedValue(
      page([ownerRequest({ status: "approved", reviewed_by: "Owner Name", reviewed_at: "2026-11-08T08:00:00Z", receipt_number: "LH-2026-000042" })]),
    );
    renderWithClient(<UpiRequestsScreen />);
    expect(await screen.findByText(/Decided by Owner Name/)).toBeInTheDocument();
    expect(screen.getByText(/LH-2026-000042/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("has an empty state and an error state with retry", async () => {
    mocks.fetchOwnerUpiRequests.mockResolvedValueOnce(page([]));
    const first = renderWithClient(<UpiRequestsScreen />);
    expect(await screen.findByText("Nothing to check")).toBeInTheDocument();
    first.unmount();
    mocks.fetchOwnerUpiRequests.mockRejectedValueOnce(new ApiError({ status: 500, code: "SERVER_ERROR", message: "x" }));
    mocks.fetchOwnerUpiRequests.mockResolvedValueOnce(page([ownerRequest()]));
    renderWithClient(<UpiRequestsScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Try again" }));
    expect(await screen.findByText(/Asha Rao/)).toBeInTheDocument();
  });
});

describe("UpiSettingsScreen (owner)", () => {
  const settings = (overrides: Partial<UpiPaymentSettings> = {}): UpiPaymentSettings => ({
    upi_enabled: true,
    upi_id: "silent.hive@okbank",
    instructions: "Pay exactly the plan amount.",
    has_qr: true,
    qr_url: "http://127.0.0.1:8000/api/v1/files/private/qr/",
    qr_url_expires_in: 600,
    ...overrides,
  });

  it("shows the saved details and the QR preview", async () => {
    mocks.fetchUpiSettings.mockResolvedValue(settings());
    renderWithClient(<UpiSettingsScreen />);
    expect(await screen.findByDisplayValue("silent.hive@okbank")).toBeInTheDocument();
    expect(screen.getByAltText("Your saved UPI QR code")).toHaveAttribute("src", settings().qr_url);
    expect(screen.getByText(/You confirm every payment yourself/)).toBeInTheDocument();
  });

  it("rejects a malformed UPI ID before sending", async () => {
    mocks.fetchUpiSettings.mockResolvedValue(settings());
    renderWithClient(<UpiSettingsScreen />);
    const field = await screen.findByLabelText("UPI ID");
    await userEvent.clear(field);
    await userEvent.type(field, "not a upi id");
    await userEvent.click(screen.getByRole("button", { name: "Save settings" }));
    expect(await screen.findByText(/valid UPI ID/)).toBeInTheDocument();
    expect(mocks.saveUpiSettings).not.toHaveBeenCalled();
  });

  it("saves the UPI ID, instructions and the switch", async () => {
    mocks.fetchUpiSettings.mockResolvedValue(settings({ upi_enabled: false }));
    mocks.saveUpiSettings.mockResolvedValue(settings());
    renderWithClient(<UpiSettingsScreen />);
    await userEvent.click(await screen.findByRole("checkbox", { name: /Accept UPI payments/ }));
    await userEvent.click(screen.getByRole("button", { name: "Save settings" }));
    await waitFor(() =>
      expect(mocks.saveUpiSettings).toHaveBeenCalledWith({
        upi_enabled: true,
        upi_id: "silent.hive@okbank",
        instructions: "Pay exactly the plan amount.",
      }),
    );
  });

  it("uploads a QR image and refuses one over 5 MB", async () => {
    mocks.fetchUpiSettings.mockResolvedValue(settings({ has_qr: false, qr_url: null }));
    mocks.uploadUpiQr.mockResolvedValue(settings());
    renderWithClient(<UpiSettingsScreen />);
    const input = await screen.findByLabelText("Choose a QR code image");
    await userEvent.upload(input, new File([new Uint8Array(6 * 1024 * 1024)], "big.png", { type: "image/png" }));
    expect(await screen.findByText(/5 MB or smaller/)).toBeInTheDocument();
    expect(mocks.uploadUpiQr).not.toHaveBeenCalled();
    const file = new File(["x"], "qr.png", { type: "image/png" });
    await userEvent.upload(input, file);
    await waitFor(() => expect(mocks.uploadUpiQr).toHaveBeenCalledWith(file));
  });

  it("removes the QR after confirmation and shows the server's reason if it is refused", async () => {
    mocks.fetchUpiSettings.mockResolvedValue(settings());
    mocks.removeUpiQr.mockRejectedValue(new ApiError({ status: 409, code: "QR_REQUIRED", message: "x" }));
    renderWithClient(<UpiSettingsScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Remove QR code" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Remove" }));
    expect(await screen.findByText(/Turn UPI payments off or add a UPI ID/)).toBeInTheDocument();
  });

  it("has an error state with retry", async () => {
    mocks.fetchUpiSettings.mockRejectedValueOnce(new ApiError({ status: 500, code: "SERVER_ERROR", message: "x" }));
    mocks.fetchUpiSettings.mockResolvedValueOnce(settings());
    renderWithClient(<UpiSettingsScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Try again" }));
    expect(await screen.findByDisplayValue("silent.hive@okbank")).toBeInTheDocument();
  });
});

describe("content security policy for payment images", () => {
  const base = { nonce: "n", apiUrl: "https://api.example.com/api/v1", mapTileUrl: undefined, isDev: false };

  it("allows the API origin and every listed media origin to serve images, and nothing else new", () => {
    const csp = buildCsp({ ...base, mediaOrigin: "https://photos.example.com, https://private.example.com" });
    const img = csp.split("; ").find((part) => part.startsWith("img-src")) ?? "";
    expect(img).toContain("https://api.example.com");
    expect(img).toContain("https://photos.example.com");
    expect(img).toContain("https://private.example.com");
    expect(csp.split("; ").find((part) => part.startsWith("script-src"))).not.toContain("example.com");
  });

  it("ignores a malformed media origin", () => {
    const img = buildCsp({ ...base, mediaOrigin: "not a url,https://ok.example.com" }).split("; ").find((part) => part.startsWith("img-src")) ?? "";
    expect(img).toContain("https://ok.example.com");
    expect(img).not.toContain("not a url");
  });
});
