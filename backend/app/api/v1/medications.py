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
from app.repositories import medication as repo
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
    """Add a medication, normalise it, then re-check the patient for safety.

    Note the order. The medication is saved FIRST, and normalisation is
    allowed to fail. RxNorm being slow or down must never stop a patient
    recording something they are actually taking.
    """
    medication = repo.create(
        db, patient_id=current_user.id, **payload.model_dump(exclude_unset=True)
    )

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
