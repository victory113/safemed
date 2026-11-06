# SafeMed

A continuous medication safety monitoring and caregiver alert platform.

CSCI 4490 Software Engineering - Fall 2026
Victory Orobosa | Chima Onochie | Pacifique Mugisha

## What it does

A patient (or an authorized caregiver) records their medications. SafeMed
identifies each medication using standardised drug data, checks the full list
against authoritative interaction and FDA recall information, and records any
potential issue together with its source and severity.

A background worker keeps checking after the app is closed. When new safety
information affects a patient's medications, the authorized caregiver is
notified and the event is written to an audit trail.

**Safety boundary.** Safety findings come from authoritative data evaluated by
deterministic rules, never from AI. AI is used only to explain a verified
finding in plain language. SafeMed does not diagnose, prescribe, or tell anyone
to change a medication. Development and demonstrations use synthetic data only.

## Running it locally

Requires Docker Desktop (running) and nothing else.

```bash
cp .env.example .env      # Windows PowerShell: Copy-Item .env.example .env
docker compose up --build
```

Then open:

- http://localhost:8000/health - service + database status
- http://localhost:8000/docs   - interactive API documentation

Stop with Ctrl+C, then `docker compose down`.

## Repository layout

```
safemed/
├── docker-compose.yml   all services: database, redis, api
├── backend/             FastAPI application
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py      application entry point
│       ├── core/        configuration
│       └── db/          database engine and sessions
└── docs/
    └── HANDBOOK.md      project handbook
```

## Team: start here

1. **[docs/TEAM_GUIDE.md](docs/TEAM_GUIDE.md)** - who does what, how we use
   GitHub and VS Code, and a complete worked example of taking one task from
   start to merged. **Read this first.**
2. [docs/SETUP.md](docs/SETUP.md) - installing everything. Done once.
3. [docs/WORKFLOW.md](docs/WORKFLOW.md) - git command reference for daily use.
4. [docs/API_CONTRACT.md](docs/API_CONTRACT.md) - the exact request and
   response shapes our code exchanges.
5. [docs/HANDBOOK.md](docs/HANDBOOK.md) - why the project is built this way.

## Repository layout

```
safemed/
├── docker-compose.yml   all services: database, redis, api
├── backend/             FastAPI application
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py      application entry point
│       ├── core/        configuration
│       └── db/          database engine and sessions
└── docs/
    └── HANDBOOK.md      project handbook
```

## For new team members

1. **[docs/SETUP.md](docs/SETUP.md)** - install everything and get the project
   running. You do this once.
2. **[docs/WORKFLOW.md](docs/WORKFLOW.md)** - how to open the project in VS Code,
   pick up a task, write code, and open a pull request. You do this every day.

## Documentation

See `docs/HANDBOOK.md` for the design decisions behind this project and an
explanation of every tool used.
