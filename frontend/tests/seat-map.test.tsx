import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SeatLegend, SeatMap, type MapSeat } from "@/components/seat-map/seat-map";

import { expectNoAxeViolations } from "./axe";

const seats: MapSeat[] = [
  { id: "a2", label: "A-2", row_label: "A", position: 2, status: "reserved" },
  { id: "a1", label: "A-1", row_label: "A", position: 1, status: "empty" },
  { id: "a3", label: "A-3", row_label: "A", position: 3, status: "occupied" },
  { id: "b1", label: "B-1", row_label: "B", position: 1, status: "disabled" },
  { id: "b2", label: "B-2", row_label: "B", position: 2, status: "empty" },
];

describe("SeatMap", () => {
  it("names every seat with its state, in row and position order", async () => {
    const { container } = render(<SeatMap label="Seat map" seats={seats} onSelect={() => {}} />);
    const names = screen.getAllByRole("button").map((button) => button.getAttribute("aria-label"));
    expect(names).toEqual([
      "Seat A-1, free",
      "Seat A-2, reserved",
      "Seat A-3, taken",
      "Seat B-1, under maintenance",
      "Seat B-2, free",
    ]);
    expect(screen.getByRole("group", { name: "Row A" })).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("lets students choose free seats only", async () => {
    const onSelect = vi.fn();
    render(<SeatMap label="Seat map" seats={seats} selectedId="a1" onSelect={onSelect} />);
    await userEvent.click(screen.getByRole("button", { name: "Seat A-3, taken" }));
    await userEvent.click(screen.getByRole("button", { name: "Seat B-1, under maintenance" }));
    expect(onSelect).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Seat B-2, free" }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: "b2" }));
    expect(screen.getByRole("button", { name: "Seat A-1, free" })).toHaveAttribute("aria-pressed", "true");
  });

  it("lets owners open any seat", async () => {
    const onSelect = vi.fn();
    render(<SeatMap label="Seat map" seats={seats} onSelect={onSelect} isSelectable={() => true} />);
    await userEvent.click(screen.getByRole("button", { name: "Seat A-3, taken" }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: "a3" }));
  });

  it("moves focus with the arrow keys, across rows too", async () => {
    render(<SeatMap label="Seat map" seats={seats} onSelect={() => {}} />);
    screen.getByRole("button", { name: "Seat A-1, free" }).focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("button", { name: "Seat A-2, reserved" })).toHaveFocus();
    await userEvent.keyboard("{ArrowDown}");
    expect(screen.getByRole("button", { name: "Seat B-2, free" })).toHaveFocus();
    await userEvent.keyboard("{ArrowUp}");
    expect(screen.getByRole("button", { name: "Seat A-2, reserved" })).toHaveFocus();
    await userEvent.keyboard("{End}");
    expect(screen.getByRole("button", { name: "Seat B-2, free" })).toHaveFocus();
    await userEvent.keyboard("{Home}");
    expect(screen.getByRole("button", { name: "Seat A-1, free" })).toHaveFocus();
  });

  it("keeps one seat in the tab order", () => {
    render(<SeatMap label="Seat map" seats={seats} onSelect={() => {}} />);
    const tabbable = screen.getAllByRole("button").filter((button) => button.tabIndex === 0);
    expect(tabbable).toHaveLength(1);
  });

  it("renders nothing without seats and explains the legend", () => {
    const { container } = render(<SeatMap label="Seat map" seats={[]} />);
    expect(container).toBeEmptyDOMElement();
    render(<SeatLegend />);
    expect(screen.getByRole("list", { name: "Seat legend" })).toHaveTextContent("Under maintenance");
  });
});
