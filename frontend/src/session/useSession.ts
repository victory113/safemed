import { useContext } from "react";

import { SessionContext } from "./context";
import type { SessionValue } from "./context";

/**
 * Who is signed in.
 *
 * Throws rather than returning null when used outside the provider. A silent
 * null would surface much later as "why is the user always signed out", which
 * is far harder to trace than an error naming the actual mistake.
 */
export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (value === null) {
    throw new Error("useSession must be used inside <SessionProvider>");
  }
  return value;
}
