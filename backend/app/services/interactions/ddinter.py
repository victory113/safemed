"""Interaction lookups backed by the DDInter dataset in our database.

DDInter is a curated, peer-reviewed drug-drug interaction database published
in Nucleic Acids Research. We import it once (see scripts/import_ddinter.py)
and query our own copy, so lookups are fast, reproducible, and unaffected by
anyone else's uptime.

Citation for the report:
    DDInter: an online drug-drug interaction database towards improving
    clinical decision-making and patient safety. Nucleic Acids Research,
    2022, 50(D1):D1200-D1207.

Licensing note: the download page carries no explicit licence statement, and
the publication describes the resource as open access and freely available
without registration. We use it for non-commercial academic work and cite it.
If that turns out to be unsuitable, the InteractionSource interface lets us
swap in a different dataset without touching the safety engine.
"""
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.enums import Severity
from app.models.interaction import DrugInteraction
from app.services.interactions.base import InteractionHit

# DDInter's wording mapped onto our three-level scale.
#
# "Unknown" means the interaction is documented but its seriousness is not
# established. We map it to MILD so it never escalates to a caregiver on its
# own, and InteractionHit.severity_is_established stays False so the finding
# can say plainly that severity is not established. Silently calling it mild
# would overstate what the source actually says.
LEVEL_TO_SEVERITY: dict[str, Severity] = {
    "major": Severity.SEVERE,
    "moderate": Severity.MODERATE,
    "minor": Severity.MILD,
    "unknown": Severity.MILD,
}


def normalize_key(name: str) -> str:
    """Turn a drug name into the key used for matching."""
    return (name or "").strip().lower()


def canonical_pair(a: str, b: str) -> tuple[str, str]:
    """Order a pair consistently so lookups only check one direction."""
    return (a, b) if a <= b else (b, a)


class DDInterSource:
    """Reads interactions from our imported copy of DDInter."""

    name = "DDInter"

    def __init__(self, db: Session, version: str = "2.0") -> None:
        self._db = db
        self.version = version

    def find_interactions(
        self,
        drug_keys: list[str],
        rxcuis: list[str] | None = None,
    ) -> list[InteractionHit]:
        """Find interactions among a patient's medications.

        Matching happens two ways, and both are needed:

        * **By RXCUI** - the reliable path. DDInter calls aspirin
          "Acetylsalicylic acid"; a patient types "aspirin". Both resolve to
          RXCUI 1191, so the identifiers match where the names never would.
        * **By name** - the fallback, for drugs whose RXCUI we could not
          resolve, or medications a patient entered that RxNorm did not
          recognise.

        Running both and merging means an unresolved drug degrades to
        name-matching instead of silently dropping out of safety checking.
        """
        keys = sorted({normalize_key(k) for k in drug_keys if normalize_key(k)})
        ids = sorted({str(r).strip() for r in (rxcuis or []) if str(r).strip()})

        if len(keys) < 2 and len(ids) < 2:
            return []

        conditions = []
        if len(keys) >= 2:
            conditions.append(
                and_(
                    DrugInteraction.drug_a_key.in_(keys),
                    DrugInteraction.drug_b_key.in_(keys),
                )
            )
        if len(ids) >= 2:
            conditions.append(
                and_(
                    DrugInteraction.drug_a_rxcui.in_(ids),
                    DrugInteraction.drug_b_rxcui.in_(ids),
                )
            )

        stmt = select(DrugInteraction).where(
            or_(*conditions),
            DrugInteraction.source_version == self.version,
        )
        rows = self._db.execute(stmt).scalars().all()

        hits: list[InteractionHit] = []
        seen: set[tuple[str, str]] = set()

        for row in rows:
            pair = canonical_pair(row.drug_a_key, row.drug_b_key)
            if pair in seen:
                continue
            seen.add(pair)

            severity = LEVEL_TO_SEVERITY.get(row.level.strip().lower(), Severity.MILD)
            hits.append(
                InteractionHit(
                    drug_a_key=row.drug_a_key,
                    drug_b_key=row.drug_b_key,
                    drug_a_name=row.drug_a_name,
                    drug_b_name=row.drug_b_name,
                    level=row.level,
                    severity=severity,
                    source_name=self.name,
                    source_version=row.source_version,
                )
            )

        # Most serious first, so the caller never has to sort.
        order = {Severity.SEVERE: 0, Severity.MODERATE: 1, Severity.MILD: 2}
        hits.sort(key=lambda h: (order[h.severity], h.drug_a_name))
        return hits

    def count(self) -> int:
        """How many interactions are loaded. Used by the status panel."""
        stmt = select(DrugInteraction).where(
            DrugInteraction.source_version == self.version
        )
        return len(self._db.execute(stmt).scalars().all())
