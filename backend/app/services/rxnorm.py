"""Medication name normalization via RxNorm.

WHY THIS EXISTS
---------------
A patient types "tylenol", "Tylenol Extra Strength", or "paracetamol". Those
are the same drug, but as text they are three different things. If the safety
engine compared names, it would miss interactions constantly.

RxNorm is the US standard vocabulary for drugs, maintained by the National
Library of Medicine. It gives every drug concept a stable identifier called an
RXCUI. Once we have that, the safety engine compares identifiers rather than
spelling.

THE CRITICAL DESIGN RULE
------------------------
This service may fail, and the medication must still save.

RxNorm is somebody else's server. It can be slow, down, or return something
unexpected. None of that is a reason to stop a patient recording a medication
they are actually taking. So every failure here returns "no match" rather than
raising - the medication is stored with rxcui = None, and the safety engine
simply has less to work with for that one entry.

This is the same principle as the AI layer: an external service may degrade a
feature, never block a core operation.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Below this, an approximate match is more likely to be wrong than right.
# RxNorm scores are roughly 0-100; a genuine near-miss spelling scores high.
MIN_APPROXIMATE_SCORE = 10.0


@dataclass(frozen=True)
class NormalizationResult:
    """What we learned about a medication name.

    `matched_by` records HOW we matched, which goes into the audit trail. A
    finding based on an approximate match deserves less confidence than one
    based on an exact match, and we must be able to tell them apart later.
    """

    rxcui: str | None
    normalized_name: str | None
    matched_by: str  # "exact" | "approximate" | "none" | "unavailable"

    @property
    def found(self) -> bool:
        return self.rxcui is not None

    @classmethod
    def none(cls, reason: str = "none") -> "NormalizationResult":
        return cls(rxcui=None, normalized_name=None, matched_by=reason)


class RxNormClient:
    """Talks to the RxNorm REST API.

    Written as a class with an injectable httpx client so tests can supply a
    fake transport. Tests that call a real external service are slow, flaky,
    and fail when the network does - so ours never touch the network.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = (base_url or settings.RXNORM_BASE_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.RXNORM_TIMEOUT_SECONDS
        self._client = client

    # ------------------------------------------------------------------ util
    def _get(self, path: str, params: dict) -> dict | None:
        """One GET request. Returns parsed JSON, or None on any failure.

        Every failure mode collapses to None on purpose. The caller does not
        need to care whether RxNorm timed out, returned a 500, or returned
        something that was not JSON - in all cases we simply have no match.
        """
        url = f"{self.base_url}{path}"
        try:
            if self._client is not None:
                response = self._client.get(url, params=params, timeout=self.timeout)
            else:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            logger.warning("RxNorm timed out after %ss for %s", self.timeout, params)
            return None
        except httpx.HTTPError as exc:
            logger.warning("RxNorm request failed: %s", exc)
            return None
        except ValueError:  # malformed JSON
            logger.warning("RxNorm returned a non-JSON response")
            return None

    # --------------------------------------------------------------- lookups
    def _exact_rxcui(self, name: str) -> str | None:
        """Exact name match. Returns {"idGroup": {"rxnormId": ["6809"]}}
        on success, or {"idGroup": {}} when nothing matched."""
        data = self._get("/REST/rxcui.json", {"name": name})
        if not data:
            return None
        ids = data.get("idGroup", {}).get("rxnormId") or []
        return ids[0] if ids else None

    def _approximate_rxcui(self, name: str) -> str | None:
        """Fuzzy match, for typos like 'metformin'.

        Only accepted above MIN_APPROXIMATE_SCORE. A bad guess here is worse
        than no guess: it would attach the patient's entry to the wrong drug,
        and every later safety check would be about a medication they do not
        take.
        """
        data = self._get(
            "/REST/approximateTerm.json", {"term": name, "maxEntries": 1}
        )
        if not data:
            return None
        candidates = data.get("approximateGroup", {}).get("candidate") or []
        if not candidates:
            return None

        best = candidates[0]
        try:
            score = float(best.get("score", 0))
        except (TypeError, ValueError):
            return None

        if score < MIN_APPROXIMATE_SCORE:
            logger.info("RxNorm approximate match for %r scored %.1f - rejected", name, score)
            return None
        return best.get("rxcui")

    def _canonical_name(self, rxcui: str) -> str | None:
        """The official RxNorm name for an identifier."""
        data = self._get(f"/REST/rxcui/{rxcui}/properties.json", {})
        if not data:
            return None
        return data.get("properties", {}).get("name")

    # ------------------------------------------------------------------ main
    def normalize(self, name: str) -> NormalizationResult:
        """Resolve a free-text medication name to an RXCUI.

        Exact match first, then approximate. Never raises.
        """
        name = (name or "").strip()
        if not name:
            return NormalizationResult.none()

        rxcui = self._exact_rxcui(name)
        matched_by = "exact"

        if rxcui is None:
            rxcui = self._approximate_rxcui(name)
            matched_by = "approximate"

        if rxcui is None:
            return NormalizationResult.none()

        canonical = self._canonical_name(rxcui)
        return NormalizationResult(
            rxcui=rxcui,
            normalized_name=canonical or name,
            matched_by=matched_by,
        )


# Default instance used by the application. Tests construct their own with a
# fake transport instead of using this one.
rxnorm_client = RxNormClient()


def normalize_medication_name(name: str) -> NormalizationResult:
    """Convenience wrapper so callers do not have to know about the client."""
    return rxnorm_client.normalize(name)
