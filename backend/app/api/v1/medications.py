"""Medication endpoints.

The HTTP layer only: validate input, call a repository or service, shape the
response. No business logic lives here - that keeps it testable without an
HTTP request and keeps this file short enough to read in one go.

Shapes follow docs/API_CONTRACT.md section 2.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.enums import MedicationStatus
from app.models.user import User
from app.models.medication import DoseSchedule
from app.repositories import dose as dose_repo
from app.repositories import medication as repo
from app.schemas.dose import DoseScheduleCreate, DoseScheduleRead
from app.schemas.medication import MedicationCreate, MedicationRead, MedicationUpdate
from app.services.rxnorm import normalize_medication_name
from app.services.safety_engine import SafetyEngine

router = APIRouter(prefix="/medications", tags=["medications"])


@router.post("", response_model=MedicationRead, status_code=status.HTTP_201_CREATED)
def create_medication(
    payload: MedicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a medication, schedule it, normalise it, then re-check for safety.

    Note the order. The medication is saved FIRST, and normalisation is
    allowed to fail. RxNorm being slow or down must never stop a patient
    recording something they are actually taking.
    """
    fields = payload.model_dump(exclude_unset=True)
    # These two describe when the medication is taken, which belongs to
    # DoseSchedule. They must not reach the Medication constructor.
    times = fields.pop("times", [])
    grace_minutes = fields.pop("grace_minutes", 120)

    medication = repo.create(db, patient_id=current_user.id, **fields)

    for at in times:
        db.add(
            DoseSchedule(
                medication_id=medication.id,
                time_of_day=at,
                grace_minutes=grace_minutes,
            )
        )
    if times:
        db.flush()

    result = normalize_medication_name(medication.name_entered)
    if result.found:
        repo.update(
            db,
            medication=medication,
            rxcui=result.rxcui,
            normalized_name=result.normalized_name,
        )

    # A new medication changes the picture, so re-evaluate the whole list.
    SafetyEngine(db).evaluate_patient(current_user.id)

    db.commit()
    db.refresh(medication)
    return medication


@router.get("", response_model=list[MedicationRead])
def list_medications(
    status_filter: str = Query("ACTIVE", alias="status", pattern="^(ACTIVE|ALL)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return repo.list_for_patient(
        db, patient_id=current_user.id, include_stopped=(status_filter == "ALL")
    )


@router.patch("/{medication_id}", response_model=MedicationRead)
def update_medication(
    medication_id: UUID,
    payload: MedicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    medication = repo.get(db, patient_id=current_user.id, medication_id=medication_id)
    if medication is None:
        # 404 rather than 403 even when it exists but belongs to someone else.
        # Confirming that a record exists is itself a disclosure.
        raise HTTPException(status_code=404, detail="Medication not found")

    repo.update(db, medication=medication, **payload.model_dump(exclude_unset=True))
    SafetyEngine(db).evaluate_patient(current_user.id)
    db.commit()
    db.refresh(medication)
    return medication


@router.delete("/{medication_id}", response_model=MedicationRead)
def stop_medication(
    medication_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stop a medication. Deliberately NOT a delete.

    Medication history is never destroyed - the record stays, marked stopped.
    """
    from datetime import date

    medication = repo.get(db, patient_id=current_user.id, medication_id=medication_id)
    if medication is None:
        raise HTTPException(status_code=404, detail="Medication not found")

    repo.update(
        db,
        medication=medication,
        status=MedicationStatus.STOPPED,
        stopped_on=date.today(),
    )
    db.commit()
    db.refresh(medication)
    return medication


# ---- Schedules -------------------------------------------------------------
#
# A schedule is "take this at 08:00". It is what the daily check-in is built
# from: dose events are generated from schedules, so a medication with no
# schedule produces nothing to confirm.


@router.get("/{medication_id}/schedules", response_model=list[DoseScheduleRead])
def list_schedules(
    medication_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    medication = repo.get(db, patient_id=current_user.id, medication_id=medication_id)
    if medication is None:
        raise HTTPException(status_code=404, detail="Medication not found")
    return dose_repo.schedules_for_medication(db, medication_id=medication.id)


@router.post(
    "/{medication_id}/schedules",
    response_model=DoseScheduleRead,
    status_code=status.HTTP_201_CREATED,
)
def add_schedule(
    medication_id: UUID,
    payload: DoseScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a time of day to an existing medication."""
    medication = repo.get(db, patient_id=current_user.id, medication_id=medication_id)
    if medication is None:
        raise HTTPException(status_code=404, detail="Medication not found")

    if dose_repo.schedule_exists_at(
        db, medication_id=medication.id, time_of_day=payload.time_of_day
    ):
        # 409, not 400: the request is well formed, it just conflicts with
        # what is already there. Two schedules at one time would ask the
        # patient to confirm the same pill twice.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This medication is already scheduled at that time",
        )

    schedule = DoseSchedule(medication_id=medication.id, **payload.model_dump())
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.delete("/{medication_id}/schedules/{schedule_id}", response_model=DoseScheduleRead)
def remove_schedule(
    medication_id: UUID,
    schedule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stop generating doses at this time.

    Deactivates rather than deletes, for the same reason stopping a medication
    does not delete it: the doses already logged against this schedule are
    part of the patient's history, and deleting the row would orphan them.
    """
    schedule = dose_repo.get_schedule(
        db, patient_id=current_user.id, schedule_id=schedule_id
    )
    if schedule is None or schedule.medication_id != medication_id:
        raise HTTPException(status_code=404, detail="Schedule not found")

    schedule.is_active = False
    db.commit()
    db.refresh(schedule)
    return schedule
