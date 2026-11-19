"""Tests for turning recalls into findings."""
from app.models.enums import FindingType, MedicationStatus, RecallMatch, Severity
from app.models.medication import Medication
from app.services.recall_monitor import RecallMonitor
from tests.test_recalls import make_recall


def add_med(db, patient, name="Metformin", ndc=None, normalized="metformin"):
    med = Medication(
        patient_id=patient.id, name_entered=name, normalized_name=normalized,
        ndc=ndc, status=MedicationStatus.ACTIVE,
    )
    db.add(med)
    db.flush()
    return med


def test_confirmed_match_creates_a_severe_or_moderate_finding(db, patient):
    add_med(db, patient, ndc="0093-1048-01")
    created = RecallMonitor(db).process([make_recall()])

    assert len(created) == 1
    finding = created[0]
    assert finding.finding_type == FindingType.RECALL
    assert finding.recall_match == RecallMatch.CONFIRMED
    assert "affects your" in finding.title


def test_possible_match_tells_the_patient_to_check_the_label(db, patient):
    """The wording has to be honest about the uncertainty, or the tier is
    pointless."""
    add_med(db, patient, ndc=None)
    finding = RecallMonitor(db).process([make_recall()])[0]

    assert finding.recall_match == RecallMatch.POSSIBLE
    assert "may affect" in finding.title
    assert "check the label" in finding.detail.lower()
    assert "Teva" in finding.detail


def test_unaffected_patient_gets_nothing(db, patient):
    add_med(db, patient, ndc="0378-0221-01")
    assert RecallMonitor(db).process([make_recall()]) == []


def test_finding_records_the_recall_number_and_source(db, patient):
    add_med(db, patient, ndc="0093-1048-01")
    finding = RecallMonitor(db).process([make_recall()])[0]

    assert finding.source_name == "openFDA"
    assert finding.evidence["recall_number"] == "D-0301-2026"
    assert finding.evidence["match_tier"] == "CONFIRMED"


def test_the_same_recall_is_not_reported_twice(db, patient):
    """The worker polls hourly. Without dedupe a caregiver would be told about
    the same recall every hour until they stopped reading alerts."""
    add_med(db, patient, ndc="0093-1048-01")
    monitor = RecallMonitor(db)

    first = monitor.process([make_recall()])
    second = monitor.process([make_recall()])

    assert len(first) == 1
    assert second == []


def test_findings_never_advise_stopping_a_medication(db, patient):
    """The safety boundary, asserted in code."""
    add_med(db, patient, ndc="0093-1048-01")
    finding = RecallMonitor(db).process([make_recall()])[0]

    assert "do not stop" in finding.detail.lower()
    assert "pharmacist" in finding.detail.lower()
