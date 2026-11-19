"""Turns FDA recalls into SafetyFindings for affected patients."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    FindingStatus,
    FindingType,
    MedicationStatus,
    RecallMatch,
)
from app.models.medication import Medication
from app.models.safety import SafetyFinding
from app.services.recalls import (
    OpenFDARecallClient,
    RecallRecord,
    severity_for,
    match_medication,
)
from app.services.safety_engine import make_dedupe_key

logger = logging.getLogger(__name__)


class RecallMonitor:
    def __init__(self, db: Session, client: OpenFDARecallClient | None = None) -> None:
        self._db = db
        self._client = client or OpenFDARecallClient()

    def _active_medications(self) -> list[Medication]:
        stmt = select(Medication).where(Medication.status == MedicationStatus.ACTIVE)
        return list(self._db.execute(stmt).scalars().all())

    def _finding_for(
        self, recall: RecallRecord, medication: Medication, match: RecallMatch,
        now: datetime,
    ) -> SafetyFinding | None:
        # Keyed on the recall and the medication, never the time, so the hourly
        # poll does not re-report the same recall for ever.
        key = make_dedupe_key(
            medication.patient_id, "recall", recall.recall_number, str(medication.id)
        )
        existing = self._db.execute(
            select(SafetyFinding).where(SafetyFinding.dedupe_key == key)
        ).scalar_one_or_none()
        if existing is not None:
            return None

        if match == RecallMatch.CONFIRMED:
            title = f"Recall affects your {medication.name_entered}"
            detail = (
                f"The FDA has recorded a {recall.classification} recall "
                f"({recall.recall_number}) by {recall.recalling_firm} covering the "
                f"product you recorded. Reason given: {recall.reason_for_recall} "
            )
        else:
            title = f"Recall may affect your {medication.name_entered}"
            detail = (
                f"The FDA has recorded a {recall.classification} recall "
                f"({recall.recall_number}) by {recall.recalling_firm} for a product "
                f"containing this medicine. We cannot tell whether your supply is "
                f"affected, because the manufacturer code on your record does not "
                f"identify it. Check the label on your bottle against the recalling "
                f"firm: {recall.recalling_firm}. Reason given: {recall.reason_for_recall} "
            )

        detail += (
            "Contact your pharmacist or healthcare provider before changing anything. "
            "Do not stop taking a medication based on this message."
        )

        return SafetyFinding(
            patient_id=medication.patient_id,
            finding_type=FindingType.RECALL,
            severity=severity_for(match, recall.classification),
            status=FindingStatus.OPEN,
            title=title,
            detail=detail,
            source_name="openFDA",
            source_version=recall.report_date or "unknown",
            source_url=(
                "https://api.fda.gov/drug/enforcement.json?search=recall_number:"
                f'"{recall.recall_number}"'
            ),
            evidence={
                "recall_number": recall.recall_number,
                "classification": recall.classification,
                "recalling_firm": recall.recalling_firm,
                "product_description": recall.product_description[:500],
                "lot_info": recall.code_info[:500],
                "match_tier": match.value,
                "patient_ndc": medication.ndc,
                "recall_ndcs": recall.product_ndcs[:10],
            },
            recall_match=match,
            dedupe_key=key,
            detected_at=now,
        )

    def process(self, recalls: list[RecallRecord], now: datetime | None = None) -> list[SafetyFinding]:
        """Match a batch of recalls against every active medication."""
        now = now or datetime.now(timezone.utc)
        medications = self._active_medications()
        created: list[SafetyFinding] = []

        for recall in recalls:
            for medication in medications:
                match = match_medication(recall, medication)
                if match is None:
                    continue
                finding = self._finding_for(recall, medication, match, now)
                if finding is None:
                    continue
                finding.medications.append(medication)
                self._db.add(finding)
                created.append(finding)

        self._db.flush()
        return created

    def check_recent(self, days: int = 30) -> list[SafetyFinding]:
        recalls = self._client.recent(days=days)
        logger.info("openFDA returned %d recalls from the last %d days", len(recalls), days)
        return self.process(recalls)

    def simulate_for_drug(self, drug_name: str) -> list[SafetyFinding]:
        """Pull real historical recalls for one drug and process them.

        Used in the demo. Real recalls affecting our synthetic patients are
        rare, and a presentation cannot wait for one.
        """
        recalls = self._client.search_drug(drug_name)
        logger.info("openFDA returned %d recalls mentioning %r", len(recalls), drug_name)
        return self.process(recalls)
