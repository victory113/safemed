# SafeMed - one-command setup (Windows / PowerShell).
#
#   .\scripts\setup.ps1              set up and leave the database empty
#   .\scripts\setup.ps1 -Demo        also seed Maria and Elena
#
# Satisfies NFR-11: a clean checkout reaches a running, usable system from one
# command. Starting the containers is not enough on its own - the schema and
# the interaction dataset are separate steps, and skipping the second one
# produces a system that checks every medication list against nothing and
# reports no problems. Every step below is idempotent, so running this twice
# is safe.

[CmdletBinding()]
param(
    [switch]$Demo
)

# Native tools (docker, psql, alembic) write progress to stderr, which
# PowerShell 5.1 turns into terminating errors under "Stop". Check exit codes
# explicitly instead.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Write-Step { param($n, $text) Write-Host "`n[$n] $text" -ForegroundColor Cyan }
function Write-Ok   { param($text)    Write-Host "    $text" -ForegroundColor Green }
function Write-Warn { param($text)    Write-Host "    $text" -ForegroundColor Yellow }

Write-Host "SafeMed setup" -ForegroundColor White
Write-Host ("=" * 60)

# ---- 1. Docker ------------------------------------------------------------
Write-Step 1 "Checking Docker"
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "    Docker is not responding. Start Docker Desktop and wait" -ForegroundColor Red
    Write-Host "    until it says 'Engine running', then run this again." -ForegroundColor Red
    exit 1
}
Write-Ok "Docker is running"

# ---- 2. Configuration -----------------------------------------------------
# SECRET_KEY has no default and the application refuses to boot without one
# (NFR-01). Generating it here means a new checkout never has to think about
# it, and it is never printed.
Write-Step 2 "Configuration"
if (Test-Path ".env") {
    Write-Ok ".env already exists - leaving it alone"
} else {
    Copy-Item ".env.example" ".env"
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $key = [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
    $content = Get-Content ".env" -Raw
    $content = $content -replace "SECRET_KEY=change-me-generate-your-own", "SECRET_KEY=$key"
    Set-Content ".env" $content -Encoding utf8 -NoNewline
    Write-Ok "Created .env with a generated SECRET_KEY"
}

# ---- 3. Services ----------------------------------------------------------
Write-Step 3 "Starting the services (first run pulls images - a few minutes)"
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "    waiting for the database to report healthy" -NoNewline
$healthy = $false
foreach ($attempt in 1..60) {
    # Ask about one service, so a plain substring match is unambiguous. The
    # JSON line carries a Publishers array, so anything matching across the
    # whole object with [^}] would never match at all.
    $state = (docker compose ps db --format json 2>$null | Out-String)
    if ($state -match '"Health":"healthy"') {
        $healthy = $true
        break
    }
    Write-Host "." -NoNewline
    Start-Sleep -Seconds 2
}
Write-Host ""
if ($healthy) {
    Write-Ok "All services up"
} else {
    Write-Warn "The database did not report healthy within two minutes."
    Write-Warn "Check 'docker compose ps' and 'docker compose logs db'."
    exit 1
}

# ---- 4. Schema ------------------------------------------------------------
# Nothing creates the tables automatically: the containers run uvicorn, not
# Alembic. A fresh database has no tables at all until this runs.
Write-Step 4 "Creating the database schema"
docker compose exec -T api alembic upgrade head
if ($LASTEXITCODE -ne 0) { exit 1 }
Write-Ok "Schema is at head"

# ---- 5. Interaction dataset ----------------------------------------------
# The expensive step, and the one whose absence is invisible: an empty
# drug_interactions table makes the safety engine correctly find nothing in
# every medication list, which looks exactly like good news.
Write-Step 5 "Interaction dataset"
$count = (docker compose exec -T db psql -U safemed -d safemed -t -A -c `
    "SELECT count(*) FROM drug_interactions;" 2>$null | Out-String).Trim()
$rows = 0
[void][int]::TryParse($count, [ref]$rows)

if ($rows -gt 0) {
    Write-Ok "$rows interactions already loaded - skipping the download"
} else {
    Write-Host "    downloading eight CSVs from DDInter - a few minutes"
    docker compose exec -T api python -m scripts.import_ddinter
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "The import failed. SafeMed will run, but every safety check"
        Write-Warn "will find nothing. Re-run this script once the network is"
        Write-Warn "available, or see the --from-dir option in README.md."
        exit 1
    }
    Write-Ok "Dataset loaded"
}

# ---- 6. Demo data (optional) ---------------------------------------------
if ($Demo) {
    Write-Step 6 "Seeding demo data"
    docker compose exec -T api python -m scripts.seed_demo
    if ($LASTEXITCODE -ne 0) { exit 1 }
}

# ---- Done -----------------------------------------------------------------
Write-Host ("=" * 60)
Write-Host "Backend ready." -ForegroundColor Green
Write-Host ""
Write-Host "  http://localhost:8000/health   service and database status"
Write-Host "  http://localhost:8000/docs     API documentation"
Write-Host ""
Write-Host "Start the frontend in another window:"
Write-Host "  npm install --prefix frontend" -ForegroundColor White
Write-Host "  npm run dev --prefix frontend" -ForegroundColor White
Write-Host ""
Write-Host "  http://localhost:5173          the application"
if (-not $Demo) {
    Write-Host ""
    Write-Host "No accounts exist yet. Register one in the app, or run this"
    Write-Host "script again with -Demo for Maria and Elena."
}
