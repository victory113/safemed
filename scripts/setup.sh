#!/usr/bin/env bash
# SafeMed - one-command setup (macOS / Linux).
#
#   ./scripts/setup.sh              set up and leave the database empty
#   ./scripts/setup.sh --demo       also seed Maria and Elena
#
# Satisfies NFR-11: a clean checkout reaches a running, usable system from one
# command. Starting the containers is not enough on its own - the schema and
# the interaction dataset are separate steps, and skipping the second one
# produces a system that checks every medication list against nothing and
# reports no problems. Every step below is idempotent, so running this twice
# is safe.

set -euo pipefail

cd "$(dirname "$0")/.."

DEMO=0
for arg in "$@"; do
    case "$arg" in
        --demo) DEMO=1 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

step() { printf '\n[%s] %s\n' "$1" "$2"; }
ok()   { printf '    %s\n' "$1"; }

echo "SafeMed setup"
printf '%s\n' "============================================================"

# ---- 1. Docker ------------------------------------------------------------
step 1 "Checking Docker"
if ! docker info >/dev/null 2>&1; then
    echo "    Docker is not responding. Start Docker Desktop and wait until" >&2
    echo "    it says 'Engine running', then run this again." >&2
    exit 1
fi
ok "Docker is running"

# ---- 2. Configuration -----------------------------------------------------
# SECRET_KEY has no default and the application refuses to boot without one
# (NFR-01). Generating it here means a new checkout never has to think about
# it, and it is never printed.
step 2 "Configuration"
if [ -f .env ]; then
    ok ".env already exists - leaving it alone"
else
    cp .env.example .env
    key="$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '=')"
    # A generated key can contain characters sed would read as part of the
    # pattern, so pass it through the environment rather than interpolating.
    KEY="$key" perl -pi -e 's/SECRET_KEY=change-me-generate-your-own/"SECRET_KEY=$ENV{KEY}"/e' .env
    ok "Created .env with a generated SECRET_KEY"
fi

# ---- 3. Services ----------------------------------------------------------
step 3 "Starting the services (first run pulls images - a few minutes)"
docker compose up --build -d

printf '    waiting for the database to report healthy'
healthy=0
for _ in $(seq 1 60); do
    if docker compose ps db --format json | grep -q '"Health":"healthy"'; then
        healthy=1
        break
    fi
    printf '.'
    sleep 2
done
printf '\n'
if [ "$healthy" -ne 1 ]; then
    echo "    The database did not report healthy within two minutes." >&2
    echo "    Check 'docker compose ps' and 'docker compose logs db'." >&2
    exit 1
fi
ok "All services up"

# ---- 4. Schema ------------------------------------------------------------
# Nothing creates the tables automatically: the containers run uvicorn, not
# Alembic. A fresh database has no tables at all until this runs.
step 4 "Creating the database schema"
docker compose exec -T api alembic upgrade head
ok "Schema is at head"

# ---- 5. Interaction dataset ----------------------------------------------
# The expensive step, and the one whose absence is invisible: an empty
# drug_interactions table makes the safety engine correctly find nothing in
# every medication list, which looks exactly like good news.
step 5 "Interaction dataset"
rows="$(docker compose exec -T db psql -U safemed -d safemed -t -A \
    -c 'SELECT count(*) FROM drug_interactions;' 2>/dev/null | tr -d '[:space:]')"
case "$rows" in
    ''|*[!0-9]*) rows=0 ;;
esac

if [ "$rows" -gt 0 ]; then
    ok "$rows interactions already loaded - skipping the download"
else
    echo "    downloading eight CSVs from DDInter - a few minutes"
    if ! docker compose exec -T api python -m scripts.import_ddinter; then
        echo "    The import failed. SafeMed will run, but every safety check" >&2
        echo "    will find nothing. Re-run this script once the network is" >&2
        echo "    available, or see the --from-dir option in README.md." >&2
        exit 1
    fi
    ok "Dataset loaded"
fi

# ---- 6. Demo data (optional) ---------------------------------------------
if [ "$DEMO" -eq 1 ]; then
    step 6 "Seeding demo data"
    docker compose exec -T api python -m scripts.seed_demo
fi

# ---- Done -----------------------------------------------------------------
printf '%s\n' "============================================================"
echo "Backend ready."
echo
echo "  http://localhost:8000/health   service and database status"
echo "  http://localhost:8000/docs     API documentation"
echo
echo "Start the frontend in another window:"
echo "  npm install --prefix frontend"
echo "  npm run dev --prefix frontend"
echo
echo "  http://localhost:5173          the application"
if [ "$DEMO" -ne 1 ]; then
    echo
    echo "No accounts exist yet. Register one in the app, or run this script"
    echo "again with --demo for Maria and Elena."
fi
