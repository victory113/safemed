"""Safety findings produced by the rules engine."""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Table, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, uuid_pk
from app.models.enums import FindingStatus, FindingType, RecallMatch, Severity

# A finding can involve several medications (an interaction involves two).
finding_medications = Table(
    "finding_medications",
    Base.metadata,
    Column("finding_id", UUID(as_uuid=True),
           ForeignKey("safety_findings.id", ondelete="CASCADE"), primary_key=True),
    Column("medication_id", UUID(as_uuid=True),
           ForeignKey("medications.id", ondelete="CASCADE"), primary_key=True),
)


class SafetyFinding(TimestampMixin, Base):
    """A potential safety issue the deterministic engine found.

    Every finding records WHERE it came from (source_name) and WHICH VERSION of
    that data (source_version). That is what makes a finding auditable: a
    reviewer can go back to the exact dataset and verify it. "The AI said so"
    is not evidence; this is.
    """

    __tablename__ = "safety_findings"

    id: Mapped[uuid.UUID] = uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )

    finding_type: Mapped[FindingType] = mapped_column(
        Enum(FindingType, name="finding_type"), index=True, nullable=False
    )
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, name="finding_severity"), index=True, nullable=False
    )
    status: Mapped[FindingStatus] = mapped_column(
        Enum(FindingStatus, name="finding_status"),
        default=FindingStatus.OPEN, index=True, nullable=False,
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)

    # Provenance - the audit trail of the finding itself.
    source_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(80))
    source_url: Mapped[str | None] = mapped_column(String(500))
    evidence: Mapped[dict | None] = mapped_column(JSONB)

    # Only set for RECALL findings. CONFIRMED means the NDC matched exactly;
    # POSSIBLE means same drug, manufacturer unknown.
    recall_match: Mapped[RecallMatch | None] = mapped_column(
        Enum(RecallMatch, name="recall_match")
    )

    # Stops the background worker creating the same finding on every run.
    dedupe_key: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    # Written by the AI layer AFTER the finding exists. Nullable because the
    # finding must stand on its own when the AI is unavailable.
    ai_explanation: Mapped[str | None] = mapped_column(Text)
    ai_model: Mapped[str | None] = mapped_column(String(100))
    ai_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    medications: Mapped[list["Medication"]] = relationship(secondary=finding_medications)
    notifications: Mapped[list["Notification"]] = relationship(back_populates="finding")

    def __repr__(self) -> str:
        return f"<SafetyFinding {self.finding_type.value} {self.severity.value}>"
