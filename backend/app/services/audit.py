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
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent

logger = logging.getLogger(__name__)


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
    # A caregiver asked for a record they are not allowed to see. Recorded
    # under its own action rather than as a "view", because nothing was
    # shown - but a refused attempt is exactly what an audit log is read for.
    PATIENT_RECORD_ACCESS_DENIED = "patient_record.access_denied"


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


def try_record_event(db: Session, **kwargs: Any) -> AuditEvent | None:
    """Record an event and commit it, but never raise.

    Use this on a **read** path. `record_event` is the right function when the
    audit row must live or die with the action it describes - a consent change
    that cannot be audited should not happen at all. A read is different: if
    the audit write fails, refusing to show a caregiver that their mother has
    a severe interaction is the worse of the two outcomes. So the read is
    served and the failure is made loud in the logs instead of silent.

    That is a deliberate trade, and it is the one place in the system where
    something happens without a guaranteed audit row. A system with a stricter
    obligation - a hospital rather than a student project - would make the
    opposite call and refuse the read.

    The write goes inside a SAVEPOINT. A failed flush otherwise leaves the
    whole session unusable, and the route handler still has its own queries to
    run afterwards - so without this, a broken audit write would surface as a
    confusing failure in the *next* query rather than where it happened. The
    savepoint confines the damage to the audit insert and nothing else.
    """
    try:
        with db.begin_nested():  # SAVEPOINT: rolled back alone if this fails
            audit_event = record_event(db, **kwargs)
    except Exception:
        logger.exception(
            "AUDIT WRITE FAILED for action=%s entity=%s - the request was still "
            "served. This needs investigating: an unaudited read has happened.",
            kwargs.get("action"),
            kwargs.get("entity_type"),
        )
        return None

    try:
        db.commit()
        return audit_event
    except Exception:
        logger.exception(
            "AUDIT COMMIT FAILED for action=%s - the request was still served.",
            kwargs.get("action"),
        )
        return None


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
