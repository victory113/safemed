"""Tests for recall matching.

The tiering rules are the point of this feature, so they get the most
attention. A recall system that cries wolf is worse than none at all.
"""
import httpx
import pytest

from app.models.enums import MedicationStatus, RecallMatch, Severity
from app.models.medication import Medication
from app.services.recalls import (
    OpenFDARecallClient,
    RecallRecord,
    match_medication,
    ndc_product_code,
    severity_for,
)


def make_recall(**kwargs) -> RecallRecord:
    defaults = dict(
        recall_number="D-0301-2026",
        classification="Class II",
        recalling_firm="Teva Pharmaceuticals",
        product_description="Metformin Hydrochloride Extended-Release Tablets, USP, 500 mg",
        reason_for_recall="Failed dissolution specifications",
        report_date="20260301",
        product_ndcs=["0093-1048"],
        generic_names=["metformin hydrochloride"],
    )
    defaults.update(kwargs)
    return RecallRecord(**defaults)


def make_med(patient, name="Metformin", ndc=None, normalized="metformin"):
    return Medication(
        patient_id=patient.id,
        name_entered=name,
        normalized_name=normalized,
        ndc=ndc,
        status=MedicationStatus.ACTIVE,
    )


# ------------------------------------------------------------ NDC parsing

def test_ndc_reduces_to_labeler_and_product():
    """A 30-count bottle must match a recall of the 90-count: the package
    segment is not part of the identity of the product."""
    assert ndc_product_code("0093-1048-01") == "93-1048"
    assert ndc_product_code("0093-1048-10") == "93-1048"


def test_ambiguous_ndc_is_refused_rather_than_guessed():
    """NDC segments are variable length (5-4-2, 4-4-2, 5-3-2 all exist), so a
    code written without separators cannot be split reliably.

    We return None, which pushes the medication down to the POSSIBLE tier.
    Telling someone their exact product was recalled on the strength of a
    guess is precisely the failure this feature exists to prevent.
    """
    assert ndc_product_code("00931048 01") is None
    assert ndc_product_code("0093104801") is None


def test_ndc_of_nothing_is_nothing():
    assert ndc_product_code(None) is None
    assert ndc_product_code("") is None


# ------------------------------------------------------------- the tiers

def test_exact_product_is_confirmed(db, patient):
    med = make_med(patient, ndc="0093-1048-01")
    assert match_medication(make_recall(), med) == RecallMatch.CONFIRMED


def test_same_drug_without_an_ndc_is_only_possible(db, patient):
    """The patient never entered a manufacturer code, so we genuinely do not
    know. Saying "your medication is recalled" would be a guess."""
    med = make_med(patient, ndc=None)
    assert match_medication(make_recall(), med) == RecallMatch.POSSIBLE


def test_different_manufacturer_is_not_a_match(db, patient):
    """This is the false alarm we exist to prevent. The patient holds a
    different company's metformin; the recall does not concern them."""
    med = make_med(patient, ndc="0378-0221-01")
    assert match_medication(make_recall(), med) is None


def test_unrelated_drug_is_not_a_match(db, patient):
    med = make_med(patient, name="Lisinopril", normalized="lisinopril")
    assert match_medication(make_recall(), med) is None


def test_recall_without_identifiers_still_matches_by_name(db, patient):
    """39 of 100 sampled recalls carried no NDC at all. Those must not be
    invisible - they fall back to the POSSIBLE tier."""
    recall = make_recall(product_ndcs=[], generic_names=[])
    med = make_med(patient, ndc="0093-1048-01")
    assert match_medication(recall, med) == RecallMatch.POSSIBLE


def test_dosage_words_do_not_cause_false_matches(db, patient):
    """"Tablets" appears in almost every product description. If common words
    counted as drug names, every patient would match every recall."""
    med = make_med(patient, name="Tablets", normalized="tablets")
    assert match_medication(make_recall(), med) is None


# ------------------------------------------------------------- severity

def test_confirmed_class_one_is_severe():
    assert severity_for(RecallMatch.CONFIRMED, "Class I") == Severity.SEVERE


def test_confirmed_class_two_is_moderate():
    assert severity_for(RecallMatch.CONFIRMED, "Class II") == Severity.MODERATE


def test_possible_never_outranks_confirmed_at_the_same_class():
    for cls in ("Class I", "Class II", "Class III"):
        confirmed = severity_for(RecallMatch.CONFIRMED, cls)
        possible = severity_for(RecallMatch.POSSIBLE, cls)
        order = {Severity.SEVERE: 0, Severity.MODERATE: 1, Severity.MILD: 2}
        assert order[confirmed] <= order[possible]


def test_class_three_possible_is_mild():
    assert severity_for(RecallMatch.POSSIBLE, "Class III") == Severity.MILD


# ------------------------------------------------- the client degrades well

def test_client_returns_empty_when_openfda_is_down():
    """The worker must survive openFDA being unavailable. A missed polling
    cycle is recoverable; a crashed worker is not."""
    def handler(request):
        raise httpx.ConnectError("no route to host", request=request)

    client = OpenFDARecallClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.recent() == []


def test_client_treats_404_as_no_results():
    """openFDA answers a search with no matches using 404, not an empty list."""
    def handler(request):
        return httpx.Response(404, json={"error": {"code": "NOT_FOUND"}})

    client = OpenFDARecallClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.recent() == []


def test_client_parses_a_real_shaped_response():
    def handler(request):
        return httpx.Response(200, json={"results": [{
            "recall_number": "D-0301-2026",
            "classification": "Class II",
            "recalling_firm": "Teva",
            "product_description": "Metformin tablets",
            "reason_for_recall": "Failed dissolution",
            "report_date": "20260301",
            "openfda": {"product_ndc": ["0093-1048"], "rxcui": ["860975"],
                        "generic_name": ["METFORMIN HYDROCHLORIDE"]},
        }]})

    client = OpenFDARecallClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    recalls = client.recent()
    assert len(recalls) == 1
    assert recalls[0].product_ndcs == ["0093-1048"]
    assert recalls[0].generic_names == ["metformin hydrochloride"]
