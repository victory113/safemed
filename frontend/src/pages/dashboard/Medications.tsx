/**
 * The patient's medication list, and the form for adding to it.
 *
 * Two things this list makes visible on purpose:
 *
 * - Whether RxNorm resolved the name. A medication with no RXCUI is still
 *   checked, but by name only, which is weaker. Saying so is more honest than
 *   letting a patient assume every entry is understood equally well.
 * - "Stop", not "Delete". The backend marks a medication stopped and keeps the
 *   record, because the doses already logged against it are part of this
 *   person's history.
 */
import { useState } from "react";
import type { FormEvent } from "react";

import { api } from "../../api/client";
import type { Medication } from "../../api/types";
import { Badge, Button, Card, Input } from "../../components";
import { errorMessage } from "../../session/errors";

/**
 * "08:00, 20:00" or "8 20:30" -> ["08:00", "20:30"]
 *
 * Deliberately forgiving about separators and missing leading zeros, because
 * this is typed by someone reading a pill bottle, not an API client. Anything
 * that is not a real time of day is dropped, and the caller notices that the
 * result is empty and says so rather than silently saving nothing.
 */
function parseTimes(raw: string): string[] {
  return raw
    .split(/[,\s]+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const [h, m = "0"] = part.split(":");
      const hour = Number(h);
      const minute = Number(m);
      if (!Number.isInteger(hour) || hour < 0 || hour > 23) return null;
      if (!Number.isInteger(minute) || minute < 0 || minute > 59) return null;
      return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
    })
    .filter((value): value is string => value !== null);
}

function AddMedication({ onAdded }: { onAdded: () => void }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);

    const name = String(data.get("name_entered") ?? "").trim();
    if (!name) {
      setError("Please enter the medication name.");
      return;
    }

    const rawTimes = String(data.get("times") ?? "");
    const times = parseTimes(rawTimes);
    if (rawTimes.trim() && times.length === 0) {
      setError("Times should look like 08:00, or 08:00, 20:00 for twice a day.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await api.addMedication({
        name_entered: name,
        dose_amount: String(data.get("dose_amount") ?? "").trim() || null,
        dose_unit: String(data.get("dose_unit") ?? "").trim() || null,
        ndc: String(data.get("ndc") ?? "").trim() || null,
        times,
      });
      form.reset();
      setOpen(false);
      onAdded();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return <Button onClick={() => setOpen(true)}>Add a medication</Button>;
  }

  return (
    <form className="med-form" onSubmit={submit} noValidate>
      <Input
        label="Medication name"
        name="name_entered"
        required
        autoFocus
        placeholder="e.g. Warfarin"
        hint="The name on the label is fine. We match it to a standard name for you."
      />

      <div className="med-form__row">
        <Input label="Amount" name="dose_amount" placeholder="5" />
        <Input label="Unit" name="dose_unit" placeholder="mg" />
      </div>

      <Input
        label="Times you take it"
        name="times"
        placeholder="08:00, 20:00"
        hint="24-hour times, separated by commas. Leave blank if you take it only as needed."
      />

      <Input
        label="NDC number (optional)"
        name="ndc"
        placeholder="0310-6225-30"
        hint="Printed on the box. It lets us tell a recall of your exact product from a recall of the same drug made by someone else."
      />

      {error && (
        <p className="dash-inline-error" role="alert">
          {error}
        </p>
      )}

      <div className="med-form__actions">
        <Button type="submit" disabled={saving}>
          {saving ? "Saving..." : "Save medication"}
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            setOpen(false);
            setError(null);
          }}
        >
          Cancel
        </Button>
      </div>
    </form>
  );
}

export function Medications({
  medications,
  onChange,
}: {
  medications: Medication[];
  onChange: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);

  async function stop(medication: Medication) {
    setBusy(medication.id);
    try {
      await api.stopMedication(medication.id);
      onChange();
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card title="Your medications" action={<AddMedication onAdded={onChange} />}>
      {medications.length === 0 ? (
        <p className="dash-empty">
          You have not added any medications yet. Add one and SafeMed will start
          checking it against known interactions and FDA recalls.
        </p>
      ) : (
        <ul className="med-list">
          {medications.map((medication) => (
            <li key={medication.id} className="med-row">
              <div className="med-row__main">
                <span className="med-row__name">{medication.name_entered}</span>
                {medication.dose_amount && (
                  <span className="med-row__dose">
                    {medication.dose_amount} {medication.dose_unit ?? ""}
                  </span>
                )}
              </div>

              <div className="med-row__tags">
                {medication.rxcui ? (
                  <Badge tone="success">
                    Matched
                    {medication.normalized_name ? `: ${medication.normalized_name}` : ""}
                  </Badge>
                ) : (
                  <Badge tone="mild">Checked by name only</Badge>
                )}
                {medication.ndc && <Badge tone="neutral">NDC {medication.ndc}</Badge>}
              </div>

              <Button
                variant="secondary"
                onClick={() => void stop(medication)}
                disabled={busy === medication.id}
                aria-label={`Stop taking ${medication.name_entered}`}
              >
                Stop
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
