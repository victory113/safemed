/**
 * The session context object and its shape.
 *
 * This lives apart from the provider component so that the hook, the provider
 * and the type can each be imported without dragging a component along.
 * React Fast Refresh only works on files that export components *only*, so
 * mixing a context, a hook and a component in one file breaks hot reloading
 * for every file that imports it.
 */
import { createContext } from "react";

import type { User } from "../api/types";

export interface SessionValue {
  user: User | null;
  /** True until a stored token has been checked against the API. */
  loading: boolean;
  logIn: (email: string, password: string) => Promise<User>;
  signUp: (
    fullName: string,
    email: string,
    password: string,
    role: string,
  ) => Promise<User>;
  logOut: () => void;
}

export const SessionContext = createContext<SessionValue | null>(null);
