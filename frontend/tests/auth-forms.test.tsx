import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ClaimFlow } from "@/components/auth/claim-flow";
import { ForgotPasswordForm } from "@/components/auth/forgot-password-form";
import { LoginForm } from "@/components/auth/login-form";
import { RegisterForm } from "@/components/auth/register-form";
import { ResetPasswordForm } from "@/components/auth/reset-password-form";
import { ProfileForm } from "@/components/profile/profile-form";
import { ApiError } from "@/lib/errors";
import type { User } from "@/lib/types";

import { expectNoAxeViolations } from "./axe";

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  search: new URLSearchParams(),
  login: vi.fn(),
  register: vi.fn(),
  completeClaim: vi.fn(),
  setUser: vi.fn(),
  startClaim: vi.fn(),
  requestPasswordReset: vi.fn(),
  confirmPasswordReset: vi.fn(),
  updateProfile: vi.fn(),
  fetchDomains: vi.fn(),
  toastSuccess: vi.fn(),
  auth: { status: "anonymous", user: null } as { status: string; user: unknown },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mocks.replace }),
  useSearchParams: () => mocks.search,
}));
vi.mock("sonner", () => ({ toast: { success: mocks.toastSuccess } }));
vi.mock("@/lib/api/auth", () => ({
  startClaim: mocks.startClaim,
  requestPasswordReset: mocks.requestPasswordReset,
  confirmPasswordReset: mocks.confirmPasswordReset,
  updateProfile: mocks.updateProfile,
  fetchDomains: mocks.fetchDomains,
}));
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    status: mocks.auth.status,
    user: mocks.auth.user,
    login: mocks.login,
    register: mocks.register,
    completeClaim: mocks.completeClaim,
    setUser: mocks.setUser,
  }),
}));

const student: User = {
  id: "s1",
  name: "Asha Rao",
  email: "asha@example.com",
  phone: "+919876543210",
  role: "student",
  domain: { code: "neet", name: "NEET" },
  created_at: "2026-10-09T00:00:00Z",
};
const owner: User = { ...student, id: "o1", role: "owner", domain: null, has_library: true };

function apiError(code: string, status = 400, extra: Partial<ConstructorParameters<typeof ApiError>[0]> = {}) {
  return new ApiError({ status, code, message: "server message", ...extra });
}

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.search = new URLSearchParams();
  mocks.auth = { status: "anonymous", user: null };
  mocks.fetchDomains.mockResolvedValue([
    { code: "neet", name: "NEET" },
    { code: "upsc", name: "UPSC" },
  ]);
});

describe("LoginForm", () => {
  it("validates before calling the API", async () => {
    const user = userEvent.setup();
    renderWithQuery(<LoginForm />);

    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByText("Enter your email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(mocks.login).not.toHaveBeenCalled();
  });

  it("logs in with the typed credentials", async () => {
    mocks.login.mockResolvedValue(student);
    const user = userEvent.setup();
    renderWithQuery(<LoginForm />);

    await user.type(screen.getByLabelText(/Email/), "asha@example.com");
    await user.type(screen.getByLabelText(/^Password/), "Str0ng-pass");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(mocks.login).toHaveBeenCalledWith("asha@example.com", "Str0ng-pass"));
  });

  it("shows the generic message for wrong credentials", async () => {
    mocks.login.mockRejectedValue(apiError("INVALID_CREDENTIALS", 401));
    const user = userEvent.setup();
    renderWithQuery(<LoginForm />);

    await user.type(screen.getByLabelText(/Email/), "asha@example.com");
    await user.type(screen.getByLabelText(/^Password/), "wrong-pass1");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect.");
  });

  it("sends a signed-in user to a safe ?next= path or to their home", () => {
    mocks.auth = { status: "authenticated", user: student };
    mocks.search = new URLSearchParams({ next: "/student/payments" });
    const { unmount } = renderWithQuery(<LoginForm />);
    expect(mocks.replace).toHaveBeenCalledWith("/student/payments");
    unmount();

    mocks.replace.mockClear();
    mocks.auth = { status: "authenticated", user: owner };
    mocks.search = new URLSearchParams();
    renderWithQuery(<LoginForm />);
    expect(mocks.replace).toHaveBeenCalledWith("/owner");
  });

  it.each(["https://evil.example", "//evil.example", "/\\evil.example", "javascript:alert(1)"])(
    "ignores the unsafe next value %s",
    (next) => {
      mocks.auth = { status: "authenticated", user: student };
      mocks.search = new URLSearchParams({ next });
      renderWithQuery(<LoginForm />);
      expect(mocks.replace).toHaveBeenCalledWith("/student");
    },
  );

  it("links to forgot password and register, and has no accessibility violations", async () => {
    const { container } = renderWithQuery(<LoginForm />);
    expect(screen.getByRole("link", { name: "Forgot password?" })).toHaveAttribute("href", "/forgot-password");
    expect(screen.getByRole("link", { name: "Create an account" })).toHaveAttribute("href", "/register");
    await expectNoAxeViolations(container);
  });
});

describe("RegisterForm", () => {
  async function fillStudent(user: ReturnType<typeof userEvent.setup>) {
    await user.type(screen.getByLabelText(/Full name/), "Asha Rao");
    await user.type(screen.getByLabelText(/Email/), "asha@example.com");
    await user.type(screen.getByLabelText(/Mobile number/), "98765 43210");
    await user.type(screen.getByLabelText(/^Password/), "Str0ng-pass");
  }

  it("registers a student with the typed phone and no domain by default", async () => {
    mocks.register.mockResolvedValue(student);
    const user = userEvent.setup();
    renderWithQuery(<RegisterForm />);
    await fillStudent(user);
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() =>
      expect(mocks.register).toHaveBeenCalledWith({
        role: "student",
        name: "Asha Rao",
        email: "asha@example.com",
        phone: "98765 43210",
        password: "Str0ng-pass",
      }),
    );
  });

  it("loads the exam list from the API for students and hides it for owners", async () => {
    const user = userEvent.setup();
    renderWithQuery(<RegisterForm />);
    const select = await screen.findByRole("combobox", { name: /Exam you are preparing for/ });
    await waitFor(() => expect(select).toBeEnabled());
    expect(mocks.fetchDomains).toHaveBeenCalledOnce();

    await user.click(screen.getByRole("radio", { name: /Library owner/ }));
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("offers a retry when the exam list cannot be loaded, without blocking sign-up", async () => {
    mocks.fetchDomains.mockRejectedValueOnce(apiError("SERVER_ERROR", 500));
    const user = userEvent.setup();
    renderWithQuery(<RegisterForm />);

    expect(await screen.findByText("We couldn't load the exam list.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create account" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("combobox", { name: /Exam you are preparing for/ })).toBeInTheDocument();
  });

  it("puts EMAIL_TAKEN on the email field", async () => {
    mocks.register.mockRejectedValue(apiError("EMAIL_TAKEN", 409));
    const user = userEvent.setup();
    renderWithQuery(<RegisterForm />);
    await fillStudent(user);
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("An account with this email already exists.")).toBeInTheDocument();
    expect(screen.getByLabelText(/Email/)).toHaveAttribute("aria-invalid", "true");
  });

  it("maps server field details onto fields", async () => {
    mocks.register.mockRejectedValue(
      apiError("VALIDATION_ERROR", 400, { details: { password: ["This password is too common."] } }),
    );
    const user = userEvent.setup();
    renderWithQuery(<RegisterForm />);
    await fillStudent(user);
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("This password is too common.")).toBeInTheDocument();
    expect(screen.getByLabelText(/^Password/)).toHaveAttribute("aria-invalid", "true");
  });

  it("switches to the claim panel on CLAIM_REQUIRED and links to the claim page with the phone", async () => {
    mocks.register.mockRejectedValue(
      apiError("CLAIM_REQUIRED", 409, { details: { channels: ["email_otp", "owner_code"], masked_email: "a***@example.com" } as never }),
    );
    const user = userEvent.setup();
    renderWithQuery(<RegisterForm />);
    await fillStudent(user);
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("A library already added you as a member.")).toBeInTheDocument();
    expect(screen.getByText(/a\*\*\*@example\.com/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Verify and link my account" })).toHaveAttribute(
      "href",
      "/claim?phone=98765%2043210",
    );

    await user.click(screen.getByRole("button", { name: "Back to sign up" }));
    expect(screen.getByRole("button", { name: "Create account" })).toBeInTheDocument();
  });

  it("tells a record without an email to ask the library for a code", async () => {
    mocks.register.mockRejectedValue(apiError("CLAIM_REQUIRED", 409, { details: { channels: ["owner_code"] } as never }));
    const user = userEvent.setup();
    renderWithQuery(<RegisterForm />);
    await fillStudent(user);
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText(/Ask your library for a claim code/)).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const { container } = renderWithQuery(<RegisterForm />);
    await screen.findByRole("combobox", { name: /Exam you are preparing for/ });
    await expectNoAxeViolations(container);
  });
});

describe("ClaimFlow", () => {
  it("sends the email code, then completes with the code and a new password", async () => {
    mocks.startClaim.mockResolvedValue({ channel: "email_otp", masked_email: null });
    mocks.completeClaim.mockResolvedValue(student);
    mocks.search = new URLSearchParams({ phone: "98765 43210" });
    const user = userEvent.setup();
    renderWithQuery(<ClaimFlow />);

    expect(screen.getByLabelText(/Mobile number/)).toHaveValue("98765 43210");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(mocks.startClaim).toHaveBeenCalledWith({ phone: "98765 43210", channel: "email_otp" }));

    expect(await screen.findByText(/we've emailed you a 6-digit code/)).toBeInTheDocument();
    await user.type(screen.getByLabelText(/6-digit code/), "123456");
    await user.type(screen.getByLabelText(/Choose a password/), "Brand-new-Pass-987");
    await user.click(screen.getByRole("button", { name: "Link my account" }));

    await waitFor(() =>
      expect(mocks.completeClaim).toHaveBeenCalledWith({
        phone: "98765 43210",
        code: "123456",
        password: "Brand-new-Pass-987",
      }),
    );
  });

  it("skips the email step for a library code and sends the optional email when given", async () => {
    mocks.completeClaim.mockResolvedValue(student);
    const user = userEvent.setup();
    renderWithQuery(<ClaimFlow />);

    await user.type(screen.getByLabelText(/Mobile number/), "9876543210");
    await user.click(screen.getByRole("radio", { name: /I have a code from my library/ }));
    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(mocks.startClaim).not.toHaveBeenCalled();
    await user.type(await screen.findByLabelText(/Library code/), "abcd-2345");
    await user.type(screen.getByLabelText(/Choose a password/), "Brand-new-Pass-987");
    await user.type(screen.getByLabelText(/^Email/), "rahul@example.com");
    await user.click(screen.getByRole("button", { name: "Link my account" }));

    await waitFor(() =>
      expect(mocks.completeClaim).toHaveBeenCalledWith({
        phone: "9876543210",
        code: "abcd-2345",
        password: "Brand-new-Pass-987",
        email: "rahul@example.com",
      }),
    );
  });

  it("switches to the library code when the record has no email on file", async () => {
    mocks.startClaim.mockRejectedValue(apiError("CLAIM_INVALID", 400, { message: "There is no email on file." }));
    const user = userEvent.setup();
    renderWithQuery(<ClaimFlow />);

    await user.type(screen.getByLabelText(/Mobile number/), "9876543210");
    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("There is no email on file.");
    expect(screen.getByRole("radio", { name: /I have a code from my library/ })).toBeChecked();
  });

  it("shows the friendly message for a wrong code and keeps the form", async () => {
    mocks.completeClaim.mockRejectedValue(apiError("CLAIM_INVALID", 400));
    const user = userEvent.setup();
    renderWithQuery(<ClaimFlow />);
    await user.type(screen.getByLabelText(/Mobile number/), "9876543210");
    await user.click(screen.getByRole("radio", { name: /I have a code from my library/ }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.type(await screen.findByLabelText(/Library code/), "ABCD2345");
    await user.type(screen.getByLabelText(/Choose a password/), "Brand-new-Pass-987");
    await user.click(screen.getByRole("button", { name: "Link my account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("That code is wrong or has expired.");
  });

  it("puts EMAIL_TAKEN on the email field", async () => {
    mocks.completeClaim.mockRejectedValue(apiError("EMAIL_TAKEN", 409));
    const user = userEvent.setup();
    renderWithQuery(<ClaimFlow />);
    await user.type(screen.getByLabelText(/Mobile number/), "9876543210");
    await user.click(screen.getByRole("radio", { name: /I have a code from my library/ }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.type(await screen.findByLabelText(/Library code/), "ABCD2345");
    await user.type(screen.getByLabelText(/Choose a password/), "Brand-new-Pass-987");
    await user.type(screen.getByLabelText(/^Email/), "taken@example.com");
    await user.click(screen.getByRole("button", { name: "Link my account" }));

    expect(await screen.findByText("An account with this email already exists.")).toBeInTheDocument();
  });

  it("lands a signed-in user on the membership page and has no accessibility violations", async () => {
    const { container } = renderWithQuery(<ClaimFlow />);
    await expectNoAxeViolations(container);

    mocks.auth = { status: "authenticated", user: student };
    renderWithQuery(<ClaimFlow />);
    expect(mocks.replace).toHaveBeenCalledWith("/student/memberships");
  });
});

describe("ForgotPasswordForm", () => {
  it("always shows the server's neutral message, links to the code screen and delays a resend", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      mocks.requestPasswordReset.mockResolvedValue({ message: "If an account exists for that email, we've sent a reset code." });
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithQuery(<ForgotPasswordForm />);

      await user.type(screen.getByLabelText(/Email/), "asha@example.com");
      await user.click(screen.getByRole("button", { name: "Send code" }));

      expect(await screen.findByText("If an account exists for that email, we've sent a reset code.")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Enter code" })).toHaveAttribute(
        "href",
        "/reset-password?email=asha%40example.com",
      );
      const resend = screen.getByRole("button", { name: /Send again in 60s/ });
      expect(resend).toBeDisabled();

      // Each tick schedules the next one after React re-renders, so advance one second per act().
      for (let second = 0; second < 60; second += 1) {
        await act(async () => {
          await vi.advanceTimersByTimeAsync(1000);
        });
      }
      await waitFor(() => expect(screen.getByRole("button", { name: "Send the code again" })).toBeEnabled());
      await user.click(screen.getByRole("button", { name: "Send the code again" }));
      expect(mocks.requestPasswordReset).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it("validates the email and shows a rate-limit message", async () => {
    mocks.requestPasswordReset.mockRejectedValue(apiError("RATE_LIMITED", 429));
    const user = userEvent.setup();
    renderWithQuery(<ForgotPasswordForm />);

    await user.type(screen.getByLabelText(/Email/), "not-an-email");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(mocks.requestPasswordReset).not.toHaveBeenCalled();

    await user.clear(screen.getByLabelText(/Email/));
    await user.type(screen.getByLabelText(/Email/), "asha@example.com");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Too many attempts.");
  });

  it("has no accessibility violations", async () => {
    const { container } = renderWithQuery(<ForgotPasswordForm />);
    await expectNoAxeViolations(container);
  });
});

describe("ResetPasswordForm", () => {
  async function fill(user: ReturnType<typeof userEvent.setup>, confirm = "Brand-new-Pass-987") {
    await user.type(screen.getByLabelText(/6-digit code/), "123456");
    await user.type(screen.getByLabelText(/^New password/), "Brand-new-Pass-987");
    await user.type(screen.getByLabelText(/Repeat new password/), confirm);
  }

  it("prefills the email from the link and sends the new password under its API name", async () => {
    mocks.confirmPasswordReset.mockResolvedValue({ message: "Your password has been changed. Please log in." });
    mocks.search = new URLSearchParams({ email: "asha@example.com" });
    const user = userEvent.setup();
    renderWithQuery(<ResetPasswordForm />);

    expect(screen.getByLabelText(/Email/)).toHaveValue("asha@example.com");
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Change password" }));

    await waitFor(() =>
      expect(mocks.confirmPasswordReset).toHaveBeenCalledWith({
        email: "asha@example.com",
        code: "123456",
        newPassword: "Brand-new-Pass-987",
      }),
    );
    expect(await screen.findByText("Your password has been changed. Please log in.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login");
  });

  it("does not submit when the passwords differ", async () => {
    mocks.search = new URLSearchParams({ email: "asha@example.com" });
    const user = userEvent.setup();
    renderWithQuery(<ResetPasswordForm />);
    await fill(user, "different-Pass-1");
    await user.click(screen.getByRole("button", { name: "Change password" }));

    expect(await screen.findByText("The passwords do not match.")).toBeInTheDocument();
    expect(mocks.confirmPasswordReset).not.toHaveBeenCalled();
  });

  it.each([
    ["RESET_INVALID", 400, "That code is wrong or has expired."],
    ["CLAIM_LOCKED", 429, "Too many attempts. Please wait a few minutes and try again."],
  ])("shows a friendly message for %s", async (code, status, message) => {
    mocks.confirmPasswordReset.mockRejectedValue(apiError(code, status));
    mocks.search = new URLSearchParams({ email: "asha@example.com" });
    const user = userEvent.setup();
    renderWithQuery(<ResetPasswordForm />);
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Change password" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });

  it("has no accessibility violations", async () => {
    const { container } = renderWithQuery(<ResetPasswordForm />);
    await expectNoAxeViolations(container);
  });
});

describe("ProfileForm", () => {
  it("shows the saved details with a read-only email and saves only when changed", async () => {
    mocks.auth = { status: "authenticated", user: student };
    const updated: User = { ...student, name: "Asha R." };
    mocks.updateProfile.mockResolvedValue(updated);
    const user = userEvent.setup();
    renderWithQuery(<ProfileForm />);

    expect(screen.getByLabelText(/Full name/)).toHaveValue("Asha Rao");
    expect(screen.getByLabelText(/^Email/)).toBeDisabled();
    expect(screen.getByLabelText(/Mobile number/)).toHaveValue("+919876543210");
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
    expect(await screen.findByRole("combobox", { name: /Exam you are preparing for/ })).toBeInTheDocument();

    await user.clear(screen.getByLabelText(/Full name/));
    await user.type(screen.getByLabelText(/Full name/), "Asha R.");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(mocks.updateProfile).toHaveBeenCalledWith({ name: "Asha R.", phone: "+919876543210", domain_code: "neet" }),
    );
    expect(mocks.setUser).toHaveBeenCalledWith(updated);
    expect(mocks.toastSuccess).toHaveBeenCalledWith("Profile updated");
  });

  it("hides the exam domain for owners and never sends it", async () => {
    mocks.auth = { status: "authenticated", user: owner };
    mocks.updateProfile.mockResolvedValue({ ...owner, name: "Owner Two" });
    const user = userEvent.setup();
    renderWithQuery(<ProfileForm />);

    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(mocks.fetchDomains).not.toHaveBeenCalled();
    await user.clear(screen.getByLabelText(/Full name/));
    await user.type(screen.getByLabelText(/Full name/), "Owner Two");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(mocks.updateProfile).toHaveBeenCalledWith({ name: "Owner Two", phone: "+919876543210" }));
  });

  it("puts PHONE_TAKEN on the phone field", async () => {
    mocks.auth = { status: "authenticated", user: owner };
    mocks.updateProfile.mockRejectedValue(apiError("PHONE_TAKEN", 409));
    const user = userEvent.setup();
    renderWithQuery(<ProfileForm />);

    await user.clear(screen.getByLabelText(/Mobile number/));
    await user.type(screen.getByLabelText(/Mobile number/), "9811100011");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByText("An account with this phone number already exists.")).toBeInTheDocument();
    expect(mocks.toastSuccess).not.toHaveBeenCalled();
  });

  it("shows a loading state until the user is known, and has no accessibility violations", async () => {
    mocks.auth = { status: "loading", user: null };
    const { unmount } = renderWithQuery(<ProfileForm />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    unmount();

    mocks.auth = { status: "authenticated", user: student };
    const { container } = renderWithQuery(<ProfileForm />);
    await screen.findByRole("combobox", { name: /Exam you are preparing for/ });
    await expectNoAxeViolations(container);
  });
});
