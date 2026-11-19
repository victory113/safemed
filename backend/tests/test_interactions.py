"""Tests for interaction lookup.

These use a handful of hand-written rows rather than the real dataset, so they
are fast and do not depend on an import having been run.
"""
import pytest

from app.models.enums import Severity
from app.models.interaction import DrugInteraction
from app.services.interactions.ddinter import (
    DDInterSource,
    canonical_pair,
    normalize_key,
)


@pytest.fixture
def loaded(db):
    """A few interactions, stored in canonical pair order.

    The first row deliberately uses DDInter's own name for aspirin,
    "Acetylsalicylic acid", with its RXCUI attached - that is the real case
    that name-only matching missed.
    """
    rows = [
        # key_a, key_b, name_a, name_b, level, rxcui_a, rxcui_b
        ("acetylsalicylic acid", "warfarin", "Acetylsalicylic acid", "Warfarin",
         "Major", "1191", "11289"),
        ("contrast media", "metformin", "Contrast media", "Metformin",
         "Moderate", None, "6809"),
        ("ibuprofen", "naproxen", "Ibuprofen", "Naproxen",
         "Unknown", "5640", "7258"),
    ]
    for a, b, na, nb, level, ra, rb in rows:
        key_a, key_b = canonical_pair(a, b)
        if normalize_key(na) == key_a:
            display_a, display_b, rx_a, rx_b = na, nb, ra, rb
        else:
            display_a, display_b, rx_a, rx_b = nb, na, rb, ra
        db.add(
            DrugInteraction(
                drug_a_key=key_a,
                drug_b_key=key_b,
                drug_a_name=display_a,
                drug_b_name=display_b,
                drug_a_rxcui=rx_a,
                drug_b_rxcui=rx_b,
                level=level,
                source_name="DDInter",
                source_version="2.0",
            )
        )
    db.flush()
    return DDInterSource(db, version="2.0")


# ------------------------------------------------------------ pair ordering

def test_canonical_pair_is_order_independent():
    assert canonical_pair("warfarin", "aspirin") == canonical_pair("aspirin", "warfarin")


def test_normalize_key_lowercases_and_trims():
    assert normalize_key("  Warfarin  ") == "warfarin"


# ----------------------------------------------------------------- lookups

def test_finds_a_known_interaction(loaded):
    hits = loaded.find_interactions(["warfarin", "acetylsalicylic acid"])
    assert len(hits) == 1
    assert hits[0].severity == Severity.SEVERE
    assert hits[0].level == "Major"
    assert hits[0].source_name == "DDInter"
    assert hits[0].source_version == "2.0"


def test_order_of_input_does_not_matter(loaded):
    """A patient's medication list has no meaningful order."""
    forward = loaded.find_interactions(["warfarin", "acetylsalicylic acid"])
    backward = loaded.find_interactions(["acetylsalicylic acid", "warfarin"])
    assert len(forward) == len(backward) == 1


def test_matching_is_case_insensitive(loaded):
    assert len(loaded.find_interactions(["Warfarin", "ACETYLSALICYLIC ACID"])) == 1


def test_unrelated_drugs_produce_nothing(loaded):
    assert loaded.find_interactions(["paracetamol", "vitamin c"]) == []


def test_a_single_drug_cannot_interact(loaded):
    assert loaded.find_interactions(["warfarin"]) == []


def test_empty_list_is_safe(loaded):
    assert loaded.find_interactions([]) == []


def test_finds_every_pair_in_a_larger_list(loaded):
    hits = loaded.find_interactions(
        ["warfarin", "acetylsalicylic acid", "ibuprofen", "naproxen"]
    )
    assert len(hits) == 2


def test_results_are_most_serious_first(loaded):
    hits = loaded.find_interactions(
        ["warfarin", "acetylsalicylic acid", "ibuprofen", "naproxen"]
    )
    assert hits[0].severity == Severity.SEVERE
    assert hits[-1].severity == Severity.MILD


# ---------------------------------------------------------------- severity

def test_unknown_level_does_not_claim_a_severity(loaded):
    """DDInter documents the interaction but not how serious it is. We must
    not present that as a mild interaction without saying so."""
    hits = loaded.find_interactions(["ibuprofen", "naproxen"])
    assert hits[0].level == "Unknown"
    assert hits[0].severity == Severity.MILD
    assert hits[0].severity_is_established is False


def test_major_is_established(loaded):
    hits = loaded.find_interactions(["warfarin", "acetylsalicylic acid"])
    assert hits[0].severity_is_established is True


def test_a_different_version_is_not_returned(db, loaded):
    """Findings must cite the version they came from, so a lookup pinned to
    2.0 must never pick up rows imported as 3.0."""
    other = DDInterSource(db, version="3.0")
    assert other.find_interactions(["warfarin", "acetylsalicylic acid"]) == []


# ------------------------------------------------------- matching by RXCUI

def test_rxcui_matching_finds_what_names_would_miss(loaded):
    """The bug this whole mechanism exists for.

    A patient types "aspirin". DDInter stores "Acetylsalicylic acid". The
    names never match, so name-only lookup returned nothing for a Major
    interaction. Both resolve to RXCUI 1191, so identifiers find it.
    """
    by_name = loaded.find_interactions(["aspirin", "warfarin"])
    assert by_name == []

    by_rxcui = loaded.find_interactions(["aspirin", "warfarin"], rxcuis=["1191", "11289"])
    assert len(by_rxcui) == 1
    assert by_rxcui[0].severity == Severity.SEVERE


def test_name_and_rxcui_results_are_not_duplicated(loaded):
    """A pair matching both ways must still be reported once."""
    hits = loaded.find_interactions(
        ["warfarin", "acetylsalicylic acid"], rxcuis=["1191", "11289"]
    )
    assert len(hits) == 1


def test_unresolved_drug_still_matches_by_name(loaded):
    """Contrast media has no RXCUI in our data. It must not vanish from
    safety checking just because normalisation failed."""
    hits = loaded.find_interactions(["contrast media", "metformin"], rxcuis=["6809"])
    assert len(hits) == 1
    assert hits[0].severity == Severity.MODERATE


def test_a_single_rxcui_cannot_interact(loaded):
    assert loaded.find_interactions([], rxcuis=["1191"]) == []
