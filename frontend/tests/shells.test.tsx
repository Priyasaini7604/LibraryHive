import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OwnerShell, PublicShell, StudentShell } from "@/components/layout/shells";
import type { AuthContextValue } from "@/lib/auth-context";

import { expectNoAxeViolations } from "./axe";

let pathname = "/student";
let auth: Partial<AuthContextValue> = { status: "anonymous", user: null, logout: vi.fn() };

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock("@/lib/auth-context", () => ({ useAuth: () => auth }));

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
    render(<OwnerShell>content</OwnerShell>);
    const sidebar = screen.getByRole("navigation", { name: "Owner" });
    expect(within(sidebar).getAllByRole("link")).toHaveLength(10);
    expect(within(sidebar).getByRole("link", { name: "Members" })).toHaveAttribute("aria-current", "page");
    expect(within(sidebar).getByRole("link", { name: "Dashboard" })).not.toHaveAttribute("aria-current");
  });
});
