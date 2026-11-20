"""The dose and schedule endpoints, through real HTTP.

These cover the gap that made the dashboard unusable: there was no way to
create a dose schedule through the API at all, so a patient who added a
medication had nothing to log against and the daily check-in was always empty.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app

PASSWORD = "testpass123"


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth(client):
    """Register and log in a patient; return their auth headers."""
    email = f"patient-{uuid.uuid4().hex[:8]}@example.com"
    created = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "Test Patient",
            "role": "PATIENT",
        },
    )
    assert created.status_code == 201, created.text
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def add_medication(client, auth, **extra):
    body = {"name_entered": "Metformin", "dose_amount": "500", "dose_unit": "mg"}
    body.update(extra)
    return client.post("/api/v1/medications", json=body, headers=auth)


# ---- scheduling on create ----------------------------------------------


def test_medication_created_with_times_produces_doses_to_log(client, auth):
    """The whole point of the feature: times in, doses out."""
    created = add_medication(client, auth, times=["08:00", "20:00"])
    assert created.status_code == 201, created.text

    doses = client.get("/api/v1/doses/today", headers=auth)
    assert doses.status_code == 200
    assert len(doses.json()) == 2
    assert {d["medication_name"] for d in doses.json()} == {"Metformin"}


def test_medication_created_without_times_produces_no_doses(client, auth):
    """A medication taken only as needed is legitimate - it just has nothing
    to confirm."""
    assert add_medication(client, auth).status_code == 201

    assert client.get("/api/v1/doses/today", headers=auth).json() == []


def test_duplicate_times_are_collapsed(client, auth):
    """Two schedules at one time would ask the patient to confirm the same
    pill twice."""
    medication = add_medication(client, auth, times=["08:00", "08:00", "20:00"]).json()

    schedules = client.get(
        f"/api/v1/medications/{medication['id']}/schedules", headers=auth
    ).json()

    assert [s["time_of_day"] for s in schedules] == ["08:00:00", "20:00:00"]


def test_grace_minutes_applies_to_every_time(client, auth):
    medication = add_medication(
        client, auth, times=["08:00", "20:00"], grace_minutes=30
    ).json()

    schedules = client.get(
        f"/api/v1/medications/{medication['id']}/schedules", headers=auth
    ).json()

    assert [s["grace_minutes"] for s in schedules] == [30, 30]


def test_times_are_not_stored_on_the_medication_itself(client, auth):
    """`times` belongs to DoseSchedule. If it leaked through to the Medication
    constructor the create would fail outright, so this guards the plumbing."""
    created = add_medication(client, auth, times=["08:00"])

    assert created.status_code == 201
    assert "times" not in created.json()


# ---- the schedules sub-resource ----------------------------------------


def test_a_time_can_be_added_later(client, auth):
    medication = add_medication(client, auth, times=["08:00"]).json()

    added = client.post(
        f"/api/v1/medications/{medication['id']}/schedules",
        json={"time_of_day": "20:00"},
        headers=auth,
    )

    assert added.status_code == 201, added.text
    assert len(client.get("/api/v1/doses/today", headers=auth).json()) == 2


def test_adding_a_time_that_already_exists_is_a_conflict(client, auth):
    medication = add_medication(client, auth, times=["08:00"]).json()

    repeat = client.post(
        f"/api/v1/medications/{medication['id']}/schedules",
        json={"time_of_day": "08:00"},
        headers=auth,
    )

    assert repeat.status_code == 409


def test_removing_a_time_deactivates_it_rather_than_deleting(client, auth):
    """The doses already logged against a schedule are history. Deleting the
    row would orphan them."""
    medication = add_medication(client, auth, times=["08:00", "20:00"]).json()
    schedules = client.get(
        f"/api/v1/medications/{medication['id']}/schedules", headers=auth
    ).json()

    removed = client.delete(
        f"/api/v1/medications/{medication['id']}/schedules/{schedules[0]['id']}",
        headers=auth,
    )

    assert removed.status_code == 200
    assert removed.json()["is_active"] is False
    # Gone from the active list, but the row still exists.
    assert len(
        client.get(
            f"/api/v1/medications/{medication['id']}/schedules", headers=auth
        ).json()
    ) == 1


def test_a_removed_time_can_be_added_back(client, auth):
    medication = add_medication(client, auth, times=["08:00"]).json()
    schedules = client.get(
        f"/api/v1/medications/{medication['id']}/schedules", headers=auth
    ).json()
    client.delete(
        f"/api/v1/medications/{medication['id']}/schedules/{schedules[0]['id']}",
        headers=auth,
    )

    again = client.post(
        f"/api/v1/medications/{medication['id']}/schedules",
        json={"time_of_day": "08:00"},
        headers=auth,
    )

    assert again.status_code == 201


def test_schedules_of_an_unknown_medication_are_404(client, auth):
    assert (
        client.get(
            f"/api/v1/medications/{uuid.uuid4()}/schedules", headers=auth
        ).status_code
        == 404
    )


def test_schedules_need_a_token(client):
    assert (
        client.get(f"/api/v1/medications/{uuid.uuid4()}/schedules").status_code == 401
    )


# ---- adherence ---------------------------------------------------------


def test_adherence_is_null_not_zero_when_nothing_has_resolved(client, auth):
    """The case that matters most. 0% would tell a caregiver this patient has
    missed everything; the truth is that there is no data yet."""
    add_medication(client, auth, times=["08:00"])

    body = client.get("/api/v1/doses/adherence?days=7", headers=auth).json()

    assert body["rate"] is None
    assert body["resolved"] == 0


def test_adherence_counts_a_confirmed_dose(client, auth):
    add_medication(client, auth, times=["08:00"])
    dose = client.get("/api/v1/doses/today", headers=auth).json()[0]
    client.post(f"/api/v1/doses/{dose['id']}/confirm", headers=auth)

    body = client.get("/api/v1/doses/adherence?days=7", headers=auth).json()

    assert body["taken"] == 1
    assert body["rate"] == 1.0
    assert body["resolved"] == 1


def test_a_skipped_dose_does_not_count_against_the_rate(client, auth):
    """A patient told to stop for a day did not fail to adhere, so a skip is
    reported separately and kept out of the denominator."""
    add_medication(client, auth, times=["08:00"])
    dose = client.get("/api/v1/doses/today", headers=auth).json()[0]
    client.post(f"/api/v1/doses/{dose['id']}/skip", json={"note": None}, headers=auth)

    body = client.get("/api/v1/doses/adherence?days=7", headers=auth).json()

    assert body["skipped"] == 1
    assert body["resolved"] == 0
    assert body["rate"] is None


def test_adherence_rejects_an_out_of_range_window(client, auth):
    assert client.get("/api/v1/doses/adherence?days=0", headers=auth).status_code == 422
    assert client.get("/api/v1/doses/adherence?days=91", headers=auth).status_code == 422


def test_adherence_needs_a_token(client):
    assert client.get("/api/v1/doses/adherence").status_code == 401


# ---- history -----------------------------------------------------------


def test_history_does_not_invent_doses(client, auth):
    """/today generates the rows it is missing; /history never does.

    So a brand-new schedule has no history at all, even though it covers the
    last seven days. That is the correct answer: generating rows for days
    already past would manufacture missed doses the patient was never asked
    about, and those invented misses would lower their adherence and could
    reach a caregiver.
    """
    add_medication(client, auth, times=["08:00"])

    assert client.get("/api/v1/doses/history?days=7", headers=auth).json() == []

    # Opening today's check-in is what brings today's dose into existence.
    client.get("/api/v1/doses/today", headers=auth)

    history = client.get("/api/v1/doses/history?days=7", headers=auth).json()
    assert len(history) == 1


def test_history_needs_a_token(client):
    assert client.get("/api/v1/doses/history").status_code == 401
