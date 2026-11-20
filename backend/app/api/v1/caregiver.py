"""What a caregiver may see about a patient who has granted them access.

Every route here depends on `require_active_grant`, which re-checks the grant
on each request, so revoking consent takes effect immediately.

THE SEVERITY RULE, which is the point of this file
--------------------------------------------------
A caregiver sees SEVERE findings only. The patient sees all of them.

That is not an oversight, it is the feature. Our own demonstration data
produces ten findings from five ordinary medications. A caregiver who was sent
all ten would be reading mostly minor interactions, and within a week would
stop reading any of them - at which point the one that mattered would be
missed too. Alert fatigue is the failure mode this project exists to avoid, so
the filter lives in the endpoint rather than being left to the interface.

The patient keeps the full picture; the caregiver gets the subset that is
worth a phone call.

(This file is kept separate from consent.py, which owns the grant lifecycle
and the patient/medication views. Splitting them keeps the authorisation rule
in one place and these read-only views in another.)
"""
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_active_grant
from app.db.session import get_db
from app.models.enums import DoseStatus, FindingStatus, Severity
from app.models.safety import SafetyFinding
from app.models.user import User
from app.repositories import dose as dose_repo
from app.schemas.dose import AdherenceRead, DoseRead
from app.schemas.finding import FindingMedication, FindingRead
from app.services import dose_scheduler as scheduler

router = APIRouter(prefix="/caregiver", tags=["caregiver"])


def _to_read(finding: SafetyFinding) -> FindingRead:
    return FindingRead(
        id=finding.id,
        finding_type=finding.finding_type,
        severity=finding.severity,
        status=finding.status,
        title=finding.title,
        detail=finding.detail,
        source_name=finding.source_name,
        source_version=finding.source_version,
        recall_match=finding.recall_match,
        ai_explanation=finding.ai_explanation,
        detected_at=finding.detected_at,
        acknowledged_at=finding.acknowledged_at,
        medications=[
            FindingMedication(id=m.id, name=m.name_entered) for m in finding.medications
        ],
    )


def _dose_to_read(event) -> DoseRead:
    return DoseRead(
        id=event.id,
        medication_id=event.medication_id,
        medication_name=event.medication.name_entered,
        dose_amount=event.medication.dose_amount,
        dose_unit=event.medication.dose_unit,
        scheduled_for=event.scheduled_for,
        status=event.status,
        confirmed_at=event.confirmed_at,
    )


def _window(days: int) -> tuple[datetime, datetime]:
    end = datetime.combine(date.today() + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return end - timedelta(days=days), end


@router.get("/patients/{patient_id}/findings", response_model=list[FindingRead])
def patient_findings(
    db: Session = Depends(get_db),
    patient: User = Depends(require_active_grant),
):
    """The serious safety findings for this patient.

    SEVERE only - see the note at the top of this file. Acknowledged findings
    are included so a caregiver can see that the patient has read something,
    but resolved ones are dropped.
    """
    stmt = (
        select(SafetyFinding)
        .where(
            SafetyFinding.patient_id == patient.id,
            SafetyFinding.severity == Severity.SEVERE,
            SafetyFinding.status != FindingStatus.RESOLVED,
        )
        .options(selectinload(SafetyFinding.medications))
        .order_by(SafetyFinding.detected_at.desc())
    )
    return [_to_read(f) for f in db.execute(stmt).scalars().all()]


@router.get("/patients/{patient_id}/doses/today", response_model=list[DoseRead])
def patient_doses_today(
    db: Session = Depends(get_db),
    patient: User = Depends(require_active_grant),
):
    """Today's doses, read-only.

    Unlike the patient's own /doses/today this does not generate missing rows.
    A caregiver looking at the screen should not cause the patient's record to
    be written to - what they see is whatever the patient's own app has
    already created.
    """
    start = datetime.combine(date.today(), time.min, tzinfo=timezone.utc)
    events = dose_repo.events_between(
        db, patient_id=patient.id, start=start, end=start + timedelta(days=1)
    )
    scheduler.refresh_statuses(db, events)
    db.commit()
    return [_dose_to_read(e) for e in events]


@router.get("/patients/{patient_id}/adherence", response_model=AdherenceRead)
def patient_adherence(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    patient: User = Depends(require_active_grant),
):
    """How reliably this patient has been taking their medication.

    The null-rather-than-zero rule matters most here, because this is the
    screen where a 0% would actually cause someone to pick up the phone about
    a patient who has simply not logged anything yet.
    """
    start, end = _window(days)
    events = dose_repo.events_between(db, patient_id=patient.id, start=start, end=end)
    scheduler.refresh_statuses(db, events)
    db.commit()

    counts = Counter(e.status for e in events)
    taken = counts[DoseStatus.TAKEN]
    missed = counts[DoseStatus.MISSED]

    return AdherenceRead(
        days=days,
        taken=taken,
        missed=missed,
        skipped=counts[DoseStatus.SKIPPED],
        scheduled=counts[DoseStatus.SCHEDULED] + counts[DoseStatus.DUE],
        resolved=taken + missed,
        rate=scheduler.adherence_rate(events),
    )
