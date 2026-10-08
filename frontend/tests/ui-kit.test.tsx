import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Button, IconButton } from "@/components/ui/button";
import { Select } from "@/components/ui/choice";
import { DataTable } from "@/components/ui/data-table";
import { FormField } from "@/components/ui/form-field";
import { Input, OtpField } from "@/components/ui/input";
import { Stepper } from "@/components/ui/navigation";
import { ConfirmDialog } from "@/components/ui/overlay";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Alert, ProgressBar, StatusBadge } from "@/components/ui/surface";
import { ApiError } from "@/lib/errors";

import { expectNoAxeViolations } from "./axe";

describe("Button", () => {
  it("is disabled and announced as busy while loading", () => {
    render(<Button loading>Save</Button>);
    const button = screen.getByRole("button", { name: /save/i });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("defaults to type=button so it never submits forms by accident", () => {
    render(<Button>Click</Button>);
    expect(screen.getByRole("button")).toHaveAttribute("type", "button");
  });

  it("gives icon-only buttons an accessible name", () => {
    render(<IconButton label="Close panel" icon={<span>x</span>} />);
    expect(screen.getByRole("button", { name: "Close panel" })).toBeInTheDocument();
  });
});

describe("FormField", () => {
  it("links label, hint and error to the control", async () => {
    const { container } = render(
      <form>
        <FormField label="Phone" hint="Indian mobile number" error="Enter a valid number" required>
          <Input />
        </FormField>
      </form>,
    );
    const input = screen.getByLabelText(/phone/i);
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-required", "true");
    expect(input).toHaveAccessibleDescription("Indian mobile number Enter a valid number");
    await expectNoAxeViolations(container);
  });

  it("supports the OTP field with one-time-code autocomplete", () => {
    render(
      <FormField label="Code">
        <OtpField />
      </FormField>,
    );
    expect(screen.getByLabelText("Code")).toHaveAttribute("autocomplete", "one-time-code");
  });

  it("works with the Select control", async () => {
    const { container } = render(
      <FormField label="Exam">
        <Select options={[{ value: "upsc", label: "UPSC" }]} />
      </FormField>,
    );
    expect(screen.getByRole("combobox", { name: "Exam" })).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });
});

describe("ConfirmDialog", () => {
  function Harness({ onConfirm }: { onConfirm: () => void }) {
    const [open, setOpen] = useState(false);
    return (
      <>
        <Button onClick={() => setOpen(true)}>Archive member</Button>
        <ConfirmDialog
          open={open}
          onOpenChange={setOpen}
          title="Archive this member?"
          description="The seat will become free. Payment and attendance history are kept."
          confirmLabel="Archive"
          destructive
          onConfirm={onConfirm}
        />
      </>
    );
  }

  it("states the consequence, confirms, and closes with Escape returning focus", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<Harness onConfirm={onConfirm} />);
    const trigger = screen.getByRole("button", { name: "Archive member" });

    await user.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "Archive this member?" });
    expect(dialog).toHaveAccessibleDescription("The seat will become free. Payment and attendance history are kept.");
    await user.click(within(dialog).getByRole("button", { name: "Archive" }));
    expect(onConfirm).toHaveBeenCalledOnce();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});

describe("DataTable", () => {
  const rows = [
    { id: "1", name: "Asha Rao", seat: "A-1", status: "Active" },
    { id: "2", name: "Ravi Kumar", seat: "B-4", status: "Due" },
  ];

  it("renders a captioned table and a card list from the same columns", async () => {
    const { container } = render(
      <DataTable
        caption="Members"
        rows={rows}
        rowKey={(row) => row.id}
        columns={[
          { key: "name", header: "Name", cell: (row) => row.name, primary: true },
          { key: "seat", header: "Seat", cell: (row) => row.seat },
          { key: "status", header: "Status", cell: (row) => row.status },
        ]}
      />,
    );
    expect(screen.getByRole("table", { name: "Members" })).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader").map((th) => th.textContent)).toEqual(["Name", "Seat", "Status"]);
    expect(screen.getByRole("list", { name: "Members" })).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });
});

describe("state components", () => {
  it("ErrorState shows a friendly message, retry and the reference", async () => {
    const user = userEvent.setup();
    const retry = vi.fn();
    render(
      <ErrorState
        error={new ApiError({ status: 500, code: "SERVER_ERROR", message: "boom", requestId: "ref-9" })}
        onRetry={retry}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong on our side.");
    expect(screen.getByText("Reference: ref-9")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("EmptyState offers the next step", () => {
    render(<EmptyState title="No members yet." action={<Button>Add offline student</Button>} />);
    expect(screen.getByRole("button", { name: "Add offline student" })).toBeInTheDocument();
  });

  it("status is shown as text, not colour alone", () => {
    render(<StatusBadge tone="warning" icon={<span>!</span>} label="Held" />);
    expect(screen.getByText("Held")).toBeInTheDocument();
  });

  it("danger alerts are announced immediately", () => {
    render(<Alert tone="danger" title="Payment failed" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Payment failed");
  });

  it("progress bar exposes its value", () => {
    render(<ProgressBar value={18} max={24} label="Seats occupied" />);
    expect(screen.getByRole("progressbar", { name: "Seats occupied" })).toHaveAttribute("aria-valuenow", "18");
  });

  it("stepper marks the current step", () => {
    render(
      <Stepper
        currentId="plans"
        steps={[
          { id: "basics", label: "Basics", complete: true },
          { id: "plans", label: "Plans", complete: false },
        ]}
      />,
    );
    expect(screen.getByText("Plans", { selector: "li" })).toHaveAttribute("aria-current", "step");
  });
});
