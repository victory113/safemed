"""Dose events - the daily 'I took my medication' log."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, uuid_pk
from app.models.enums import DoseStatus


class DoseEvent(TimestampMixin, Base):
    """One expected dose at one point in time.

    Rows are generated ahead of time from DoseSchedule, then updated as the
    patient confirms them. Storing every expected dose - not just the taken
    ones - is what lets us detect a MISSED dose at all.
    """

    __tablename__ = "dose_events"
    __table_args__ = (
        # Makes dose generation idempotent: running the generator twice cannot
        # create duplicate rows for the same scheduled moment.
        UniqueConstraint("schedule_id", "scheduled_for", name="uq_dose_schedule_time"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    medication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medications.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dose_schedules.id", ondelete="SET NULL"), index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )

    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    status: Mapped[DoseStatus] = mapped_column(
        Enum(DoseStatus, name="dose_status"), default=DoseStatus.SCHEDULED,
        index=True, nullable=False,
    )

    # When the patient actually confirmed. Distinct from scheduled_for so we
    # can report "taken, 40 minutes late" rather than just "taken".
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recorded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(String(500))

    medication: Mapped["Medication"] = relationship()

    def __repr__(self) -> str:
        return f"<DoseEvent {self.scheduled_for} {self.status.value}>"
