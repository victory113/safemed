import { ApiError } from "../api/client";

/**
 * Turn an unknown thrown value into something safe to show a person.
 *
 * `catch` gives us `unknown` - it can be anything - so this narrows it down
 * and falls back to a plain sentence rather than rendering "[object Object]"
 * or an internal stack trace to a patient.
 */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}
