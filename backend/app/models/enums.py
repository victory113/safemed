"""Every fixed set of values used in the database.

Why enums instead of plain strings: the database itself rejects an invalid
value. A typo like "SEVER" fails at write time rather than silently creating a
severity nobody handles. These also become the allowed values in the API docs.
"""
import enum


class UserRole(str, enum.Enum):
    PATIENT = "PATIENT"
    CAREGIVER = "CAREGIVER"
    ADMIN = "ADMIN"


class ConsentStatus(str, enum.Enum):
    """A caregiver may only see a patient through an ACTIVE grant."""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class MedicationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    STOPPED = "STOPPED"


class Frequency(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


class DoseStatus(str, enum.Enum):
    """The dose state machine.

    SCHEDULED -> DUE -> TAKEN
                     -> MISSED   (grace period elapsed with no confirmation)
                     -> SKIPPED  (patient deliberately skipped it)
    """
    SCHEDULED = "SCHEDULED"
    DUE = "DUE"
    TAKEN = "TAKEN"
    MISSED = "MISSED"
    SKIPPED = "SKIPPED"


class FindingType(str, enum.Enum):
    INTERACTION = "INTERACTION"
    RECALL = "RECALL"
    DUPLICATE_THERAPY = "DUPLICATE_THERAPY"


class Severity(str, enum.Enum):
    """Drives who sees what, and how loudly.

    Taken from the source dataset, never inferred (FR-11). Two decisions read
    it: a caregiver is shown SEVERE findings only (FR-25), and the patient
    interface expands SEVERE while collapsing the rest (FR-35).

    There is no notification service. An earlier design routed alerts by
    severity through one, and the `notifications` table still carries the
    channel and delivery-status columns that design needed. Nothing writes a
    row: caregiver alerting is delivered by the dashboard, and the gap is
    recorded in FINAL_REPORT.md section 10.1 rather than left to be inferred
    from a comment pointing at a class that was never written.
    """
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"


class FindingStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class RecallMatch(str, enum.Enum):
    """Tiered recall matching - our defence against false alarms.

    CONFIRMED: the recall names the exact product (NDC) the patient holds.
    POSSIBLE:  same drug, manufacturer unknown. The patient is asked to check
               the label rather than being told they are affected.
    """
    CONFIRMED = "CONFIRMED"
    POSSIBLE = "POSSIBLE"


class NotificationChannel(str, enum.Enum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    SMS = "SMS"


class NotificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
