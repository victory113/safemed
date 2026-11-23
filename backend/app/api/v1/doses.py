"""Dose logging endpoints - the daily "I took my medication" feature."""
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.enums import DoseStatus
from app.models.user import User
from app.repositories import dose as dose_repo
from app.schemas.dose import AdherenceRead, DoseRead, DoseSkip
from app.services import dose_scheduler as scheduler

router = APIRouter(prefix="/doses", tags=["doses"])


def _to_read(event) -> DoseRead:
    """Flatten the medication details onto the dose so the UI can render a row
    without a second request."""
    return DoseRead(
        id=event.id,
        medication_id=event.medication_id,
        medication_name=event.medication.name_entered,
        dose_amount=event.medication.dose_amount,
        dose_unit=event.medication.dose_unit,
        scheduled_for=event.scheduled_for,
        status=event.status,
        confirmed_at=event.confirmed_at,
    )


@router.get("/today", response_model=list[DoseRead])
def doses_today(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Today's expected doses, with their statuses brought up to date.

    Statuses are recalculated on read rather than only by the background
    worker, so the screen is correct the instant a patient opens it instead of
    waiting for the next scheduled run.
    """
    today = date.today()
    start = datetime.combine(today, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    # Make sure rows exist for today before reading them.
    scheduler.generate_dose_events(db, patient_id=current_user.id, start=today, days=1)

    events = dose_repo.events_between(
        db, patient_id=current_user.id, start=start, end=end
    )
    scheduler.refresh_statuses(db, events)
    db.commit()

    return [_to_read(e) for e in events]


@router.post("/{dose_id}/confirm", response_model=DoseRead)
def confirm_dose(
    dose_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = dose_repo.get_event(db, patient_id=current_user.id, dose_id=dose_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Dose not found")

    try:
        scheduler.confirm(db, event=event, user_id=current_user.id)
    except ValueError as exc:
        # Already taken or skipped. 409 Conflict, not 400 - the request was
        # well formed, it just conflicts with the current state.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None

    db.commit()
    db.refresh(event)
    return _to_read(event)


@router.post("/{dose_id}/skip", response_model=DoseRead)
def skip_dose(
    dose_id: UUID,
    payload: DoseSkip,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = dose_repo.get_event(db, patient_id=current_user.id, dose_id=dose_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Dose not found")

    try:
        scheduler.skip(db, event=event, user_id=current_user.id, note=payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None

    db.commit()
    db.refresh(event)
    return _to_read(event)


@router.get("/history", response_model=list[DoseRead])
def dose_history(
    days: int = Query(7, ge=1, le=90, description="How many days back to look."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recent doses, oldest first, with statuses brought up to date.

    Read-only: unlike /today this does not generate missing rows. Inventing
    history for days that have already passed would manufacture missed doses
    the patient was never actually asked about.
    """
    end = datetime.combine(date.today() + timedelta(days=1), time.min, tzinfo=timezone.utc)
    start = end - timedelta(days=days)

    events = dose_repo.events_between(db, patient_id=current_user.id, start=start, end=end)
    scheduler.refresh_statuses(db, events)
    db.commit()

    return [_to_read(e) for e in events]


@router.get("/adherence", response_model=AdherenceRead)
def adherence(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """How reliably this patient has taken their medication recently.

    The counts are returned alongside the rate on purpose. "80%" means
    something very different over 5 doses than over 500, and a caregiver
    deciding whether to worry needs the denominator.
    """
    end = datetime.combine(date.today() + timedelta(days=1), time.min, tzinfo=timezone.utc)
    start = end - timedelta(days=days)

    events = dose_repo.events_between(db, patient_id=current_user.id, start=start, end=end)
    scheduler.refresh_statuses(db, events)
    db.commit()

    counts = Counter(e.status for e in events)
    taken = counts[DoseStatus.TAKEN]
    missed = counts[DoseStatus.MISSED]

    return AdherenceRead(
        days=days,
        taken=taken,
        missed=missed,
        skipped=counts[DoseStatus.SKIPPED],
        scheduled=counts[DoseStatus.SCHEDULED] + counts[DoseStatus.DUE],
        resolved=taken + missed,
        rate=scheduler.adherence_rate(events),
    )
