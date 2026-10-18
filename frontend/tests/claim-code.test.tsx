import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ClaimCodeDialog } from "@/components/owner/claim-code-dialog";
import { ApiError } from "@/lib/errors";

import { expectNoAxeViolations } from "./axe";

vi.setConfig({ testTimeout: 20_000 });

const mocks = vi.hoisted(() => ({ issueClaimCode: vi.fn() }));
vi.mock("@/lib/api/memberships", () => ({ issueClaimCode: mocks.issueClaimCode }));

function renderDialog(onClose = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ClaimCodeDialog studentId="u1" studentName="Ravi Walkin" onClose={onClose} />
    </QueryClientProvider>,
  );
  return onClose;
}

beforeEach(() => {
  mocks.issueClaimCode.mockReset();
});

describe("ClaimCodeDialog", () => {
  it("creates nothing until the owner asks", async () => {
    renderDialog();
    expect(await screen.findByRole("button", { name: "Create a claim code" })).toBeInTheDocument();
    expect(mocks.issueClaimCode).not.toHaveBeenCalled();
  });

  it("shows the code once, with the expiry and what to tell the student", async () => {
    mocks.issueClaimCode.mockResolvedValue({ code: "K7M2QX9P", expires_at: "2026-10-26T10:00:00Z" });
    renderDialog();
    await userEvent.click(await screen.findByRole("button", { name: "Create a claim code" }));
    expect(await screen.findByLabelText("Claim code")).toHaveTextContent("K7M2QX9P");
    expect(mocks.issueClaimCode).toHaveBeenCalledExactlyOnceWith("u1");
    expect(screen.getByText("This is the only time you will see this code")).toBeInTheDocument();
    expect(screen.getByText(/Claim your account/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Done" })).toBeInTheDocument();
    await expectNoAxeViolations(document.body);
  });

  it("explains why a code can't be issued", async () => {
    mocks.issueClaimCode.mockRejectedValue(new ApiError({ status: 409, code: "CONFLICT", message: "x" }));
    renderDialog();
    await userEvent.click(await screen.findByRole("button", { name: "Create a claim code" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/went wrong/i);
    expect(screen.queryByLabelText("Claim code")).not.toBeInTheDocument();
  });

  it("closes without keeping the code anywhere", async () => {
    mocks.issueClaimCode.mockResolvedValue({ code: "K7M2QX9P", expires_at: "2026-10-26T10:00:00Z" });
    const onClose = renderDialog();
    await userEvent.click(await screen.findByRole("button", { name: "Create a claim code" }));
    await userEvent.click(await screen.findByRole("button", { name: "Done" }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(JSON.stringify({ ...localStorage })).not.toContain("K7M2QX9P");
    expect(JSON.stringify({ ...sessionStorage })).not.toContain("K7M2QX9P");
  });
});
