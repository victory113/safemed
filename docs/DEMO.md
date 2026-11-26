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

Point at the adherence figure changing.

> "86% over the last seven days — 38 taken, 6 missed. And note that a dose she
> was *told* to skip is counted separately, because being told to stop for a day
> is not a failure to adhere."

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

> "Maria's screen had fifteen findings. Elena's has **three.** Only the serious
> ones reach a caregiver — a 70% reduction — and the screen says so out loud
> rather than letting her assume she's seeing everything."

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

### Beat 7b — The audit log (45 seconds) — *answers "how do you know?"*

With Elena's refused screen still up, run this where the room can see it:

```bash
docker compose exec db psql -U safemed -d safemed -c "SELECT action, created_at FROM audit_events ORDER BY created_at DESC LIMIT 8;"
```

You will get something close to this — verified on a clean seed:

```
 patient_record.access_denied | 23:21:24.121187
 consent.revoked              | 23:21:23.969529
 patient_record.viewed        | 23:21:23.645082
 patient_record.viewed        | 23:21:23.363048
 consent.accepted             | 23:21:11.696452
 consent.invited              | 23:21:11.694967
```

> "Consent says what someone is *allowed* to see. This says what they
> actually did.
>
> Reading up from the bottom: Maria invited Elena, Elena accepted, Elena read
> the record — every page load, not just the first — then Maria revoked her.
> And the top row: `patient_record.access_denied`. Elena tried again after
> being revoked, and the attempt is on the record.
>
> A log that only records successes can't answer 'did anyone try?' — and
> that's usually the question you actually have."

**The gap between those two rows is worth knowing about**, if someone asks a
database question. `consent.invited` and `consent.accepted` are written in the same
transaction. PostgreSQL's `now()` returns the *transaction* start time, so
with it both rows get an identical timestamp and their order is lost. The
column defaults to `clock_timestamp()` instead, which reads the real clock
each call - which is why those two rows are a measurably different time rather
than tied. Do not quote a figure: it tracks machine load, and has been seen
at 2.3ms and at 209ms on the same machine. The point is that the order is
recoverable at all.

**Expect more `patient_record.viewed` rows than there were page loads.** One
caregiver screen produces six: three endpoints (`findings`, `doses/today`,
`adherence`), each hit twice because React's StrictMode deliberately runs
effects twice in development to surface unsafe ones. A production build makes
three. Every read genuinely is a read, so logging each one is correct — but
know the number so you can answer it rather than be surprised by it.

If asked how solid it is:

> "Append-only, and not by convention — the ORM raises if any code tries to
> change or delete a row, and there's a test for it. Every entry is written
> inside the same transaction as the thing it describes, so there's never an
> entry for something that didn't happen, and never a change with no entry."

*(Re-invite Elena afterwards if you plan to demo again.)*

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
| **70%** | reduction in what reaches a caregiver, via severity routing |
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
