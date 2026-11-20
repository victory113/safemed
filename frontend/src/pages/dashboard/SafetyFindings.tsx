/**
 * Safety findings - the part of SafeMed that justifies the project.
 *
 * Three decisions worth understanding, because each one is there to stop the
 * screen doing harm:
 *
 * 1. SEVERE findings are shown expanded and first; the rest collapse into a
 *    quieter list. Our own seed data produces ten findings from five
 *    medications, and a wall of ten equally loud warnings trains people to
 *    ignore all of them. Severity routing is the feature, so the UI has to
 *    show it.
 *
 * 2. `detail` always renders. `ai_explanation` is shown as an *addition* when
 *    it exists, clearly labelled as a plain-language rewrite. The AI never
 *    replaces the deterministic text, so a finding is complete and correct
 *    even when the AI layer is off, unavailable, or its output was rejected by
 *    the guardrails.
 *
 * 3. Every finding states where it came from, and a POSSIBLE recall match
 *    says "check the label" instead of asserting the patient is affected.
 */
import { useState } from "react";

import { api } from "../../api/client";
import type { Finding, Severity } from "../../api/types";
import { Alert, Badge, Button, Card } from "../../components";
import { timestamp } from "./format";

const SEVERITY_RANK: Record<Severity, number> = { SEVERE: 0, MODERATE: 1, MILD: 2 };

const SEVERITY_WORD: Record<Severity, string> = {
  SEVERE: "Serious",
  MODERATE: "Moderate",
  MILD: "Minor",
};

const TYPE_WORD = {
  INTERACTION: "Interaction",
  RECALL: "Recall",
  DUPLICATE_THERAPY: "Duplicate",
} as const;

function sourceLine(finding: Finding): string {
  const version = finding.source_version ? ` ${finding.source_version}` : "";
  return `Source: ${finding.source_name}${version}`;
}

function FindingBody({ finding }: { finding: Finding }) {
  return (
    <>
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
        <span>{sourceLine(finding)}</span>
        <span>Detected {timestamp(finding.detected_at)}</span>
      </p>
    </>
  );
}

export function SafetyFindings({
  findings,
  onChange,
}: {
  findings: Finding[];
  onChange: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [rechecking, setRechecking] = useState(false);

  const open = findings
    .filter((f) => f.status === "OPEN")
    .sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]);

  const severe = open.filter((f) => f.severity === "SEVERE");
  const lesser = open.filter((f) => f.severity !== "SEVERE");
  const acknowledged = findings.filter((f) => f.status !== "OPEN");

  async function acknowledge(id: string) {
    setBusy(id);
    try {
      await api.acknowledgeFinding(id);
      onChange();
    } finally {
      setBusy(null);
    }
  }

  async function recheck() {
    setRechecking(true);
    try {
      await api.reEvaluate();
      onChange();
    } finally {
      setRechecking(false);
    }
  }

  return (
    <Card
      title="Safety checks"
      action={
        <Button variant="secondary" onClick={() => void recheck()} disabled={rechecking}>
          {rechecking ? "Checking..." : "Check again"}
        </Button>
      }
    >
      {open.length === 0 && (
        <Alert level="success" title="No safety concerns found">
          <p>
            Your current medications were checked against known interactions and
            FDA recalls. Nothing needs your attention right now.
          </p>
        </Alert>
      )}

      {severe.map((finding) => (
        <div key={finding.id} className="finding finding--severe">
          <Alert level="severe" title={finding.title}>
            <FindingBody finding={finding} />
            <Button
              variant="secondary"
              onClick={() => void acknowledge(finding.id)}
              disabled={busy === finding.id}
            >
              I have read this
            </Button>
          </Alert>
        </div>
      ))}

      {lesser.length > 0 && (
        <div className="finding-group">
          <h3 className="finding-group__title">
            Also worth knowing <span className="finding-group__count">({lesser.length})</span>
          </h3>
          <p className="finding-group__note">
            These are recorded for completeness. They are not urgent, and they are
            not sent to your caregiver.
          </p>
          <ul className="finding-list">
            {lesser.map((finding) => (
              <li key={finding.id} className="finding finding--quiet">
                <div className="finding__head">
                  <Badge tone={finding.severity === "MODERATE" ? "moderate" : "mild"}>
                    {SEVERITY_WORD[finding.severity]}
                  </Badge>
                  <Badge tone="neutral">{TYPE_WORD[finding.finding_type]}</Badge>
                  {finding.recall_match === "POSSIBLE" && (
                    <Badge tone="mild">Check the label</Badge>
                  )}
                  <span className="finding__title">{finding.title}</span>
                </div>
                <FindingBody finding={finding} />
                <Button
                  variant="secondary"
                  onClick={() => void acknowledge(finding.id)}
                  disabled={busy === finding.id}
                >
                  I have read this
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {acknowledged.length > 0 && (
        <details className="finding-archive">
          <summary>{acknowledged.length} already read</summary>
          <ul className="finding-list">
            {acknowledged.map((finding) => (
              <li key={finding.id} className="finding finding--read">
                <span className="finding__title">{finding.title}</span>
                <span className="finding__meta">
                  {finding.acknowledged_at
                    ? `Read ${timestamp(finding.acknowledged_at)}`
                    : finding.status}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}

      <p className="finding-disclaimer">
        SafeMed does not diagnose or prescribe, and never tells you to change or
        stop a medication. Talk to your doctor or pharmacist before changing
        anything.
      </p>
    </Card>
  );
}
