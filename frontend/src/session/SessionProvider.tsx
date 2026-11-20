/**
 * Who is signed in, for the whole app.
 *
 * The token lives in localStorage so a refresh does not sign you out. The
 * *user* is never read from storage - it is fetched from /auth/me. That
 * difference matters: a stored user object would let a stale or tampered copy
 * decide what the UI shows, whereas asking the API means the server decides,
 * every time. A rejected token logs you out rather than leaving the app in a
 * half-signed-in state.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { api, readToken, writeToken } from "../api/client";
import type { User } from "../api/types";
import { SessionContext } from "./context";

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  /* Initialised from whether a token exists, rather than set inside the
   * effect below. With no token there is nothing to verify, so the app is
   * ready immediately - and it avoids a synchronous setState in an effect,
   * which would cost an extra render pass on every load. */
  const [loading, setLoading] = useState(() => readToken() !== null);

  useEffect(() => {
    /* No token: `loading` already started false, so there is nothing to do
     * and nothing to set. */
    if (!readToken()) return;

    let cancelled = false;

    api
      .me()
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch(() => {
        /* Expired, revoked, or the API is unreachable. Either way we are not
         * signed in, so drop the token rather than keep a useless one. */
        writeToken(null);
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const logIn = useCallback(async (email: string, password: string) => {
    const token = await api.login({ email, password });
    writeToken(token.access_token);
    try {
      const me = await api.me();
      setUser(me);
      return me;
    } catch (error) {
      /* We hold a token we cannot use. Dropping it avoids a stuck state where
       * the app believes it is signed in but every request fails. */
      writeToken(null);
      throw error;
    }
  }, []);

  const signUp = useCallback(
    async (fullName: string, email: string, password: string, role: string) => {
      await api.register({ email, password, full_name: fullName, role });
      /* Registering does not sign you in - /register returns the user, not a
       * token - so log in straight afterwards. To the person filling in the
       * form it is one step, which is what they expect. */
      return logIn(email, password);
    },
    [logIn],
  );

  const logOut = useCallback(() => {
    writeToken(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, logIn, signUp, logOut }),
    [user, loading, logIn, signUp, logOut],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
