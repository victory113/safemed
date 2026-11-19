"""The interface every interaction data source must satisfy.

WHY THIS EXISTS
---------------
Our instructor's feedback was explicit: verify the external data is usable,
and if reliable interaction data becomes hard to obtain, do not let that block
the project.

This file is the answer to that. The safety engine depends on this interface,
not on DDInter. If DDInter became unavailable or its licensing turned out to
be unsuitable, we write a second class satisfying the same interface - backed
by the ONC high-priority interaction list plus FDA label text - and change one
line of configuration. No other code moves.

That is the difference between a risk and a blocker.
"""
from dataclasses import dataclass
from typing import Protocol

from app.models.enums import Severity


@dataclass(frozen=True)
class InteractionHit:
    """One interaction found between two of a patient's medications."""

    drug_a_key: str
    drug_b_key: str
    drug_a_name: str
    drug_b_name: str
    # RxNorm ids where known. The source names a drug its own way
    # ("Acetylsalicylic acid"); the patient entered "aspirin". The id is the
    # only reliable way to link a hit back to the patient's own record.
    drug_a_rxcui: str | None
    drug_b_rxcui: str | None
    level: str                 # the source's own wording
    severity: Severity         # mapped to our scale
    source_name: str
    source_version: str

    @property
    def severity_is_established(self) -> bool:
        """False when the source documents the interaction but not how serious
        it is. The finding must say so rather than implying a severity we do
        not actually have."""
        return self.level.strip().lower() != "unknown"


class InteractionSource(Protocol):
    """What the safety engine requires of an interaction dataset.

    A Protocol is Python's way of saying "any class with these methods will
    do" - no inheritance needed. It keeps the engine honest: it can only use
    what is declared here.
    """

    name: str
    version: str

    def find_interactions(
        self,
        drug_keys: list[str],
        rxcuis: list[str] | None = None,
    ) -> list[InteractionHit]:
        """Return every documented interaction among the given drugs.

        `drug_keys` are lowercased generic drug names; `rxcuis` are RxNorm
        identifiers where known. An implementation should prefer identifiers
        and fall back to names, so a drug that failed to normalise is still
        checked rather than silently skipped.

        Each pair must be returned at most once, regardless of input order.
        """
        ...
