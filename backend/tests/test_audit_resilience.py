"""The three gaps found reviewing feature/audit-log.

Each test here failed before the fix it covers, which is the only reason any
of them is worth keeping:

1. A failing audit write took the caregiver's dashboard down with it (500).
2. A refused access attempt left no trace at all, so "who kept trying to read
   records they had no grant for" was unanswerable.
3. The MEDICATION_* actions existed as constants and nothing used them, so a
   patient's own medication history was never recorded.
"""
import uuid

import pytest
from sqlalchemy import select

from app.models.audit import AuditEvent
from app.services.audit import AuditAction

from tests.test_audit_hooks import events, linked, pair  # noqa: F401
from tests.test_consent import client, invite, make_user  # noqa: F401


def post_medication(client, headers, name="Metformin", **extra):
    """Create a medication through the API.

    test_consent.add_medication inserts straight into the session, which is
    fine for the access-control tests it was written for - but it bypasses
    the route, and the route is exactly what we are checking audits here.
    """
    return client.post(
        "/api/v1/medications", json={"name_entered": name, **extra}, headers=headers
    )


# ---- 1. A broken audit backend must not break a read -------------------


def test_a_failed_audit_write_still_serves_the_caregiver(client, linked, monkeypatch):
    """The trade stated in app/services/audit.py, pinned as a test.

    Refusing to show a caregiver a severe interaction because a log write
    failed is worse than serving it unaudited. This is the one place the
    system tolerates an unaudited action, so it should be deliberate and
    visible rather than an accident someone discovers in production.
    """
    # Patch the *inner* writer, so the isolation wrapper is the thing on trial.
    import app.services.audit as audit_service

    def boom(*args, **kwargs):
        raise RuntimeError("audit backend is down")

    monkeypatch.setattr(audit_service, "record_event", boom)

    response = client.get(
        f"/api/v1/caregiver/patients/{linked['patient_id']}/findings",
        headers=linked["caregiver_headers"],
    )

    assert response.status_code == 200, (
        "A caregiver must still see the record when the audit write fails. "
        "Before the fix this was a 500."
    )


def test_the_session_is_usable_after_a_failed_audit_write(client, linked, monkeypatch):
    """A failed flush poisons the session, and the route still has queries to run.

    Without the rollback inside try_record_event, this request fails *after*
    the audit step, in the view's own query, which is a far more confusing
    bug than the original one.
    """
    import app.services.audit as audit_service

    calls = {"n": 0}
    original = audit_service.record_event

    def fail_once(db, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient failure")
        return original(db, **kwargs)

    monkeypatch.setattr(audit_service, "record_event", fail_once)

    first = client.get(
        f"/api/v1/caregiver/patients/{linked['patient_id']}/doses/today",
        headers=linked["caregiver_headers"],
    )
    assert first.status_code == 200
    assert isinstance(first.json(), list)

    # And the next request, with the backend healthy again, audits normally.
    second = client.get(
        f"/api/v1/caregiver/patients/{linked['patient_id']}/doses/today",
        headers=linked["caregiver_headers"],
    )
    assert second.status_code == 200


# ---- 2. Refused attempts are recorded ----------------------------------


def test_a_refused_attempt_is_recorded_under_its_own_action(client, db, pair):
    """No grant exists, so this is refused - and that refusal is the record."""
    response = client.get(
        f"/api/v1/caregiver/patients/{pair['patient_id']}/findings",
        headers=pair["caregiver_headers"],
    )
    assert response.status_code == 403

    denied = events(db, AuditAction.PATIENT_RECORD_ACCESS_DENIED)
    assert len(denied) == 1
    assert denied[0].actor_id == uuid.UUID(pair["caregiver_id"])
    assert denied[0].entity_id == uuid.UUID(pair["patient_id"])
    assert denied[0].details["path"].endswith("/findings")

    # Still not a "view" - nothing was shown.
    assert events(db, AuditAction.PATIENT_RECORD_VIEWED) == []


def test_a_refusal_does_not_confirm_the_patient_exists(client, db, pair):
    """patient_id stays null on a refusal.

    Filling it in would make the audit log itself answer the question the
    403 is carefully designed not to answer: does this person exist?
    """
    unknown = uuid.uuid4()
    response = client.get(
        f"/api/v1/caregiver/patients/{unknown}/findings",
        headers=pair["caregiver_headers"],
    )
    assert response.status_code == 403

    denied = events(db, AuditAction.PATIENT_RECORD_ACCESS_DENIED)
    assert len(denied) == 1
    assert denied[0].patient_id is None
    assert denied[0].entity_id == unknown


def test_repeated_refusals_each_leave_a_row(client, db, pair):
    """The pattern is the point. One refusal is noise; six is a question."""
    for _ in range(6):
        client.get(
            f"/api/v1/caregiver/patients/{uuid.uuid4()}/findings",
            headers=pair["caregiver_headers"],
        )

    assert len(events(db, AuditAction.PATIENT_RECORD_ACCESS_DENIED)) == 6


def test_revoking_then_looking_is_recorded_as_denied(client, db, linked):
    """The sequence a reviewer actually wants to see in the log."""
    revoked = client.post(
        f"/api/v1/consent/{linked['grant_id']}/revoke",
        headers=linked["patient_headers"],
    )
    assert revoked.status_code == 200

    response = client.get(
        f"/api/v1/caregiver/patients/{linked['patient_id']}/findings",
        headers=linked["caregiver_headers"],
    )
    assert response.status_code == 403

    actions = [event.action for event in events(db)]
    assert actions[-2:] == [
        AuditAction.CONSENT_REVOKED,
        AuditAction.PATIENT_RECORD_ACCESS_DENIED,
    ]


def test_rows_written_in_one_transaction_are_still_ordered(db, patient):
    """Why created_at uses clock_timestamp() rather than now().

    PostgreSQL's now() is the transaction start time: identical for every
    statement inside it. With now(), these three rows would share a timestamp
    and `ORDER BY created_at` would return them in arbitrary order - so the
    sequence "revoked, then tried to look, then was refused" could never be
    reconstructed, which is most of the point of keeping the log.
    """
    from app.services.audit import record_event

    for action in ("first", "second", "third"):
        record_event(
            db, action=action, entity_type="probe", patient_id=patient.id
        )

    written = [
        row.action
        for row in db.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_type == "probe")
            .order_by(AuditEvent.created_at)
        ).all()
    ]
    assert written == ["first", "second", "third"]


# ---- 3. Medication changes are recorded --------------------------------


def test_adding_a_medication_is_audited(client, db, pair):
    created = post_medication(client, pair["patient_headers"], "Metformin")
    assert created.status_code == 201

    rows = events(db, AuditAction.MEDICATION_CREATED)
    assert len(rows) == 1
    assert rows[0].entity_id == uuid.UUID(created.json()["id"])
    assert rows[0].actor_id == uuid.UUID(pair["patient_id"])
    assert rows[0].patient_id == uuid.UUID(pair["patient_id"])


def test_stopping_a_medication_is_audited_and_the_creation_row_survives(
    client, db, pair
):
    """Stopping is not deleting, and the audit log must show both events."""
    created = post_medication(client, pair["patient_headers"], "Warfarin").json()

    stopped = client.delete(
        f"/api/v1/medications/{created['id']}", headers=pair["patient_headers"]
    )
    assert stopped.status_code == 200

    actions = [
        event.action
        for event in events(db)
        if event.entity_id == uuid.UUID(created["id"])
    ]
    assert actions == [AuditAction.MEDICATION_CREATED, AuditAction.MEDICATION_STOPPED]


def test_an_update_records_which_fields_changed_not_their_values(client, db, pair):
    created = post_medication(client, pair["patient_headers"], "Lisinopril").json()

    updated = client.patch(
        f"/api/v1/medications/{created['id']}",
        headers=pair["patient_headers"],
        json={"dose_amount": "20 mg"},
    )
    assert updated.status_code == 200

    rows = events(db, AuditAction.MEDICATION_UPDATED)
    assert len(rows) == 1
    assert rows[0].details == {"fields": ["dose_amount"]}
    assert "20 mg" not in str(rows[0].details)


def test_a_failed_medication_write_leaves_no_audit_row(client, db, pair):
    """The other half of the trade: a write that does not happen is not logged.

    record_event flushes into the caller's transaction, so a rollback takes
    the audit row with it.
    """
    before = len(events(db, AuditAction.MEDICATION_UPDATED))

    missing = client.patch(
        f"/api/v1/medications/{uuid.uuid4()}",
        headers=pair["patient_headers"],
        json={"dose_amount": "5 mg"},
    )
    assert missing.status_code == 404
    assert len(events(db, AuditAction.MEDICATION_UPDATED)) == before
