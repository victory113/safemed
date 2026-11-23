"""The audit log writer.

Every meaningful action - a medication changed, consent given or revoked, a
caregiver reading a patient's record - leaves one row in `audit_events`: who
did what, to what, and when.

Two rules this module exists to enforce:

1. **Append-only.** The only thing you can do with an audit row is add one.
   Nothing here updates or deletes, and the guards below make the ORM refuse
   if any other code tries. That is what lets us show that history was never
   silently changed.

2. **Written in the caller's transaction.** `record_event` adds the row and
   flushes it, but never commits. The caller's own commit saves the action
   and its audit row together; if the action fails and rolls back, so does
   the audit row. There is never an audit entry for something that did not
   happen, and never a change with no entry.

What goes in `details`: ids, which fields changed, previous and new values of
non-sensitive fields, why a background job acted. Never passwords, tokens, or
anything that is not already safe to show the patient.
"""
from typing import Any
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


class AuditAction:
    """The action names we record. One place, so names stay consistent and a
    search for "everything that happened to this patient" is predictable."""

    # Consent
    CONSENT_INVITED = "consent.invited"
    CONSENT_ACCEPTED = "consent.accepted"
    CONSENT_REVOKED = "consent.revoked"

    # Medications
    MEDICATION_CREATED = "medication.created"
    MEDICATION_UPDATED = "medication.updated"
    MEDICATION_STOPPED = "medication.stopped"

    # Someone looking at a patient's record (a caregiver, for example)
    PATIENT_RECORD_VIEWED = "patient_record.viewed"


class AuditLogImmutableError(RuntimeError):
    """Raised when code tries to change or delete an audit row."""


def record_event(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: UUID | None = None,
    actor_id: UUID | None = None,
    patient_id: UUID | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    """Add one audit row and flush it. Does NOT commit - see the module note.

    actor_id    who did it; None when the system itself acted (a worker)
    patient_id  whose data was touched; the usual way this log is searched
    entity_type what kind of thing, e.g. "medication", "consent_grant"
    entity_id   which one
    details     JSON-able extras: changed fields, request origin, a reason
    """
    if not action or not action.strip():
        raise ValueError("An audit event needs an action")
    if not entity_type or not entity_type.strip():
        raise ValueError("An audit event needs an entity_type")

    audit_event = AuditEvent(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        patient_id=patient_id,
        details=details,
    )
    db.add(audit_event)
    db.flush()  # assigns id and created_at; the caller's commit saves it
    return audit_event


# ---- Append-only guards -------------------------------------------------
#
# Registered when this module is imported, which happens whenever anything
# writes an audit event. They turn "nothing updates or deletes an audit row"
# from a convention into something the ORM enforces.


@event.listens_for(AuditEvent, "before_update")
def _refuse_update(mapper, connection, target) -> None:
    raise AuditLogImmutableError("Audit events are append-only and cannot be changed")


@event.listens_for(AuditEvent, "before_delete")
def _refuse_delete(mapper, connection, target) -> None:
    raise AuditLogImmutableError("Audit events are append-only and cannot be deleted")
