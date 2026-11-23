"""Pydantic schemas for dose events and schedules."""
from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DoseStatus, Frequency


class DoseScheduleCreate(BaseModel):
    """One time of day a medication should be taken."""

    time_of_day: time
    frequency: Frequency = Frequency.DAILY
    days_of_week: str | None = Field(
        default=None,
        description='For WEEKLY schedules, e.g. "MON,WED,FRI". Null means every day.',
    )
    grace_minutes: int = Field(
        default=120,
        ge=0,
        le=1440,
        description=(
            "How long after the scheduled time an unconfirmed dose may remain "
            "before it counts as missed."
        ),
    )


class DoseScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    time_of_day: time
    frequency: Frequency
    days_of_week: str | None
    grace_minutes: int
    is_active: bool


class DoseRead(BaseModel):
    """One expected dose, as the frontend sees it.

    medication_name and the dose fields are flattened in from the related
    Medication so the UI can render a row without a second request.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    medication_id: UUID
    medication_name: str
    dose_amount: str | None
    dose_unit: str | None
    scheduled_for: datetime
    status: DoseStatus
    confirmed_at: datetime | None


class DoseSkip(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class AdherenceRead(BaseModel):
    """How reliably a patient has been taking their medication.

    `rate` is deliberately nullable. A patient with no resolved doses yet has
    no adherence rate, and that is not the same thing as 0%. Sending 0.0 would
    make a brand-new patient look like they had missed everything - which, on
    a caregiver's screen, is a false alarm manufactured by the API itself.

    Scheduled (still-future) doses are excluded from the denominator for the
    same reason: nobody should look non-adherent for not having reached
    tomorrow yet.
    """

    days: int = Field(description="Size of the window looked at, in days.")
    taken: int
    missed: int
    skipped: int = Field(
        description=(
            "Deliberate skips. Counted separately and excluded from the rate - "
            "a patient who was told to stop for a day did not fail to adhere."
        )
    )
    scheduled: int = Field(description="Doses still in the future.")
    resolved: int = Field(description="Denominator of the rate: taken + missed.")
    rate: float | None = Field(
        description="Share of resolved doses that were taken, 0.0-1.0, or null."
    )
