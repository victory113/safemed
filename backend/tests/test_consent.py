"""Consent grants and the caregiver views they unlock.

These go through the real HTTP endpoints with real tokens, because the rule
being tested ("no ACTIVE grant, no access") lives across the whole request:
the token, the role check and the grant lookup.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.enums import ConsentStatus
from app.models.medication import Medication
from app.models.user import ConsentGrant

PASSWORD = "testpass123"


@pytest.fixture
def client(db):
    """A test client whose requests use the rolled-back test session."""
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_user(client, role):
    """Register a user, log in, and return (id, email, auth headers)."""
    email = f"{role.lower()}-{uuid.uuid4().hex[:8]}@example.com"
    created = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": f"Test {role}", "role": role},
    )
    assert created.status_code == 201, created.text
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["access_token"]
    return created.json()["id"], email, {"Authorization": f"Bearer {token}"}


def invite(client, patient_headers, caregiver_email):
    return client.post(
        "/api/v1/consent/invitations",
        json={"caregiver_email": caregiver_email},
        headers=patient_headers,
    )


def add_medication(db, patient_id, name="Metformin"):
    db.add(Medication(patient_id=uuid.UUID(patient_id), name_entered=name))
    db.flush()


def meds_url(patient_id):
    return f"/api/v1/caregiver/patients/{patient_id}/medications"


# ---- The core rule -----------------------------------------------------


def test_caregiver_with_no_grant_gets_403(client, db):
    patient_id, _, _ = make_user(client, "PATIENT")
    _, _, caregiver_headers = make_user(client, "CAREGIVER")
    add_medication(db, patient_id)

    response = client.get(meds_url(patient_id), headers=caregiver_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have access to this patient"


def test_unknown_patient_id_looks_the_same_as_no_grant(client):
    _, _, caregiver_headers = make_user(client, "CAREGIVER")

    response = client.get(meds_url(uuid.uuid4()), headers=caregiver_headers)

    assert response.status_code == 403


def test_pending_grant_does_not_give_access(client, db):
    patient_id, _, patient_headers = make_user(client, "PATIENT")
    _, caregiver_email, caregiver_headers = make_user(client, "CAREGIVER")
    add_medication(db, patient_id)
    assert invite(client, patient_headers, caregiver_email).status_code == 201

    response = client.get(meds_url(patient_id), headers=caregiver_headers)

    assert response.status_code == 403


def test_accepted_grant_gives_access(client, db):
    patient_id, _, patient_headers = make_user(client, "PATIENT")
    _, caregiver_email, caregiver_headers = make_user(client, "CAREGIVER")
    add_medication(db, patient_id, "Metformin")
    grant = invite(client, patient_headers, caregiver_email).json()

    accepted = client.post(f"/api/v1/consent/{grant['id']}/accept", headers=caregiver_headers)
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ACTIVE"
    assert accepted.json()["granted_at"] is not None

    response = client.get(meds_url(patient_id), headers=caregiver_headers)
    assert response.status_code == 200
    assert [m["name_entered"] for m in response.json()] == ["Metformin"]


def test_revoking_blocks_access_immediately_and_keeps_the_record(client, db):
    patient_id, _, patient_headers = make_user(client, "PATIENT")
    _, caregiver_email, caregiver_headers = make_user(client, "CAREGIVER")
    add_medication(db, patient_id)
    grant = invite(client, patient_headers, caregiver_email).json()
    client.post(f"/api/v1/consent/{grant['id']}/accept", headers=caregiver_headers)
    assert client.get(meds_url(patient_id), headers=caregiver_headers).status_code == 200

    revoked = client.post(f"/api/v1/consent/{grant['id']}/revoke", headers=patient_headers)

    assert revoked.status_code == 200
    assert revoked.json()["status"] == "REVOKED"
    assert client.get(meds_url(patient_id), headers=caregiver_headers).status_code == 403
    # The row is still there, marked revoked, with the time it happened.
    row = db.get(ConsentGrant, uuid.UUID(grant["id"]))
    assert row is not None
    assert row.status == ConsentStatus.REVOKED
    assert row.revoked_at is not None


def test_a_grant_for_one_patient_does_not_open_another(client, db):
    patient_a, _, headers_a = make_user(client, "PATIENT")
    patient_b, _, _ = make_user(client, "PATIENT")
    _, caregiver_email, caregiver_headers = make_user(client, "CAREGIVER")
    add_medication(db, patient_b)
    grant = invite(client, headers_a, caregiver_email).json()
    client.post(f"/api/v1/consent/{grant['id']}/accept", headers=caregiver_headers)

    assert client.get(meds_url(patient_a), headers=caregiver_headers).status_code == 200
    assert client.get(meds_url(patient_b), headers=caregiver_headers).status_code == 403


# ---- Roles -------------------------------------------------------------


def test_no_token_is_401(client):
    assert client.get("/api/v1/consent").status_code == 401
    assert client.get("/api/v1/caregiver/patients").status_code == 401


def test_patient_cannot_use_caregiver_views(client):
    patient_id, _, patient_headers = make_user(client, "PATIENT")

    assert client.get("/api/v1/caregiver/patients", headers=patient_headers).status_code == 403
    assert client.get(meds_url(patient_id), headers=patient_headers).status_code == 403


def test_caregiver_cannot_send_invitations(client):
    _, email, caregiver_headers = make_user(client, "CAREGIVER")

    assert invite(client, caregiver_headers, email).status_code == 403


# ---- Inviting ----------------------------------------------------------


def test_invite_creates_a_pending_grant(client):
    patient_id, _, patient_headers = make_user(client, "PATIENT")
    caregiver_id, caregiver_email, _ = make_user(client, "CAREGIVER")

    response = invite(client, patient_headers, caregiver_email)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["patient"]["id"] == patient_id
    assert body["caregiver"]["id"] == caregiver_id
    assert body["granted_at"] is None
    assert "password" not in str(body) and "hashed" not in str(body)


def test_invite_email_is_case_insensitive(client):
    _, _, patient_headers = make_user(client, "PATIENT")
    _, caregiver_email, _ = make_user(client, "CAREGIVER")

    assert invite(client, patient_headers, caregiver_email.upper()).status_code == 201


def test_invite_unknown_email_is_404(client):
    _, _, patient_headers = make_user(client, "PATIENT")

    assert invite(client, patient_headers, "nobody@example.com").status_code == 404


def test_cannot_invite_a_patient_account_as_caregiver(client):
    _, _, patient_headers = make_user(client, "PATIENT")
    _, other_patient_email, _ = make_user(client, "PATIENT")

    assert invite(client, patient_headers, other_patient_email).status_code == 404


def test_inviting_twice_is_rejected(client):
    _, _, patient_headers = make_user(client, "PATIENT")
    _, caregiver_email, _ = make_user(client, "CAREGIVER")
    assert invite(client, patient_headers, caregiver_email).status_code == 201

    assert invite(client, patient_headers, caregiver_email).status_code == 400


def test_re_inviting_after_revoke_reuses_the_row_as_pending(client):
    _, _, patient_headers = make_user(client, "PATIENT")
    _, caregiver_email, caregiver_headers = make_user(client, "CAREGIVER")
    grant = invite(client, patient_headers, caregiver_email).json()
    client.post(f"/api/v1/consent/{grant['id']}/accept", headers=caregiver_headers)
    client.post(f"/api/v1/consent/{grant['id']}/revoke", headers=patient_headers)

    again = invite(client, patient_headers, caregiver_email)

    assert again.status_code == 201
    assert again.json()["id"] == grant["id"]
    assert again.json()["status"] == "PENDING"
    assert again.json()["revoked_at"] is None


# ---- Accepting and revoking: who may do it -----------------------------


def test_only_the_invited_caregiver_can_accept(client):
    _, _, patient_headers = make_user(client, "PATIENT")
    _, caregiver_email, _ = make_user(client, "CAREGIVER")
    _, _, stranger_headers = make_user(client, "CAREGIVER")
    grant = invite(client, patient_headers, caregiver_email).json()

    response = client.post(f"/api/v1/consent/{grant['id']}/accept", headers=stranger_headers)

    assert response.status_code == 404


def test_patient_cannot_accept_their_own_invitation(client):
    _, _, patient_headers = make_user(client, "PATIENT")
    _, caregiver_email, _ = make_user(client, "CAREGIVER")
    grant = invite(client, patient_headers, caregiver_email).json()

    response = client.post(f"/api/v1/consent/{grant['id']}/accept", headers=patient_headers)

    assert response.status_code == 403


def test_accepting_twice_is_rejected(client):
    _, _, patient_headers = make_user(client, "PATIENT")
    _, caregiver_email, caregiver_headers = make_user(client, "CAREGIVER")
    grant = invite(client, patient_headers, caregiver_email).json()
    client.post(f"/api/v1/consent/{grant['id']}/accept", headers=caregiver_headers)

    again = client.post(f"/api/v1/consent/{grant['id']}/accept", headers=caregiver_headers)

    assert again.status_code == 400


def test_a_stranger_cannot_revoke_someone_elses_grant(client):
    _, _, patient_headers = make_user(client, "PATIENT")
    _, _, other_patient_headers = make_user(client, "PATIENT")
    _, caregiver_email, _ = make_user(client, "CAREGIVER")
    grant = invite(client, patient_headers, caregiver_email).json()

    response = client.post(
        f"/api/v1/consent/{grant['id']}/revoke", headers=other_patient_headers
    )

    assert response.status_code == 404


def test_caregiver_can_decline_an_invitation(client):
    _, _, patient_headers = make_user(client, "PATIENT")
    _, caregiver_email, caregiver_headers = make_user(client, "CAREGIVER")
    grant = invite(client, patient_headers, caregiver_email).json()

    response = client.post(f"/api/v1/consent/{grant['id']}/revoke", headers=caregiver_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "REVOKED"


def test_revoking_twice_is_rejected(client):
    _, _, patient_headers = make_user(client, "PATIENT")
    _, caregiver_email, _ = make_user(client, "CAREGIVER")
    grant = invite(client, patient_headers, caregiver_email).json()
    client.post(f"/api/v1/consent/{grant['id']}/revoke", headers=patient_headers)

    again = client.post(f"/api/v1/consent/{grant['id']}/revoke", headers=patient_headers)

    assert again.status_code == 400


# ---- Listing -----------------------------------------------------------


def test_each_side_lists_only_its_own_grants(client):
    _, _, patient_headers = make_user(client, "PATIENT")
    _, _, other_patient_headers = make_user(client, "PATIENT")
    _, caregiver_email, caregiver_headers = make_user(client, "CAREGIVER")
    grant = invite(client, patient_headers, caregiver_email).json()

    patient_list = client.get("/api/v1/consent", headers=patient_headers).json()
    caregiver_list = client.get("/api/v1/consent", headers=caregiver_headers).json()
    other_list = client.get("/api/v1/consent", headers=other_patient_headers).json()

    assert [g["id"] for g in patient_list] == [grant["id"]]
    assert [g["id"] for g in caregiver_list] == [grant["id"]]
    assert other_list == []


def test_status_filter_on_the_list(client):
    _, _, patient_headers = make_user(client, "PATIENT")
    _, caregiver_email, _ = make_user(client, "CAREGIVER")
    invite(client, patient_headers, caregiver_email)

    pending = client.get("/api/v1/consent?status=PENDING", headers=patient_headers).json()
    active = client.get("/api/v1/consent?status=ACTIVE", headers=patient_headers).json()

    assert len(pending) == 1
    assert active == []


def test_my_patients_lists_only_active_grants(client):
    patient_a, _, headers_a = make_user(client, "PATIENT")
    _, _, headers_b = make_user(client, "PATIENT")
    _, caregiver_email, caregiver_headers = make_user(client, "CAREGIVER")
    grant_a = invite(client, headers_a, caregiver_email).json()
    invite(client, headers_b, caregiver_email)  # stays PENDING
    client.post(f"/api/v1/consent/{grant_a['id']}/accept", headers=caregiver_headers)

    response = client.get("/api/v1/caregiver/patients", headers=caregiver_headers)

    assert response.status_code == 200
    assert [p["id"] for p in response.json()] == [patient_a]
