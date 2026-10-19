/** Helpers shared by the forms (UI_ARCHITECTURE.md 7: server `details` map onto fields, the rest goes in an Alert). */

import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

import { ApiError, userMessage } from "./errors";

/**
 * Put the server's field errors on their fields and focus the first one. Returns the message for
 * an Alert above the submit button, or null when every problem was attached to a field.
 *
 * `codeFields` maps an error code to a field, e.g. { EMAIL_TAKEN: "email" }.
 */
export function applyServerError<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fields: readonly Path<T>[],
  codeFields: Record<string, Path<T>> = {},
): string | null {
  if (!(error instanceof ApiError)) return userMessage(error);

  let attached = 0;
  for (const [name, messages] of Object.entries(error.details ?? {})) {
    if ((fields as readonly string[]).includes(name) && messages.length > 0) {
      setError(name as Path<T>, { type: "server", message: messages[0] }, { shouldFocus: attached === 0 });
      attached += 1;
    }
  }
  const mapped = codeFields[error.code];
  if (mapped) {
    setError(mapped, { type: "server", message: userMessage(error) }, { shouldFocus: attached === 0 });
    return null;
  }
  if (attached > 0 && error.code === "VALIDATION_ERROR") return null;
  return userMessage(error);
}
