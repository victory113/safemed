"""The safety engine - the heart of SafeMed.

Given a patient's medication list, it produces persisted SafetyFinding
records. Everything else in the system either feeds this or reacts to it.

THE RULE THIS FILE EXISTS TO ENFORCE
------------------------------------
Nothing here calls an AI model. Every finding comes from authoritative data
evaluated by fixed rules, and every finding records which dataset and which
version produced it. That is what makes a finding reproducible and auditable.

The AI layer runs afterwards and only rewrites a finished finding into plain
language. If it is unavailable, the finding still stands - it simply displays
its raw source text instead.

DEDUPLICATION
-------------
Every finding carries a dedupe_key derived from what it is about, not when it
was found. The background worker re-evaluates patients on a timer, so without
this the same interaction would be reported every single hour until the
caregiver stopped reading alerts entirely.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import FindingStatus, FindingType, MedicationStatus, Severity
from app.models.medication import Medication
from app.models.safety import SafetyFinding
from app.services.interactions.base import InteractionSource
from app.services.interactions.ddinter import DDInterSource, normalize_key


@dataclass
class EvaluationResult:
    """What one evaluation run produced."""

    created: list[SafetyFinding]
    existing: list[SafetyFinding]

    @property
    def total(self) -> int:
        return len(self.created) + len(self.existing)


def make_dedupe_key(patient_id: UUID, kind: str, *parts: str) -> str:
    """A stable identifier for 'this specific concern, for this patient'.

    Built from the subject of the finding only - never from a timestamp - so
    re-running the engine recognises a concern it has already reported.
    """
    raw = "|".join([str(patient_id), kind, *(p.strip().lower() for p in parts if p)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


def _medication_keys(medications: list[Medication]) -> tuple[list[str], list[str]]:
    """Pull out the two things the interaction source can match on.

    Names AND identifiers, because a medication RxNorm could not resolve must
    still be checked by name rather than silently dropping out.
    """
    names, rxcuis = [], []
    for med in medications:
        name = med.normalized_name or med.name_entered
        if name:
            names.append(normalize_key(name))
        if med.rxcui:
            rxcuis.append(med.rxcui)
    return names, rxcuis


def _index_by_key(medications: list[Medication]) -> dict[str, Medication]:
    index: dict[str, Medication] = {}
    for med in medications:
        for value in (med.normalized_name, med.name_entered):
            if value:
                index.setdefault(normalize_key(value), med)
        if med.rxcui:
            index.setdefault(med.rxcui, med)
    return index


class SafetyEngine:
    """Evaluates a patient's medications and persists what it finds."""

    def __init__(self, db: Session, interaction_source: InteractionSource | None = None) -> None:
        self._db = db
        # Defaults to DDInter, but any InteractionSource will do. This is the
        # seam that lets us swap datasets without touching this file.
        self._interactions = interaction_source or DDInterSource(db)

    # ------------------------------------------------------------- helpers
    def _active_medications(self, patient_id: UUID) -> list[Medication]:
        stmt = select(Medication).where(
            Medication.patient_id == patient_id,
            Medication.status == MedicationStatus.ACTIVE,
        )
        return list(self._db.execute(stmt).scalars().all())

    def _existing(self, dedupe_key: str) -> SafetyFinding | None:
        stmt = select(SafetyFinding).where(SafetyFinding.dedupe_key == dedupe_key)
        return self._db.execute(stmt).scalar_one_or_none()

    # ----------------------------------------------------------- the checks
    def _check_interactions(
        self, patient_id: UUID, medications: list[Medication], now: datetime
    ) -> tuple[list[SafetyFinding], list[SafetyFinding]]:
        created: list[SafetyFinding] = []
        existing: list[SafetyFinding] = []

        names, rxcuis = _medication_keys(medications)
        hits = self._interactions.find_interactions(names, rxcuis=rxcuis)
        index = _index_by_key(medications)

        for hit in hits:
            key = make_dedupe_key(
                patient_id, "interaction", hit.drug_a_key, hit.drug_b_key
            )
            found = self._existing(key)
            if found is not None:
                existing.append(found)
                continue

            # Say plainly when the source documents an interaction but not how
            # serious it is. Presenting it as "mild" would overstate the data.
            if hit.severity_is_established:
                detail = (
                    f"{hit.source_name} records a potential interaction between "
                    f"{hit.drug_a_name} and {hit.drug_b_name}, rated {hit.level}."
                )
            else:
                detail = (
                    f"{hit.source_name} records a potential interaction between "
                    f"{hit.drug_a_name} and {hit.drug_b_name}. The severity of "
                    f"this interaction is not established in the source data."
                )

            detail += (
                " Discuss this with your pharmacist or healthcare provider. "
                "Do not stop or change a medication based on this message."
            )

            finding = SafetyFinding(
                patient_id=patient_id,
                finding_type=FindingType.INTERACTION,
                severity=hit.severity,
                status=FindingStatus.OPEN,
                title=f"Potential interaction: {hit.drug_a_name} and {hit.drug_b_name}",
                detail=detail,
                source_name=hit.source_name,
                source_version=hit.source_version,
                evidence={
                    "level": hit.level,
                    "severity_established": hit.severity_is_established,
                    "drug_a": hit.drug_a_name,
                    "drug_b": hit.drug_b_name,
                },
                dedupe_key=key,
                detected_at=now,
            )

            # Link the patient's own medications to the finding, so the UI can
            # show which of THEIR entries are involved.
            #
            # Match on the RxNorm id first. The source calls a drug
            # "Acetylsalicylic acid" while the patient typed "aspirin" - the
            # names never match, but the ids do. The name key is the fallback
            # for drugs that never resolved.
            for rxcui, drug_key in (
                (hit.drug_a_rxcui, hit.drug_a_key),
                (hit.drug_b_rxcui, hit.drug_b_key),
            ):
                med = (index.get(rxcui) if rxcui else None) or index.get(drug_key)
                if med is not None and med not in finding.medications:
                    finding.medications.append(med)

            self._db.add(finding)
            created.append(finding)

        return created, existing

    def _check_duplicates(
        self, patient_id: UUID, medications: list[Medication], now: datetime
    ) -> tuple[list[SafetyFinding], list[SafetyFinding]]:
        """Two active entries for the same drug.

        Usually a data-entry slip, occasionally a real double-dose risk when a
        brand and a generic are both on the list. Either way the patient
        should see it.
        """
        created: list[SafetyFinding] = []
        existing: list[SafetyFinding] = []

        groups: dict[str, list[Medication]] = {}
        for med in medications:
            key = med.rxcui or normalize_key(med.normalized_name or med.name_entered)
            if key:
                groups.setdefault(key, []).append(med)

        for key, group in groups.items():
            if len(group) < 2:
                continue

            dedupe = make_dedupe_key(patient_id, "duplicate", key)
            found = self._existing(dedupe)
            if found is not None:
                existing.append(found)
                continue

            names = ", ".join(sorted({m.name_entered for m in group}))
            finding = SafetyFinding(
                patient_id=patient_id,
                finding_type=FindingType.DUPLICATE_THERAPY,
                severity=Severity.MODERATE,
                status=FindingStatus.OPEN,
                title=f"Duplicate entry: {group[0].name_entered}",
                detail=(
                    f"{len(group)} active entries appear to be the same medication "
                    f"({names}). This may be a duplicate record, or it may mean the "
                    f"same medicine is being taken twice. Check with your pharmacist "
                    f"or healthcare provider."
                ),
                source_name="SafeMed rules",
                source_version="1.0",
                evidence={"medication_ids": [str(m.id) for m in group], "match_key": key},
                dedupe_key=dedupe,
                detected_at=now,
            )
            for med in group:
                finding.medications.append(med)

            self._db.add(finding)
            created.append(finding)

        return created, existing

    # ------------------------------------------------------------- publicly
    def evaluate_patient(
        self, patient_id: UUID, now: datetime | None = None
    ) -> EvaluationResult:
        """Run every check for one patient and persist new findings.

        Safe to call repeatedly: findings already reported are recognised and
        returned as `existing` rather than created again.
        """
        now = now or datetime.now(timezone.utc)
        medications = self._active_medications(patient_id)

        created: list[SafetyFinding] = []
        existing: list[SafetyFinding] = []

        for check in (self._check_interactions, self._check_duplicates):
            new, old = check(patient_id, medications, now)
            created.extend(new)
            existing.extend(old)

        self._db.flush()
        return EvaluationResult(created=created, existing=existing)
