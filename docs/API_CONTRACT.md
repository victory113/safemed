# SafeMed — API Contract

**Why this file exists:** three people are building different layers at the
same time. Pacifique needs to know the shape of a medication before the
endpoint exists. Victory needs to know how to identify the current user before
authentication is written.

This document is the agreement. Build against it, not against each other's
half-finished code.

**If you need to change something here, say so in the team chat before you do.**
Changing it silently breaks someone else's work.

---

## Conventions

- Base path: **`/api/v1`**
- All request and response bodies are JSON
- All dates and times are **ISO 8601 UTC**, e.g. `2026-11-05T14:30:00Z`
- All ids are **UUID strings**
- Authentication is a bearer token: `Authorization: Bearer <token>`

### Error shape

Every error returns this shape, whatever the status code:

```json
{ "detail": "Human-readable message" }
```

| Status | Meaning |
|---|---|
| 400 | The request was malformed |
| 401 | Not signed in, or the token is invalid/expired |
| 403 | Signed in, but not allowed to touch this resource |
| 404 | Does not exist, or you are not permitted to know it exists |
| 422 | Validation failed (FastAPI's own format, includes which field) |

---

## 1. Authentication — owned by Chima

### `POST /api/v1/auth/register`

Request:
```json
{
  "email": "patient@example.com",
  "password": "at least 8 characters",
  "full_name": "Maria Santos",
  "role": "PATIENT"
}
```

`role` is `"PATIENT"` or `"CAREGIVER"`. `"ADMIN"` cannot be self-assigned.

Response `201`:
```json
{
  "id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
  "email": "patient@example.com",
  "full_name": "Maria Santos",
  "role": "PATIENT",
  "is_active": true
}
```

The password is never returned, in any response, ever.

### `POST /api/v1/auth/login`

Request:
```json
{ "email": "patient@example.com", "password": "..." }
```

Response `200`:
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

On bad credentials: `401` with `{"detail": "Incorrect email or password"}` —
the same message whether the email or the password was wrong, so the endpoint
cannot be used to discover which emails are registered.

### `GET /api/v1/auth/me`

Returns the signed-in user, same shape as register's response. `401` if the
token is missing, malformed, or expired.

### The dependency everyone else depends on

**This signature is the contract.** Victory is building endpoints against a
temporary stub with exactly this shape; when Chima's version lands, the stub is
deleted and nothing else changes.

```python
# backend/app/api/deps.py

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Return the authenticated User, or raise HTTPException(401)."""
```

Also provide:

```python
def require_role(*roles: UserRole):
    """Dependency factory: raise HTTPException(403) unless the current
    user's role is one of `roles`."""
```

---

## 2. Medications — owned by Victory

All of these require authentication. A patient only ever sees their own
medications.

### `POST /api/v1/medications`

Request:
```json
{
  "name_entered": "Metformin",
  "dose_amount": "500",
  "dose_unit": "mg",
  "ndc": "0093-1048-01",
  "notes": "Take with food",
  "started_on": "2026-10-01"
}
```

Only `name_entered` is required. Everything else may be omitted or null.

Response `201`:
```json
{
  "id": "uuid",
  "name_entered": "Metformin",
  "normalized_name": "metformin hydrochloride",
  "rxcui": "6809",
  "ndc": "0093-1048-01",
  "dose_amount": "500",
  "dose_unit": "mg",
  "notes": "Take with food",
  "status": "ACTIVE",
  "started_on": "2026-10-01",
  "stopped_on": null,
  "created_at": "2026-11-05T14:30:00Z"
}
```

`rxcui` and `normalized_name` are **nullable**. If RxNorm is unavailable or does
not recognise the name, the medication still saves with those fields null. The
frontend must handle null here — it is a normal state, not an error.

### `GET /api/v1/medications`

Query parameter `status` is optional: `ACTIVE` (default) or `ALL`.

Response `200`: an array of the object above.

### `PATCH /api/v1/medications/{id}`

Any subset of `dose_amount`, `dose_unit`, `notes`, `status`, `stopped_on`.
Returns the updated object. `404` if the medication belongs to someone else.

### `DELETE /api/v1/medications/{id}`

Does **not** delete. Sets `status` to `STOPPED` and records `stopped_on`.
Medication history is never destroyed. Returns `200` with the updated object.

---

## 3. Doses — owned by Victory

### `GET /api/v1/doses/today`

Response `200`:
```json
[
  {
    "id": "uuid",
    "medication_id": "uuid",
    "medication_name": "Metformin",
    "dose_amount": "500",
    "dose_unit": "mg",
    "scheduled_for": "2026-11-05T08:00:00Z",
    "status": "TAKEN",
    "confirmed_at": "2026-11-05T08:04:00Z"
  }
]
```

`status` is one of `SCHEDULED`, `DUE`, `TAKEN`, `MISSED`, `SKIPPED`.

### `POST /api/v1/doses/{id}/confirm`

No request body. Marks the dose `TAKEN` and sets `confirmed_at` to now.
Returns the updated dose. `409` if the dose is already `TAKEN`.

### `POST /api/v1/doses/{id}/skip`

Request: `{ "note": "optional reason" }`. Marks it `SKIPPED`.

---

## 4. Safety findings — owned by Victory (later sprint)

### `GET /api/v1/findings`

```json
[
  {
    "id": "uuid",
    "finding_type": "INTERACTION",
    "severity": "SEVERE",
    "status": "OPEN",
    "title": "Potential interaction: Warfarin and Aspirin",
    "detail": "...",
    "source_name": "DDInter",
    "source_version": "2.0",
    "recall_match": null,
    "ai_explanation": "Plain-language text, or null if unavailable",
    "detected_at": "2026-11-05T03:00:00Z",
    "medications": [{ "id": "uuid", "name": "Warfarin" }]
  }
]
```

`ai_explanation` is **nullable**. When null, show `detail` and the source. The
UI must never depend on the AI explanation being present.

---

## 5. Frontend types — owned by Pacifique

Put these in `frontend/src/api/types.ts` so every component uses one definition:

```ts
export type UserRole = "PATIENT" | "CAREGIVER" | "ADMIN";
export type MedicationStatus = "ACTIVE" | "STOPPED";
export type DoseStatus = "SCHEDULED" | "DUE" | "TAKEN" | "MISSED" | "SKIPPED";
export type Severity = "MILD" | "MODERATE" | "SEVERE";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
}

export interface Medication {
  id: string;
  name_entered: string;
  normalized_name: string | null;
  rxcui: string | null;
  ndc: string | null;
  dose_amount: string | null;
  dose_unit: string | null;
  notes: string | null;
  status: MedicationStatus;
  started_on: string | null;
  stopped_on: string | null;
  created_at: string;
}

export interface Dose {
  id: string;
  medication_id: string;
  medication_name: string;
  dose_amount: string | null;
  dose_unit: string | null;
  scheduled_for: string;
  status: DoseStatus;
  confirmed_at: string | null;
}
```

Note every `| null`. Those are not laziness — each one is a real state the
backend can return, usually because an external service was unavailable.

---

## Who owns which files

Stay inside your own list. If you need a change in someone else's, ask them.

| Owner | Files |
|---|---|
| **Victory** | `backend/app/models/`, `backend/app/services/`, `backend/app/api/v1/medications.py`, `backend/app/api/v1/doses.py`, `frontend/src/components/`, `frontend/src/styles/`, `frontend/src/pages/PatientDashboard.tsx` |
| **Chima** | `backend/app/core/security.py`, `backend/app/api/v1/auth.py`, `backend/app/api/deps.py`, `backend/app/services/audit.py`, `backend/app/api/v1/consent.py` |
| **Pacifique** | `frontend/src/api/`, `frontend/src/pages/Login.tsx`, `frontend/src/pages/Register.tsx`, `frontend/src/routes.tsx`, `frontend/src/pages/CaregiverDashboard.tsx` |

Shared files that need a heads-up in chat before editing:
`backend/app/main.py`, `frontend/src/App.tsx`, `docker-compose.yml`,
`backend/requirements.txt`, `frontend/package.json`.
