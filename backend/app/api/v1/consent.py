"""Consent grants and the caregiver views they unlock.

A caregiver can see a patient only through an ACTIVE grant. The flow:

    patient invites caregiver  -> grant is PENDING
    caregiver accepts          -> grant is ACTIVE   (access starts)
    either side revokes        -> grant is REVOKED  (access stops at once)

Revoking never deletes the row: we keep the record of who had access and when.
The unique (patient, caregiver) pair means a re-invite after a revoke reuses
the same row and puts it back to PENDING.
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_active_grant, require_role
from app.db.session import get_db
from app.models.enums import ConsentStatus, UserRole
from app.models.user import ConsentGrant, User
from app.repositories import medication as medication_repo
from app.schemas.medication import MedicationRead
from app.services.audit import AuditAction, record_event

router = APIRouter(prefix="/consent", tags=["consent"])
caregiver_router = APIRouter(prefix="/caregiver", tags=["caregiver"])


# ---- Schemas -----------------------------------------------------------


class InviteRequest(BaseModel):
    caregiver_email: EmailStr


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str


class ConsentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: ConsentStatus
    patient: PersonOut
    caregiver: PersonOut
    granted_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class CaregiverPatientOut(BaseModel):
    """A patient a caregiver may see, with when access began."""

    id: UUID
    email: EmailStr
    full_name: str
    granted_at: datetime | None


# ---- Consent flow ------------------------------------------------------


@router.post("/invitations", response_model=ConsentOut, status_code=status.HTTP_201_CREATED)
def invite_caregiver(
    payload: InviteRequest,
    db: Session = Depends(get_db),
    patient: User = Depends(require_role(UserRole.PATIENT)),
):
    """A patient invites a caregiver by email. The grant starts PENDING."""
    caregiver = db.scalar(
        select(User).where(
            func.lower(User.email) == payload.caregiver_email.lower(),
            User.role == UserRole.CAREGIVER,
            User.is_active.is_(True),
        )
    )
    if caregiver is None:
        # Same message for "no such email" and "not a caregiver account".
        raise HTTPException(status_code=404, detail="No caregiver account found with that email")

    grant = db.scalar(
        select(ConsentGrant).where(
            ConsentGrant.patient_id == patient.id,
            ConsentGrant.caregiver_id == caregiver.id,
        )
    )
    if grant is None:
        grant = ConsentGrant(
            patient_id=patient.id, caregiver_id=caregiver.id, status=ConsentStatus.PENDING
        )
        db.add(grant)
    elif grant.status == ConsentStatus.REVOKED:
        # Re-inviting after a revoke: same row, back to PENDING.
        grant.status = ConsentStatus.PENDING
        grant.granted_at = None
        grant.revoked_at = None
    else:
        raise HTTPException(
            status_code=400, detail="This caregiver has already been invited"
        )

    try:
        db.flush()  # assigns the grant its id and surfaces a duplicate-pair error
        record_event(
            db,
            action=AuditAction.CONSENT_INVITED,
            entity_type="consent_grant",
            entity_id=grant.id,
            actor_id=patient.id,
            patient_id=patient.id,
            details={"caregiver_id": str(caregiver.id)},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="This caregiver has already been invited"
        ) from None
    db.refresh(grant)
    return grant


@router.get("", response_model=list[ConsentOut])
def list_grants(
    status_filter: ConsentStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.PATIENT, UserRole.CAREGIVER)),
):
    """A patient sees the grants they have given; a caregiver sees the ones
    offered to them."""
    owner_column = (
        ConsentGrant.patient_id if user.role == UserRole.PATIENT else ConsentGrant.caregiver_id
    )
    stmt = select(ConsentGrant).where(owner_column == user.id)
    if status_filter is not None:
        stmt = stmt.where(ConsentGrant.status == status_filter)
    stmt = stmt.order_by(ConsentGrant.created_at.desc())
    return list(db.scalars(stmt).all())


@router.post("/{grant_id}/accept", response_model=ConsentOut)
def accept_invitation(
    grant_id: UUID,
    db: Session = Depends(get_db),
    caregiver: User = Depends(require_role(UserRole.CAREGIVER)),
):
    """The invited caregiver accepts. Access starts now."""
    grant = db.scalar(
        select(ConsentGrant).where(
            ConsentGrant.id == grant_id, ConsentGrant.caregiver_id == caregiver.id
        )
    )
    if grant is None:
        # 404, not 403: do not confirm that someone else's grant exists.
        raise HTTPException(status_code=404, detail="Invitation not found")
    if grant.status != ConsentStatus.PENDING:
        raise HTTPException(
            status_code=400, detail="Only a pending invitation can be accepted"
        )

    grant.status = ConsentStatus.ACTIVE
    grant.granted_at = datetime.now(timezone.utc)
    record_event(
        db,
        action=AuditAction.CONSENT_ACCEPTED,
        entity_type="consent_grant",
        entity_id=grant.id,
        actor_id=caregiver.id,
        patient_id=grant.patient_id,
        details={"caregiver_id": str(caregiver.id)},
    )
    db.commit()
    db.refresh(grant)
    return grant


@router.post("/{grant_id}/revoke", response_model=ConsentOut)
def revoke_grant(
    grant_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.PATIENT, UserRole.CAREGIVER)),
):
    """Revoke access. The patient can withdraw consent; the caregiver can
    decline an invitation or step away. The row is kept."""
    grant = db.scalar(
        select(ConsentGrant).where(
            ConsentGrant.id == grant_id,
            or_(ConsentGrant.patient_id == user.id, ConsentGrant.caregiver_id == user.id),
        )
    )
    if grant is None:
        raise HTTPException(status_code=404, detail="Grant not found")
    if grant.status == ConsentStatus.REVOKED:
        raise HTTPException(status_code=400, detail="This grant is already revoked")

    previous_status = grant.status
    grant.status = ConsentStatus.REVOKED
    grant.revoked_at = datetime.now(timezone.utc)
    record_event(
        db,
        action=AuditAction.CONSENT_REVOKED,
        entity_type="consent_grant",
        entity_id=grant.id,
        actor_id=user.id,
        patient_id=grant.patient_id,
        details={
            "caregiver_id": str(grant.caregiver_id),
            "revoked_by": user.role.value,
            "previous_status": previous_status.value,
        },
    )
    db.commit()
    db.refresh(grant)
    return grant


# ---- Caregiver views (only through an ACTIVE grant) --------------------


@caregiver_router.get("/patients", response_model=list[CaregiverPatientOut])
def my_patients(
    db: Session = Depends(get_db),
    caregiver: User = Depends(require_role(UserRole.CAREGIVER)),
):
    """The patients this caregiver may currently see."""
    rows = db.execute(
        select(User, ConsentGrant.granted_at)
        .join(ConsentGrant, ConsentGrant.patient_id == User.id)
        .where(
            ConsentGrant.caregiver_id == caregiver.id,
            ConsentGrant.status == ConsentStatus.ACTIVE,
        )
        .order_by(User.full_name)
    ).all()
    return [
        CaregiverPatientOut(
            id=patient.id,
            email=patient.email,
            full_name=patient.full_name,
            granted_at=granted_at,
        )
        for patient, granted_at in rows
    ]


@caregiver_router.get(
    "/patients/{patient_id}/medications", response_model=list[MedicationRead]
)
def patient_medications(
    status_filter: str = Query("ACTIVE", alias="status", pattern="^(ACTIVE|ALL)$"),
    db: Session = Depends(get_db),
    patient: User = Depends(require_active_grant),
):
    """A patient's medications, read-only, for a caregiver with an ACTIVE grant."""
    return medication_repo.list_for_patient(
        db, patient_id=patient.id, include_stopped=(status_filter == "ALL")
    )
