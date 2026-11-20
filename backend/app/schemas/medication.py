"""Pydantic schemas for medications.

A schema is the shape of data crossing the API boundary. It is NOT the
database model:

* the model says how a medication is stored
* the schema says what a client may send, and what we agree to send back

Keeping them separate means we can store fields we never expose, and reject
fields a client is not allowed to set (nobody should be able to POST their own
`id` or `created_at`).

Shapes here match docs/API_CONTRACT.md section 2. Change one, change both.
"""
from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import MedicationStatus


class MedicationCreate(BaseModel):
    """What a client may send to create a medication.

    Only the name is required. Everything else is optional because a patient
    reading a label may not have all of it, and a half-complete record is far
    better than no record.
    """

    name_entered: str = Field(min_length=1, max_length=300)
    dose_amount: str | None = Field(default=None, max_length=50)
    dose_unit: str | None = Field(default=None, max_length=50)
    ndc: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=1000)
    started_on: date | None = None

    # Scheduling belongs to adding a medication, not to a separate second
    # step. A medication recorded without times has nothing to log against, so
    # the patient's daily check-in would simply be empty - and the feature
    # would look broken rather than unconfigured.
    times: list[time] = Field(
        default_factory=list,
        max_length=12,
        description=(
            'Times of day this is taken, e.g. ["08:00", "20:00"]. Each one '
            "becomes a dose schedule. Duplicates are ignored."
        ),
    )
    grace_minutes: int = Field(
        default=120,
        ge=0,
        le=1440,
        description=(
            "How long after a scheduled time an unconfirmed dose may remain "
            "before it counts as missed. Applies to every time above."
        ),
    )

    @field_validator("times")
    @classmethod
    def drop_duplicate_times(cls, value: list[time]) -> list[time]:
        """Two schedules at the same time would generate two doses for one
        pill, and the patient would be asked to confirm the same thing twice.

        Order is preserved rather than sorted, so the response reflects what
        the client sent.
        """
        seen: set[time] = set()
        unique: list[time] = []
        for at in value:
            if at not in seen:
                seen.add(at)
                unique.append(at)
        return unique


class MedicationUpdate(BaseModel):
    """A partial update. Every field is optional.

    A field left out is untouched. This is why PATCH is the right verb - PUT
    would mean "replace the whole thing", and omitting a field would wipe it.
    """

    dose_amount: str | None = Field(default=None, max_length=50)
    dose_unit: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=1000)
    status: MedicationStatus | None = None
    stopped_on: date | None = None


class MedicationRead(BaseModel):
    """What we send back.

    from_attributes=True lets FastAPI build this straight from a SQLAlchemy
    object, reading attributes rather than dictionary keys.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name_entered: str
    normalized_name: str | None
    rxcui: str | None
    ndc: str | None
    dose_amount: str | None
    dose_unit: str | None
    notes: str | None
    status: MedicationStatus
    started_on: date | None
    stopped_on: date | None
    created_at: datetime
