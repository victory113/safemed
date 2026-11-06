"""Database queries for dose schedules and dose events."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.dose import DoseEvent
from app.models.medication import DoseSchedule, Medication


def active_schedules_for_patient(db: Session, *, patient_id: UUID) -> list[DoseSchedule]:
    stmt = (
        select(DoseSchedule)
        .join(Medication)
        .where(
            Medication.patient_id == patient_id,
            DoseSchedule.is_active.is_(True),
        )
        .options(joinedload(DoseSchedule.medication))
    )
    return list(db.execute(stmt).scalars().all())


def get_event(db: Session, *, patient_id: UUID, dose_id: UUID) -> DoseEvent | None:
    stmt = (
        select(DoseEvent)
        .where(DoseEvent.id == dose_id, DoseEvent.patient_id == patient_id)
        .options(joinedload(DoseEvent.medication))
    )
    return db.execute(stmt).scalar_one_or_none()


def events_between(
    db: Session, *, patient_id: UUID, start: datetime, end: datetime
) -> list[DoseEvent]:
    """All expected doses in a window, earliest first."""
    stmt = (
        select(DoseEvent)
        .where(
            DoseEvent.patient_id == patient_id,
            DoseEvent.scheduled_for >= start,
            DoseEvent.scheduled_for < end,
        )
        .options(joinedload(DoseEvent.medication))
        .order_by(DoseEvent.scheduled_for.asc())
    )
    return list(db.execute(stmt).scalars().all())


def event_exists(db: Session, *, schedule_id: UUID, scheduled_for: datetime) -> bool:
    """Used to keep dose generation idempotent."""
    stmt = select(DoseEvent.id).where(
        DoseEvent.schedule_id == schedule_id,
        DoseEvent.scheduled_for == scheduled_for,
    )
    return db.execute(stmt).first() is not None
