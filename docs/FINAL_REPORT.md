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
| Containers | Docker Compose | The whole system starts from a clean checkout with one command |
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

> **Note for the team.** This section must be written in your own words. The
> material below is a set of prompts and the factual record each answer rests
> on — not prose to submit. You should be able to explain every item here
> without reference to notes.

**9.1 The silent failure.** Aspirin and warfarin returned nothing, with no
error. Why is a safety check that quietly finds zero more dangerous than one
that crashes? What did this change about how you test?

**9.2 Choosing data sources under constraint.** The NLM's RxNav interaction
API was retired in January 2024. How did discovering that early change the
architecture, and what would have happened had you discovered it in week ten?

**9.3 Coordinating a team of unequal pace.** Work was duplicated at least
once. What specifically caused it, and what would you do differently from
week one?

**9.4 Deciding what *not* to build.** Notifications, per-user time zones and
an audit review screen were all descoped. How did you decide, and how do you
defend descoping to someone who asks why a table exists with nothing writing
to it?

**9.5 When the tooling was wrong, not the code.** A failing test turned out
to encode a false assumption. A migration passed CI for weeks because CI
never ran migrations. What does this suggest about trusting a green build?

**9.6 The hardest trade.** If the audit write fails, should a caregiver still
be shown a severe interaction? Argue both sides, then state your choice and
why.

---

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
