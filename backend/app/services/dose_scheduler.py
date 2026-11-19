r"""Dose generation and the dose state machine.

This is the engine behind the daily "I took my medication" feature.

The important design decision: we create a row for every EXPECTED dose ahead
of time, rather than only recording doses that were taken. If we only stored
confirmations, a missed dose would simply be an absence of data - and you
cannot detect, count, or alert on an absence. Generating expected doses turns
"missed" into an observable fact.

The state machine:

    SCHEDULED  the dose is in the future
        |
        v  the scheduled time arrives
    DUE        the patient should take it now
        |\
        | \  the patient confirms
        |  -> TAKEN
        | \  the patient deliberately skips
        |  -> SKIPPED
        v  the grace period elapses with no confirmation
    MISSED     the caregiver may be notified

The grace period matters. Without it, a patient who takes their pill but
forgets to tap the button is recorded as missing it, and their caregiver gets
a false alarm. Two false alarms and people stop reading the alerts entirely.
"""
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.dose import DoseEvent
from app.models.enums import DoseStatus
from app.models.medication import DoseSchedule
from app.repositories import dose as dose_repo

# Monday=0 .. Sunday=6, matching datetime.weekday()
_WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def schedule_applies_on(schedule: DoseSchedule, day: date) -> bool:
    """Does this schedule produce a dose on this calendar day?

    A daily schedule applies every day. A weekly schedule applies only on the
    days named in days_of_week. A weekly schedule with no days named is
    treated as daily rather than as never - failing towards reminding someone
    is safer than failing towards silence.
    """
    if not schedule.days_of_week:
        return True
    wanted = {d.strip().upper() for d in schedule.days_of_week.split(",") if d.strip()}
    return _WEEKDAYS[day.weekday()] in wanted


def combine(day: date, at: time) -> datetime:
    """Build a timezone-aware UTC datetime from a day and a time.

    Everything in the database is stored in UTC. Mixing naive and aware
    datetimes is one of the most common sources of off-by-hours bugs, so we
    never produce a naive one.
    """
    return datetime.combine(day, at, tzinfo=timezone.utc)


def generate_dose_events(
    db: Session,
    *,
    patient_id: UUID,
    start: date,
    days: int = 7,
) -> list[DoseEvent]:
    """Create DoseEvent rows for the next `days` days.

    Idempotent: running it twice over the same window creates nothing the
    second time. The background worker will call this on a timer, so it must
    be safe to run repeatedly - and the unique constraint on
    (schedule_id, scheduled_for) is the database-level guarantee behind it.
    """
    created: list[DoseEvent] = []
    schedules = dose_repo.active_schedules_for_patient(db, patient_id=patient_id)

    for offset in range(days):
        day = start + timedelta(days=offset)
        for schedule in schedules:
            if not schedule_applies_on(schedule, day):
                continue

            scheduled_for = combine(day, schedule.time_of_day)
            if dose_repo.event_exists(
                db, schedule_id=schedule.id, scheduled_for=scheduled_for
            ):
                continue

            event = DoseEvent(
                medication_id=schedule.medication_id,
                schedule_id=schedule.id,
                patient_id=patient_id,
                scheduled_for=scheduled_for,
                status=DoseStatus.SCHEDULED,
            )
            db.add(event)
            created.append(event)

    db.flush()
    return created


def resolve_status(event: DoseEvent, now: datetime) -> DoseStatus:
    """What status should this dose have at time `now`?

    A pure function: no database, no side effects, same answer every time for
    the same inputs. That makes the rule trivial to unit-test, which matters
    because this is the logic that decides whether a caregiver gets alerted.

    TAKEN and SKIPPED are final - once a patient has told us what happened, the
    passage of time does not change it.
    """
    if event.status in (DoseStatus.TAKEN, DoseStatus.SKIPPED):
        return event.status

    grace = timedelta(minutes=event.schedule.grace_minutes if event.schedule else 120)

    if now < event.scheduled_for:
        return DoseStatus.SCHEDULED
    if now <= event.scheduled_for + grace:
        return DoseStatus.DUE
    return DoseStatus.MISSED


def refresh_statuses(db: Session, events: list[DoseEvent], now: datetime | None = None) -> int:
    """Bring a batch of doses up to date. Returns how many changed."""
    now = now or datetime.now(timezone.utc)
    changed = 0
    for event in events:
        new_status = resolve_status(event, now)
        if new_status != event.status:
            event.status = new_status
            changed += 1
    if changed:
        db.flush()
    return changed


def confirm(db: Session, *, event: DoseEvent, user_id: UUID, now: datetime | None = None) -> DoseEvent:
    """Record that a dose was taken.

    Raises ValueError if it was already resolved; the endpoint turns that into
    a 409 Conflict. Double-tapping a button should not quietly rewrite history.
    """
    if event.status in (DoseStatus.TAKEN, DoseStatus.SKIPPED):
        raise ValueError(f"Dose is already {event.status.value}")

    event.status = DoseStatus.TAKEN
    event.confirmed_at = now or datetime.now(timezone.utc)
    event.recorded_by_id = user_id
    db.flush()
    db.refresh(event)
    return event


def skip(
    db: Session, *, event: DoseEvent, user_id: UUID, note: str | None = None,
    now: datetime | None = None,
) -> DoseEvent:
    """Record that a dose was deliberately not taken."""
    if event.status in (DoseStatus.TAKEN, DoseStatus.SKIPPED):
        raise ValueError(f"Dose is already {event.status.value}")

    event.status = DoseStatus.SKIPPED
    event.confirmed_at = now or datetime.now(timezone.utc)
    event.recorded_by_id = user_id
    event.note = note
    db.flush()
    db.refresh(event)
    return event


def adherence_rate(events: list[DoseEvent]) -> float | None:
    """Share of resolved doses that were taken, 0.0 to 1.0.

    Doses still in the future are excluded - counting them would make everyone
    look non-adherent simply for not having reached tomorrow yet. Returns None
    when nothing has resolved, because 0% and "no data" are different things
    and a caregiver must not see one presented as the other.
    """
    resolved = [e for e in events if e.status in (DoseStatus.TAKEN, DoseStatus.MISSED)]
    if not resolved:
        return None
    taken = sum(1 for e in resolved if e.status == DoseStatus.TAKEN)
    return taken / len(resolved)
