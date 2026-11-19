"""FDA recall monitoring with tiered matching.

THE PROBLEM THIS SOLVES
-----------------------
A recall is not issued against "metformin". It is issued against one
manufacturer's specific lots of one specific product. Most people taking
metformin are completely unaffected by any given metformin recall.

If SafeMed told every metformin patient "your medication has been recalled",
it would be wrong most of the time. Two false alarms and people stop reading
alerts - which makes the system worse than useless, because it also destroys
the credibility of the true alerts.

We sampled 100 recent recalls from openFDA: 61 carried an NDC (the product
code identifying the manufacturer), and 39 carried no structured identifier at
all. So we cannot simply match on identifiers, and we must not simply match on
names either.

TIERED MATCHING
---------------
CONFIRMED  the recall names the exact product the patient holds (NDC match).
           "Your medication is affected."

POSSIBLE   same drug, but we cannot tell whose product the patient has -
           either they never entered an NDC, or the recall carries none.
           "Check your bottle: does it say Teva?"

No match   different drug entirely. Say nothing.

The distinction is the whole feature. It is the difference between an alert a
caregiver trusts and one they learn to ignore.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

import httpx

from app.models.enums import RecallMatch, Severity
from app.models.medication import Medication

logger = logging.getLogger(__name__)

OPENFDA_URL = "https://api.fda.gov/drug/enforcement.json"

# Words that appear in nearly every product description and would match far
# too much if treated as a drug name.
_STOPWORDS = {
    "tablet", "tablets", "capsule", "capsules", "oral", "solution", "usp",
    "injection", "mg", "ml", "count", "bottle", "bottles", "extended",
    "release", "hydrochloride", "sodium", "and", "the", "for", "rx", "only",
}


@dataclass(frozen=True)
class RecallRecord:
    """One FDA recall, reduced to the fields we actually use."""

    recall_number: str
    classification: str          # "Class I" | "Class II" | "Class III"
    recalling_firm: str
    product_description: str
    reason_for_recall: str
    report_date: str
    code_info: str = ""
    product_ndcs: list[str] = field(default_factory=list)
    rxcuis: list[str] = field(default_factory=list)
    generic_names: list[str] = field(default_factory=list)
    brand_names: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, raw: dict) -> "RecallRecord":
        openfda = raw.get("openfda") or {}
        return cls(
            recall_number=raw.get("recall_number", ""),
            classification=raw.get("classification", ""),
            recalling_firm=raw.get("recalling_firm", ""),
            product_description=raw.get("product_description", ""),
            reason_for_recall=raw.get("reason_for_recall", ""),
            report_date=raw.get("report_date", ""),
            code_info=raw.get("code_info", "") or "",
            product_ndcs=list(openfda.get("product_ndc") or []),
            rxcuis=list(openfda.get("rxcui") or []),
            generic_names=[n.lower() for n in (openfda.get("generic_name") or [])],
            brand_names=[n.lower() for n in (openfda.get("brand_name") or [])],
        )


def ndc_product_code(ndc: str | None) -> str | None:
    """Reduce an NDC to its labeler-product portion, or None if unsure.

    A bottle shows something like 0093-1048-01: labeler (manufacturer),
    product, package size. openFDA publishes recalls at labeler-product level
    (0093-1048), so we compare on that and ignore the package segment -
    otherwise a 30-count bottle would not match a recall of the 90-count.

    Segments are variable length - 5-4-2, 4-4-2 and 5-3-2 all exist - so an
    NDC written without separators is genuinely ambiguous. We return None
    rather than guess.

    That matters: an unparseable code means the medication falls back to the
    POSSIBLE tier ("check your bottle") instead of being declared CONFIRMED on
    the strength of a guess. Wrongly telling someone their exact product was
    recalled is the failure mode this whole feature exists to avoid.
    """
    if not ndc:
        return None
    parts = [p for p in re.split(r"[-\s]+", ndc.strip()) if p]
    # Real segments are never longer than 5 characters. Anything longer means
    # the separators are missing and we cannot tell where labeler ends.
    if len(parts) >= 2 and all(len(p) <= 5 for p in parts[:2]):
        return f"{parts[0].lstrip('0') or '0'}-{parts[1].lstrip('0') or '0'}"
    return None


def _normalise_ndc_list(ndcs: list[str]) -> set[str]:
    out = set()
    for n in ndcs:
        code = ndc_product_code(n)
        if code:
            out.add(code)
    return out


def _recall_text_tokens(recall: RecallRecord) -> set[str]:
    """Words from the recall that might name a drug."""
    text = " ".join(
        [recall.product_description, *recall.generic_names, *recall.brand_names]
    ).lower()
    tokens = set(re.findall(r"[a-z]{4,}", text))
    return tokens - _STOPWORDS


def match_medication(recall: RecallRecord, medication: Medication) -> RecallMatch | None:
    """Decide how (or whether) this recall affects this medication."""
    # --- Tier 1: the exact product ---------------------------------------
    patient_code = ndc_product_code(medication.ndc)
    recall_codes = _normalise_ndc_list(recall.product_ndcs)
    if patient_code and recall_codes:
        if patient_code in recall_codes:
            return RecallMatch.CONFIRMED
        # Both sides identified, and they differ: this patient holds a
        # different manufacturer's product. Saying nothing is correct.
        return None

    # --- Tier 2: same drug, manufacturer unknown -------------------------
    tokens = _recall_text_tokens(recall)
    for name in (medication.normalized_name, medication.name_entered):
        if not name:
            continue
        for word in re.findall(r"[a-z]{4,}", name.lower()):
            if word in _STOPWORDS:
                continue
            if word in tokens:
                return RecallMatch.POSSIBLE
    return None


def severity_for(match: RecallMatch, classification: str) -> Severity:
    """How loudly to speak.

    FDA classes: I is a reasonable probability of serious harm, II is
    temporary or reversible, III is unlikely to cause harm. A confirmed match
    always outranks a possible one at the same class, because certainty about
    the product is what makes an alert actionable.
    """
    cls = (classification or "").strip().lower()
    is_class_one = "class i" in cls and "class ii" not in cls and "class iii" not in cls

    if match == RecallMatch.CONFIRMED:
        return Severity.SEVERE if is_class_one else Severity.MODERATE
    return Severity.MODERATE if is_class_one else Severity.MILD


class OpenFDARecallClient:
    """Reads recalls from openFDA.

    Like RxNorm, every failure returns an empty list rather than raising. The
    worker must survive openFDA being down - a missed polling cycle is
    recoverable, a crashed worker is not.
    """

    def __init__(self, timeout: float = 20.0, client: httpx.Client | None = None) -> None:
        self.timeout = timeout
        self._client = client

    def _get(self, params: dict) -> list[dict]:
        try:
            if self._client is not None:
                response = self._client.get(OPENFDA_URL, params=params, timeout=self.timeout)
            else:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(OPENFDA_URL, params=params)
            if response.status_code == 404:
                return []           # openFDA's way of saying "no matches"
            response.raise_for_status()
            return response.json().get("results", [])
        except httpx.HTTPError as exc:
            logger.warning("openFDA request failed: %s", exc)
            return []
        except ValueError:
            logger.warning("openFDA returned a non-JSON response")
            return []

    def recent(self, days: int = 30, limit: int = 100) -> list[RecallRecord]:
        since = (date.today() - timedelta(days=days)).strftime("%Y%m%d")
        until = date.today().strftime("%Y%m%d")
        raw = self._get({
            "search": f"report_date:[{since}+TO+{until}]",
            "limit": limit,
        })
        return [RecallRecord.from_api(r) for r in raw]

    def search_drug(self, drug_name: str, limit: int = 10) -> list[RecallRecord]:
        """Recalls mentioning a drug, any date.

        Used by the demo: real recalls are rare, so we cannot wait for one to
        appear during a presentation.
        """
        safe = re.sub(r"[^A-Za-z0-9 ]", "", drug_name).strip().replace(" ", "+")
        if not safe:
            return []
        raw = self._get({
            "search": f'product_description:"{safe}"',
            "limit": limit,
        })
        return [RecallRecord.from_api(r) for r in raw]
