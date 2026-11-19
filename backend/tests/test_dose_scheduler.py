"""Tests for dose generation and the dose state machine.

These are the rules that decide whether a caregiver is alerted, so they get
tested more carefully than anything else in this layer.
"""
from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.models.dose import DoseEvent
from app.models.enums import DoseStatus, Frequency, MedicationStatus
from app.models.medication import DoseSchedule, Medication
from app.services import dose_scheduler as svc


@pytest.fixture
def medication(db, patient):
    med = Medication(
        patient_id=patient.id,
        name_entered="Metformin",
        dose_amount="500",
        dose_unit="mg",
        status=MedicationStatus.ACTIVE,
    )
    db.add(med)
    db.flush()
    return med


@pytest.fixture
def daily_schedule(db, medication):
    schedule = DoseSchedule(
        medication_id=medication.id,
        time_of_day=time(8, 0),
        frequency=Frequency.DAILY,
        grace_minutes=120,
    )
    db.add(schedule)
    db.flush()
    return schedule


# ----------------------------------------------------------- generation ----

def test_generates_one_event_per_day(db, patient, daily_schedule):
    created = svc.generate_dose_events(
        db, patient_id=patient.id, start=date(2026, 11, 10), days=7
    )
    assert len(created) == 7
    assert all(e.status == DoseStatus.SCHEDULED for e in created)


def test_generation_is_idempotent(db, patient, daily_schedule):
    """Running it twice must not create duplicates.

    The background worker runs on a timer, so this is not a theoretical
    concern - it will happen on every single run.
    """
    svc.generate_dose_events(db, patient_id=patient.id, start=date(2026, 11, 10), days=3)
    second = svc.generate_dose_events(db, patient_id=patient.id, start=date(2026, 11, 10), days=3)
    assert second == []


def test_weekly_schedule_only_on_named_days(db, patient, medication):
    db.add(
        DoseSchedule(
            medication_id=medication.id,
            time_of_day=time(9, 0),
            frequency=Frequency.WEEKLY,
            days_of_week="MON,WED,FRI",
        )
    )
    db.flush()
    # 2026-11-09 is a Monday, so a 7-day window holds Mon, Wed, Fri.
    created = svc.generate_dose_events(
        db, patient_id=patient.id, start=date(2026, 11, 9), days=7
    )
    assert len(created) == 3


def test_weekly_with_no_days_is_treated_as_daily(db, patient, medication):
    """Failing towards reminding someone is safer than failing silent."""
    db.add(
        DoseSchedule(
            medication_id=medication.id,
            time_of_day=time(9, 0),
            frequency=Frequency.WEEKLY,
            days_of_week=None,
        )
    )
    db.flush()
    created = svc.generate_dose_events(
        db, patient_id=patient.id, start=date(2026, 11, 9), days=4
    )
    assert len(created) == 4


# -------------------------------------------------------- state machine ----

def _event(schedule, scheduled_for, status=DoseStatus.SCHEDULED):
    event = DoseEvent(
        medication_id=schedule.medication_id,
        schedule_id=schedule.id,
        patient_id=schedule.medication.patient_id,
        scheduled_for=scheduled_for,
        status=status,
    )
    event.schedule = schedule
    return event


def test_future_dose_is_scheduled(db, daily_schedule):
    at = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)
    event = _event(daily_schedule, at)
    assert svc.resolve_status(event, at - timedelta(hours=1)) == DoseStatus.SCHEDULED


def test_dose_becomes_due_at_its_time(db, daily_schedule):
    at = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)
    event = _event(daily_schedule, at)
    assert svc.resolve_status(event, at) == DoseStatus.DUE


def test_dose_stays_due_inside_the_grace_period(db, daily_schedule):
    """The point of the grace period: a patient who takes their pill but taps
    late must not be reported as missing it."""
    at = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)
    event = _event(daily_schedule, at)
    assert svc.resolve_status(event, at + timedelta(minutes=119)) == DoseStatus.DUE


def test_dose_is_missed_after_the_grace_period(db, daily_schedule):
    at = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)
    event = _event(daily_schedule, at)
    assert svc.resolve_status(event, at + timedelta(minutes=121)) == DoseStatus.MISSED


def test_taken_is_final(db, daily_schedule):
    at = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)
    event = _event(daily_schedule, at, status=DoseStatus.TAKEN)
    assert svc.resolve_status(event, at + timedelta(days=3)) == DoseStatus.TAKEN


# ------------------------------------------------------------ confirm ------

def test_confirm_marks_taken(db, patient, daily_schedule):
    at = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)
    event = _event(daily_schedule, at)
    db.add(event)
    db.flush()

    confirmed = svc.confirm(db, event=event, user_id=patient.id, now=at + timedelta(minutes=4))
    assert confirmed.status == DoseStatus.TAKEN
    assert confirmed.confirmed_at == at + timedelta(minutes=4)
    assert confirmed.recorded_by_id == patient.id


def test_confirming_twice_is_rejected(db, patient, daily_schedule):
    at = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)
    event = _event(daily_schedule, at)
    db.add(event)
    db.flush()

    svc.confirm(db, event=event, user_id=patient.id, now=at)
    with pytest.raises(ValueError):
        svc.confirm(db, event=event, user_id=patient.id, now=at)


# ---------------------------------------------------------- adherence ------

def test_adherence_ignores_future_doses(db, daily_schedule):
    at = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)
    events = [
        _event(daily_schedule, at, DoseStatus.TAKEN),
        _event(daily_schedule, at, DoseStatus.MISSED),
        _event(daily_schedule, at, DoseStatus.SCHEDULED),
    ]
    assert svc.adherence_rate(events) == 0.5


def test_adherence_is_none_with_no_resolved_doses(db, daily_schedule):
    """No data is not the same as 0%, and a caregiver must never see one
    presented as the other."""
    at = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)
    events = [_event(daily_schedule, at, DoseStatus.SCHEDULED)]
    assert svc.adherence_rate(events) is None
