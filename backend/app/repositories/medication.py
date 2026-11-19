"""Database queries for medications.

Why a repository layer at all: it is the only place that knows SQLAlchemy.
Endpoints call these functions and deal in plain objects, which means the
business logic can be tested without an HTTP request, and swapping how
something is queried never touches the endpoint.

Every function takes patient_id. That is deliberate - it makes it hard to
write a query that accidentally returns another patient's data, because the
owner is a required argument rather than an afterthought.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import MedicationStatus
from app.models.medication import Medication


def create(db: Session, *, patient_id: UUID, **fields) -> Medication:
    medication = Medication(patient_id=patient_id, **fields)
    db.add(medication)
    db.flush()      # assigns the id without committing
    db.refresh(medication)
    return medication


def get(db: Session, *, patient_id: UUID, medication_id: UUID) -> Medication | None:
    """Fetch one medication belonging to this patient.

    Returns None when it does not exist OR belongs to someone else. The caller
    turns both into a 404 - we never reveal that a record exists but is not
    yours, because that alone leaks information.
    """
    stmt = select(Medication).where(
        Medication.id == medication_id,
        Medication.patient_id == patient_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def list_for_patient(
    db: Session, *, patient_id: UUID, include_stopped: bool = False
) -> list[Medication]:
    stmt = select(Medication).where(Medication.patient_id == patient_id)
    if not include_stopped:
        stmt = stmt.where(Medication.status == MedicationStatus.ACTIVE)
    stmt = stmt.order_by(Medication.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def update(db: Session, *, medication: Medication, **fields) -> Medication:
    """Apply only the fields that were actually provided.

    `fields` comes from a Pydantic model dumped with exclude_unset=True, so a
    field the client omitted is absent here and is left untouched.
    """
    for key, value in fields.items():
        setattr(medication, key, value)
    db.flush()
    db.refresh(medication)
    return medication
