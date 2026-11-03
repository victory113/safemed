# Creates the Sprint 1 issues on GitHub.
#
# One-off bootstrap script. Run it once, then delete it or leave it as a record
# of how the first sprint was planned.
#
# Requires the GitHub CLI:   winget install --id GitHub.cli
# Then sign in once:         gh auth login
#
# EDIT THESE TWO LINES with your teammates' GitHub usernames before running.
$CHIMA     = "chima-github-username"
$PACIFIQUE = "pacifique-github-username"
$VICTORY   = "victory113"

# ---------------------------------------------------------------------------

function New-SafeMedIssue {
    param($Title, $Body, $Assignee)

    Write-Host "Creating: $Title" -ForegroundColor Cyan
    gh issue create --title $Title --body $Body --assignee $Assignee
}

# ----- Victory -------------------------------------------------------------

New-SafeMedIssue -Assignee $VICTORY -Title "Create data model and initial migration" -Body @'
The database foundation every other feature depends on.

**Done when:**
- [x] User, ConsentGrant, Medication, DoseSchedule, DoseEvent, SafetyFinding, Notification, AuditEvent models
- [x] Alembic configured to read DATABASE_URL from application settings
- [x] Initial migration generated and applied
- [x] All 9 tables confirmed present in psql

**Area:** Backend
'@

New-SafeMedIssue -Assignee $VICTORY -Title "Add medication CRUD endpoints" -Body @'
Patients need to record what they take.

**Done when:**
- [ ] POST /api/v1/medications adds a medication for the current patient
- [ ] GET /api/v1/medications lists the current patient's medications
- [ ] PATCH /api/v1/medications/{id} updates dose, notes, or status
- [ ] A patient can only see and edit their own medications
- [ ] Every create, update, and status change writes an audit event
- [ ] Tests cover the happy path and the unauthorised-access case

**Area:** Backend
'@

New-SafeMedIssue -Assignee $VICTORY -Title "Normalize medication names via RxNorm" -Body @'
Free text like "tylenol" must resolve to a stable identifier so the safety
engine can reason over IDs rather than spelling.

**Done when:**
- [ ] Look up the entered name and store rxcui + normalized_name
- [ ] The medication still saves when RxNorm is unavailable (rxcui stays null)
- [ ] Requests time out after 2 seconds rather than hanging
- [ ] Tests cover: match found, no match, service unavailable

**Area:** Backend
'@

New-SafeMedIssue -Assignee $VICTORY -Title "Generate dose events and daily dose logging" -Body @'
The daily "I took my medication" feature. Expected doses are generated ahead of
time so a MISSED dose can be detected at all.

**Done when:**
- [ ] DoseEvent rows generated from active schedules
- [ ] Running the generator twice creates no duplicates (idempotent)
- [ ] POST /api/v1/doses/{id}/confirm marks a dose TAKEN with a timestamp
- [ ] Doses past their grace period become MISSED
- [ ] GET /api/v1/doses/today returns the patient's doses for today
- [ ] Tests cover the full scheduled -> due -> taken/missed flow

**Area:** Backend
'@

# ----- Chima ---------------------------------------------------------------

New-SafeMedIssue -Assignee $CHIMA -Title "Add password hashing and JWT authentication" -Body @'
Users must register and log in before any patient data is accessible.

**Done when:**
- [ ] POST /api/v1/auth/register creates a user with a bcrypt-hashed password
- [ ] POST /api/v1/auth/login returns a JWT on valid credentials
- [ ] Invalid credentials return 401 without revealing which field was wrong
- [ ] get_current_user dependency rejects missing, invalid, and expired tokens
- [ ] Plain-text passwords never appear in the database or in logs
- [ ] Unit tests cover hashing and token validation

**Area:** Backend
'@

New-SafeMedIssue -Assignee $CHIMA -Title "Add role-based access control and consent grants" -Body @'
A caregiver may only see a patient who has granted them access.

**Done when:**
- [ ] Roles PATIENT, CAREGIVER, ADMIN enforced on protected endpoints
- [ ] A patient can invite a caregiver; the caregiver accepts
- [ ] A caregiver sees a patient's data only through an ACTIVE grant
- [ ] Revoking a grant blocks access immediately; the record is retained
- [ ] Tests prove a caregiver with no grant receives 403

**Area:** Backend
'@

New-SafeMedIssue -Assignee $CHIMA -Title "Add audit log writer" -Body @'
Every meaningful action must be recorded, append-only.

**Done when:**
- [ ] Helper records actor, action, entity type, entity id, and details
- [ ] Called on medication changes, consent changes, and record access
- [ ] Nothing in the codebase updates or deletes an audit row
- [ ] Tests confirm an audit row is written for each covered action

**Area:** Backend
'@

# ----- Pacifique -----------------------------------------------------------

New-SafeMedIssue -Assignee $PACIFIQUE -Title "Scaffold React frontend" -Body @'
The frontend shell. No API calls yet - this unblocks all later UI work.

**Done when:**
- [ ] Vite + React + TypeScript project in frontend/
- [ ] React Router with routes for /login, /patient, /caregiver
- [ ] Shared layout with navigation between them
- [ ] npm run dev serves with no errors or warnings
- [ ] README note on how to start the frontend

**Area:** Frontend
'@

New-SafeMedIssue -Assignee $PACIFIQUE -Title "Build login and registration pages" -Body @'
Our users skew older, so accessibility is a requirement, not a nicety.

**Done when:**
- [ ] Login and registration forms with validation and clear error messages
- [ ] Large text and high contrast throughout
- [ ] Fully usable with the keyboard alone
- [ ] Calls are placeholders; wired to the real API once auth is merged

**Area:** Frontend
'@

New-SafeMedIssue -Assignee $PACIFIQUE -Title "Build patient dashboard shell" -Body @'
The screen a patient sees every day.

**Done when:**
- [ ] Medication list with an add-medication form
- [ ] Today's doses, each with an "I took this" button
- [ ] An area for safety findings
- [ ] Mock data for now; wired to the API when the endpoints land

**Area:** Frontend
'@

Write-Host ""
Write-Host "Done. Now open the project board and use 'Add item' to pull these in," -ForegroundColor Green
Write-Host "or check the Issues tab to confirm all 10 were created." -ForegroundColor Green
