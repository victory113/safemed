/**
 * Display helpers for the dashboard.
 *
 * A NOTE ON TIME ZONES, because it looks like a bug otherwise.
 *
 * The backend stores a schedule as a wall-clock `time_of_day` and builds each
 * dose timestamp by combining it with a date in UTC. So a patient who asks for
 * 08:00 gets a dose stamped 08:00Z. There is no per-user time zone in the data
 * model yet.
 *
 * Given that, we format these timestamps in UTC rather than in the browser's
 * zone. Converting would show "8:00 AM" as "2:00 AM" to anyone in US Central -
 * the number the patient typed would not be the number they see back, which
 * reads as broken. Formatting as UTC keeps what they entered and what they
 * read identical.
 *
 * The real fix is a time zone on the user record, so 08:00 means 08:00 where
 * they live. Until then this is the honest presentation of what is stored.
 */

export function doseTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
  });
}

export function doseDay(iso: string): string {
  return new Date(iso).toLocaleDateString([], {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** "2 Nov, 3:04 PM" - for when a finding was detected. */
export function timestamp(iso: string): string {
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function doseLabel(amount: string | null, unit: string | null): string {
  if (!amount) return "";
  return unit ? `${amount} ${unit}` : amount;
}

/** 0.875 -> "88%". Null is the caller's problem, deliberately. */
export function percent(rate: number): string {
  return `${Math.round(rate * 100)}%`;
}
