/* SafeMed — final capstone presentation deck.
 * Build:  node build.js
 */
const pptxgen = require("pptxgenjs");
const path = require("path");
// applyTheme writes the theme palette into the generated file. It ships with
// Claude's pptx skill; if it is not present the deck still builds and simply
// falls back to Office's stock scheme colours for the few placeholder
// defaults that use them. Set PPTX_SKILL to its scripts directory to enable.
let applyTheme = null;
try {
  const skill = process.env.PPTX_SKILL ||
    "C:/Users/Owner/AppData/Local/Claude-Data/claude_pzs8sxrjxfjjc/local-agent-mode-sessions/skills-plugin/d2617960-7d72-4f58-9973-44e5e8edcdef/7a028dd0-1756-46e8-b639-5b06d8d760a3/skills/pptx/scripts";
  ({ applyTheme } = require(skill + "/apply_theme.js"));
} catch {
  console.warn("apply_theme.js not found - building without theme colours.");
}

const THEME = {
  name: "SafeMed",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "16232B",
    lt1: "FFFFFF",
    dk2: "0B3B5C",
    lt2: "EDF4F7",
    accent1: "028090",
    accent2: "02C39A",
    accent3: "C9A227",
    accent4: "B23A48",
    accent5: "5A7A8A",
    accent6: "6D8B74",
    hlink: "028090",
    folHlink: "5A7A8A",
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.author = "Victory Orobosa, Chima Onochie, Pacifique Mugisha";
pres.title = "SafeMed - Final Capstone Presentation";
pres.subject = "CSCI 4490 Software Engineering, Fall 2026";

const C = pres.SchemeColor;
const W = 13.3;
const H = 7.5;
const M = 0.7; // side margin

/* ---------------- layouts ---------------- */

pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: THEME.colors.dk2 },
  objects: [
    {
      placeholder: {
        options: { name: "title", type: "title", x: M, y: 2.3, w: W - 2 * M, h: 1.5,
          fontSize: 44, bold: true, color: C.background1, align: "left" },
        text: "",
      },
    },
    {
      placeholder: {
        options: { name: "body", type: "body", x: M, y: 3.9, w: W - 2 * M, h: 2.2,
          fontSize: 16, color: THEME.colors.lt2, align: "left" },
        text: "",
      },
    },
  ],
});

pres.defineSlideMaster({
  title: "SECTION",
  background: { color: THEME.colors.accent1 },
  objects: [
    {
      placeholder: {
        options: { name: "title", type: "title", x: M, y: 3.0, w: W - 2 * M, h: 1.3,
          fontSize: 40, bold: true, color: C.background1, align: "left" },
        text: "",
      },
    },
    {
      placeholder: {
        options: { name: "body", type: "body", x: M, y: 4.3, w: W - 2 * M, h: 1.0,
          fontSize: 17, color: "DFF3F0", align: "left" },
        text: "",
      },
    },
  ],
});

// Light content slide: title at a fixed height on every one.
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  objects: [
    {
      placeholder: {
        options: { name: "title", type: "title", x: M, y: 0.45, w: W - 2 * M, h: 0.85,
          fontSize: 32, bold: true, color: THEME.colors.dk2, align: "left" },
        text: "",
      },
    },
    { text: { text: "SafeMed · CSCI 4490 · Fall 2026",
        options: { x: M, y: H - 0.5, w: 6, h: 0.3, fontSize: 9,
          color: THEME.colors.accent5, isTextBox: true } } },
    { placeholder: { options: { name: "slideNumber", type: "sldNum",
        x: W - 1.45, y: H - 0.5, w: 0.8, h: 0.3, fontSize: 9,
        color: THEME.colors.accent5, align: "right" }, text: "" } },
  ],
  slideNumber: { x: W - 1.45, y: H - 0.5, fontSize: 9, color: THEME.colors.accent5 },
});

// Dark content slide, same title geometry as CONTENT.
pres.defineSlideMaster({
  title: "CONTENT_DARK",
  background: { color: THEME.colors.dk2 },
  objects: [
    {
      placeholder: {
        options: { name: "title", type: "title", x: M, y: 0.45, w: W - 2 * M, h: 0.85,
          fontSize: 32, bold: true, color: C.background1, align: "left" },
        text: "",
      },
    },
    { text: { text: "SafeMed · CSCI 4490 · Fall 2026",
        options: { x: M, y: H - 0.5, w: 6, h: 0.3, fontSize: 9,
          color: "7FA3B8", isTextBox: true } } },
  ],
  slideNumber: { x: W - 1.45, y: H - 0.5, fontSize: 9, color: "7FA3B8" },
});

/* ---------------- helpers ---------------- */

function card(slide, { x, y, w, h, fill, line }) {
  slide.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.1,
    fill: { color: fill || THEME.colors.lt2 },
    line: line ? { color: line, width: 1 } : { color: "DCE7ED", width: 0.75 },
    objectName: "card",
  });
}

function stat(slide, { x, y, w, value, label, color }) {
  slide.addText(value, {
    x, y, w, h: 0.95, fontSize: 52, bold: true, align: "center",
    color: color || THEME.colors.accent1, isTextBox: true, margin: 0,
  });
  slide.addText(label, {
    x, y: y + 0.95, w, h: 0.75, fontSize: 12, align: "center",
    color: THEME.colors.dk1, isTextBox: true, margin: 0,
  });
}

function bullets(slide, items, opts) {
  const o = Object.assign(
    { x: M, y: 1.6, w: W - 2 * M, h: 4.5, fontSize: 16,
      color: THEME.colors.dk1, isTextBox: true, paraSpaceAfter: 10 },
    opts || {}
  );
  slide.addText(
    items.map((t, i) => ({
      text: t,
      options: { bullet: true, breakLine: i !== items.length - 1 },
    })),
    o
  );
}

/* ---------------- slides ---------------- */

// 1 — title
pres.addSection({ title: "Opening" });
let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Opening" });
s.addText("SafeMed", { placeholder: "title" });
s.addText(
  [
    { text: "Continuous medication safety monitoring and caregiver alerts", options: { breakLine: true, fontSize: 19, color: "9FD9D2" } },
    { text: "", options: { breakLine: true, fontSize: 8 } },
    { text: "Victory Orobosa  ·  Chima Onochie  ·  Pacifique Mugisha", options: { breakLine: true, fontSize: 15 } },
    { text: "CSCI 4490 Software Engineering  ·  Fall 2026  ·  University of Central Arkansas", options: { fontSize: 13, color: "7FA3B8" } },
  ],
  { placeholder: "body" }
);
s.addShape(pres.ShapeType.rect, { x: M, y: 1.95, w: 1.2, h: 0.09,
  fill: { color: THEME.colors.accent2 }, line: { width: 0 }, objectName: "rule" });
s.addNotes(
  "Introduce the team and roles in one sentence each. Do not open the app yet - the problem has to land first."
);

// 2 — the problem
pres.addSection({ title: "Problem" });
s = pres.addSlide({ masterName: "CONTENT_DARK", sectionTitle: "Problem" });
s.addText("Two safe prescriptions, nobody holding the list", { placeholder: "title" });
s.addText(
  "Most medication harm is not one bad prescription. It is two reasonable prescriptions from two prescribers who never see each other's work.",
  { x: M, y: 1.55, w: 7.3, h: 1.2, fontSize: 17, color: "C8DDE8", isTextBox: true }
);
const probs = [
  ["RxNorm", "Standard drug naming, published and free"],
  ["openFDA", "Recall and enforcement reports, updated continuously"],
  ["DDInter 2.0", "160,235 curated, peer-reviewed interaction pairs"],
];
probs.forEach(([k, v], i) => {
  const y = 3.0 + i * 1.05;
  card(s, { x: M, y, w: 7.3, h: 0.9, fill: "14496D", line: "2E6286" });
  s.addText(k, { x: M + 0.25, y: y + 0.08, w: 2.1, h: 0.4, fontSize: 15, bold: true,
    color: THEME.colors.accent2, isTextBox: true, margin: 0 });
  s.addText(v, { x: M + 2.4, y: y + 0.08, w: 4.7, h: 0.7, fontSize: 13,
    color: "D5E6EF", isTextBox: true, margin: 0 });
});
card(s, { x: 8.5, y: 1.55, w: 4.1, h: 4.5, fill: "0E4463", line: THEME.colors.accent3 });
s.addText("The gap", { x: 8.75, y: 1.8, w: 3.6, h: 0.4, fontSize: 16, bold: true,
  color: THEME.colors.accent3, isTextBox: true, margin: 0 });
s.addText(
  "None of this information is anywhere near the person actually taking the tablets.\n\nAnd none of it is watching continuously.",
  { x: 8.75, y: 2.3, w: 3.6, h: 3.4, fontSize: 15, color: "E8F2F7", isTextBox: true, margin: 0 }
);
s.addNotes(
  "45 seconds, no screen. The information is public - the gap is distribution and monitoring, not knowledge."
);

// 3 — why a system
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem" });
s.addText("Why this is a system, not a prompt", { placeholder: "title" });
s.addText(
  "Anyone can ask a chatbot about one drug pair once. That is a question, and it is answered and forgotten.",
  { x: M, y: 1.45, w: W - 2 * M, h: 0.6, fontSize: 16, color: THEME.colors.accent5, isTextBox: true, italic: true }
);
const steps = [
  ["Recall published", "03:00 on a Tuesday, nobody is awake"],
  ["Checked automatically", "Against one patient's specific product code"],
  ["Routed by severity", "Only serious findings reach a caregiver"],
  ["Recorded", "Who saw what, and when, append-only"],
];
steps.forEach(([k, v], i) => {
  const x = M + i * 3.017;
  card(s, { x, y: 2.4, w: 2.85, h: 2.5 });
  s.addShape(pres.ShapeType.ellipse, { x: x + 0.25, y: 2.65, w: 0.6, h: 0.6,
    fill: { color: THEME.colors.accent1 }, line: { width: 0 }, objectName: "step-dot" });
  s.addText(String(i + 1), { x: x + 0.25, y: 2.72, w: 0.6, h: 0.45, fontSize: 18, bold: true,
    align: "center", color: "FFFFFF", isTextBox: true, margin: 0 });
  s.addText(k, { x: x + 0.25, y: 3.4, w: 2.35, h: 0.6, fontSize: 15, bold: true,
    color: THEME.colors.dk2, isTextBox: true, margin: 0 });
  s.addText(v, { x: x + 0.25, y: 4.0, w: 2.35, h: 0.8, fontSize: 12,
    color: THEME.colors.dk1, isTextBox: true, margin: 0 });
});
s.addText(
  "That is scheduling, idempotency, normalisation, authorization and auditability - a systems problem.",
  { x: M, y: 5.3, w: W - 2 * M, h: 0.5, fontSize: 15, bold: true, color: THEME.colors.dk2, isTextBox: true }
);
s.addNotes("The 'couldn't ChatGPT do this?' question, answered before it is asked.");

// 4 — architecture
pres.addSection({ title: "Design" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Design" });
s.addText("The architecture is one arrow", { placeholder: "title" });
const flow = [
  ["Authoritative\ndata", THEME.colors.accent1],
  ["Deterministic\nengine", THEME.colors.accent1],
  ["Verified\nfinding", THEME.colors.dk2],
  ["AI explains\nit", THEME.colors.accent3],
];
flow.forEach(([label, col], i) => {
  const x = M + i * 3.133;
  s.addShape(pres.ShapeType.roundRect, { x, y: 1.9, w: 2.5, h: 1.3, rectRadius: 0.1,
    fill: { color: col }, line: { width: 0 }, objectName: "flow-box" });
  s.addText(label, { x, y: 2.05, w: 2.5, h: 1.0, fontSize: 15, bold: true, align: "center",
    color: "FFFFFF", isTextBox: true, margin: 0 });
  if (i < 3) {
    s.addShape(pres.ShapeType.rightArrow, { x: x + 2.6, y: 2.4, w: 0.45, h: 0.3,
      fill: { color: THEME.colors.accent5 }, line: { width: 0 }, objectName: "arrow" });
  }
});
s.addText("Reverse that arrow and you get a different system", {
  x: M, y: 3.6, w: W - 2 * M, h: 0.45, fontSize: 18, bold: true, color: THEME.colors.accent4, isTextBox: true,
});
bullets(s, [
  "Patient data into a model, asking \"is this safe?\", answers confidently whether or not it is right",
  "No citation, so a pharmacist has nothing to check",
  "Severity would be invented rather than read from a source",
  "Turn the AI off in SafeMed and every finding still works - the full test suite passes with it disabled",
], { y: 4.15, h: 2.1, fontSize: 15 });
s.addNotes("This single slide is the thesis of the project. Do not rush it.");

// 5 — the stack
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Design" });
s.addText("What it is built from", { placeholder: "title" });
const stack = [
  ["Frontend", "React 19 · TypeScript · Vite", "2,862 lines"],
  ["API", "FastAPI · Pydantic v2", "4,234 lines"],
  ["Data", "PostgreSQL 16 · SQLAlchemy · Alembic", "4 migrations"],
  ["Background", "Celery · Celery Beat · Redis", "3 scheduled jobs"],
  ["Quality", "pytest · GitHub Actions CI", "194 tests"],
];
stack.forEach(([layer, tech, metric], i) => {
  const y = 1.55 + i * 0.92;
  card(s, { x: M, y, w: 8.1, h: 0.78 });
  s.addText(layer, { x: M + 0.22, y: y + 0.2, w: 1.7, h: 0.4, fontSize: 14, bold: true,
    color: THEME.colors.accent1, isTextBox: true, margin: 0 });
  s.addText(tech, { x: M + 2.0, y: y + 0.2, w: 4.0, h: 0.4, fontSize: 13,
    color: THEME.colors.dk1, isTextBox: true, margin: 0 });
  s.addText(metric, { x: M + 6.1, y: y + 0.2, w: 1.9, h: 0.4, fontSize: 13, bold: true,
    align: "right", color: THEME.colors.dk2, isTextBox: true, margin: 0 });
});
card(s, { x: 9.3, y: 1.55, w: 3.3, h: 4.15, fill: THEME.colors.dk2 });
s.addText("Modular monolith", { x: 9.52, y: 1.8, w: 2.9, h: 0.4, fontSize: 15, bold: true,
  color: THEME.colors.accent2, isTextBox: true, margin: 0 });
s.addText(
  "Microservices were considered and rejected.\n\nA three-person team cannot operate a distributed system and also build the thing being distributed.\n\nModule boundaries are still real - no service imports the HTTP layer.",
  { x: 9.52, y: 2.3, w: 2.9, h: 3.2, fontSize: 12, color: "DCEAF2", isTextBox: true, margin: 0 }
);
s.addNotes("Keep this brief - 30 seconds. The interesting slides come next.");

// 6 — the defining bug
pres.addSection({ title: "Findings" });
s = pres.addSlide({ masterName: "CONTENT_DARK", sectionTitle: "Findings" });
s.addText("The bug that defined the project", { placeholder: "title" });
s.addText(
  "Warfarin + aspirin is a textbook major interaction. Our safety check returned nothing.",
  { x: M, y: 1.5, w: W - 2 * M, h: 0.5, fontSize: 18, color: "C8DDE8", isTextBox: true }
);
card(s, { x: M, y: 2.25, w: 5.8, h: 1.5, fill: "14496D", line: "2E6286" });
s.addText("What the patient types", { x: M + 0.25, y: 2.42, w: 5.3, h: 0.35, fontSize: 12,
  color: "9FD9D2", isTextBox: true, margin: 0 });
s.addText("Aspirin", { x: M + 0.25, y: 2.8, w: 5.3, h: 0.6, fontSize: 26, bold: true,
  color: "FFFFFF", isTextBox: true, margin: 0 });
card(s, { x: 6.9, y: 2.25, w: 5.7, h: 1.5, fill: "14496D", line: "2E6286" });
s.addText("What the dataset calls it", { x: 7.15, y: 2.42, w: 5.2, h: 0.35, fontSize: 12,
  color: "9FD9D2", isTextBox: true, margin: 0 });
s.addText("Acetylsalicylic acid", { x: 7.15, y: 2.8, w: 5.2, h: 0.6, fontSize: 26, bold: true,
  color: THEME.colors.accent3, isTextBox: true, margin: 0 });
card(s, { x: M, y: 4.0, w: W - 2 * M, h: 1.9, fill: "5A1F28", line: THEME.colors.accent4 });
s.addText("No error. No warning. No exception.", { x: M + 0.3, y: 4.25, w: 11.4, h: 0.5,
  fontSize: 22, bold: true, color: "FFD9DE", isTextBox: true, margin: 0 });
s.addText(
  "A safety check that quietly finds zero looks exactly like good news. That is the failure mode that matters here - and it is why every medication is resolved to an RXCUI and matched by identifier, not by name.",
  { x: M + 0.3, y: 4.85, w: 11.4, h: 0.9, fontSize: 15, color: "F6DDE1", isTextBox: true, margin: 0 }
);
s.addNotes(
  "This is the strongest moment in the whole presentation. Slow down. Markers have seen projects that work; they have seen few students explain an invisible bug and what changed so it cannot recur."
);

// 7 — measured: 25%
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
s.addText("So we measured what name matching misses", { placeholder: "title" });
s.addText(
  "15-medication panel. Same drugs, same dataset, same code path. The only variable is whether identifiers are available.",
  { x: M, y: 1.4, w: W - 2 * M, h: 0.5, fontSize: 15, color: THEME.colors.accent5, isTextBox: true }
);
s.addChart(
  pres.ChartType.bar,
  [{ name: "Interactions found", labels: ["Name matching only", "Matched by RXCUI"], values: [63, 84] }],
  {
    x: M, y: 2.1, w: 6.6, h: 3.5, barDir: "col",
    chartColors: [THEME.colors.accent5, THEME.colors.accent1],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 15,
    dataLabelColor: THEME.colors.dk1, dataLabelFontFace: "+mn-lt",
    showLegend: false, showTitle: false,
    catAxisLabelColor: THEME.colors.dk1, catAxisLabelFontSize: 13, catAxisLabelFontFace: "+mn-lt",
    valAxisLabelColor: THEME.colors.accent5, valAxisLabelFontSize: 11, valAxisLabelFontFace: "+mn-lt",
    valGridLine: { color: "E3EBEF", size: 1 }, catGridLine: { style: "none" },
    valAxisMaxVal: 90,
  }
);
stat(s, { x: 7.6, y: 2.2, w: 2.5, value: "25%", label: "of real interactions missed\nby name matching alone", color: THEME.colors.accent4 });
stat(s, { x: 10.2, y: 2.2, w: 2.5, value: "2", label: "of those rated SEVERE", color: THEME.colors.accent4 });
card(s, { x: 7.6, y: 4.1, w: 5.1, h: 1.5 });
s.addText("Missed by name alone", { x: 7.82, y: 4.25, w: 4.7, h: 0.35, fontSize: 13, bold: true,
  color: THEME.colors.dk2, isTextBox: true, margin: 0 });
s.addText(
  "Acetylsalicylic acid + Warfarin  (Major)\nAcetylsalicylic acid + Ibuprofen  (Major)\nAcetaminophen + Warfarin  (Moderate)",
  { x: 7.82, y: 4.62, w: 4.7, h: 0.9, fontSize: 12, color: THEME.colors.dk1, isTextBox: true, margin: 0 }
);
s.addNotes("Name matching recovers only 75% of what the same dataset holds for the same patient.");

// 8 — recalls
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
s.addText("Recalls: saying how sure we are", { placeholder: "title" });
s.addText(
  "We sampled 100 current FDA enforcement reports. 45 carry no product identifier at all.",
  { x: M, y: 1.4, w: W - 2 * M, h: 0.5, fontSize: 16, color: THEME.colors.dk1, isTextBox: true }
);
card(s, { x: M, y: 2.1, w: 5.9, h: 3.4, fill: "E9F6F2", line: THEME.colors.accent2 });
s.addText("CONFIRMED", { x: M + 0.3, y: 2.35, w: 5.3, h: 0.45, fontSize: 18, bold: true,
  color: "02765E", isTextBox: true, margin: 0 });
s.addText("The recall names the exact product code the patient holds.",
  { x: M + 0.3, y: 2.85, w: 5.3, h: 0.6, fontSize: 14, color: THEME.colors.dk1, isTextBox: true, margin: 0 });
s.addText("\u201CRecall affects your Metformin\u201D", { x: M + 0.3, y: 3.6, w: 5.3, h: 0.5,
  fontSize: 17, bold: true, italic: true, color: THEME.colors.dk2, isTextBox: true, margin: 0 });
s.addText("55 of 100 sampled recalls", { x: M + 0.3, y: 4.75, w: 5.3, h: 0.4, fontSize: 13,
  color: THEME.colors.accent5, isTextBox: true, margin: 0 });

card(s, { x: 6.9, y: 2.1, w: 5.7, h: 3.4, fill: "FBF3DC", line: THEME.colors.accent3 });
s.addText("POSSIBLE", { x: 7.2, y: 2.35, w: 5.1, h: 0.45, fontSize: 18, bold: true,
  color: "8A6D12", isTextBox: true, margin: 0 });
s.addText("Same drug, but the notice identifies no manufacturer. We genuinely do not know.",
  { x: 7.2, y: 2.85, w: 5.1, h: 0.6, fontSize: 14, color: THEME.colors.dk1, isTextBox: true, margin: 0 });
s.addText("\u201CMay affect - check the label\u201D", { x: 7.2, y: 3.6, w: 5.1, h: 0.5,
  fontSize: 17, bold: true, italic: true, color: THEME.colors.dk2, isTextBox: true, margin: 0 });
s.addText("45 of 100 sampled recalls", { x: 7.2, y: 4.75, w: 5.1, h: 0.4, fontSize: 13,
  color: THEME.colors.accent5, isTextBox: true, margin: 0 });

s.addText(
  "Alert on drug name alone and you tell a patient they are affected 45% of the time without knowing. Two false alarms and they stop reading all of them - including the one that was real.",
  { x: M, y: 5.7, w: W - 2 * M, h: 0.7, fontSize: 14, bold: true, color: THEME.colors.dk2, isTextBox: true }
);
s.addNotes("The false-alarm argument is the one non-technical markers find most persuasive.");

// 9 — consent and routing
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
s.addText("Consent is the authorization rule", { placeholder: "title" });
bullets(s, [
  "A caregiver sees a patient only through a grant the patient created and can revoke",
  "The grant is re-checked on every single request - revocation bites on the next one, not at session expiry",
  "A revoked grant is kept, greyed out: who had access and until when is part of what makes consent meaningful",
  "An unknown patient and an unauthorized one return identical 403s, so status codes cannot be used to enumerate who exists",
], { y: 1.5, w: 7.4, h: 3.0, fontSize: 15 });
card(s, { x: 8.4, y: 1.5, w: 4.2, h: 4.1, fill: THEME.colors.lt2 });
s.addText("Severity routing", { x: 8.65, y: 1.72, w: 3.7, h: 0.4, fontSize: 16, bold: true,
  color: THEME.colors.dk2, isTextBox: true, margin: 0 });
s.addText("Maria sees", { x: 8.65, y: 2.3, w: 3.7, h: 0.3, fontSize: 12,
  color: THEME.colors.accent5, isTextBox: true, margin: 0 });
s.addText("10 findings", { x: 8.65, y: 2.58, w: 3.7, h: 0.55, fontSize: 30, bold: true,
  color: THEME.colors.dk2, isTextBox: true, margin: 0 });
s.addText("3 severe · 5 moderate · 2 mild", { x: 8.65, y: 3.12, w: 3.7, h: 0.3, fontSize: 11,
  color: THEME.colors.accent5, isTextBox: true, margin: 0 });
s.addText("Her daughter sees", { x: 8.65, y: 3.65, w: 3.7, h: 0.3, fontSize: 12,
  color: THEME.colors.accent5, isTextBox: true, margin: 0 });
s.addText("3 findings", { x: 8.65, y: 3.93, w: 3.7, h: 0.55, fontSize: 30, bold: true,
  color: THEME.colors.accent1, isTextBox: true, margin: 0 });
s.addText("a 70% reduction - and the screen says so out loud rather than letting her assume she sees everything",
  { x: 8.65, y: 4.55, w: 3.7, h: 0.9, fontSize: 12, color: THEME.colors.dk1, isTextBox: true, margin: 0 });
s.addNotes("Ten warnings of equal weight is the same as no warnings.");

// 10 — audit
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
s.addText("Consent says what is allowed. The audit log says what happened", { placeholder: "title" });
const log = [
  ["consent.invited", "Maria invited Elena", THEME.colors.accent5],
  ["consent.accepted", "Elena accepted", THEME.colors.accent5],
  ["patient_record.viewed", "Elena read the record", THEME.colors.accent1],
  ["consent.revoked", "Maria removed her access", THEME.colors.accent3],
  ["patient_record.access_denied", "Elena tried again anyway", THEME.colors.accent4],
];
log.forEach(([action, meaning, col], i) => {
  const y = 1.5 + i * 0.75;
  card(s, { x: M, y, w: 7.6, h: 0.62 });
  s.addShape(pres.ShapeType.ellipse, { x: M + 0.18, y: y + 0.19, w: 0.24, h: 0.24,
    fill: { color: col }, line: { width: 0 }, objectName: "dot" });
  s.addText(action, { x: M + 0.55, y: y + 0.14, w: 3.5, h: 0.35, fontSize: 12.5, bold: true,
    color: THEME.colors.dk2, fontFace: "Courier New", isTextBox: true, margin: 0 });
  s.addText(meaning, { x: M + 4.2, y: y + 0.14, w: 3.2, h: 0.35, fontSize: 12.5,
    color: THEME.colors.dk1, isTextBox: true, margin: 0 });
});
card(s, { x: 8.7, y: 1.5, w: 3.9, h: 3.85, fill: THEME.colors.dk2 });
s.addText("Why the last row matters", { x: 8.95, y: 1.72, w: 3.4, h: 0.4, fontSize: 15, bold: true,
  color: THEME.colors.accent2, isTextBox: true, margin: 0 });
s.addText(
  "A log that records only successes cannot answer \u201Cdid anyone try?\u201D - and that is usually the question you actually have.\n\nAppend-only is enforced by the ORM, not promised in a comment. Two tests prove it.\n\nAn audit row is written in the same transaction as the action, so there is never an entry for something that did not happen.",
  { x: 8.95, y: 2.2, w: 3.4, h: 3.0, fontSize: 11.5, color: "DCEAF2", isTextBox: true, margin: 0 }
);
s.addNotes("Run the psql query live here if the terminal is already up. Read the log bottom to top.");

// 11 — AI boundary
s = pres.addSlide({ masterName: "CONTENT_DARK", sectionTitle: "Findings" });
s.addText("Where the AI is, and where it is not", { placeholder: "title" });
const guards = [
  ["It never judges", "Severity comes from the dataset. The prompt asks for a rewrite, not an assessment."],
  ["It never sees a patient", "Drug names and source text only. No name, age, email, id or medication list - there is no payload to leak."],
  ["Every response is checked", "11 forbidden patterns catch any instruction to stop or change a medication. A failing response is discarded, not shown."],
];
guards.forEach(([t, d], i) => {
  const x = M + i * 4.05;
  card(s, { x, y: 1.75, w: 3.8, h: 2.9, fill: "14496D", line: "2E6286" });
  s.addShape(pres.ShapeType.ellipse, { x: x + 0.3, y: 2.0, w: 0.55, h: 0.55,
    fill: { color: THEME.colors.accent2 }, line: { width: 0 }, objectName: "guard-dot" });
  s.addText(String(i + 1), { x: x + 0.3, y: 2.07, w: 0.55, h: 0.4, fontSize: 16, bold: true,
    align: "center", color: "0B3B5C", isTextBox: true, margin: 0 });
  s.addText(t, { x: x + 0.3, y: 2.7, w: 3.2, h: 0.5, fontSize: 15, bold: true,
    color: "FFFFFF", isTextBox: true, margin: 0 });
  s.addText(d, { x: x + 0.3, y: 3.2, w: 3.2, h: 1.3, fontSize: 12,
    color: "CFE3EE", isTextBox: true, margin: 0 });
});
s.addText(
  "Turn the AI off completely and every finding still works. The AI makes SafeMed easier to understand. It is never what makes it correct.",
  { x: M, y: 5.0, w: W - 2 * M, h: 0.8, fontSize: 17, bold: true, color: THEME.colors.accent3, isTextBox: true }
);
s.addNotes("If asked how much is AI-generated: answer honestly and specifically, and point at the handbook.");

// 12 — demo divider
pres.addSection({ title: "Demo" });
s = pres.addSlide({ masterName: "SECTION", sectionTitle: "Demo" });
s.addText("Live demonstration", { placeholder: "title" });
s.addText(
  "Maria's list and what it found  ·  the daily check-in  ·  a live FDA recall  ·  her daughter's view  ·  consent revoked  ·  the audit log",
  { placeholder: "body" }
);
s.addNotes(
  "Follow DEMO.md. If a beat fails, say one sentence and move on - never debug live. Beats 3, 6 and 7 carry the presentation on their own."
);

// 13 — testing
pres.addSection({ title: "Quality" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Quality" });
s.addText("Testing and continuous integration", { placeholder: "title" });
stat(s, { x: M, y: 1.5, w: 2.7, value: "194", label: "automated tests" });
stat(s, { x: M + 2.9, y: 1.5, w: 2.7, value: "16", label: "test files" });
stat(s, { x: M + 5.8, y: 1.5, w: 2.7, value: "4", label: "CI checks per push" });
stat(s, { x: M + 8.7, y: 1.5, w: 2.7, value: "0", label: "duplicates over\n3 full re-runs" });
bullets(s, [
  "Tests run against a real PostgreSQL, not SQLite - the application depends on real constraint behaviour, and a suite testing something you do not ship is not testing",
  "Access control is tested through real HTTP with real tokens: a unit test proves the permission function works, not that the route uses it",
  "Every test runs in a transaction that is rolled back, so the suite is safe to run a hundred times",
  "CI runs tests, type checking, linting and a migration check on every push - as parallel jobs, so one cannot mask the other",
], { y: 3.5, h: 2.3, fontSize: 14 });
s.addNotes("Mention that CI was added late and immediately found a real defect - next slide.");

// 14 — the CI catch
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Quality" });
s.addText("CI tested the app, but not the thing that deploys it", { placeholder: "title" });
card(s, { x: M, y: 1.5, w: 5.9, h: 2.1, fill: THEME.colors.lt2 });
s.addText("What we found", { x: M + 0.3, y: 1.72, w: 5.3, h: 0.35, fontSize: 14, bold: true,
  color: THEME.colors.dk2, isTextBox: true, margin: 0 });
s.addText(
  "The test suite builds its schema from the models and never runs Alembic. So a broken migration had always passed CI.",
  { x: M + 0.3, y: 2.12, w: 5.3, h: 1.2, fontSize: 14, color: THEME.colors.dk1, isTextBox: true, margin: 0 }
);
card(s, { x: 6.9, y: 1.5, w: 5.7, h: 2.1, fill: "FBE9EB", line: THEME.colors.accent4 });
s.addText("The defect it exposed", { x: 7.2, y: 1.72, w: 5.1, h: 0.35, fontSize: 14, bold: true,
  color: "8C2430", isTextBox: true, margin: 0 });
s.addText(
  "The initial migration dropped its tables but left all 11 ENUM types behind. The second upgrade died on \u201Ctype user_role already exists\u201D.",
  { x: 7.2, y: 2.12, w: 5.1, h: 1.2, fontSize: 14, color: THEME.colors.dk1, isTextBox: true, margin: 0 }
);
card(s, { x: M, y: 3.9, w: W - 2 * M, h: 1.9, fill: THEME.colors.dk2 });
s.addText("The migration chain was one-way", { x: M + 0.35, y: 4.15, w: 11.3, h: 0.5,
  fontSize: 20, bold: true, color: THEME.colors.accent2, isTextBox: true, margin: 0 });
s.addText(
  "A deploy could be rolled back but never re-applied - and you would discover that at the exact moment you were already rolling back. CI now runs upgrade, downgrade, upgrade on every push.",
  { x: M + 0.35, y: 4.7, w: 11.3, h: 0.9, fontSize: 15, color: "DCEAF2", isTextBox: true, margin: 0 }
);
s.addNotes("A good answer to 'what would you have done differently' - test the deployment path, not just the app.");

// 15 — evaluation summary
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Quality" });
s.addText("What we measured, and what it does not prove", { placeholder: "title" });
const results = [
  ["25%", "of real interactions missed by name matching alone", THEME.colors.accent4],
  ["45 / 100", "FDA recalls carry no product identifier", THEME.colors.accent3],
  ["70%", "fewer findings reach a caregiver", THEME.colors.accent1],
  ["7.2 ms", "median evaluation time", THEME.colors.accent1],
];
results.forEach(([v, l, col], i) => {
  const x = M + i * 3.017;
  card(s, { x, y: 1.5, w: 2.85, h: 2.0 });
  s.addText(v, { x: x + 0.15, y: 1.72, w: 2.55, h: 0.75, fontSize: 32, bold: true,
    align: "center", color: col, isTextBox: true, margin: 0 });
  s.addText(l, { x: x + 0.15, y: 2.5, w: 2.55, h: 0.85, fontSize: 12, align: "center",
    color: THEME.colors.dk1, isTextBox: true, margin: 0 });
});
card(s, { x: M, y: 3.8, w: W - 2 * M, h: 2.0, fill: "FBF3DC", line: THEME.colors.accent3 });
s.addText("Threats to validity", { x: M + 0.35, y: 4.0, w: 11.3, h: 0.4, fontSize: 16, bold: true,
  color: "8A6D12", isTextBox: true, margin: 0 });
s.addText(
  [
    { text: "The 15-medication panel was chosen, not sampled. It is realistic, not representative.", options: { bullet: true, breakLine: true } },
    { text: "One interaction dataset, so this measures internal consistency and never completeness.", options: { bullet: true, breakLine: true } },
    { text: "The recall sample is a snapshot of one day, not a longitudinal study.", options: { bullet: true, breakLine: true } },
    { text: "No clinical validation. Nothing here says SafeMed improves anyone's health.", options: { bullet: true } },
  ],
  { x: M + 0.35, y: 4.45, w: 11.3, h: 1.25, fontSize: 13, color: THEME.colors.dk1, isTextBox: true, paraSpaceAfter: 4 }
);
s.addNotes("State the limits yourself. A marker who finds a limitation you did not mention stops believing the rest.");

// 16 — limitations and future work
pres.addSection({ title: "Close" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Close" });
s.addText("What we did not build, and what comes next", { placeholder: "title" });
s.addText("Known limitations", { x: M, y: 1.45, w: 5.9, h: 0.4, fontSize: 17, bold: true,
  color: THEME.colors.accent4, isTextBox: true });
bullets(s, [
  "No interface for reading the audit log - the rows exist, nobody can read them",
  "Schedules are wall-clock UTC; no per-user time zones",
  "One interaction dataset",
  "Append-only is enforced in the application, not cryptographically",
  "Not deployed to a hosted environment",
], { x: M, y: 1.9, w: 5.9, h: 3.4, fontSize: 14 });
s.addText("Next, in priority order", { x: 6.9, y: 1.45, w: 5.7, h: 0.4, fontSize: 17, bold: true,
  color: THEME.colors.accent1, isTextBox: true });
bullets(s, [
  "An audit review interface - the data exists and is unusable by the people it protects",
  "A second interaction dataset, so we could speak to completeness",
  "Per-user time zones",
  "Notification delivery with status and retry",
  "Alerting on repeated refused access attempts",
], { x: 6.9, y: 1.9, w: 5.7, h: 3.4, fontSize: 14 });
s.addNotes("Having a precise answer here is worth more than having fewer limitations.");

// 17 — team and process
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Close" });
s.addText("How we worked", { placeholder: "title" });
const team = [
  ["Victory Orobosa", "Project Leader, Full-Stack", "Data model, safety engine, RxNorm and recall integration, dose scheduling, AI guardrails, both frontends, CI, evaluation"],
  ["Chima Onochie", "Backend and Data Integration", "JWT authentication, consent grants and RBAC, caregiver endpoints, the append-only audit log"],
  ["Pacifique Mugisha", "Security, Testing and Deployment", "Accessible login and registration, form validation and its tests, API client error handling"],
];
team.forEach(([n, r, c], i) => {
  const y = 1.5 + i * 1.3;
  card(s, { x: M, y, w: 8.3, h: 1.15 });
  s.addText(n, { x: M + 0.25, y: y + 0.12, w: 2.6, h: 0.35, fontSize: 14, bold: true,
    color: THEME.colors.dk2, isTextBox: true, margin: 0 });
  s.addText(r, { x: M + 0.25, y: y + 0.48, w: 2.6, h: 0.5, fontSize: 11,
    color: THEME.colors.accent1, isTextBox: true, margin: 0 });
  s.addText(c, { x: M + 3.0, y: y + 0.15, w: 5.1, h: 0.9, fontSize: 11.5,
    color: THEME.colors.dk1, isTextBox: true, margin: 0 });
});
card(s, { x: 9.5, y: 1.5, w: 3.1, h: 3.95, fill: THEME.colors.lt2 });
s.addText("Process", { x: 9.72, y: 1.7, w: 2.7, h: 0.35, fontSize: 15, bold: true,
  color: THEME.colors.dk2, isTextBox: true, margin: 0 });
s.addText(
  "47 commits\nFeature branches and pull requests\nCI green on every push\nCode review before merge, with findings addressed in follow-up commits rather than silently amended\nGitHub Issues and a project board",
  { x: 9.72, y: 2.15, w: 2.7, h: 3.1, fontSize: 11.5, color: THEME.colors.dk1, isTextBox: true, margin: 0 }
);
s.addNotes("Mention the integration conflict honestly - duplicated work, what caused it, what changed.");

// 18 — close
s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Close" });
s.addText("What SafeMed argues", { placeholder: "title" });
s.addText(
  [
    { text: "Whether a drug combination is dangerous is a question with a sourced, checkable answer. That answer should come from the source.", options: { breakLine: true, fontSize: 17 } },
    { text: "", options: { breakLine: true, fontSize: 8 } },
    { text: "Explaining it to a frightened seventy-two-year-old is a language problem. That is where a language model earns its place.", options: { breakLine: true, fontSize: 17 } },
    { text: "", options: { breakLine: true, fontSize: 8 } },
    { text: "Keeping those two jobs apart is what lets SafeMed cite every claim it makes.", options: { fontSize: 17, bold: true, color: "9FD9D2" } },
  ],
  { placeholder: "body" }
);
s.addShape(pres.ShapeType.rect, { x: M, y: 1.95, w: 1.2, h: 0.09,
  fill: { color: THEME.colors.accent2 }, line: { width: 0 }, objectName: "rule" });
s.addText("github.com/victory113/safemed", { x: M, y: 6.3, w: 8, h: 0.4, fontSize: 14,
  color: "7FA3B8", isTextBox: true });
s.addNotes("End here. Take questions. The Q&A section of DEMO.md has prepared answers for the six most likely.");

const out = path.join(__dirname, "SafeMed_Final_Presentation.pptx");
pres.writeFile({ fileName: out }).then(async () => {
  if (applyTheme) await applyTheme(out, THEME);
  console.log("wrote", out);
});
