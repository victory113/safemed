"""Safety finding endpoints."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.enums import FindingStatus
from app.models.safety import SafetyFinding
from app.models.user import User
from app.schemas.finding import FindingMedication, FindingRead
from app.services.safety_engine import SafetyEngine

router = APIRouter(prefix="/findings", tags=["safety"])


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


@router.get("", response_model=list[FindingRead])
def list_findings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Open findings for the signed-in patient, most serious first."""
    stmt = (
        select(SafetyFinding)
        .where(
            SafetyFinding.patient_id == current_user.id,
            SafetyFinding.status != FindingStatus.RESOLVED,
        )
        .options(selectinload(SafetyFinding.medications))
        .order_by(SafetyFinding.detected_at.desc())
    )
    findings = list(db.execute(stmt).scalars().all())

    order = {"SEVERE": 0, "MODERATE": 1, "MILD": 2}
    findings.sort(key=lambda f: order.get(f.severity.value, 3))
    return [_to_read(f) for f in findings]


@router.post("/re-evaluate", response_model=list[FindingRead])
def re_evaluate(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run the safety engine now. Used by the demo and for manual re-checks."""
    SafetyEngine(db).evaluate_patient(current_user.id)
    db.commit()
    return list_findings(db=db, current_user=current_user)


@router.post("/{finding_id}/acknowledge", response_model=FindingRead)
def acknowledge(
    finding_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a finding as seen. The finding is never deleted."""
    stmt = (
        select(SafetyFinding)
        .where(
            SafetyFinding.id == finding_id,
            SafetyFinding.patient_id == current_user.id,
        )
        .options(selectinload(SafetyFinding.medications))
    )
    finding = db.execute(stmt).scalar_one_or_none()
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")

    finding.status = FindingStatus.ACKNOWLEDGED
    finding.acknowledged_at = datetime.now(timezone.utc)
    finding.acknowledged_by_id = current_user.id
    db.commit()
    db.refresh(finding)
    return _to_read(finding)
