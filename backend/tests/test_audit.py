"""The audit log writer.

Covers what ticket #7 asks for: a row is written with actor, action, entity
type, entity id and details; it joins the caller's transaction; and nothing
can update or delete an audit row.
"""
import uuid

import pytest
from sqlalchemy import select

from app.models.audit import AuditEvent
from app.models.enums import UserRole
from app.models.user import User
from app.services.audit import (
    AuditAction,
    AuditLogImmutableError,
    record_event,
)


@pytest.fixture
def caregiver(db) -> User:
    user = User(
        email=f"caregiver-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="not-a-real-hash",
        full_name="Sam Caregiver",
        role=UserRole.CAREGIVER,
    )
    db.add(user)
    db.flush()
    return user


def all_events(db):
    return list(db.scalars(select(AuditEvent)).all())


# ---- Writing -----------------------------------------------------------


def test_records_actor_action_entity_and_details(db, patient):
    entity_id = uuid.uuid4()

    event = record_event(
        db,
        action=AuditAction.MEDICATION_UPDATED,
        entity_type="medication",
        entity_id=entity_id,
        actor_id=patient.id,
        patient_id=patient.id,
        details={"changed": ["dose_amount"], "dose_amount": {"old": "500", "new": "850"}},
    )

    saved = db.get(AuditEvent, event.id)
    assert saved.action == "medication.updated"
    assert saved.entity_type == "medication"
    assert saved.entity_id == entity_id
    assert saved.actor_id == patient.id
    assert saved.patient_id == patient.id
    assert saved.details["dose_amount"] == {"old": "500", "new": "850"}
    assert saved.created_at is not None


def test_system_actions_have_no_actor(db, patient):
    event = record_event(
        db,
        action=AuditAction.PATIENT_RECORD_VIEWED,
        entity_type="patient",
        entity_id=patient.id,
        patient_id=patient.id,
    )

    assert event.actor_id is None
    assert event.details is None


def test_a_caregiver_viewing_a_record_is_recorded_against_the_patient(db, patient, caregiver):
    record_event(
        db,
        action=AuditAction.PATIENT_RECORD_VIEWED,
        entity_type="patient",
        entity_id=patient.id,
        actor_id=caregiver.id,
        patient_id=patient.id,
    )

    found = db.scalars(select(AuditEvent).where(AuditEvent.patient_id == patient.id)).all()
    assert [(e.actor_id, e.action) for e in found] == [
        (caregiver.id, "patient_record.viewed")
    ]


def test_each_call_appends_a_new_row(db, patient):
    for _ in range(3):
        record_event(
            db,
            action=AuditAction.CONSENT_INVITED,
            entity_type="consent_grant",
            patient_id=patient.id,
        )

    assert len(all_events(db)) == 3


def test_an_event_needs_an_action_and_an_entity_type(db):
    with pytest.raises(ValueError):
        record_event(db, action="", entity_type="medication")
    with pytest.raises(ValueError):
        record_event(db, action="medication.created", entity_type="   ")
    assert all_events(db) == []


# ---- Transaction behaviour ---------------------------------------------


def test_the_row_rolls_back_with_the_callers_transaction(db, patient):
    """No audit entry for something that did not happen."""
    savepoint = db.begin_nested()
    record_event(
        db,
        action=AuditAction.MEDICATION_CREATED,
        entity_type="medication",
        patient_id=patient.id,
    )
    assert len(all_events(db)) == 1

    savepoint.rollback()

    assert all_events(db) == []


def test_record_event_does_not_commit_on_its_own(db, patient, monkeypatch):
    def fail_commit():
        raise AssertionError("record_event must not commit")

    monkeypatch.setattr(db, "commit", fail_commit)

    record_event(
        db,
        action=AuditAction.CONSENT_REVOKED,
        entity_type="consent_grant",
        patient_id=patient.id,
    )


# ---- Append-only -------------------------------------------------------


@pytest.mark.filterwarnings("ignore:transaction already deassociated")
def test_an_audit_row_cannot_be_updated(db, patient):
    event = record_event(
        db,
        action=AuditAction.MEDICATION_CREATED,
        entity_type="medication",
        patient_id=patient.id,
    )
    event.action = "something.else"

    with pytest.raises(AuditLogImmutableError):
        with db.begin_nested():
            db.flush()


@pytest.mark.filterwarnings("ignore:transaction already deassociated")
def test_an_audit_row_cannot_be_deleted(db, patient):
    event = record_event(
        db,
        action=AuditAction.MEDICATION_CREATED,
        entity_type="medication",
        patient_id=patient.id,
    )
    db.delete(event)

    with pytest.raises(AuditLogImmutableError):
        with db.begin_nested():
            db.flush()
