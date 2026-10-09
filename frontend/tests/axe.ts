import axe from "axe-core";
import { expect } from "vitest";

/** Fails the test if axe finds accessibility violations (colour contrast is not computable in jsdom). */
export async function expectNoAxeViolations(container: Element): Promise<void> {
  const results = await axe.run(container, {
    rules: { "color-contrast": { enabled: false }, region: { enabled: false } },
  });
  const summary = results.violations.map((violation) => `${violation.id}: ${violation.help}`);
  expect(summary).toEqual([]);
}
