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
