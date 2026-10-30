# The SafeMed Handbook

A study companion to the SafeMed capstone project.

**Who this is for:** you, Victory, as you build this. It explains not just *what* we build but *why* each decision was made and what the alternatives were. A software engineer who can explain their choices is more valuable than one who can only type code.

**How it grows:** one chapter per stage of the project. Chapters appear as we build the thing they describe, so nothing here is theory you haven't touched.

**Where it lives:** this file moves into the repository at `docs/HANDBOOK.md` once the repo exists, so it is version-controlled alongside the code it describes.

---

## Chapter 1 — What We Are Building and Why

### 1.1 The one-sentence version

> SafeMed is a web platform that continuously watches a patient's medication list against authoritative drug-safety data, and alerts an authorized caregiver when something needs attention — even when nobody has the app open.

Read that again and notice what it does *not* say. It does not say "an AI healthcare app." The AI is a small part at the end. The value is in the watching.

### 1.2 The problem, stated carefully

Many people — especially older adults and people with chronic conditions — take several prescriptions written by **different** providers and filled at **different** pharmacies. The information about those medications is scattered: one doctor knows about three of them, the pharmacy knows about four, the patient remembers five, and the daughter who drives them to appointments knows about two.

Separately, drug-safety information **changes over time**. The FDA issues recalls. A specific manufacturer's batch gets pulled. Nobody phones the patient to tell them.

Be careful how you state this. **Do not say "nobody is checking."** Pharmacies do run interaction checks, and a professor or judge can challenge that claim immediately. The accurate claim is:

> Medication safety information is fragmented across prescribers, pharmacies, patients, and caregivers, and safety communications change after a prescription is filled. SafeMed prototypes an additional patient- and caregiver-facing safety layer.

That is a claim you can defend. The first one is not.

### 1.3 The core loop

Everything in SafeMed exists to serve one loop. If you remember nothing else, remember this:

```
medication profile
      ↓
authoritative safety data   (RxNorm, interaction dataset, FDA recalls)
      ↓
deterministic evaluation    (fixed rules — not AI)
      ↓
persistent safety finding   (stored with its source and data version)
      ↓
alert routed by severity    (patient only / caregiver immediately)
      ↓
caregiver acknowledgement
      ↓
audit trail
```

Every feature we build either *is* part of that loop or supports it. When you are tempted to add something, ask where it fits in the loop. If it doesn't fit, it's a stretch goal.

### 1.4 The single most important design decision

> **Safety decisions come from authoritative data evaluated by deterministic rules. AI only explains findings in plain language. AI never decides whether something is unsafe.**

This is the heart of the project and the thing you will be asked about. Three reasons it matters:

**1. Correctness.** A language model generates text that is *plausible*. For a drug interaction, plausible is not good enough — a hallucinated interaction could cause real harm, and a hallucinated *absence* of an interaction is worse. A lookup in a real dataset either finds a record or doesn't.

**2. Reproducibility.** Given the same medication list and the same data version, our engine produces the same finding every time. That is testable. A model's opinion is not reliably reproducible, which means you cannot write a passing test for it.

**3. Auditability.** Every finding we store records *which source* it came from and *which version* of that data. A professor — or a pharmacist — can click through and verify it. "The AI said so" is not evidence.

**Deterministic** means: same input → same output, every time, no randomness. Learn that word; you will use it in your presentation.

### 1.5 The "can't Claude just do this?" test

This project survived a test worth internalizing. Ask of any software idea:

> Does the value come from **knowing** something, or from **doing** something?

If the value is explanation or knowledge, a chatbot already does it for free, and you don't have a project. Value survives when it comes from:

| Source of value | Why a chatbot can't | In SafeMed |
|---|---|---|
| Data the model doesn't have | Published after training, or private | RxNorm IDs, FDA recall feed, interaction dataset |
| Exactness required | Plausible-but-wrong is unacceptable | Drug interactions, dosages |
| Persistent state | A chat has no memory of last Tuesday | Medication history, dose events, findings |
| Multiple people, different permissions | No concept of roles or consent | Patient vs. caregiver access |
| **Running while you sleep** | Request-and-response only | The background monitoring worker |

That last row is the strongest. **A chatbot cannot watch something for you.** It is the reason SafeMed is a real system and not a prompt.

### 1.6 What SafeMed must never do

This boundary was approved by your professor and must be preserved:

**SafeMed CAN:** identify and normalize medications · retrieve authoritative safety information · flag supported findings · track adherence · notify authorized caregivers · maintain history and an audit trail · explain verified findings in plain language.

**SafeMed CANNOT:** prescribe · diagnose · change a dosage · tell a patient to start, stop, or alter a medication · declare a medication "safe" for an individual · replace a physician or pharmacist.

When SafeMed finds something, the correct output is always of this shape:

> *Potential interaction detected between A and B. Severity: moderate. Source: [dataset, version]. Please contact your pharmacist or healthcare provider. Do not change or stop a medication based on this system.*

This is not a limitation that makes the project weaker. It makes it **credible**, and credibility is what the grade and the vote reward.

### 1.7 Scope: what is in, what is out

Your professor named the MVP explicitly: *medication management, safety/recall monitoring, caregiver alerts, role-based access, and an audit trail.* Treat that list as a contract.

**Must ship (the core):**
- Login with patient and caregiver roles, plus a consent grant a caregiver needs
- Medication entry, with RxNorm lookup and NDC (manufacturer code) capture
- Interaction checking with severity, every finding citing its source
- Alerts routed by severity, with a caregiver "I've seen this" acknowledgement
- Background worker with tiered recall matching
- Dose tracking (scheduled → due → taken / missed)
- AI plain-language explanation, with tests that block unsafe phrasing
- Medication timeline, audit log, system status panel

**Stretch (only if ahead):** backup-contact escalation · phone push reminders · drug–food interactions · emergency medical QR card.

**Explicitly not building:** prescriptions, billing, lab integration, scheduling, a chatbot, blockchain, microservices.

That last list matters as much as the first. Scope creep is the most common way a capstone fails.

---

## Chapter 2 — The Toolchain, and Why Each Piece

A professional engineer can answer "why did you use that?" for every tool. Here are your answers.

### 2.1 The shape of the system

```
Browser (React + TypeScript)
        │  HTTPS / JSON
        ▼
FastAPI  ──────────────┐
  │                    │
  │ SQLAlchemy         │ Celery task queue
  ▼                    ▼
PostgreSQL  ◄──────  Celery worker + beat  ──►  RxNorm / openFDA
        ▲                    │
        └── Redis (broker) ◄─┘
```

Everything above runs in **Docker containers**, started together by **Docker Compose**.

### 2.2 Python + FastAPI — the backend

**What it is:** FastAPI is a Python web framework for building APIs — the layer that receives HTTP requests from the browser and returns JSON.

**Why we chose it:**
- **Automatic API documentation.** FastAPI generates an interactive docs page at `/docs` from your code. You will demo this. It costs zero extra work and looks professional.
- **Validation built in.** It uses Pydantic, so a request with a missing field is rejected before your code runs, with a clear error. Fewer bugs, less defensive code.
- **Async support**, which matters because we make network calls to RxNorm and openFDA that spend most of their time waiting.
- **Python** is where the data and healthcare ecosystem lives, and it's the language you'll be most productive in.

**The alternative we didn't pick:** Node/Express (fine, but no built-in validation or docs), or Django (excellent but heavyweight — it brings an admin panel and ORM conventions we don't need).

### 2.3 PostgreSQL — the database

**What it is:** a relational database. Data lives in tables with defined columns and enforced relationships.

**Why relational and not a document store:** our data is deeply relational — a patient *has* medications, which *have* dose events and safety findings, which *have* notifications. Enforcing "a visit note cannot exist without a patient" is exactly what a relational database does natively.

**Why PostgreSQL specifically:**
- **Real constraints.** Foreign keys, unique constraints, and transactions mean the *database* refuses invalid data, not just your Python code. Defence in depth.
- **It's what you'd deploy.** Using the same engine in development and production eliminates a whole class of "it worked locally" bugs.
- **JSON columns when you need them** — useful for storing a raw API response alongside structured fields.

**Honest note:** SQLite would have been easier to set up and we considered it. You chose PostgreSQL, which is the better call for a project that must look and behave like production software — and it's the right answer when a judge asks what you'd run in the real world.

### 2.4 SQLAlchemy + Alembic — talking to the database

**SQLAlchemy** is an **ORM** (Object-Relational Mapper). It lets you write Python classes that map to database tables, so you write `patient.medications` instead of hand-writing SQL.

Why it matters: it keeps SQL out of your business logic, prevents SQL-injection by construction, and means the safety engine is written in plain Python you can unit-test without a database.

**Alembic** handles **migrations** — versioned, repeatable changes to the database schema. When you add a column, you generate a migration file and commit it. Your teammates run one command and their database matches yours.

Without migrations, three developers end up with three different database shapes and nothing works on anyone else's machine. This is not optional on a team project.

### 2.5 Docker + Docker Compose — making it run anywhere

**Docker** packages an application together with everything it needs to run — the right Python version, the right libraries, the right system packages — into an image. That image runs identically on your laptop, on Chima's, and on a server.

**Docker Compose** describes *several* containers and how they connect, in one file. For us: the API, the database, Redis, and the worker. One command starts all four.

**Why this matters for your team specifically:** your teammates do not have to install PostgreSQL, Redis, or the right Python version. They run `docker compose up` and have a working system. That removes the single most common reason team projects stall in week 3.

**The cost, stated honestly:** Docker Desktop on Windows 11 Home requires WSL2, which means an install and a reboot before you can start. That is a real cost, paid once.

### 2.6 Redis + Celery — the part that runs while you sleep

This is the heart of your demo, so understand it properly.

**Celery** is a task queue. Instead of doing slow work inside a web request, you hand the job to a queue, and a separate **worker** process picks it up and does it. **Celery Beat** is the scheduler that puts a job on the queue on a timer — "check FDA recalls every hour."

**Redis** is the **broker**: a fast in-memory store that holds the queue of pending jobs, passing them from the API or Beat to the worker.

**Why not just a loop inside FastAPI?** Three reasons: the web server should stay responsive and not be blocked doing a long scan; a failed job can be retried without losing it; and the worker is a separate process you can show running independently, which is what makes "nobody opened the app" demonstrably true rather than a claim.

### 2.7 React + TypeScript + Vite — the frontend

**React** builds the interface as reusable components. **TypeScript** adds types to JavaScript, so a typo in a field name is caught while you type instead of at runtime in front of a judge. **Vite** is the build tool — it starts a dev server instantly and reloads the page as you edit.

**Why types matter here:** the data flowing through this app is safety information with specific shapes. `severity` must be one of three values, not any string. TypeScript enforces that at compile time.

### 2.8 pytest + GitHub Actions — proving it works

**pytest** runs your automated tests. **GitHub Actions** runs those tests automatically on every push, so a broken change is caught before it reaches `main`.

For this project, tests are not just good practice — they are **evidence**. Your evaluation section needs numbers like "the engine correctly identified 100% of benchmark interactions" and "zero AI explanations contained medication-changing advice across 200 cases." Those numbers come from tests.

### 2.9 Git + GitHub + Jira — how three people work without collisions

**Git** tracks every change. **GitHub** hosts the repository and shows who contributed what — which your professor explicitly grades. **Jira** tracks who is doing what and when.

The workflow we'll use, every time:

```
create a branch → write code + tests → push → open a pull request
       → teammate reviews → merge to main → move the Jira ticket to Done
```

Nobody commits directly to `main`. This isn't bureaucracy — it means every change is reviewed, `main` always works, and the git history shows three people genuinely collaborating rather than one person committing everything.

---

## Glossary

| Term | Plain meaning |
|---|---|
| **API** | The set of URLs your frontend calls to get or change data |
| **Endpoint** | One specific URL + method, e.g. `POST /medications` |
| **ORM** | Library that maps database rows to objects in code |
| **Migration** | A versioned, repeatable change to the database structure |
| **Container** | An isolated package of an app plus everything it needs to run |
| **Image** | The blueprint a container is started from |
| **Broker** | The middleman holding queued jobs (Redis, for us) |
| **Worker** | A process that pulls jobs off the queue and runs them |
| **Deterministic** | Same input always produces the same output |
| **RxNorm** | US standard naming system for drugs; gives each a stable ID |
| **NDC** | National Drug Code — identifies the specific product *and manufacturer* on a bottle |
| **RBAC** | Role-Based Access Control — permissions by role, not per person |
| **Idempotent** | Safe to run twice without changing the result (matters for our worker) |
| **Migration vs. seed** | Migration changes structure; seed inserts starting data |

---

*Chapter 3 (the repository layout and the first running service) will be added once the environment is up.*
