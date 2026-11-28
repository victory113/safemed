# SafeMed — Presentation Script

Ten minutes, then two minutes of questions. This document is what you rehearse
from. [DEMO.md](DEMO.md) is the longer run sheet and stays the reference for
setup and for the full version of each beat; this is the cut that fits the
clock.

---

## 1. The constraint, and what it forced

The deck had eighteen slides. The demo script had nine beats and ran about
eight minutes. Eighteen slides at a realistic thirty seconds each is nine
minutes **before** the demo starts. The two documents together described a
sixteen-minute talk, and you have ten.

Nothing was deleted. The deck is now **nine slides that carry the talk and
twelve appendix slides** that sit after the close. You never present the
appendix. You jump to it when a question needs it, by typing the slide number
and pressing Enter in presenter view, and — this is the part worth
remembering — **three of those appendix slides are screenshots of the running
app**, so a demo that will not start costs you nothing but the word "live".

The demo is cut from eight minutes to four and a half. What came out:

| Cut | Why it is safe to cut |
|---|---|
| Beat 1, the spoken problem | Slide 2 does it, with the sources on screen |
| Beat 8, where the AI is | Promoted to its own slide, slide 7 |
| The long form of beat 7b | Compressed; the audit log is shown, not narrated line by line |

---

## 2. Run of show

| | Time | Length | What | Who |
|---|---|---|---|---|
| Slide 1 | 0:00 | 0:20 | Title and team | Victory |
| Slide 2 | 0:20 | 0:45 | The problem | Victory |
| Slide 3 | 1:05 | 0:45 | The architecture is one arrow | Victory |
| Slide 4 | 1:50 | **4:30** | **Live demonstration** | all three |
| Slide 5 | 6:20 | 0:50 | The bug that defined the project | Victory |
| Slide 6 | 7:10 | 0:50 | What we measured | Victory |
| Slide 7 | 8:00 | 0:45 | Where the AI is, and where it is not | Victory |
| Slide 8 | 8:45 | 0:35 | What we did not build | Chima |
| Slide 9 | 9:20 | 0:30 | What SafeMed argues | Victory |
| | 9:50 | | **ten seconds of slack** | |
| Q&A | | 2:00 | | whoever owns the area |

The timings are also in the speaker notes of each slide, as `[0:20-1:05]`
prefixes, so presenter view tells you whether you are ahead or behind without
arithmetic.

---

## 3. Who says what, and why

The split follows who built what, which is the only split you can defend if a
marker asks.

**Victory** — the safety engine, interactions, recalls, the background
workers, the AI layer, CI and the documents. 51 of the 61 commits. Takes the
framing, the demo's safety half, and the close.

**Chima** — authentication and JWT, consent grants, caregiver views and
role-based access, and the append-only audit log. Takes the consent, caregiver
and audit section of the demo, and slide 8, because the audit review interface
is the first thing he would build next.

**Pacifique** — the account pages, accessibility and the welcome animation,
the API client, and the integration conflict. Takes the daily check-in part of
the demo, which is the patient-facing interface he built.

That gives Victory roughly six minutes, Chima two, Pacifique one. **If your
instructor expects equal speaking time, say so now and we will rebalance** —
the honest way to do it is to move slides 2 and 3 to Pacifique and slide 6 to
Chima, not to invent contributions.

**Handovers must be rehearsed.** Three people swapping a clicker mid-demo is
where team presentations lose thirty seconds. Agree one sentence each:

- Victory → Pacifique: *"Pacifique built the screen she actually uses every day."*
- Pacifique → Chima: *"Chima will show you what her daughter can see."*
- Chima → Victory: *"Back to Victory for what nearly went wrong."*

---

## 4. Before you walk in

The full checklist is in [DEMO.md](DEMO.md) under *Before you start*. The short
version, in order:

```powershell
cd ~/dev/safemed; .\scripts\setup.ps1 -Demo
```

```powershell
docker compose exec api python -c "from app.workers.tasks import explain_findings; print(explain_findings())"
```

Expect `'ok': 10`. Then clear the audit log, start the frontend, log in once to
check, and log out:

```powershell
docker compose exec db psql -U safemed -d safemed -c "DELETE FROM audit_events;"
```

```powershell
npm run dev --prefix frontend
```

Then, before anyone is watching:

- **Two browser windows, not two tabs.** Tabs share storage and will sign one
  account out mid-demo. Window 1 logged out on the login page, window 2 ready.
- **A terminal visible**, large font, for the recall command and the audit log.
- **Browser zoom about 125%.** The back row cannot read the source citations,
  and slide 5 depends on them reading *Involves: Aspirin, Warfarin*.
- **Do Not Disturb on.** You are projecting a login screen.
- Laptop plugged in, sleep disabled.

---

## 5. The script

Say these in your own words. The sentences in **bold** are the ones that carry
the argument — those, say close to verbatim.

### Slide 1 — Title · 0:00–0:20 · Victory

> "SafeMed is continuous medication safety monitoring with caregiver alerts.
> I'm Victory — I built the safety engine, the recall monitoring and the
> background jobs. Chima built authentication, consent and the audit log.
> Pacifique built the patient interface and the API client."

Do not open the app yet. Twenty seconds, then move.

### Slide 2 — The problem · 0:20–1:05 · Victory

> "The FDA estimates medication errors injure around 1.3 million people a year
> in the United States. **Most of that is not one bad prescription. It is two
> reasonable prescriptions from two prescribers who never see each other's
> work** — and nobody holding the whole list.
>
> The information needed to catch it is already public. RxNorm publishes
> standard drug naming. openFDA publishes recalls continuously. DDInter
> publishes 160,235 peer-reviewed interaction pairs.
>
> **None of it is anywhere near the person actually taking the tablets, and
> none of it is watching continuously.** That gap is the project."

### Slide 3 — The architecture is one arrow · 1:05–1:50 · Victory

> "The whole design is one rule about ordering.
>
> **Authoritative data decides whether something is dangerous. A deterministic
> engine evaluates it. Only then, and only to rephrase a finding that already
> exists, does a language model run.**
>
> That ordering is why every warning in this system can name its source. The
> severity on the screen is the severity DDInter recorded — we never infer it.
> If you remember one thing from this talk, remember the direction of that
> arrow, because everything else follows from it."

Do not rush this slide. It is the thesis.

### Slide 4 — Live demonstration · 1:50–6:20 · all three

See section 6. Come back to slide 5 when the demo ends.

### Slide 5 — The bug that defined the project · 6:20–7:10 · Victory

> "I want to show you the bug, because it taught us more than the features did.
>
> Early on, aspirin and warfarin — a pair DDInter grades Major, a serious
> bleeding interaction — **returned nothing. No error. The safety check quietly
> found zero.**
>
> The dataset does not call it aspirin. It calls it acetylsalicylic acid. We
> were matching on names, and the two sources name the same drug differently.
>
> **A crash would have been better.** A crash tells the patient something is
> wrong and sends her to a pharmacist. A green screen that says 'no safety
> concerns found' tells her she is fine, and she stops looking."

### Slide 6 — What we measured · 7:10–8:00 · Victory

> "So we stopped guessing and measured it. Across a fifteen-medication panel,
> name matching alone finds 63 of the 84 interactions the dataset actually
> holds for that patient. **It misses 25 percent, including two rated severe.**
> That is why everything is matched by RxNorm identifier instead of name.
>
> Two more numbers. **45 of 100 FDA recalls carry no usable product
> identifier** — that is why a recall is either 'affects you' or 'may affect
> you, check the label', and never a guess. And severity routing cuts what
> reaches a caregiver by **70 percent**, ten findings down to three.
>
> What this does not prove: the panel was chosen by us, not sampled, and we
> measure one dataset's internal consistency, not completeness."

Say that last sentence. A marker who finds a limitation you did not name stops
trusting the numbers you did.

### Slide 7 — Where the AI is, and where it is not · 8:00–8:45 · Victory

> "There is a language model in this system, and the interesting part is what
> it is not allowed to do.
>
> **It never decides whether something is dangerous** — that comes from the
> dataset, deterministically, before any model runs. **It never receives
> patient data** — it gets drug names and the finding's own text, no name, no
> identifier, no age, no medication list. And **every response is checked
> against eleven forbidden patterns and thrown away** if it tells someone to
> stop or change a medication.
>
> That is not theoretical. On the recall findings the model wrote 'do not stop
> taking your medication' — good advice — and our filter refused it anyway,
> because it matches a phrase we will not let through. We kept the false
> positive. **A rejected explanation costs us nicer wording. An accepted one
> that told her to stop a medication costs something we are not willing to
> risk.**
>
> Turn the AI off completely and every finding here still works. It makes
> SafeMed easier to understand. It is never what makes it correct."

### Slide 8 — What we did not build · 8:45–9:20 · Chima

> "Four things we are not claiming.
>
> **There is no screen for the audit log.** Every row is written and
> queryable, but only through SQL — which means the people it protects cannot
> read it. That is the first thing we would build next.
>
> Schedules are stored as wall-clock UTC, with no per-user time zones. The
> `notifications` table exists and nothing writes to it — caregiver alerting
> is delivered by the dashboard, not by email. And append-only is enforced in
> the application, not in the database: direct database access can still alter
> history. Real tamper-evidence needs cryptographic chaining."

### Slide 9 — What SafeMed argues · 9:20–9:50 · Victory

> "SafeMed delivers medication management, continuous safety and recall
> monitoring, consent-based caregiver alerting, role-based access control and
> an append-only audit trail, with 197 automated tests running in CI.
>
> But the contribution is not any one feature. It is a position about where
> machine learning belongs in a safety system. **Whether a drug combination is
> dangerous is a question with a sourced, checkable answer, and that answer
> should come from the source. Explaining it to a frightened
> seventy-two-year-old is a language problem, and that is where a model earns
> its place.** Keeping those two jobs apart is what lets SafeMed cite every
> claim it makes.
>
> Thank you — we'll take questions."

---

## 6. The demo, compressed to 4:30

Six beats. Times are elapsed within the demo.

### B1 · 0:00–0:20 · Maria's list · Victory

Log in as Maria. Let the dashboard land.

> "Maria is 72 and takes five medications from two prescribers. Every one has a
> green badge — that is her entry resolved to an RxNorm identifier, not to the
> string she typed."

### B2 · 0:20–1:30 · What it found · Victory

Scroll to the top of Safety checks.

> "Three serious interactions — aspirin and warfarin, aspirin and ibuprofen,
> ibuprofen and warfarin. All three raise bleeding risk, all three rated Major
> in the source data."

Point at the line under a finding.

> "Every finding says where it came from and which of her own medicines are
> involved. It cites its source, so a pharmacist can check it."

Point at the card title, then the *Involves* line.

> "And look at the two names on this one card. The title says **Acetylsalicylic
> acid**. The line below says **Aspirin**. Those are the same drug, and getting
> that wrong is the bug I'll come back to in a minute."

Scroll to *Also worth knowing*.

> "Seven more, moderate and minor. Recorded, not shouting, and not sent to her
> daughter."

*Handover: "Pacifique built the screen she actually uses every day."*

### B3 · 1:30–2:05 · The daily check-in · Pacifique

Scroll to Today's doses.

> "This is the part she touches. Her doses for today, each one button. Watch
> the adherence figure."

Tap **I took it** on one dose. Read the number off the screen before and after.

> "One tap, and it updates. Deliberate skips are counted separately from missed
> doses, because a patient who tells you she skipped one is giving you better
> information than one who says nothing — penalising her for honesty would
> teach her to stop."

*Handover: "Back to Victory for the part that is live."*

### B4 · 2:05–3:15 · A live FDA recall · Victory

Run the command in the visible terminal:

```powershell
docker compose exec api python -c "from app.workers.tasks import simulate_recall; print(simulate_recall.delay('metformin').get(timeout=120))"
```

> "That is a background worker querying openFDA — the real FDA enforcement
> API, right now, not a fixture."

When it returns `findings_created: 5`, reload Maria's dashboard.

> "Five findings, and they are not all the same. **This one says the recall
> affects her** — the recall names the exact product code on her record:
> Cardinal Health, D-0435-2021, a real recall. **This one says it may affect
> her, check the label** — same drug, but the manufacturer code on her record
> does not identify the recalled product, so we will not tell her she is
> affected.
>
> 45 of 100 FDA recalls have no usable product identifier. **A system that
> cried wolf on every recall would be switched off inside a week.**"

*Handover: "Chima will show you what her daughter can see."*

### B5 · 3:15–3:55 · Her daughter's view · Chima

Switch to the second window, already logged in as Elena.

> "This is Elena, Maria's daughter. Maria has ten findings. **Elena sees
> three** — and the screen says so in words: serious alerts only.
>
> That is not a filter in the browser. The server decides, on every single
> request, and it re-checks the consent grant each time. Ten warnings of equal
> weight is the same as no warnings."

### B6 · 3:55–4:30 · Consent and the audit log · Chima

In Maria's window, revoke Elena's access. Reload Elena's screen — her patient
list is now empty.

> "Maria revokes it, and it takes effect on Elena's **next request**, not when
> her session expires. The grant is kept, not deleted — it shows as access
> removed, with the time."

Run the audit query in the terminal:

```powershell
docker compose exec db psql -U safemed -d safemed -c "SELECT created_at, action, patient_id FROM audit_events ORDER BY created_at DESC LIMIT 8;"
```

> "And every one of those actions is in an append-only log: the invitation, the
> acceptance, each time Elena read the record, and the revocation. **The
> application cannot update or delete a row in this table.** We know who saw
> what, and when."

Stop. Go to slide 5.

---

## 7. Q&A — two minutes

That is roughly **three questions**. Answer in forty seconds each. If an answer
needs a screen, say the appendix slide number out loud to your clicker-holder.

**"Couldn't ChatGPT just tell you about drug interactions?"**

> It could describe one. It cannot monitor. The point is not answering a
> question once — it is that a recall was published at 3am and something
> checked Maria's specific product code against it. And a model asked "is this
> dangerous?" answers confidently whether or not it is right, with no citation.
> Every finding here points at a dataset a pharmacist can check.

**"That is a Class I recall, the FDA's most serious class, and you show it as Moderate?"**

> Severity is two axes, not one: the FDA's class, and how confident we are that
> it is her product. An unconfirmed Class I and a confirmed Class II both land
> on Moderate. We would rather be honest about the uncertainty than inflate it.

**"It is four in the afternoon — why does it say the 8pm dose was missed?"**

> Two kinds of time. A schedule is the number she typed, so it renders as she
> entered it, in UTC. An event is a real instant, so it renders in her own time
> zone. Per-user time zones are a stated limitation.

**"How do you know the audit log is complete?"**

> The audit row for a write is committed in the same transaction as the action
> it describes, so a rolled-back action leaves no record and a recorded action
> cannot be rolled back. Refusals are logged too, with the patient id null, so
> the log cannot be used to find out who exists.

**"Is this a medical device?"**

> No. SafeMed does not diagnose, prescribe, or advise changing a medication,
> and every screen says to talk to a pharmacist. It surfaces published safety
> information about a list the patient entered herself.

**"How much of this is AI-generated?"**

> Answer honestly and specifically. Say what you designed, what you decided,
> and what you can explain — and you can explain every decision in this
> project. Do not be vague here; vagueness reads as evasion.

**"Why isn't it deployed?"**

> It runs under Docker Compose and we did not do a hosted deployment — it is
> listed as a limitation. What we did do is make CI build the image and start
> the stack, because the compose file mounts the source over the container's
> own copy, which means `compose up` alone never proves the image works.

---

## 8. If something breaks

| Symptom | Do this |
|---|---|
| Dashboard spinner forever | API is down. `docker compose restart api`, wait 10s, reload |
| "Could not reach SafeMed" | Same — and it is *supposed* to say that rather than show a blank screen. Say so |
| Recall command hangs | Worker, or the network. **Skip to B5.** Do not debug |
| Recall returns `findings_created: 0` | openFDA is unreachable. Jump to appendix slide 11 and narrate the screenshot |
| Login fails | Re-run `scripts.seed_demo`, then regenerate explanations |
| No *In plain language* panels | You re-seeded and did not re-run `explain_findings`. Harmless — say the AI layer is off and the findings still work. That is slide 7's point |
| Nothing starts at all | Appendix slides 10, 11, 12 are the demo as screenshots. Narrate them with the same words |

**The rule: one sentence, then move on.** "The worker isn't responding — I'll
come back to that." Never debug in front of the room. Slides 5, 6 and 7 carry
the presentation on their own.

---

## 9. The numbers, and nothing else

Memorise these six. Do not quote a number that is not on this list.

| | |
|---|---|
| **1.3 million** | people a year injured by medication errors in the US (FDA estimate) |
| **160,235** | interaction pairs from DDInter 2.0, 99.8% identifier-addressable |
| **25%** | of real interactions missed by name matching alone — two of them severe |
| **45 of 100** | FDA recalls carry no usable product identifier |
| **70%** | reduction in what reaches a caregiver — **ten findings down to three** |
| **197** | automated tests, run by CI on every push |

The 70% denominator is the one that trips people. It is measured on the ten
interaction findings. After the recall beat the screen shows fifteen findings
and three alerts, which is 80% — if someone does that arithmetic out loud,
agree with them and say which number you measured.

---

## 10. What to actually rehearse

In priority order, because you will not have time for all of it.

1. **Slide 3 and slide 5, out loud, until they need no notes.** The thesis and
   the bug are what the presentation is. Everything else is support.
2. **The demo, twice, end to end, on the clock.** Not reading it — doing it.
   Clicking the wrong thing is what costs you the minute you do not have.
3. **The three handover sentences**, with the actual laptop and the actual
   clicker.
4. **The first three Q&A answers**, out loud once each.
5. Everything else once.

The strongest moment in this talk is not a feature. It is slide 5 — when you
say the safety check returned nothing and no error, and explain why that was
worse than a crash. Markers have seen a lot of projects that work. They have
seen very few students explain a bug that was invisible, why it was invisible,
and what they changed so it could not happen again.

Do not rush that part.
