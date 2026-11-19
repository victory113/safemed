"""Tests for the safety engine.

This is the component that decides whether a caregiver gets alerted, so it is
tested harder than anything else. The interaction data is supplied by a fake
source rather than the real dataset, so these tests are fast and do not depend
on an import having been run.
"""
import pytest

from app.models.enums import (
    FindingStatus,
    FindingType,
    MedicationStatus,
    Severity,
)
from app.models.medication import Medication
from app.services.interactions.base import InteractionHit
from app.services.safety_engine import SafetyEngine, make_dedupe_key


class FakeInteractionSource:
    """An InteractionSource that returns whatever we tell it to.

    Writing this took five lines and removes any dependence on the real
    dataset. It also proves the Protocol works: the engine accepts this
    without knowing anything about DDInter.
    """

    name = "FakeSource"
    version = "test-1"

    def __init__(self, hits: list[InteractionHit] | None = None) -> None:
        self._hits = hits or []
        self.calls: list[tuple[list[str], list[str] | None]] = []

    def find_interactions(self, drug_keys, rxcuis=None):
        self.calls.append((drug_keys, rxcuis))
        return self._hits


def hit(a="aspirin", b="warfarin", level="Major", severity=Severity.SEVERE,
        rxcui_a="1191", rxcui_b="11289", name_a="Acetylsalicylic acid",
        name_b="Warfarin") -> InteractionHit:
    return InteractionHit(
        drug_a_key=a, drug_b_key=b,
        drug_a_name=name_a, drug_b_name=name_b,
        drug_a_rxcui=rxcui_a, drug_b_rxcui=rxcui_b,
        level=level, severity=severity,
        source_name="FakeSource", source_version="test-1",
    )


def add_med(db, patient, name, rxcui=None, normalized=None,
            status=MedicationStatus.ACTIVE):
    med = Medication(
        patient_id=patient.id,
        name_entered=name,
        normalized_name=normalized or name,
        rxcui=rxcui,
        status=status,
    )
    db.add(med)
    db.flush()
    return med


# ---------------------------------------------------------------- findings

def test_creates_a_finding_for_an_interaction(db, patient):
    add_med(db, patient, "aspirin", rxcui="1191")
    add_med(db, patient, "warfarin", rxcui="11289")

    engine = SafetyEngine(db, FakeInteractionSource([hit()]))
    result = engine.evaluate_patient(patient.id)

    assert len(result.created) == 1
    finding = result.created[0]
    assert finding.finding_type == FindingType.INTERACTION
    assert finding.severity == Severity.SEVERE
    assert finding.status == FindingStatus.OPEN


def test_finding_records_its_source_and_version(db, patient):
    """Provenance is what makes a finding auditable. Without it we are just
    asserting things."""
    add_med(db, patient, "aspirin", rxcui="1191")
    add_med(db, patient, "warfarin", rxcui="11289")

    engine = SafetyEngine(db, FakeInteractionSource([hit()]))
    finding = engine.evaluate_patient(patient.id).created[0]

    assert finding.source_name == "FakeSource"
    assert finding.source_version == "test-1"
    assert finding.evidence["level"] == "Major"


def test_finding_links_the_patients_own_medications(db, patient):
    """The source calls it "Acetylsalicylic acid"; the patient typed
    "aspirin". The finding must point at the patient's own record, or the UI
    cannot highlight which of their entries is involved."""
    aspirin = add_med(db, patient, "aspirin", rxcui="1191")
    warfarin = add_med(db, patient, "warfarin", rxcui="11289")

    engine = SafetyEngine(db, FakeInteractionSource([hit()]))
    finding = engine.evaluate_patient(patient.id).created[0]

    linked = {m.id for m in finding.medications}
    assert linked == {aspirin.id, warfarin.id}


def test_ai_explanation_is_empty_until_the_ai_layer_runs(db, patient):
    """A finding must be complete and displayable before AI touches it."""
    add_med(db, patient, "aspirin", rxcui="1191")
    add_med(db, patient, "warfarin", rxcui="11289")

    engine = SafetyEngine(db, FakeInteractionSource([hit()]))
    finding = engine.evaluate_patient(patient.id).created[0]

    assert finding.ai_explanation is None
    assert finding.detail          # stands on its own
    assert "pharmacist" in finding.detail.lower()


# ------------------------------------------------------------ deduplication

def test_running_twice_does_not_duplicate_a_finding(db, patient):
    """The background worker re-evaluates on a timer. Without dedupe the same
    interaction would be reported every hour until nobody read the alerts."""
    add_med(db, patient, "aspirin", rxcui="1191")
    add_med(db, patient, "warfarin", rxcui="11289")
    source = FakeInteractionSource([hit()])

    first = SafetyEngine(db, source).evaluate_patient(patient.id)
    second = SafetyEngine(db, source).evaluate_patient(patient.id)

    assert len(first.created) == 1
    assert len(second.created) == 0
    assert len(second.existing) == 1


def test_dedupe_key_ignores_time(db, patient):
    """Keys are built from what the finding is about, never from when it was
    found - otherwise every run would produce a 'new' concern."""
    a = make_dedupe_key(patient.id, "interaction", "aspirin", "warfarin")
    b = make_dedupe_key(patient.id, "interaction", "aspirin", "warfarin")
    assert a == b


def test_dedupe_key_differs_per_patient(db, patient):
    import uuid

    other = uuid.uuid4()
    assert make_dedupe_key(patient.id, "interaction", "a", "b") != make_dedupe_key(
        other, "interaction", "a", "b"
    )


# ----------------------------------------------------------------- severity

def test_unknown_severity_is_stated_not_implied(db, patient):
    """When the source documents an interaction but not how serious it is, the
    finding must say so rather than quietly presenting it as mild."""
    add_med(db, patient, "ibuprofen", rxcui="5640")
    add_med(db, patient, "naproxen", rxcui="7258")

    source = FakeInteractionSource([
        hit(a="ibuprofen", b="naproxen", level="Unknown", severity=Severity.MILD,
            rxcui_a="5640", rxcui_b="7258", name_a="Ibuprofen", name_b="Naproxen")
    ])
    finding = SafetyEngine(db, source).evaluate_patient(patient.id).created[0]

    assert "not established" in finding.detail.lower()
    assert finding.evidence["severity_established"] is False


# ------------------------------------------------------------- scope rules

def test_stopped_medications_are_not_evaluated(db, patient):
    """A medication the patient stopped taking cannot interact with anything."""
    add_med(db, patient, "aspirin", rxcui="1191")
    add_med(db, patient, "warfarin", rxcui="11289", status=MedicationStatus.STOPPED)

    source = FakeInteractionSource([hit()])
    SafetyEngine(db, source).evaluate_patient(patient.id)

    # Only the active medication should have been offered to the source.
    names, rxcuis = source.calls[0]
    assert "warfarin" not in names
    assert "11289" not in (rxcuis or [])


def test_both_names_and_rxcuis_are_offered_to_the_source(db, patient):
    """A medication RxNorm could not resolve must still be checked by name."""
    add_med(db, patient, "aspirin", rxcui="1191")
    add_med(db, patient, "contrast media", rxcui=None)

    source = FakeInteractionSource([])
    SafetyEngine(db, source).evaluate_patient(patient.id)

    names, rxcuis = source.calls[0]
    assert "contrast media" in names
    assert rxcuis == ["1191"]


def test_no_medications_produces_no_findings(db, patient):
    result = SafetyEngine(db, FakeInteractionSource([])).evaluate_patient(patient.id)
    assert result.created == []


# ---------------------------------------------------------- duplicate check

def test_detects_the_same_drug_entered_twice(db, patient):
    add_med(db, patient, "Metformin", rxcui="6809")
    add_med(db, patient, "metformin 500mg", rxcui="6809")

    result = SafetyEngine(db, FakeInteractionSource([])).evaluate_patient(patient.id)

    duplicates = [f for f in result.created if f.finding_type == FindingType.DUPLICATE_THERAPY]
    assert len(duplicates) == 1
    assert len(duplicates[0].medications) == 2


def test_two_different_drugs_are_not_a_duplicate(db, patient):
    add_med(db, patient, "Metformin", rxcui="6809")
    add_med(db, patient, "Lisinopril", rxcui="29046")

    result = SafetyEngine(db, FakeInteractionSource([])).evaluate_patient(patient.id)

    assert not [f for f in result.created if f.finding_type == FindingType.DUPLICATE_THERAPY]
