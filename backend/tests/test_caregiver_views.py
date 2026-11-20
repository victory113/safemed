"""What a caregiver can and cannot see.

The severity filter is the subject of most of these tests. A caregiver sees
SEVERE findings only, and that rule has to hold at the endpoint rather than in
the interface - otherwise a second client, or a direct API call, would hand
someone all ten findings and reintroduce exactly the alert fatigue the
severity routing exists to prevent.
"""
import uuid
from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.dose import DoseEvent
from app.models.enums import (
    ConsentStatus,
    DoseStatus,
    FindingStatus,
    FindingType,
    MedicationStatus,
    Severity,
)
from app.models.medication import DoseSchedule, Medication
from app.models.safety import SafetyFinding
from app.models.user import ConsentGrant

PASSWORD = "testpass123"


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_user(client, role):
    email = f"{role.lower()}-{uuid.uuid4().hex[:8]}@example.com"
    created = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": f"Test {role}",
            "role": role,
        },
    )
    assert created.status_code == 201, created.text
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["access_token"]
    return created.json()["id"], email, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def linked(client, db):
    """A patient and a caregiver with an ACTIVE grant between them."""
    patient_id, _, patient_headers = make_user(client, "PATIENT")
    caregiver_id, caregiver_email, caregiver_headers = make_user(client, "CAREGIVER")

    grant = ConsentGrant(
        patient_id=uuid.UUID(patient_id),
        caregiver_id=uuid.UUID(caregiver_id),
        status=ConsentStatus.ACTIVE,
        granted_at=datetime.now(timezone.utc),
    )
    db.add(grant)
    db.flush()

    return {
        "patient_id": patient_id,
        "patient_headers": patient_headers,
        "caregiver_email": caregiver_email,
        "caregiver_headers": caregiver_headers,
        "grant": grant,
    }


def add_finding(db, patient_id, severity, title, status=FindingStatus.OPEN):
    finding = SafetyFinding(
        patient_id=uuid.UUID(patient_id),
        finding_type=FindingType.INTERACTION,
        severity=severity,
        status=status,
        title=title,
        detail="Detail text.",
        source_name="TestSource",
        source_version="1",
        dedupe_key=uuid.uuid4().hex,
        # Set explicitly: the safety engine stamps this, so the column has no
        # default and a fixture that omits it would fail at insert.
        detected_at=datetime.now(timezone.utc),
        acknowledged_at=(
            datetime.now(timezone.utc) if status == FindingStatus.ACKNOWLEDGED else None
        ),
    )
    db.add(finding)
    db.flush()
    return finding


def add_dose(db, patient_id, at: time, status: DoseStatus, day: date | None = None):
    medication = Medication(
        patient_id=uuid.UUID(patient_id),
        name_entered="Metformin",
        status=MedicationStatus.ACTIVE,
    )
    db.add(medication)
    db.flush()

    schedule = DoseSchedule(medication_id=medication.id, time_of_day=at)
    db.add(schedule)
    db.flush()

    event = DoseEvent(
        medication_id=medication.id,
        schedule_id=schedule.id,
        patient_id=uuid.UUID(patient_id),
        scheduled_for=datetime.combine(day or date.today(), at, tzinfo=timezone.utc),
        status=status,
        confirmed_at=datetime.now(timezone.utc)
        if status in (DoseStatus.TAKEN, DoseStatus.SKIPPED)
        else None,
    )
    db.add(event)
    db.flush()
    return event


def findings_url(patient_id):
    return f"/api/v1/caregiver/patients/{patient_id}/findings"


# ---- the severity rule -------------------------------------------------


def test_caregiver_sees_only_severe_findings(client, db, linked):
    """Ten findings on the patient's screen, three on the caregiver's."""
    pid = linked["patient_id"]
    add_finding(db, pid, Severity.SEVERE, "Serious one")
    add_finding(db, pid, Severity.SEVERE, "Serious two")
    add_finding(db, pid, Severity.MODERATE, "Moderate one")
    add_finding(db, pid, Severity.MILD, "Mild one")

    seen = client.get(findings_url(pid), headers=linked["caregiver_headers"]).json()

    assert {f["title"] for f in seen} == {"Serious one", "Serious two"}


def test_the_patient_still_sees_everything(client, db, linked):
    """The filter is about who is told, not about hiding data from the person
    it belongs to."""
    pid = linked["patient_id"]
    add_finding(db, pid, Severity.SEVERE, "Serious one")
    add_finding(db, pid, Severity.MODERATE, "Moderate one")
    add_finding(db, pid, Severity.MILD, "Mild one")

    own = client.get("/api/v1/findings", headers=linked["patient_headers"]).json()

    assert len(own) == 3


def test_an_acknowledged_severe_finding_is_still_shown(client, db, linked):
    """A caregiver should be able to see that the patient has read it."""
    pid = linked["patient_id"]
    add_finding(db, pid, Severity.SEVERE, "Read already", status=FindingStatus.ACKNOWLEDGED)

    seen = client.get(findings_url(pid), headers=linked["caregiver_headers"]).json()

    assert [f["title"] for f in seen] == ["Read already"]


def test_a_resolved_finding_is_not_shown(client, db, linked):
    pid = linked["patient_id"]
    add_finding(db, pid, Severity.SEVERE, "Done with", status=FindingStatus.RESOLVED)

    assert client.get(findings_url(pid), headers=linked["caregiver_headers"]).json() == []


# ---- access control ----------------------------------------------------


def test_no_grant_means_no_findings(client, db):
    patient_id, _, _ = make_user(client, "PATIENT")
    _, _, caregiver_headers = make_user(client, "CAREGIVER")
    add_finding(db, patient_id, Severity.SEVERE, "Serious one")

    assert client.get(findings_url(patient_id), headers=caregiver_headers).status_code == 403


def test_revoking_consent_closes_the_findings_view(client, db, linked):
    pid = linked["patient_id"]
    add_finding(db, pid, Severity.SEVERE, "Serious one")
    headers = linked["caregiver_headers"]
    assert client.get(findings_url(pid), headers=headers).status_code == 200

    linked["grant"].status = ConsentStatus.REVOKED
    db.flush()

    assert client.get(findings_url(pid), headers=headers).status_code == 403


def test_a_patient_cannot_use_the_caregiver_findings_view(client, linked):
    """Even for their own record - this route is for caregivers."""
    assert (
        client.get(
            findings_url(linked["patient_id"]), headers=linked["patient_headers"]
        ).status_code
        == 403
    )


def test_findings_need_a_token(client, linked):
    assert client.get(findings_url(linked["patient_id"])).status_code == 401


def test_every_caregiver_route_is_behind_the_grant(client, db):
    """One missed dependency would open a hole, so each route is checked."""
    patient_id, _, _ = make_user(client, "PATIENT")
    _, _, caregiver_headers = make_user(client, "CAREGIVER")

    base = f"/api/v1/caregiver/patients/{patient_id}"
    for path in (f"{base}/findings", f"{base}/doses/today", f"{base}/adherence"):
        assert client.get(path, headers=caregiver_headers).status_code == 403, path


# ---- doses and adherence -----------------------------------------------


def test_caregiver_sees_todays_doses(client, db, linked):
    pid = linked["patient_id"]
    add_dose(db, pid, time(8, 0), DoseStatus.TAKEN)
    add_dose(db, pid, time(20, 0), DoseStatus.SCHEDULED)

    seen = client.get(
        f"/api/v1/caregiver/patients/{pid}/doses/today",
        headers=linked["caregiver_headers"],
    ).json()

    assert len(seen) == 2


def test_the_caregiver_view_does_not_create_doses(client, db, linked):
    """Looking at a patient's record must not write to it. The patient has a
    schedule but has never opened their own app, so no dose rows exist yet."""
    pid = linked["patient_id"]
    medication = Medication(
        patient_id=uuid.UUID(pid), name_entered="Metformin", status=MedicationStatus.ACTIVE
    )
    db.add(medication)
    db.flush()
    db.add(DoseSchedule(medication_id=medication.id, time_of_day=time(8, 0)))
    db.flush()

    seen = client.get(
        f"/api/v1/caregiver/patients/{pid}/doses/today",
        headers=linked["caregiver_headers"],
    ).json()

    assert seen == []


def test_adherence_is_null_not_zero_for_a_patient_with_no_history(client, linked):
    """The case most likely to cause a needless phone call."""
    body = client.get(
        f"/api/v1/caregiver/patients/{linked['patient_id']}/adherence",
        headers=linked["caregiver_headers"],
    ).json()

    assert body["rate"] is None
    assert body["resolved"] == 0


def test_adherence_reflects_the_patients_record(client, db, linked):
    pid = linked["patient_id"]
    yesterday = date.today() - timedelta(days=1)
    add_dose(db, pid, time(8, 0), DoseStatus.TAKEN, day=yesterday)
    add_dose(db, pid, time(12, 0), DoseStatus.TAKEN, day=yesterday)
    add_dose(db, pid, time(20, 0), DoseStatus.MISSED, day=yesterday)

    body = client.get(
        f"/api/v1/caregiver/patients/{pid}/adherence?days=7",
        headers=linked["caregiver_headers"],
    ).json()

    assert body["taken"] == 2
    assert body["missed"] == 1
    assert body["rate"] == pytest.approx(2 / 3)
