"""Tests for the dose repository's queries.

The ordering test here is a regression test. The dashboard reshuffled its rows
every time a dose was confirmed, because four medications taken at 08:00 share
one `scheduled_for` value and the query left ties to the database. The row a
patient had just tapped would jump somewhere else in the list.
"""
from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.models.dose import DoseEvent
from app.models.enums import DoseStatus, MedicationStatus
from app.models.medication import DoseSchedule, Medication
from app.repositories import dose as repo

TODAY = date.today()


def add_medication(db, patient, name: str) -> Medication:
    med = Medication(
        patient_id=patient.id, name_entered=name, status=MedicationStatus.ACTIVE
    )
    db.add(med)
    db.flush()
    return med


def add_dose(db, patient, medication, at: time) -> DoseEvent:
    schedule = DoseSchedule(medication_id=medication.id, time_of_day=at, grace_minutes=120)
    db.add(schedule)
    db.flush()

    event = DoseEvent(
        medication_id=medication.id,
        schedule_id=schedule.id,
        patient_id=patient.id,
        scheduled_for=datetime.combine(TODAY, at, tzinfo=timezone.utc),
        status=DoseStatus.SCHEDULED,
    )
    db.add(event)
    db.flush()
    return event


@pytest.fixture
def window() -> tuple[datetime, datetime]:
    start = datetime.combine(TODAY, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def test_doses_at_the_same_time_come_back_in_a_stable_order(db, patient, window):
    """Four medications at 08:00 must always come back in the same order.

    They are inserted in an order that is deliberately not alphabetical, so a
    query that simply returned insertion order would fail this.
    """
    start, end = window
    for name in ("Warfarin", "Aspirin", "Metformin", "Ibuprofen"):
        add_dose(db, patient, add_medication(db, patient, name), time(8, 0))

    names = [
        [e.medication.name_entered for e in repo.events_between(
            db, patient_id=patient.id, start=start, end=end
        )]
        for _ in range(3)
    ]

    assert names[0] == ["Aspirin", "Ibuprofen", "Metformin", "Warfarin"]
    # Same answer every time, not merely sorted once.
    assert names[0] == names[1] == names[2]


def test_time_still_sorts_before_name(db, patient, window):
    """Name is only the tie-breaker. An earlier dose always comes first, even
    when its name sorts later."""
    start, end = window
    add_dose(db, patient, add_medication(db, patient, "Zinc"), time(8, 0))
    add_dose(db, patient, add_medication(db, patient, "Aspirin"), time(20, 0))

    order = [
        e.medication.name_entered
        for e in repo.events_between(db, patient_id=patient.id, start=start, end=end)
    ]

    assert order == ["Zinc", "Aspirin"]


def test_window_excludes_doses_outside_it(db, patient, window):
    start, end = window
    medication = add_medication(db, patient, "Metformin")
    inside = add_dose(db, patient, medication, time(8, 0))

    # Yesterday, which falls before `start`.
    schedule = DoseSchedule(medication_id=medication.id, time_of_day=time(9, 0))
    db.add(schedule)
    db.flush()
    db.add(
        DoseEvent(
            medication_id=medication.id,
            schedule_id=schedule.id,
            patient_id=patient.id,
            scheduled_for=datetime.combine(
                TODAY - timedelta(days=1), time(9, 0), tzinfo=timezone.utc
            ),
            status=DoseStatus.MISSED,
        )
    )
    db.flush()

    found = repo.events_between(db, patient_id=patient.id, start=start, end=end)

    assert [e.id for e in found] == [inside.id]


def test_another_patients_doses_are_never_returned(db, patient, window):
    """patient_id is a required argument precisely so this cannot be forgotten."""
    from app.models.enums import UserRole
    from app.models.user import User

    start, end = window
    add_dose(db, patient, add_medication(db, patient, "Metformin"), time(8, 0))

    other = User(
        email="someone-else@example.com",
        hashed_password="x",
        full_name="Someone Else",
        role=UserRole.PATIENT,
    )
    db.add(other)
    db.flush()

    assert repo.events_between(db, patient_id=other.id, start=start, end=end) == []


def test_schedule_exists_at_ignores_deactivated_schedules(db, patient):
    """A deactivated schedule must not block re-adding that time.

    Removing a schedule deactivates it rather than deleting it, so a patient
    who removes 08:00 and later adds it back would otherwise be told it is
    already there.
    """
    medication = add_medication(db, patient, "Metformin")
    schedule = DoseSchedule(medication_id=medication.id, time_of_day=time(8, 0))
    db.add(schedule)
    db.flush()

    assert repo.schedule_exists_at(
        db, medication_id=medication.id, time_of_day=time(8, 0)
    )

    schedule.is_active = False
    db.flush()

    assert not repo.schedule_exists_at(
        db, medication_id=medication.id, time_of_day=time(8, 0)
    )


def test_get_schedule_refuses_another_patients_schedule(db, patient):
    """Ownership is enforced by the join, not by the caller remembering to
    check it."""
    from app.models.enums import UserRole
    from app.models.user import User

    medication = add_medication(db, patient, "Metformin")
    schedule = DoseSchedule(medication_id=medication.id, time_of_day=time(8, 0))
    db.add(schedule)
    db.flush()

    other = User(
        email="stranger@example.com",
        hashed_password="x",
        full_name="Stranger",
        role=UserRole.PATIENT,
    )
    db.add(other)
    db.flush()

    assert repo.get_schedule(db, patient_id=patient.id, schedule_id=schedule.id) is not None
    assert repo.get_schedule(db, patient_id=other.id, schedule_id=schedule.id) is None
