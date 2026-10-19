import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CheckoutScreen } from "@/components/booking/checkout-screen";
import { RenewalScreen, renewalStart } from "@/components/booking/renewal-screen";
import { ApiError } from "@/lib/errors";
import type { CheckoutHandlers } from "@/lib/razorpay";
import type { PaymentOrder, StudentHold, StudentMembershipDetail } from "@/lib/types";

import { expectNoAxeViolations } from "./axe";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  fetchCurrentHolds: vi.fn(),
  cancelHold: vi.fn(),
  createBookingOrder: vi.fn(),
  createRenewalOrder: vi.fn(),
  verifyPayment: vi.fn(),
  fetchStudentPayments: vi.fn(),
  openCheckout: vi.fn(),
  fetchStudentMembership: vi.fn(),
  fetchLibrary: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));
vi.mock("@/lib/api/seats", () => ({ fetchCurrentHolds: mocks.fetchCurrentHolds, cancelHold: mocks.cancelHold }));
vi.mock("@/lib/api/payments", () => ({
  createBookingOrder: mocks.createBookingOrder,
  createRenewalOrder: mocks.createRenewalOrder,
  verifyPayment: mocks.verifyPayment,
  fetchStudentPayments: mocks.fetchStudentPayments,
}));
vi.mock("@/lib/razorpay", () => ({ openCheckout: mocks.openCheckout }));
vi.mock("@/lib/api/memberships", () => ({ fetchStudentMembership: mocks.fetchStudentMembership }));
vi.mock("@/lib/api/libraries", () => ({ fetchLibrary: mocks.fetchLibrary }));

const hold = (overrides: Partial<StudentHold> = {}): StudentHold => ({
  id: "h1",
  seat: { id: "s1", label: "A-3" },
  library: { id: "lib1", name: "Silent Hive" },
  plan: { id: "p1", name: "Monthly", duration_days: 30, price: "1200.00" },
  amount: "1200.00",
  expires_at: new Date(Date.now() + 10 * 60_000).toISOString(),
  ...overrides,
});

const order: PaymentOrder = {
  payment_id: "pay1",
  gateway: "razorpay",
  key_id: "rzp_test_x",
  order_id: "order_1",
  amount_paise: 120000,
  currency: "INR",
  description: "Monthly at Silent Hive",
  prefill: { name: "Asha", email: "a@example.com", phone: "+919000000001" },
};

const verified = {
  payment: { id: "pay1", status: "success", receipt_number: "LH-2026-000007", amount: "1200.00", period_start: "2026-10-18", period_end: "2026-11-17" },
  membership: { id: "m1", seat: { id: "s1", label: "A-3" }, next_due_date: "2026-11-17", status: "active" },
};

const callback = { razorpay_order_id: "order_1", razorpay_payment_id: "pay_1", razorpay_signature: "sig" };

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

/** Capture the handlers the screen gives the payment window, so a test can play the window's part. */
function captureWindow(): { handlers: () => CheckoutHandlers } {
  let captured: CheckoutHandlers | null = null;
  mocks.openCheckout.mockImplementation(async (_order: PaymentOrder, handlers: CheckoutHandlers) => {
    captured = handlers;
  });
  return { handlers: () => captured as CheckoutHandlers };
}

beforeEach(() => {
  for (const mock of Object.values(mocks)) mock.mockReset();
  mocks.fetchCurrentHolds.mockResolvedValue([hold()]);
  mocks.createBookingOrder.mockResolvedValue(order);
});
afterEach(() => vi.useRealTimers());

async function pay() {
  await userEvent.click(await screen.findByRole("button", { name: "Pay ₹1,200" }));
  await waitFor(() => expect(mocks.openCheckout).toHaveBeenCalled());
}

describe("CheckoutScreen", () => {
  it("shows the summary with the server's amount and a countdown", async () => {
    const { container } = renderWithClient(<CheckoutScreen holdId="h1" />);
    expect(await screen.findByText("Silent Hive")).toBeInTheDocument();
    expect(screen.getByText(/Seat A-3 · Monthly plan/)).toBeInTheDocument();
    expect(screen.getByText(/Seat held for/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pay ₹1,200" })).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("creates the order from the hold only and opens the payment window", async () => {
    captureWindow();
    renderWithClient(<CheckoutScreen holdId="h1" />);
    await pay();
    expect(mocks.createBookingOrder).toHaveBeenCalledExactlyOnceWith("h1");
    expect(mocks.openCheckout).toHaveBeenCalledWith(order, expect.any(Object));
    expect(await screen.findByText(/Complete the payment in the payment window/)).toBeInTheDocument();
  });

  it("confirms only after the server verifies the result", async () => {
    const window = captureWindow();
    mocks.verifyPayment.mockResolvedValue(verified);
    renderWithClient(<CheckoutScreen holdId="h1" />);
    await pay();
    expect(mocks.verifyPayment).not.toHaveBeenCalled(); // opening the window confirms nothing
    await act(async () => window.handlers().onSuccess(callback));
    expect(mocks.verifyPayment).toHaveBeenCalledWith(callback);
    expect(await screen.findByText("Your seat is booked")).toBeInTheDocument();
    expect(screen.getByText(/receipt LH-2026-000007/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to my membership" })).toHaveAttribute("href", "/student/memberships/m1");
    expect(screen.getByRole("link", { name: "View receipt" })).toHaveAttribute("href", "/student/payments/pay1");
  });

  it("lets the student try again when the window is closed without paying", async () => {
    const window = captureWindow();
    renderWithClient(<CheckoutScreen holdId="h1" />);
    await pay();
    await act(async () => window.handlers().onDismiss());
    expect(await screen.findByText("Payment not completed")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(mocks.verifyPayment).not.toHaveBeenCalled();
  });

  it("shows the gateway's failure and a retry", async () => {
    const window = captureWindow();
    renderWithClient(<CheckoutScreen holdId="h1" />);
    await pay();
    await act(async () => window.handlers().onFailure("Card declined"));
    expect(await screen.findByText("Card declined")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("explains a lost seat and the refund, without offering another payment", async () => {
    const window = captureWindow();
    mocks.verifyPayment.mockRejectedValue(new ApiError({ status: 409, code: "SEAT_LOST_REFUND_PENDING", message: "x" }));
    renderWithClient(<CheckoutScreen holdId="h1" />);
    await pay();
    await act(async () => window.handlers().onSuccess(callback));
    expect(await screen.findByText(/Your payment was received but the seat was taken/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Pay|Try again/ })).not.toBeInTheDocument();
  });

  it("shows a bad signature as a failure with the server's wording", async () => {
    const window = captureWindow();
    mocks.verifyPayment.mockRejectedValue(new ApiError({ status: 400, code: "INVALID_SIGNATURE", message: "x" }));
    renderWithClient(<CheckoutScreen holdId="h1" />);
    await pay();
    await act(async () => window.handlers().onSuccess(callback));
    expect(await screen.findByText(/couldn't verify this payment/i)).toBeInTheDocument();
  });

  it("keeps asking the server when verification can't be reached, and never asks to pay again", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const window = captureWindow();
    mocks.verifyPayment.mockRejectedValue(new ApiError({ status: 503, code: "SERVICE_UNAVAILABLE", message: "x" }));
    mocks.fetchStudentPayments
      .mockResolvedValueOnce({ items: [{ id: "pay1", status: "pending", receipt_number: "LH-1" }], page: 1, page_size: 20, total: 1 })
      .mockResolvedValue({
        items: [{ id: "pay1", status: "success", receipt_number: "LH-2026-000007", amount: "1200.00", period_start: "2026-10-18", period_end: "2026-11-17" }],
        page: 1,
        page_size: 20,
        total: 1,
      });
    renderWithClient(<CheckoutScreen holdId="h1" />);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await user.click(await screen.findByRole("button", { name: "Pay ₹1,200" }));
    await waitFor(() => expect(mocks.openCheckout).toHaveBeenCalled());
    await act(async () => window.handlers().onSuccess(callback));
    expect(await screen.findByText("We're confirming your payment")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Pay|Try again/ })).not.toBeInTheDocument();

    await act(async () => vi.advanceTimersByTimeAsync(3000));
    expect(mocks.fetchStudentPayments).toHaveBeenCalledWith({ order_id: "order_1" });
    await act(async () => vi.advanceTimersByTimeAsync(3000));
    expect(await screen.findByText("Your seat is booked")).toBeInTheDocument();
    expect(mocks.createBookingOrder).toHaveBeenCalledTimes(1);
  });

  it("gives up politely after 90 seconds with the order reference", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const window = captureWindow();
    mocks.verifyPayment.mockRejectedValue(new ApiError({ status: 0, code: "NETWORK_ERROR", message: "x" }));
    mocks.fetchStudentPayments.mockResolvedValue({ items: [{ id: "pay1", status: "pending", receipt_number: "LH-1" }], page: 1, page_size: 20, total: 1 });
    renderWithClient(<CheckoutScreen holdId="h1" />);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await user.click(await screen.findByRole("button", { name: "Pay ₹1,200" }));
    await waitFor(() => expect(mocks.openCheckout).toHaveBeenCalled());
    await act(async () => window.handlers().onSuccess(callback));
    await act(async () => vi.advanceTimersByTimeAsync(95_000));
    expect(await screen.findByText("Your payment is still being confirmed")).toBeInTheDocument();
    expect(screen.getByText(/Reference: order_1/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "My payments" })).toHaveAttribute("href", "/student/payments");
  });

  it("shows an expired hold when the order is refused as expired", async () => {
    mocks.createBookingOrder.mockRejectedValue(new ApiError({ status: 409, code: "HOLD_EXPIRED", message: "x" }));
    renderWithClient(<CheckoutScreen holdId="h1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Pay ₹1,200" }));
    expect(await screen.findByText("Your hold expired")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Choose a seat again" })).toBeInTheDocument();
  });

  it("shows an expired hold when the server no longer lists it", async () => {
    mocks.fetchCurrentHolds.mockResolvedValue([]);
    renderWithClient(<CheckoutScreen holdId="gone" />);
    expect(await screen.findByText("Your hold expired")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Choose a seat again" })).toHaveAttribute("href", "/discover");
    expect(screen.queryByRole("button", { name: /Pay/ })).not.toBeInTheDocument();
  });

  it("cancels the booking after a confirmation and returns to the library", async () => {
    mocks.cancelHold.mockResolvedValue(hold());
    renderWithClient(<CheckoutScreen holdId="h1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Cancel booking" }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Cancel booking" }));
    await waitFor(() => expect(mocks.cancelHold).toHaveBeenCalledWith("h1"));
    await waitFor(() => expect(mocks.push).toHaveBeenCalledWith("/libraries/lib1"));
  });

  it("shows a retryable error if the hold can't be loaded", async () => {
    mocks.fetchCurrentHolds.mockRejectedValueOnce(new ApiError({ status: 500, code: "SERVER_ERROR", message: "x" }));
    renderWithClient(<CheckoutScreen holdId="h1" />);
    expect(await screen.findByText("We couldn't load your booking.")).toBeInTheDocument();
    mocks.fetchCurrentHolds.mockResolvedValue([hold()]);
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Silent Hive")).toBeInTheDocument();
  });
});

const membership = (overrides: Partial<StudentMembershipDetail> = {}): StudentMembershipDetail => ({
  id: "m1",
  library: { id: "lib1", name: "Silent Hive" },
  seat: { label: "A-3" },
  plan: { id: "p1", name: "Monthly", price: "1200.00", duration_days: 30 },
  source: "online",
  status: "due",
  start_date: "2026-09-18",
  next_due_date: "2026-10-20",
  days_to_due: 2,
  renewal_open: true,
  payments: [],
  ...overrides,
});

describe("renewalStart", () => {
  it("continues from the due date until the member is more than 15 days overdue", () => {
    expect(renewalStart("2026-10-20", "2026-10-18")).toBe("2026-10-20"); // early
    expect(renewalStart("2026-10-18", "2026-10-18")).toBe("2026-10-18"); // on time
    expect(renewalStart("2026-10-03", "2026-10-18")).toBe("2026-10-03"); // exactly 15 days late
    expect(renewalStart("2026-10-02", "2026-10-18")).toBe("2026-10-18"); // 16 days late: restart today
  });
});

describe("RenewalScreen", () => {
  beforeEach(() => {
    mocks.fetchStudentMembership.mockResolvedValue(membership());
    mocks.fetchLibrary.mockResolvedValue({
      id: "lib1",
      plans: [
        { id: "p1", name: "Monthly", duration_days: 30, price: "1200.00", timing_note: "" },
        { id: "p2", name: "Quarterly", duration_days: 90, price: "3200.00", timing_note: "" },
      ],
    });
  });

  it("renews with the same plan by default and sends no plan id", async () => {
    const window = captureWindow();
    mocks.createRenewalOrder.mockResolvedValue(order);
    mocks.verifyPayment.mockResolvedValue({ ...verified, membership: { ...verified.membership, id: "m1" } });
    renderWithClient(<RenewalScreen membershipId="m1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Pay ₹1,200" }));
    await waitFor(() => expect(mocks.openCheckout).toHaveBeenCalled());
    expect(mocks.createRenewalOrder).toHaveBeenCalledWith("m1", undefined);
    await act(async () => window.handlers().onSuccess(callback));
    expect(await screen.findByText("Your membership is renewed")).toBeInTheDocument();
  });

  it("lets the student switch plan and shows that plan's price", async () => {
    mocks.createRenewalOrder.mockResolvedValue(order);
    captureWindow();
    renderWithClient(<RenewalScreen membershipId="m1" />);
    await userEvent.click(await screen.findByRole("radio", { name: /Quarterly/ }));
    const payButton = await screen.findByRole("button", { name: "Pay ₹3,200" });
    await userEvent.click(payButton);
    await waitFor(() => expect(mocks.createRenewalOrder).toHaveBeenCalledWith("m1", "p2"));
  });

  it("does not allow paying before renewal opens", async () => {
    mocks.fetchStudentMembership.mockResolvedValue(membership({ renewal_open: false, status: "active", next_due_date: "2026-12-01" }));
    renderWithClient(<RenewalScreen membershipId="m1" />);
    expect(await screen.findByText("Renewal isn't open yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pay ₹1,200" })).toBeDisabled();
  });

  it("points an ended membership back to the library", async () => {
    mocks.fetchStudentMembership.mockResolvedValue(membership({ status: "archived", renewal_open: false }));
    renderWithClient(<RenewalScreen membershipId="m1" />);
    expect(await screen.findByText(/This membership has ended/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to the library" })).toHaveAttribute("href", "/libraries/lib1");
  });
});
