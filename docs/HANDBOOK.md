# The SafeMed Handbook

A study companion to the SafeMed capstone project.

**Who this is for:** you, Victory, as you build this. It explains not just *what* we build but *why* each decision was made and what the alternatives were. A software engineer who can explain their choices is more valuable than one who can only type code.

**How it grows:** one chapter per stage of the project. Chapters appear as we build the thing they describe, so nothing here is theory you haven't touched.

**Where it lives:** `docs/HANDBOOK.md`, in the repository, version-controlled alongside the code it describes. Chapters 1-10 were written as the system was built; 11-14 cover the documenting, deploying and shipping stages that came after.

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

## Chapter 3 — The First Running System

*Written after the milestone: three containers running, `/health` reporting `database: connected`, and the repository live on GitHub.*

### 3.1 What we actually did

In one sitting we went from an empty folder to a running multi-service application:

1. Installed WSL2, then Docker Desktop (Windows 11 Home requires WSL2 to run Linux containers)
2. Created the repository skeleton
3. Started PostgreSQL, Redis, and a FastAPI application together with one command
4. Confirmed the API could reach the database
5. Put it all under version control and pushed it to GitHub

That ordering is deliberate and worth internalising: **get something running end to end before adding features.** A thin slice that works beats a thick slice that doesn't, because every later problem is then a *change* to a working system rather than a mystery in a system that has never worked.

### 3.2 Why Docker Compose, in concrete terms

Our system needs three processes running at once. Without Docker, each developer would have to install PostgreSQL, install Redis, install the right Python version, create a database, create a user, set a password, and keep all three machines in agreement.

With Compose, that entire setup is **a file in the repository**. Chima and Pacifique run:

```bash
git clone ...
Copy-Item .env.example .env
docker compose up --build
```

and have an identical system. The setup is now *code*, reviewed and versioned like any other code. This is the idea behind "infrastructure as code," and it's the single biggest reason team projects don't stall in week three.

### 3.3 Reading `docker-compose.yml`

```yaml
services:
  db:
    image: postgres:16-alpine
```

**`image`** names a pre-built image from Docker Hub. `16` pins the major version — never use `latest` in a project you'll be graded on, because the image can change under you. **`alpine`** is a minimal Linux base: smaller download, faster startup.

```yaml
    ports:
      - "5433:5432"
```

**Port mapping is `host:container`.** PostgreSQL listens on 5432 *inside* its container. We expose it as **5433** on your machine so that if you ever install PostgreSQL natively, the two don't collide. Redis is mapped 6380→6379 for the same reason.

Important consequence: **inside** the Docker network, services reach each other on their *internal* ports. That's why `DATABASE_URL` says `@db:5432`, not `5433`. The hostname `db` is the service name — Docker runs a DNS server that resolves service names to container addresses.

```yaml
    volumes:
      - safemed_pgdata:/var/lib/postgresql/data
```

A **named volume**: storage managed by Docker that outlives the container. Without it, every `docker compose down` would erase your entire database. The data is not in your project folder, which is why it isn't in git.

```yaml
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
```

A **health check** is a command Docker runs repeatedly to decide whether a service is genuinely ready. PostgreSQL accepts TCP connections seconds before it's ready to serve queries, so "the port is open" is not the same as "the database works."

```yaml
  api:
    depends_on:
      db:
        condition: service_healthy
```

This is why it matters. `depends_on` alone only controls *start order*; it does not wait for readiness. With `condition: service_healthy`, the API container genuinely waits until the health check passes. Without it you get an intermittent crash on startup — the kind of bug that appears on someone else's slower laptop and not on yours.

```yaml
    volumes:
      - ./backend:/app
```

A **bind mount**: your local `backend/` folder appears inside the container at `/app`. Edit a file on Windows and the container sees it immediately, so `--reload` restarts the server. Without this you'd rebuild the image after every edit.

### 3.4 Reading the Dockerfile — why the order of lines matters

```dockerfile
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
```

This looks redundant — why not copy everything once? Because **Docker caches each instruction as a layer**, and a layer is rebuilt only if it or something before it changed.

If we copied all the code first, editing one line in `main.py` would invalidate the cache and reinstall every package — two minutes per rebuild. By copying only `requirements.txt` first, the install layer is reused until the dependency list itself changes. Editing code rebuilds in about two seconds.

This is a standard pattern in every well-written Dockerfile. Knowing *why* is the sort of thing that separates copying examples from understanding them.

```dockerfile
ENV PYTHONUNBUFFERED=1
```

Python normally buffers output. Inside a container that means your print statements and logs may not appear until the buffer fills — so a crashing app appears to say nothing. This flag sends output straight through.

### 3.5 Configuration and secrets

Database passwords are never written in code. They come from **environment variables**, which Compose reads from `.env`.

Two files, deliberately:

| File | Committed? | Purpose |
|---|---|---|
| `.env` | **No** (git-ignored) | Real values for your machine |
| `.env.example` | **Yes** | The list of variables, with safe placeholder values |

`.env.example` is how a teammate knows what to set without you sending them secrets over chat. Right now our `.env` only holds a local development password, but the habit matters: later this file will hold a real API key, and a leaked key in a public repo is a genuine incident.

`app/core/config.py` reads these with **pydantic-settings**, which validates them. If `DATABASE_URL` is missing, the app fails immediately at startup with a clear message, rather than mysteriously failing on the first database query.

### 3.6 The FastAPI application

**Engine vs. session** — the distinction that confuses everyone at first:

- The **engine** is created once for the whole application. It owns a *pool* of database connections, because opening a connection is slow and we want to reuse them.
- A **session** is created per request. It's a unit of work: a scratch space of pending changes that is either committed together or thrown away together.

`get_db()` is a **dependency**. FastAPI calls it before your endpoint, passes the session in, and — because of the `try/finally` — always closes it afterwards, even if your code raised an exception. This pattern is called *dependency injection*: the endpoint declares what it needs and gets it, rather than constructing it itself. It also makes testing easy, because a test can substitute a different database.

**Why `/health` checks the database:**

```python
db.execute(text("SELECT 1"))
```

A health endpoint that only returns `{"status": "ok"}` proves only that Python is running. Ours runs a trivial query, so it proves the API can actually reach PostgreSQL. It reports the two independently, so when something breaks you know *which* thing broke. This same endpoint becomes the system status panel in the final demo.

**`/docs` for free.** FastAPI reads your type hints and generates interactive API documentation automatically. Open it, click an endpoint, press "Try it out," and it calls your live API. We did not write a line of it. It will be part of the demo.

### 3.7 Version control, and what each git command actually does

```powershell
git init          # create the .git folder - this directory is now a repository
git branch -M main   # rename the default branch to 'main'
git add .         # stage: mark files to be included in the next snapshot
git commit -m ""  # snapshot: save the staged files permanently with a message
git remote add origin <url>   # record where the shared copy lives
git push -u origin main       # upload commits; -u remembers the pairing
```

**Staging exists so that a commit is a deliberate, meaningful unit** rather than "whatever happened to be saved." You can commit two files and leave a third half-finished one out.

**An error worth understanding.** We hit this:

```
error: src refspec main does not match any
```

The push ran before any commit existed. A **branch is just a movable pointer to a commit** — with zero commits, `main` doesn't exist yet, so there was nothing to push. Git's error message describes the internals rather than the cause, which is common; learning to translate them is part of the job.

**What `.gitignore` saved us from.** `.env` was excluded automatically. Had it been committed to a public repo, the fix isn't just deleting it — the value stays in the history and must be treated as compromised. Prevention is the only clean option.

### 3.8 Why it's already on GitHub, with one commit

Your professor's guidelines require that *"repository activity should reflect meaningful development progress, contributions from team members, and appropriate documentation."*

A repository with one commit on the day it was created, then thirty on the last night, tells a story nobody wants to read. Committing from day one, in small meaningful units, produces an honest history that shows how the project was built.

From here, the team workflow is:

```
branch → code + tests → push → pull request → review → merge to main
```

Nobody commits to `main` directly. That guarantees `main` always works, every change is seen by another person, and the history shows three people collaborating — not one person committing everything.

### 3.9 Try these yourself

Understanding comes from poking at it:

1. **Break the database on purpose.** In a second terminal: `docker compose stop db`, then reload `/health`. It should still respond, with `database` reporting unavailable rather than crashing. That's deliberate design — a system that reports its own degradation. Restart with `docker compose start db`.
2. **Watch hot reload.** Change the text in the `root()` endpoint in `main.py`, save, and watch the API terminal restart by itself. That's the bind mount plus `--reload`.
3. **Look inside the database.** `docker compose exec db psql -U safemed -d safemed` opens a SQL prompt inside the container. Type `\dt` to list tables — there are none yet. Type `\q` to exit. You'll run this again after the first migration.
4. **See what's running.** `docker compose ps` lists the services and their health.

### 3.10 Where we are

| Piece | Status |
|---|---|
| PostgreSQL 16 | Running, data persists in a named volume |
| Redis 7 | Running, waiting for the worker |
| FastAPI | Running with hot reload |
| `/health` | Confirms database connectivity |
| `/docs` | Auto-generated, interactive |
| Repository | Public on GitHub, `.env` excluded |

**Next:** the data model, and the decision that makes dose tracking possible at all.

---

## Chapter 4 — The Data Model

### 4.1 What a data model actually decides

A data model is usually described as "the tables". That undersells it. The model decides **which questions the system can answer at all**.

The clearest example in SafeMed is dose logging. There are two obvious designs:

| Design | What you store |
|---|---|
| A | A row each time the patient says "I took it" |
| B | A row for every dose the patient is *expected* to take, created in advance, then updated |

Design A is simpler and smaller. It is also incapable of the one thing SafeMed is for. If you only store confirmations, a missed dose is an *absence of data* — and you cannot count, detect, or alert on an absence. "Maria missed her evening warfarin" is not a row that exists; it is a row that doesn't.

Design B turns a missed dose into an observable fact. That is why `dose_events` is generated ahead of time, and why the whole adherence feature is possible.

> **The lesson worth taking:** when you cannot work out how to query something, the problem is usually the model, not the query.

### 4.2 The nine tables

| Table | Holds | The interesting part |
|---|---|---|
| `users` | patients, caregivers, admins | One table, a `role` column — not three tables |
| `consent_grants` | who may see whom | *This table is the authorisation rule* |
| `medications` | what a patient takes | Keeps both what they typed and what we matched |
| `dose_schedules` | "08:00 every day" | The template |
| `dose_events` | "the 08:00 dose on 19 Nov" | The instance, generated from the template |
| `safety_findings` | one concern we detected | Carries its own provenance |
| `finding_medications` | which meds a finding involves | A join table — a finding can involve two |
| `notifications` | what we sent, to whom | Separate from the finding itself |
| `audit_events` | who looked at what | Currently defined but unwritten — see 4.9 |

### 4.3 Why `consent_grants` is the most important table

Most apps answer "may this person see this?" with code — an `if` statement somewhere in a view. SafeMed answers it with a row.

```python
class ConsentGrant(TimestampMixin, Base):
    __tablename__ = "consent_grants"
    __table_args__ = (
        UniqueConstraint("patient_id", "caregiver_id",
                         name="uq_consent_patient_caregiver"),
    )
    status: Mapped[ConsentStatus]     # PENDING | ACTIVE | REVOKED
    granted_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]
```

Three consequences follow, and all three are things a marker will notice:

1. **Revoking is instant.** The grant is looked up on every request, so consent withdrawn at 10:00 takes effect at 10:00 — not whenever a cached token expires.
2. **Revoking does not delete.** The status changes and `revoked_at` is stamped. We never destroy the record of who had access and when. In a health context, that history *is* the accountability.
3. **The unique constraint makes re-inviting safe.** One pair, one row. Invite → revoke → invite again reuses the same row and sets it back to `PENDING`, so the history stays in one place instead of accumulating duplicates.

### 4.4 The template/instance split

```
DoseSchedule          "Metformin, 08:00, daily, 120 minutes grace"
      │
      │ generated for each day
      ▼
DoseEvent             "Metformin, 2026-11-19 08:00Z, status=TAKEN"
```

Separating these is what lets a patient change their schedule without rewriting history. Change the schedule to 09:00 and yesterday's 08:00 dose still says 08:00, because it was recorded as a fact rather than derived from the current template.

It is also why removing a time **deactivates** the schedule rather than deleting it:

```python
schedule.is_active = False
```

Deleting the row would orphan every dose already logged against it.

### 4.5 Keeping what the patient typed

```python
name_entered: Mapped[str]              # "aspirin"
normalized_name: Mapped[str | None]    # "aspirin" (from RxNorm)
rxcui: Mapped[str | None]              # "1191"
```

Three columns for what looks like one piece of information. The reason: `name_entered` is what the patient actually said, and we must never overwrite it. If RxNorm matches the wrong drug, the original is still there to correct from. If RxNorm is down, the medication still saves with `rxcui = NULL` and is checked by name instead.

A nullable column here is not sloppiness. It is an honest record that this particular medication is understood less well than the others — which is why the dashboard shows "Checked by name only" rather than hiding it.

### 4.6 Migrations: why not just `create_all()`

SQLAlchemy can build every table from the models in one call. For a solo project that works. For three developers it does not, because `create_all()` only *creates* — it never alters. Once a table exists, adding a column does nothing to it.

Alembic generates a numbered, reviewable script per change:

```bash
docker compose exec api alembic revision --autogenerate -m "add dose events"
docker compose exec api alembic upgrade head
```

Chima pulls, runs `upgrade head`, and his database matches yours exactly. Without this, "works on my machine" becomes the default state of the project.

> **Autogenerate drafts, it does not decide.** Always read the generated script. It detects added and removed columns well; it cannot tell a rename from a drop-plus-add, and a drop destroys data.

### 4.7 A bug this chapter exists to prevent

The `/doses/today` endpoint returned HTTP 500:

```
'DoseEvent' object has no attribute 'schedule'
```

The model had a `schedule_id` column but no `schedule` **relationship**, so `event.schedule` did not exist.

The genuinely alarming part: **every test passed.** The test fixture had done this:

```python
event.schedule = schedule        # a plain Python attribute
```

Python lets you attach any attribute to an object. The fixture invented a relationship the model did not have, and every test exercised the fixture's fiction rather than the real code.

The fix was one line in the model:

```python
schedule: Mapped["DoseSchedule | None"] = relationship()
```

and a rewritten fixture that goes through the real relationship. The comment left in the test file is worth memorising:

> *A fixture that invents structure the model does not have is testing the fixture, not the code.*

### 4.8 Three details that look small

**UUIDs, not auto-incrementing integers.** Sequential ids leak information — `/medications/41` tells you roughly how many medications exist in the system, and `/medications/42` is a reasonable guess at someone else's. UUIDs are also generated without asking the database, which matters for the background worker.

**Timestamps are always timezone-aware UTC.** Mixing naive and aware datetimes is one of the most common sources of off-by-hours bugs. There is one helper and everything goes through it.

**Every repository function takes `patient_id`.**

```python
def get(db, *, patient_id: UUID, medication_id: UUID) -> Medication | None:
```

Not a convention — a *required argument*. You cannot write a query that accidentally returns another patient's data, because the owner is something you must pass rather than something you must remember.

### 4.9 What is still missing

`audit_events` is defined and unused. Nothing writes to it. In a system where a caregiver can read someone else's medication record, the log of who looked at what is not optional — and it is the clearest remaining gap in the model.

### 4.10 Try these yourself

1. **Look at the tables.** `docker compose exec db psql -U safemed -d safemed`, then `\dt`, then `\d consent_grants`. Find the unique constraint.
2. **Prove the template/instance split.** Find a `dose_schedules` row, then `SELECT * FROM dose_events WHERE schedule_id = '...';` — one template, many instances.
3. **Try to break ownership.** Log in as one patient, note a medication id, log in as another, and `GET /medications/{that id}`. You get 404, not 403. Ask yourself why 404 is the safer answer.

---

## Chapter 5 — Making Drug Names Comparable, and the Safety Engine

### 5.1 The bug that explains this chapter

Warfarin and aspirin together is a textbook Major interaction — it is in every pharmacology course. We put both in the database, ran the engine, and got **zero findings**.

Nothing was broken. The interaction dataset calls aspirin **"Acetylsalicylic acid"**. The patient typed "aspirin". String comparison said: different drugs.

This is the entire problem of drug data in one example. The same substance has a brand name, a generic name, a chemical name, and a dozen spellings. Matching on text will fail, and — this is the dangerous part — **it fails silently**. No error, no warning, just a safety check that quietly finds nothing.

### 5.2 RxNorm: an id instead of a name

RxNorm is the US National Library of Medicine's drug vocabulary. Its job is to give every drug concept one stable identifier, the **RXCUI**.

```
"aspirin"               ─┐
"Acetylsalicylic acid"  ─┼──► RXCUI 1191
"ASA"                   ─┘

"paracetamol"    ─┐
"acetaminophen"  ─┴──────► RXCUI 161
```

Once both sides carry 1191, the comparison is `1191 == 1191`. Names stop mattering.

### 5.3 Normalisation must never block saving

```python
medication = repo.create(db, patient_id=..., **fields)   # saved FIRST

result = normalize_medication_name(medication.name_entered)
if result.found:
    repo.update(db, medication=medication,
                rxcui=result.rxcui, normalized_name=result.normalized_name)
```

The order is deliberate. RxNorm is an external service over the internet. It can be slow, down, or return nonsense. **None of that is a reason to stop a patient recording a medication they are actually taking.**

So `RxNormClient.normalize()` has an unusual rule: every failure returns "no match" rather than raising. A timeout, a 500, malformed JSON — all collapse to the same harmless outcome. The medication saves with `rxcui = NULL` and gets checked by name, which is weaker but far better than nothing.

> Deciding *what a failure should degrade into* is a design decision, not an error-handling afterthought.

### 5.4 Resolving the dataset, once

Normalising the patient's side is only half of it. The dataset needed RXCUIs too, so we wrote `scripts/resolve_rxcuis.py` and ran it once:

| | |
|---|---|
| Distinct drug names in DDInter | 1,914 |
| Resolved to an RXCUI | **1,904 (99.5%)** |
| Interaction rows with both RXCUIs | 159,906 of 160,235 |

The 10 unresolved names still match by text, so nothing is lost — the fallback stays. And matching happens both ways:

```python
for rxcui, drug_key in ((hit.drug_a_rxcui, hit.drug_a_key),
                        (hit.drug_b_rxcui, hit.drug_b_key)):
    med = (index.get(rxcui) if rxcui else None) or index.get(drug_key)
```

**ID first, name as fallback.** Without the fallback, the ten unresolved drugs would silently stop being checked.

### 5.5 Pluggable sources, and why the professor was right

Your professor's warning was that an unavailable data source should not block the project. He was right in a way we only discovered later — the NLM's own Drug Interaction API was **retired in January 2024**, which is exactly the kind of thing that sinks a capstone in week nine.

So the engine does not depend on DDInter. It depends on a shape:

```python
class InteractionSource(Protocol):
    name: str
    version: str
    def find_interactions(self, drug_keys, rxcuis=None) -> list[InteractionHit]: ...
```

Any object with that shape works. The proof is in the tests, which pass a five-line fake:

```python
class FakeInteractionSource:
    name, version = "FakeSource", "test-1"
    def find_interactions(self, drug_keys, rxcuis=None):
        return self._hits
```

That fake does two jobs at once: it makes the tests fast and independent of whether anyone has run the import, and it demonstrates that swapping the data source is genuinely a drop-in change.

### 5.6 Stating uncertainty instead of hiding it

DDInter rates interactions Major, Moderate, Minor — and sometimes Unknown. The tempting move is to map Unknown to Minor and move on. We map it to MILD *and record that the severity is not established*:

```python
assert "not established" in finding.detail.lower()
assert finding.evidence["severity_established"] is False
```

The patient reads "The severity of this interaction is not established in the source data" rather than being quietly told it is minor. Presenting an unknown as a known is a way of being wrong that is very hard to detect later.

### 5.7 Provenance: a finding that cannot be audited is just an assertion

Every finding carries where it came from:

```python
finding.source_name      # "DDInter"
finding.source_version   # "2.0"
finding.evidence         # the raw record we based this on
```

When a pharmacist asks "where does this claim come from?", the answer is in the row. This is also what makes the AI layer safe to add later — the deterministic claim and its source exist *before* any model touches it.

### 5.8 Deduplication: the feature that stops the alerts being useless

The worker re-evaluates every patient on a timer. Without dedupe, the same aspirin/warfarin interaction would be reported every hour, for ever.

```python
def make_dedupe_key(patient_id, kind, *parts) -> str:
    # SHA-256 of WHO and WHAT. Never WHEN.
```

Excluding time is the whole trick. A key built from "this patient + interaction + aspirin + warfarin" is identical on every run, so the second run finds the existing finding and creates nothing:

```python
first  = SafetyEngine(db, source).evaluate_patient(patient.id)
second = SafetyEngine(db, source).evaluate_patient(patient.id)

assert len(first.created) == 1
assert len(second.created) == 0
assert len(second.existing) == 1
```

Include a timestamp and every run produces a "new" concern, the patient is buried, and the entire safety feature becomes noise.

### 5.9 Try these yourself

1. **Reproduce the original bug.** `SELECT drug_a_key, drug_b_key FROM drug_interactions WHERE drug_a_key ILIKE '%acetylsalicylic%' LIMIT 5;` — the dataset's name for aspirin, in the raw.
2. **Watch dedupe work.** On the dashboard press **Check again** twice. The findings do not multiply.
3. **Break normalisation on purpose.** Add a medication called `zzzqqq`. It saves, and shows "Checked by name only".

---

## Chapter 6 — Recalls, False Alarms, and the Worker

### 6.1 The number that shaped the design

FDA recall notices do not reliably identify the product. We sampled 100 recent drug enforcement reports:

| | |
|---|---|
| Carry an NDC (identifies the exact product *and* manufacturer) | 61 |
| Carry no NDC at all | 39 |

So for roughly four recalls in ten, the honest answer to "does this affect my patient?" is **we cannot tell**.

You have three options. Two of them are bad:

- **Alert on every name match.** Metformin is recalled; every metformin patient is told they are affected. Most are not — different manufacturer entirely. After the second false alarm, people stop reading.
- **Alert only on exact matches.** No false alarms, and you silently miss 39% of recalls.
- **Say which one you have.** This is what SafeMed does.

### 6.2 Tiered matching

| Tier | When | What the patient reads |
|---|---|---|
| `CONFIRMED` | The recall's NDC matches the patient's NDC | "This recall **affects your** Metformin" |
| `POSSIBLE` | Same drug, manufacturer unknown | "This recall **may affect your** Metformin — check the label" |
| no match | Different drug | nothing |

Severity routing falls out of the tier:

```python
CONFIRMED + Class I  -> SEVERE
CONFIRMED + other    -> MODERATE
POSSIBLE  + Class I  -> MODERATE
POSSIBLE  + other    -> MILD
```

A `POSSIBLE` match is never escalated to a caregiver as though it were certain. The difference between "affects" and "may affect — check the label" is the difference between a system people trust and one they mute.

### 6.3 Refusing to guess

NDC codes come in several formats, and some are genuinely ambiguous about where the product code ends. The first version of `ndc_product_code()` guessed. A test failed, and the right fix was not a cleverer guess:

```python
def test_ambiguous_ndc_is_refused_rather_than_guessed(): ...
```

The function now returns `None` for ambiguous input, which downgrades the match from CONFIRMED to POSSIBLE. **A guess here would mean telling someone a recall definitely affects their medication when we do not know that.** Degrading to "check the label" is the correct failure.

Note the test name. It states the behaviour and its justification, so nobody later "fixes" the refusal back into a guess.

### 6.4 The worker, and why scheduled work needs a different design

Checking the FDA for recalls cannot happen inside a web request — nobody is on the page at 3 a.m. That needs **Celery** (runs jobs) and **Redis** (holds the queue).

```python
beat_schedule = {
    "check-recalls":          {"task": "check_recalls",         "schedule": 3600},
    "explain-findings":       {"task": "explain_findings",      "schedule": 600},
    "refresh-dose-statuses":  {"task": "refresh_dose_statuses", "schedule": 900},
}
```

Three processes, one codebase: `api` serves requests, `worker` runs jobs, `beat` puts jobs on the queue on a timer.

**Everything a worker does must be idempotent** — safe to run twice. A worker can be killed mid-job and the job redelivered, so "ran twice" is a normal operating condition, not an edge case. Two mechanisms do the work:

```python
task_acks_late = True        # acknowledge after completing, not on receipt
```

and the dedupe key from 5.8, backed by a unique constraint in the database. The constraint is what makes it true — a comment saying "this should not happen twice" is a wish; a unique index is a guarantee.

### 6.5 A real bug: counting rows that were not inserted

The DDInter import reported:

```
Inserted -81 new rows
```

Negative rows. The cause: PostgreSQL returns `-1` from `cursor.rowcount` for batched `INSERT ... ON CONFLICT DO NOTHING`, and we were summing those. The fix was to stop asking the driver and count the table before and after.

Small, silly, and worth keeping in mind: **a number that is obviously impossible is a gift.** It is a bug that cannot hide. The dangerous version of this bug would have reported a plausible wrong number.

### 6.6 Severity routing, stated once

This is the rule the whole project turns on:

> Our demo data produces **ten findings from five ordinary medications.** Only the SEVERE ones reach a caregiver.

Ten findings is not a bug in the data. Five common drugs really do have that many documented interactions, most of them minor. A caregiver sent all ten would be reading mostly noise, and within a week would stop reading any of them — including the one that mattered.

So the caregiver endpoint filters to SEVERE **in the endpoint, not the interface**:

```python
.where(SafetyFinding.severity == Severity.SEVERE)
```

Put the filter in the UI and a second client, or a direct API call, hands someone all ten and reintroduces exactly the problem. Where a rule lives determines whether it is actually a rule.

### 6.7 Try these yourself

1. **Trigger a recall check by hand:**
   ```bash
   docker compose exec api python -c "from app.workers.tasks import simulate_recall; print(simulate_recall.delay('metformin').get(timeout=120))"
   ```
   Watch `docker compose logs -f worker` while it runs. The demo patient's Metformin carries Cardinal Health's NDC `0310-6225-30`, which matches real FDA recall D-0435-2021 — so you should see one CONFIRMED alongside several POSSIBLE.
2. **Look at the queue.** `docker compose exec redis redis-cli LLEN celery` before and immediately after dispatching.
3. **Run it twice.** The findings do not duplicate. That is 5.8 doing its job.

---

## Chapter 7 — The AI Layer, and the Line It Must Not Cross

### 7.1 The question this project has to answer

Early on you asked the right question about a different project idea: *"can't anyone just upload it to Claude and get the same answer?"* If yes, it is a prompt, not a system.

SafeMed has to survive that question, and it does — but only because of where the AI sits.

### 7.2 What AI is not allowed to do here

**The model never decides whether something is dangerous.**

That decision is made by the deterministic engine, from DDInter and FDA data, before any model is involved. By the time the AI layer runs, the finding already exists, is already severity-rated, already carries its source, and is already displayable.

```
DDInter / openFDA  ──►  deterministic engine  ──►  finding (complete)
                                                        │
                                                        ▼
                                                  AI rewrites it
                                                  in plain language
```

The AI's only job is translation: turning *"DDInter records a potential interaction between Acetylsalicylic acid and Warfarin, rated Major"* into something a 72-year-old can act on.

This matters for a reason beyond safety. An LLM asked "is this combination dangerous?" will answer confidently every time, including when it is wrong, and you cannot tell the difference from the output. Asking it to rephrase a claim that already has a citation is a job it is genuinely good at.

### 7.3 The three protections

**1. The model never judges.** Severity comes from the dataset. The prompt asks for a rewrite, not an assessment.

**2. No patient data is sent.** The model receives drug names and the source's description. Not the name, age, email, id, or medication list of any person. The privacy guarantee is structural — there is no payload to leak, so a logged prompt cannot expose a patient.

**3. Every response is validated before it is stored.**

```python
FORBIDDEN_PATTERNS = [...]   # 11 regexes
REQUIRED_PATTERN   = ...     # must refer the reader to a professional
```

The forbidden patterns catch the model telling someone to stop, change, or adjust a medication. The required pattern ensures it points them at a pharmacist or doctor. A response failing either check is **discarded, not shown**:

```python
ExplanationResult(text, status)   # ok | rejected | unavailable | disabled
```

### 7.4 Why `ai_explanation` is nullable, and why that is the important part

```python
ai_explanation: str | None
```

Four ways it ends up null: the AI is disabled, the API is unreachable, the response failed the guardrails, or the job has not run yet.

In every one of those cases **the finding still stands and still displays**, because `detail` was written by the deterministic engine and never depended on the model. The frontend enforces this too — `detail` always renders; `ai_explanation` is shown as an addition, visually separated, under the heading "In plain language".

The test states the rule directly:

```python
def test_ai_explanation_is_empty_until_the_ai_layer_runs(db, patient):
    assert finding.ai_explanation is None
    assert finding.detail                       # stands on its own
    assert "pharmacist" in finding.detail.lower()
```

> **The design principle, in one line:** the AI makes SafeMed easier to understand. It is never what makes SafeMed correct.

This is also the answer to "why not just use Claude?" — not because a model could not describe an interaction, but because a system that is *accountable* needs the claim and its citation to exist independently of the model.

### 7.5 Try these yourself

1. **Turn the AI off.** Comment out `ANTHROPIC_API_KEY` in `.env`, `docker compose restart api worker`, and reload the dashboard. Every finding still reads correctly — only the "In plain language" block disappears.
2. **Read the guardrails.** Open `backend/app/services/ai_explainer.py` and look at `FORBIDDEN_PATTERNS`. For each one, ask what harm it prevents.

---

## Chapter 8 — The Frontend, Auth, and Consent

### 8.1 What a frontend is actually responsible for

It is tempting to think the frontend just displays what the API sends. On a safety screen it has two further duties, and both are design decisions rather than styling:

1. **Not implying things the data does not say.** An empty screen reads as "nothing is wrong". If a request failed, the screen must say so, because silence is a claim.
2. **Not making everything equally loud.** Ten warnings of equal weight is the same as no warnings.

### 8.2 Where the token lives, and where the user does not

```ts
const [loading, setLoading] = useState(() => readToken() !== null);
```

The **token** is stored in `localStorage`, so a refresh does not sign you out. The **user** is never stored — it is fetched from `/auth/me` on load.

That asymmetry is the point. A stored user object would let a stale or tampered copy decide what the interface shows. Asking the server means the server decides, every time. If the token is rejected, we drop it and show the login form, rather than leaving the app in a half-signed-in state where it believes it is authenticated and every request fails.

Every `localStorage` access is wrapped in `try/catch`, because it *throws* rather than returning null in some private-browsing modes.

### 8.3 Routing guards are convenience, not security

```tsx
if (wantsPatient) return user && user.role !== "CAREGIVER" ? <Dashboard /> : null;
```

Worth being honest about: this stops someone seeing a screen that would be blank for them. It is not what protects the data. **The server decides what anyone may read** — caregiver endpoints refuse anyone without an active grant, regardless of what the browser believes.

Note `role !== "CAREGIVER"` rather than `role === "PATIENT"`. `ADMIN` is a third role in the enum; an equality check would route an admin to a page that then refuses to render, stranding them on a blank screen with no way out. Enums grow, and exhaustive checks age badly.

### 8.4 Severity in the interface

The patient's findings list is deliberately not a list:

- **SEVERE** — expanded, full text, `role="alert"` so a screen reader announces it immediately
- **MODERATE / MILD** — collapsed under "Also worth knowing (7)", with a note saying they are not urgent and are not sent to a caregiver
- **Acknowledged** — folded into a `<details>` element

Three findings demand attention; seven are available without shouting. `role="alert"` is used **only** on severe items — if everything interrupts, nothing does.

### 8.5 Accessibility, because of who uses this

The people most affected by medication interactions are often older, and the project's accessibility decisions follow from that rather than from a checklist:

| Decision | Why |
|---|---|
| 18px base text | Not 14px. This is read by people who find small text hard |
| 44px touch targets | The "I took it" button is tapped daily, possibly with unsteady hands |
| Colour is never the only signal | Roughly 1 in 12 men has a colour vision deficiency; a red box and an amber box can look identical. Every badge states its status in words, and alerts carry an icon |
| `aria-label` on dose buttons | "I took it" alone is meaningless out of context. The label reads "Record that you took Metformin at 8:00 AM" |
| Status words, not jargon | "Later today", "Due now", "Missed" |

### 8.6 Two bugs the browser found

**Rows jumped after every tap.** Four medications at 08:00 share one `scheduled_for` value, and the query ordered by that column alone — so ties came back in whatever order the database felt like. Confirming a dose reshuffled the list and the row you just tapped moved.

Fixed in the query, not the component:

```python
.order_by(DoseEvent.scheduled_for.asc(), Medication.name_entered.asc())
```

Fixing it in the frontend would have left the next consumer of that endpoint with the same bug.

**One patient's data under another's name.** Switching patients in the caregiver view kept the previous patient's findings on screen while the new request was in flight. The fix is one React idiom:

```tsx
<PatientDetail key={selected.id} patient={selected} />
```

Changing `key` destroys the component and builds a new one, so state cannot survive the switch. On a screen about someone's medication, attributing one person's data to another is the worst thing it could do.

### 8.7 Consent, from both sides

**The patient** invites by email, sees everyone who has access, and revokes in one click — no confirmation dialog asking them to justify it. *Withdrawing consent should never be harder than giving it.* Revoked caregivers stay in the list, greyed out, because the record of who had access and until when is part of what makes consent meaningful to the person who gave it.

**The caregiver** accepts or declines, then sees serious alerts, adherence, and today's doses — read-only. They cannot log a dose on someone else's behalf.

And the screen says what it is not showing:

> "You are shown serious findings only. Maria sees the full list, including minor ones, on their own account."

Without that sentence a caregiver reads a short list as reassurance. It is deliberately not styled as fine print.

### 8.8 Why there is no router library

The route table is about forty lines and has no dependency:

```ts
export function navigate(to: string): void {
  if (to === currentPath()) return;
  window.history.pushState({}, "", to);
  window.dispatchEvent(new Event(PATH_CHANGE));
}
```

`pushState` deliberately does not fire `popstate` — that event is for the back button — so `navigate()` dispatches its own. Every path change, whether from a link or the back button, then flows through one code path.

`Link` stays a real `<a>` with a real `href` and intercepts only a plain left-click, so middle-click, ctrl-click and "open in new tab" keep working and screen readers still announce it as a link.

A dependency is a thing you must understand, update, and justify. For four routes, forty lines you wrote is cheaper than a library you did not.

### 8.9 Try these yourself

1. **Prove the guard is cosmetic.** Sign in as Elena (caregiver) and manually visit `/dashboard`. You are redirected. Now in the browser console: `await fetch('http://localhost:8000/api/v1/findings', {headers:{Authorization:'Bearer '+localStorage.getItem('safemed.token')}}).then(r=>r.json())` — you get *your own* (empty) findings, not Maria's. The server, not the router, is what protects the data.
2. **See severity routing with your own eyes.** Sign in as `maria@safemed.demo` and count the findings. Sign in as `elena@safemed.demo` and count them again. 10 versus 3.
3. **Revoke and watch it bite.** As Maria, remove Elena's access. Reload Elena's screen — Maria is gone immediately, no waiting for a token to expire.
4. **Shrink the window** to phone width. The dose rows stack and the buttons stay full size.

---

## Chapter 9 — Testing, Continuous Integration, and Evaluation

### 9.1 Two different questions

These sound like the same activity and are not:

| | Question it answers |
|---|---|
| **Testing** | Does the code do what we said it does? |
| **Evaluation** | Was what we said worth doing? |

A project can pass every test and still be pointless. SafeMed's tests prove the safety engine finds the interactions it is given; the *evaluation* is what shows that matching by identifier instead of by name finds a quarter more of them. Only one of those answers "why did you build it this way", which is the question you will actually be asked.

So the project does both, and keeps them in separate places: `backend/tests/` and `docs/EVALUATION.md`.

### 9.2 Why the tests use a real PostgreSQL

The easy route is SQLite in memory: no services, instant startup. It was rejected, because the application depends on behaviour SQLite does not share — server-side defaults, real foreign-key enforcement, `ON CONFLICT` semantics, actual type checking.

A test suite running against a different database than production is testing something you do not ship. The bugs it misses are exactly the ones you care about: the ones that only appear under real constraints.

So `conftest.py` creates a separate database next to the development one:

```python
TEST_DATABASE_URL = settings.DATABASE_URL.rsplit("/", 1)[0] + "/safemed_test"
```

Derived from the real URL rather than hardcoded, which is why the same `conftest.py` works unchanged on your laptop, in Docker, and in CI — each supplies its own `DATABASE_URL` and the test database follows.

### 9.3 Two fixture decisions worth understanding

**Every test runs in a transaction that is rolled back.**

```python
connection = engine.connect()
transaction = connection.begin()
session = sessionmaker(bind=connection)()
try:
    yield session
finally:
    session.close()
    transaction.rollback()
    connection.close()
```

Nothing a test writes survives it. That gives two properties that matter more than speed: tests cannot see each other's data, so they pass in any order; and the suite is safe to run a hundred times, because it never leaves anything behind. A suite you are reluctant to run is a suite you stop running.

**The schema is dropped before it is created.**

```python
Base.metadata.drop_all(eng)
Base.metadata.create_all(eng)
```

`create_all()` creates missing tables. It does **not** alter existing ones. Without the `drop_all`, the day you add a column every test fails with `column does not exist` — and the cause looks like your new code rather than a stale test database. That is an hour lost to a problem that is not real. Two lines prevents it permanently.

### 9.4 Testing through real HTTP, with real tokens

The consent and RBAC tests do not call the permission functions directly. They start the app, register real users, log in to get real JWTs, and make real requests:

```python
response = client.get(
    f"/api/v1/caregiver/patients/{patient_id}/findings",
    headers={"Authorization": f"Bearer {caregiver_token}"},
)
assert response.status_code == 403
```

This matters for an access-control test specifically. A unit test of `require_active_grant` proves the function returns what you expect when you call it. It proves nothing about whether the route *uses* it — and a route that forgets its dependency is precisely how authorization gets bypassed in real systems. Going through HTTP tests the wiring, which is where the hole would be.

> **The rule:** test security at the boundary an attacker would actually reach.

One related decision, visible in those tests: an unknown patient id and a patient you have no grant for both return **403**, never 404. A 404 would confirm the id does not exist, and a 403 that is only ever returned for *real* patients lets an attacker enumerate who exists by reading the status code. Identical responses leak nothing.

### 9.5 When the test is wrong

While adding dose history, this test was written:

```python
def test_history_does_not_invent_doses_for_past_days(...)
```

It failed. The first instinct is to go fix the code.

The code was right. The assumption was wrong — a dose *schedule* is a standing instruction ("08:00 daily"), and a dose *event* is a row that exists only once something generated it. Asking for history of a day before any rows were generated correctly returns nothing, not because of a bug but because nothing happened that day.

The test was rewritten to state the real behaviour. Nothing in the application changed.

> **A failing test is a disagreement between two things you wrote.** Before changing the code, work out which of the two is wrong. Roughly a quarter of the time it is the test — and a test "fixed" by bending the code around a false assumption leaves you worse off than having no test at all.

### 9.6 Regression tests, and where to put the fix

The browser found a real bug: tapping **I took it** reshuffled the dose list. Four medications at 08:00 share one `scheduled_for` value, and the query ordered by that column alone, so tied rows came back in whatever order PostgreSQL chose — a different order each time.

The fix was one line, in the repository:

```python
.order_by(DoseEvent.scheduled_for.asc(), Medication.name_entered.asc())
```

It could have been fixed in the React component by sorting the array after fetching. That would have worked, and it would have been wrong: `/doses/history`, `/caregiver/patients/{id}/doses/today` and every future consumer of that query would still have the bug, each waiting to be fixed separately.

> **Fix a bug at the layer where the mistake was made,** not at the layer where you noticed it.

Then a test was added that fails if anyone removes the secondary sort — because the bug is invisible in any dataset where no two doses share a time, which includes most test fixtures someone might write later.

### 9.7 Continuous integration, and the tests nobody ran

`.github/workflows/ci.yml` runs on every push and every pull request: the backend suite against a real PostgreSQL service container, and the frontend typecheck, lint and unit tests. Two jobs, in parallel, deliberately — a frontend type error must not hide a backend test failure, or the reverse.

Three details that are decisions rather than boilerplate:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

A second push to the same branch cancels the first run. Only the newest commit's result is interesting, and runner minutes are finite.

```yaml
run: npm ci
```

`npm ci` installs exactly what the lock file says and fails if the lock file and `package.json` disagree. `npm install` would quietly resolve something newer, which means CI could pass against dependencies nobody has committed — and then fail on a teammate's machine.

```yaml
options: >-
  --health-cmd pg_isready
```

Without the health check, the test step can start before PostgreSQL accepts connections, and the job fails for no real reason. A flaky CI is worse than no CI: people learn to ignore a red build.

**And the reason this chapter exists at all.** `frontend/tests/auth-validation.test.mjs` was committed on 10 November, contains five passing tests, and had never been executed by anything — there was no `test` script in `package.json`. Five tests of real value, invisible for nine days.

> **A test that is not in CI is not a test.** It is a file that happens to contain assertions. Until something runs it automatically, nobody finds out when it breaks.

### 9.8 What evaluation adds

The project makes three expensive design claims. Each cost real complexity, so each was measured rather than asserted. `backend/scripts/evaluate.py` runs five experiments and writes `docs/EVALUATION.md`:

| Claim | Measured |
|---|---|
| Identifier matching beats name matching | Name matching alone finds 63 of 84 real interactions — **missing 25%, two of them SEVERE** |
| Recalls need tiered confidence | **45 of 100** sampled FDA recalls carry no product identifier at all |
| Severity routing protects caregivers | **70%** fewer findings reach a caregiver than the patient sees |
| The worker is idempotent | **0** duplicates across three full re-runs |

That first number is the aspirin/warfarin bug expressed as a measurement. The bug was one missed interaction; the evaluation says how many others were waiting.

The report ends with threats to validity, and that section is not modesty — it is the difference between a measurement and a marketing claim:

- The fifteen-medication panel was **chosen, not sampled.** It is realistic, not representative.
- **One interaction dataset.** This measures internal consistency, never completeness.
- **No clinical validation.** No pharmacist has reviewed the output.

State the limits yourself. A marker who finds a limitation you did not mention stops believing the numbers you did.

### 9.9 Try these yourself

1. **Watch the rollback work.** Add a test that creates a user and asserts it exists. Run the suite twice. It passes both times — if the fixture leaked, the second run would fail on a duplicate email.
2. **Cause the stale-schema failure on purpose.** Comment out `Base.metadata.drop_all(eng)`, add a column to any model, and run the suite. Read the error and notice how little it points at the real cause. Then put the line back.
3. **Break the secondary sort.** Delete `Medication.name_entered.asc()` from the ordering and run `pytest backend/tests/test_dose_repository.py`. One test fails and names the problem.
4. **Run what CI runs**, before pushing rather than after:
   ```bash
   docker compose exec api pytest
   cd frontend && npx tsc -b && npm run lint && npm test
   ```
5. **Re-run the evaluation.** `docker compose exec api python -m scripts.evaluate` and diff `docs/EVALUATION.md`. The numbers should not move. If they do, something changed that you did not intend to change.

---

## Chapter 10 — The Audit Log, and Who Gets to Be Trusted

### 10.1 Why this is not optional

Everything else in SafeMed answers "what should this person see?". The audit log answers a different question: **"what did they actually see?"**

Consent without a record of what it permitted is a promise, not a control. If Maria revokes Elena's access, she is entitled to know what Elena looked at while she had it. No amount of correct permission-checking provides that. Only a log does.

This was the last item in the instructor's named MVP, and it is the one a marker is most likely to probe, because it is the part students usually skip.

### 10.2 One rule that shapes the whole design

```python
db.add(audit_event)
db.flush()   # NOT commit
```

`record_event` writes the row into **the caller's transaction** and never commits. The caller's own commit saves the action and its audit row together.

Follow that through:

- The action succeeds → both are saved.
- The action fails and rolls back → the audit row rolls back with it.

So there is never an audit entry for something that did not happen, and never a change with no entry. If `record_event` committed on its own, a medication update that failed afterwards would leave a log claiming it succeeded — a log that lies is worse than no log, because people act on it.

### 10.3 Append-only, enforced rather than promised

```python
@event.listens_for(AuditEvent, "before_update")
def _refuse_update(mapper, connection, target) -> None:
    raise AuditLogImmutableError("Audit events are append-only and cannot be changed")
```

The original model said *"append-only by convention: nothing in the application ever updates or deletes a row here."*

A convention is a comment. It holds until someone who has not read the comment writes `grant.audit_event.details = {...}` eighteen months later. These two listeners make the ORM refuse, and there are tests that prove it refuses.

> **If a rule matters, make the machine enforce it.** A rule that lives only in a docstring is a rule you are hoping about.

Note what this does *not* do: it stops the application changing a row. Someone with direct database access can still edit the table. Real append-only storage is a different and much larger problem. Say that plainly if you are asked, rather than overclaiming.

### 10.4 A refusal is the interesting part

The first version logged successful reads only, and documented the choice: *"A refused request is not recorded as a view: nothing was seen."*

That is correct about the word "view", and wrong about what an audit log is for. Consider what each version can answer:

| Question | Successes only | Both |
|---|---|---|
| What did Elena read? | yes | yes |
| Did anyone try to read records they had no grant for? | **no** | yes |
| Did a caregiver keep trying after being revoked? | **no** | yes |

The second and third questions are the security-relevant ones, and they are invisible if only successes are written. The fix keeps both truths — a refusal is recorded, under its own action:

```python
PATIENT_RECORD_ACCESS_DENIED = "patient_record.access_denied"
```

One subtlety worth understanding, because it ties back to Chapter 8. On a refusal, `entity_id` holds the id that was *asked for*, but `patient_id` is left **null**:

```python
entity_id=patient_id,   # what they asked for - may not exist
patient_id=None,        # we must not imply it does
```

The endpoint deliberately returns the same 403 whether the patient exists or not, so the response cannot be used to enumerate who exists. Filling in `patient_id` would make the audit log answer the exact question the 403 was designed to refuse. A privacy property you protect in one place and leak in another is not protected.

### 10.5 The one place the system tolerates an unaudited action

A probe during review turned a working caregiver request into a 500 simply by making the audit writer raise. That is a real failure mode: a broken log takes the dashboard down with it.

Which raises a genuine design question, and it is not a technical one:

> If you cannot record that someone read a record, should you let them read it?

A hospital answers **no**. No audit, no access — the obligation to account for access outranks the access itself.

SafeMed answers **yes**, for reads only, and says so out loud:

```python
def try_record_event(db: Session, **kwargs) -> AuditEvent | None:
    """Record an event and commit it, but never raise. Use on a read path."""
```

The reasoning: refusing to show a caregiver that their mother has a severe interaction, because a logging table was unavailable, is the worse of the two harms. Writes keep the strict behaviour — a consent change that cannot be audited does not happen.

Be ready to defend this one. The answer is not "it was easier"; it is that the two failure modes have different costs, and the trade is written down rather than discovered.

**The savepoint detail matters too:**

```python
with db.begin_nested():   # SAVEPOINT
    audit_event = record_event(db, **kwargs)
```

A failed flush leaves the entire session unusable, and the route still has its own queries to run. Without the savepoint, a broken audit write surfaces as a confusing error in the *next* query rather than where it actually happened. The savepoint confines the damage to the audit insert.

### 10.6 `now()` is not the time

This one is worth remembering well beyond this project.

```python
server_default=text("clock_timestamp()")   # not func.now()
```

PostgreSQL's `now()` returns **the time the transaction started**. Every statement inside one transaction sees the same value. Verified in `psql`:

```
BEGIN;
SELECT now();                        -- 23:14:44.199224
SELECT pg_sleep(0.05);
SELECT now(), clock_timestamp();     -- 23:14:44.199224 | 23:14:44.253365
```

`now()` did not move. `clock_timestamp()` did.

So two audit rows written during a single request shared a timestamp, and `ORDER BY created_at` returned them in arbitrary order — losing the sequence, which is most of what an audit log is for.

Nothing in SafeMed writes two rows in one request today. That is exactly why it was worth fixing: the trap is invisible until someone adds the second one, and then it fails silently, which is the failure mode this project keeps running into.

> **The bugs worth hunting are the ones that produce plausible wrong answers**, not the ones that crash. An out-of-order audit log looks completely normal.

### 10.7 What this does not do

Stated here so you state it first:

- **Nothing reads the log.** Rows are written and queryable by SQL; there is no review screen. A real system needs one, because a log nobody can read is a log nobody checks.
- **No retention policy.** Rows accumulate forever. Real systems age them out, and the policy is a legal question before it is a technical one.
- **No tamper-evidence.** Append-only is enforced in the application, not cryptographically. Someone with database access can still rewrite history.
- **Repeated refusals are recorded but not alerted on.** The data to detect a caregiver probing for records is there; nothing watches it.

### 10.8 Try these yourself

1. **Watch a refusal get recorded.** Sign in as Elena, have Maria revoke her, then reload Elena's screen. Then:
   ```bash
   docker compose exec db psql -U safemed -d safemed -c \
     "SELECT action, actor_id, patient_id, created_at FROM audit_events ORDER BY created_at DESC LIMIT 5;"
   ```
   The revoke and the refused read are both there, in order.
2. **Prove append-only.** In the same `psql` session the application cannot stop you — but try it through the app's own models and the listener raises. `pytest tests/test_audit.py -k cannot_be` shows both tests.
3. **Break the audit writer on purpose.** Patch `record_event` to raise, as `tests/test_audit_resilience.py` does, and confirm the caregiver's dashboard still loads while the error appears in the log. Then ask yourself whether you agree with that trade.
4. **See the `now()` problem for yourself.** Run the `BEGIN; SELECT now(); ...` block above in `psql`. It is a two-minute experiment that will save you a day at some point in your career.

---

## Chapter 11 — Requirements, and Proving You Met Them

Everything up to here was about building. This chapter is about the document that says what you were supposed to build, and the harder question of how anyone knows you did. It describes `docs/REQUIREMENTS.md`.

### 11.1 Why requirements come in layers

A requirement like "the system should keep patients safe" cannot be built or checked. A requirement like "`POST /medications` returns 201" can be checked but says nothing about why it exists. Neither is enough alone, so requirements are written in layers, each answering a different question.

| Layer | Answers | Example from SafeMed |
|---|---|---|
| **BR** — business | Why does this project exist? | BR-03: a patient's family can help without the patient losing control |
| **UR** — user | What does a person want to do? | UR-06: as a caregiver, see only the serious alerts for someone who invited me |
| **FR** — functional | What must the software do? | FR-29: record every occasion on which a caregiver reads a patient's record |

Read downward it is a justification: this endpoint exists because this user needs this, because the business promised that. Read upward it is a test of completeness — if a UR has no FR beneath it, nothing was built for it; if an FR has no UR above it, you built something nobody asked for. Both happen, and the layering is how you notice.

### 11.2 The four kinds in this document

SafeMed's specification has FRs and three other sets, because three things mattered here that a functional requirement cannot express.

- **FR-01 to FR-37** — things the system does. Each is one sentence containing "shall" and exactly one claim.
- **NFR-01 to NFR-11** — how well, rather than what. Response times, degradation behaviour, accessibility.
- **AIR-01 to AIR-05** — constraints on the AI layer specifically. These exist because the riskiest part of this project is the one a functional requirement would blandly describe as "explains a finding."
- **BC-01 to BC-03** — boundary constraints. Things the system must *never* do: diagnose, prescribe, or tell anyone to change a medication.

That last group is worth noticing as document design. A prohibition is not a feature, so it does not belong in the FR list — and yet the entire safety argument of this project rests on a requirement whose whole content is "do not."

### 11.3 How to write a requirement that can be checked

Three habits, all visible in the document.

**One claim per requirement.** FR-31 says a medication change shall be recorded *and* that a modification shall record which fields changed rather than their values. That is close to the limit. A requirement that can half-pass cannot be marked pass or fail, which is the only thing a requirement is for.

**"Shall", never "should" or "will".** "Should" invites an argument about whether it was really important. In a specification, "shall" means mandatory, and nothing else does.

**No implementation.** FR-30 says a refused attempt shall be recorded under an action distinct from a successful read. It does not say `patient_record.access_denied`, because that name is a design decision and the requirement has to outlive it.

### 11.4 Traceability, and what it is actually for

Section 8.1 maps business requirements to user requirements to functional requirements. It looks like bureaucracy. It does one thing nothing else does: it answers *"if we cut this, what breaks?"*

Look at the BR-02 row:

```
| BR-02 | UR-03 | FR-13...FR-16 |
```

Four functional requirements, one user requirement, one business reason. If recall monitoring had to be cut, that row tells you immediately that exactly one user-facing promise disappears with it, and which one. Without the table you would be reading thirty-seven requirements under time pressure trying to work out what depended on what — which is precisely when you get it wrong.

### 11.5 The column that makes it real

A specification that only lists requirements is a wish list. What makes this one checkable is that every functional requirement names the automated test that demonstrates it:

```
| FR-30 | The system shall record every refused attempt to read a patient's
          record, under an action distinct from a successful read.
        | test_audit_resilience.py::test_a_refused_attempt_is_recorded_under_its_own_action |
```

That third column changes the character of the document. "We met FR-30" stops being a claim and becomes a command anyone in the room can run. It also keeps the document honest: delete that test and CI stays green, but the specification now cites a test that does not exist, and the next person to check finds out.

Section 8.2 totals it by area — 197 automated tests across eight areas, every one run by CI on every push.

> **A requirement with no test is an intention.** The test is what converts it into something you can demonstrate rather than assert.

### 11.6 The section most specifications do not have

Section 9 is titled **Requirements Deliberately Not Met**. It lists six gaps with a reason for each: no interface for reading the audit log, schedules in UTC with no per-user time zones, a single interaction dataset, read-path audit failures tolerated, nothing deployed to a hosted environment, and the unused `notifications` table.

Writing that section is uncomfortable, and it is the most defensible thing in the document. Two reasons.

Every one of those gaps is findable by anyone who looks for twenty minutes. The only question is whether they hear it from you or discover it themselves, and those two produce very different impressions of the same project.

The subtler reason: naming a gap proves you understand your own system. "The `notifications` table is unused" is a sentence you can only write if you went looking for the difference between what you planned and what you built. Someone who cannot write that section does not know which of the two they are holding.

### 11.7 What this document does not do

- **It was written after most of the code.** An honest specification is written first and amended as reality intervenes. This one largely documents decisions already made, which makes it accurate but means it did not shape the build the way a specification is supposed to.
- **The NFRs are mostly unmeasured.** Response-time targets are stated and not benchmarked. An NFR you have not measured is an aspiration with a number attached to it.
- **Acceptance criteria and tests are the same thing here.** For a project this size that is defensible. On a larger one the people writing acceptance criteria are deliberately not the people writing the tests, and that separation is the entire point of having both.

### 11.8 Try these yourself

1. **Follow one requirement all the way down.** Start at BR-03, find its URs in section 3, find UR-06's FRs, pick FR-29, and run the test it names. Five minutes, and you will never again be caught by "how do you know you met your requirements?"
2. **Break the traceability on purpose.** Pick an FR, imagine deleting that feature, and use the 8.1 table to list everything that falls over. Then check whether the table was right.
3. **Find a requirement you cannot test.** Go through the NFRs and identify the ones with no automated check. Decide for each whether that is acceptable and why. That is the exact question you will be asked.

---

## Chapter 12 — Design Documents, and Who They Are For

`docs/DESIGN.md` is the other half of chapter 11. Requirements say what the system must do. Design says how it is arranged so that it can.

### 12.1 Four views, because there are four questions

One diagram of a whole system is unreadable, so the document gives four views, each answering one question for one audience.

| View | Question | Diagram |
|---|---|---|
| **Logical** | What are the parts, and what may call what? | module dependency graph |
| **Data** | What is stored, and how is it related? | entity-relationship diagram |
| **Process** | What is running, and what talks to what at runtime? | container and process diagram |
| **Scenario** | What actually happens when someone does X? | three sequence diagrams |

The scenario view is the one people skip and the one most worth having. A reviewer's real question is almost never "what are the modules." It is "what happens when a caregiver opens that page," and a sequence diagram answers that in ten seconds where prose takes a paragraph.

### 12.2 Why the diagrams are text, not pictures

Every diagram in `DESIGN.md` is a Mermaid code block — text that GitHub renders into a picture when the file is viewed.

This matters more than it sounds. A diagram drawn in a tool and exported as a PNG is a binary blob: git cannot diff it, nobody can edit it without the original file, and it goes stale silently the moment the code changes. A Mermaid block sits in the same file as its explanation, shows up in a pull-request diff as readable lines, and can be corrected by anyone with a text editor.

The trade is real — you get much less control over layout, and you depend on someone else's renderer. For a document whose job is to stay true to the code, that is the right trade.

### 12.3 Reading the module diagram: dependency direction

The logical view is not merely a map of the modules. It records a rule about which way dependencies may point. Section 2.1 calls it enforced dependency direction: API may call services, services may call repositories, and nothing points back up.

The reason is the one from chapter 5. If a service imported from the API layer, testing the safety engine would require an HTTP request, and the engine would be unusable from the Celery worker, which has no HTTP layer at all. The arrows in that diagram are why the same safety engine runs unchanged inside a web request and inside a background job.

### 12.4 Reading the ER diagram

The entity-relationship diagram shows the tables and how they relate, and section 3.1 highlights three decisions visible in the shape rather than in any single column.

One thing worth learning to spot: this diagram shows `notifications` related to `safety_findings`, and nothing writes to it. The diagram is accurate about the schema and misleading about the system — which is exactly the gap chapter 11's section 9 exists to close.

> **A design document describes structure. Only the requirements document can tell you whether that structure is used.**

### 12.5 Two Mermaid traps that cost real time

Both of these broke the diagrams in this project, and both took a while to find, because a Mermaid syntax error renders as blank space rather than an error message.

**Quotes inside a `Note` line.** `Note over A,B: he said "hello"` breaks the parser. Fixed in commit `5953b63`.

**A semicolon.** In Mermaid, `;` ends a statement. A semicolon used as ordinary English punctuation inside a label truncates it or kills the whole block. Fixed in `8dc10cd`.

And a third problem that is not a syntax error at all: **GitHub caches the rendered diagram.** After fixing one, the file can still display the broken version. Open it at its commit-pinned URL — `/blob/<sha>/docs/DESIGN.md` — to see what your fix actually produced rather than what the cache remembers. At least once in this project, a diagram that looked broken had already been fixed.

### 12.6 Design-level verification

Section 8 does something the diagrams cannot: it states which design decisions are enforced by a test rather than by discipline. The dependency direction, the audit guards, the degradation behaviour — each is either checked automatically or it is a convention that lasts until someone who has not read the document touches it.

This is chapter 11.5 one level up. A design decision nothing enforces is a decision with an expiry date you cannot see.

### 12.7 Try these yourself

1. **Break a diagram deliberately.** Put a semicolon inside a Mermaid label in a scratch branch, push it, and look at the rendered file. Learning what a Mermaid failure looks like is worth more than being told about it.
2. **Trace a sequence diagram against the code.** Take section 5.2, the caregiver read, and follow each arrow to the function that performs it. If the diagram and the code disagree, the diagram is wrong — fix it.
3. **Find the dependency rule's teeth.** Add an import from a service module back up to the API layer and run the suite. Whether anything stops you is the answer to whether that rule is enforced or merely written down.

---

## Chapter 13 — Deployment, Migrations, and the Build You Could Not Trust

Chapter 9 was about tests and the build that runs them. This chapter is about the thing chapter 9 missed for several weeks, which is a better lesson than anything chapter 9 got right.

### 13.1 The gap

CI ran on every push. It was green for weeks. It told you nothing whatsoever about whether the application could be installed.

Here is the mechanism, and it is one line. The test suite builds its database schema directly from the SQLAlchemy models:

```python
Base.metadata.drop_all(eng)
Base.metadata.create_all(eng)
```

Alembic — the tool that actually builds the schema when you deploy — was never invoked. So every test in the suite, including any migration test you might have written, ran against a schema Alembic had not produced.

This is not a coverage gap you could close by writing more tests of the same kind. The tests were not insufficient; they were exercising a different artifact than a deployment uses.

> **A migration nobody can run is a deploy nobody can do.** And nothing about a green application test suite reveals it.

### 13.2 Two ways to build a schema, and why having both is a trap

| | `create_all()` | Alembic |
|---|---|---|
| Builds from | the models, as they are right now | an ordered chain of migration scripts |
| Used by | the test suite | every real deployment |
| Knows about history | nothing | everything |

Having both is legitimate — `create_all()` is fast, which matters when the suite runs on every push. The trap is that the two can disagree indefinitely without any symptom, because the only thing that would reveal the disagreement is running the one you are not running.

### 13.3 What the check found the same day

Adding one CI step found a real defect immediately. The initial migration's `downgrade()` dropped its tables and left all eleven PostgreSQL ENUM types in place, because Alembic's autogenerate creates enum types and never writes the code to drop them.

The consequence: after any downgrade, the next upgrade died.

```
sqlalchemy.exc.ProgrammingError: type "user_role" already exists
```

And the detail that is worth more than the bug: **Alembic's own generated stub contained the words "please adjust!"** A tool stated in writing that it had left work unfinished, in a file that was read, committed, and reviewed. Generated code is a first draft with a note attached, and the note is usually accurate.

### 13.4 Why one-way is worse than broken

A migration that fails outright is an inconvenience — you find out at once and fix it. A migration chain that applies forward but cannot be re-applied after a rollback is worse, because of *when* you discover it.

You discover it while rolling back. Which is to say: at the one moment you are already dealing with a problem, under pressure, with the production system in a state you did not choose. The failure mode is not "the deploy breaks." It is "the escape hatch breaks, on the way out."

### 13.5 Reversibility as a rule, with teeth

Two things changed. `downgrade()` now drops the types it created. And CI runs this on every push:

```yaml
- name: Migrations apply and reverse cleanly
  working-directory: backend
  run: |
    alembic upgrade head
    alembic downgrade base
    alembic upgrade head
```

Three commands, in that order, deliberately. Upgrade proves it installs. Downgrade proves it can be rolled back. **The second upgrade is the one that matters** — it proves the rollback left the database in a state the migration can be applied to again, which is the property that was broken.

Note which database it runs against. The suite uses `safemed_test`; this step uses `safemed`, which nothing else in CI touches. The check needs a database whose state it controls completely, and the test database is not that.

### 13.6 What "not deployed" means, and why we say it

SafeMed runs under Docker Compose and has never been deployed to a hosted environment. That is listed as a gap in the requirements specification rather than left to be noticed.

The honest version of the claim is narrow and worth getting exactly right: *part of the deployment path is tested, and none of it has been exercised against real infrastructure.* Migrations apply and reverse on every push, and the whole system starts from `docker compose up` on a machine that has never seen it. What has not been proven is anything involving a hostname, a certificate, a managed database, secrets handling outside a local `.env`, or the behaviour of any of it under concurrent real users.

Those are not small. Claiming "it works in Docker, so it would work deployed" is the kind of sentence that gets taken apart in a question, and the narrower claim is both true and defensible.

And there was one more gap of exactly the kind this chapter is about, found while writing this chapter:

**CI did not build the Dockerfile.** The backend job installs Python on the runner with `setup-python` and runs `pytest` against a PostgreSQL service container. There was no `docker build` in the workflow anywhere. So `backend/Dockerfile` was a third artifact nothing checked — break it, and CI stayed green while `docker compose up` failed on every machine including this one.

That is the same mistake as section 13.1, one layer out. Having found it once and named the principle, we then failed to apply the principle to the next artifact along. Which is worth saying out loud, because the lesson of 13.1 is not "test your migrations." It is:

> **Ask which artifact your green build actually exercised, and name the ones it did not.** That question has to be asked repeatedly, because the answer changes every time you add a way of building or shipping the thing.

### 13.7 Testing the deploy path, and the mount that hides it

The `deploy-path` job closes that gap. It deliberately follows the path the README gives a contributor rather than a convenient approximation: copy `.env.example`, generate a `SECRET_KEY`, `docker compose build`, `docker compose up -d`, then prove the thing serves traffic. It fails if the template's placeholder key survives, if any of the five services is not running, or if `/health` does not answer inside sixty seconds — and dumps `compose ps` and the container logs when it does fail, because a CI failure nobody can diagnose from the log is a CI failure people learn to ignore.

One step in it is not obvious, and it is the interesting part of the whole job.

```yaml
- name: The image contains a working application
  run: |
    docker build -t safemed-api:ci ./backend
    docker run --rm -e SECRET_KEY=... -e DATABASE_URL=... \
      safemed-api:ci python -c "import app.main; print('import ok')"
```

Why build and run the image separately, when the job is about to start the whole stack anyway? Because of this, in `docker-compose.yml`:

```yaml
volumes:
  - ./backend:/app        # live code reload during development
```

That mount puts the host's source directory on top of `/app` at runtime, which is what makes editing a file reload the server without rebuilding. It also means **the image's own copy of the code is masked.** The container runs the host's files, not the ones the Dockerfile copied in.

So `docker compose up` proves the image's *dependencies* are right. It cannot prove the image's *code* is there at all. A `Dockerfile` that forgot `COPY . .` would pass the compose check and then fail on any machine without the source tree sitting next to it — which is every machine you would actually deploy to.

Running the bare image with no mount is the only step in this repository that tests what ships.

> **A convenience that makes development pleasant can also make a test meaningless.** The live-reload mount is worth having. It is also the reason one of these two checks is not enough.

### 13.8 Try these yourself

1. **Break the chain again and watch CI catch it.** On a branch, remove the enum drops from the initial migration's `downgrade()` and push. The migration step fails with the exact error above. That is what a regression test for infrastructure looks like.
2. **Run the three commands by hand, against a throwaway database.** Never against your development one — the downgrade deletes everything. Create `safemed_scratch`, point `DATABASE_URL` at it, and run them. Then check that a downgrade left no enum types behind:
   ```bash
   docker compose exec db psql -U safemed -d safemed_scratch -c "\dT"
   ```
3. **Read a generated migration before committing it.** Autogenerate one for a trivial model change and read every line. Find at least one thing it got wrong or left out. There usually is one.
4. **Prove the mount really does mask the image.** Build the image, then run it twice — once as compose does and once bare — and look at the difference:
   ```bash
   docker build -t safemed-try ./backend
   docker run --rm safemed-try ls /app/app/main.py
   docker run --rm -v "$PWD/backend:/app" safemed-try ls /app/app/main.py
   ```
   Both find the file, which is the point: the second one found the *host's* copy. Now delete `COPY . .` from a scratch copy of the Dockerfile and run both again. The bare run fails; the mounted one still passes. That is the failure the `deploy-path` job's bare-image step exists to catch, and it is worth seeing once.
5. **Make the deploy-path job fail on purpose.** Change the health URL in the workflow to a path that does not exist and push to a branch. Read the failure output. If you cannot tell from the log what went wrong, the step needs more diagnostics — that judgement is the whole reason it dumps `compose ps` and the container logs.

---

## Chapter 14 — Finishing

Shipping is a phase with its own skills, and they are not the ones that got you here. This chapter is about the last two weeks.

### 14.1 Writing about your own work

The hard part of the final report is not the writing. It is that you are the worst-placed person to describe your own system, because everything about it feels obvious to you, including the parts that are only obvious if you built it.

Two habits that help.

**Write from the record, not from memory.** Every factual claim in the report traces to a file, a commit, or a query. Not because anyone demanded it, but because your memory of this project is already wrong in places — the account of the merge collision in section 9.3 of the report is the opposite of what everyone remembered, and only the timestamps revealed it.

**Prefer the claim you can point at.** An early draft said aspirin and warfarin interact "seriously enough to be one of the standard textbook examples." True, probably, and unanswerable if someone asks *which* textbook. It became "a pair DDInter grades Major" — a column value, checkable in ten seconds. Every claim in a submitted document is a claim you have offered to defend.

### 14.2 The report is a build artifact

`docs/FINAL_REPORT.md` is the source. The PDF is generated:

```bash
docker compose exec api python -m scripts.build_report FINAL_REPORT
```

The reason is the one from chapter 12.2. A hand-edited PDF beside a Markdown source is two documents that will disagree, and you will not find out which is current until someone reads the wrong one. Generating it means the Markdown is the only thing that can be edited, so drift is structurally impossible rather than merely discouraged.

The PDF is also git-ignored, which follows: committing a build output invites someone to edit it.

One thing `build_report.py` does that is worth knowing about in general. The base-14 PDF fonts cover WinAnsi only, so a character like an arrow has no glyph and renders as a blank box — **silently**, which is how a submitted document ends up with holes in it. The script transliterates those characters to ASCII before conversion. The lesson generalises past PDFs: a pipeline that drops data without complaining is worse than one that fails, which is chapter 9's lesson and section 9.1 of the report arriving from a third direction.

### 14.3 Numbers you can defend

The demo script ends with four numbers to memorise. The reason to memorise numbers rather than read them is not performance; it is that a number you have internalised is one you will not misstate under a question, and a misstated number is the fastest way to lose a room's confidence in everything else you said.

The same script used to say two rows in the audit log were "1.5 milliseconds apart." Rehearsing found that figure tracks machine load — 2.3ms on one run, 208.6ms on another, same machine. If you quote it and the screen disagrees, you have handed away credibility for no reason. It now describes the property instead: the order is recoverable at all, which is the actual point.

**State the property, not the measurement, unless the measurement is the point.** When it is the point — 21 of 84, 45 of 100 — know exactly where it came from.

### 14.4 The project-management lesson, stated plainly

The one real coordination failure is in section 9.3 of the report. Two people created the same file independently on the same afternoon. The lesson, in one line:

> **Tasks defined by outcome cannot be checked for overlap. Tasks defined by directory can.**

"Connect the account forms to the API" and "wire the frontend to the API" are the same sentence twice, and neither names the file they collided in. No amount of communicating fixes that, because spotting the overlap requires both people to have already imagined the same implementation. Ownership by directory makes the boundary visible in a diff before anything merges, and `CODEOWNERS` can enforce it without a conversation.

The second half is less comfortable and more useful. One member committing twelve features in a day makes collision arithmetic rather than misfortune — anyone working in parallel is standing in ground about to be built over, and their own pace has nothing to do with it. If you are the fast one, the burden of announcing scope is yours, because you are the one generating the overlap.

### 14.5 Rehearsing is testing

A demo is a program with a human runtime, and it deserves the same treatment as code: run it end to end, against the real system, before it matters.

Rehearsing this one found two defects in the script and confirmed six claims. That ratio is normal. The things worth checking are the ones that depend on something outside your control:

- Anything hitting a live external API. The recall beat calls openFDA for real; it returns in about twenty seconds against a 120-second timeout, which is comfortable and not guaranteed.
- Anything quoting a number that the screen will also show.
- Anything requiring a sequence of UI steps in a particular order. The audit beat needs invite, accept, view, revoke, retry — and the refusal row only exists if all five happened.
- Anything with accumulated state. The audit log cannot be cleared by the application, by design, so rehearsing fills it. Clear it once from `psql` before the real run — and notice that having to use `psql` to do it is itself the honest caveat: append-only is enforced in the application, not in the database.

### 14.6 What we would do differently from week one

Four things, and each is a mechanism rather than an intention, because a small team fitting this around coursework will not sustain anything that depends on everyone remembering.

1. **Assign work by directory, not by outcome.** The collision becomes structurally impossible rather than merely unlikely.
2. **Push every branch daily, finished or not.** Unpushed work does not exist. Three and a half hours of invisible work is all it took.
3. **Claim the issue on the board before the first commit.** The board existed the whole time and was not the mechanism.
4. **Grow the schema with the code.** The data model was written in week one, which made it a forecast rather than a record — and `notifications` is the table where the forecast was wrong.

### 14.7 The last word

The handbook started with a claim: a software engineer who can explain their choices is worth more than one who can only type code.

Fourteen chapters later the evidence for that is specific rather than inspirational. The most valuable things in this project were not the features. They were a quiet empty list that should have been a warning, a green build that was testing the wrong artifact, a merge conflict whose timestamps contradicted everyone's memory of it, and a table that exists because of a plan nobody revisited.

None of those are in the feature list. All of them are things you can now explain, and that is the difference the handbook was for.

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
| **RXCUI** | RxNorm stable numeric id for a drug concept - what makes "aspirin" and "Acetylsalicylic acid" comparable |
| **Dedupe key** | A hash of who and what a finding concerns, never when, so re-running finds nothing new |
| **Provenance** | Where a claim came from: source name, version, and the raw evidence |
| **Tiered matching** | CONFIRMED vs POSSIBLE vs no match - saying how sure we are instead of guessing |
| **Grace period** | Minutes after a scheduled dose before it counts as missed |
| **Severity routing** | Only SEVERE findings reach a caregiver; the patient sees all of them |
| **Guardrail** | A check on AI output that discards a response rather than showing it |
| **Protocol (Python)** | A required shape rather than a base class - any object with the right methods fits |
| **CI** | Continuous integration - a server that runs your tests automatically on every push |
| **Fixture** | Reusable setup a test asks for by name (our `db` fixture hands over a session that is rolled back afterwards) |
| **Regression test** | A test written after a bug, whose job is to fail if that bug ever comes back |
| **Threats to validity** | The stated reasons a measurement might not generalise - named by you, not left for the reader to find |
| **Append-only** | A table you can add to but never change or delete - what makes a log usable as evidence |
| **Savepoint** | A marker inside a transaction you can roll back to without losing the rest of it |
| **clock_timestamp()** | PostgreSQL function returning the real current time; `now()` returns the transaction start time instead |
| **SRS** | Software Requirements Specification - the document saying what the system must do, and why |
| **BR / UR / FR** | Business, user and functional requirement - the three layers, from why the project exists down to what the software does |
| **NFR** | Non-functional requirement - how well rather than what (speed, accessibility, degradation) |
| **Boundary constraint** | A requirement whose whole content is "never do this"; BC-01, no diagnosing, is the most important requirement in SafeMed |
| **Traceability** | The chain from business reason to user need to functional requirement to the test that proves it |
| **Mermaid** | Diagrams written as text in the Markdown file and rendered by GitHub, so they diff and cannot silently go stale |
| **Sequence diagram** | Shows the order of calls between parts for one scenario - answers "what happens when someone does X" |
| **Dependency direction** | The rule about which layers may call which; why the same safety engine runs in a web request and in a worker |
| **create_all()** | Builds the schema straight from the models. Fast, used by the test suite, knows nothing about history - and not what a deployment runs |
| **Reversible migration** | One whose downgrade leaves the database in a state the upgrade can be applied to again. Proved by upgrade / downgrade / upgrade, where the second upgrade is the one that matters |
| **Build artifact** | A file generated from a source and never edited directly - our PDF, which is git-ignored so nobody is tempted |
| **CODEOWNERS** | A GitHub file mapping paths to the people who must review changes to them - how task-by-directory gets enforced instead of remembered |
| **Bind mount** | A host directory placed over a path inside a container. Gives live reload, and masks the image's own copy of whatever is underneath - which is why the image has to be tested without one |

---
