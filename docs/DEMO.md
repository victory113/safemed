# SafeMed — Demo Script

A run sheet for the presentation. Nine beats, about eight minutes of demo.

The structure is deliberate: **every beat shows something that is hard to
fake.** Live FDA data, a real interaction dataset, two accounts seeing
different things. A demo that only shows screens could be a mockup; this one
cannot.

---

## Before you start

Run these about ten minutes before, not five.

```bash
cd ~/dev/safemed && docker compose up -d
```

```bash
docker compose ps
```

All five services (`api`, `db`, `redis`, `worker`, `beat`) must say `Up`, and
`db` and `redis` must say `healthy`. If anything is restarting, give it thirty
seconds and look again.

```bash
docker compose exec api python -m scripts.seed_demo
```

This resets Maria's data and rebuilds it, so it is safe to run twice. It should
end with **10 findings created**. If it says anything else, run it once more.

It does **not** clear the audit log — nothing can, which is the point. If you
have rehearsed a few times, beat 7b will show older rows below the current
run's. Either narrate only the top six, or clear it once before the real
thing:

```bash
docker compose exec db psql -U safemed -d safemed -c "DELETE FROM audit_events;"
```

Doing that from `psql` rather than through the app is itself the honest
caveat: append-only is enforced in the application, not in the database.

```bash
npm run dev --prefix frontend
```

Then open `http://localhost:5173`, log in as Maria, and confirm the dashboard
loads. **Log out again** so you start the demo on the login screen.

Have two browser windows ready, not two tabs — you will be switching between a
patient and a caregiver, and tabs share storage in a way that will sign one of
them out.

| Account | Email | Password |
|---|---|---|
| Patient | `maria@safemed.demo` | `demo-password-123` |
| Caregiver | `elena@safemed.demo` | `demo-password-123` |

And have this ready to paste in a terminal you can see:

```bash
docker compose exec api python -c "from app.workers.tasks import simulate_recall; print(simulate_recall.delay('metformin').get(timeout=120))"
```

---

## The run of show

### Beat 1 — The problem (45 seconds, no screen)

> "The FDA has estimated that medication errors injure around 1.3 million
> people a year in the US. A lot of that is not one bad prescription — it is
> two safe prescriptions from two different doctors that should not be taken
> together, and nobody holding the whole list.
>
> The information needed to catch this is public. It is just not anywhere near
> the person taking the pills."

Do not open anything yet. Let the problem land first.

> **Be careful with that number.** It is a real FDA estimate and it is widely
> quoted, but the primary source is an FDA medication-errors page archived
> around 2008–09, and the current FDA site does not appear to restate it. Say
> *"the FDA has estimated"*, not *"the FDA says"*. If you are pressed for
> something current, the defensible line is that the FDA receives more than
> 100,000 reports a year associated with suspected medication errors. Either
> way, do not let the whole opening rest on one statistic — the demo is the
> argument.

### Beat 2 — Maria's list (45 seconds)

Log in as Maria. Scroll past the alerts to **Your medications**.

> "This is Maria. Five medications — nothing exotic, this is an ordinary list
> for someone in their seventies."

Point at the green **Matched** badges.

> "Each one has been matched to a standard identifier called an RXCUI. That
> matters more than it looks, and I'll show you why in a second."

### Beat 3 — What it found (90 seconds) — *the core*

Scroll to the top.

> "Three serious interactions. Aspirin and warfarin, aspirin and ibuprofen,
> ibuprofen and warfarin — all three raise bleeding risk, and all three are
> rated Major in the source data."

Point at the source line under a finding.

> "Every finding says where it came from — DDInter 2.0 — and which of her own
> medications are involved. It cites its source, so a pharmacist can check it."

Now the part that makes the project:

> "The interaction dataset doesn't call it aspirin. It calls it
> **Acetylsalicylic acid**. When we first built this, warfarin and aspirin —
> a pair DDInter grades Major — returned **nothing**. No error. The safety
> check just quietly found zero.
>
> That is why everything is matched by identifier instead of name. We measured
> it: across a fifteen-medication panel, name matching alone finds 63 of the 84
> interactions that are actually in the dataset. **It misses 25%, including two
> rated severe.**"

Then scroll to **Also worth knowing (7)**.

> "There are seven more. Moderate and minor. They are recorded, but they are
> not shouting, and — this is the important part — they are not sent to her
> daughter."

### Beat 4 — The daily check-in (45 seconds)

Scroll to **Today's medication**. Click **I took it** on one row.

> "This is what she actually opens the app for. One tap."

Point at the adherence figure.

> "Just under three quarters over the last seven days. And note that a dose she
> was *told* to skip is counted separately, because being told to stop for a
> day is not a failure to adhere."

**Read the percentage off the screen. Do not quote one from this script.** The
seed's miss pattern is deterministic - the comment in `seed_demo.py` says so -
but it only creates doses that have already come due, so the totals depend on
what time of day you seeded. This script said 86% (38 taken, 6 missed) when it
was written; a rehearsal seeded at 3:57pm showed 73% (36 taken, 13 missed).
Both are correct for their seed and neither is correct in general.

The sentence that is true whatever the number says is the one under the figure:
deliberate skips are counted separately and do not lower it. That is the design
decision worth pointing at. Expect **Stopped: 0** in the demo data, so point at
the explanatory note rather than hunting for a non-zero count.

### Beat 5 — A live FDA recall (90 seconds) — *the one they remember*

Show the terminal. Run the paste-ready command.

> "This is hitting the real FDA openFDA API, right now, live."

When it returns, reload Maria's dashboard.

> "Five recall findings. Look at the difference in wording."

Point at them in turn:

> "One says **'Recall affects your Metformin'** — because Maria's NDC, the
> number on her box, matches the recalled product exactly. That is Cardinal
> Health's metformin, real recall D-0435-2021.
>
> The other four say **'may affect'** and **'check the label'** — same drug,
> but the recall notice doesn't identify a manufacturer, so we genuinely do not
> know.
>
> We sampled 100 current FDA recalls: **45 of them carry no product
> identifier.** A system that alerted on drug name alone would tell her she was
> affected 45% of the time without knowing. Two false alarms and she stops
> reading all of them — including the one that was real."

### Beat 6 — Her daughter's view (60 seconds)

Switch to the second window. Log in as Elena.

> "This is Elena, Maria's daughter. She can see this only because Maria invited
> her and she accepted — and Maria can revoke it in one click."

Point at the alert count.

> "Maria's screen has fifteen findings now — the ten we started with, plus the
> five recalls we just created. Elena's has **three.** Only the serious ones
> reach a caregiver, and the screen says so out loud rather than letting her
> assume she is seeing everything."

**Do not say "a 70% reduction" here.** The measured 70% in EVALUATION.md is ten
findings reduced to three, and it is correct - but it is measured on the
interaction findings alone, before any recall. By this point in the demo beat 5
has added five more, so the screen shows fifteen against three, which is 80%.
Anyone doing the arithmetic while you talk will catch the mismatch.

If you want the measured figure, attach it to the right denominator:

> "On the ten interaction findings on their own, that is the 70% reduction we
> measured. With the recalls included it is higher."

Point at adherence.

> "She sees whether her mother has been taking her medication. She cannot
> change anything. She is watching, not prescribing."

### Beat 7 — Consent, revoked (30 seconds)

Back in Maria's window, in **Who can see this**, click **Remove access**.
Reload Elena's screen.

> "Gone. Immediately — not whenever a session expires. The grant is checked on
> every single request.
>
> And the record stays, greyed out. We never delete who had access and when.
> In a health system that history *is* the accountability."

**Do not re-invite yet** — the next beat needs Elena locked out.

### Beat 7b — The audit log (60 seconds) — *answers "how do you know?"*

**Read this before rehearsing: reloading Elena's screen does not produce a
refusal.** Her dashboard asks "who am I linked to?" first, gets an empty list,
and therefore never requests Maria's record at all. No request, no refusal, no
row. That is correct behaviour and it is worth saying out loud, because it
means the browser is not where the boundary lives. So ask the API directly.

With Elena's locked-out screen still up, run:

```bash
docker compose exec api python -m scripts.demo_refused_read
```

> "Elena's browser cannot even ask any more - her patient list is empty. But a
> browser is just one client. The real boundary is the API, so let's ask it
> directly, the way a stale tab or someone curious would."

It prints three lines. Narrate them:

```
  signed in as elena@safemed.demo              200
  GET her patient's findings            403  {"detail":"You do not have access to this patient"}
  GET a patient that does not exist     403  {"detail":"You do not have access to this patient"}
```

> "She can still sign in - revoking consent is not the same as disabling an
> account, and we did not conflate the two. But the record is refused.
>
> And look at the third line. That is a patient id that does not exist at all.
> Same status, same body, character for character. The refusal does not tell
> you which patients are real - otherwise the error message becomes a way to
> enumerate them."

Now the log:

```bash
docker compose exec db psql -U safemed -d safemed -c "SELECT action, patient_id, created_at FROM audit_events ORDER BY created_at DESC LIMIT 8;"
```

```
 patient_record.access_denied |                                      | 22:50:45.628
 patient_record.access_denied |                                      | 22:50:45.603
 consent.revoked              | fa9c68f9-faa1-4c0b-9299-aebad065ad24 | 22:49:19
 patient_record.viewed        | fa9c68f9-faa1-4c0b-9299-aebad065ad24 | 22:49:01
 patient_record.viewed        | fa9c68f9-faa1-4c0b-9299-aebad065ad24 | 22:49:00
```

> "Reading up from the bottom: Elena read the record - every page load, not
> just the first - then Maria revoked her, then two refused attempts.
>
> And notice the patient column is empty on both refusals. We record that
> someone was refused, and we deliberately do not record who they asked about,
> because the log itself would otherwise confirm that a patient exists. The
> same reason the endpoint returns 403 and not 404.
>
> A log that only records successes cannot answer 'did anyone try?' - and
> that is usually the question you actually have."

**Expect more `patient_record.viewed` rows than there were page loads.** One
caregiver screen produces six: three endpoints (`findings`, `doses/today`,
`adherence`), each hit twice because React's StrictMode deliberately runs
effects twice in development to surface unsafe ones. A production build makes
three. Every read genuinely is a read, so logging each one is correct - but
know the number so you can answer it rather than be surprised by it.

**On the gap between the two consent rows**, if someone asks a database
question. `consent.invited` and `consent.accepted` are written in the same
transaction. PostgreSQL's `now()` returns the *transaction* start time, so with
it both rows get an identical timestamp and their order is lost. The column
defaults to `clock_timestamp()` instead, which reads the real clock each call.
Do not quote a figure for the gap: it tracks machine load, and has been seen at
2.3ms and at 209ms on the same machine. The point is that the order is
recoverable at all.

If asked how solid it is:

> "Append-only, and not by convention - the ORM raises if any code tries to
> change or delete a row, and there's a test for it. Every entry is written
> inside the same transaction as the thing it describes, so there's never an
> entry for something that didn't happen, and never a change with no entry."

*(Re-invite Elena afterwards if you plan to demo again - or just re-run
`scripts.seed_demo`, which restores the grant to ACTIVE.)*

### Beat 8 — Where the AI is, and where it isn't (45 seconds)

> "There's an AI layer, and the interesting part is what it is not allowed to
> do. It never decides whether something is dangerous — that comes from the
> dataset, deterministically, before any model runs. It never receives patient
> data, only drug names. And every response it produces is checked against
> eleven rules and **discarded** if it tells someone to stop or change a
> medication.
>
> Turn the AI off completely and every finding here still works. The AI makes
> SafeMed easier to understand. It is never what makes it correct."

---

## If something breaks

| Symptom | Do this |
|---|---|
| Dashboard won't load, spinner forever | API is down. `docker compose restart api`, wait 10s, reload |
| "Could not reach SafeMed" | Same — and it is *supposed* to say that rather than show a blank screen. You can say so |
| Recall command hangs | Worker is down. `docker compose restart worker`. If it still hangs, **skip beat 5** and move to Elena — do not debug on stage |
| Login fails | Re-run `scripts.seed_demo` |
| Findings are duplicated | You re-seeded mid-demo. Harmless, but re-seed cleanly |
| Frontend blank after a git pull | Stop the dev server, `npm install --prefix frontend`, start it again |

**The rule for stage:** if a beat fails, say one sentence and move on. "The
worker's not responding — I'll come back to that." Never debug live. Beats 3,
6 and 7 carry the presentation on their own.

---

## Questions you will be asked

**"Couldn't ChatGPT just tell you about drug interactions?"**

> It could describe one. It can't monitor. The point isn't answering a question
> once — it's that a recall was published at 3am on a Tuesday and something
> checked Maria's specific NDC against it. And an LLM asked "is this
> dangerous?" answers confidently whether or not it's right, with no citation.
> Every finding here points at a dataset a pharmacist can check.

**"How do you know the interaction data is any good?"**

> DDInter — curated, peer-reviewed, published in Nucleic Acids Research,
> 160,000 interaction pairs. We cite it. And the safety engine depends on an
> interface, not on DDInter, so the source is swappable — which matters,
> because the NLM's own interaction API was retired in January 2024. Building
> on a single live API would have sunk the project.

**"What happens when a service is down?"**

> It degrades instead of failing. If RxNorm is unreachable, the medication
> still saves and gets checked by name — weaker, and the interface says
> "Checked by name only" rather than hiding it. If the AI is unavailable, every
> finding still displays. Nothing in the safety path depends on a service being
> up.

**"That's a Class I recall — the FDA's most serious class — and you're only showing it as Moderate?"**

> Severity here is two axes, not one: how serious the FDA says the recall is,
> and how sure we are it is her product. A Class I recall we cannot tie to her
> specific NDC is Moderate - serious, but unconfirmed. A Class I we *can* tie
> to her NDC is Severe and goes to her daughter. We do not let FDA class alone
> drive the alert, because that would send a caregiver an alarm about a product
> the patient may not even have.

The matrix is in `app/services/recalls.py`:

| | Class I | Class II or III |
|---|---|---|
| **CONFIRMED** - her NDC matches | SEVERE | MODERATE |
| **POSSIBLE** - drug name only | MODERATE | MILD |

Which is why no recall in the demo reaches Elena: the confirmed one is Class II
and the Class I ones are unconfirmed. If that looks like the system
under-reacting, it is the same argument as the 45-of-100 number - a caregiver
who gets two false alarms stops reading the third.

**"It's four in the afternoon — why does it say the 8pm dose was missed?"**

> There are two kinds of time on that screen and we treat them differently on
> purpose. A *schedule* is what the patient typed: she asked for 8:00, so she
> sees 8:00. If we converted it to her browser's zone she would see 2:00 AM,
> and the number she typed would not be the number she reads back, which looks
> broken. An *event* timestamp - when a finding was detected, when access was
> removed - is a real instant, so that one does render in your local zone.
>
> The gap is that there is no time zone on the user record yet, so "missed" is
> computed against UTC. That is a listed limitation and the real fix is a zone
> on the user. What we refused to do was guess a zone and print a confident
> wrong hour, which is the failure this whole project is about.

The reasoning is written at the top of `frontend/src/pages/dashboard/format.ts`
if anyone wants to see it. Do not be defensive about this: it connects the one
cosmetic oddity on screen to the central argument of the project.

**Know what the screen will show before you walk in.** Dose rows are UTC, so
what reads as "missed" depends on the gap between UTC and your local clock,
not on the data. Central time is UTC-6, so:

| You present at | UTC is | 8:00 AM row | 8:00 PM row |
|---|---|---|---|
| 9:00am CST | 15:00 | past, loggable | still ahead |
| 2:00pm CST | 20:00 | past, loggable | just come due |
| 5:00pm CST | 23:00 | past | past - shows Missed |

Earlier in the day is the better-looking demo, because fewer rows have come
due. Check the screen after seeding and know which rows read as missed, so the
question does not surprise you mid-sentence.

**"What happens if the audit log itself fails?"**

> A caregiver's *read* is still served, and the failure is logged loudly. A
> write — a consent change, a medication change — is not: it rolls back with
> its audit row, because the two share a transaction. That split is
> deliberate. Refusing to show someone a severe interaction because a logging
> table was unavailable is the worse of the two harms. A hospital under a
> real regulatory obligation would make the opposite call, and we'd change it.

**"Is it really append-only?"**

> Within the application, yes, and enforced rather than promised — SQLAlchemy
> listeners raise on any update or delete, and there are tests for both.
> Someone with direct database access can still rewrite the table. Real
> tamper-evidence needs cryptographic chaining, and we didn't build that.

**"Is this a medical device?"**

> No, and it is built not to become one. It does not diagnose, prescribe, or
> ever tell anyone to change or stop a medication. It surfaces published safety
> information about a list you gave it and tells you to talk to a pharmacist.
> That boundary is enforced in code — the AI guardrails actively discard any
> response that crosses it.

**"What's the hardest problem you hit?"**

> Aspirin and warfarin returning nothing. Not because it was hard to fix, but
> because it taught us the failure mode that matters here is the *silent* one.
> A crash tells you something is wrong. A safety check that quietly finds zero
> looks exactly like good news.

**"What would you do next?"**

> Three things. A way to *read* the audit log — we write it, and it's
> queryable by SQL, but there's no review screen, and a log nobody can read
> is a log nobody checks. Per-user time zones: right now a schedule is stored
> as wall-clock UTC. And a second interaction dataset, so we could say
> something about completeness rather than only about our own consistency.

**"A severe finding appears at 3am. Does Elena get a text message?"**

> No, and that is a deliberate boundary rather than an unfinished feature.
> Nothing is sent. She sees it when she opens the app.
>
> The `notifications` table exists with channel and delivery-status columns —
> `EMAIL`, `SMS`, `PENDING`, `SENT`, `FAILED` — because that is what delivery
> *would* need. Nothing writes a row. We stopped at the point where we would
> have had to claim an alert was delivered without being able to prove it, and
> an alert you cannot prove arrived is worse than a dashboard you know she can
> read: it lets everyone assume she was told.
>
> The gap is in the report as a limitation, and wiring the model to a
> transport **with delivery status and retry** is item four in future work. The
> schema is the honest part — it records what the design would require, and the
> ER diagram labels that relationship `"would alert"`.

**"Could someone read the audit log in the app?"**

> Not yet, and it's the first thing we'd build. The rows are written and
> queryable, but only by SQL — which means the people the log protects cannot
> see it. That is why I am showing it to you from `psql` and not from a screen.

**"How much is AI-generated?"**

> Answer this one honestly and specifically. Say what you designed, what you
> decided, and what you can explain. You can explain every decision in this
> project — that is what the handbook was for.

---

## The four numbers to memorise

| | |
|---|---|
| **25%** | of real interactions missed by name matching alone (2 of them severe) |
| **45 of 100** | FDA recalls carry no product identifier — hence CONFIRMED vs POSSIBLE |
| **70%** | reduction in what reaches a caregiver, via severity routing — measured on the 10 interaction findings reduced to 3, so quote that denominator, not the 15 on screen after beat 5 |
| **160,235** | interaction pairs, 99.8% identifier-addressable |

Full method and threats to validity in [EVALUATION.md](EVALUATION.md).

---

## One last thing

The strongest moment in this demo is not a feature. It is beat 3, when you say
the safety check returned nothing and no error. Markers have seen a lot of
projects that work. They have seen very few students explain a bug that was
invisible, why it was invisible, and what they changed so it could not happen
again.

Do not rush that part.
