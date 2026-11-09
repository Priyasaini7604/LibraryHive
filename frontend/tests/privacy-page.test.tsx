import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PrivacyPage from "@/app/(public)/privacy/page";
import { PublicShell } from "@/components/layout/shells";

import { expectNoAxeViolations } from "./axe";

vi.mock("next/navigation", () => ({
  usePathname: () => "/privacy",
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ status: "anonymous", user: null, logout: vi.fn() }) }));
vi.mock("@/components/notifications/notification-bell", () => ({ NotificationBell: () => null }));

describe("privacy policy page (draft)", () => {
  it("has one h1, labelled sections, and no accessibility violations", async () => {
    const { container } = render(<PrivacyPage />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 2 }).length).toBeGreaterThanOrEqual(8);
    await expectNoAxeViolations(container);
  });

  it("says plainly that it is a draft and marks every undecided business detail", () => {
    const { container } = render(<PrivacyPage />);
    expect(screen.getByRole("note")).toHaveTextContent(/draft for review/i);
    expect(container.querySelectorAll('[data-placeholder="true"]').length).toBeGreaterThanOrEqual(8);
  });

  it("discloses the location flow without claiming the coordinates are never logged", () => {
    render(<PrivacyPage />);
    const location = within(screen.getByRole("region", { name: "Location" }));
    expect(location.getByText(/sent to the LibraryHive server/i)).toBeInTheDocument();
    expect(location.getByText(/browser.s history/i)).toBeInTheDocument();
    expect(location.getByText(/not yet checked/i)).toBeInTheDocument();
    expect(location.getByText(/shown\s+publicly/i)).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/never logged|not logged|no location data/i);
  });

  it("discloses the outside services your browser contacts directly", () => {
    render(<PrivacyPage />);
    const outside = within(screen.getByRole("region", { name: "Outside services your browser contacts" }));
    expect(outside.getByText(/tile\.openstreetmap\.org/)).toBeInTheDocument();
    expect(outside.getByText(/IP address, which part of the\s+map/i)).toBeInTheDocument();
    expect(outside.getByText(/Nothing is sent while typing/i)).toBeInTheDocument();
    expect(outside.getByText(/Razorpay \(online payments\)/)).toBeInTheDocument();
  });

  it("is linked from the public footer", () => {
    render(<PublicShell>content</PublicShell>);
    const footer = screen.getByRole("navigation", { name: "Footer" });
    expect(within(footer).getByRole("link", { name: "Privacy Policy" })).toHaveAttribute("href", "/privacy");
  });
});
