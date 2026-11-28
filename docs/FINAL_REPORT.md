# SafeMed — Final Project Report

**A Continuous Medication Safety Monitoring and Caregiver Alert Platform**

CSCI 4490 — Software Engineering · Fall 2026
University of Central Arkansas · Instructor: Md Jobair Hossain Faruk, Ph.D.

| | |
|---|---|
| **Victory Orobosa** | Project Leader, Full-Stack Development |
| **Chima Onochie** | Backend and Data Integration |
| **Pacifique Mugisha** | Security, Testing and Deployment |

Repository: https://github.com/victory113/safemed
Submitted 24 November 2026

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Introduction and Problem Statement](#2-introduction-and-problem-statement)
3. [Requirements Analysis](#3-requirements-analysis)
4. [Software Modeling and Design](#4-software-modeling-and-design)
5. [Implementation](#5-implementation)
6. [Testing and Quality Assurance](#6-testing-and-quality-assurance)
7. [Evaluation and Results](#7-evaluation-and-results)
8. [Project Management](#8-project-management)
9. [Challenges and Lessons Learned](#9-challenges-and-lessons-learned)
10. [Limitations and Future Work](#10-limitations-and-future-work)
11. [Conclusion](#11-conclusion)
12. [References](#12-references)

---

## 1. Executive Summary

SafeMed is a working software system that continuously monitors a patient's
medication list against authoritative drug-interaction and FDA recall data,
and surfaces potential safety issues to the patient and — with the patient's
explicit, revocable consent — to a caregiver.

The central engineering claim is that **safety determination must be
deterministic and sourced, and artificial intelligence must sit strictly
downstream of it.** AI in SafeMed never decides whether a combination is
dangerous; it rephrases a finding that already exists, already carries a
citation, and already has a severity drawn from the source data.

**Delivered:** a modular monolith in FastAPI and PostgreSQL with an
asynchronous Celery worker, a React and TypeScript single-page frontend,
160,235 imported interaction pairs, live integration with the FDA openFDA
enforcement API, consent-based role access, an append-only audit trail, and
194 automated tests running in continuous integration on every push.

**Measured, not asserted:**

| Finding | Result |
|---|---|
| Interactions missed by name matching alone | **25%** (21 of 84), two rated severe |
| FDA recalls carrying no product identifier | **45 of 100** sampled |
| Reduction in findings reaching a caregiver | **70%** |
| Duplicate findings across three full re-runs | **0** |
| Median safety evaluation time | **7.2 ms** |

---

## 2. Introduction and Problem Statement

### 2.1 The problem

Harm from medication frequently arises not from one bad prescription but from
two safe prescriptions issued by two different prescribers who never see each
other's work, with no single party holding the complete list. The FDA has
estimated that medication errors injure a large number of people in the
United States annually, and separately reports receiving more than 100,000
reports a year associated with suspected medication errors.

The information needed to catch many of these problems is public. RxNorm
standardises drug naming. The FDA publishes enforcement and recall reports.
Curated interaction datasets exist and are peer-reviewed. The gap is not
knowledge; it is that none of this information is anywhere near the person
actually taking the tablets, and none of it is watching continuously.

### 2.2 Why this is a software engineering problem

A single question could be answered by asking any competent source once.
What cannot be done by asking is **monitoring**: a recall published at
03:00 on a Tuesday, checked automatically against one specific patient's
specific product code, with the result routed to the right person at the
right severity and the whole transaction recorded.

That is a systems problem — scheduling, idempotency, data normalisation,
authorization, auditability — and it is the problem SafeMed addresses.

### 2.3 Scope and boundary

SafeMed deliberately does not diagnose, prescribe, or advise anyone to start,
stop or change a medication. Every finding directs the reader to a pharmacist
or physician. This boundary is not a disclaimer; it is enforced in code, and
Section 5.5 describes the mechanism.

All development, testing and demonstration uses synthetic data. No real
patient record has been processed at any point.

---

## 3. Requirements Analysis

The complete specification is [REQUIREMENTS.md](REQUIREMENTS.md). This
section summarises the method and the outcome.

### 3.1 Method

Requirements were derived top-down: five business requirements describing the
harm to be reduced, ten user requirements expressed from the patient's and
caregiver's point of view, and thirty-seven functional requirements that
implement them. Eleven non-functional requirements, five AI-specific
requirements and three boundary constraints complete the set.

### 3.2 Structure

| Class | Count | Example |
|---|---|---|
| Business (BR) | 5 | BR-04: every safety claim must be attributable to a named, checkable source |
| User (UR) | 10 | UR-06: as a caregiver, I want only the serious alerts, so I am useful without being intrusive |
| Functional (FR) | 37 | FR-27: an unknown patient and an unauthorized patient must produce identical responses |
| Non-functional (NFR) | 11 | NFR-05: failure of any external service must degrade functionality, not prevent it |
| AI (AIR) | 5 | AIR-02: AI input must contain drug names and source text only |
| Boundary constraints (BC) | 3 | BC-01: the system must never instruct a user to change a medication |

### 3.3 Verifiability

Every functional requirement names the automated test that verifies it rather
than asserting coverage in prose. FR-32, for example — that the application
must not permit an audit record to be modified or deleted — points at
`test_audit.py::test_an_audit_row_cannot_be_updated` and
`::test_an_audit_row_cannot_be_deleted`. A reader can run them.

The traceability matrix in REQUIREMENTS.md §8 maps every business requirement
through its user requirements to its functional requirements and test count.

### 3.4 Requirements deliberately not met

REQUIREMENTS.md §9 lists six, including the absence of an interface for
reading the audit log and the unused `notifications` table. These are stated
in the specification rather than discovered by a reader.

---

## 4. Software Modeling and Design

The complete design document, with six diagrams, is [DESIGN.md](DESIGN.md).

### 4.1 Architectural style

SafeMed is a **modular monolith with an asynchronous worker**. Microservices
were considered and rejected: a three-person team in one semester cannot
operate a distributed system *and* build the thing being distributed, and the
project's real difficulty is drug-data correctness rather than scale.

Module boundaries are nonetheless real and enforced by import direction. No
module in `app/services/` or `app/repositories/` imports from `app/api/`,
which is why the safety engine is testable without an HTTP request.

### 4.2 The governing data flow

```
Authoritative data → Deterministic engine → Verified finding → AI explains it
```

The direction of that arrow is the architecture's single most important
property. Reversing it — patient data into a model, asking "is this safe?" —
produces a system that answers confidently whether or not it is correct, with
no citation and no way to check.

### 4.3 Design decisions visible in the schema

| Decision | Consequence |
|---|---|
| `rxcui` is nullable | RxNorm being unreachable cannot stop a patient recording a medication; the UI then says "Checked by name only" |
| `dedupe_key` hashes the finding's subject, never the time | Re-evaluation is idempotent; a second run creates nothing |
| `ai_explanation` is nullable | Four distinct AI failures all leave the finding complete and displayable |
| `audit_events.created_at` defaults to `clock_timestamp()` | `now()` returns transaction start time, so rows written in one request would otherwise share a timestamp and lose their order |

### 4.4 Views modelled

DESIGN.md presents the logical (module) view, the data model as an ER
diagram, the process view showing five containers at runtime, three key
scenarios as sequence diagrams, and the development view of source
organisation.

---

## 5. Implementation

### 5.1 Technology stack and rationale

| Layer | Technology | Why |
|---|---|---|
| Frontend | React 19, TypeScript 6, Vite 8 | Type errors caught at build; no router dependency needed for four routes |
| API | FastAPI, Pydantic v2 | Request validation and OpenAPI documentation derived from the same type declarations |
| Data | PostgreSQL 16, SQLAlchemy 2.0, Alembic | Real constraint behaviour and server-side defaults; versioned, reversible schema |
| Background | Celery, Celery Beat, Redis 7 | Monitoring must continue when nobody is using the application |
| Containers | Docker Compose | Five services from a clean checkout; `scripts/setup.sh` adds the schema and dataset steps starting them does not cover |
| CI | GitHub Actions | Tests, type check, lint and migration check on every push |

PostgreSQL was chosen over SQLite deliberately. The application depends on
server-side defaults and real constraint enforcement; a test suite running
against a different database is testing something that is not shipped.

### 5.2 Scale

| | Lines |
|---|---|
| Backend application | 4,234 |
| Backend tests | 3,054 |
| Frontend | 2,862 |
| Documentation | 4,136 |

47 commits between 30 October and 24 November 2026.

### 5.3 Drug name normalisation — the project's defining problem

The interaction dataset does not call aspirin "aspirin". It calls it
*Acetylsalicylic acid*. When the safety engine was first built and matched on
names, the combination of warfarin and aspirin — a textbook major
interaction — returned **nothing**. No error, no warning, no exception: a
safety check that quietly found zero.

This is the failure mode that matters in a safety system, and it drove the
decision to resolve every medication to an RXCUI via RxNorm and match on
identifiers. Section 7.1 quantifies what name matching was missing.

### 5.4 Tiered recall matching

An FDA enforcement report often does not identify the manufacturer of the
affected product. SafeMed therefore distinguishes two cases:

- **CONFIRMED** — the recall names the exact product code the patient holds.
  Wording: "Recall affects your Metformin."
- **POSSIBLE** — same drug, no product identifier in the notice. Wording:
  "May affect — check the label."

A system that alerted on drug name alone would tell a patient they were
affected 45% of the time without knowing. Two false alarms and the patient
stops reading all of them, including the one that was real.

### 5.5 How the AI boundary is enforced

Three mechanisms, all testable:

1. **The model never judges.** Severity comes from the dataset. By the time
   the AI layer runs, the finding already exists with its source and rating.
2. **No patient data is sent.** The model receives drug names and the
   source's own description — never a name, age, email, identifier or
   medication list. The privacy property is structural: there is no payload
   to leak.
3. **Every response is validated before storage.** Eleven forbidden patterns
   catch any instruction to stop, change or adjust a medication; a required
   pattern ensures the reader is directed to a professional. A response
   failing either check is discarded, not shown.

Disabling AI entirely leaves every finding complete. The full test suite
passes with the AI layer switched off.

### 5.6 The audit trail

Every consent change, medication change, caregiver read and **refused**
caregiver read is recorded. Two design properties:

**Writes share the caller's transaction.** `record_event` flushes but never
commits, so an action and its audit row are saved together or roll back
together. There is never an entry for something that did not happen.

**Append-only is enforced, not promised.** SQLAlchemy `before_update` and
`before_delete` listeners raise, with tests proving they do. The original
model said "append-only by convention" — a convention is a comment, and it
holds only until someone who has not read it writes code.

One deliberate exception: on a **read** path, if the audit write itself
fails, the read is still served and the failure logged loudly. Refusing to
show a caregiver that their mother has a severe interaction because a logging
table was unavailable is the greater of the two harms. A system under a real
regulatory obligation would make the opposite choice, and the reasoning is
recorded in the code so that the trade is deliberate rather than accidental.

---

## 6. Testing and Quality Assurance

### 6.1 Strategy

**194 automated tests** across 16 files, run against a real PostgreSQL
instance rather than an in-memory substitute.

| Area | Tests |
|---|---|
| Consent and access control | 24 |
| Dose scheduling and adherence | 37 |
| Interaction matching | 17 |
| Recalls | 22 |
| Safety engine | 13 |
| Caregiver views | 13 |
| Audit | 30 |
| AI guardrails | 15 |
| Repositories | 10 |

### 6.2 Two fixture decisions

**Every test runs inside a transaction that is rolled back.** Tests cannot
see each other's data, so they pass in any order, and the suite is safe to
run repeatedly — a suite you are reluctant to run is a suite you stop
running.

**The schema is dropped before it is created.** `create_all()` does not alter
existing tables, so without the drop, the first model change makes every test
fail with "column does not exist", and the cause looks like the new code
rather than a stale test database.

### 6.3 Testing authorization at the boundary

Access-control tests do not call the permission functions directly. They
start the application, register real users, log in for real tokens, and make
real HTTP requests. A unit test of a permission function proves the function
works; it proves nothing about whether the route *uses* it — and a route that
forgets its dependency is exactly how authorization is bypassed in practice.

### 6.4 Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request: the backend
suite against a PostgreSQL service container, frontend type checking, linting
and unit tests, and a migration check — as two parallel jobs so a frontend
error cannot mask a backend failure.

The migration check was added late and immediately found a real defect. The
test suite builds its schema from the models and never invokes Alembic, so a
broken migration had always passed CI. Running upgrade → downgrade → upgrade
revealed that the initial migration dropped its tables but left all eleven
PostgreSQL ENUM types behind, so the second upgrade failed on
`type "user_role" already exists`. The migration chain was one-way: a deploy
could be rolled back but never re-applied — discovered, had it not been
caught, at the exact moment of rolling back.

### 6.5 When the test is wrong

While adding dose history, a test was written asserting that history returns
nothing for days before any doses existed. It failed. The code was right and
the assumption was wrong: a dose *schedule* is a standing instruction, while
a dose *event* is a row that exists only once generated. The test was
rewritten to state the real behaviour and no application code changed.

A failing test is a disagreement between two things the team wrote. Deciding
which of the two is wrong — rather than reflexively changing the code — is a
practice this project adopted explicitly.

---

## 7. Evaluation and Results

Three design decisions cost real complexity. Each was measured rather than
argued. `backend/scripts/evaluate.py` runs the experiments and regenerates
[EVALUATION.md](EVALUATION.md).

### 7.1 Identifier matching versus name matching

**Method.** A fifteen-medication panel, written the way a patient would say
them. The same interaction source is queried twice — once with names only,
once with names and RXCUIs. Same drugs, same dataset, same code path; the
only variable is whether identifiers are available.

| Measure | Result |
|---|---|
| Panel size | 15 medications |
| Resolved to an RXCUI | 15 / 15 |
| Interactions found, names only | 63 |
| Interactions found, with RXCUI | 84 |
| **Missed by name matching alone** | **21 (25%)** |
| Of those, rated SEVERE | 2 |

**Result.** Name matching recovers 75% of the interactions the same dataset
holds for the same patient. The missed set includes aspirin + warfarin and
aspirin + ibuprofen, both rated Major.

### 7.2 Dataset coverage

| Measure | Result |
|---|---|
| Interaction pairs imported | 160,235 |
| Pairs with both RXCUIs | 159,906 |
| Identifier-addressable | 99.79% |

The remainder still match by name, so coverage degrades rather than
disappearing.

### 7.3 Recall identifiability

Of 100 sampled current FDA enforcement reports, **45 carry no product
identifier**. This is the measurement behind the CONFIRMED / POSSIBLE
distinction: without it, 45% of recall alerts would assert an effect the
system cannot actually establish.

### 7.4 Severity routing

| Measure | Result |
|---|---|
| Findings shown to the patient | 10 (3 severe, 5 moderate, 2 mild) |
| Findings reaching the caregiver | 3 |
| **Reduction** | **70%** |

### 7.5 Idempotency and performance

Three consecutive full re-runs of the safety evaluation and recall check
produced **0** duplicate findings. Median evaluation time for a realistic
list was **7.2 ms**, slowest run 9.9 ms.

### 7.6 Threats to validity

Stated in EVALUATION.md and repeated here because they qualify every number
above:

- The fifteen-medication panel was **chosen, not sampled**. It is realistic,
  not statistically representative.
- **One interaction dataset.** These figures measure internal consistency,
  never completeness against ground truth.
- **The recall sample is a snapshot** of ongoing recalls on the day it was
  taken, not a longitudinal study.
- **No clinical validation.** Nothing here says SafeMed improves anyone's
  health — only that it finds interactions a name-matching system misses and
  raises fewer false alarms than a naive one.

---

## 8. Project Management

### 8.1 Roles

| Member | Role | Principal contributions |
|---|---|---|
| Victory Orobosa | Project Leader, Full-Stack | Data model, safety engine, RxNorm and recall integration, dose scheduling, AI layer and guardrails, patient and caregiver frontends, CI, evaluation, documentation |
| Chima Onochie | Backend and Data Integration | JWT authentication and password hashing, consent grants and RBAC, caregiver view endpoints, the append-only audit log |
| Pacifique Mugisha | Security, Testing and Deployment | Accessible login and registration interface, form validation and its tests, API client error handling |

### 8.2 Process

- **Version control:** GitHub, feature branches, pull requests, 47 commits.
- **Continuous integration:** every push and pull request runs the full suite.
- **Code review:** branches were reviewed before merge; findings were recorded
  and addressed in follow-up commits rather than silently amended.
- **Issue tracking:** GitHub Issues with labels, mapped onto a project board.

### 8.3 Integration practice

Two integration conflicts occurred and both are instructive.

A teammate independently built an API client layer that already existed on
`main`. Rather than discard the branch, it was reviewed and three genuine
improvements were extracted and merged with co-authorship: a race condition
in token handling that the original had not considered, a double-submit
guard, and suppression of server error detail from reaching a patient's
screen. The root cause was a coordination failure — the overlap was not
announced before work began — and it changed how file ownership was
communicated thereafter.

The audit log was assigned to one member and built by them. On review, three
gaps were identified and fixed in a follow-up commit: a failing audit write
took the caregiver's dashboard down with it, refused access attempts left no
trace, and three defined action constants were unused. The original author's
reasoning was preserved where it was correct — the decision not to record a
refusal as a *view* was right, and the fix recorded it under a distinct
action instead.

---

## 9. Challenges and Lessons Learned

**9.1 The silent failure.** During testing we asked SafeMed about a patient
taking aspirin and warfarin, a pair DDInter grades Major. The check returned
nothing. There was no error, no failed request, and nothing in the logs. The
dashboard rendered a green success panel titled "No safety concerns found",
with the line "Nothing needs your attention right now."

The cause was not a logic error. The name matching compared the medication
names the patient had entered against the names stored in the interaction
dataset, and it did that correctly. The problem is that a patient types
"aspirin" and DDInter stores "Acetylsalicylic acid". The two strings never
match, so a Major interaction came back as an empty list. What was broken was
an assumption about the data, not the code acting on it.

We consider this more dangerous than a crash for three reasons.

The first is that the screen is identical. Zero findings because the patient
is safe and zero findings because the lookup is broken produce the same green
panel. Nothing in the response distinguishes them.

The second is that nobody has done anything wrong. Both prescriptions are
correct and the patient takes both as directed. The risk lives in the
combination, and the one system whose job was to catch combinations reported
that there was nothing to report.

The third is the reason we now think of a silent zero as the worse failure. A
patient opens SafeMed because they are not certain their medications are safe
together. Had the check crashed, they would still be uncertain, and that
uncertainty is what sends someone to a pharmacist. The green panel answers the
question, so it displaces the one step that would have caught the problem
without us. A crash fails safely; this did not.

It also would not have been found by anyone using the software. A crash
produces a signal, and signals get reported. This produced none. The patient
saw green and closed the app, the caregiver saw nothing serious and closed the
app, and neither had anything to report, because from where they sat nothing
had happened. We found it only by going to look for it: measuring name
matching against the full dataset showed 21 of 84 interactions missed, two of
them severe.

The fix was to match on RxNorm identifiers, keeping name matching as a
fallback for drugs that do not resolve. What changed more lastingly is how we
write tests. Our fixtures had been passing because we wrote them ourselves, in
the names we expected, so they confirmed the same assumption that caused the
bug. The regression test now stores DDInter's own spelling and asserts both
halves: that name lookup still returns nothing, and that identifier lookup
finds the severe interaction. Asserting the failure keeps the assumption
visible, and stops a later reader deleting the identifier matching as
redundant. More generally, we stopped treating passing examples as evidence of
coverage. A fixture only tests the case you thought of, so anything
safety-relevant is now also measured against the real dataset, where a count
says how large the gap is rather than whether one case works.

**9.2 Choosing data sources under constraint.** Our first plan was to call the
NLM's RxNav Drug Interaction API. Checking it in week one, before any of the
safety engine existed, we found it had been retired in January 2024. Only the
interaction endpoint was withdrawn; RxNorm itself remains available, and
SafeMed still calls it to turn a typed medication name into an RXCUI.

Losing the endpoint changed the architecture rather than just the supplier.
Interaction data became something we hold rather than something we ask for:
DDInter is downloaded as CSVs and imported into our own PostgreSQL, 160,235
pairs, by `scripts/import_ddinter.py`. Nothing in the running system contacts
a third party to produce a safety finding.

We then did something that needs defending, because DDInter has not gone
anywhere. Rather than query it directly from the safety engine, we put an
interface in front of it - `InteractionSource`, a Protocol with one method -
and named a replacement we have not built, the ONC high-priority interaction
list combined with FDA label text. The engine depends on the interface, so a
second source is a new class and one line of configuration.

Two things justify that. The first is that DDInter being open-access for
academic use is not the same as being cleared for redistribution in a deployed
health product; if that distinction ever mattered, it would matter suddenly.
The second is the stronger one, and it is not a hedge against failure at all.
Our evaluation states plainly that having a single dataset means we measured
internal consistency rather than completeness. The only way to address that is
to run a second source alongside the first and compare them. Behind the
interface, that is an addition. With DDInter's queries spread through the
safety engine, it would be a rewrite, and we would be choosing between a known
gap in our safety claims and work we do not have time for.

If this looks like speculative over-engineering, the answer is that we were not
speculating. A data source had already been withdrawn from this project, in
week one, and the body that withdrew it was the US National Library of
Medicine - the institution maintaining the country's standard drug vocabulary.
An open-access dataset maintained by a research group is not a safer bet than
that. The interface costs about twenty lines and no inheritance, which is a
small price against a risk we had already watched arrive once.

Discovering the same thing in week ten would have been materially worse, and
not only because of the time. By then the local-data architecture would not
exist: no `drug_interactions` table, since the table exists precisely because
the data lives with us, no import pipeline, and no dataset to evaluate
against. We would have built all of it in the last fortnight.

The specific consequence is worth stating, because it cuts against us. The
retired endpoint took identifiers, so the live-API design has no name-matching
step and the failure described in 9.1 could not occur in it. Name matching is
a cost of holding the data ourselves. Building the import under week-ten
pressure would have introduced that failure mode for the first time with no
time left to measure across the dataset - so the bug we are most pleased to
have caught is the one we would have shipped. The decision that created the
problem also created the only instrument that found it, and we needed the nine
intervening weeks to use it.

The habit that came out of this outlasted the specific choice. Any external
service may degrade a feature and must never block a core operation. RxNorm is
somebody else's server, so a failed lookup returns no match instead of
raising: the medication still saves with `rxcui = None` and the safety engine
falls back to name matching for that entry. The AI explanation layer follows
the same rule. Losing RxNav did not just cost us a supplier; it told us what
to assume about everyone else's.

**9.3 Coordinating a team of unequal pace.** The clearest instance is datable
to the hour. On 19 November, Pacifique branched from main at 12:32 and
committed `frontend/src/api/client.ts` at 16:00, fifty-one lines, alongside
`auth.ts` and changes to the sign-in form. At 19:38 the same evening, Victory
committed `frontend/src/api/client.ts` as well, a hundred and seventy-six
lines, as part of wiring the dashboard. Both commits create the same file from
nothing, which is why the branch would not merge: the conflict was add against
add rather than an ordinary overlap.

It matters that Pacifique committed first. The convenient account is that his
branch duplicated work already in main, and the timestamps refuse it - at
16:00 there was nothing to duplicate, because the file did not exist. Victory's
version is the one that survived, and it survived on merit, with session
handling and error paths the shorter version did not have. That is not a
process defence.

Each of us contributed a different half of the failure. His work was invisible
because it stayed on an unpushed local branch for hours. Victory's was
unannounced because it went to main directly, so even a pushed branch would
have gone unnoticed without someone choosing to look. Neither of us had any
obligation to look.

The deeper cause is in how the two tasks were worded. One was "connect the
account forms to the API"; the other was "wire the frontend to the API and add
the patient dashboard." Those are the same sentence written twice, and neither
names a file. Two people can satisfy two differently worded outcomes by
writing the same module, and discussion cannot reliably prevent it, because
spotting the overlap requires both people to have imagined the same
implementation in advance.

The section title is "unequal pace," and the record does not support reading
that as the slower members being the problem. On 19 November one of us merged
three feature branches and then committed the safety engine, FDA recall
monitoring, the Celery worker, the AI explanation layer, the frontend wiring,
the patient dashboard, the caregiver view, consent controls, five handbook
chapters, the evaluation script and the demo script. Against that rate,
collision is arithmetic rather than misfortune: anyone working in parallel
stands in territory about to be built over, and their own speed has no bearing
on it. Velocity concentrated into unannounced bursts is what makes the overlap
window wide, so the burden of announcing belongs with whoever is generating it.

What we did after the collision is the part we would repeat. The branch was
reviewed rather than discarded, and seven changes from it are in main across
two commits that credit him as co-author: a 401 that only clears the token
when it is still the one that request sent, so a slow response cannot destroy
a newer session; a ref-based double-submit guard, because `setState` is not
synchronous and a fast double-tap could create two accounts; a committed
`.env.example`; a 500 that shows "SafeMed is temporarily unavailable" instead
of the server's own detail; and three smaller corrections to error wording and
request headers. Rebuilding work is a waste. Throwing away the judgment inside
it is a larger one.

The same root cause appeared in a second form that took nine days to notice.
`tests/auth-validation.test.mjs` was committed on 10 November with five
passing tests, and nothing in the project ran it, because there was no `npm
test` script. Work existed and no one could see it - not hidden, just outside
the view of every mechanism we had.

From week one we would change four things, and each is a mechanism rather than
an intention, because a three-person team fitting this around coursework will
not sustain anything that depends on everyone remembering. Tasks would be
assigned by directory rather than by outcome, so a boundary violation is
visible in a diff before it merges and could be enforced with CODEOWNERS.
Branches would be pushed daily even when incomplete, on the rule that
unpushed work does not exist. An issue would be claimed on the board before
its first commit, which is a thing the board could have done for us from the
start and did not. And whoever is about to commit a large amount of work would
say which directories it touches first, since that cost falls on the person
best able to pay it.

**9.4 Deciding what *not* to build.** Three things were cut: email and SMS
notification, per-user time zones, and a screen for reading the audit log.
All three are declared in the requirements specification under "Requirements
Deliberately Not Met," with the reason for each, rather than left for a reader
to discover.

The rule we applied, stated as what we refused rather than what we allowed,
was that nothing could be cut if it changed what the system is able to claim
about safety. The things protected when time ran short - the audit log, RXCUI
matching, consent enforcement, the guardrails on the AI layer - each determine
whether a finding is correct, whether it is complete, or whether the person
reading it is entitled to see it. The three that went are layers sitting
on top of determinations already made and tested. Notification re-delivers
findings the caregiver dashboard already shows, which is why UR-06, "see only
the serious alerts for someone who invited me," is satisfied without it. Per-user time
zones restyle a schedule already computed correctly. A review screen reads
records that are already written, already immutable and already queryable.
None of the three changes what SafeMed knows; they change how conveniently it
is conveyed.

A second rule came out of the time zone decision, and it is the same principle
as 9.1 applied to scope rather than to code. We could have displayed local
times without knowing any user's zone, which shows a confident and wrong hour.
Instead the interface displays UTC, which is correct and inconvenient.
Descoping may make a system less convenient. It may not make it quietly
incorrect.

The visible residue is one table. `notifications` exists, with its channel and
status enums, and nothing writes a row to it. The useful question is not why it
is still there but why it was ever created, and the answer is that it is in the
initial migration, `c7cbadec06cf`, written in week one alongside every other
table. The schema was therefore a forecast of the system rather than a record
of it, and a forecast is wrong in places. Dead schema is what that error looks
like six weeks later. Had the data model been grown alongside the code, the
table would never have been created, and the thing we would defend is a
decision not to add it rather than a decision not to remove it.

We chose to leave it. Removing it is a ten-line migration and CI now proves
migrations reverse cleanly, so the work is not the obstacle; the objection is
that it is a schema change made days before a demonstration, in the one area
of this project that has already failed once, for a benefit that is entirely
cosmetic. The table costs a row in a limitations table we have written anyway.
It is also, read correctly, more informative than a clean schema would be: it
records where the week-one plan and the delivered system part company, and we
would rather explain that than hide it.

Nothing in the traceability matrix is unmet. Notification was never a numbered
functional requirement, and FR-28 through FR-34, which cover the audit, all
pass. What was lost is a second delivery channel and some convenience. What
was kept is every claim the system makes about a patient's safety.

**9.5 When the tooling was wrong, not the code.** A passing suite licenses one
belief: that the assertions we wrote held, on the setup our harness built.
Both halves of that matter, and three incidents in this project are the same
error seen from different sides.

The first is that CI was green for weeks while the deployment path was broken.
The test suite constructs its schema from the SQLAlchemy models with
`create_all()` and never invokes Alembic at all. So the application was tested
and the thing that installs it never was, and a migration nobody could run
passed every check we had. This is not a coverage gap that more tests of the
same kind would have closed: every test in the suite, including any migration
test we might have written, ran against a schema Alembic had not produced. The
tests were not insufficient. They were exercising a different artifact than a
deployment uses.

Adding a single CI step found a real defect the same day. The initial schema's
`downgrade()` dropped its tables and left all eleven PostgreSQL ENUM types in
place, because Alembic's autogenerate creates enum types and never writes the
code to drop them. After any downgrade, the next upgrade died on `type
"user_role" already exists`. The chain was one-way: a deploy could be rolled
back but never re-applied, and the moment that becomes apparent is the moment
you are already rolling back. A detail worth recording is that Alembic's own
generated stub contained the words "please adjust!" - a tool stating in writing
that it had left work unfinished, in a file we read and committed.

The second incident is a test that failed while being correct. An ordering
assertion on `audit_events` failed, and the comfortable reading was a flaky
test. PostgreSQL's `now()` returns the transaction start time and is identical
for every statement inside that transaction, so two rows written during one
request shared a timestamp and their order could not be recovered afterwards.
Confirmed directly in psql: `now()` returned the same value twice while
`clock_timestamp()` advanced fifty-four milliseconds. The false assumption was
ours, not the test's, and no amount of reasoning about the code would have
surfaced it, because the code did exactly what we believed `now()` meant.

The third points the other way. An audit isolation test failed because a
`rollback()` on the read path discarded the shared transaction the test
fixtures lived in. The production behaviour was defensible and the harness had
manufactured the failure. We still changed the production code, to write
inside a SAVEPOINT via `begin_nested()`, but on production grounds rather than
test grounds: a failed flush otherwise leaves the whole session unusable, and
the route has further queries to run, so the failure would have surfaced in the
next query rather than where it happened. A test artefact had pointed at a real
design question.

Taken together these say that a build result is evidence about what the harness
exercised. Green misleads when the harness differs from production; red
misleads in exactly the same way, and neither direction can be trusted without
knowing what was actually run. The useful question was never whether the build
is green but which artifact it ran against. A related case appears in 9.3:
five auth validation tests sat in the repository for nine days passing nothing,
because no script ran them. A suite can be green partly because some of it does
not execute.

What changed is that CI now runs `alembic upgrade head`, `downgrade base`
and `upgrade head` again on every push, against the `safemed` database,
which nothing else in CI touches - the suite runs against `safemed_test`.
The deployment path is now something the build checks rather than something
we assume.

**9.6 The hardest trade.** The system treats the two paths differently. A
write goes through `record_event`, which flushes the audit row into the
caller's own transaction, so a consent change that cannot be audited does not
happen at all. A read goes through `try_record_event`, which writes inside a
SAVEPOINT and never raises: if the audit write fails, the caregiver is still
shown the finding and the failure is written to the application log. This is
the only place in SafeMed where something happens without a guaranteed audit
row, and it is deliberate.

The case for refusing the read is stronger than it first appears. An audit
log's value is its completeness, and a log with unknown gaps supports a claim -
that we can show who read what - which has become false in ways we cannot
enumerate. Under HIPAA an unauditable disclosure is a violation whatever the
motive, so "we judged the read more important" is not a defence available to a
covered entity. The rule also reads badly stated plainly: if the audit write
fails, proceed anyway. Anyone able to induce audit failures has been handed a
way to turn an availability fault into unlogged access. And the system is now
internally inconsistent, strict on writes and permissive on reads about the
same log, and an exception is where defects tend to live.

The hardest objection is one we have evidence for from our own project. Our
defence is that the failure is loud: `logger.exception` records in plain words
that an unaudited read has happened. But "loud" is a claim about human
behaviour, not a property of the system, and section 9.5 is evidence against
it. Alembic wrote "please adjust!" into a migration we read and committed, and
that warning sat unacted on for weeks until a CI step exposed the defect it
was describing. With three people, no log aggregation, no alerting and nobody
on call, the reader that makes the mitigation work is hypothetical. The log
line is the right thing to write and it is not a control.

The case for serving the read rests on what the read is. It is the safety
function itself. Refusing it means a caregiver is not shown that someone has a
severe interaction because a logging subsystem had a fault, which makes the
patient pay for an infrastructure failure. The audit log exists to protect that
patient, and declining to inform their caregiver in its name inverts the
purpose it was built for.

The attack is also narrower than it sounds, and this is the strongest point in
favour of the choice. Authorization and auditing are separate steps:
`require_active_grant` checks the consent grant whether or not the audit write
succeeds. Breaking the audit writer costs the record of an authorized access;
it does not produce access. The attacker still needs a valid, patient-granted
consent grant, which is what they needed before. The failure degrades
accountability, not confidentiality. A write is not comparable: it alters the
record and leaves no other trace, which is why writes keep the strict rule.

Our choice is to serve the read, keep writes strict, and declare the asymmetry
in the README and the requirements specification rather than let it be
discovered. We think it is correct for what this system is - a student project
on synthetic data, where the cost of a withheld severe interaction during a
demonstration exceeds the cost of a missing log row. We do not think it is
correct in general, and the code says so in the docstring: a system under a
real regulatory obligation would refuse the read.

Two changes would reverse the decision, and naming them is the honest way to
hold it. Centralised logging with alerting would make "loud" a property of the
system rather than an aspiration, at which point serving the read costs
nothing. And a genuine regulatory obligation would make an unauditable
disclosure unacceptable regardless of the clinical cost, which is the position
a hospital is actually in and we are not.

## 10. Limitations and Future Work

### 10.1 Known limitations

| Limitation | Nature |
|---|---|
| No interface for reading the audit log | Records are written and queryable by SQL; no review screen exists. A log nobody can read is a log nobody checks. |
| Schedules stored as wall-clock UTC | No per-user time zones. The interface displays UTC rather than silently showing a wrong local time. |
| Single interaction dataset | Evaluation measures internal consistency, not completeness. |
| `notifications` table unused | The model and enums exist; nothing writes a row. Caregiver alerting is delivered by the dashboard. |
| Append-only enforced in the application only | Direct database access can still alter history. Real tamper-evidence requires cryptographic chaining. |
| Not deployed to a hosted environment | The system runs under Docker Compose; no production deployment was performed. |

### 10.2 Future work, in priority order

1. **An audit review interface.** The highest-value next increment: the data
   exists and is unusable by the people it protects.
2. **A second interaction dataset.** Would allow statements about
   completeness rather than only internal consistency.
3. **Per-user time zones.** Required before the system could be used by
   anyone outside a single zone.
4. **Notification delivery.** Wire the existing model to a transport, with
   delivery status and retry.
5. **Alerting on repeated refusals.** The data to detect a caregiver probing
   for records already exists; nothing watches it.

---

## 11. Conclusion

SafeMed delivers the system it set out to deliver: medication management,
continuous safety and recall monitoring, consent-based caregiver alerting,
role-based access control and an append-only audit trail, with 194 automated
tests and continuous integration.

The project's substantive contribution is not any individual feature but a
position about where machine learning belongs in a safety system. Determining
whether a drug combination is dangerous is a question with a sourced,
checkable answer, and that answer should come from the source. Explaining
that answer to a frightened seventy-two-year-old is a language problem, and
that is where a language model earns its place. Keeping those two jobs
separate is what allows SafeMed to cite every claim it makes.

The strongest evidence that the approach is sound is not that the system
works. It is that the project can state precisely what it gets wrong: 25% of
interactions would have been missed by the obvious implementation, 45% of
recalls cannot be attributed to a specific product, and the evaluation rests
on a panel that was chosen rather than sampled. A system that can describe
its own limits is one a pharmacist could begin to trust.

---

## 12. References

1. **DDInter 2.0** — Xiong, G. et al. *DDInter: an online drug–drug
   interaction database.* Nucleic Acids Research. Open-access curated
   interaction dataset with severity ratings; 160,235 pairs imported.
   https://ddinter.scbdd.com/

2. **RxNorm / RxNav** — U.S. National Library of Medicine. Standard drug
   nomenclature providing RXCUI concept identifiers.
   https://lhncbc.nlm.nih.gov/RxNav/
   *Note: the RxNav Drug Interaction API was discontinued in January 2024,
   which directly shaped this project's architecture.*

3. **openFDA Drug Enforcement Reports** — U.S. Food and Drug Administration.
   Live recall and enforcement data. https://open.fda.gov/apis/drug/enforcement/

4. **FDA medication error statistics** — U.S. Food and Drug Administration.
   Figures on medication-error-related injury are widely cited from an FDA
   medication errors page archived circa 2008–09; the current FDA site
   reports receiving more than 100,000 suspected medication error reports
   annually. The archived page is at
   https://webarchive.library.unt.edu/eot2008/20090117034701/http://www.fda.gov/cder/handbook/mederror.htm

5. **WCAG 2.1** — W3C Web Content Accessibility Guidelines, used for the
   text size, touch target and colour-independence requirements in NFR-08.

### Project documents

| Document | Contents |
|---|---|
| [REQUIREMENTS.md](REQUIREMENTS.md) | Full requirements specification and traceability matrix |
| [DESIGN.md](DESIGN.md) | Architecture and design, six diagrams |
| [EVALUATION.md](EVALUATION.md) | Measured results, method and threats to validity |
| [HANDBOOK.md](HANDBOOK.md) | Ten chapters on why each decision was made |
| [DEMO.md](DEMO.md) | Presentation run sheet |
| [API_CONTRACT.md](API_CONTRACT.md) | Request and response shapes |
| [SETUP.md](SETUP.md) / [WORKFLOW.md](WORKFLOW.md) / [TEAM_GUIDE.md](TEAM_GUIDE.md) | Environment, git workflow, team process |
