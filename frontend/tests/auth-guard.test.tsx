import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthGuard, decideAccess } from "@/components/layout/auth-guard";
import type { AuthContextValue } from "@/lib/auth-context";
import type { User } from "@/lib/types";

const replace = vi.fn();
let pathname = "/student";
let auth: Pick<AuthContextValue, "status" | "user">;

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => auth,
}));

const student: User = {
  id: "s1",
  name: "Asha Rao",
  email: "asha@example.com",
  phone: "+919876543210",
  role: "student",
  domain: null,
  created_at: "2026-10-09T00:00:00Z",
};
const owner: User = { ...student, id: "o1", role: "owner", has_library: true };

describe("decideAccess", () => {
  it("waits while the session is being restored", () => {
    expect(decideAccess("loading", null, "student", "/student")).toEqual({ kind: "wait" });
  });

  it("sends anonymous visitors to login with the current path", () => {
    expect(decideAccess("anonymous", null, "owner", "/owner/seats")).toEqual({
      kind: "redirect",
      to: "/login?next=%2Fowner%2Fseats",
    });
  });

  it("sends a user with the wrong role to their own home", () => {
    expect(decideAccess("authenticated", student, "owner", "/owner")).toEqual({ kind: "redirect", to: "/student" });
    expect(decideAccess("authenticated", owner, "student", "/student")).toEqual({ kind: "redirect", to: "/owner" });
  });

  it("sends owners without a library to onboarding, except on onboarding itself", () => {
    const newOwner = { ...owner, has_library: false };
    expect(decideAccess("authenticated", newOwner, "owner", "/owner/seats")).toEqual({
      kind: "redirect",
      to: "/owner/onboarding",
    });
    expect(decideAccess("authenticated", newOwner, "owner", "/owner/onboarding")).toEqual({ kind: "allow" });
  });

  it("allows the right role", () => {
    expect(decideAccess("authenticated", student, "student", "/student")).toEqual({ kind: "allow" });
  });
});

describe("AuthGuard", () => {
  beforeEach(() => {
    replace.mockReset();
    pathname = "/student";
  });

  it("never renders protected content while loading", () => {
    auth = { status: "loading", user: null };
    render(
      <AuthGuard requiredRole="student">
        <p>Secret</p>
      </AuthGuard>,
    );
    expect(screen.queryByText("Secret")).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("redirects anonymous visitors without showing content", () => {
    auth = { status: "anonymous", user: null };
    render(
      <AuthGuard requiredRole="student">
        <p>Secret</p>
      </AuthGuard>,
    );
    expect(screen.queryByText("Secret")).not.toBeInTheDocument();
    expect(replace).toHaveBeenCalledWith("/login?next=%2Fstudent");
  });

  it("renders content for the right role", () => {
    auth = { status: "authenticated", user: student };
    render(
      <AuthGuard requiredRole="student">
        <p>Secret</p>
      </AuthGuard>,
    );
    expect(screen.getByText("Secret")).toBeInTheDocument();
  });
});
