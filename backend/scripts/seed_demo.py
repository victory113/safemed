"""Build the demonstration dataset.

    docker compose exec api python -m scripts.seed_demo

Creates Maria Santos (patient) and her daughter Elena (caregiver), with a
medication list chosen so that every part of the system has something real to
show. Runs the safety engine at the end.

All data is synthetic. No real patient information is used anywhere in this
project.

The script is idempotent: running it again resets Maria's data and rebuilds
it, so a rehearsal never leaves the demo in a half-used state.

WHY THESE PARTICULAR MEDICATIONS
--------------------------------
Each one earns its place:

  aspirin    + warfarin   -> a Major interaction, and the one that proves
                             RXCUI matching works: DDInter calls aspirin
                             "Acetylsalicylic acid", so name matching finds
                             nothing here.
  ibuprofen              -> interacts with both of the above, so the list
                             produces several findings rather than one.
  metformin (Cardinal)   -> NDC 0310-6225 matches a real FDA recall, giving a
                             CONFIRMED match.
  lisinopril (Sandoz)    -> a different manufacturer's NDC, so a metformin
                             recall does NOT produce a CONFIRMED match
                             against it. The false alarm we prevent.

A note on volume: five medications produce around ten interaction findings.
That is not a bug and it is worth saying out loud in the demo - it is exactly
why severity routing exists. Only the SEVERE ones reach a caregiver; the rest
stay on the patient's own profile. A system that escalated all ten would be
ignored within a week.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, func, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.dose import DoseEvent
from app.models.enums import (
    ConsentStatus,
    DoseStatus,
    MedicationStatus,
    UserRole,
)
from app.models.interaction import DrugInteraction
from app.models.medication import DoseSchedule, Medication
from app.models.safety import SafetyFinding, finding_medications
from app.models.user import ConsentGrant, User
from app.services.audit import AuditAction, record_event
from app.services.rxnorm import normalize_medication_name
from app.services.safety_engine import SafetyEngine

PATIENT_EMAIL = "maria@safemed.demo"
CAREGIVER_EMAIL = "elena@safemed.demo"
PASSWORD = "demo-password-123"

MEDICATIONS = [
    # name,        dose,   unit, ndc,              times
    ("Aspirin",    "81",   "mg", None,             [time(8, 0)]),
    ("Warfarin",   "5",    "mg", None,             [time(20, 0)]),
    ("Ibuprofen",  "200",  "mg", None,             [time(8, 0), time(20, 0)]),
    # Cardinal Health's product - matches FDA recall D-0435-2021.
    ("Metformin",  "500",  "mg", "0310-6225-30",   [time(8, 0), time(20, 0)]),
    ("Lisinopril", "10",   "mg", "0378-0021-01",   [time(8, 0)]),
]


def wipe(db, patient: User) -> None:
    """Remove everything belonging to this patient, in dependency order."""
    med_ids = db.execute(
        select(Medication.id).where(Medication.patient_id == patient.id)
    ).scalars().all()
    finding_ids = db.execute(
        select(SafetyFinding.id).where(SafetyFinding.patient_id == patient.id)
    ).scalars().all()

    if finding_ids:
        db.execute(
            delete(finding_medications).where(
                finding_medications.c.finding_id.in_(finding_ids)
            )
        )
    db.execute(delete(SafetyFinding).where(SafetyFinding.patient_id == patient.id))
    db.execute(delete(DoseEvent).where(DoseEvent.patient_id == patient.id))
    if med_ids:
        db.execute(delete(DoseSchedule).where(DoseSchedule.medication_id.in_(med_ids)))
    db.execute(delete(Medication).where(Medication.patient_id == patient.id))
    db.flush()


def get_or_create_user(db, email: str, name: str, role: UserRole) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            hashed_password=hash_password(PASSWORD),
            full_name=name,
            role=role,
        )
        db.add(user)
        db.flush()
    return user


def build_dose_history(db, patient: User, days_back: int = 7) -> dict:
    """Create a believable week of dose history.

    Not a perfect record - a patient who never misses a dose makes the
    adherence feature look pointless. Evening doses are missed more often than
    morning ones, which is also what happens in reality.
    """
    now = datetime.now(timezone.utc)
    taken = missed = 0

    schedules = db.execute(
        select(DoseSchedule)
        .join(Medication)
        .where(Medication.patient_id == patient.id)
    ).scalars().all()

    for offset in range(days_back, 0, -1):
        day = date.today() - timedelta(days=offset)
        for schedule in schedules:
            scheduled_for = datetime.combine(day, schedule.time_of_day, tzinfo=timezone.utc)
            if scheduled_for > now:
                continue

            evening = schedule.time_of_day.hour >= 18
            # A deterministic pattern, so every rehearsal looks the same.
            skip = evening and (offset % 3 == 0)

            event = DoseEvent(
                medication_id=schedule.medication_id,
                schedule_id=schedule.id,
                patient_id=patient.id,
                scheduled_for=scheduled_for,
                status=DoseStatus.MISSED if skip else DoseStatus.TAKEN,
                confirmed_at=None if skip else scheduled_for + timedelta(minutes=4),
                recorded_by_id=None if skip else patient.id,
            )
            db.add(event)
            missed += 1 if skip else 0
            taken += 0 if skip else 1

    db.flush()
    return {"taken": taken, "missed": missed}


def require_interaction_data(db) -> int:
    """Refuse to seed into an empty interaction dataset.

    Without this check the seed succeeds, the safety engine runs, and it
    correctly reports no interactions - because there is nothing to compare
    against. The dashboard then shows "No safety concerns found", which is
    indistinguishable from a working system that happens to have good news.

    That is the same false negative this project's own report is about
    (FINAL_REPORT.md section 9.1), one layer out: an empty result must never
    be allowed to look like a clean result. So we stop here and say why,
    rather than producing a patient whose safety screen is reassuringly blank.
    """
    rows = db.scalar(select(func.count()).select_from(DrugInteraction)) or 0
    if rows == 0:
        print()
        print("  STOPPING: the drug_interactions table is empty.")
        print()
        print("  Nothing has been changed. The safety engine would run and find")
        print("  no interactions - not because Maria's medications are safe, but")
        print("  because there is no dataset to check them against.")
        print()
        print("  Load it first, then seed again:")
        print("    docker compose exec api python -m scripts.import_ddinter")
        print()
        print("  That takes a few minutes and ends with 160,235 interactions.")
        return 0
    print(f"  dataset   : {rows:,} interactions loaded")
    return rows


def main() -> int:
    print("SafeMed demo seed")
    print("=" * 60)

    with SessionLocal() as db:
        if require_interaction_data(db) == 0:
            return 1

        patient = get_or_create_user(db, PATIENT_EMAIL, "Maria Santos", UserRole.PATIENT)
        caregiver = get_or_create_user(db, CAREGIVER_EMAIL, "Elena Santos", UserRole.CAREGIVER)
        print(f"  patient   : {patient.full_name} <{patient.email}>")
        print(f"  caregiver : {caregiver.full_name} <{caregiver.email}>")

        wipe(db, patient)

        # Consent: Elena may see Maria's data. Without this grant she sees
        # nothing, which is the point of the consent model.
        grant = db.execute(
            select(ConsentGrant).where(
                ConsentGrant.patient_id == patient.id,
                ConsentGrant.caregiver_id == caregiver.id,
            )
        ).scalar_one_or_none()
        if grant is None:
            grant = ConsentGrant(patient_id=patient.id, caregiver_id=caregiver.id)
            db.add(grant)
        grant.status = ConsentStatus.ACTIVE
        grant.granted_at = datetime.now(timezone.utc)
        grant.revoked_at = None
        db.flush()

        # The seed writes the grant straight into the database rather than
        # going through the API, so the audit rows those endpoints would have
        # written do not exist. Write them here, because the demo reads the
        # audit log out loud and a history that starts mid-story is a
        # misleading history. These describe actions that genuinely happened,
        # just not over HTTP.
        record_event(
            db,
            action=AuditAction.CONSENT_INVITED,
            entity_type="consent_grant",
            entity_id=grant.id,
            actor_id=patient.id,
            patient_id=patient.id,
            details={"caregiver_id": str(caregiver.id), "source": "seed_demo"},
        )
        record_event(
            db,
            action=AuditAction.CONSENT_ACCEPTED,
            entity_type="consent_grant",
            entity_id=grant.id,
            actor_id=caregiver.id,
            patient_id=patient.id,
            details={"caregiver_id": str(caregiver.id), "source": "seed_demo"},
        )
        print("  consent   : active")

        print("\n  medications (normalising via RxNorm):")
        for name, amount, unit, ndc, times in MEDICATIONS:
            medication = Medication(
                patient_id=patient.id,
                name_entered=name,
                dose_amount=amount,
                dose_unit=unit,
                ndc=ndc,
                status=MedicationStatus.ACTIVE,
                started_on=date.today() - timedelta(days=90),
            )
            db.add(medication)
            db.flush()

            result = normalize_medication_name(name)
            if result.found:
                medication.rxcui = result.rxcui
                medication.normalized_name = result.normalized_name

            for at in times:
                db.add(
                    DoseSchedule(
                        medication_id=medication.id,
                        time_of_day=at,
                        grace_minutes=120,
                    )
                )
            db.flush()
            rx = medication.rxcui or "-"
            print(f"    {name:<12} {amount:>4} {unit:<3} rxcui={rx:<8} ndc={ndc or '-'}")

        history = build_dose_history(db, patient)
        total = history["taken"] + history["missed"]
        rate = history["taken"] / total * 100 if total else 0
        print(f"\n  dose history: {history['taken']} taken, {history['missed']} missed "
              f"({rate:.0f}% adherence)")

        print("\n  running the safety engine ...")
        result = SafetyEngine(db).evaluate_patient(patient.id)
        db.commit()

        for finding in sorted(result.created, key=lambda f: f.severity.value):
            meds = ", ".join(m.name_entered for m in finding.medications)
            print(f"    [{finding.severity.value:<8}] {finding.title}")
            print(f"               involves: {meds}")

        print(f"\n  {len(result.created)} findings created")

    print("=" * 60)
    print("Sign in as:")
    print(f"  patient   {PATIENT_EMAIL} / {PASSWORD}")
    print(f"  caregiver {CAREGIVER_EMAIL} / {PASSWORD}")
    print()
    print("For the recall part of the demo, run:")
    print("  docker compose exec api python -c \\")
    print("    \"from app.workers.tasks import simulate_recall;"
          " print(simulate_recall.delay('metformin').get(timeout=120))\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
