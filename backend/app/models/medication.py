"""Medications and their dosing schedules."""
import uuid
from datetime import datetime, time

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, uuid_pk
from app.models.enums import Frequency, MedicationStatus


class Medication(TimestampMixin, Base):
    __tablename__ = "medications"

    id: Mapped[uuid.UUID] = uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # What the user typed, kept verbatim. We never overwrite the patient's own
    # words with our interpretation of them.
    name_entered: Mapped[str] = mapped_column(String(300), nullable=False)

    # What RxNorm resolved it to. Nullable on purpose: if RxNorm is down or the
    # name is unrecognised, the medication is still saved. Core features must
    # never depend on an external service.
    rxcui: Mapped[str | None] = mapped_column(String(20), index=True)
    normalized_name: Mapped[str | None] = mapped_column(String(300))

    # National Drug Code - identifies the exact product AND manufacturer from
    # the bottle. This is what makes tiered recall matching possible.
    ndc: Mapped[str | None] = mapped_column(String(20), index=True)

    dose_amount: Mapped[str | None] = mapped_column(String(50))   # "500"
    dose_unit: Mapped[str | None] = mapped_column(String(50))     # "mg"
    notes: Mapped[str | None] = mapped_column(String(1000))

    status: Mapped[MedicationStatus] = mapped_column(
        Enum(MedicationStatus, name="medication_status"),
        default=MedicationStatus.ACTIVE,
        nullable=False,
    )
    started_on: Mapped[datetime | None] = mapped_column(Date)
    stopped_on: Mapped[datetime | None] = mapped_column(Date)

    patient: Mapped["User"] = relationship(back_populates="medications")
    schedules: Mapped[list["DoseSchedule"]] = relationship(
        back_populates="medication", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Medication {self.name_entered} rxcui={self.rxcui}>"


class DoseSchedule(TimestampMixin, Base):
    """One time of day a medication should be taken.

    Separate from Medication because "twice daily" is two rows, not one field.
    Dose events are generated from these.
    """

    __tablename__ = "dose_schedules"

    id: Mapped[uuid.UUID] = uuid_pk()
    medication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medications.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    time_of_day: Mapped[time] = mapped_column(Time, nullable=False)
    frequency: Mapped[Frequency] = mapped_column(
        Enum(Frequency, name="schedule_frequency"), default=Frequency.DAILY, nullable=False
    )
    # For WEEKLY schedules: "MON,WED,FRI". Null means every day.
    days_of_week: Mapped[str | None] = mapped_column(String(40))

    # How long after the scheduled time before an unconfirmed dose counts as
    # missed. Without this, a patient who takes a pill but forgets to tap gets
    # marked missed and their caregiver gets a false alarm.
    grace_minutes: Mapped[int] = mapped_column(default=120, nullable=False)

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    medication: Mapped["Medication"] = relationship(back_populates="schedules")
