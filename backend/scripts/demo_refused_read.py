"""Make a revoked caregiver attempt to read a patient record, for the demo.

Run it inside the API container, after the patient has revoked access:

    docker compose exec api python -m scripts.demo_refused_read

WHY THIS EXISTS
---------------
Beat 7b of the demo shows that the audit log records refused attempts, not
only successful ones. Producing a refusal through the browser turns out to be
impossible: the caregiver dashboard asks "who am I linked to?" first, gets an
empty list once access is revoked, and therefore never requests the record at
all. No request, no refusal, no row.

That is correct behaviour and it makes the point harder to demonstrate, not
easier. So ask the API directly, which is where the boundary actually lives.
A browser is one client; the authorization check does not depend on it.

What this proves, in the order it prints:

1. The caregiver can still authenticate. Revoking consent is not the same as
   disabling an account, and conflating the two would hide what is being
   tested.
2. The record request is refused with 403.
3. A request for a patient id that does not exist is refused identically.
   Same status, same body - the API does not reveal which patients are real.
4. Both attempts are now in the audit log with patient_id NULL.
"""
from __future__ import annotations

import sys
from uuid import uuid4

import httpx
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.user import User

BASE = "http://localhost:8000/api/v1"
CAREGIVER = "elena@safemed.demo"
PATIENT = "maria@safemed.demo"
PASSWORD = "demo-password-123"


def main() -> int:
    with SessionLocal() as db:
        patient = db.execute(
            select(User).where(User.email == PATIENT)
        ).scalar_one_or_none()
    if patient is None:
        print(f"No {PATIENT}. Run scripts.seed_demo first.")
        return 1

    with httpx.Client(base_url=BASE, timeout=10.0) as client:
        login = client.post(
            "/auth/login", json={"email": CAREGIVER, "password": PASSWORD}
        )
        if login.status_code != 200:
            print(f"Could not sign in as {CAREGIVER}: {login.status_code}")
            return 1
        token = login.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}

        print(f"  signed in as {CAREGIVER}              {login.status_code}")

        real = client.get(f"/caregiver/patients/{patient.id}/findings", headers=auth)
        print(f"  GET her patient's findings            {real.status_code}  {real.text.strip()[:60]}")

        fake = client.get(f"/caregiver/patients/{uuid4()}/findings", headers=auth)
        print(f"  GET a patient that does not exist     {fake.status_code}  {fake.text.strip()[:60]}")

    print()
    if real.status_code == 403 and real.text == fake.text:
        print("  Identical responses: the refusal does not confirm who exists.")
    else:
        print("  WARNING: the two responses differ. That is an information leak.")

    print()
    print("  Now look at the log:")
    print('    docker compose exec db psql -U safemed -d safemed -c \\')
    print('      "SELECT action, patient_id, created_at FROM audit_events '
          'ORDER BY created_at DESC LIMIT 8;"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
