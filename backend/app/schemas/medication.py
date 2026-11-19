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
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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
