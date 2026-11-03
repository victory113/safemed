"""The append-only audit log."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import uuid_pk


class AuditEvent(Base):
    """Who did what, to what, and when.

    Append-only by convention: nothing in the application ever updates or
    deletes a row here. This is what lets the clinic - or a professor - verify
    that information was never silently changed.

    No TimestampMixin: an audit row is never updated, so updated_at would be
    misleading.
    """

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = uuid_pk()

    # Null when the actor is the system itself, e.g. the background worker.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    # Which patient's data was touched - the usual way this log is searched.
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    action: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)

    # Previous/new values, request origin, or why the worker acted.
    details: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )

    def __repr__(self) -> str:
        return f"<AuditEvent {self.action} {self.entity_type}>"
