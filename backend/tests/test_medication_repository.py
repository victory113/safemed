"""Tests for the medication repository.

The access-control tests matter most: they prove one patient cannot reach
another patient's records.
"""
import uuid

from app.models.enums import MedicationStatus, UserRole
from app.models.user import User
from app.repositories import medication as repo


def _other_patient(db):
    user = User(
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        full_name="Other Person",
        role=UserRole.PATIENT,
    )
    db.add(user)
    db.flush()
    return user


def test_create_and_read_back(db, patient):
    med = repo.create(db, patient_id=patient.id, name_entered="Metformin", dose_amount="500")
    assert med.id is not None
    assert med.status == MedicationStatus.ACTIVE
    assert med.rxcui is None      # not normalised yet - a normal state

    found = repo.get(db, patient_id=patient.id, medication_id=med.id)
    assert found is not None
    assert found.name_entered == "Metformin"


def test_cannot_read_another_patients_medication(db, patient):
    med = repo.create(db, patient_id=patient.id, name_entered="Warfarin")
    intruder = _other_patient(db)

    assert repo.get(db, patient_id=intruder.id, medication_id=med.id) is None


def test_list_excludes_stopped_by_default(db, patient):
    repo.create(db, patient_id=patient.id, name_entered="Active one")
    stopped = repo.create(db, patient_id=patient.id, name_entered="Stopped one")
    repo.update(db, medication=stopped, status=MedicationStatus.STOPPED)

    active = repo.list_for_patient(db, patient_id=patient.id)
    assert [m.name_entered for m in active] == ["Active one"]

    everything = repo.list_for_patient(db, patient_id=patient.id, include_stopped=True)
    assert len(everything) == 2


def test_update_only_touches_given_fields(db, patient):
    med = repo.create(
        db, patient_id=patient.id, name_entered="Metformin",
        dose_amount="500", notes="With food",
    )
    repo.update(db, medication=med, dose_amount="1000")

    assert med.dose_amount == "1000"
    assert med.notes == "With food"     # untouched
