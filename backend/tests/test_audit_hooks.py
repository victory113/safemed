"""The audit log is actually written by the code that matters.

test_audit.py proves the writer works. These tests prove it is wired in:
consent changes and caregiver access each leave a row, and a request that
fails or is refused does not.
"""
import uuid

import pytest
from sqlalchemy import select

from app.models.audit import AuditEvent
from app.services.audit import AuditAction

# Reuse the fixtures and helpers the consent tests already define.
from tests.test_consent import (  # noqa: F401  (client is a pytest fixture)
    add_medication,
    client,
    invite,
    make_user,
    meds_url,
)


def events(db, action=None):
    stmt = select(AuditEvent).order_by(AuditEvent.created_at, AuditEvent.id)
    if action is not None:
        stmt = stmt.where(AuditEvent.action == action)
    return list(db.scalars(stmt).all())


@pytest.fixture
def pair(client):
    """A patient and a caregiver, no grant yet."""
    patient_id, _, patient_headers = make_user(client, "PATIENT")
    caregiver_id, caregiver_email, caregiver_headers = make_user(client, "CAREGIVER")
    return {
        "patient_id": patient_id,
        "patient_headers": patient_headers,
        "caregiver_id": caregiver_id,
        "caregiver_email": caregiver_email,
        "caregiver_headers": caregiver_headers,
    }


@pytest.fixture
def linked(client, pair):
    """The same pair, with an ACTIVE grant. Returns the pair plus grant_id."""
    grant = invite(client, pair["patient_headers"], pair["caregiver_email"]).json()
    accepted = client.post(
        f"/api/v1/consent/{grant['id']}/accept", headers=pair["caregiver_headers"]
    )
    assert accepted.status_code == 200
    return {**pair, "grant_id": grant["id"]}


# ---- Consent changes ---------------------------------------------------


def test_inviting_is_audited(client, db, pair):
    grant = invite(client, pair["patient_headers"], pair["caregiver_email"]).json()

    (event,) = events(db, AuditAction.CONSENT_INVITED)
    assert str(event.actor_id) == pair["patient_id"]
    assert str(event.patient_id) == pair["patient_id"]
    assert event.entity_type == "consent_grant"
    assert str(event.entity_id) == grant["id"]
    assert event.details == {"caregiver_id": pair["caregiver_id"]}


def test_accepting_is_audited(client, db, pair):
    grant = invite(client, pair["patient_headers"], pair["caregiver_email"]).json()
    client.post(f"/api/v1/consent/{grant['id']}/accept", headers=pair["caregiver_headers"])

    (event,) = events(db, AuditAction.CONSENT_ACCEPTED)
    assert str(event.actor_id) == pair["caregiver_id"]
    assert str(event.patient_id) == pair["patient_id"]
    assert str(event.entity_id) == grant["id"]


def test_revoking_records_who_did_it_and_what_it_was_before(client, db, linked):
    client.post(
        f"/api/v1/consent/{linked['grant_id']}/revoke", headers=linked["patient_headers"]
    )

    (event,) = events(db, AuditAction.CONSENT_REVOKED)
    assert str(event.actor_id) == linked["patient_id"]
    assert event.details["revoked_by"] == "PATIENT"
    assert event.details["previous_status"] == "ACTIVE"
    assert event.details["caregiver_id"] == linked["caregiver_id"]


def test_a_caregiver_declining_is_audited_as_the_caregiver(client, db, pair):
    grant = invite(client, pair["patient_headers"], pair["caregiver_email"]).json()
    client.post(f"/api/v1/consent/{grant['id']}/revoke", headers=pair["caregiver_headers"])

    (event,) = events(db, AuditAction.CONSENT_REVOKED)
    assert str(event.actor_id) == pair["caregiver_id"]
    assert event.details["revoked_by"] == "CAREGIVER"
    assert event.details["previous_status"] == "PENDING"


def test_the_whole_history_is_kept_after_a_revoke(client, db, linked):
    client.post(
        f"/api/v1/consent/{linked['grant_id']}/revoke", headers=linked["patient_headers"]
    )

    # Compared as a set: inside one test transaction every row shares a
    # timestamp, so their order is not meaningful here.
    assert sorted(e.action for e in events(db)) == sorted(
        [
            AuditAction.CONSENT_INVITED,
            AuditAction.CONSENT_ACCEPTED,
            AuditAction.CONSENT_REVOKED,
        ]
    )


def test_failed_consent_actions_leave_no_audit_row(client, db, pair):
    # Unknown email: 404.
    assert invite(client, pair["patient_headers"], "nobody@example.com").status_code == 404
    # A real invite, then the same invite again: 400.
    grant = invite(client, pair["patient_headers"], pair["caregiver_email"]).json()
    assert invite(client, pair["patient_headers"], pair["caregiver_email"]).status_code == 400
    # Someone else tries to accept it: 404.
    _, _, stranger_headers = make_user(client, "CAREGIVER")
    refused = client.post(f"/api/v1/consent/{grant['id']}/accept", headers=stranger_headers)
    assert refused.status_code == 404

    assert [e.action for e in events(db)] == [AuditAction.CONSENT_INVITED]


# ---- Caregiver access --------------------------------------------------

CAREGIVER_VIEWS = [
    "medications",
    "findings",
    "doses/today",
    "adherence",
]


@pytest.mark.parametrize("view", CAREGIVER_VIEWS)
def test_every_caregiver_view_records_who_looked_at_whom(client, db, linked, view):
    add_medication(db, linked["patient_id"])
    url = f"/api/v1/caregiver/patients/{linked['patient_id']}/{view}"

    response = client.get(url, headers=linked["caregiver_headers"])

    assert response.status_code == 200, response.text
    (event,) = events(db, AuditAction.PATIENT_RECORD_VIEWED)
    assert str(event.actor_id) == linked["caregiver_id"]
    assert str(event.patient_id) == linked["patient_id"]
    assert event.entity_type == "patient"
    assert event.details == {"method": "GET", "path": url}


def test_each_look_is_its_own_row(client, db, linked):
    url = meds_url(linked["patient_id"])

    client.get(url, headers=linked["caregiver_headers"])
    client.get(url, headers=linked["caregiver_headers"])

    assert len(events(db, AuditAction.PATIENT_RECORD_VIEWED)) == 2


def test_a_refused_request_is_not_recorded_as_a_view(client, db, pair):
    # No grant at all.
    response = client.get(meds_url(pair["patient_id"]), headers=pair["caregiver_headers"])
    assert response.status_code == 403
    # An id that does not exist.
    response = client.get(meds_url(uuid.uuid4()), headers=pair["caregiver_headers"])
    assert response.status_code == 403

    assert events(db, AuditAction.PATIENT_RECORD_VIEWED) == []


def test_looking_after_a_revoke_is_refused_and_not_recorded(client, db, linked):
    url = meds_url(linked["patient_id"])
    client.get(url, headers=linked["caregiver_headers"])  # allowed, recorded
    client.post(
        f"/api/v1/consent/{linked['grant_id']}/revoke", headers=linked["patient_headers"]
    )

    response = client.get(url, headers=linked["caregiver_headers"])

    assert response.status_code == 403
    assert len(events(db, AuditAction.PATIENT_RECORD_VIEWED)) == 1
