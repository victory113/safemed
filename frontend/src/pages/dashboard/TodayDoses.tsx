/**
 * The daily check-in: "I took my medication".
 *
 * This is the feature a patient touches every day, so the two buttons are
 * full size and the status is stated in words next to a coloured badge rather
 * than by colour alone.
 */
import { useState } from "react";

import { ApiError, api } from "../../api/client";
import type { Dose, DoseStatus } from "../../api/types";
import { Badge, Button, Card } from "../../components";
import { doseLabel, doseTime } from "./format";

/* Wording shown to the patient. "Missed" is stated plainly - softening it
 * would defeat the point of tracking it. */
const STATUS_TEXT: Record<DoseStatus, string> = {
  SCHEDULED: "Later today",
  DUE: "Due now",
  TAKEN: "Taken",
  MISSED: "Missed",
  SKIPPED: "Skipped",
};

const STATUS_TONE: Record<DoseStatus, "mild" | "moderate" | "severe" | "success" | "neutral"> = {
  SCHEDULED: "neutral",
  DUE: "moderate",
  TAKEN: "success",
  MISSED: "severe",
  SKIPPED: "mild",
};

/** TAKEN and SKIPPED are final on the backend, so there is nothing to press. */
function isResolved(status: DoseStatus): boolean {
  return status === "TAKEN" || status === "SKIPPED";
}

export function TodayDoses({ doses, onChange }: { doses: Dose[]; onChange: () => void }) {
  /* Which row is mid-request, so only that row's buttons go disabled rather
   * than the whole list. */
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function act(dose: Dose, action: "confirm" | "skip") {
    setBusyId(dose.id);
    setError(null);
    try {
      if (action === "confirm") await api.confirmDose(dose.id);
      else await api.skipDose(dose.id);
      onChange();
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        /* Already logged - most likely a double tap, or a caregiver recorded
         * it. Not an error worth alarming anyone about, so reload to show the
         * truth instead of complaining. */
        onChange();
      } else {
        setError(
          caught instanceof Error ? caught.message : "Could not save that. Please try again.",
        );
      }
    } finally {
      setBusyId(null);
    }
  }

  const remaining = doses.filter((d) => !isResolved(d.status)).length;

  return (
    <Card
      title="Today's medication"
      action={
        doses.length > 0 ? (
          <Badge tone={remaining === 0 ? "success" : "neutral"}>
            {remaining === 0 ? "All logged" : `${remaining} to log`}
          </Badge>
        ) : undefined
      }
    >
      {error && (
        <p className="dash-inline-error" role="alert">
          {error}
        </p>
      )}

      {doses.length === 0 ? (
        <p className="dash-empty">
          Nothing scheduled for today. Add a medication below and include the
          times you take it, and it will appear here.
        </p>
      ) : (
        <ul className="dose-list">
          {doses.map((dose) => (
            <li key={dose.id} className={`dose-row dose-row--${dose.status.toLowerCase()}`}>
              <div className="dose-row__when">
                <span className="dose-row__time">{doseTime(dose.scheduled_for)}</span>
                <Badge tone={STATUS_TONE[dose.status]}>{STATUS_TEXT[dose.status]}</Badge>
              </div>

              <div className="dose-row__what">
                <span className="dose-row__name">{dose.medication_name}</span>
                {doseLabel(dose.dose_amount, dose.dose_unit) && (
                  <span className="dose-row__dose">
                    {doseLabel(dose.dose_amount, dose.dose_unit)}
                  </span>
                )}
              </div>

              <div className="dose-row__actions">
                {isResolved(dose.status) ? (
                  <span className="dose-row__done">
                    {dose.status === "TAKEN" ? "Logged" : "Skipped"}
                  </span>
                ) : (
                  <>
                    <Button
                      onClick={() => void act(dose, "confirm")}
                      disabled={busyId === dose.id}
                      aria-label={`Record that you took ${dose.medication_name} at ${doseTime(dose.scheduled_for)}`}
                    >
                      I took it
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => void act(dose, "skip")}
                      disabled={busyId === dose.id}
                      aria-label={`Record that you skipped ${dose.medication_name} at ${doseTime(dose.scheduled_for)}`}
                    >
                      Skip
                    </Button>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
