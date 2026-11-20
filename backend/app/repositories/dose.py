"""Database queries for dose schedules and dose events."""
from datetime import datetime, time
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
        .options(joinedload(DoseEvent.medication), joinedload(DoseEvent.schedule))
    )
    return db.execute(stmt).scalar_one_or_none()


def events_between(
    db: Session, *, patient_id: UUID, start: datetime, end: datetime
) -> list[DoseEvent]:
    """All expected doses in a window, earliest first, then by medication name.

    The second sort key is not cosmetic. A patient taking four medications at
    08:00 has four rows with an identical `scheduled_for`, and ordering by that
    column alone leaves ties to whatever order the database happens to return
    - which changes between queries. On screen that means the list reshuffles
    every time a dose is confirmed, so the row you just tapped jumps somewhere
    else. Breaking the tie by name makes the order stable.

    The explicit join exists only to make Medication.name_entered available to
    ORDER BY; the joinedload still does the loading.
    """
    stmt = (
        select(DoseEvent)
        .join(Medication, DoseEvent.medication_id == Medication.id)
        .where(
            DoseEvent.patient_id == patient_id,
            DoseEvent.scheduled_for >= start,
            DoseEvent.scheduled_for < end,
        )
        .options(joinedload(DoseEvent.medication), joinedload(DoseEvent.schedule))
        .order_by(DoseEvent.scheduled_for.asc(), Medication.name_entered.asc())
    )
    return list(db.execute(stmt).scalars().all())


def event_exists(db: Session, *, schedule_id: UUID, scheduled_for: datetime) -> bool:
    """Used to keep dose generation idempotent."""
    stmt = select(DoseEvent.id).where(
        DoseEvent.schedule_id == schedule_id,
        DoseEvent.scheduled_for == scheduled_for,
    )
    return db.execute(stmt).first() is not None


def schedules_for_medication(
    db: Session, *, medication_id: UUID, include_inactive: bool = False
) -> list[DoseSchedule]:
    stmt = select(DoseSchedule).where(DoseSchedule.medication_id == medication_id)
    if not include_inactive:
        stmt = stmt.where(DoseSchedule.is_active.is_(True))
    return list(db.execute(stmt.order_by(DoseSchedule.time_of_day.asc())).scalars().all())


def get_schedule(
    db: Session, *, patient_id: UUID, schedule_id: UUID
) -> DoseSchedule | None:
    """Fetch one schedule, but only through its owning patient.

    The join on Medication is what enforces ownership. Looking a schedule up
    by id alone would let anyone who guessed an id edit someone else's.
    """
    stmt = (
        select(DoseSchedule)
        .join(Medication)
        .where(DoseSchedule.id == schedule_id, Medication.patient_id == patient_id)
    )
    return db.execute(stmt).scalar_one_or_none()


def schedule_exists_at(
    db: Session, *, medication_id: UUID, time_of_day: time
) -> bool:
    """Is there already an active schedule for this medication at this time?

    Used to stop a patient accidentally creating two reminders for one pill.
    """
    stmt = select(DoseSchedule.id).where(
        DoseSchedule.medication_id == medication_id,
        DoseSchedule.time_of_day == time_of_day,
        DoseSchedule.is_active.is_(True),
    )
    return db.execute(stmt).first() is not None
