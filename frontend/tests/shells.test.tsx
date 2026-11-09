import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OwnerShell, PublicShell, StudentShell } from "@/components/layout/shells";
import type { AuthContextValue } from "@/lib/auth-context";

import { expectNoAxeViolations } from "./axe";

const upiMocks = vi.hoisted(() => ({ fetchOwnerUpiSummary: vi.fn() }));

let pathname = "/student";
let auth: Partial<AuthContextValue> = { status: "anonymous", user: null, logout: vi.fn() };

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock("@/lib/auth-context", () => ({ useAuth: () => auth }));
vi.mock("@/lib/api/upi", () => ({ fetchOwnerUpiSummary: upiMocks.fetchOwnerUpiSummary }));

function renderOwner() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <OwnerShell>content</OwnerShell>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  upiMocks.fetchOwnerUpiSummary.mockReset();
  upiMocks.fetchOwnerUpiSummary.mockResolvedValue({ pending: 0, overdue: 0 });
});
// The bell has its own test; here it only needs to exist in the header.
vi.mock("@/components/notifications/notification-bell", () => ({
  NotificationBell: ({ href }: { href: string }) => <a href={href}>Notifications</a>,
}));

describe("shells", () => {
  it("public shell offers log in and sign up to visitors, with a skip link", async () => {
    auth = { status: "anonymous", user: null, logout: vi.fn() };
    const { container } = render(<PublicShell>content</PublicShell>);
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main");
    expect(screen.getByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("link", { name: "Sign up" })).toHaveAttribute("href", "/register");
    expect(screen.getByRole("main")).toHaveTextContent("content");
    await expectNoAxeViolations(container);
  });

  it("student bottom bar has five items and marks the current page", () => {
    pathname = "/student/attendance";
    auth = { status: "authenticated", user: null, logout: vi.fn() };
    render(<StudentShell>content</StudentShell>);
    const bottomBar = screen.getAllByRole("navigation", { name: "Primary" })[0]!;
    const links = within(bottomBar).getAllByRole("link");
    expect(links.map((link) => link.textContent)).toEqual(["Discover", "Home", "Attendance", "Alerts", "Profile"]);
    expect(within(bottomBar).getByRole("link", { name: "Attendance" })).toHaveAttribute("aria-current", "page");
  });

  it("owner sidebar lists every owner area and highlights the most specific match", () => {
    pathname = "/owner/members/42";
    auth = { status: "authenticated", user: null, logout: vi.fn() };
    renderOwner();
    const sidebar = screen.getByRole("navigation", { name: "Owner" });
    expect(within(sidebar).getAllByRole("link")).toHaveLength(10);
    expect(within(sidebar).getByRole("link", { name: "Members" })).toHaveAttribute("aria-current", "page");
    expect(within(sidebar).getByRole("link", { name: "Dashboard" })).not.toHaveAttribute("aria-current");
  });

  it("owner Payments link shows how many UPI payments wait for a decision", async () => {
    pathname = "/owner";
    auth = { status: "authenticated", user: null, logout: vi.fn() };
    upiMocks.fetchOwnerUpiSummary.mockResolvedValue({ pending: 3, overdue: 0 });
    renderOwner();
    const sidebar = screen.getByRole("navigation", { name: "Owner" });
    await waitFor(() => expect(within(sidebar).getByRole("link", { name: /Payments/ })).toHaveTextContent("3"));
    expect(within(sidebar).getByText("3 UPI payments waiting for your decision")).toBeInTheDocument();
  });

  it("marks the badge urgent in words when a request is overdue", async () => {
    pathname = "/owner";
    auth = { status: "authenticated", user: null, logout: vi.fn() };
    upiMocks.fetchOwnerUpiSummary.mockResolvedValue({ pending: 2, overdue: 1 });
    renderOwner();
    expect(await screen.findAllByText("2 UPI payments waiting, some overdue")).not.toHaveLength(0);
  });

  it("shows no badge for zero, and no badge (and no crash) if the count cannot be loaded", async () => {
    pathname = "/owner";
    auth = { status: "authenticated", user: null, logout: vi.fn() };
    renderOwner();
    await waitFor(() => expect(upiMocks.fetchOwnerUpiSummary).toHaveBeenCalled());
    expect(screen.queryByText(/UPI payments waiting/)).not.toBeInTheDocument();
    upiMocks.fetchOwnerUpiSummary.mockReset();
    upiMocks.fetchOwnerUpiSummary.mockRejectedValue(new Error("offline"));
    renderOwner();
    await waitFor(() => expect(upiMocks.fetchOwnerUpiSummary).toHaveBeenCalled());
    expect(screen.queryByText(/UPI payments waiting/)).not.toBeInTheDocument();
  });
});
