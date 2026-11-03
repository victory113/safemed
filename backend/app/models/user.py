"""Users and the consent that links a caregiver to a patient."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, uuid_pk
from app.models.enums import ConsentStatus, UserRole


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # A patient's own medications.
    medications: Mapped[list["Medication"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role.value})>"


class ConsentGrant(TimestampMixin, Base):
    """Permission for one caregiver to see one patient.

    This table IS the authorisation rule. A caregiver with no ACTIVE grant for
    a patient can see nothing about them, and revoking is a status change that
    leaves the history intact - we never delete the record of who had access.
    """

    __tablename__ = "consent_grants"
    __table_args__ = (
        UniqueConstraint("patient_id", "caregiver_id", name="uq_consent_patient_caregiver"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    caregiver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[ConsentStatus] = mapped_column(
        Enum(ConsentStatus, name="consent_status"),
        default=ConsentStatus.PENDING,
        nullable=False,
    )
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    patient: Mapped["User"] = relationship(foreign_keys=[patient_id])
    caregiver: Mapped["User"] = relationship(foreign_keys=[caregiver_id])
