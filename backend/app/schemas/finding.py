"""Schemas for safety findings."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import FindingStatus, FindingType, RecallMatch, Severity


class FindingMedication(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class FindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    finding_type: FindingType
    severity: Severity
    status: FindingStatus
    title: str
    detail: str
    source_name: str
    source_version: str | None
    recall_match: RecallMatch | None

    # Nullable on purpose. When the AI is unavailable the finding still stands
    # and the UI shows `detail` instead. The schema makes that explicit so no
    # frontend code assumes an explanation is always present.
    ai_explanation: str | None

    detected_at: datetime
    acknowledged_at: datetime | None
    medications: list[FindingMedication]
