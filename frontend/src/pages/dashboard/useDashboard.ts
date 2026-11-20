/**
 * Loads everything the dashboard shows, and exposes one way to reload it.
 *
 * All four requests go out together rather than in sequence, so the screen
 * fills in one round trip's worth of time instead of four.
 *
 * Why a single reload() for the whole dashboard: the parts are not
 * independent. Adding a medication makes the backend re-run the safety
 * engine, so the findings list changes too; confirming a dose changes the
 * adherence rate. Refreshing only the list that was touched would leave the
 * rest of the screen quietly stale - and on a safety screen, stale is worse
 * than a slightly heavier refresh.
 */
import { useCallback, useEffect, useState } from "react";

import { api } from "../../api/client";
import type { Adherence, Dose, Finding, Medication } from "../../api/types";
import { errorMessage } from "../../session/errors";

interface DashboardData {
  doses: Dose[];
  adherence: Adherence | null;
  findings: Finding[];
  medications: Medication[];
}

const EMPTY: DashboardData = {
  doses: [],
  adherence: null,
  findings: [],
  medications: [],
};

/** The requests, with no React state involved, so both the first load and a
 *  manual reload share exactly one definition of "fetch the dashboard". */
async function fetchAll(): Promise<DashboardData> {
  const [doses, adherence, findings, medications] = await Promise.all([
    api.dosesToday(),
    api.adherence(7),
    api.listFindings(),
    api.listMedications("ACTIVE"),
  ]);
  return { doses, adherence, findings, medications };
}

export function useDashboard() {
  const [data, setData] = useState<DashboardData>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /* The reload path, for after a dose is confirmed or a medication added. */
  const reload = useCallback(async () => {
    try {
      setData(await fetchAll());
      setError(null);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  /* The first load is written out here rather than calling reload(), for two
   * reasons: every setState is visibly after an await, and the `cancelled`
   * flag stops a response that arrives after the component has gone from
   * setting state on something unmounted. React's StrictMode mounts effects
   * twice in development, so this path really does run twice. */
  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const next = await fetchAll();
        if (!cancelled) {
          setData(next);
          setError(null);
        }
      } catch (caught) {
        if (!cancelled) setError(errorMessage(caught));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return { ...data, loading, error, reload };
}
