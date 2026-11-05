import { useState } from "react";
import { Alert, Badge, Button, Card, Input } from "../components";

/**
 * The team's reference page for the design system.
 *
 * Every component appears here with every variant. Before building a screen,
 * look here first - if something already exists, use it rather than writing
 * new CSS. That is what keeps the app looking like one product.
 */
export function StyleGuide() {
  const [email, setEmail] = useState("");

  return (
    <main className="app-container">
      <h1>SafeMed Design System</h1>
      <p style={{ color: "var(--color-text-muted)" }}>
        Shared components and styles. Build screens from these rather than
        writing new CSS.
      </p>

      <Card title="Buttons">
        <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", marginBottom: "1rem" }}>
          <Button variant="primary">Save medication</Button>
          <Button variant="secondary">Cancel</Button>
          <Button variant="danger">Stop medication</Button>
          <Button variant="primary" disabled>
            Disabled
          </Button>
        </div>
        <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
          <Button size="lg">Large - primary action</Button>
        </div>
        <p style={{ marginTop: "1rem", color: "var(--color-text-muted)" }}>
          Minimum height is 44px. Use the large size for the main action on a
          patient-facing screen.
        </p>
      </Card>

      <Card title="Form fields">
        <Input
          label="Email address"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          hint="We use this to sign you in."
        />
        <Input
          label="Medication name"
          placeholder="e.g. Metformin"
          hint="Type the name exactly as it appears on the bottle."
        />
        <Input
          label="Dose amount"
          defaultValue="abc"
          error="Enter a number, for example 500."
        />
      </Card>

      <Card
        title="Safety alerts"
        action={<Badge tone="severe">1 needs attention</Badge>}
      >
        <Alert level="severe" title="Potential interaction detected">
          <p>
            Warfarin and Aspirin may interact in a way that increases bleeding
            risk. Source: DDInter v2.0.
          </p>
          <p>
            <strong>
              Contact your pharmacist or healthcare provider. Do not stop or
              change a medication based on this message.
            </strong>
          </p>
        </Alert>

        <Alert level="moderate" title="Recall may affect your medication">
          Metformin from one manufacturer has been recalled. Check whether your
          bottle says Teva.
        </Alert>

        <Alert level="mild" title="Duplicate entry">
          Ibuprofen appears twice in your medication list.
        </Alert>

        <Alert level="success" title="Dose recorded">
          Metformin 500mg marked as taken at 8:04 AM.
        </Alert>
      </Card>

      <Card title="Status badges">
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <Badge tone="success">Taken</Badge>
          <Badge tone="neutral">Scheduled</Badge>
          <Badge tone="moderate">Due now</Badge>
          <Badge tone="severe">Missed</Badge>
          <Badge tone="mild">Mild</Badge>
        </div>
      </Card>

      <Card title="Type scale">
        <h1>Heading 1 - 36px</h1>
        <h2>Heading 2 - 28px</h2>
        <h3>Heading 3 - 22px</h3>
        <p>
          Body text is 18px, not the usual 16px, because many of our users are
          older adults. Line height is generous and lines are capped at about
          68 characters, which makes long passages easier to track.
        </p>
        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>
          Small text - 16px. Used for hints and captions, never for important
          information.
        </p>
      </Card>

      <Card title="Accessibility rules we follow">
        <ul>
          <li>Every interactive element is reachable and usable by keyboard.</li>
          <li>Focus is always visible - press Tab on this page to see it.</li>
          <li>Colour is never the only way meaning is conveyed.</li>
          <li>Every input has a real label, not just a placeholder.</li>
          <li>Text and background meet WCAG AA contrast (4.5:1 or better).</li>
          <li>Touch targets are at least 44px tall.</li>
        </ul>
      </Card>
    </main>
  );
}
