"""Authentication dependencies used by every protected endpoint."""
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User

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