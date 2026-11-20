/**
 * The patient's side of consent: who can see their information.
 *
 * Consent is the patient's to give and to take back, so this lives on their
 * dashboard rather than being something arranged for them. Two details that
 * follow from that:
 *
 * - Revoking is always available, in one click, with no confirmation step
 *   asking them to justify it. Withdrawing consent should never be harder
 *   than giving it.
 * - A revoked caregiver is still listed, greyed out, rather than vanishing.
 *   The record of who had access and when is part of what makes consent
 *   meaningful, and the patient is entitled to see it.
 */
import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import { consentApi } from "../../api/client";
import type { ConsentGrant } from "../../api/types";
import { Badge, Button, Card, Input } from "../../components";
import { errorMessage } from "../../session/errors";
import { timestamp } from "./format";

const STATUS_WORD = {
  PENDING: "Invited",
  ACTIVE: "Can see your information",
  REVOKED: "Access removed",
} as const;

const STATUS_TONE = {
  PENDING: "mild",
  ACTIVE: "success",
  REVOKED: "neutral",
} as const;

export function Caregivers() {
  const [grants, setGrants] = useState<ConsentGrant[] | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setGrants(await consentApi.listGrants());
      setError(null);
    } catch (caught) {
      setError(errorMessage(caught));
      setGrants([]);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const list = await consentApi.listGrants();
        if (!cancelled) setGrants(list);
      } catch (caught) {
        if (!cancelled) {
          setError(errorMessage(caught));
          setGrants([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const email = String(new FormData(form).get("caregiver_email") ?? "").trim();
    if (!email) {
      setError("Please enter their email address.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await consentApi.invite(email);
      form.reset();
      setOpen(false);
      await load();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  async function revoke(grant: ConsentGrant) {
    setBusy(grant.id);
    try {
      await consentApi.revoke(grant.id);
      await load();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card
      title="Who can see this"
      action={
        !open && (
          <Button onClick={() => setOpen(true)}>Invite someone</Button>
        )
      }
    >
      {open && (
        <form className="med-form" onSubmit={invite} noValidate>
          <Input
            label="Their email address"
            name="caregiver_email"
            type="email"
            autoComplete="email"
            autoCapitalize="none"
            spellCheck={false}
            required
            autoFocus
            placeholder="them@example.com"
            hint="They need a SafeMed caregiver account already. They will be asked to accept before they can see anything."
          />
          <div className="med-form__actions">
            <Button type="submit" disabled={saving}>
              {saving ? "Sending..." : "Send invitation"}
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
      )}

      {error && (
        <p className="dash-inline-error" role="alert">
          {error}
        </p>
      )}

      {grants === null ? (
        <p className="dash-empty">Loading...</p>
      ) : grants.length === 0 ? (
        <p className="dash-empty">
          Nobody else can see your information. If you would like a family member
          or carer to be told about serious safety alerts, you can invite them.
        </p>
      ) : (
        <ul className="med-list">
          {grants.map((grant) => (
            <li
              key={grant.id}
              className={`med-row${grant.status === "REVOKED" ? " med-row--past" : ""}`}
            >
              <div className="med-row__main">
                <span className="med-row__name">{grant.caregiver.full_name}</span>
                <span className="med-row__dose">{grant.caregiver.email}</span>
              </div>

              <div className="med-row__tags">
                <Badge tone={STATUS_TONE[grant.status]}>
                  {STATUS_WORD[grant.status]}
                </Badge>
                {grant.status === "ACTIVE" && grant.granted_at && (
                  <span className="med-row__dose">since {timestamp(grant.granted_at)}</span>
                )}
                {grant.status === "REVOKED" && grant.revoked_at && (
                  <span className="med-row__dose">
                    removed {timestamp(grant.revoked_at)}
                  </span>
                )}
              </div>

              {grant.status !== "REVOKED" && (
                <Button
                  variant="secondary"
                  onClick={() => void revoke(grant)}
                  disabled={busy === grant.id}
                  aria-label={`Remove ${grant.caregiver.full_name}'s access to your information`}
                >
                  {grant.status === "PENDING" ? "Cancel" : "Remove access"}
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      <p className="finding-disclaimer">
        Anyone you add is shown serious safety alerts and whether you have been
        taking your medication. They cannot change anything, and you can remove
        their access at any time.
      </p>
    </Card>
  );
}
