# SafeMed

[![CI](https://github.com/victory113/safemed/actions/workflows/ci.yml/badge.svg)](https://github.com/victory113/safemed/actions/workflows/ci.yml)

A continuous medication safety monitoring and caregiver alert platform.

CSCI 4490 Software Engineering — Fall 2026
Victory Orobosa | Chima Onochie | Pacifique Mugisha

## What it does

A patient records their medications. SafeMed identifies each one against
standardised drug data, checks the full list against authoritative interaction
and FDA recall information, and records every potential issue together with its
source and severity.

A background worker keeps checking after the app is closed. When new safety
information affects a patient's medications, a caregiver the patient has
explicitly authorized is shown the serious findings — and only the serious
ones.

Every consent change, every medication change, and every time a caregiver
reads a patient's record is written to an append-only audit log — including
the attempts that were refused.

**Safety boundary.** Safety findings come from authoritative data evaluated by
deterministic rules, never from AI. AI is used only to explain a verified
finding in plain language, receives no patient data, and any response that
tells someone to stop or change a medication is discarded rather than shown.
SafeMed does not diagnose, prescribe, or advise changing a medication.
Development and demonstration use synthetic data only.

## Running it locally

Requires Docker Desktop (running) for the backend, and Node 20+ for the
frontend development server.

**The short way.** One command does everything below except the frontend, and
is safe to re-run:

```bash
./scripts/setup.sh --demo          # Windows: .\scripts\setup.ps1 -Demo
```

Drop `--demo` to set up without the demo patient. Then start the frontend
(step 5). The rest of this section is what that script does, step by step, for
when you want to run the steps yourself or one of them fails.

Each step prints something you can check, because a step that half-worked is
the expensive kind.

**1. Configuration.**

```bash
cp .env.example .env      # Windows PowerShell: Copy-Item .env.example .env
```

`.env` is git-ignored. Generate your own `SECRET_KEY` before starting — the
application refuses to boot without one, on purpose:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**2. Start the services.**

```bash
docker compose up --build -d
```

`docker compose ps` should show five services — `api`, `db`, `redis`,
`worker`, `beat` — with `db` and `redis` reporting `healthy`.

**3. Create the schema.** Nothing creates it automatically: the containers run
`uvicorn`, not Alembic, so a fresh database starts with no tables.

```bash
docker compose exec api alembic upgrade head
```

**4. Load the interaction dataset.** This downloads eight CSVs from DDInter
and takes a few minutes. Without it the `drug_interactions` table is empty and
the safety engine will correctly find nothing in any medication list — which
looks exactly like an application that works and has nothing to report.

```bash
docker compose exec api python -m scripts.import_ddinter
```

Expect **160,235 interactions** when it finishes. The import is idempotent, so
running it twice is harmless. If DDInter is unreachable, download the eight
`ddinter_downloads_code_*.csv` files by hand and pass
`--from-dir /app/data` instead.

**5. Start the frontend.**

```bash
npm install --prefix frontend && npm run dev --prefix frontend
```

Then open:

- http://localhost:5173 — the application
- http://localhost:8000/health — service and database status
- http://localhost:8000/docs — interactive API documentation

`/health` reports the database separately from the API, so it distinguishes
"the API is down" from "the API is up and cannot reach Postgres".

Stop the frontend with Ctrl+C, then `docker compose down`. Use `down -v` only
when you want the database destroyed — it deletes the imported dataset too,
and steps 3 and 4 have to be repeated.

## Running the checks

The same two commands CI runs on every push:

```bash
docker compose exec api pytest
```

```bash
cd frontend && npx tsc -b && npm run lint && npm test
```

## Seeding a demo

```bash
docker compose exec api python -m scripts.seed_demo
```

Creates a patient (`maria@safemed.demo`) and a caregiver
(`elena@safemed.demo`), both with password `demo-password-123`, and generates
their safety findings. Safe to re-run.

It should end with **10 findings created**. If it ends with 0, step 4 above has
not been run — the script checks for this and says so rather than producing a
patient whose safety screen is reassuringly empty. See
[docs/DEMO.md](docs/DEMO.md) for the presentation run sheet.

## Repository layout

```
safemed/
├── docker-compose.yml       all five services
├── .github/workflows/ci.yml backend tests + frontend typecheck, lint, tests
├── scripts/                 setup.sh / setup.ps1 — one-command setup (NFR-11)
├── backend/
│   ├── Dockerfile
│   ├── alembic/             database migrations
│   ├── scripts/             data import, RXCUI resolution, seeding, evaluation
│   ├── tests/               16 files, 194 tests
│   └── app/
│       ├── main.py          application entry point
│       ├── api/             HTTP routes and dependencies
│       ├── core/            configuration and security
│       ├── db/              engine and sessions
│       ├── models/          SQLAlchemy tables
│       ├── schemas/         Pydantic request and response shapes
│       ├── repositories/    database queries
│       ├── services/        safety engine, RxNorm, recalls, AI explainer
│       └── workers/         Celery tasks and schedule
├── frontend/
│   └── src/
│       ├── api/             the only place that talks to the API
│       ├── components/      shared UI primitives
│       ├── pages/           auth, patient dashboard, caregiver dashboard
│       ├── session/         who is signed in, routing, links
│       └── styles/
└── docs/
```

## Documentation

| | |
|---|---|
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | Requirements specification — business, user, functional, non-functional, AI and boundary constraints, with a traceability matrix. |
| [docs/DESIGN.md](docs/DESIGN.md) | Architecture and design — module, data, process and scenario views, with diagrams. |
| [docs/HANDBOOK.md](docs/HANDBOOK.md) | Why the project is built this way, chapter by chapter. Start here to understand the design. |
| [docs/EVALUATION.md](docs/EVALUATION.md) | What was measured, how, and the threats to validity. |
| [docs/FINAL_REPORT.md](docs/FINAL_REPORT.md) | The final project report. |
| [docs/DEMO.md](docs/DEMO.md) | The presentation run sheet. |
| [docs/SafeMed_Final_Presentation.pptx](docs/SafeMed_Final_Presentation.pptx) | The slide deck, generated from [docs/presentation/build.js](docs/presentation/build.js). |
| [docs/API_CONTRACT.md](docs/API_CONTRACT.md) | Exact request and response shapes. |

## Team: start here

1. **[docs/TEAM_GUIDE.md](docs/TEAM_GUIDE.md)** — who does what, how we use
   GitHub and VS Code, and a worked example of taking one task from start to
   merged. **Read this first.**
2. [docs/SETUP.md](docs/SETUP.md) — installing everything. Done once.
3. [docs/WORKFLOW.md](docs/WORKFLOW.md) — git command reference for daily use.

## Known limitations

Stated here rather than discovered later:

- **The audit log has one deliberate hole.** If the audit write itself fails,
  a caregiver's *read* is still served and the failure is logged loudly
  rather than refused. Writes keep the strict behaviour. A system under a
  real regulatory obligation would make the opposite call; the reasoning is
  in `app/services/audit.py`.
- **Nothing reads the audit log yet.** Rows are written and queryable by SQL,
  but there is no screen or endpoint for reviewing them.
- **Schedules are wall-clock UTC.** There are no per-user time zones, and the
  interface formats times in UTC rather than silently showing the wrong hour.
- **One interaction dataset.** DDInter only, so the evaluation measures
  internal consistency rather than completeness. The source sits behind an
  interface and is swappable.
