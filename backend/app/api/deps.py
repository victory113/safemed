"""Authentication dependencies used by every protected endpoint."""
import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.enums import ConsentStatus, UserRole
from app.models.user import ConsentGrant, User
from app.services.audit import AuditAction, record_event

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def oauth2_scheme(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Pull the bearer token out of the Authorization header."""
    if credentials is None:
        raise _unauthorized("Not authenticated")
    return credentials.credentials


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Return the authenticated User, or raise HTTPException(401)."""
    user_id = decode_access_token(token)
    if user_id is None:
        raise _unauthorized("Invalid or expired token")
    try:
        user = db.get(User, uuid.UUID(user_id))
    except ValueError:
        raise _unauthorized("Invalid or expired token") from None
    if user is None or not user.is_active:
        raise _unauthorized("Invalid or expired token")
    return user


def require_role(*roles: UserRole):
    """Dependency factory: raise HTTPException(403) unless the current
    user's role is one of `roles`."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to do that",
            )
        return user

    return checker


def require_active_grant(
    patient_id: uuid.UUID,
    request: Request,
    caregiver: User = Depends(require_role(UserRole.CAREGIVER)),
    db: Session = Depends(get_db),
) -> User:
    """Return the patient only if this caregiver holds an ACTIVE grant for them.

    Use it on any route shaped /caregiver/patients/{patient_id}/... . The grant
    is looked up on every request, so revoking takes effect on the very next
    call. A pending, revoked or missing grant, and a patient id that does not
    exist, all give the same 403, so the response never confirms whether a
    particular patient exists.

    Every successful pass is written to the audit log (who looked at whom, and
    which route), so any caregiver view that uses this dependency is recorded
    without the view having to remember to do it. The row is committed here,
    not left to the view, because several views only read and never commit.
    A refused request is not recorded as a view: nothing was seen.
    """
    patient = db.scalar(
        select(User)
        .join(ConsentGrant, ConsentGrant.patient_id == User.id)
        .where(
            User.id == patient_id,
            ConsentGrant.caregiver_id == caregiver.id,
            ConsentGrant.status == ConsentStatus.ACTIVE,
        )
    )
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this patient",
        )

    record_event(
        db,
        action=AuditAction.PATIENT_RECORD_VIEWED,
        entity_type="patient",
        entity_id=patient.id,
        actor_id=caregiver.id,
        patient_id=patient.id,
        details={"method": request.method, "path": request.url.path},
    )
    db.commit()
    return patient
