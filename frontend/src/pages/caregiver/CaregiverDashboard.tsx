/**
 * What a caregiver sees.
 *
 * The contrast with the patient's dashboard is the point of the project, and
 * the screen says so out loud: the patient's own list holds every finding,
 * while this one holds only the serious ones. The server enforces that, not
 * this component - but the interface has to explain it, or a caregiver will
 * assume they are seeing everything and read the silence as "all is well".
 *
 * Nothing here can change the patient's record. A caregiver watches; they do
 * not log doses on someone else's behalf.
 */
import { useCallback, useEffect, useState } from "react";

import { consentApi } from "../../api/client";
import type {
  Adherence,
  CaregiverPatient,
  ConsentGrant,
  Dose,
  Finding,
} from "../../api/types";
import { Alert, Badge, Button, Card } from "../../components";
import { errorMessage } from "../../session/errors";
import { useSession } from "../../session/useSession";
import { doseLabel, doseTime, percent, timestamp } from "../dashboard/format";
import "../dashboard/dashboard.css";
import "./caregiver.css";

interface PatientView {
  findings: Finding[];
  doses: Dose[];
  adherence: Adherence | null;
}

function Invitations({ onChange }: { onChange: () => void }) {
  const [pending, setPending] = useState<ConsentGrant[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setPending(await consentApi.listGrants("PENDING"));
    } catch {
      /* An invitation list that fails to load is not worth an alarm on this
       * screen; the patients below are the important part. */
      setPending([]);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const grants = await consentApi.listGrants("PENDING");
        if (!cancelled) setPending(grants);
      } catch {
        if (!cancelled) setPending([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function respond(grant: ConsentGrant, accept: boolean) {
    setBusy(grant.id);
    try {
      if (accept) await consentApi.accept(grant.id);
      else await consentApi.revoke(grant.id);
      await load();
      onChange();
    } finally {
      setBusy(null);
    }
  }

  if (pending.length === 0) return null;

  return (
    <Card title="Invitations">
      <ul className="cg-invites">
        {pending.map((grant) => (
          <li key={grant.id}>
            <p className="cg-invites__who">
              <strong>{grant.patient.full_name}</strong> has asked you to help keep
              an eye on their medication.
            </p>
            <div className="cg-invites__actions">
              <Button onClick={() => void respond(grant, true)} disabled={busy === grant.id}>
                Accept
              </Button>
              <Button
                variant="secondary"
                onClick={() => void respond(grant, false)}
                disabled={busy === grant.id}
              >
                Decline
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/**
 * One patient's information.
 *
 * Mounted with `key={patient.id}`, so switching patients destroys this
 * component and builds a new one. That is deliberate: it guarantees the state
 * starts empty for the new patient, instead of briefly showing the previous
 * patient's findings under the new patient's name while the request is in
 * flight. On a screen about someone's medication, attributing one person's
 * data to another is the worst thing it could do.
 */
function PatientDetail({ patient }: { patient: CaregiverPatient }) {
  const [view, setView] = useState<PatientView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const [findings, doses, adherence] = await Promise.all([
          consentApi.patientFindings(patient.id),
          consentApi.patientDosesToday(patient.id),
          consentApi.patientAdherence(patient.id, 7),
        ]);
        if (!cancelled) {
          setView({ findings, doses, adherence });
          setError(null);
        }
      } catch (caught) {
        if (!cancelled) setError(errorMessage(caught));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [patient.id]);

  if (error) {
    return (
      <div className="dash-error" role="alert">
        <p className="dash-error__title">We could not load this patient</p>
        <p>{error}</p>
      </div>
    );
  }

  if (view === null) {
    return (
      <p className="dash-loading" role="status">
        Loading {patient.full_name}&rsquo;s information...
      </p>
    );
  }

  const missed = view.doses.filter((d) => d.status === "MISSED");

  return (
    <div className="cg-detail">
      <Card
        title="Serious safety alerts"
        action={
          <Badge tone={view.findings.length === 0 ? "success" : "severe"}>
            {view.findings.length === 0 ? "None" : `${view.findings.length}`}
          </Badge>
        }
      >
        {view.findings.length === 0 ? (
          <Alert level="success" title="Nothing serious to report">
            <p>
              No serious safety concerns for {patient.full_name.split(" ")[0]} right
              now.
            </p>
          </Alert>
        ) : (
          view.findings.map((finding) => (
            <Alert key={finding.id} level="severe" title={finding.title}>
              <p className="finding__detail">{finding.detail}</p>
              {finding.ai_explanation && (
                <div className="finding__ai">
                  <p className="finding__ai-label">In plain language</p>
                  <p>{finding.ai_explanation}</p>
                </div>
              )}
              <p className="finding__meta">
                {finding.medications.length > 0 && (
                  <span>Involves: {finding.medications.map((m) => m.name).join(", ")}</span>
                )}
                <span>
                  Source: {finding.source_name}
                  {finding.source_version ? ` ${finding.source_version}` : ""}
                </span>
                <span>Detected {timestamp(finding.detected_at)}</span>
                {finding.acknowledged_at && (
                  <span className="cg-read">
                    {patient.full_name.split(" ")[0]} has read this
                  </span>
                )}
              </p>
            </Alert>
          ))
        )}

        {/* Stated plainly, because a caregiver who assumes this list is
            everything would read a quiet screen as "nothing is wrong". */}
        <p className="cg-scope-note">
          You are shown serious findings only. {patient.full_name.split(" ")[0]} sees
          the full list, including minor ones, on their own account.
        </p>
      </Card>

      <div className="cg-detail__row">
        <Card title="Last 7 days">
          {view.adherence === null || view.adherence.rate === null ? (
            <p className="dash-empty">
              No doses have come due yet, so there is no adherence figure. This is
              not the same as a missed dose.
            </p>
          ) : (
            <div className="adherence">
              <p className="adherence__figure">
                <span className="adherence__value">{percent(view.adherence.rate)}</span>
                <span className="adherence__caption">of doses taken on time</span>
              </p>
              <div
                className="adherence__bar"
                aria-hidden="true"
                data-level={
                  view.adherence.rate >= 0.8
                    ? "good"
                    : view.adherence.rate >= 0.5
                      ? "fair"
                      : "low"
                }
              >
                <span style={{ width: `${Math.round(view.adherence.rate * 100)}%` }} />
              </div>
              <dl className="adherence__counts">
                <div>
                  <dt>Taken</dt>
                  <dd>{view.adherence.taken}</dd>
                </div>
                <div>
                  <dt>Missed</dt>
                  <dd>{view.adherence.missed}</dd>
                </div>
                <div>
                  <dt>Skipped</dt>
                  <dd>{view.adherence.skipped}</dd>
                </div>
              </dl>
            </div>
          )}
        </Card>

        <Card
          title="Today"
          action={
            missed.length > 0 ? (
              <Badge tone="severe">{missed.length} missed</Badge>
            ) : undefined
          }
        >
          {view.doses.length === 0 ? (
            <p className="dash-empty">
              Nothing recorded for today yet. Doses appear here once
              {" "}
              {patient.full_name.split(" ")[0]} opens their own app.
            </p>
          ) : (
            <ul className="dose-list">
              {view.doses.map((dose) => (
                <li key={dose.id} className="cg-dose">
                  <span className="cg-dose__time">{doseTime(dose.scheduled_for)}</span>
                  <span className="cg-dose__name">
                    {dose.medication_name}
                    {doseLabel(dose.dose_amount, dose.dose_unit) && (
                      <span className="dose-row__dose">
                        {" "}
                        {doseLabel(dose.dose_amount, dose.dose_unit)}
                      </span>
                    )}
                  </span>
                  <Badge
                    tone={
                      dose.status === "TAKEN"
                        ? "success"
                        : dose.status === "MISSED"
                          ? "severe"
                          : dose.status === "DUE"
                            ? "moderate"
                            : dose.status === "SKIPPED"
                              ? "mild"
                              : "neutral"
                    }
                  >
                    {dose.status === "SCHEDULED"
                      ? "Later today"
                      : dose.status.charAt(0) + dose.status.slice(1).toLowerCase()}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

export function CaregiverDashboard() {
  const { user, logOut } = useSession();
  const [patients, setPatients] = useState<CaregiverPatient[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadPatients = useCallback(async () => {
    try {
      const list = await consentApi.myPatients();
      setPatients(list);
      setError(null);
      setSelectedId((current) =>
        current && list.some((p) => p.id === current) ? current : (list[0]?.id ?? null),
      );
    } catch (caught) {
      setError(errorMessage(caught));
      setPatients([]);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const list = await consentApi.myPatients();
        if (!cancelled) {
          setPatients(list);
          setSelectedId(list[0]?.id ?? null);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(errorMessage(caught));
          setPatients([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = patients?.find((p) => p.id === selectedId) ?? null;

  return (
    <div className="dash">
      <a className="sr-only dash-skip" href="#cg-main">
        Skip to content
      </a>

      <header className="dash-header">
        <div className="dash-header__brand">
          <span className="dash-header__mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" fill="none">
              <path
                d="M16 3 27 7v8c0 7-11 14-11 14S5 22 5 15V7l11-4Z"
                stroke="currentColor"
                strokeWidth="2"
              />
              <path
                d="M16 10v12m-6-6h12"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </span>
          <span className="dash-header__name">SafeMed</span>
        </div>
        <div className="dash-header__account">
          {user && (
            <span className="dash-header__who">
              {user.full_name}
              <span className="dash-header__role">Caregiver</span>
            </span>
          )}
          <button type="button" className="dash-header__out" onClick={logOut}>
            Log out
          </button>
        </div>
      </header>

      <main id="cg-main" className="dash-main">
        <div className="dash-greeting">
          <h1>Hello, {user?.full_name?.split(" ")[0] ?? ""}.</h1>
          <p>The people you help look after.</p>
        </div>

        {error && (
          <div className="dash-error" role="alert">
            <p className="dash-error__title">We could not load your patients</p>
            <p>{error}</p>
            <button type="button" onClick={() => void loadPatients()}>
              Try again
            </button>
          </div>
        )}

        <div className="cg-layout">
          <Invitations onChange={() => void loadPatients()} />

          {patients === null ? (
            <p className="dash-loading" role="status">
              Loading...
            </p>
          ) : patients.length === 0 ? (
            <Card title="No one yet">
              <p className="dash-empty">
                You are not currently linked to anyone. A patient invites you from
                their own account, and the invitation will appear here for you to
                accept.
              </p>
            </Card>
          ) : (
            <>
              {patients.length > 1 && (
                <nav className="cg-tabs" aria-label="Patients">
                  {patients.map((patient) => (
                    <button
                      key={patient.id}
                      type="button"
                      className="cg-tabs__item"
                      aria-current={patient.id === selectedId ? "true" : undefined}
                      onClick={() => setSelectedId(patient.id)}
                    >
                      {patient.full_name}
                    </button>
                  ))}
                </nav>
              )}

              {selected && (
                <>
                  <p className="cg-since">
                    Viewing <strong>{selected.full_name}</strong>
                    {selected.granted_at
                      ? ` - access granted ${timestamp(selected.granted_at)}`
                      : ""}
                  </p>
                  <PatientDetail key={selected.id} patient={selected} />
                </>
              )}
            </>
          )}
        </div>
      </main>

      <footer className="dash-footer">
        <span>SafeMed</span>
        <span>
          Not a medical device. Does not diagnose or prescribe. Always speak to a
          doctor or pharmacist.
        </span>
      </footer>
    </div>
  );
}
